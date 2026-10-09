// SPDX-License-Identifier: AGPL-3.0-only

#include "kis_segito_ui.h"

#include <algorithm>
#include <cctype>
#include <climits>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <strings.h>

#include <esp_attr.h>
#include <esp_heap_caps.h>
#include <esp_system.h>
#include <esp_http_client.h>
#include <esp_rom_crc.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <misc/cache/instance/lv_image_cache.h>
#include <misc/cache/instance/lv_image_header_cache.h>

#include "esphome/components/json/json_util.h"
#include "esphome/core/hal.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"
#include "esphome/core/application.h"
#include "esphome/core/defines.h"
#ifdef USE_API
#include "esphome/components/api/api_server.h"
#endif

namespace esphome::kis_segito_ui {

static const char *const TAG = "kis_segito_ui";

// PSRAM always kept free for LVGL's own work (layers, image transforms): slot
// snapshots and picture downloads are skipped instead of eating into it.
static constexpr size_t PSRAM_RESERVE = 384 * 1024;
// Downloaded pictures nothing shows are kept in PSRAM up to this size (the
// least recently used go first); the flash cache brings the others back.
static constexpr size_t PHOTO_KEEP_UNUSED = 1024 * 1024;

static size_t psram_largest_block() { return heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT); }

static bool psram_can_spare(size_t bytes) { return psram_largest_block() >= bytes + PSRAM_RESERVE; }

// Whether a block of this size can be allocated now (with a little room left).
static bool psram_has(size_t bytes) { return psram_largest_block() >= bytes + 64 * 1024; }

// Icons that are not compiled into the firmware (assets/device_assets.json,
// "_online"): the knob downloads them from Home Assistant when it shows them.
static bool is_online_icon(const std::string &key) {
  static const char *const PREFIXES[] = {"routine_", "task_", "reward_", "test_avatar_"};
  for (const char *prefix : PREFIXES) {
    if (key.rfind(prefix, 0) == 0)
      return true;
  }
  return false;
}


// Carousel slots are drawn inside this window: everything outside it is under
// the opaque band of the time track, so it never needs drawing while a
// carousel slides.
static constexpr int WIN_X = 44, WIN_Y = 44, WIN_END = 436;

// A carousel item is drawn once into this ARGB8888 buffer (allocated once)
// and kept as a picture cropped to its content (ItemPic).
static constexpr int SNAP_MAX_W = 300, SNAP_MAX_H = 410;
static lv_draw_buf_t *g_snap_tmp = nullptr;

// Item pictures get blocks in steps of this size, so a freed block is reused
// by a later picture and the memory does not break up into small pieces.
static constexpr size_t ITEM_BLOCK_STEP = 32 * 1024;

static bool snapshot_tmp_ready() {
  if (g_snap_tmp == nullptr)
    g_snap_tmp = lv_draw_buf_create(SNAP_MAX_W, SNAP_MAX_H, LV_COLOR_FORMAT_ARGB8888, LV_STRIDE_AUTO);
  return g_snap_tmp != nullptr;
}

// A drawn carousel item (RGB565A8, cropped to its content), shared by the
// cache and the slots showing it; freed when neither needs it any more.
struct ItemPic {
  lv_draw_buf_t *buf{nullptr};
  int x0{0}, y0{0};  // position of the crop in the slot
  std::set<std::string> keys;  // downloaded pictures it shows
  size_t bytes() const { return this->buf == nullptr ? 0 : this->buf->data_size; }
  ~ItemPic() {
    if (this->buf != nullptr) {
      lv_image_cache_drop(this->buf);
      lv_image_header_cache_drop(this->buf);
      lv_draw_buf_destroy(this->buf);
    }
  }
};

// The not fully transparent part of an ARGB8888 snapshot as a new RGB565A8
// picture of exactly that size; nullptr when nothing is visible or there is
// no memory.
static std::shared_ptr<ItemPic> crop_item(const lv_draw_buf_t *src) {
  const int w = src->header.w, h = src->header.h;
  const uint32_t sstride = src->header.stride;
  int minx = w, miny = h, maxx = -1, maxy = -1;
  for (int y = 0; y < h; y++) {
    const uint8_t *row = src->data + y * sstride;
    for (int x = 0; x < w; x++) {
      if (row[x * 4 + 3] != 0) {
        minx = std::min(minx, x);
        maxx = std::max(maxx, x);
        miny = std::min(miny, y);
        maxy = y;
      }
    }
  }
  if (maxx < 0)
    return nullptr;
  const int cw = maxx - minx + 1, ch = maxy - miny + 1;
  auto pic = std::make_shared<ItemPic>();
  // The block: the picture's size rounded up to ITEM_BLOCK_STEP, as rows of
  // the full snapshot width.
  const size_t block = (static_cast<size_t>(cw) * ch * 3 + ITEM_BLOCK_STEP - 1) / ITEM_BLOCK_STEP * ITEM_BLOCK_STEP;
  const uint32_t rows = (block + SNAP_MAX_W * 3 - 1) / (SNAP_MAX_W * 3);
  pic->buf = lv_draw_buf_create(SNAP_MAX_W, rows, LV_COLOR_FORMAT_RGB565A8, SNAP_MAX_W * 2);
  if (pic->buf == nullptr)
    return nullptr;
  if (lv_draw_buf_reshape(pic->buf, LV_COLOR_FORMAT_RGB565A8, cw, ch, cw * 2) == nullptr)
    return nullptr;
  uint8_t *alpha = pic->buf->data + cw * 2 * ch;
  for (int y = 0; y < ch; y++) {
    const uint8_t *s = src->data + (y + miny) * sstride + minx * 4;
    auto *d = reinterpret_cast<uint16_t *>(pic->buf->data + y * cw * 2);
    uint8_t *a = alpha + y * cw;
    for (int x = 0; x < cw; x++, s += 4) {
      d[x] = static_cast<uint16_t>(((s[2] & 0xF8) << 8) | ((s[1] & 0xFC) << 3) | (s[0] >> 3));
      a[x] = s[3];
    }
  }
  pic->x0 = minx;
  pic->y0 = miny;
  return pic;
}

static void blend_into(lv_draw_buf_t *canvas, const lv_image_dsc_t *src, int x, int y, int opa = 255);

// Carousel items already drawn, by their content (Carousel::sig): an item
// that comes back is shown from here instead of being drawn again. Pictures
// on screen are always kept; of the others, the least recently used go when
// the budget is full or memory is needed for downloaded pictures.
struct CacheEntry {
  std::string sig;
  std::shared_ptr<ItemPic> pic;
  uint32_t used_ms;
};
static std::vector<CacheEntry> g_pic_cache;
static constexpr size_t PIC_CACHE_BYTES = 1300 * 1024;  // on screen included

static std::shared_ptr<ItemPic> pic_cache_find(const std::string &sig) {
  for (auto &c : g_pic_cache) {
    if (c.sig == sig) {
      c.used_ms = millis();
      return c.pic;
    }
  }
  return nullptr;
}

// Drops unused pictures (oldest first) until the cache is within its budget
// and `free_bytes` more can be allocated.
static void pic_cache_trim(size_t free_bytes) {
  while (true) {
    size_t total = 0;
    for (const auto &c : g_pic_cache)
      total += c.pic->bytes();
    if (total <= PIC_CACHE_BYTES && psram_has(free_bytes))
      return;
    auto oldest = g_pic_cache.end();
    for (auto it = g_pic_cache.begin(); it != g_pic_cache.end(); ++it) {
      if (it->pic.use_count() == 1 && (oldest == g_pic_cache.end() || it->used_ms < oldest->used_ms))
        oldest = it;
    }
    if (oldest == g_pic_cache.end())
      return;  // everything left is on screen
    g_pic_cache.erase(oldest);
  }
}

static void pic_cache_put(const std::string &sig, const std::shared_ptr<ItemPic> &pic) {
  g_pic_cache.push_back({sig, pic, millis()});
  pic_cache_trim(0);
}

// While a carousel slot is filled: how many downloaded pictures it needed
// that are not here yet (such an item is not stored).
static int g_fill_missing = 0;

// While a carousel slot is filled: collects the downloaded pictures it uses.
static std::set<std::string> *g_fill_keys = nullptr;

// Frame statistics while a carousel slides (debug log).
static uint32_t g_slide_frames = 0, g_slide_render_ms = 0, g_refr_start = 0;
static uint32_t g_slide_px = 0, g_slide_flush_us = 0, g_flush_start_us = 0;
static bool g_slide_measure = false;

static void log_psram(const char *when) {
  ESP_LOGI(TAG, "PSRAM %s: %u KB free, largest block %u KB", when,
           (unsigned) (heap_caps_get_free_size(MALLOC_CAP_SPIRAM) / 1024), (unsigned) (psram_largest_block() / 1024));
}

static constexpr int SCREEN = 480;
static constexpr int CENTER = SCREEN / 2;
static constexpr uint32_t BASE_BG = 0x1B2140;  // deep navy
static constexpr uint32_t TRACK_DIM = 0x3A4066;
static constexpr uint32_t ZONE_OK = 0x6BCB77;
static constexpr uint32_t ZONE_WARN = 0xFF9F43;
static constexpr uint32_t ZONE_LATE = 0xFF6B6B;
static constexpr uint32_t ZONE_DEPOSIT = 0x6BCB77;   // tokens into the piggy bank
static constexpr uint32_t ZONE_WITHDRAW = 0xFF9F43;  // tokens out of it
// Time track geometry: outer edge radius and width of each arc (an LVGL arc is
// drawn inwards from its outer edge).
static constexpr int OUTER_R = 222;  // outer (shared) track
static constexpr int OUTER_W = 14;
static constexpr int OUTER_MID = OUTER_R - OUTER_W / 2;
static constexpr int INNER_R = 203;  // inner (child) track, 5 px inside the outer one
static constexpr int INNER_W = 6;
static constexpr int INNER_MID = INNER_R - INNER_W / 2;
static constexpr int BAND_R = 196;   // the track band is solid from here outwards
static constexpr int FADE_W = 6;     // soft inner edge of the band

// Deterministic pseudo-random numbers for pile jitter.
static uint32_t hash32(uint32_t x) {
  x ^= x >> 16;
  x *= 0x7feb352d;
  x ^= x >> 15;
  x *= 0x846ca68b;
  x ^= x >> 16;
  return x;
}

static void remove_defaults(lv_obj_t *obj) {
  lv_obj_remove_style_all(obj);
  lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_remove_flag(obj, LV_OBJ_FLAG_CLICKABLE);
}

// ---------------------------------------------------------------- Carousel

int Carousel::wrap_(int index) const { return ((index % this->count_) + this->count_) % this->count_; }

void Carousel::create(lv_obj_t *parent, int count, int selected, int slot_w, int slot_h, int y, int spacing,
                      FillFn fill, uint32_t anim_ms, bool snapshot) {
  this->release();
  this->snapshot_ = snapshot;
  this->count_ = std::max(count, 1);
  this->selected_ = this->wrap_(selected);
  this->slot_w_ = slot_w;
  this->slot_h_ = slot_h;
  this->y_ = y;
  this->spacing_ = spacing;
  this->fill_ = std::move(fill);
  this->anim_ms_ = anim_ms;
  // The slots move inside a window that clips them to the inner circle's
  // square, so a slide redraws only that area.
  const int top = std::max(y, WIN_Y);
  this->window_ = lv_obj_create(parent);
  remove_defaults(this->window_);
  lv_obj_set_pos(this->window_, WIN_X, top);
  lv_obj_set_size(this->window_, WIN_END - WIN_X, std::max(1, std::min(y + slot_h, WIN_END) - top));
  this->win_y_ = top;
  for (int i = 0; i < 4; i++) {
    lv_obj_t *slot = lv_obj_create(this->window_);
    remove_defaults(slot);
    lv_obj_set_size(slot, slot_w, slot_h);
    lv_obj_set_user_data(slot, reinterpret_cast<void *>(static_cast<intptr_t>(slot_w)));
    this->slots_[i] = slot;
  }
  this->refill();
}

lv_obj_t *Carousel::center_slot() const {
  for (int i = 0; i < 4; i++) {
    if (this->offset_[i] == 0)
      return this->slots_[i];
  }
  return nullptr;
}

void Carousel::release() {
  if (this->prepare_timer_ != nullptr) {
    lv_timer_delete(this->prepare_timer_);
    this->prepare_timer_ = nullptr;
  }
  for (int i = 0; i < 4; i++) {
    this->keys_[i].clear();
    this->ready_[i] = false;
    this->pic_[i].reset();  // the slots' objects are gone already
  }
  g_slide_measure = false;
}

void Carousel::forget() {
  this->release();
  this->window_ = nullptr;
  for (auto &slot : this->slots_)
    slot = nullptr;
  this->count_ = 0;
}

bool Carousel::uses(const std::string &key) const {
  for (const auto &keys : this->keys_) {
    if (keys.count(key))
      return true;
  }
  return false;
}

void Carousel::refill_key(const std::string &key) {
  // Only slots rendered into a snapshot need it; live image objects are
  // updated directly.
  for (int i = 0; i < 4; i++) {
    if (this->slots_[i] != nullptr && this->ready_[i] && this->keys_[i].count(key) &&
        lv_obj_has_flag(this->slots_[i], LV_OBJ_FLAG_USER_1))
      this->fill_slot_(i);
  }
}

void Carousel::show_pic_(int i, const std::shared_ptr<ItemPic> &pic) {
  lv_obj_t *img = lv_image_create(this->slots_[i]);
  lv_image_set_src(img, pic->buf);
  lv_obj_set_pos(img, pic->x0, pic->y0);
  lv_obj_add_flag(this->slots_[i], LV_OBJ_FLAG_USER_1);  // a picture: fades cheaply
  this->pic_[i] = pic;
  this->keys_[i] = pic->keys;
  this->ready_[i] = true;
}

void Carousel::fill_slot_(int i) {
  App.feed_wdt();  // several of these can follow each other (screen build)
  lv_obj_t *slot = this->slots_[i];
  lv_obj_clean(slot);  // its picture goes before it is released
  lv_obj_remove_flag(slot, LV_OBJ_FLAG_USER_1);
  this->pic_[i].reset();
  this->keys_[i].clear();
  // The same item drawn before: its picture is shown again.
  const std::string sig = this->sig ? this->sig(this->index_[i]) : std::string();
  if (this->snapshot_ && !sig.empty()) {
    auto cached = pic_cache_find(sig);
    if (cached != nullptr) {
      this->show_pic_(i, cached);
      return;
    }
  }
  const uint32_t started = millis();
  g_fill_missing = 0;
  g_fill_keys = &this->keys_[i];
  this->fill_(slot, this->index_[i]);
  g_fill_keys = nullptr;
  this->ready_[i] = true;
  if (!this->snapshot_)
    return;
  // Draw the item's objects once into one picture, unless memory is short:
  // then the objects stay (slower to slide, but always shown).
  pic_cache_trim(static_cast<size_t>(this->slot_w_) * this->slot_h_ * 3);
  if (this->slot_w_ > SNAP_MAX_W || this->slot_h_ > SNAP_MAX_H || !snapshot_tmp_ready()) {
    static bool logged = false;
    if (!logged) {
      ESP_LOGE(TAG, "No memory for carousel pictures; drawing the objects instead");
      log_psram("now");
      logged = true;
    }
    return;
  }
  const bool hidden = lv_obj_has_flag(slot, LV_OBJ_FLAG_HIDDEN);
  lv_obj_remove_flag(slot, LV_OBJ_FLAG_HIDDEN);
  lv_obj_update_layout(slot);
  const lv_result_t res = lv_snapshot_take_to_draw_buf(slot, LV_COLOR_FORMAT_ARGB8888, g_snap_tmp);
  if (hidden)
    lv_obj_add_flag(slot, LV_OBJ_FLAG_HIDDEN);
  auto pic = res == LV_RESULT_OK ? crop_item(g_snap_tmp) : nullptr;
  if (pic == nullptr) {
    if (res != LV_RESULT_OK)
      ESP_LOGW(TAG, "Carousel picture failed; drawing the objects");
    return;  // the objects stay
  }
  pic->keys = this->keys_[i];
  lv_obj_clean(slot);
  this->show_pic_(i, pic);
  // Drawn with a stand-in for a picture still on its way: not stored, it is
  // drawn again when the picture arrives.
  if (!sig.empty() && g_fill_missing == 0)
    pic_cache_put(sig, pic);
  ESP_LOGD(TAG, "Carousel item drawn in %u ms (%ux%u, %u KB)", (unsigned) (millis() - started),
           (unsigned) pic->buf->header.w, (unsigned) pic->buf->header.h, (unsigned) (pic->bytes() / 1024));
}

void Carousel::refill() {
  const int offsets[4] = {-1, 0, 1, 2};
  for (int i = 0; i < 4; i++) {
    lv_anim_delete(this->slots_[i], nullptr);
    this->offset_[i] = offsets[i];
    this->index_[i] = this->wrap_(this->selected_ + offsets[i]);
    if (this->count_ > 1 || offsets[i] == 0) {
      this->fill_slot_(i);
    } else {
      lv_obj_clean(this->slots_[i]);
      this->ready_[i] = false;
    }
    this->place_(i, offsets[i], false);
  }
}

static void slot_x_cb(void *var, int32_t centre_x) {
  auto *slot = static_cast<lv_obj_t *>(var);
  const int half = static_cast<int>(reinterpret_cast<intptr_t>(lv_obj_get_user_data(slot))) / 2;
  lv_obj_set_x(slot, centre_x - half - WIN_X);
  // Side slots fade (to ~105). Only a snapshot image fades: its image opacity is
  // cheap, while an opacity on the slot itself makes LVGL render the whole slot
  // into a layer on every frame, which makes the slide stutter or jump.
  if (lv_obj_has_flag(slot, LV_OBJ_FLAG_USER_1) && lv_obj_get_child_count(slot) > 0) {
    const int dist = std::abs(centre_x - CENTER);
    const int opa = 255 - std::min(dist, 240) * 150 / 240;
    lv_obj_set_style_image_opa(lv_obj_get_child(slot, 0), static_cast<lv_opa_t>(std::max(opa, 0)), 0);
  }
}

