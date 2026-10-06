// SPDX-License-Identifier: AGPL-3.0-only

#include "kis_segito_ui.h"

#include <algorithm>
#include <cmath>

#include "esphome/core/hal.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

namespace esphome::kis_segito_ui {

static const char *const TAG = "kis_segito_ui";

static constexpr int SCREEN = 480;
static constexpr int CENTER = SCREEN / 2;
static constexpr uint32_t BASE_BG = 0x1B2140;  // deep navy
static constexpr uint32_t TRACK_DIM = 0x3A4066;
static constexpr uint32_t ZONE_OK = 0x6BCB77;
static constexpr uint32_t ZONE_WARN = 0xFF9F43;
static constexpr uint32_t ZONE_LATE = 0xFF6B6B;
static constexpr uint32_t INACTIVITY_MS = 60000;

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
                      FillFn fill, uint32_t anim_ms) {
  this->count_ = std::max(count, 1);
  this->selected_ = this->wrap_(selected);
  this->slot_w_ = slot_w;
  this->y_ = y;
  this->spacing_ = spacing;
  this->fill_ = std::move(fill);
  this->anim_ms_ = anim_ms;
  for (int i = 0; i < 4; i++) {
    lv_obj_t *slot = lv_obj_create(parent);
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

void Carousel::refill() {
  const int offsets[4] = {-1, 0, 1, 2};
  for (int i = 0; i < 4; i++) {
    lv_anim_delete(this->slots_[i], nullptr);
    this->offset_[i] = offsets[i];
    this->index_[i] = this->wrap_(this->selected_ + offsets[i]);
    lv_obj_clean(this->slots_[i]);
    if (this->count_ > 1 || offsets[i] == 0)
      this->fill_(this->slots_[i], this->index_[i]);
    this->place_(i, offsets[i], false);
  }
}

static void slot_x_cb(void *var, int32_t centre_x) {
  auto *slot = static_cast<lv_obj_t *>(var);
  const int half = static_cast<int>(reinterpret_cast<intptr_t>(lv_obj_get_user_data(slot))) / 2;
  lv_obj_set_x(slot, centre_x - half);
  const int dist = std::abs(centre_x - CENTER);
  const int opa = 255 - std::min(dist, 240) * 150 / 240;  // sides fade to ~105
  lv_obj_set_style_opa(slot, static_cast<lv_opa_t>(std::max(opa, 0)), 0);
}

void Carousel::place_(int slot, int offset, bool animate) {
  lv_obj_t *obj = this->slots_[slot];
  const int target = CENTER + offset * this->spacing_;
  lv_obj_set_y(obj, this->y_);
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
  const int from = lv_obj_get_x(obj) + half;
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

void Carousel::rotate(int dir) {
  if (this->count_ <= 1 || dir == 0)
    return;
  dir = dir > 0 ? 1 : -1;
  // Finish a running animation immediately so input never waits.
  for (int i = 0; i < 4; i++) {
    lv_anim_delete(this->slots_[i], nullptr);
    this->place_(i, this->offset_[i], false);
  }
  // The spare slot (|offset| == 2, or the one not shown) becomes the incoming item.
  int spare = 0;
  for (int i = 0; i < 4; i++) {
    if (std::abs(this->offset_[i]) > 1) {
      spare = i;
      break;
    }
  }
  this->offset_[spare] = 2 * dir;
  this->index_[spare] = this->wrap_(this->selected_ + 2 * dir);
  lv_obj_clean(this->slots_[spare]);
  this->fill_(this->slots_[spare], this->index_[spare]);
  this->place_(spare, this->offset_[spare], false);
  lv_obj_remove_flag(this->slots_[spare], LV_OBJ_FLAG_HIDDEN);

  this->selected_ = this->wrap_(this->selected_ + dir);
  for (int i = 0; i < 4; i++) {
    this->offset_[i] -= dir;
    this->place_(i, this->offset_[i], true);
  }
}

// ---------------------------------------------------------------- Setup / test data

void KisSegitoUI::setup() {
  // Built-in test data, shown until Home Assistant sends real data.
  this->children_ = {
      {"test_avatar_1", 0x6CB8FF, 7, 12, true, 5, 7},
      {"test_avatar_2", 0xFF8FB1, 24, 3, true, 2, 7},
      {"test_avatar_3", 0x6BCB77, 260, 0, false, 6, 7},
  };
  this->rewards_ = {
      {"reward_toy_car", 8}, {"reward_doll", 12}, {"reward_bricks", 20}, {"reward_long_story", 5}, {"reward_treat", 3},
  };
  const std::vector<RoutineTask> tasks = {
      {"task_clothes", false},
      {"task_breakfast", false},
      {"task_toothbrush", false},
      {"task_shoes", false},
      {"task_bag", false},
  };
  this->routines_ = {
      {"routine_morning", 40 * 60, 0, tasks},
      {"routine_evening", 30 * 60, 0, tasks},
  };
  // The last selected child is kept across reboots.
  this->child_pref_ = global_preferences->make_preference<int32_t>(fnv1_hash("kis_segito_ui_child"));
  int32_t saved = 0;
  if (this->child_pref_.load(&saved) && saved >= 0 && saved < static_cast<int32_t>(this->children_.size()))
    this->child_ = saved;
}

void KisSegitoUI::select_child_(int index) {
  if (index == this->child_)
    return;
  this->child_ = index;
  int32_t value = index;
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
  const uint32_t now_s = millis() / 1000;
  // Test routines: the morning one started 12 minutes ago, the evening one 5.
  this->routines_[0].started_s = now_s > 720 ? now_s - 720 : 0;
  this->routines_[1].started_s = now_s > 300 ? now_s - 300 : 0;

  this->screen_obj_ = lv_obj_create(nullptr);
  remove_defaults(this->screen_obj_);
  lv_obj_set_style_bg_color(this->screen_obj_, lv_color_hex(BASE_BG), 0);
  lv_obj_set_style_bg_opa(this->screen_obj_, LV_OPA_COVER, 0);
  lv_screen_load(this->screen_obj_);

  this->offline_icon_ = lv_image_create(lv_layer_top());
  lv_image_set_src(this->offline_icon_, this->img_("status_disconnected_28"));
  lv_obj_align(this->offline_icon_, LV_ALIGN_BOTTOM_MID, 0, -8);
  lv_obj_add_flag(this->offline_icon_, LV_OBJ_FLAG_HIDDEN);

  this->last_input_ms_ = millis();
  this->tick_timer_ = lv_timer_create(
      [](lv_timer_t *t) {
        auto *self = static_cast<KisSegitoUI *>(lv_timer_get_user_data(t));
        if (self->screen_ == Screen::ROUTINE)
          self->update_routine_();
        if (self->screen_ != Screen::CHILDREN && !self->busy_ && millis() - self->last_input_ms_ > INACTIVITY_MS)
          self->show_(Screen::CHILDREN);
      },
      1000, this);

  this->show_(Screen::CHILDREN);
  ESP_LOGI(TAG, "UI started with test data (%u children)", (unsigned) this->children_.size());
}

// ---------------------------------------------------------------- Helpers

const lv_image_dsc_t *KisSegitoUI::img_(const std::string &key) {
  auto it = this->images_.find(key);
  if (it == this->images_.end()) {
    ESP_LOGW(TAG, "Missing image %s", key.c_str());
    return nullptr;
  }
  return it->second->get_lv_image_dsc();
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

// A physical-looking heap of exactly `count` coins. It grows upwards as a
// pyramid up to max_rows, then spreads sideways up to max_width coins, then
// "flows" downwards below base_y (off the screen if needed). Coins below the
// screen are counted but not created.
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

  // Create back to front: top pyramid rows first, then the base, then the spill.
  std::vector<size_t> order;
  for (size_t i = 0; i < rows.size(); i++)
    order.push_back(i);
  std::sort(order.begin(), order.end(), [&rows](size_t a, size_t b) { return rows[a].y < rows[b].y; });

  int created = 0;
  for (size_t idx : order) {
    const Row &row = rows[idx];
    if (row.y - 14 > SCREEN + 16)
      continue;  // below the screen: counted, not drawn
    for (int i = 0; i < row.n && created < 320; i++) {
      const uint32_t h = hash32(seed * 7919u + idx * 131u + i);
      const int jx = static_cast<int>(h % 7) - 3;
      const int jy = static_cast<int>((h >> 8) % 5) - 2;
      const int x = cx + static_cast<int>((i - (row.n - 1) / 2.0f) * dx) + jx;
      lv_obj_t *coin = lv_image_create(parent);
      const lv_image_dsc_t *dsc = dscs[(h >> 16) % 3];
      if (dsc == nullptr)
        continue;
      lv_image_set_src(coin, dsc);
      lv_obj_set_pos(coin, x - 14, row.y + jy - 14);
      created++;
    }
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

std::vector<Function> KisSegitoUI::functions_for_(const Child &child) const {
  std::vector<Function> fns = {Function::ROUTINE_MORNING, Function::ROUTINE_EVENING, Function::REWARDS};
  if (child.piggy_unlocked)
    fns.push_back(Function::PIGGY);
  fns.push_back(Function::TOKENS);
  return fns;
}

// ---------------------------------------------------------------- Navigation

void KisSegitoUI::show_(Screen screen) {
  if (this->screen_obj_ == nullptr)
    return;
  // Deleting the screen's objects also deletes their animations.
  this->busy_ = false;
  lv_obj_clean(this->screen_obj_);
  this->elapsed_arc_ = this->now_dot_ = this->top_gap_ = this->task_big_ = this->timeline_ = nullptr;
  this->confirm_ring_ = this->confirm_no_ = this->confirm_yes_obj_ = nullptr;
  this->shown_reward_ = -1;
  this->screen_ = screen;
  const Child &child = this->children_[this->child_];
  const lv_color_t bg = screen == Screen::CHILDREN ? lv_color_hex(BASE_BG) : this->tint_(child.color, 46);
  lv_obj_set_style_bg_color(this->screen_obj_, bg, 0);
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
  if (!this->started_)
    return;
  this->last_input_ms_ = millis();
  if (this->busy_)
    return;
  switch (this->screen_) {
    case Screen::CHILDREN:
      this->carousel_.rotate(dir);
      this->select_child_(this->carousel_.selected());
      break;
    case Screen::FUNCTIONS:
      this->carousel_.rotate(dir);
      this->function_ = this->carousel_.selected();
      break;
    case Screen::REWARDS:
      this->carousel_.rotate(dir);
      this->reward_ = this->carousel_.selected();
      break;
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

void KisSegitoUI::click() {
  if (!this->started_)
    return;
  this->last_input_ms_ = millis();
  if (this->busy_)
    return;
  const Child &child = this->children_[this->child_];
  switch (this->screen_) {
    case Screen::CHILDREN:
      this->function_ = 0;
      this->show_(Screen::FUNCTIONS);
      break;
    case Screen::FUNCTIONS: {
      const auto fns = this->functions_for_(child);
      switch (fns[this->function_ % fns.size()]) {
        case Function::ROUTINE_MORNING:
          this->routine_ = 0;
          this->show_(Screen::ROUTINE);
          break;
        case Function::ROUTINE_EVENING:
          this->routine_ = 1;
          this->show_(Screen::ROUTINE);
          break;
        case Function::REWARDS:
          this->show_(Screen::REWARDS);
          break;
        case Function::PIGGY:
          this->show_(Screen::PIGGY);
          break;
        case Function::TOKENS:
          this->show_(Screen::TOKENS);
          break;
      }
      break;
    }
    case Screen::REWARDS: {
      const Reward &r = this->rewards_[this->reward_];
      if (r.cost > child.wallet) {
        // Locked: a short shake instead of opening the confirmation.
        lv_obj_t *target = this->carousel_.center_slot();
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
      Child &c = this->children_[this->child_];
      const Reward &r = this->rewards_[this->reward_];
      c.wallet -= r.cost;
      // The exact number of spent tokens fly from the wallet to the reward.
      this->busy_ = true;
      const int flying = std::min(r.cost, 40);
      for (int i = 0; i < flying; i++) {
        lv_obj_t *coin = this->image_(this->screen_obj_, "token_coin_front_28", CENTER, 452);
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, coin);
        lv_anim_set_values(&a, lv_obj_get_y(coin), 170 + static_cast<int>(hash32(i) % 30));
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
            self->show_(Screen::REWARDS);
          },
          this->anim_ms_(450) + flying * 45 + 300, this);
      lv_timer_set_repeat_count(done, 1);
      ESP_LOGI(TAG, "Test redemption: reward %d for %d tokens", this->reward_, r.cost);
      break;
    }
    case Screen::ROUTINE:
      if (!this->connected_) {
        this->refuse_offline_(this->task_big_);
        return;
      }
      this->complete_task_();
      break;
    default:
      break;
  }
}

void KisSegitoUI::long_press() {
  if (!this->started_)
    return;
  this->last_input_ms_ = millis();
  switch (this->screen_) {
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

// ---------------------------------------------------------------- Screens

void KisSegitoUI::build_children_() {
  this->carousel_.create(
      this->screen_obj_, static_cast<int>(this->children_.size()), this->child_, 300, SCREEN, 0, 250,
      [this](lv_obj_t *slot, int index) {
        const Child &c = this->children_[index];
        const int cx = 150;  // slot centre
        this->disc_(slot, cx, 175, 196, lv_color_hex(c.color));
        this->image_(slot, c.avatar + "_180", cx, 175);
        this->pile_(slot, cx, 392, c.wallet, static_cast<uint32_t>(index) + 1, 12, 15, 19, 10);
        this->number_pill_(slot, cx, 440, c.wallet, true);
      },
      this->anim_ms_(260));
}

void KisSegitoUI::build_functions_() {
  const Child &child = this->children_[this->child_];
  const auto fns = this->functions_for_(child);
  this->function_ %= static_cast<int>(fns.size());
  this->carousel_.create(
      this->screen_obj_, static_cast<int>(fns.size()), this->function_, 240, 240, 140, 230,
      [this, fns](lv_obj_t *slot, int index) {
        const Child &c = this->children_[this->child_];
        this->disc_(slot, 120, 120, 210, lv_color_mix(lv_color_hex(c.color), lv_color_white(), 90));
        static const char *const ICONS[] = {"routine_morning_160", "routine_evening_160", "fn_rewards_160",
                                            "fn_piggy_160", "fn_tokens_160"};
        this->image_(slot, ICONS[static_cast<int>(fns[index])], 120, 120);
      },
      this->anim_ms_(240));
  // Small child marker at the top centre: context only, not the focus.
  this->disc_(this->screen_obj_, CENTER, 62, 76, lv_color_hex(child.color));
  lv_obj_t *avatar = this->image_(this->screen_obj_, child.avatar + "_180", CENTER, 62);
  lv_image_set_scale(avatar, 92);  // 180 px -> ~65 px
}

void KisSegitoUI::build_rewards_() {
  const Child &child = this->children_[this->child_];
  this->carousel_.create(
      this->screen_obj_, static_cast<int>(this->rewards_.size()), this->reward_, 260, 340, 80, 240,
      [this](lv_obj_t *slot, int index) {
        const Reward &r = this->rewards_[index];
        const Child &c = this->children_[this->child_];
        const bool locked = r.cost > c.wallet;
        lv_obj_t *disc = this->disc_(slot, 130, 120, 200,
                                     locked ? lv_color_hex(0x4A4F6A)
                                            : lv_color_mix(lv_color_hex(c.color), lv_color_white(), 80));
        (void) disc;
        lv_obj_t *icon = this->image_(slot, r.icon + "_160", 130, 120);
        if (locked) {
          lv_obj_set_style_image_recolor(icon, lv_color_hex(0x8C96A5), 0);
          lv_obj_set_style_image_recolor_opa(icon, 150, 0);
          this->image_(slot, "status_lock_64", 205, 190);
        }
        // The price as a small pile of exactly that many tokens.
        this->pile_(slot, 130, 290, r.cost, 1000u + index, 4, 9, 16, 9);
        this->number_pill_(slot, 130, 320, r.cost, false);
      },
      this->anim_ms_(240));
  // Current wallet in the top gap.
  this->number_pill_(this->screen_obj_, CENTER, 44, child.wallet, true);
}

void KisSegitoUI::build_confirm_() {
  const Reward &r = this->rewards_[this->reward_];
  const Child &child = this->children_[this->child_];
  this->disc_(this->screen_obj_, CENTER, 175, 190, lv_color_mix(lv_color_hex(child.color), lv_color_white(), 80));
  this->image_(this->screen_obj_, r.icon + "_160", CENTER, 175);
  this->number_pill_(this->screen_obj_, CENTER, 300, r.cost, true);
  this->confirm_no_ = this->image_(this->screen_obj_, "action_x_88", 150, 380);
  this->confirm_yes_obj_ = this->image_(this->screen_obj_, "action_check_88", 330, 380);
  // The selected choice is circled (not only coloured).
  this->confirm_ring_ = lv_obj_create(this->screen_obj_);
  remove_defaults(this->confirm_ring_);
  lv_obj_set_size(this->confirm_ring_, 116, 116);
  lv_obj_set_style_radius(this->confirm_ring_, LV_RADIUS_CIRCLE, 0);
  lv_obj_set_style_border_width(this->confirm_ring_, 6, 0);
  lv_obj_set_style_border_color(this->confirm_ring_, lv_color_white(), 0);
  lv_obj_set_style_border_opa(this->confirm_ring_, LV_OPA_COVER, 0);
  lv_obj_set_pos(this->confirm_ring_, 150 - 58, 380 - 58);
  lv_obj_set_style_image_opa(this->confirm_yes_obj_, 140, 0);
  this->number_pill_(this->screen_obj_, CENTER, 44, child.wallet, true);
}

void KisSegitoUI::build_tokens_() {
  const Child &child = this->children_[this->child_];
  this->pile_(this->screen_obj_, CENTER, 300, child.wallet, 500u + this->child_, 11, 20, 19, 10);
  this->number_pill_(this->screen_obj_, CENTER, 345, child.wallet, true);
  // Streak: flame + one marker per day of the target.
  this->image_(this->screen_obj_, "streak_flame_64", CENTER, 60);
  const int n = std::max(child.streak_target, 1);
  const int step = 34;
  const int x0 = CENTER - (n - 1) * step / 2;
  for (int i = 0; i < n; i++) {
    const int x = x0 + i * step;
    if (i < child.streak) {
      this->image_(this->screen_obj_, "action_check_small_24", x, 410);
    } else {
      lv_obj_t *dot = this->disc_(this->screen_obj_, x, 410, 22, lv_color_hex(BASE_BG));
      lv_obj_set_style_border_width(dot, 3, 0);
      lv_obj_set_style_border_color(dot, lv_color_hex(0x8C96A5), 0);
    }
  }
}

void KisSegitoUI::build_piggy_() {
  const Child &child = this->children_[this->child_];
  this->image_(this->screen_obj_, "piggy_large_180", CENTER, 185);
  this->pile_(this->screen_obj_, CENTER, 300, child.piggy, 900u + this->child_, 5, 14, 19, 10);
  this->number_pill_(this->screen_obj_, CENTER, 340, child.piggy, true);
  // The wallet is a separate thing: shown small at the bottom.
  this->number_pill_(this->screen_obj_, CENTER, 420, child.wallet, true);
}

// ---------------------------------------------------------------- Routine

Routine &KisSegitoUI::current_routine_() { return this->routines_[this->routine_ % this->routines_.size()]; }

int KisSegitoUI::routine_reward_now_() const {
  const Routine &r = this->routines_[this->routine_ % this->routines_.size()];
  const uint32_t now_s = millis() / 1000;
  const int remaining = static_cast<int>(r.started_s + r.total_s) - static_cast<int>(now_s);
  if (remaining > 15 * 60)
    return 3;
  if (remaining > 5 * 60)
    return 2;
  if (remaining > 0)
    return 1;
  return 0;
}

void KisSegitoUI::build_routine_() {
  Routine &r = this->current_routine_();
  const Child &child = this->children_[this->child_];
  const float total = static_cast<float>(r.total_s);
  // Future colour structure, visible from the start: OK, then warning from
  // T-15 min, then late from T-5 min.
  const float warn = std::max(0.0f, 1.0f - 15 * 60 / total);
  const float late = std::max(0.0f, 1.0f - 5 * 60 / total);
  const int outer = 222;
  this->track_arc_(this->screen_obj_, outer, 14, 0.0f, warn, lv_color_hex(ZONE_OK));
  this->track_arc_(this->screen_obj_, outer, 14, warn, late, lv_color_hex(ZONE_WARN));
  this->track_arc_(this->screen_obj_, outer, 14, late, 1.0f, lv_color_hex(ZONE_LATE));
  // Inner, child-specific track, slightly inside the outer one.
  this->track_arc_(this->screen_obj_, outer - 20, 6, 0.0f, 1.0f, this->tint_(child.color, 140));
  // Elapsed time is dimmed; it is redrawn every second.
  this->elapsed_arc_ = this->track_arc_(this->screen_obj_, outer, 16, 0.0f, 0.001f, lv_color_hex(TRACK_DIM));
  this->now_dot_ = this->disc_(this->screen_obj_, 0, 0, 18, lv_color_white());

  // Checkpoints: global ones on the outer track, a child one on the inner track.
  int x, y;
  this->ring_point_(0.5f, outer, &x, &y);
  this->image_(this->screen_obj_, "task_breakfast_32", x, y);
  this->ring_point_(1.0f, outer, &x, &y);
  this->image_(this->screen_obj_, "task_door_ready_32", x, y);
  this->ring_point_(0.8f, outer - 20, &x, &y);
  this->image_(this->screen_obj_, "checkpoint_flag_28", x, y);

  // Top gap container (brand mark or the reward available now).
  this->top_gap_ = lv_obj_create(this->screen_obj_);
  remove_defaults(this->top_gap_);
  lv_obj_set_size(this->top_gap_, 160, 56);
  lv_obj_set_pos(this->top_gap_, CENTER - 80, 4);

  // Current task, big, and the bottom semicircle timeline.
  this->timeline_ = lv_obj_create(this->screen_obj_);
  remove_defaults(this->timeline_);
  lv_obj_set_size(this->timeline_, SCREEN, SCREEN);
  this->task_big_ = lv_image_create(this->screen_obj_);
  lv_image_set_pivot(this->task_big_, 75, 75);

  // Rebuild the task parts.
  int current = -1;
  for (size_t i = 0; i < r.tasks.size(); i++) {
    if (!r.tasks[i].done) {
      current = static_cast<int>(i);
      break;
    }
  }
  if (current >= 0) {
    lv_image_set_src(this->task_big_, this->img_(r.tasks[current].icon + "_150"));
  } else {
    lv_image_set_src(this->task_big_, this->img_("action_check_88"));
  }
  lv_obj_update_layout(this->task_big_);
  lv_obj_set_pos(this->task_big_, CENTER - lv_obj_get_width(this->task_big_) / 2,
                 205 - lv_obj_get_height(this->task_big_) / 2);

  // Completed tasks collect on the left (grey), future ones on the right.
  int done_slot = 0, future_slot = 0;
  for (size_t i = 0; i < r.tasks.size(); i++) {
    if (static_cast<int>(i) == current)
      continue;
    const bool done = r.tasks[i].done;
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
  this->update_routine_();
}

void KisSegitoUI::update_routine_() {
  if (this->elapsed_arc_ == nullptr)
    return;
  Routine &r = this->current_routine_();
  const uint32_t now_s = millis() / 1000;
  float p = (static_cast<float>(now_s) - static_cast<float>(r.started_s)) / static_cast<float>(r.total_s);
  p = std::max(0.001f, std::min(p, 1.0f));
  auto norm = [](float deg) {
    while (deg < 0)
      deg += 360;
    while (deg >= 360)
      deg -= 360;
    return deg;
  };
  lv_arc_set_bg_angles(this->elapsed_arc_, static_cast<lv_value_precise_t>(norm(240.0f - 300.0f * p)),
                       static_cast<lv_value_precise_t>(240));
  int x, y;
  this->ring_point_(p, 222, &x, &y);
  lv_obj_set_pos(this->now_dot_, x - 9, y - 9);

  const int reward = this->routine_reward_now_();
  if (reward != this->shown_reward_) {
    this->shown_reward_ = reward;
    lv_obj_clean(this->top_gap_);
    if (reward > 0) {
      // The reward available now, as that many tokens.
      const int step = 18;
      const int x0 = 80 - (reward - 1) * step / 2;
      for (int i = 0; i < reward; i++)
        this->image_(this->top_gap_, "token_coin_front_28", x0 + i * step, 30);
    } else {
      this->image_(this->top_gap_, "brand_mark_48", 80, 28);
    }
  }
}

void KisSegitoUI::complete_task_() {
  Routine &r = this->current_routine_();
  int current = -1;
  for (size_t i = 0; i < r.tasks.size(); i++) {
    if (!r.tasks[i].done) {
      current = static_cast<int>(i);
      break;
    }
  }
  if (current < 0)
    return;
  r.tasks[current].done = true;
  const bool last = current == static_cast<int>(r.tasks.size()) - 1;
  const int reward = last ? this->routine_reward_now_() : 0;
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
  lv_obj_t *check = this->image_(this->screen_obj_, "action_check_88", CENTER, 205);
  (void) check;
  lv_timer_t *t = lv_timer_create(
      [](lv_timer_t *timer) {
        auto *self = static_cast<KisSegitoUI *>(lv_timer_get_user_data(timer));
        lv_timer_delete(timer);
        self->busy_ = false;
        self->show_(Screen::ROUTINE);
      },
      ms + 250, this);
  lv_timer_set_repeat_count(t, 1);
  if (last && reward > 0)
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

}  // namespace esphome::kis_segito_ui