void Carousel::place_(int slot, int offset, bool animate) {
  lv_obj_t *obj = this->slots_[slot];
  const int target = CENTER + offset * this->spacing_;
  lv_obj_set_y(obj, this->y_ - this->win_y_);
  const bool visible = std::abs(offset) <= 1 && (this->count_ > 1 || offset == 0);
  if (visible)
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_HIDDEN);
  if (!animate || this->anim_ms_ == 0) {
    slot_x_cb(obj, target);
    if (!visible)
      lv_obj_add_flag(obj, LV_OBJ_FLAG_HIDDEN);
    return;
  }
  const int half = static_cast<int>(reinterpret_cast<intptr_t>(lv_obj_get_user_data(obj))) / 2;
  const int from = lv_obj_get_x(obj) + half + WIN_X;
  lv_anim_t a;
  lv_anim_init(&a);
  lv_anim_set_var(&a, obj);
  lv_anim_set_values(&a, from, target);
  lv_anim_set_duration(&a, this->anim_ms_);
  lv_anim_set_exec_cb(&a, slot_x_cb);
  lv_anim_set_path_cb(&a, lv_anim_path_ease_out);
  if (!visible) {
    lv_anim_set_completed_cb(&a, [](lv_anim_t *anim) {
      lv_obj_add_flag(static_cast<lv_obj_t *>(anim->var), LV_OBJ_FLAG_HIDDEN);
    });
  }
  lv_anim_start(&a);
}

void Carousel::rotate(int dir, bool animate) {
  if (this->count_ <= 1 || dir == 0)
    return;
  dir = dir > 0 ? 1 : -1;
  this->last_dir_ = dir;
  if (this->prepare_timer_ != nullptr) {
    lv_timer_delete(this->prepare_timer_);
    this->prepare_timer_ = nullptr;
  }
  // Finish a running slide immediately so input never waits.
  for (int i = 0; i < 4; i++) {
    lv_anim_delete(this->slots_[i], nullptr);
    this->place_(i, this->offset_[i], false);
  }
  // The spare slot (|offset| == 2, or the one not shown) becomes the incoming
  // item. It is usually prepared already (prepare_spare_); turning back the
  // other way fills it now.
  int spare = 0;
  for (int i = 0; i < 4; i++) {
    if (std::abs(this->offset_[i]) > 1) {
      spare = i;
      break;
    }
  }
  const int incoming = this->wrap_(this->selected_ + 2 * dir);
  const bool prepared = this->ready_[spare] && this->offset_[spare] == 2 * dir && this->index_[spare] == incoming;
  this->offset_[spare] = 2 * dir;
  this->index_[spare] = incoming;
  if (!prepared)
    this->fill_slot_(spare);
  this->place_(spare, this->offset_[spare], false);

  animate = animate && this->anim_ms_ > 0;
  lv_obj_remove_flag(this->slots_[spare], LV_OBJ_FLAG_HIDDEN);
  this->selected_ = this->wrap_(this->selected_ + dir);
  for (int i = 0; i < 4; i++) {
    this->offset_[i] -= dir;
    this->place_(i, this->offset_[i], animate);
  }
  if (!animate)
    return;
  g_slide_frames = g_slide_render_ms = g_slide_px = g_slide_flush_us = 0;
  g_slide_measure = true;
  this->prepare_timer_ = lv_timer_create(
      [](lv_timer_t *t) {
        auto *self = static_cast<Carousel *>(lv_timer_get_user_data(t));
        self->prepare_timer_ = nullptr;
        lv_timer_delete(t);
        if (g_slide_measure && g_slide_frames > 0) {
          ESP_LOGD(TAG, "Slide: %u frames, %u ms drawing per frame (%u ms of it sending to the panel), %u kpx per frame",
                   (unsigned) g_slide_frames, (unsigned) (g_slide_render_ms / g_slide_frames),
                   (unsigned) (g_slide_flush_us / 1000 / g_slide_frames), (unsigned) (g_slide_px / 1000 / g_slide_frames));
        }
        g_slide_measure = false;
        if (self->on_settled)
          self->on_settled();
        self->prepare_spare_();
      },
      // After the last frame of the slide has been drawn.
      this->anim_ms_ + 100, this);
}

void Carousel::jump(int steps) {
  if (this->count_ <= 1 || steps == 0)
    return;
  if (this->prepare_timer_ != nullptr) {
    lv_timer_delete(this->prepare_timer_);
    this->prepare_timer_ = nullptr;
  }
  this->last_dir_ = steps > 0 ? 1 : -1;
  this->selected_ = this->wrap_(this->selected_ + steps);
  this->refill();
}

void Carousel::prepare_spare_() {
  if (this->count_ <= 1)
    return;
  for (int i = 0; i < 4; i++) {
    if (std::abs(this->offset_[i]) <= 1)
      continue;
    const int index = this->wrap_(this->selected_ + 2 * this->last_dir_);
    if (this->ready_[i] && this->offset_[i] == 2 * this->last_dir_ && this->index_[i] == index)
      return;
    this->offset_[i] = 2 * this->last_dir_;
    this->index_[i] = index;
    lv_obj_add_flag(this->slots_[i], LV_OBJ_FLAG_HIDDEN);
    this->fill_slot_(i);
    this->place_(i, this->offset_[i], false);
    return;
  }
}

// ---------------------------------------------------------------- Setup / test data

static const char *reset_reason_text(esp_reset_reason_t reason) {
  switch (reason) {
    case ESP_RST_POWERON:
      return "power on";
    case ESP_RST_EXT:
      return "external pin";
    case ESP_RST_SW:
      return "software restart";
    case ESP_RST_PANIC:
      return "crash (panic)";
    case ESP_RST_INT_WDT:
      return "interrupt watchdog";
    case ESP_RST_TASK_WDT:
      return "task watchdog";
    case ESP_RST_WDT:
      return "other watchdog";
    case ESP_RST_DEEPSLEEP:
      return "deep sleep";
    case ESP_RST_BROWNOUT:
      return "brownout (power dip)";
    case ESP_RST_SDIO:
      return "SDIO";
    default:
      return "unknown";
  }
}

// Why the previous run ended; after an OTA rollback this explains the crash.
// Logged at boot and again with the first state from Home Assistant, when the
// log also reaches Home Assistant.
void KisSegitoUI::log_reset_reason_() {
  const esp_reset_reason_t reason = esp_reset_reason();
  if (reason == ESP_RST_PANIC || reason == ESP_RST_INT_WDT || reason == ESP_RST_TASK_WDT ||
      reason == ESP_RST_WDT || reason == ESP_RST_BROWNOUT) {
    ESP_LOGE(TAG, "Previous run ended by: %s (reset reason %d)", reset_reason_text(reason), (int) reason);
  } else {
    ESP_LOGI(TAG, "Previous run ended by: %s (reset reason %d)", reset_reason_text(reason), (int) reason);
  }
}

// Survives a software restart: marks the restart made to load a picture.
static RTC_NOINIT_ATTR uint32_t g_picture_restart;
static constexpr uint32_t PICTURE_RESTART_MAGIC = 0x4B535052;  // "KSPR"
// Pictures at least this big (backgrounds) are stored in flash and loaded
// after a restart when PSRAM has no room for them.
static constexpr int64_t RESTART_PICTURE_BYTES = 200 * 1024;

void KisSegitoUI::setup() {
  this->restarted_for_picture_ = g_picture_restart == PICTURE_RESTART_MAGIC;
  g_picture_restart = 0;
  this->log_reset_reason_();
  log_psram("at boot");
  this->load_test_data_();
  // The last selected child is kept across reboots (as a hash of its id).
  this->child_pref_ = global_preferences->make_preference<uint32_t>(fnv1_hash("kis_segito_ui_child_id"));
  uint32_t saved = 0;
  if (this->child_pref_.load(&saved)) {
    for (size_t i = 0; i < this->children_.size(); i++) {
      if (fnv1_hash(this->children_[i].id) == saved)
        this->child_ = static_cast<int>(i);
    }
  }
}

// Built-in test data, shown until Home Assistant sends a snapshot.
void KisSegitoUI::load_test_data_() {
  this->state_now_ = 1800000000;  // any fixed epoch; only differences matter
  this->state_ms_ = millis();
  const int64_t now = this->state_now_;
  this->children_ = {
      {"test1", "test_avatar_1", 0x6CB8FF, 7, 12, true, 5, 7, true},
      {"test2", "test_avatar_2", 0xFF8FB1, 24, 3, true, 2, 7, true},
      {"test3", "test_avatar_3", 0x6BCB77, 260, 0, false, 6, 7, true},
  };
  this->rewards_ = {
      {"r1", "reward_toy_car", 8, false}, {"r2", "reward_doll", 12, false},  {"r3", "reward_bricks", 20, false},
      {"r4", "reward_long_story", 5, false}, {"r5", "reward_treat", 3, false},
  };
  Routine morning;
  morning.id = "morning";
  morning.icon = "routine_morning";
  morning.start = now - 12 * 60;
  morning.end = morning.start + 40 * 60;
  morning.zones = {{15 * 60, ZONE_WARN}, {5 * 60, ZONE_LATE}};
  morning.checkpoints = {
      {"breakfast", "task_breakfast", morning.start + 20 * 60, {}, {{5 * 60, 2}, {0, 1}}},
      {"door", "routine_departure", morning.end, {}, {{15 * 60, 3}, {5 * 60, 2}, {0, 1}}},
      {"flag1", "checkpoint_flag", morning.start + 32 * 60, {"test1"}, {{0, 1}}},
  };
  morning.tasks = {
      {"t1", "task_clothes", "breakfast"}, {"t2", "task_breakfast", "breakfast"}, {"t3", "task_toothbrush", "door"},
      {"t4", "task_shoes", "door"},        {"t5", "routine_prepare", "door"},
  };
  Routine evening = morning;
  evening.id = "evening";
  evening.icon = "routine_evening";
  evening.start = now - 5 * 60;
  evening.end = evening.start + 30 * 60;
  for (auto &cp : evening.checkpoints)
    cp.t = evening.start + (cp.t - morning.start) * 30 / 40;
  this->routines_ = {morning, evening};
}

int64_t KisSegitoUI::now_() const {
  return this->state_now_ + static_cast<int64_t>((millis() - this->state_ms_) / 1000);
}

static uint32_t parse_color(const char *hex, uint32_t fallback) {
  if (hex == nullptr)
    return fallback;
  if (*hex == '#')
    hex++;
  char *end = nullptr;
  const unsigned long value = strtoul(hex, &end, 16);
  return end != hex ? static_cast<uint32_t>(value) : fallback;
}

static std::vector<std::string> string_list(JsonVariantConst value) {
  std::vector<std::string> out;
  for (JsonVariantConst item : value.as<JsonArrayConst>())
    out.emplace_back(item.as<const char *>() ? item.as<const char *>() : "");
  return out;
}

void KisSegitoUI::set_state(const std::string &json) {
  JsonDocument doc = json::parse_json(json);
  JsonObjectConst root = doc.as<JsonObjectConst>();
  if (root.isNull() || root["v"].as<int>() != 1) {
    ESP_LOGW(TAG, "Ignoring state: unreadable or unknown schema");
    return;
  }
  // The same data again with only the time moved on: no need to rebuild.
  uint32_t sig = 2166136261u;
  {
    const size_t at = json.find("\"now\":");
    for (size_t i = 0; i < json.size(); i++) {
      if (i == at) {
        i += 6;
        while (i < json.size() && isdigit(static_cast<unsigned char>(json[i])))
          i++;
        if (i >= json.size())
          break;
      }
      sig = (sig ^ static_cast<uint8_t>(json[i])) * 16777619u;
    }
  }
  if (sig == this->state_sig_ && this->have_state_) {
    this->state_now_ = root["now"].as<int64_t>();
    this->state_ms_ = millis();
    return;
  }
  this->state_sig_ = sig;
  const bool first_state = !this->have_state_;
  // Keep the selection by id across the update.
  const std::string child_id = this->children_.empty() ? "" : this->children_[this->child_].id;
  const std::string routine_id = this->routines_.empty() ? "" : this->current_routine_().id;
  const std::string reward_id =
      this->rewards_.empty() ? "" : this->rewards_[this->reward_ % this->rewards_.size()].id;

  this->state_now_ = root["now"].as<int64_t>();
  this->img_base_ = root["img"]["u"] | "";
  this->general_bg_ = root["bg"] | "";
  const std::string token = root["img"]["t"] | "";
  if (token != this->img_token_) {
    // A new picture key: retry the pictures the old one could not fetch.
    for (const auto &key : this->photo_failed_)
      this->photo_requested_.erase(key);
    this->photo_failed_.clear();
    this->img_token_ = token;
  }
  this->state_ms_ = millis();
  std::vector<Child> children;
  for (JsonObjectConst c : root["children"].as<JsonArrayConst>()) {
    Child child;
    child.id = c["id"].as<const char *>() ? c["id"].as<const char *>() : "";
    child.avatar = c["a"] | "placeholder_avatar";
    child.color = parse_color(c["c"].as<const char *>(), 0x6CB8FF);
    child.wallet = c["w"] | 0;
    child.piggy = c["p"] | 0;
    child.piggy_unlocked = c["pu"] | false;
    child.streak = c["s"] | 0;
    child.streak_target = c["st"] | 7;
    child.selectable = c["sel"] | true;
    child.pending_interest = c["pi"] | 0;
    child.background = c["bg"] | "";
    if (this->images_.count(child.avatar + "_180") == 0) {
      // Built-in avatars come from Home Assistant like uploaded pictures.
      const bool served = child.avatar.rfind("avatar_", 0) == 0 || is_online_icon(child.avatar);
      child.avatar = served ? "@" + child.avatar : "placeholder_avatar";
    }
    if (c["ai"].is<const char *>() && strlen(c["ai"].as<const char *>()) > 0)
      child.avatar = std::string("@") + c["ai"].as<const char *>();
    children.push_back(child);
  }
  std::vector<Reward> rewards;
  for (JsonObjectConst r : root["rewards"].as<JsonArrayConst>()) {
    Reward reward;
    reward.id = r["id"] | "";
    reward.icon = r["i"] | "fn_rewards";
    reward.cost = r["c"] | 0;
    if (r["ii"].is<const char *>() && strlen(r["ii"].as<const char *>()) > 0)
      reward.icon = std::string("@") + r["ii"].as<const char *>();
    reward.piggy_unlock = strcmp(r["k"] | "normal", "piggy_unlock") == 0;
    rewards.push_back(reward);
  }
  std::vector<Routine> routines;
  for (JsonObjectConst r : root["routines"].as<JsonArrayConst>()) {
    Routine routine;
    routine.id = r["id"] | "";
    routine.icon = r["i"] | "routine_generic";
    routine.start = r["s"].as<int64_t>();
    routine.end = r["e"].as<int64_t>();
    routine.children = string_list(r["ch"]);
    routine.base_color = parse_color(r["base"].as<const char *>(), ZONE_OK);
    for (JsonArrayConst z : r["z"].as<JsonArrayConst>())
      routine.zones.push_back({z[0].as<int>(), parse_color(z[1].as<const char *>(), ZONE_WARN)});
    std::sort(routine.zones.begin(), routine.zones.end(),
              [](const Zone &a, const Zone &b) { return a.offset_s > b.offset_s; });
    for (JsonObjectConst c : r["cp"].as<JsonArrayConst>()) {
      Checkpoint cp;
      cp.id = c["id"] | "";
      cp.icon = c["i"] | "checkpoint_flag";
      cp.t = c["t"].as<int64_t>();
      cp.children = string_list(c["ch"]);
      for (JsonArrayConst b : c["b"].as<JsonArrayConst>())
        cp.bands.push_back({b[0].as<int>(), b[1].as<int>()});
      routine.checkpoints.push_back(cp);
    }
    for (JsonObjectConst t : r["t"].as<JsonArrayConst>())
      routine.tasks.push_back({t["id"] | "", t["i"] | "task_generic", t["cp"] | ""});
    for (JsonPairConst kv : r["done"].as<JsonObjectConst>())
      routine.done[kv.key().c_str()] = string_list(kv.value());
    for (JsonPairConst kv : r["cpd"].as<JsonObjectConst>())
      routine.cp_done[kv.key().c_str()] = string_list(kv.value());
    routines.push_back(routine);
  }
  this->children_ = children;
  this->rewards_ = rewards;
  this->routines_ = routines;
  this->have_state_ = true;
  this->inactivity_ms_ = static_cast<uint32_t>(std::max(10, root["idle"] | 60)) * 1000;
  if (root["scr"].is<JsonObjectConst>()) {
    JsonObjectConst scr = root["scr"].as<JsonObjectConst>();
    const std::string saver_type = scr["ss"] | "balls";
    const uint32_t saver = std::max(0, scr["saver"] | 0), dim = std::max(0, scr["dim"] | 60),
                   blank = std::max(0, scr["blank"] | 0), off = std::max(0, scr["off"] | 120);
    const uint8_t lvl = static_cast<uint8_t>(std::min(100, std::max(1, scr["lvl"] | 15)));
    if (saver != this->saver_after_ || dim != this->dim_after_ || lvl != this->dim_level_ ||
        blank != this->blank_after_ || off != this->off_after_ || saver_type != this->saver_type_ ||
        first_state) {
      ESP_LOGI(TAG, "Screen: screensaver (%s) after %us, dimmed to %u%% after %us, drawing off after %us, "
                    "backlight off after %us (0 = never)",
               saver_type.c_str(), (unsigned) saver, (unsigned) lvl, (unsigned) dim, (unsigned) blank,
               (unsigned) off);
    }
    this->saver_after_ = saver;
    this->dim_after_ = dim;
    this->dim_level_ = lvl;
    this->blank_after_ = blank;
    this->off_after_ = off;
    this->saver_type_ = saver_type;
  }
  if (root["anim"].is<const char *>())
    this->set_animation_mode(root["anim"].as<const char *>());

  this->child_ = 0;
  for (size_t i = 0; i < this->children_.size(); i++) {
    if (this->children_[i].id == child_id)
      this->child_ = static_cast<int>(i);
  }
  this->routine_ = 0;
  for (size_t i = 0; i < this->routines_.size(); i++) {
    if (this->routines_[i].id == routine_id)
      this->routine_ = static_cast<int>(i);
  }
  for (size_t i = 0; i < this->rewards_.size(); i++) {
    if (this->rewards_[i].id == reward_id)
      this->reward_ = static_cast<int>(i);
  }
  ESP_LOGI(TAG, "State: %u children, %u rewards, %u routines", (unsigned) this->children_.size(),
           (unsigned) this->rewards_.size(), (unsigned) this->routines_.size());
  if (!this->boot_info_logged_) {
    this->boot_info_logged_ = true;
    this->log_reset_reason_();
  }
  log_psram("after the state");
  if (!this->started_)
    return;
  if (this->busy_) {
    this->pending_rebuild_ = true;  // applied when the animation ends
    this->shown_routine_ = nullptr;
    return;
  }
  this->pending_rebuild_ = false;
  this->show_(this->screen_);
}

void KisSegitoUI::send_action_(const char *kind, const std::string &extra) {
  // {"a":kind,"id":unique,"c":child,...}: Home Assistant runs each id once.
  char id[20];
  snprintf(id, sizeof(id), "%08x%04x", (unsigned) random_uint32(), (unsigned) (++this->action_seq_ & 0xFFFF));
  std::string json = std::string("{\"a\":\"") + kind + "\",\"id\":\"" + id + "\",\"c\":\"" +
                     this->children_[this->child_].id + "\"" + extra + "}";
  ESP_LOGI(TAG, "Action: %s", json.c_str());
  // The screen now shows a guess; the next snapshot replaces it, even if it
  // is the same as the last one.
  this->state_sig_ = 0;
  if (this->action_sensor_ != nullptr)
    this->action_sensor_->publish_state(json);
}

bool KisSegitoUI::is_done_(const Routine &r, const std::string &task_id) const {
  auto it = r.done.find(this->children_[this->child_].id);
  return it != r.done.end() && std::find(it->second.begin(), it->second.end(), task_id) != it->second.end();
}

bool KisSegitoUI::cp_done_(const Routine &r, const std::string &cp_id) const {
  auto it = r.cp_done.find(this->children_[this->child_].id);
  return it != r.cp_done.end() && std::find(it->second.begin(), it->second.end(), cp_id) != it->second.end();
}

static bool applies(const std::vector<std::string> &children, const std::string &child_id) {
  return children.empty() || std::find(children.begin(), children.end(), child_id) != children.end();
}

// The next checkpoint this child still has to reach in a routine.
const Checkpoint *KisSegitoUI::next_checkpoint_(const Routine &r) const {
  const Checkpoint *best = nullptr;
  for (const auto &cp : r.checkpoints) {
    if (!applies(cp.children, this->children_[this->child_].id) || this->cp_done_(r, cp.id))
      continue;
    if (best == nullptr || cp.t < best->t)
      best = &cp;
  }
  return best;
}

static int reward_for(const std::vector<Band> &bands, int64_t seconds_early) {
  int best = 0;
  int best_threshold = INT32_MIN;
  for (const auto &b : bands) {
    if (seconds_early >= b.early_s && b.early_s > best_threshold) {
      best = std::max(b.tokens, 0);
      best_threshold = b.early_s;
    }
  }
  return best;
}

void KisSegitoUI::select_child_(int index) {
  if (index == this->child_)
    return;
  this->child_ = index;
  uint32_t value = fnv1_hash(this->children_[index].id);
  this->child_pref_.save(&value);
}

void KisSegitoUI::refuse_offline_(lv_obj_t *target) {
  // Token transactions need Home Assistant: refuse with a shake and a pulse
  // of the offline marker instead of acting on cached data.
  ESP_LOGI(TAG, "Offline: transaction refused");
  if (this->offline_icon_ != nullptr && this->anim_ms_(300) > 0) {
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, this->offline_icon_);
    lv_anim_set_values(&a, 256, 420);
    lv_anim_set_duration(&a, 160);
    lv_anim_set_reverse_duration(&a, 160);
    lv_anim_set_repeat_count(&a, 1);
    lv_anim_set_exec_cb(&a, [](void *var, int32_t v) { lv_image_set_scale(static_cast<lv_obj_t *>(var), v); });
    lv_anim_start(&a);
  }
  if (target != nullptr && this->anim_ms_(300) > 0) {
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, target);
    lv_anim_set_values(&a, -10, 10);
    lv_anim_set_duration(&a, 60);
    lv_anim_set_reverse_duration(&a, 60);
    lv_anim_set_repeat_count(&a, 2);
    lv_anim_set_exec_cb(&a, [](void *var, int32_t v) {
      lv_obj_set_style_translate_x(static_cast<lv_obj_t *>(var), v, 0);
    });
    lv_anim_set_completed_cb(&a, [](lv_anim_t *anim) {
      lv_obj_set_style_translate_x(static_cast<lv_obj_t *>(anim->var), 0, 0);
    });
    lv_anim_start(&a);
  }
}

void KisSegitoUI::start() {
  if (this->started_)
    return;
  this->started_ = true;
  this->root_ = lv_obj_create(nullptr);
  remove_defaults(this->root_);
  lv_obj_set_style_bg_color(this->root_, lv_color_hex(BASE_BG), 0);
  lv_obj_set_style_bg_opa(this->root_, LV_OPA_COVER, 0);
  // Screen content first, the time track above it: content sliding under the
  // track band fades out, so the arcs stay clearly visible.
  this->screen_obj_ = lv_obj_create(this->root_);
  remove_defaults(this->screen_obj_);
  lv_obj_set_size(this->screen_obj_, SCREEN, SCREEN);
  // The ring of the time track (pictures, see render_ring_), then the live
  // track objects above it.
  this->ring_layer_ = lv_obj_create(this->root_);
  remove_defaults(this->ring_layer_);
  lv_obj_set_size(this->ring_layer_, SCREEN, SCREEN);
  this->track_layer_ = lv_obj_create(this->root_);
  remove_defaults(this->track_layer_);
  lv_obj_set_size(this->track_layer_, SCREEN, SCREEN);
  lv_screen_load(this->root_);
  // A long redraw (many areas, e.g. after waking) must not trip the task
  // watchdog: it is fed with every area sent to the panel.
  lv_display_add_event_cb(
      lv_display_get_default(),
      [](lv_event_t *e) {
        App.feed_wdt();
        if (g_slide_measure) {
          const auto *area = static_cast<const lv_area_t *>(lv_event_get_param(e));
          if (area != nullptr)
            g_slide_px += lv_area_get_size(area);
          g_flush_start_us = micros();
        }
      },
      LV_EVENT_FLUSH_START, nullptr);
  lv_display_add_event_cb(
      lv_display_get_default(),
      [](lv_event_t *) {
        if (g_slide_measure)
          g_slide_flush_us += micros() - g_flush_start_us;
      },
      LV_EVENT_FLUSH_FINISH, nullptr);
  // How long drawing a frame takes while a carousel slides (debug log).
  lv_display_add_event_cb(
      lv_display_get_default(), [](lv_event_t *) { g_refr_start = millis(); }, LV_EVENT_REFR_START, nullptr);
  lv_display_add_event_cb(
      lv_display_get_default(),
      [](lv_event_t *) {
        if (g_slide_measure) {
          g_slide_frames++;
          g_slide_render_ms += millis() - g_refr_start;
        }
      },
      LV_EVENT_REFR_READY, nullptr);

  // Always visible while offline, at the right edge of the top gap.
  this->offline_icon_ = lv_image_create(lv_layer_top());
  lv_image_set_src(this->offline_icon_, this->img_("status_disconnected_28"));
  lv_obj_set_pos(this->offline_icon_, CENTER + 50, 18);
  lv_obj_add_flag(this->offline_icon_, LV_OBJ_FLAG_HIDDEN);

  this->last_input_ms_ = millis();
  this->tick_timer_ = lv_timer_create(
      [](lv_timer_t *t) {
        auto *self = static_cast<KisSegitoUI *>(lv_timer_get_user_data(t));
        if (self->pending_rebuild_ && !self->busy_) {
          self->pending_rebuild_ = false;
          self->show_(self->screen_);
          return;
        }
        self->update_track_();
        if (self->screen_ != Screen::CHILDREN && !self->busy_ && millis() - self->last_input_ms_ > self->inactivity_ms_)
          self->show_(Screen::CHILDREN);
      },
      1000, this);

  // The inner track belongs to the centred child: drawn for it when a slide
  // on the child carousel has ended.
  this->carousel_.on_settled = [this]() {
    if (this->screen_ != Screen::CHILDREN)
      return;
    this->build_inner_track_();
    this->update_ring_();
  };
  this->show_(Screen::CHILDREN);
  ESP_LOGI(TAG, "UI started (%s, %u children)", this->have_state_ ? "Home Assistant data" : "test data",
           (unsigned) this->children_.size());
}

// ---------------------------------------------------------------- Helpers

std::string KisSegitoUI::photo_key_(const std::string &key) const {
  if (!key.empty() && key[0] == '@')
    return key;
  if (this->images_.count(key) == 0 && is_online_icon(key))
    return "@" + key;  // downloaded from Home Assistant
  return "";
}

const lv_image_dsc_t *KisSegitoUI::img_(const std::string &key) {
  const std::string pk = this->photo_key_(key);
  if (!pk.empty()) {
    // A downloaded picture: shown once it is here; until then a placeholder
    // for avatars, nothing for icons and backgrounds.
    if (g_fill_keys != nullptr)
      g_fill_keys->insert(pk);
    auto photo = this->photos_.find(pk);
    if (photo != this->photos_.end()) {
      photo->second.used_ms = millis();
      return photo->second.dsc;
    }
    this->request_photo_(pk);
    if (g_fill_keys != nullptr)
      g_fill_missing++;
    const size_t n = 4;
    if (pk.size() > n && pk.compare(pk.size() - n, n, "_180") == 0)
      return this->img_("placeholder_avatar_180");
    return nullptr;
  }
  auto it = this->images_.find(key);
  if (it == this->images_.end()) {
    // Not built in at this size: use the nearest size of the same icon.
    const size_t sep = key.rfind('_');
    if (sep != std::string::npos && sep + 1 < key.size()) {
      const std::string prefix = key.substr(0, sep + 1);
      const int want = atoi(key.c_str() + sep + 1);
      int best_diff = INT_MAX;
      for (auto i = this->images_.lower_bound(prefix); i != this->images_.end(); ++i) {
        if (i->first.compare(0, prefix.size(), prefix) != 0)
          break;
        const std::string rest = i->first.substr(prefix.size());
        if (rest.empty() || rest.find_first_not_of("0123456789") != std::string::npos)
          continue;
        const int diff = std::abs(atoi(rest.c_str()) - want);
        if (diff < best_diff) {
          best_diff = diff;
          it = i;
        }
      }
    }
    if (it == this->images_.end()) {
      ESP_LOGW(TAG, "Missing image %s", key.c_str());
      return nullptr;
    }
  }
  return it->second->get_lv_image_dsc();
}

void KisSegitoUI::bind_(lv_obj_t *obj, const std::string &key, int cx, int cy) {
  this->bindings_.push_back({obj, key, static_cast<int16_t>(cx), static_cast<int16_t>(cy)});
  lv_obj_add_event_cb(obj, &KisSegitoUI::unbind_cb_, LV_EVENT_DELETE, this);
}

void KisSegitoUI::unbind_cb_(lv_event_t *e) {
  auto *self = static_cast<KisSegitoUI *>(lv_event_get_user_data(e));
  lv_obj_t *obj = lv_event_get_target_obj(e);
  auto &b = self->bindings_;
  b.erase(std::remove_if(b.begin(), b.end(), [obj](const Binding &x) { return x.obj == obj; }), b.end());
}

// A downloaded picture arrived (or changed): shown where it is used, without
// rebuilding the screen.
void KisSegitoUI::picture_ready_(const std::string &key) {
  auto it = this->photos_.find(key);
  if (it == this->photos_.end() || !this->started_)
    return;
  const lv_image_dsc_t *dsc = it->second.dsc;
  if (key == this->shown_bg_)
    lv_obj_set_style_bg_image_src(this->root_, dsc, 0);  // a newer version of it
  for (const auto &b : this->bindings_) {
    if (b.key != key)
      continue;
    lv_image_set_src(b.obj, dsc);
    lv_obj_set_pos(b.obj, b.cx - dsc->header.w / 2, b.cy - dsc->header.h / 2);
  }
  this->carousel_.refill_key(key);
  this->apply_background_(this->wanted_bg_);
}

// Frees downloaded pictures nothing shows, least recently used first: those
// over PHOTO_KEEP_UNUSED, and with `need` as many more as it takes to make a
// block of that size available.
void KisSegitoUI::release_photos_(size_t need) {
  std::vector<std::pair<uint32_t, std::string>> unused;
  size_t unused_bytes = 0;
  for (const auto &kv : this->photos_) {
    if (kv.first == this->shown_bg_ || this->carousel_.uses(kv.first))
      continue;
    bool bound = false;
    for (const auto &b : this->bindings_) {
      if (b.key == kv.first) {
        bound = true;
        break;
      }
    }
    if (bound)
      continue;
    unused.emplace_back(kv.second.used_ms, kv.first);
    unused_bytes += kv.second.bytes;
  }
  std::sort(unused.begin(), unused.end());  // least recently used first
  for (const auto &u : unused) {
    // Only as many as needed: freeing pictures that are needed again soon
    // means loading and drawing them again.
    if (unused_bytes <= PHOTO_KEEP_UNUSED && (need == 0 || psram_can_spare(need)))
      break;
    Photo &p = this->photos_[u.second];
    lv_image_cache_drop(p.dsc);
    heap_caps_free(p.raw);
    delete p.dsc;
    unused_bytes -= p.bytes;
    this->photos_.erase(u.second);
    this->photo_requested_.erase(u.second);  // loaded again when needed
  }
}

void KisSegitoUI::apply_background_(const std::string &id) {
  this->wanted_bg_ = id;
  const std::string &use = id.empty() ? this->general_bg_ : id;
  const lv_image_dsc_t *dsc = this->background_(id);
  if (dsc == nullptr && !use.empty() && !this->photo_failed_.count("@" + use + "_480"))
    return;  // still loading: keep what is shown
  this->shown_bg_ = dsc != nullptr ? "@" + use + "_480" : "";
  if (lv_obj_get_style_bg_image_src(this->root_, LV_PART_MAIN) != dsc) {
    lv_obj_set_style_bg_image_src(this->root_, dsc, 0);
    this->update_ring_();  // the ring shows the background too
  }
}

bool KisSegitoUI::has_image_(const std::string &key) const {
  return this->images_.count(key) > 0 || is_online_icon(key);
}

const lv_image_dsc_t *KisSegitoUI::background_(const std::string &id) {
  const std::string &use = id.empty() ? this->general_bg_ : id;
  if (use.empty())
    return nullptr;
  return this->img_("@" + use + "_480");
}

void KisSegitoUI::request_photo_(const std::string &key) {
  if (this->img_base_.empty() || this->photo_requested_.count(key))
    return;
  this->photo_requested_.insert(key);
  // "@<id>_<size>" -> <base>/api/kis_segito/knob_image/<id>/<size>; the token goes
  // in a header, never in the URL (URLs end up in logs).
  const size_t sep = key.rfind('_');
  if (sep == std::string::npos || sep < 2)
    return;
  const std::string url =
      this->img_base_ + "/api/kis_segito/knob_image/" + key.substr(1, sep - 1) + "/" + key.substr(sep + 1);
  {
    std::lock_guard<std::mutex> lock(this->photo_mutex_);
    this->photo_queue_.push_back({key, url, this->img_token_});
  }
  if (!this->photo_task_started_) {
    this->photo_task_started_ = true;
    xTaskCreate(&KisSegitoUI::photo_task_, "ks_photos", 6144, this, 1, nullptr);
  }
}

static esp_err_t http_event(esp_http_client_event_t *evt) {
  if (evt->event_id == HTTP_EVENT_ON_HEADER && evt->user_data != nullptr && strcasecmp(evt->header_key, "ETag") == 0)
    *static_cast<std::string *>(evt->user_data) = evt->header_value;
  return ESP_OK;
}

// Worker task: loads queued pictures into PSRAM, one at a time: from the
// flash cache when it is there (checked once per start with Home Assistant,
// which answers "not modified" for an unchanged picture), else downloaded and
// stored in the cache.
void KisSegitoUI::photo_task_(void *arg) {
  auto *self = static_cast<KisSegitoUI *>(arg);
  self->cache_.begin();
  auto deliver = [self](const std::string &key, uint8_t *buf, size_t size, bool fresh) {
    std::lock_guard<std::mutex> lock(self->photo_mutex_);
    self->photo_done_.push_back({key, buf, size, fresh});
  };
  while (true) {
    if (self->stopping_) {
      self->worker_idle_ = true;
      vTaskDelay(pdMS_TO_TICKS(1000));  // stopped until the restart
      continue;
    }
    PhotoJob job;
    {
      std::lock_guard<std::mutex> lock(self->photo_mutex_);
      if (!self->photo_queue_.empty()) {
        job = self->photo_queue_.front();
        self->photo_queue_.pop_front();
      }
    }
    if (job.key.empty()) {
      self->worker_idle_ = true;
      vTaskDelay(pdMS_TO_TICKS(100));
      continue;
    }
    self->worker_idle_ = false;
    std::string cached_etag;
    size_t cached_size = 0;
    uint8_t *cached = nullptr;
    if (self->cache_.ready()) {
      const size_t size = self->cache_.size(job.key);
      if (size > 0 && !psram_can_spare(size))
        self->need_memory_ = size;
      cached = self->cache_.read(job.key, &cached_size, &cached_etag);
    }
    uint32_t cached_crc = 0;
    if (cached != nullptr) {
      cached_crc = esp_rom_crc32_le(0, cached, cached_size);
      deliver(job.key, cached, cached_size, false);
      if (self->validated_.count(job.key))
        continue;
    }
    std::string etag;
    esp_http_client_config_t cfg{};
    cfg.url = job.url.c_str();
    cfg.timeout_ms = 10000;
    cfg.event_handler = http_event;
    cfg.user_data = &etag;
    esp_http_client_handle_t client = esp_http_client_init(&cfg);
    if (client != nullptr) {
      esp_http_client_set_header(client, "X-Kis-Segito-Token", job.token.c_str());
      if (cached != nullptr && !cached_etag.empty())
        esp_http_client_set_header(client, "If-None-Match", cached_etag.c_str());
    }
    uint8_t *buf = nullptr;
    int got = 0;
    int status = 0;
    if (client != nullptr && esp_http_client_open(client, 0) == ESP_OK) {
      const int64_t len = esp_http_client_fetch_headers(client);
      status = esp_http_client_get_status_code(client);
      if (status == 200 && len > 8 && len < 600 * 1024) {
        if (psram_can_spare(len)) {
          buf = static_cast<uint8_t *>(heap_caps_malloc(len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
        } else if (job.tries < 30) {
          // Ask the main loop for room and try again shortly.
          self->need_memory_ = len;
          esp_http_client_close(client);
          esp_http_client_cleanup(client);
          job.tries++;
          {
            std::lock_guard<std::mutex> lock(self->photo_mutex_);
            self->photo_queue_.push_back(job);
          }
          vTaskDelay(pdMS_TO_TICKS(300));
          continue;
        } else if (psram_has(len)) {
          // Last try: without the usual reserve.
          buf = static_cast<uint8_t *>(heap_caps_malloc(len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
        } else if (len >= RESTART_PICTURE_BYTES && self->cache_.ready() && !etag.empty() &&
                   !self->restarted_for_picture_) {
          // No room now, but after a restart there is: stored in flash and
          // loaded from there at the start.
          const bool stored = self->cache_.write_stream(job.key, etag, len, [client](uint8_t *b, int n) {
            return esp_http_client_read(client, reinterpret_cast<char *>(b), n);
          });
          if (stored) {
            ESP_LOGW(TAG, "Not enough PSRAM for picture %s (%u KB): restarting to load it", job.key.c_str(),
                     (unsigned) (len / 1024));
            self->restart_for_picture_ = true;
          }
        }
        if (buf == nullptr && !self->restart_for_picture_)
          ESP_LOGE(TAG, "Not enough PSRAM for picture %s (%u KB)", job.key.c_str(), (unsigned) (len / 1024));
        while (buf != nullptr && got < len) {
          const int r = esp_http_client_read(client, reinterpret_cast<char *>(buf) + got, len - got);
          if (r <= 0)
            break;
          got += r;
        }
        if (buf != nullptr && got != len) {
          heap_caps_free(buf);
          buf = nullptr;
        }
      }
      esp_http_client_close(client);
    }
    if (client != nullptr)
      esp_http_client_cleanup(client);
    if (status == 304 || (status == 200 && buf != nullptr))
      self->validated_.insert(job.key);
    if (buf != nullptr) {
      if (self->cache_.ready() && !etag.empty())
        self->cache_.write(job.key, etag, buf, got);
      if (cached != nullptr && static_cast<size_t>(got) == cached_size &&
          esp_rom_crc32_le(0, buf, got) == cached_crc) {
        heap_caps_free(buf);  // the same picture as the cached one already shown
        continue;
      }
      deliver(job.key, buf, got, true);
    } else if (cached == nullptr && !self->restart_for_picture_) {
      deliver(job.key, nullptr, 0, false);  // could not be loaded
    }
    // With a cached copy and Home Assistant out of reach, the cached one stays.
  }
}

void KisSegitoUI::on_shutdown() {
  this->stopping_ = true;
  if (!this->photo_task_started_)
    return;
  // Let a download or flash write in progress finish (at most about 1.5 s).
  for (int i = 0; i < 150 && !this->worker_idle_; i++)
    delay(10);
}

void KisSegitoUI::loop() {
  this->handle_input_();
  const uint32_t now = millis();
  if (now - this->last_poll_ms_ >= 1000) {
    this->last_poll_ms_ = now;
    this->poll_connection_();
    if (this->started_)
      this->release_photos_(0);
  }
  // Downloaded pictures come before carousel pictures: room is made for them,
  // only when one is waiting for it. (Measuring the free memory walks the whole
  // PSRAM heap, so it is not done on every loop.)
  if (this->restart_for_picture_ && !this->stopping_) {
    g_picture_restart = PICTURE_RESTART_MAGIC;
    App.safe_reboot();
  }
  const size_t need = this->need_memory_;
  if (need > 0) {
    pic_cache_trim(need);
    if (!psram_can_spare(need) && this->started_)
      this->release_photos_(need);
    this->need_memory_ = 0;
  }
  std::vector<Download> done;
  {
    std::lock_guard<std::mutex> lock(this->photo_mutex_);
    if (this->photo_done_.empty())
      return;
    done.swap(this->photo_done_);
  }
  for (auto &d : done) {
    // b"KSI1" + width + height (uint16 LE) + RGB565 pixels + alpha bytes, or
    // b"KSI2" (backgrounds): the same without alpha.
    const bool opaque = d.data != nullptr && d.size >= 8 && memcmp(d.data, "KSI2", 4) == 0;
    if (d.data == nullptr || d.size < 8 || (!opaque && memcmp(d.data, "KSI1", 4) != 0)) {
      ESP_LOGW(TAG, "Picture %s could not be downloaded", d.key.c_str());
      this->photo_failed_.insert(d.key);
      if (d.data != nullptr)
        heap_caps_free(d.data);
      if (this->started_)
        this->apply_background_(this->wanted_bg_);  // a failed background: the plain colour
      continue;
    }
    const uint16_t w = d.data[4] | (d.data[5] << 8);
    const uint16_t h = d.data[6] | (d.data[7] << 8);
    const size_t bytes_per_pixel = opaque ? 2 : 3;
    if (d.size != 8 + static_cast<size_t>(w) * h * bytes_per_pixel) {
      heap_caps_free(d.data);
      this->photo_failed_.insert(d.key);
      continue;
    }
    auto *dsc = new lv_image_dsc_t{};
    dsc->header.magic = LV_IMAGE_HEADER_MAGIC;
    dsc->header.cf = opaque ? LV_COLOR_FORMAT_RGB565 : LV_COLOR_FORMAT_RGB565A8;
    dsc->header.w = w;
    dsc->header.h = h;
    dsc->header.stride = w * 2;
    dsc->data_size = static_cast<uint32_t>(w) * h * bytes_per_pixel;
    dsc->data = d.data + 8;
    Photo old;
    auto it = this->photos_.find(d.key);
    if (it != this->photos_.end())
      old = it->second;  // a newer version: replaced once it is shown
    if (d.fresh && old.dsc != nullptr)
      this->photo_version_[d.key]++;
    this->photo_seen_.insert(d.key);
    this->photos_[d.key] = {dsc, d.data, d.size, millis()};
    this->photo_failed_.erase(d.key);
    this->photo_requested_.insert(d.key);
    ESP_LOGD(TAG, "Picture %s ready (%ux%u)", d.key.c_str(), w, h);
    this->picture_ready_(d.key);
    if (old.dsc != nullptr) {
      lv_image_cache_drop(old.dsc);
      heap_caps_free(old.raw);
      delete old.dsc;
    }
  }
}

uint32_t KisSegitoUI::anim_ms_(uint32_t full_ms) const {
  if (this->anim_mode_ == 0)
    return 0;
  return this->anim_mode_ == 1 ? full_ms / 2 : full_ms;
}

lv_color_t KisSegitoUI::tint_(uint32_t color, uint8_t amount) const {
  return lv_color_mix(lv_color_hex(color), lv_color_hex(BASE_BG), amount);
}

void KisSegitoUI::set_animation_mode(const std::string &mode) {
  this->anim_mode_ = mode == "off" ? 0 : (mode == "reduced" ? 1 : 2);
}

void KisSegitoUI::set_language(const std::string &language) {
  if (language == this->language_)
    return;
  this->language_ = language;
  // Language-specific artwork changes live, without a restart.
  this->shown_reward_ = -1;
  if (this->started_)
    this->update_track_();
}

void KisSegitoUI::show_ui() {
  if (this->root_ != nullptr)
    lv_screen_load(this->root_);
}

void KisSegitoUI::set_connected(bool connected) {
  this->connected_ = connected;
  if (this->offline_icon_ == nullptr)
    return;
  if (connected)
    lv_obj_add_flag(this->offline_icon_, LV_OBJ_FLAG_HIDDEN);
  else
    lv_obj_remove_flag(this->offline_icon_, LV_OBJ_FLAG_HIDDEN);
}

lv_obj_t *KisSegitoUI::disc_(lv_obj_t *parent, int cx, int cy, int d, lv_color_t color) {
  lv_obj_t *obj = lv_obj_create(parent);
  remove_defaults(obj);
  lv_obj_set_size(obj, d, d);
  lv_obj_set_pos(obj, cx - d / 2, cy - d / 2);
  lv_obj_set_style_radius(obj, LV_RADIUS_CIRCLE, 0);
  lv_obj_set_style_bg_color(obj, color, 0);
  lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
  return obj;
}

lv_obj_t *KisSegitoUI::image_(lv_obj_t *parent, const std::string &key, int cx, int cy) {
  lv_obj_t *img = lv_image_create(parent);
  const lv_image_dsc_t *dsc = this->img_(key);
  if (dsc != nullptr) {
    lv_image_set_src(img, dsc);
    lv_obj_set_pos(img, cx - dsc->header.w / 2, cy - dsc->header.h / 2);
  }
  const std::string pk = this->photo_key_(key);
  if (!pk.empty())
    this->bind_(img, pk, cx, cy);
  return img;
}

lv_obj_t *KisSegitoUI::number_pill_(lv_obj_t *parent, int cx, int cy, int value, bool with_coin) {
  lv_obj_t *pill = lv_obj_create(parent);
  remove_defaults(pill);
  lv_obj_set_size(pill, LV_SIZE_CONTENT, 48);
  lv_obj_set_style_radius(pill, 24, 0);
  lv_obj_set_style_bg_color(pill, lv_color_hex(0x0F1330), 0);
  lv_obj_set_style_bg_opa(pill, 200, 0);
  lv_obj_set_style_pad_hor(pill, 14, 0);
  lv_obj_set_style_pad_column(pill, 6, 0);
  lv_obj_set_flex_flow(pill, LV_FLEX_FLOW_ROW);
  lv_obj_set_flex_align(pill, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
  if (with_coin) {
    lv_obj_t *coin = lv_image_create(pill);
    lv_image_set_src(coin, this->img_("token_coin_front_28"));
  }
  lv_obj_t *label = lv_label_create(pill);
  lv_label_set_text_fmt(label, "%d", value);
  if (this->number_font_ != nullptr)
    lv_obj_set_style_text_font(label, this->number_font_, 0);
  lv_obj_set_style_text_color(label, lv_color_hex(0xFFE08A), 0);
  lv_obj_update_layout(pill);
  lv_obj_set_pos(pill, cx - lv_obj_get_width(pill) / 2, cy - 24);
  return pill;
}

// Blends a built-in image (RGB565A8, RGB565 or ARGB8888) at (x, y) over an
// RGB565A8 canvas ("over" compositing, so the canvas keeps its own alpha).
static void blend_into(lv_draw_buf_t *canvas, const lv_image_dsc_t *src, int x, int y, int opa) {
  const int cw = canvas->header.w, ch = canvas->header.h;
  const int sw = src->header.w, sh = src->header.h;
  const uint32_t cstride = canvas->header.stride;
  uint8_t *calpha = canvas->data + cstride * ch;
  const lv_color_format_t cf = static_cast<lv_color_format_t>(src->header.cf);
  const uint32_t sstride = src->header.stride;
  for (int j = 0; j < sh; j++) {
    const int ty = y + j;
    if (ty < 0 || ty >= ch)
      continue;
    auto *drow = reinterpret_cast<uint16_t *>(canvas->data + ty * cstride);
    uint8_t *arow = calpha + ty * (cstride / 2);
    for (int i = 0; i < sw; i++) {
      const int tx = x + i;
      if (tx < 0 || tx >= cw)
        continue;
      uint32_t r, g, b, a;
      if (cf == LV_COLOR_FORMAT_ARGB8888) {
        const uint8_t *p = src->data + j * sstride + i * 4;
        b = p[0];
        g = p[1];
        r = p[2];
        a = p[3];
      } else {
        const uint16_t c = reinterpret_cast<const uint16_t *>(src->data + j * sstride)[i];
        r = (c >> 8) & 0xF8;
        g = (c >> 3) & 0xFC;
        b = (c << 3) & 0xF8;
        a = cf == LV_COLOR_FORMAT_RGB565A8 ? src->data[sstride * sh + j * (sstride / 2) + i] : 255;
      }
      if (opa < 255)
        a = a * opa / 255;
      if (a == 0)
        continue;
      const uint32_t da = arow[tx];
      if (a == 255 || da == 0) {
        drow[tx] = static_cast<uint16_t>(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
        arow[tx] = static_cast<uint8_t>(a);
        continue;
      }
      const uint16_t dc = drow[tx];
      const uint32_t dr = (dc >> 8) & 0xF8, dg = (dc >> 3) & 0xFC, db = (dc << 3) & 0xF8;
      const uint32_t dw = da * (255 - a) / 255;  // what still shows of the canvas
      const uint32_t oa = a + dw;
      r = (r * a + dr * dw) / oa;
      g = (g * a + dg * dw) / oa;
      b = (b * a + db * dw) / oa;
      drow[tx] = static_cast<uint16_t>(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
      arow[tx] = static_cast<uint8_t>(oa);
    }
  }
}

// A physical-looking heap of exactly `count` coins. It grows upwards as a
// pyramid up to max_rows, then spreads sideways up to max_width coins, then
// "flows" downwards below base_y (off the screen if needed). Coins below the
// screen are counted but not drawn. The coins are composed into one picture
// (one object instead of hundreds); the newest few (count % 10) stay separate
// objects in front of it.
void KisSegitoUI::pile_(lv_obj_t *parent, int cx, int base_y, int count, uint32_t seed, int max_rows, int max_width,
                        int dx, int dy) {
  if (count <= 0)
    return;
  static const char *const VARIANTS[3] = {"token_coin_front_28", "token_coin_tilt_left_28", "token_coin_tilt_right_28"};
  const lv_image_dsc_t *dscs[3] = {this->img_(VARIANTS[0]), this->img_(VARIANTS[1]), this->img_(VARIANTS[2])};

  auto capacity = [max_rows](int width) {
    int cap = 0;
    for (int r = 0; r < max_rows && r < width; r++)
      cap += width - r;
    return cap;
  };
  int width = 1;
  while (width < max_width && capacity(width) < count)
    width++;

  // Row sizes, bottom (0) upwards, then spill rows below the base.
  struct Row {
    int y;
    int n;
  };
  std::vector<Row> rows;
  int left = count;
  for (int r = 0; r < max_rows && r < width && left > 0; r++) {
    const int n = std::min(width - r, left);
    rows.push_back({base_y - r * dy, n});
    left -= n;
  }
  int spill = 0;
  while (left > 0) {
    spill++;
    const int n = std::min(width + spill, left);
    rows.push_back({base_y + spill * dy, n});
    left -= n;
  }

  // Back to front: top pyramid rows first, then the base, then the spill.
  std::vector<size_t> order;
  for (size_t i = 0; i < rows.size(); i++)
    order.push_back(i);
  std::sort(order.begin(), order.end(), [&rows](size_t a, size_t b) { return rows[a].y < rows[b].y; });

  struct Coin {
    int x, y;  // top left in parent coordinates
    const lv_image_dsc_t *dsc;
  };
  std::vector<Coin> coins;
  for (size_t idx : order) {
    const Row &row = rows[idx];
    if (row.y - 14 > SCREEN + 16)
      continue;  // below the screen: counted, not drawn
    for (int i = 0; i < row.n; i++) {
      const uint32_t h = hash32(seed * 7919u + idx * 131u + i);
      const int jx = static_cast<int>(h % 7) - 3;
      const int jy = static_cast<int>((h >> 8) % 5) - 2;
      const int x = cx + static_cast<int>((i - (row.n - 1) / 2.0f) * dx) + jx;
      const lv_image_dsc_t *dsc = dscs[(h >> 16) % 3];
      if (dsc != nullptr)
        coins.push_back({x - 14, row.y + jy - 14, dsc});
    }
  }
  if (coins.empty())
    return;
  const size_t live = std::min<size_t>(count % 10, coins.size());
  const size_t composed = coins.size() - live;
  size_t first_live = 0;  // coins from here on are separate objects
  if (composed > 0) {
    int x0 = INT_MAX, y0 = INT_MAX, x1 = INT_MIN, y1 = INT_MIN;
    for (size_t i = 0; i < composed; i++) {
      x0 = std::min(x0, coins[i].x);
      y0 = std::min(y0, coins[i].y);
      x1 = std::max(x1, coins[i].x + static_cast<int>(coins[i].dsc->header.w));
      y1 = std::max(y1, coins[i].y + static_cast<int>(coins[i].dsc->header.h));
    }
    lv_draw_buf_t *canvas = lv_draw_buf_create(x1 - x0, y1 - y0, LV_COLOR_FORMAT_RGB565A8, LV_STRIDE_AUTO);
    if (canvas != nullptr) {
      memset(canvas->data + canvas->header.stride * canvas->header.h, 0,
             (canvas->header.stride / 2) * canvas->header.h);
      for (size_t i = 0; i < composed; i++)
        blend_into(canvas, coins[i].dsc, coins[i].x - x0, coins[i].y - y0);
      lv_obj_t *img = lv_image_create(parent);
      lv_image_set_src(img, canvas);
      lv_obj_set_pos(img, x0, y0);
      lv_obj_add_event_cb(
          img,
          [](lv_event_t *e) {
            auto *buf = static_cast<lv_draw_buf_t *>(lv_event_get_user_data(e));
            lv_image_cache_drop(buf);
            lv_image_header_cache_drop(buf);
            lv_draw_buf_destroy(buf);
          },
          LV_EVENT_DELETE, canvas);
      first_live = composed;
    }
    // Without memory for the picture every coin is an object (slower).
  }
  for (size_t i = first_live; i < coins.size(); i++) {
    lv_obj_t *coin = lv_image_create(parent);
    lv_image_set_src(coin, coins[i].dsc);
    lv_obj_set_pos(coin, coins[i].x, coins[i].y);
  }
}

void KisSegitoUI::ring_point_(float p, int radius, int *x, int *y) const {
  // Track position p in [0, 1]: 0 = 11 o'clock, then counter-clockwise the
  // long way round, 1 = 1 o'clock. LVGL angles: 0 deg = 3 o'clock, clockwise.
  const float deg = 240.0f - 300.0f * p;
  const float rad = deg * static_cast<float>(M_PI) / 180.0f;
  *x = CENTER + static_cast<int>(std::round(radius * std::cos(rad)));
  *y = CENTER + static_cast<int>(std::round(radius * std::sin(rad)));
}

lv_obj_t *KisSegitoUI::track_arc_(lv_obj_t *parent, int radius, int width, float p_from, float p_to,
                                  lv_color_t color) {
  lv_obj_t *arc = lv_arc_create(parent);
  lv_obj_remove_style_all(arc);
  lv_obj_remove_flag(arc, LV_OBJ_FLAG_CLICKABLE);
  lv_obj_set_size(arc, 2 * radius, 2 * radius);
  lv_obj_set_pos(arc, CENTER - radius, CENTER - radius);
  auto norm = [](float deg) {
    while (deg < 0)
      deg += 360;
    while (deg >= 360)
      deg -= 360;
    return deg;
  };
  // Drawn clockwise from the later position to the earlier one.
  const float start = norm(240.0f - 300.0f * p_to);
  const float end = norm(240.0f - 300.0f * p_from);
  lv_arc_set_bg_angles(arc, static_cast<lv_value_precise_t>(start), static_cast<lv_value_precise_t>(end));
  lv_obj_set_style_arc_width(arc, width, LV_PART_MAIN);
  lv_obj_set_style_arc_color(arc, color, LV_PART_MAIN);
  lv_obj_set_style_arc_rounded(arc, true, LV_PART_MAIN);
  lv_obj_set_style_arc_opa(arc, LV_OPA_COVER, LV_PART_MAIN);
  lv_obj_set_style_arc_opa(arc, LV_OPA_TRANSP, LV_PART_INDICATOR);
  lv_obj_set_style_bg_opa(arc, LV_OPA_TRANSP, LV_PART_KNOB);
  return arc;
}

std::vector<int> KisSegitoUI::shop_() const {
  // Rewards the selected child can see: an unlocked piggy bank is not sold
  // again (#11).
  std::vector<int> shop;
  const bool unlocked = !this->children_.empty() && this->children_[this->child_].piggy_unlocked;
  for (size_t i = 0; i < this->rewards_.size(); i++) {
    if (!(this->rewards_[i].piggy_unlock && unlocked))
      shop.push_back(static_cast<int>(i));
  }
  return shop;
}

std::vector<FnItem> KisSegitoUI::functions_for_(const Child &child) const {
  // Today's routines for this child first, then rewards, piggy bank, tokens.
  std::vector<FnItem> fns;
  for (size_t i = 0; i < this->routines_.size(); i++) {
    if (applies(this->routines_[i].children, child.id))
      fns.push_back({FnType::ROUTINE, static_cast<int>(i)});
  }
  fns.push_back({FnType::REWARDS, -1});
  if (child.piggy_unlocked)
    fns.push_back({FnType::PIGGY, -1});
  fns.push_back({FnType::TOKENS, -1});
  return fns;
}

// ---------------------------------------------------------------- Navigation

void KisSegitoUI::show_(Screen screen) {
  if (this->screen_obj_ == nullptr)
    return;
  // Deleting the screen's objects also deletes their animations.
  this->busy_ = false;
  this->cancel_idle_anim_();
  lv_obj_clean(this->screen_obj_);
  this->carousel_.forget();  // its slots were just deleted
  this->task_big_ = this->timeline_ = this->piggy_label_ = nullptr;
  this->confirm_ring_ = this->confirm_no_ = this->confirm_yes_obj_ = nullptr;
  this->shown_reward_ = -1;
  this->pending_rebuild_ = false;
  this->screen_ = screen;
  if (this->children_.empty()) {
    // No children configured yet: only the track and the brand mark.
    this->screen_ = Screen::CHILDREN;
    lv_obj_set_style_bg_color(this->root_, lv_color_hex(BASE_BG), 0);
    this->apply_background_("");
    this->build_track_();
    return;
  }
  if ((screen == Screen::ROUTINE && this->routines_.empty()) ||
      ((screen == Screen::REWARDS || screen == Screen::CONFIRM) && this->shop_().empty()))
    screen = this->screen_ = Screen::FUNCTIONS;
  if (screen != Screen::CHILDREN && !this->children_[this->child_].selectable)
    screen = this->screen_ = Screen::CHILDREN;
  const Child &child = this->children_[this->child_];
  const lv_color_t bg = screen == Screen::CHILDREN ? lv_color_hex(BASE_BG) : this->tint_(child.color, 46);
  lv_obj_set_style_bg_color(this->root_, bg, 0);
  // The general background on the child selector, the child's own (or the
  // general one) on that child's screens; none: the plain colour. While a new
  // background is still downloading, the previous one stays.
  this->apply_background_(screen == Screen::CHILDREN ? "" : child.background);
  this->build_track_();
  switch (screen) {
    case Screen::CHILDREN:
      this->build_children_();
      break;
    case Screen::FUNCTIONS:
      this->build_functions_();
      break;
    case Screen::REWARDS:
      this->build_rewards_();
      break;
    case Screen::CONFIRM:
      this->build_confirm_();
      break;
    case Screen::ROUTINE:
      this->build_routine_();
      break;
    case Screen::TOKENS:
      this->build_tokens_();
      break;
    case Screen::PIGGY:
      this->build_piggy_();
      break;
    case Screen::NONE:
      break;
  }
}

void KisSegitoUI::rotate(int dir) {
  if (this->started_ && dir != 0)
    this->input_.push_back(dir > 0 ? 1 : -1);
}

void KisSegitoUI::click() {
  if (this->started_)
    this->input_.push_back(2);
}

void KisSegitoUI::long_press() {
  if (this->started_)
    this->input_.push_back(3);
}

// One queued input per loop, so the screen is drawn between steps.
void KisSegitoUI::handle_input_() {
  if (this->input_.empty())
    return;
  const int in = this->input_.front();
  this->input_.pop_front();
  if (in == 2) {
    this->do_click_();
  } else if (in == 3) {
    this->do_long_press_();
  } else {
    // Turns that piled up while the screen was busy are added up: the
    // carousel jumps to the item before the last at once (one redraw, however
    // many turns) and slides the last step, so it stops when the knob stops.
    int net = in;
    while (!this->input_.empty() && (this->input_.front() == 1 || this->input_.front() == -1)) {
      net += this->input_.front();
      this->input_.pop_front();
    }
    if (net == 0)
      return;
    const int dir = net > 0 ? 1 : -1;
    const bool carousel = this->screen_ == Screen::CHILDREN || this->screen_ == Screen::FUNCTIONS ||
                          this->screen_ == Screen::REWARDS;
    if (carousel && std::abs(net) > 1) {
      this->do_rotate_(net - dir, false);
    } else {
      for (int k = 1; k < std::abs(net); k++)
        this->do_rotate_(dir, false);
    }
    this->do_rotate_(dir, true);
  }
}

void KisSegitoUI::do_rotate_(int dir, bool animate) {
  if (!animate && std::abs(dir) >= 1 &&
      (this->screen_ == Screen::CHILDREN || this->screen_ == Screen::FUNCTIONS || this->screen_ == Screen::REWARDS)) {
    if (this->busy_ || this->children_.empty())
      return;
    this->last_input_ms_ = millis();
    this->cancel_idle_anim_();
    this->carousel_.jump(dir);
    if (this->screen_ == Screen::CHILDREN) {
      this->select_child_(this->carousel_.selected());
    } else if (this->screen_ == Screen::FUNCTIONS) {
      this->function_ = this->carousel_.selected();
    } else {
      this->reward_ = this->shop_()[this->carousel_.selected()];
    }
    return;
  }
  this->last_input_ms_ = millis();
  this->cancel_idle_anim_();
  if (this->busy_ || this->children_.empty())
    return;
  switch (this->screen_) {
    case Screen::CHILDREN:
      this->carousel_.rotate(dir, animate);
      this->select_child_(this->carousel_.selected());
      break;
    case Screen::FUNCTIONS:
      this->carousel_.rotate(dir, animate);
      this->function_ = this->carousel_.selected();
      break;
    case Screen::REWARDS:
      this->carousel_.rotate(dir, animate);
      this->reward_ = this->shop_()[this->carousel_.selected()];
      break;
    case Screen::PIGGY: {
      // Turning chooses how many tokens move: clockwise into the piggy bank
      // (up to the wallet), anticlockwise out of it (up to the piggy bank).
      const Child &c = this->children_[this->child_];
      this->piggy_amount_ = std::max(-c.piggy, std::min(c.wallet, this->piggy_amount_ + dir));
      this->update_piggy_amount_();
      break;
    }
    case Screen::CONFIRM: {
      this->confirm_yes_ = !this->confirm_yes_;
      lv_obj_t *target = this->confirm_yes_ ? this->confirm_yes_obj_ : this->confirm_no_;
      lv_obj_t *other = this->confirm_yes_ ? this->confirm_no_ : this->confirm_yes_obj_;
      lv_obj_set_pos(this->confirm_ring_, lv_obj_get_x(target) + lv_obj_get_width(target) / 2 - 58,
                     lv_obj_get_y(target) + lv_obj_get_height(target) / 2 - 58);
      lv_obj_set_style_image_opa(target, LV_OPA_COVER, 0);
      lv_obj_set_style_image_opa(other, 140, 0);
      break;
    }
    default:
      break;
  }
}

void KisSegitoUI::shake_(lv_obj_t *target) {
  if (target == nullptr || this->anim_ms_(300) == 0)
    return;
  lv_anim_t a;
  lv_anim_init(&a);
  lv_anim_set_var(&a, target);
  lv_anim_set_values(&a, -10, 10);
  lv_anim_set_duration(&a, 60);
  lv_anim_set_reverse_duration(&a, 60);
  lv_anim_set_repeat_count(&a, 2);
  lv_anim_set_exec_cb(&a, [](void *var, int32_t v) { lv_obj_set_style_translate_x(static_cast<lv_obj_t *>(var), v, 0); });
  lv_anim_set_completed_cb(&a, [](lv_anim_t *anim) {
    lv_obj_set_style_translate_x(static_cast<lv_obj_t *>(anim->var), 0, 0);
  });
  lv_anim_start(&a);
}

void KisSegitoUI::do_click_() {
  this->last_input_ms_ = millis();
  this->cancel_idle_anim_();
  if (this->busy_ || this->children_.empty())
    return;
  Child &child = this->children_[this->child_];
  switch (this->screen_) {
    case Screen::CHILDREN:
      if (!child.selectable) {
        // Another child's knob: visible, but locked here.
        this->shake_(this->carousel_.center_slot());
        return;
      }
      this->function_ = 0;
      this->show_(Screen::FUNCTIONS);
      break;
    case Screen::FUNCTIONS: {
      const auto fns = this->functions_for_(child);
      const FnItem &fn = fns[this->function_ % fns.size()];
      switch (fn.type) {
        case FnType::ROUTINE:
          this->routine_ = fn.routine;
          this->show_(Screen::ROUTINE);
          break;
        case FnType::REWARDS:
          if (!this->shop_().empty())
            this->show_(Screen::REWARDS);
          break;
        case FnType::PIGGY:
          this->show_(Screen::PIGGY);
          break;
        case FnType::TOKENS:
          this->show_(Screen::TOKENS);
          break;
      }
      break;
    }
    case Screen::REWARDS: {
      const Reward &r = this->rewards_[this->reward_ % this->rewards_.size()];
      if (r.cost > child.wallet) {
        // Locked: a short shake instead of opening the confirmation.
        this->shake_(this->carousel_.center_slot());
        return;
      }
      this->confirm_yes_ = false;
      this->show_(Screen::CONFIRM);
      break;
    }
    case Screen::CONFIRM: {
      if (!this->confirm_yes_) {
        this->show_(Screen::REWARDS);
        return;
      }
      if (!this->connected_) {
        this->refuse_offline_(this->confirm_yes_obj_);
        return;
      }
      const Reward &r = this->rewards_[this->reward_ % this->rewards_.size()];
      // Shown at once; Home Assistant books it and sends the real balance.
      child.wallet -= r.cost;
      if (r.piggy_unlock)
        child.piggy_unlocked = true;
      this->send_action_("redeem", ",\"r\":\"" + r.id + "\"");
      // The exact number of spent tokens fly from the wallet to the reward.
      this->busy_ = true;
      const int flying = std::min(r.cost, 40);
      for (int i = 0; i < flying; i++) {
        lv_obj_t *coin = this->image_(this->screen_obj_, "token_coin_front_28", CENTER, 420);
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, coin);
        lv_anim_set_values(&a, lv_obj_get_y(coin), 150 + static_cast<int>(hash32(i) % 30));
        lv_anim_set_delay(&a, i * 45);
        lv_anim_set_duration(&a, this->anim_ms_(450));
        lv_anim_set_exec_cb(&a, [](void *var, int32_t v) { lv_obj_set_y(static_cast<lv_obj_t *>(var), v); });
        lv_anim_set_path_cb(&a, lv_anim_path_ease_in);
        lv_anim_set_completed_cb(&a, [](lv_anim_t *anim) {
          lv_obj_add_flag(static_cast<lv_obj_t *>(anim->var), LV_OBJ_FLAG_HIDDEN);
        });
        lv_anim_start(&a);
      }
      lv_timer_t *done = lv_timer_create(
          [](lv_timer_t *t) {
            auto *self = static_cast<KisSegitoUI *>(lv_timer_get_user_data(t));
            lv_timer_delete(t);
            self->busy_ = false;
            self->show_(Screen::REWARDS);
          },
          this->anim_ms_(450) + flying * 45 + 300, this);
      lv_timer_set_repeat_count(done, 1);
      break;
    }
    case Screen::ROUTINE:
      if (!this->connected_) {
        this->refuse_offline_(this->task_big_);
        return;
      }
      this->complete_task_();
      break;
    case Screen::PIGGY: {
      const int amount = this->piggy_amount_;
      if (amount == 0)
        return;
      if (!this->connected_) {
        this->refuse_offline_(this->piggy_label_);
        return;
      }
      // Shown at once; Home Assistant books it and sends the real balances.
      child.wallet -= amount;
      child.piggy += amount;
      this->piggy_amount_ = 0;
      this->send_action_("piggy", ",\"n\":" + std::to_string(amount));
      // Exactly that many tokens fly between the wallet and the piggy bank.
      this->busy_ = true;
      const int flying = std::min(std::abs(amount), 40);
      for (int i = 0; i < flying; i++) {
        const int from = amount > 0 ? 410 : 185;
        const int to = amount > 0 ? 185 : 410;
        lv_obj_t *coin = this->image_(this->screen_obj_, "token_coin_front_28", CENTER, from);
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, coin);
        lv_anim_set_values(&a, from - 14, to - 14 + static_cast<int>(hash32(i) % 20) - 10);
        lv_anim_set_delay(&a, i * 45);
        lv_anim_set_duration(&a, this->anim_ms_(450));
        lv_anim_set_exec_cb(&a, [](void *var, int32_t v) { lv_obj_set_y(static_cast<lv_obj_t *>(var), v); });
        lv_anim_set_path_cb(&a, lv_anim_path_ease_in_out);
        lv_anim_set_completed_cb(&a, [](lv_anim_t *anim) {
          lv_obj_add_flag(static_cast<lv_obj_t *>(anim->var), LV_OBJ_FLAG_HIDDEN);
        });
        lv_anim_start(&a);
      }
      lv_timer_t *done = lv_timer_create(
          [](lv_timer_t *t) {
            auto *self = static_cast<KisSegitoUI *>(lv_timer_get_user_data(t));
            lv_timer_delete(t);
            self->busy_ = false;
            self->show_(Screen::PIGGY);
          },
          this->anim_ms_(450) + flying * 45 + 300, this);
      lv_timer_set_repeat_count(done, 1);
      break;
    }
    default:
      break;
  }
}

void KisSegitoUI::do_long_press_() {
  this->last_input_ms_ = millis();
  switch (this->screen_) {
    case Screen::CHILDREN:
      // On the home screen, while Home Assistant is not connected: try to
      // connect again.
      if (!this->connected_)
        this->reconnect_();
      break;
    case Screen::FUNCTIONS:
      this->show_(Screen::CHILDREN);
      break;
    case Screen::REWARDS:
    case Screen::ROUTINE:
    case Screen::TOKENS:
    case Screen::PIGGY:
      this->show_(Screen::FUNCTIONS);
      break;
    case Screen::CONFIRM:
      this->show_(Screen::REWARDS);
      break;
    default:
      break;
  }
}

// Home Assistant subscribed to the knob's states: connected. (Other API
// clients, such as a log viewer, do not count.)
void KisSegitoUI::poll_connection_() {
#ifdef USE_API
  if (api::global_api_server == nullptr)
    return;
  const bool connected = api::global_api_server->is_connected_with_state_subscription();
  if (connected != this->connected_)
    this->set_connected(connected);
#endif
}

void KisSegitoUI::reconnect_() {
  ESP_LOGI(TAG, "Reconnecting to Home Assistant (long press)");
#ifdef USE_API
  if (api::global_api_server != nullptr) {
    // Closing the connections makes Home Assistant connect again and send
    // the texts and the data anew.
    for (const auto &client : api::global_api_server->active_clients())
      client->on_fatal_error();
  }
#endif
  this->set_connected(false);
  this->refuse_offline_(nullptr);  // the offline mark pulses
}

// ---------------------------------------------------------------- Screens

// What a picture key shows right now (changes when the picture arrives or is
// replaced), for the carousel item signatures.
std::string KisSegitoUI::pic_state_(const std::string &key) const {
  const std::string pk = this->photo_key_(key);
  if (pk.empty())
    return key;
  // Which version of the picture an item shows; whether it is in memory right
  // now does not matter (a stored item has it drawn in already).
  if (!this->photo_seen_.count(pk))
    return key + "@-";
  auto ver = this->photo_version_.find(pk);
  return key + "@" + std::to_string(ver != this->photo_version_.end() ? ver->second : 0u);
}

void KisSegitoUI::build_children_() {
  this->carousel_.sig = [this](int index) {
    const Child &c = this->children_[index];
    return "c|" + c.id + "|" + this->pic_state_(c.avatar + "_180") + "|" + std::to_string(c.color) + "|" +
           std::to_string(c.wallet) + "|" + (c.selectable ? "1" : "0") +
           (c.pending_interest > 0 && c.piggy_unlocked ? "i" : "");
  };
  this->carousel_.create(
      // Slot from y = 60 to 340: avatar and the token count. Each slot is
      // drawn once into a picture, so it slides smoothly (#10).
      this->screen_obj_, static_cast<int>(this->children_.size()), this->child_, 300, 280, 60, 250,
      [this](lv_obj_t *slot, int index) {
        const Child &c = this->children_[index];
        const int cx = 150;  // slot centre
        // Children of another knob: visible but greyed and locked here.
        const lv_color_t disc = c.selectable ? lv_color_hex(c.color) : lv_color_hex(0x4A4F6A);
        this->disc_(slot, cx, 105, 190, disc);
        lv_obj_t *avatar = this->image_(slot, c.avatar + "_180", cx, 105);
        // The tokens as one coin and the number (the full pile is on the
        // token screen).
        this->number_pill_(slot, cx, 236, c.wallet, true);
        if (c.pending_interest > 0 && c.piggy_unlocked)
          this->image_(slot, "badge_piggy_plus_48", cx - 72, 40);  // interest waiting
        if (!c.selectable) {
          lv_obj_set_style_image_recolor(avatar, lv_color_hex(0x8C96A5), 0);
          lv_obj_set_style_image_recolor_opa(avatar, 150, 0);
          this->image_(slot, "status_lock_64", cx + 70, 170);
        }
      },
      this->anim_ms_(260), true);
}

void KisSegitoUI::build_functions_() {
  const Child &child = this->children_[this->child_];
  const auto fns = this->functions_for_(child);
  this->function_ %= static_cast<int>(fns.size());
  this->carousel_.sig = [this, fns](int index) {
    const FnItem &fn = fns[index];
    std::string icon = fn.type == FnType::ROUTINE ? this->routines_[fn.routine].icon : std::to_string(static_cast<int>(fn.type));
    return "f|" + this->pic_state_(icon + "_160") + "|" + std::to_string(this->children_[this->child_].color);
  };
  this->carousel_.create(
      this->screen_obj_, static_cast<int>(fns.size()), this->function_, 240, 240, 145, 230,
      [this, fns](lv_obj_t *slot, int index) {
        const Child &c = this->children_[this->child_];
        this->disc_(slot, 120, 120, 210, lv_color_mix(lv_color_hex(c.color), lv_color_white(), 90));
        const FnItem &fn = fns[index];
        std::string icon;
        switch (fn.type) {
          case FnType::ROUTINE:
            icon = this->routines_[fn.routine].icon;
            break;
          case FnType::REWARDS:
            icon = "fn_rewards";
            break;
          case FnType::PIGGY:
            icon = "fn_piggy";
            break;
          case FnType::TOKENS:
            icon = "fn_tokens";
            break;
        }
        if (!this->has_image_(icon + "_160"))
          icon = "fn_rewards";
        this->image_(slot, icon + "_160", 120, 120);
      },
      this->anim_ms_(240), true);
  // Small child marker at the top centre: context only, not the focus.
  this->disc_(this->screen_obj_, CENTER, 96, 76, lv_color_hex(child.color));
  lv_obj_t *avatar = this->image_(this->screen_obj_, child.avatar + "_180", CENTER, 96);
  lv_image_set_scale(avatar, 92);  // 180 px -> ~65 px
}

void KisSegitoUI::build_rewards_() {
  const Child &child = this->children_[this->child_];
  // The child's shop: the piggy-bank unlock is left out once it is unlocked.
  const std::vector<int> shop = this->shop_();
  int position = 0;
  for (size_t i = 0; i < shop.size(); i++) {
    if (shop[i] == this->reward_)
      position = static_cast<int>(i);
  }
  this->reward_ = shop[position];
  this->carousel_.sig = [this, shop](int index) {
    const Reward &r = this->rewards_[shop[index]];
    const Child &c = this->children_[this->child_];
    return "r|" + r.id + "|" + this->pic_state_(r.icon + "_160") + "|" + std::to_string(r.cost) + "|" +
           (r.cost > c.wallet ? "l" : "") + "|" + std::to_string(c.color);
  };
  this->carousel_.create(
      this->screen_obj_, static_cast<int>(shop.size()), position, 260, 290, 60, 240,
      [this, shop](lv_obj_t *slot, int index) {
        const Reward &r = this->rewards_[shop[index]];
        const Child &c = this->children_[this->child_];
        // The lock only means "not enough tokens".
        const bool locked = r.cost > c.wallet;
        this->disc_(slot, 130, 120, 200,
                    locked ? lv_color_hex(0x4A4F6A) : lv_color_mix(lv_color_hex(c.color), lv_color_white(), 80));
        lv_obj_t *icon = this->image_(slot, r.icon + "_160", 130, 120);
        if (locked) {
          lv_obj_set_style_image_recolor(icon, lv_color_hex(0x8C96A5), 0);
          lv_obj_set_style_image_recolor_opa(icon, 150, 0);
          this->image_(slot, "status_lock_64", 205, 190);
        }
        // The price as a small pile of exactly that many tokens.
        // The price as one coin and the number.
        this->number_pill_(slot, 130, 252, r.cost, true);
      },
      this->anim_ms_(240), true);
  // Current wallet below the carousel.
  this->number_pill_(this->screen_obj_, CENTER, 420, child.wallet, true);
}

void KisSegitoUI::build_confirm_() {
  const Reward &r = this->rewards_[this->reward_ % this->rewards_.size()];
  const Child &child = this->children_[this->child_];
  this->disc_(this->screen_obj_, CENTER, 160, 180, lv_color_mix(lv_color_hex(child.color), lv_color_white(), 80));
  this->image_(this->screen_obj_, r.icon + "_160", CENTER, 160);
  this->number_pill_(this->screen_obj_, CENTER, 272, r.cost, true);
  this->confirm_no_ = this->image_(this->screen_obj_, "action_x_88", 160, 345);
  this->confirm_yes_obj_ = this->image_(this->screen_obj_, "action_check_88", 320, 345);
  // The selected choice is circled (not only coloured).
  this->confirm_ring_ = lv_obj_create(this->screen_obj_);
  remove_defaults(this->confirm_ring_);
  lv_obj_set_size(this->confirm_ring_, 116, 116);
  lv_obj_set_style_radius(this->confirm_ring_, LV_RADIUS_CIRCLE, 0);
  lv_obj_set_style_border_width(this->confirm_ring_, 6, 0);
  lv_obj_set_style_border_color(this->confirm_ring_, lv_color_white(), 0);
  lv_obj_set_style_border_opa(this->confirm_ring_, LV_OPA_COVER, 0);
  lv_obj_set_pos(this->confirm_ring_, 160 - 58, 345 - 58);
  lv_obj_set_style_image_opa(this->confirm_yes_obj_, 140, 0);
  this->number_pill_(this->screen_obj_, CENTER, 420, child.wallet, true);
}

void KisSegitoUI::build_tokens_() {
  const Child &child = this->children_[this->child_];
  this->pile_(this->screen_obj_, CENTER, 290, child.wallet, 500u + this->child_, 11, 18, 19, 10);
  this->number_pill_(this->screen_obj_, CENTER, 335, child.wallet, true);
  // Streak: flame + one marker per day of the target.
  this->image_(this->screen_obj_, "streak_flame_64", CENTER, 100);
  const int n = std::max(child.streak_target, 1);
  const int step = 30;
  const int x0 = CENTER - (n - 1) * step / 2;
  for (int i = 0; i < n; i++) {
    const int x = x0 + i * step;
    if (i < child.streak) {
      this->image_(this->screen_obj_, "action_check_small_24", x, 392);
    } else {
      lv_obj_t *dot = this->disc_(this->screen_obj_, x, 392, 22, lv_color_hex(BASE_BG));
      lv_obj_set_style_border_width(dot, 3, 0);
      lv_obj_set_style_border_color(dot, lv_color_hex(0x8C96A5), 0);
    }
  }
}

void KisSegitoUI::build_piggy_() {
  Child &child = this->children_[this->child_];
  this->piggy_amount_ = 0;
  if (child.pending_interest > 0) {
    // Interest paid while the child was away: drop exactly that many tokens
    // into the piggy bank once, then tell Home Assistant it was shown.
    const int coins = std::min(child.pending_interest, 40);
    child.pending_interest = 0;
    this->send_action_("seen", "");
    if (this->anim_ms_(500) > 0) {
      for (int i = 0; i < coins; i++) {
        lv_obj_t *coin = this->image_(this->screen_obj_, "token_coin_front_28", CENTER - 40 + static_cast<int>(hash32(i) % 80), 60);
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, coin);
        lv_anim_set_values(&a, 46, 160);
        lv_anim_set_delay(&a, 200 + i * 80);
        lv_anim_set_duration(&a, this->anim_ms_(500));
        lv_anim_set_exec_cb(&a, [](void *var, int32_t v) { lv_obj_set_y(static_cast<lv_obj_t *>(var), v); });
        lv_anim_set_path_cb(&a, lv_anim_path_ease_in);
        lv_anim_set_completed_cb(&a, [](lv_anim_t *anim) {
          lv_obj_add_flag(static_cast<lv_obj_t *>(anim->var), LV_OBJ_FLAG_HIDDEN);
        });
        lv_anim_start(&a);
      }
    }
  }
  this->image_(this->screen_obj_, "piggy_large_180", CENTER, 175);
  this->number_pill_(this->screen_obj_, CENTER, 268, child.piggy, true);
  // The amount to move, chosen by turning; pressing moves it.
  this->piggy_label_ = lv_label_create(this->screen_obj_);
  if (this->number_font_ != nullptr)
    lv_obj_set_style_text_font(this->piggy_label_, this->number_font_, 0);
  this->update_piggy_amount_();
  // The wallet is a separate thing: shown at the bottom.
  this->number_pill_(this->screen_obj_, CENTER, 410, child.wallet, true);
}

void KisSegitoUI::cancel_idle_anim_() {
  for (lv_obj_t **obj : {&this->idle_coin_, &this->idle_hand_}) {
    if (*obj != nullptr) {
      lv_anim_delete(*obj, nullptr);
      lv_obj_delete(*obj);
      *obj = nullptr;
    }
  }
}

// Keyframes of the idle animation (ms): the token rolls off, rests, is
// carried back; the hand comes in, carries it and leaves.
static constexpr int IDLE_ROLL_END = 700, IDLE_HAND_IN = 900, IDLE_CARRY = 1600, IDLE_BACK = 2200,
                     IDLE_HAND_OUT = 2300, IDLE_END = 2800;
static int idle_top_y = 260;  // top of the pile while the animation runs

static int lerp(int a, int b, int t, int t0, int t1) {
  if (t <= t0)
    return a;
  if (t >= t1)
    return b;
  const float k = static_cast<float>(t - t0) / static_cast<float>(t1 - t0);
  const float e = k * k * (3 - 2 * k);  // smoothstep
  return a + static_cast<int>((b - a) * e);
}

static void idle_coin_cb(void *var, int32_t t) {
  auto *coin = static_cast<lv_obj_t *>(var);
  const int x0 = CENTER - 14, x1 = CENTER + 56, rest_y = 346 - 14, top = idle_top_y - 14;
  int x, y;
  if (t < IDLE_CARRY) {
    x = lerp(x0, x1, t, 0, IDLE_ROLL_END);
    // Falling with a small bounce at the end.
    const int fall = lerp(top, rest_y, t, 0, IDLE_ROLL_END - 150);
    const int bounce = (t > IDLE_ROLL_END - 150 && t < IDLE_ROLL_END) ? -8 : 0;
    y = fall + bounce;
    lv_image_set_rotation(coin, lerp(0, 7200, t, 0, IDLE_ROLL_END));
  } else {
    x = lerp(x1, x0, t, IDLE_CARRY, IDLE_BACK);
    y = lerp(rest_y, top, t, IDLE_CARRY, IDLE_BACK);
  }
  lv_obj_set_pos(coin, x, y);
}

static void idle_hand_cb(void *var, int32_t t) {
  auto *hand = static_cast<lv_obj_t *>(var);
  const int out = SCREEN + 8, x1 = CENTER + 56, x0 = CENTER - 14;
  int x;
  if (t < IDLE_CARRY)
    x = lerp(out, x1 + 4, t, IDLE_HAND_IN, IDLE_HAND_IN + 500);
  else if (t < IDLE_HAND_OUT)
    x = lerp(x1 + 4, x0 + 4, t, IDLE_CARRY, IDLE_BACK);
  else
    x = lerp(x0 + 4, out, t, IDLE_HAND_OUT, IDLE_END);
  lv_obj_set_x(hand, x);
}

void KisSegitoUI::idle_pile_anim_() {
  // A token slips off the top of the centred child's pile and rolls aside;
  // a cartoon hand comes in and puts it back. Any input cancels it.
  const Child &c = this->children_[this->child_];
  if (c.wallet <= 0 || this->idle_coin_ != nullptr)
    return;
  idle_top_y = 300 - std::min(c.wallet, 12) * 4;
  this->idle_coin_ = this->image_(this->screen_obj_, "token_coin_front_28", CENTER, idle_top_y);
  lv_image_set_pivot(this->idle_coin_, 14, 14);
  this->idle_hand_ = this->image_(this->screen_obj_, "hand_cartoon_64", SCREEN + 40, 346);
  for (lv_obj_t *obj : {this->idle_coin_, this->idle_hand_}) {
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, obj);
    lv_anim_set_values(&a, 0, IDLE_END);
    lv_anim_set_duration(&a, IDLE_END);
    lv_anim_set_exec_cb(&a, obj == this->idle_coin_ ? idle_coin_cb : idle_hand_cb);
    lv_anim_start(&a);
  }
  lv_timer_t *t = lv_timer_create(
      [](lv_timer_t *timer) {
        auto *self = static_cast<KisSegitoUI *>(lv_timer_get_user_data(timer));
        lv_timer_delete(timer);
        self->cancel_idle_anim_();
      },
      IDLE_END + 100, this);
  lv_timer_set_repeat_count(t, 1);
}

void KisSegitoUI::update_piggy_amount_() {
  if (this->piggy_label_ == nullptr)
    return;
  const int n = this->piggy_amount_;
  if (n == 0) {
    lv_label_set_text(this->piggy_label_, "+/-");  // number font: digits, + - / only
    lv_obj_set_style_text_color(this->piggy_label_, lv_color_hex(0x8C96A5), 0);
  } else {
    lv_label_set_text_fmt(this->piggy_label_, "%+d", n);
    lv_obj_set_style_text_color(this->piggy_label_, lv_color_hex(n > 0 ? ZONE_DEPOSIT : ZONE_WITHDRAW), 0);
  }
  lv_obj_update_layout(this->piggy_label_);
  lv_obj_set_pos(this->piggy_label_, CENTER - lv_obj_get_width(this->piggy_label_) / 2,
                 340 - lv_obj_get_height(this->piggy_label_) / 2);
}

// ---------------------------------------------------------------- Routine

Routine &KisSegitoUI::current_routine_() { return this->routines_[this->routine_ % this->routines_.size()]; }

// Position of a moment on a routine's track (0 = start, 1 = end).
static float track_p(const Routine &r, int64_t t) {
  const float total = static_cast<float>(std::max<int64_t>(r.end - r.start, 1));
  return std::max(0.0f, std::min(1.0f, static_cast<float>(t - r.start) / total));
}

int KisSegitoUI::routine_reward_now_() const {
  // Tokens for reaching the child's next checkpoint now (time bands from HA).
  if (this->routines_.empty() || this->children_.empty())
    return 0;
  const Routine &r = this->routines_[this->routine_ % this->routines_.size()];
  const Checkpoint *cp = this->next_checkpoint_(r);
  return cp == nullptr ? 0 : reward_for(cp->bands, cp->t - this->now_());
}

void KisSegitoUI::build_routine_() {
  // The time track (zones, checkpoints, top gap) is drawn by build_track_().
  Routine &r = this->current_routine_();
  // Current task, big, and the bottom semicircle timeline.
  this->timeline_ = lv_obj_create(this->screen_obj_);
  remove_defaults(this->timeline_);
  lv_obj_set_size(this->timeline_, SCREEN, SCREEN);
  int current = -1;
  for (size_t i = 0; i < r.tasks.size(); i++) {
    if (!this->is_done_(r, r.tasks[i].id)) {
      current = static_cast<int>(i);
      break;
    }
  }
  this->task_big_ =
      this->image_(this->screen_obj_, current >= 0 ? r.tasks[current].icon + "_150" : "action_check_88", CENTER, 205);
  lv_image_set_pivot(this->task_big_, 75, 75);

  // Completed tasks collect on the left (grey), future ones on the right.
  int done_slot = 0, future_slot = 0;
  for (size_t i = 0; i < r.tasks.size(); i++) {
    if (static_cast<int>(i) == current)
      continue;
    const bool done = this->is_done_(r, r.tasks[i].id);
    const float deg = done ? 90.0f + 30.0f + 20.0f * done_slot++ : 90.0f - 30.0f - 20.0f * future_slot++;
    const float rad = deg * static_cast<float>(M_PI) / 180.0f;
    const int tx = CENTER + static_cast<int>(150 * std::cos(rad));
    const int ty = CENTER + static_cast<int>(150 * std::sin(rad));
    lv_obj_t *icon = this->image_(this->timeline_, r.tasks[i].icon + "_40", tx, ty);
    if (done) {
      lv_obj_set_style_image_recolor(icon, lv_color_hex(0x8C96A5), 0);
      lv_obj_set_style_image_recolor_opa(icon, 200, 0);
      lv_obj_set_style_image_opa(icon, 170, 0);
    }
  }
}

// ---------------------------------------------------------------- Time track

Routine *KisSegitoUI::track_routine_() {
  // On a routine screen its own routine; elsewhere the one running now for
  // the selected child (or for anyone).
  if (this->routines_.empty())
    return nullptr;
  if (this->screen_ == Screen::ROUTINE)
    return &this->current_routine_();
  const int64_t now = this->now_();
  const std::string child_id = this->children_.empty() ? "" : this->children_[this->child_].id;
  Routine *any = nullptr;
  for (auto &r : this->routines_) {
    if (now < r.start || now >= r.end)
      continue;
    if (applies(r.children, child_id))
      return &r;
    if (any == nullptr)
      any = &r;
  }
  return any;
}

// The ring of the time track (the band, the shared track with its zones and
// the dimmed elapsed part, the selected child's inner track) is computed pixel
// by pixel into small tiles along the ring (TRACK_TILE px squares), shown as
// pictures in their own layer. Drawing these arcs with LVGL on every frame was
// what made sliding slow; computing them takes a few tens of ms and happens
// only when something on the ring changes. The tiles stay on screen while new
// content is computed into them.
static constexpr int TRACK_TILE = 96;  // few large tiles: little work per frame
struct TrackTile {
  int x, y;  // cell origin
  lv_draw_buf_t *buf;
  lv_obj_t *img;
};
static std::vector<TrackTile> g_track_tiles;
// A glow in the selected child's colour around the inner track and the
// shared track: this wide on each side, at most this opaque.
static constexpr int GLOW_W = INNER_W;
static constexpr int GLOW_MAX = 115;  // of 255: well under half the colour

static float smooth01(float x) {
  x = std::max(0.0f, std::min(1.0f, x));
  return x * x * (3 - 2 * x);
}

// atan2 to about 0.3 degrees, much quicker than atan2f.
static float fast_atan2(float y, float x) {
  const float ax = std::fabs(x), ay = std::fabs(y);
  const float mx = std::max(ax, ay);
  if (mx == 0)
    return 0;
  const float a = std::min(ax, ay) / mx;
  const float s = a * a;
  float r = ((-0.0464964749f * s + 0.15931422f) * s - 0.327622764f) * s * a + a;
  if (ay > ax)
    r = 1.57079637f - r;
  if (x < 0)
    r = 3.14159274f - r;
  return y < 0 ? -r : r;
}

// Position along the track (0 = start at 11 o'clock, 1 = end at 1 o'clock;
// above 1: the top gap) of a pixel offset from the centre.
static float ring_pos(float dx, float dy) {
  float t = 240.0f - fast_atan2(dy, dx) * (180.0f / static_cast<float>(M_PI));
  if (t < 0)
    t += 360.0f;
  if (t >= 360.0f)
    t -= 360.0f;
  return t / 300.0f;
}

static uint16_t to565(uint32_t c) {
  return static_cast<uint16_t>((((c >> 16) & 0xF8) << 8) | (((c >> 8) & 0xFC) << 3) | ((c & 0xFF) >> 3));
}

// k/256 of b over a.
static uint16_t mix565(uint16_t a, uint16_t b, int k) {
  const int ra = a >> 11, ga = (a >> 5) & 0x3F, ba = a & 0x1F;
  const int r = ra + (((b >> 11) - ra) * k >> 8);
  const int g = ga + ((((b >> 5) & 0x3F) - ga) * k >> 8);
  const int bl = ba + (((b & 0x1F) - ba) * k >> 8);
  return static_cast<uint16_t>((r << 11) | (g << 5) | bl);
}

// A band of the track from p = 0 to p_end, with round ends.
struct RingBand {
  float r_in, r_out, p_end;
  float cap_x[2], cap_y[2];  // centres of the round ends
  RingBand(float r_in, float r_out, float p_end) : r_in(r_in), r_out(r_out), p_end(p_end) {
    const float mid = (r_in + r_out) / 2;
    const float ends[2] = {0.0f, p_end};
    for (int i = 0; i < 2; i++) {
      const float rad = (240.0f - 300.0f * ends[i]) * static_cast<float>(M_PI) / 180.0f;
      cap_x[i] = mid * cosf(rad);
      cap_y[i] = mid * sinf(rad);
    }
  }
  // Distance (px) of a pixel outside the band, 0 inside. Distances of at
  // least `limit` may be returned as any value of at least `limit`.
  float dist(float r, float p, float dx, float dy, float limit = 1e9f) const {
    const float radial = std::max(std::max(this->r_in - r, r - this->r_out), 0.0f);
    if (p <= this->p_end || radial >= limit)
      return radial;  // the round ends are never closer than the band's edges
    const float half = (this->r_out - this->r_in) / 2;
    float d = 1e9f;
    for (int i = 0; i < 2; i++)
      d = std::min(d, std::sqrt((dx - cap_x[i]) * (dx - cap_x[i]) + (dy - cap_y[i]) * (dy - cap_y[i])) - half);
    return std::max(d, 0.0f);
  }
  // Coverage (0..256) of a pixel at radius r, track position p.
  int cover(float r, float p, float dx, float dy) const {
    if (r < this->r_in - 0.5f || r > this->r_out + 0.5f)
      return 0;  // the round ends lie within the band's radii too
    float c;
    if (p <= this->p_end) {
      c = std::min(std::max(this->r_out - r + 0.5f, 0.0f), 1.0f) * std::min(std::max(r - this->r_in + 0.5f, 0.0f), 1.0f);
    } else {
      const float half = (this->r_out - this->r_in) / 2;
      c = 0;
      for (int i = 0; i < 2; i++) {
        const float d = std::sqrt((dx - cap_x[i]) * (dx - cap_x[i]) + (dy - cap_y[i]) * (dy - cap_y[i]));
        c = std::max(c, std::min(std::max(half + 0.5f - d, 0.0f), 1.0f));
      }
    }
    return static_cast<int>(c * 256.0f);
  }
};

// The ring: the background picture (or colour) again, so carousel content
// under it is hidden, with a narrow soft edge inwards; the shared track with
// its zones and the dimmed elapsed part; the selected child's inner track;
// and a glow in the child's colour around both tracks.
void KisSegitoUI::render_ring_tile_(int index, float r_min, float r_max) {
  TrackTile &t = g_track_tiles[index];
  const RingSpec &spec = this->ring_spec_;
  const RingBand outer(OUTER_R - OUTER_W, OUTER_R, 1.0f);
  const RingBand dim(OUTER_R - OUTER_W - 1, OUTER_R + 1, spec.elapsed);
  const RingBand inner(INNER_R - INNER_W, INNER_R, 1.0f);
  const lv_image_dsc_t *bg = spec.bg_image;
  const bool bg_ok = bg != nullptr && bg->header.w == SCREEN && bg->header.h == SCREEN &&
                     bg->header.cf == LV_COLOR_FORMAT_RGB565;
  constexpr float FADE_FROM = BAND_R - FADE_W;
  constexpr float ARC_IN = INNER_R - INNER_W - GLOW_W - 2, ARC_OUT = OUTER_R + GLOW_W + 2;
  const uint16_t bg_color = to565(spec.bg_color), dim_color = to565(TRACK_DIM), inner_color = to565(spec.inner_color);
  uint16_t zone565[RingSpec::MAX_ZONES];
  for (int z = 0; z < spec.zone_count; z++)
    zone565[z] = to565(spec.zone_colors[z]);
  auto glow = [](float d) {
    return d >= GLOW_W ? 0 : static_cast<int>(GLOW_MAX * (1 - smooth01(d * (1.0f / GLOW_W))));
  };
  lv_image_cache_drop(t.buf);
  auto *px = reinterpret_cast<uint16_t *>(t.buf->data);
  const uint32_t stride = TRACK_TILE;
  uint8_t *alpha = t.buf->data + TRACK_TILE * 2 * TRACK_TILE;
  bool opaque = true;
  for (int y = 0; y < TRACK_TILE; y++) {
    const int sy = t.y + y;
    const float dy = sy + 0.5f - CENTER;
    for (int x = 0; x < TRACK_TILE; x++) {
      const int sx = t.x + x;
      const float dx = sx + 0.5f - CENTER;
      const float r2 = dx * dx + dy * dy;
      const size_t i = y * stride + x;
      if (r2 < r_min * r_min || r2 > r_max * r_max) {
        opaque = opaque && alpha[i] == 255;  // kept as it is
        continue;
      }
      if (r2 < FADE_FROM * FADE_FROM || sx >= SCREEN || sy >= SCREEN) {
        alpha[i] = 0;
        opaque = false;
        continue;
      }
      uint16_t c = bg_ok ? reinterpret_cast<const uint16_t *>(bg->data)[sy * SCREEN + sx] : bg_color;
      int a = 255;
      if (r2 < BAND_R * BAND_R) {
        const float r = std::sqrt(r2);
        a = static_cast<int>(smooth01((r - FADE_FROM) / FADE_W) * 255.0f + 0.5f);
      }
      if (r2 >= ARC_IN * ARC_IN && r2 <= ARC_OUT * ARC_OUT) {
        const float r = std::sqrt(r2);
        const float p = ring_pos(dx, dy);
        const int co = outer.cover(r, p, dx, dy);
        // The glow (under the tracks), then the inner track, then the shared one.
        if (spec.has_inner) {
          const int g = std::max(glow(inner.dist(r, p, dx, dy, GLOW_W)),
                                 glow(std::max(0.0f, outer.dist(r, p, dx, dy, GLOW_W + 1.0f) - 1.0f)));
          if (g > 0) {
            c = mix565(c, inner_color, g);
            a = std::max(a, g);
          }
          const int ci = inner.cover(r, p, dx, dy);
          if (ci > 0) {
            c = mix565(c, inner_color, ci);
            a = std::max(a, std::min(255, ci));
          }
        }
        if (co > 0) {
          uint16_t zc = dim_color;  // no routine running: an empty track
          if (spec.has_routine) {
            zc = zone565[0];
            for (int z = 1; z < spec.zone_count; z++) {
              if (p >= spec.zone_from[z])
                zc = zone565[z];
            }
          }
          c = mix565(c, zc, co);
        }
        if (spec.has_routine && spec.elapsed > 0) {
          const int cd = dim.cover(r, p, dx, dy);
          if (cd > 0)
            c = mix565(c, dim_color, cd);
        }
      }
      px[i] = c;
      alpha[i] = static_cast<uint8_t>(a);
      opaque = opaque && a == 255;
    }
  }
  // A tile that is opaque everywhere is shown without alpha: copied instead of
  // blended, and LVGL does not draw what is under it.
  t.buf->header.cf = opaque ? LV_COLOR_FORMAT_RGB565 : LV_COLOR_FORMAT_RGB565A8;
  lv_image_header_cache_drop(t.buf);
  if (t.img != nullptr) {
    lv_image_set_src(t.img, t.buf);
    lv_obj_invalidate(t.img);
  }
}

bool KisSegitoUI::ring_ready_() {
  if (!g_track_tiles.empty())
    return g_track_tiles.front().img != nullptr;
  for (int cy = 0; cy < SCREEN; cy += TRACK_TILE) {
    for (int cx = 0; cx < SCREEN; cx += TRACK_TILE) {
      float dmax = 0;
      for (int x : {cx, cx + TRACK_TILE}) {
        for (int y : {cy, cy + TRACK_TILE})
          dmax = std::max(dmax, std::hypot(static_cast<float>(x - CENTER), static_cast<float>(y - CENTER)));
      }
      if (dmax > BAND_R - FADE_W)
        g_track_tiles.push_back({cx, cy, nullptr, nullptr});
    }
  }
  for (auto &t : g_track_tiles) {
    t.buf = lv_draw_buf_create(TRACK_TILE, TRACK_TILE, LV_COLOR_FORMAT_RGB565A8, TRACK_TILE * 2);
    if (t.buf == nullptr) {
      ESP_LOGE(TAG, "No memory for the track ring");
      return false;
    }
    memset(t.buf->data + TRACK_TILE * 2 * TRACK_TILE, 0, TRACK_TILE * TRACK_TILE);
  }
  for (auto &t : g_track_tiles) {
    t.img = lv_image_create(this->ring_layer_);
    lv_image_set_src(t.img, t.buf);
    lv_obj_set_pos(t.img, t.x, t.y);
  }
  return true;
}

// Computes the ring again, all at once, when anything on it changed: the
// background, the screen colour, the selected child, the routine or the
// elapsed time (to the minute).
void KisSegitoUI::update_ring_() {
  if (this->ring_layer_ == nullptr || !this->ring_ready_())
    return;
  RingSpec spec;
  spec.bg_image = static_cast<const lv_image_dsc_t *>(lv_obj_get_style_bg_image_src(this->root_, LV_PART_MAIN));
  spec.bg_key = spec.bg_image != nullptr ? this->shown_bg_ : std::string();
  // The colour only shows where there is no picture.
  spec.bg_color = spec.bg_image != nullptr ? 0 : lv_color_to_u32(lv_obj_get_style_bg_color(this->root_, LV_PART_MAIN)) & 0xFFFFFF;
  spec.has_inner = !this->children_.empty();
  if (spec.has_inner) {
    spec.inner_color =
        lv_color_to_u32(lv_color_mix(lv_color_hex(this->children_[this->child_].color), lv_color_hex(BASE_BG), 200)) &
        0xFFFFFF;
  }
  const Routine *r = this->shown_routine_;
  spec.has_routine = r != nullptr;
  if (r != nullptr) {
    spec.zone_from[0] = 0;
    spec.zone_colors[0] = r->base_color;
    spec.zone_count = 1;
    for (const auto &zone : r->zones) {
      if (spec.zone_count >= RingSpec::MAX_ZONES)
        break;
      spec.zone_from[spec.zone_count] = track_p(*r, r->end - zone.offset_s);
      spec.zone_colors[spec.zone_count] = zone.color;
      spec.zone_count++;
    }
    const int64_t now = this->now_();
    spec.elapsed = track_p(*r, now - now % 60);  // moves on once a minute
  }
  // The same background loaded again: only its address changed.
  this->ring_spec_.bg_image = spec.bg_image;
  if (this->ring_drawn_ && spec == this->ring_spec_)
    return;
  // Only the child or the elapsed time changed: just the band of the tracks
  // and their glow is computed again.
  const bool tracks_only = this->ring_drawn_ && spec.same_but_tracks(this->ring_spec_);
  const float r_min = tracks_only ? INNER_R - INNER_W - GLOW_W - 2 : 0.0f;
  const float r_max = tracks_only ? OUTER_R + GLOW_W + 2 : 1e6f;
  this->ring_drawn_ = true;
  this->ring_spec_ = spec;
  const uint32_t started = millis();
  for (size_t k = 0; k < g_track_tiles.size(); k++) {
    const TrackTile &t = g_track_tiles[k];
    // Tiles entirely inside or outside that band are left alone.
    float dmin = 1e9f, dmax = 0;
    for (int x : {t.x, t.x + TRACK_TILE}) {
      for (int y : {t.y, t.y + TRACK_TILE})
        dmax = std::max(dmax, std::hypot(static_cast<float>(x - CENTER), static_cast<float>(y - CENTER)));
    }
    const int nx = std::min(std::max(CENTER, t.x), t.x + TRACK_TILE);
    const int ny = std::min(std::max(CENTER, t.y), t.y + TRACK_TILE);
    dmin = std::hypot(static_cast<float>(nx - CENTER), static_cast<float>(ny - CENTER));
    if (dmax < r_min || dmin > r_max)
      continue;
    this->render_ring_tile_(static_cast<int>(k), r_min, r_max);
  }
  ESP_LOGD(TAG, "Track ring drawn in %u ms", (unsigned) (millis() - started));
}

void KisSegitoUI::build_track_() {
  lv_obj_clean(this->track_layer_);
  this->inner_layer_ = this->elapsed_arc_ = this->now_dot_ = this->top_gap_ = nullptr;
  this->shown_reward_ = -1;
  Routine *r = this->track_routine_();
  this->shown_routine_ = r;
  this->update_ring_();

  // The selected child's inner track, below the outer markers.
  this->inner_layer_ = lv_obj_create(this->track_layer_);
  remove_defaults(this->inner_layer_);
  lv_obj_set_size(this->inner_layer_, SCREEN, SCREEN);
  this->build_inner_track_();

  if (r != nullptr) {
    // Shared (global) checkpoints on the outer track; reached ones are grey.
    for (const auto &cp : r->checkpoints) {
      if (!cp.children.empty())
        continue;
      int x, y;
      this->ring_point_(track_p(*r, cp.t), OUTER_MID, &x, &y);
      std::string key = cp.icon + "_32";
      if (!this->has_image_(key))
        key = "checkpoint_flag_32";
      lv_obj_t *icon = this->image_(this->track_layer_, key, x, y);
      if (!this->children_.empty() && this->cp_done_(*r, cp.id)) {
        lv_obj_set_style_image_recolor(icon, lv_color_hex(0x8C96A5), 0);
        lv_obj_set_style_image_recolor_opa(icon, 200, 0);
      }
    }
    this->now_dot_ = this->disc_(this->track_layer_, 0, 0, 18, lv_color_white());
  }

  // Top gap: the brand mark, or the reward available now on a routine screen.
  this->top_gap_ = lv_obj_create(this->track_layer_);
  remove_defaults(this->top_gap_);
  lv_obj_set_size(this->top_gap_, 160, 56);
  lv_obj_set_pos(this->top_gap_, CENTER - 80, 4);
  this->update_track_();
}

void KisSegitoUI::build_inner_track_() {
  if (this->inner_layer_ == nullptr || this->children_.empty())
    return;
  lv_obj_clean(this->inner_layer_);
  const Child &child = this->children_[this->child_];
  const Routine *r = this->shown_routine_;
  if (r == nullptr)
    return;
  // This child's own checkpoints on the inner track.
  for (const auto &cp : r->checkpoints) {
    if (cp.children.empty() || !applies(cp.children, child.id))
      continue;
    int x, y;
    this->ring_point_(track_p(*r, cp.t), INNER_MID, &x, &y);
    std::string key = cp.icon + "_28";
    if (!this->has_image_(key))
      key = this->has_image_(cp.icon + "_32") ? cp.icon + "_32" : "checkpoint_flag_28";
    lv_obj_t *icon = this->image_(this->inner_layer_, key, x, y);
    if (this->cp_done_(*r, cp.id)) {
      lv_obj_set_style_image_recolor(icon, lv_color_hex(0x8C96A5), 0);
      lv_obj_set_style_image_recolor_opa(icon, 200, 0);
    }
  }
}

void KisSegitoUI::update_track_() {
  // New data waits for the running animation; the shown routine may be gone.
  if (this->track_layer_ == nullptr || this->pending_rebuild_)
    return;
  // The routine running now may have changed (one ended, another started).
  if (this->screen_ != Screen::ROUTINE && this->track_routine_() != this->shown_routine_ && !this->busy_) {
    this->build_track_();
    return;
  }
  const Routine *r = this->shown_routine_;
  if (r != nullptr && this->now_dot_ != nullptr) {
    const float p = std::max(0.001f, track_p(*r, this->now_()));
    // The dimmed elapsed part is drawn into the ring; it moves on once a
    // minute, while nobody is using the knob.
    if (!this->busy_ && millis() - this->last_input_ms_ > 3000 && this->input_.empty() &&
        lv_screen_active() == this->root_)
      this->update_ring_();
    int x, y;
    this->ring_point_(p, OUTER_MID, &x, &y);
    lv_obj_set_pos(this->now_dot_, x - 9, y - 9);
  }

  const int reward = this->screen_ == Screen::ROUTINE ? this->routine_reward_now_() : 0;
  if (reward != this->shown_reward_ && this->top_gap_ != nullptr) {
    this->shown_reward_ = reward;
    lv_obj_clean(this->top_gap_);
    if (reward > 0) {
      // The reward available now, as that many tokens.
      const int step = 18;
      const int x0 = 80 - (reward - 1) * step / 2;
      for (int i = 0; i < reward; i++)
        this->image_(this->top_gap_, "token_coin_front_28", x0 + i * step, 30);
    } else {
      this->image_(this->top_gap_, this->language_ == "hu" ? "brand_mark_48" : "brand_mark_en_48", 80, 28);
    }
  }
}

void KisSegitoUI::complete_task_() {
  Routine &r = this->current_routine_();
  const std::string child_id = this->children_[this->child_].id;
  int current = -1;
  for (size_t i = 0; i < r.tasks.size(); i++) {
    if (!this->is_done_(r, r.tasks[i].id)) {
      current = static_cast<int>(i);
      break;
    }
  }
  if (current < 0)
    return;
  const RoutineTask &task = r.tasks[current];
  // Shown at once; Home Assistant books it and sends the real state.
  r.done[child_id].push_back(task.id);
  this->send_action_("task", ",\"r\":\"" + r.id + "\",\"t\":\"" + task.id + "\"");

  // Was this the last task before its checkpoint? Then the checkpoint is
  // reached, worth its current time-band reward.
  int reward = 0;
  const Checkpoint *cp = nullptr;
  for (const auto &c : r.checkpoints) {
    if (c.id == task.checkpoint)
      cp = &c;
  }
  if (cp != nullptr && applies(cp->children, child_id) && !this->cp_done_(r, cp->id)) {
    bool all = true;
    for (const auto &t : r.tasks) {
      if (t.checkpoint == cp->id && !this->is_done_(r, t.id))
        all = false;
    }
    if (all) {
      reward = reward_for(cp->bands, cp->t - this->now_());
      r.cp_done[child_id].push_back(cp->id);
    }
  }
  this->busy_ = true;

  // Bounce, check, then rebuild with the next task.
  const uint32_t ms = this->anim_ms_(420);
  if (ms > 0) {
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, this->task_big_);
    lv_anim_set_values(&a, 256, 300);
    lv_anim_set_duration(&a, ms / 3);
    lv_anim_set_reverse_duration(&a, ms / 3);
    lv_anim_set_exec_cb(&a, [](void *var, int32_t v) { lv_image_set_scale(static_cast<lv_obj_t *>(var), v); });
    lv_anim_start(&a);
  }
  this->image_(this->screen_obj_, "action_check_88", CENTER, 205);
  lv_timer_t *t = lv_timer_create(
      [](lv_timer_t *timer) {
        auto *self = static_cast<KisSegitoUI *>(lv_timer_get_user_data(timer));
        lv_timer_delete(timer);
        self->busy_ = false;
        self->pending_rebuild_ = false;
        self->show_(Screen::ROUTINE);
      },
      ms + 250, this);
  lv_timer_set_repeat_count(t, 1);
  if (reward > 0)
    this->celebrate_(reward);
}

void KisSegitoUI::celebrate_(int tokens) {
  Child &c = this->children_[this->child_];
  c.wallet += tokens;
  ESP_LOGI(TAG, "Test reward: +%d tokens", tokens);
  if (this->anim_mode_ < 2)
    return;
  // Confetti on the top layer, so the screen rebuild does not remove it.
  static const uint32_t COLORS[] = {0xFF6B6B, 0xFFC94A, 0x6BCB77, 0x6CB8FF, 0xA78BFA, 0xFF8FB1};
  for (int i = 0; i < 36; i++) {
    const uint32_t h = hash32(i + 77);
    lv_obj_t *piece = lv_obj_create(lv_layer_top());
    remove_defaults(piece);
    lv_obj_set_size(piece, 8, 14);
    lv_obj_set_style_radius(piece, 2, 0);
    lv_obj_set_style_bg_color(piece, lv_color_hex(COLORS[i % 6]), 0);
    lv_obj_set_style_bg_opa(piece, LV_OPA_COVER, 0);
    lv_obj_set_pos(piece, 60 + static_cast<int>(h % 360), -20);
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, piece);
    lv_anim_set_values(&a, -20, 300 + static_cast<int>((h >> 8) % 180));
    lv_anim_set_delay(&a, (h >> 16) % 400);
    lv_anim_set_duration(&a, 1200);
    lv_anim_set_exec_cb(&a, [](void *var, int32_t v) { lv_obj_set_y(static_cast<lv_obj_t *>(var), v); });
    lv_anim_set_path_cb(&a, lv_anim_path_ease_in);
    lv_anim_set_completed_cb(&a, [](lv_anim_t *anim) { lv_obj_delete(static_cast<lv_obj_t *>(anim->var)); });
    lv_anim_start(&a);
  }
}

// ---------------------------------------------------------------- Screensaver

// Confetti and stars run on their own black screen (so nothing else is drawn
// under them), with a fixed set of small pictures created once, like the
// bouncing balls.
//
// Confetti: on every frame the pieces only move. Each piece falls on its own
// swaying path with its own speed and a sideways drift that changes direction
// now and then. Now and then a gust catches a few pieces near each other and
// blows them aside, each a little differently; pieces blown off the screen
// come back only when too few are left.
//
// Stars: they stand still. Each one appears at a random place, brightens and
// dims slowly like breathing, and vanishes, then appears elsewhere. Now and
// then a shooting star crosses from top right to bottom left on a curve.
static constexpr uint32_t CONFETTI_COLORS[] = {0xFF6B6B, 0xFFC94A, 0x6BCB77, 0x6CB8FF, 0xA78BFA, 0xFF8FB1};
static constexpr uint32_t STAR_COLORS[] = {0xFFE08A, 0xFFFFFF, 0xFFC94A, 0xBFE3FF, 0xFFD6F0, 0xFFF3B0};
static constexpr int STAR_SIZES[] = {8, 10, 12};  // never bigger than a confetti piece

static float frand(float lo, float hi) { return lo + (hi - lo) * static_cast<float>(random_uint32() % 10000) / 10000.0f; }

// A five-pointed star of the given size and colour (RGB565A8, anti-aliased).
static lv_draw_buf_t *make_star(int size, uint32_t color) {
  lv_draw_buf_t *buf = lv_draw_buf_create(size, size, LV_COLOR_FORMAT_RGB565A8, LV_STRIDE_AUTO);
  if (buf == nullptr)
    return nullptr;
  float vx[10], vy[10];
  const float c = size / 2.0f, outer = size / 2.0f, inner = outer * 0.45f;
  for (int i = 0; i < 10; i++) {
    const float a = -static_cast<float>(M_PI) / 2 + i * static_cast<float>(M_PI) / 5;
    const float rad = (i % 2 == 0) ? outer : inner;
    vx[i] = c + rad * cosf(a);
    vy[i] = c + rad * sinf(a);
  }
  auto inside = [&](float x, float y) {
    bool in = false;
    for (int i = 0, j = 9; i < 10; j = i++) {
      if ((vy[i] > y) != (vy[j] > y) && x < (vx[j] - vx[i]) * (y - vy[i]) / (vy[j] - vy[i]) + vx[i])
        in = !in;
    }
    return in;
  };
  const uint16_t rgb = static_cast<uint16_t>((((color >> 16) & 0xF8) << 8) | (((color >> 8) & 0xFC) << 3) |
                                             ((color & 0xFF) >> 3));
  auto *px = reinterpret_cast<uint16_t *>(buf->data);
  uint8_t *alpha = buf->data + buf->header.stride * size;
  for (int y = 0; y < size; y++) {
    for (int x = 0; x < size; x++) {
      int hits = 0;
      for (int sy = 0; sy < 4; sy++) {
        for (int sx = 0; sx < 4; sx++)
          hits += inside(x + (sx + 0.5f) / 4, y + (sy + 0.5f) / 4) ? 1 : 0;
      }
      px[y * (buf->header.stride / 2) + x] = rgb;
      alpha[y * (buf->header.stride / 2) + x] = static_cast<uint8_t>(hits * 255 / 16);
    }
  }
  return buf;
}

void KisSegitoUI::spawn_piece_(Piece &p, bool anywhere) {
  p.x = frand(10, SCREEN - 10 - p.w);
  p.y = anywhere ? frand(-40, SCREEN - 20) : frand(-60, -p.h - 2.0f);
  p.vy = frand(150, 215);
  p.drift = frand(-45, 45);
  p.drift_to = frand(-60, 60);
  p.drift_ms = millis() + 500 + random_uint32() % 2000;
  p.gust = p.gust_vy = 0;
  p.sway = frand(14, 40);
  p.sway_hz = frand(0.3f, 0.9f);
  p.phase = frand(0, 6.283f);
  p.on_screen = true;
  lv_obj_set_pos(p.obj, static_cast<int>(p.x), static_cast<int>(p.y));
}

// A confetti piece: a small rounded rectangle (RGB565A8, soft corners).
static lv_draw_buf_t *make_piece(int w, int h, uint32_t color) {
  lv_draw_buf_t *buf = lv_draw_buf_create(w, h, LV_COLOR_FORMAT_RGB565A8, LV_STRIDE_AUTO);
  if (buf == nullptr)
    return nullptr;
  auto *px = reinterpret_cast<uint16_t *>(buf->data);
  uint8_t *alpha = buf->data + buf->header.stride * h;
  const uint32_t stride = buf->header.stride / 2;
  for (int y = 0; y < h; y++) {
    for (int x = 0; x < w; x++) {
      const bool corner = (x == 0 || x == w - 1) && (y == 0 || y == h - 1);
      px[y * stride + x] = to565(color);
      alpha[y * stride + x] = corner ? 90 : 255;
    }
  }
  return buf;
}

void KisSegitoUI::start_confetti() {
  if (this->saver_screen_ != nullptr)
    return;
  const bool stars = this->saver_type_ == "stars";
  this->stars_ = stars;
  this->saver_screen_ = lv_obj_create(nullptr);
  remove_defaults(this->saver_screen_);
  lv_obj_set_style_bg_color(this->saver_screen_, lv_color_black(), 0);
  lv_obj_set_style_bg_opa(this->saver_screen_, LV_OPA_COVER, 0);
  if (stars) {
    for (auto &st : this->stars_list_) {
      st.obj = lv_image_create(this->saver_screen_);
      this->spawn_star_(st, true);
    }
    // The shooting star: a head and a fading tail of smaller stars.
    for (int k = 0; k < SHOOT_PARTS; k++) {
      this->shoot_[k] = lv_image_create(this->saver_screen_);
      lv_image_set_src(this->shoot_[k], star_image(1, k == 0 ? 2 : (k < 3 ? 1 : 0)));
      lv_obj_set_style_image_opa(this->shoot_[k], static_cast<lv_opa_t>(255 - k * 40), 0);
      lv_obj_set_pos(this->shoot_[k], -40, -40);  // off the screen until it flies
    }
    this->shoot_start_ms_ = 0;
    this->next_shoot_ms_ = millis() + 4000 + random_uint32() % 8000;
  } else {
    static lv_draw_buf_t *pieces[6][2][3] = {};
    for (int i = 0; i < CONFETTI; i++) {
      Piece &p = this->confetti_[i];
      const int c = i % 6, wide = random_uint32() & 1, sz = random_uint32() % 3;
      const float k = 0.85f + 0.15f * sz;  // size within about +/-15-20 %
      p.w = static_cast<int>(std::lround((wide ? 12 : 7) * k));
      p.h = static_cast<int>(std::lround((wide ? 7 : 12) * k));
      if (pieces[c][wide][sz] == nullptr)
        pieces[c][wide][sz] = make_piece(p.w, p.h, CONFETTI_COLORS[c]);
      p.obj = lv_image_create(this->saver_screen_);
      if (pieces[c][wide][sz] != nullptr)
        lv_image_set_src(p.obj, pieces[c][wide][sz]);
      this->spawn_piece_(p, true);  // already spread over the screen
    }
    this->next_gust_ms_ = millis() + 2500 + random_uint32() % 4000;
  }
  lv_screen_load(this->saver_screen_);
  this->confetti_ms_ = millis();
  this->confetti_timer_ = lv_timer_create(
      // About 33 frames a second, like the bouncing balls; a frame redraws only
      // the small areas that changed.
      [](lv_timer_t *t) {
        auto *self = static_cast<KisSegitoUI *>(lv_timer_get_user_data(t));
        if (self->stars_)
          self->stars_step_();
        else
          self->confetti_step_();
      },
      30, this);
}

// A star picture: colour index, size index (cached).
lv_draw_buf_t *KisSegitoUI::star_image(int color, int size) {
  static lv_draw_buf_t *cache[6][3] = {};
  if (cache[color][size] == nullptr)
    cache[color][size] = make_star(STAR_SIZES[size], STAR_COLORS[color]);
  return cache[color][size];
}

void KisSegitoUI::spawn_star_(Star &st, bool first) {
  const int sz = static_cast<int>(random_uint32() % 3);
  lv_draw_buf_t *img = star_image(static_cast<int>(random_uint32() % 6), sz);
  if (img != nullptr)
    lv_image_set_src(st.obj, img);
  // Anywhere inside the round screen.
  const float a = frand(0, 6.283f), rad = 205.0f * std::sqrt(frand(0, 1));
  lv_obj_set_pos(st.obj, static_cast<int>(CENTER + rad * cosf(a)) - STAR_SIZES[sz] / 2,
                 static_cast<int>(CENTER + rad * sinf(a)) - STAR_SIZES[sz] / 2);
  st.fade_in = frand(1.5f, 3.0f);
  st.hold = frand(0.3f, 1.5f);
  st.fade_out = frand(1.5f, 3.0f);
  st.gap = frand(0.3f, 2.5f);
  st.peak = static_cast<uint8_t>(frand(170, 255));
  st.t = first ? frand(0, st.fade_in + st.hold + st.fade_out + st.gap) : 0.0f;
  st.opa = 0;
  lv_obj_set_style_image_opa(st.obj, 0, 0);
}

void KisSegitoUI::stars_step_() {
  const uint32_t now = millis();
  const float dt = std::min(static_cast<float>(now - this->confetti_ms_), 70.0f) / 1000.0f;
  this->confetti_ms_ = now;
  for (auto &st : this->stars_list_) {
    st.t += dt;
    float k;
    if (st.t < st.fade_in) {
      k = smooth01(st.t / st.fade_in);
    } else if (st.t < st.fade_in + st.hold) {
      k = 1;
    } else if (st.t < st.fade_in + st.hold + st.fade_out) {
      k = 1 - smooth01((st.t - st.fade_in - st.hold) / st.fade_out);
    } else if (st.t < st.fade_in + st.hold + st.fade_out + st.gap) {
      k = 0;
    } else {
      this->spawn_star_(st, false);  // invisible now: appears elsewhere next
      continue;
    }
    const auto opa = static_cast<uint8_t>(st.peak * k);
    if (std::abs(opa - st.opa) >= 3 || (opa == 0) != (st.opa == 0)) {
      st.opa = opa;
      lv_obj_set_style_image_opa(st.obj, opa, 0);
    }
  }
  // The shooting star: from top right to bottom left along a curve, its start
  // 50-80 px higher or lower each time.
  if (this->shoot_start_ms_ == 0 && static_cast<int32_t>(now - this->next_shoot_ms_) >= 0) {
    this->shoot_start_ms_ = now;
    this->shoot_ms_ = 1300 + random_uint32() % 600;
    const float off = ((random_uint32() & 1) ? 1.0f : -1.0f) * frand(50, 80);
    this->shoot_p_[0] = 400;
    this->shoot_p_[1] = 110 + off;
    this->shoot_p_[4] = 80;
    this->shoot_p_[5] = 370 + off * 0.5f;
    // An arc bending up and left: the star starts almost level, high, and
    // curves down to the left; the control point is at the start's height,
    // so it never climbs.
    this->shoot_p_[2] = this->shoot_p_[4] + (this->shoot_p_[0] - this->shoot_p_[4]) * frand(0.35f, 0.5f);
    this->shoot_p_[3] = this->shoot_p_[1];
  }
  if (this->shoot_start_ms_ != 0) {
    const float t = static_cast<float>(now - this->shoot_start_ms_) / this->shoot_ms_;
    for (int k = 0; k < SHOOT_PARTS; k++) {
      const float u = t - k * 0.035f;  // the tail follows the head
      if (u < 0 || u > 1) {
        lv_obj_set_pos(this->shoot_[k], -40, -40);
        continue;
      }
      const float a = (1 - u) * (1 - u), b = 2 * (1 - u) * u, c = u * u;
      const float x = a * this->shoot_p_[0] + b * this->shoot_p_[2] + c * this->shoot_p_[4];
      const float y = a * this->shoot_p_[1] + b * this->shoot_p_[3] + c * this->shoot_p_[5];
      lv_obj_set_pos(this->shoot_[k], static_cast<int>(x) - 6, static_cast<int>(y) - 6);
    }
    if (t > 1 + SHOOT_PARTS * 0.035f) {
      this->shoot_start_ms_ = 0;
      this->next_shoot_ms_ = now + 8000 + random_uint32() % 12000;
    }
  }
}

void KisSegitoUI::confetti_step_() {
  const uint32_t now = millis();
  // Real elapsed time, so a late frame does not slow the fall down.
  const float dt = std::min(static_cast<float>(now - this->confetti_ms_), 70.0f) / 1000.0f;
  this->confetti_ms_ = now;
  if (static_cast<int32_t>(now - this->next_gust_ms_) >= 0) {
    // A gust: 5-7 pieces closest to a random point, in a random direction.
    this->next_gust_ms_ = now + 3500 + random_uint32() % 6000;
    const float gx = frand(60, SCREEN - 60), gy = frand(40, SCREEN - 160);
    const float dir = (random_uint32() & 1) ? 1.0f : -1.0f;
    const float lift = frand(-90, 30);  // a little up or down, different each gust
    std::vector<std::pair<float, int>> near;
    for (int i = 0; i < CONFETTI; i++) {
      const Piece &p = this->confetti_[i];
      if (p.on_screen && p.y > 0)
        near.emplace_back((p.x - gx) * (p.x - gx) + (p.y - gy) * (p.y - gy), i);
    }
    std::sort(near.begin(), near.end());
    const size_t n = std::min<size_t>(near.size(), 5 + random_uint32() % 3);
    for (size_t j = 0; j < n; j++) {
      Piece &p = this->confetti_[near[j].second];
      p.gust = dir * frand(200, 560);  // each one blown a little differently
      p.gust_vy = lift * frand(0.4f, 1.6f);
    }
  }
  int on_screen = 0;
  for (const auto &p : this->confetti_)
    on_screen += p.on_screen ? 1 : 0;
  // A gust fades out over about a second (air drag).
  const float drag = std::max(0.0f, 1.0f - 1.5f * dt);
  for (auto &p : this->confetti_) {
    if (!p.on_screen) {
      if (on_screen < CONFETTI_MIN) {
        this->spawn_piece_(p, false);
        on_screen++;
      }
      continue;
    }
    if (static_cast<int32_t>(now - p.drift_ms) >= 0) {
      p.drift_to = frand(-60, 60);  // the air around it turns
      p.drift_ms = now + 700 + random_uint32() % 2200;
    }
    p.drift += (p.drift_to - p.drift) * std::min(1.0f, 1.2f * dt);
    p.phase += 6.283f * p.sway_hz * dt;
    p.gust *= drag;
    p.gust_vy *= drag;
    p.x += (p.drift + p.gust + p.sway * 6.283f * p.sway_hz * cosf(p.phase)) * dt;
    p.y += std::max(20.0f, p.vy + p.gust_vy) * dt;
    if (p.x < -p.w - 4 || p.x > SCREEN + 4) {
      p.on_screen = false;  // blown off the screen; it stays there for now
      continue;
    }
    if (p.y > SCREEN + 4) {
      this->spawn_piece_(p, false);  // fell out at the bottom: again from the top
      continue;
    }
    // Old and new place as one area, so the piece is redrawn in one go and
    // never shows missing for a moment.
    const int nx = static_cast<int>(p.x), ny = static_cast<int>(p.y);
    const int ox = lv_obj_get_x(p.obj), oy = lv_obj_get_y(p.obj);
    lv_area_t area{std::min(ox, nx), std::min(oy, ny), std::max(ox, nx) + p.w, std::max(oy, ny) + p.h};
    lv_obj_invalidate_area(this->saver_screen_, &area);
    lv_obj_set_pos(p.obj, nx, ny);
  }
}

void KisSegitoUI::stop_confetti() {
  if (this->confetti_timer_ != nullptr) {
    lv_timer_delete(this->confetti_timer_);
    this->confetti_timer_ = nullptr;
  }
  if (this->saver_screen_ != nullptr) {
    if (lv_screen_active() == this->saver_screen_ && this->root_ != nullptr)
      lv_screen_load(this->root_);
    lv_obj_delete(this->saver_screen_);  // deletes the pieces too
    this->saver_screen_ = nullptr;
  }
}

}  // namespace esphome::kis_segito_ui
