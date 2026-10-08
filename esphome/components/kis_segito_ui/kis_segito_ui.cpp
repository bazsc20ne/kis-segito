// SPDX-License-Identifier: AGPL-3.0-only

#include "kis_segito_ui.h"

#include <algorithm>
#include <cmath>

#include <esp_heap_caps.h>
#include <esp_http_client.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "esphome/components/json/json_util.h"
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
static constexpr int FADE_W = 16;    // soft inner edge of the band

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

void Carousel::release() {
  for (auto &buf : this->snap_) {
    if (buf != nullptr) {
      lv_draw_buf_destroy(buf);
      buf = nullptr;
    }
  }
}

void Carousel::fill_slot_(int i) {
  lv_obj_t *slot = this->slots_[i];
  lv_obj_clean(slot);  // before freeing the snapshot its image shows
  if (this->snap_[i] != nullptr) {
    lv_draw_buf_destroy(this->snap_[i]);
    this->snap_[i] = nullptr;
  }
  this->fill_(slot, this->index_[i]);
  if (!this->snapshot_)
    return;
  // Render the slot's content at full opacity into one image.
  const bool hidden = lv_obj_has_flag(slot, LV_OBJ_FLAG_HIDDEN);
  const lv_opa_t opa = lv_obj_get_style_opa(slot, LV_PART_MAIN);
  lv_obj_remove_flag(slot, LV_OBJ_FLAG_HIDDEN);
  lv_obj_set_style_opa(slot, LV_OPA_COVER, 0);
  lv_obj_update_layout(slot);
  lv_draw_buf_t *buf = lv_snapshot_take(slot, LV_COLOR_FORMAT_ARGB8888);
  lv_obj_set_style_opa(slot, opa, 0);
  if (hidden)
    lv_obj_add_flag(slot, LV_OBJ_FLAG_HIDDEN);
  if (buf == nullptr) {
    ESP_LOGW(TAG, "Slot snapshot failed (out of memory?); keeping the objects");
    return;
  }
  lv_obj_clean(slot);
  lv_obj_t *img = lv_image_create(slot);
  lv_image_set_src(img, buf);
  lv_obj_set_pos(img, 0, 0);
  this->snap_[i] = buf;
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
    }
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
  this->fill_slot_(spare);
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
      {"door", "task_door_ready", morning.end, {}, {{15 * 60, 3}, {5 * 60, 2}, {0, 1}}},
      {"flag1", "checkpoint_flag", morning.start + 32 * 60, {"test1"}, {{0, 1}}},
  };
  morning.tasks = {
      {"t1", "task_clothes", "breakfast"}, {"t2", "task_breakfast", "breakfast"}, {"t3", "task_toothbrush", "door"},
      {"t4", "task_shoes", "door"},        {"t5", "task_bag", "door"},
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
  // Keep the selection by id across the update.
  const std::string child_id = this->children_.empty() ? "" : this->children_[this->child_].id;
  const std::string routine_id = this->routines_.empty() ? "" : this->current_routine_().id;
  const std::string reward_id =
      this->rewards_.empty() ? "" : this->rewards_[this->reward_ % this->rewards_.size()].id;

  this->state_now_ = root["now"].as<int64_t>();
  this->img_base_ = root["img"]["u"] | "";
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
    if (this->images_.count(child.avatar + "_180") == 0)
      child.avatar = "placeholder_avatar";
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
  this->track_layer_ = lv_obj_create(this->root_);
  remove_defaults(this->track_layer_);
  lv_obj_set_size(this->track_layer_, SCREEN, SCREEN);
  lv_screen_load(this->root_);

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
        // Now and then, while nobody touches the knob, the pile comes alive.
        const uint32_t now = millis();
        if (self->screen_ == Screen::CHILDREN && self->anim_mode_ == 2 && !self->busy_ &&
            !self->children_.empty() && now - self->last_input_ms_ > 15000) {
          if (self->next_idle_anim_ms_ == 0)
            self->next_idle_anim_ms_ = now + 30000 + random_uint32() % 60000;
          if (static_cast<int32_t>(now - self->next_idle_anim_ms_) >= 0) {
            self->next_idle_anim_ms_ = 0;
            self->idle_pile_anim_();
          }
        }
        if (self->screen_ != Screen::CHILDREN && !self->busy_ && millis() - self->last_input_ms_ > self->inactivity_ms_)
          self->show_(Screen::CHILDREN);
      },
      1000, this);

  this->show_(Screen::CHILDREN);
  ESP_LOGI(TAG, "UI started (%s, %u children)", this->have_state_ ? "Home Assistant data" : "test data",
           (unsigned) this->children_.size());
}

// ---------------------------------------------------------------- Helpers

const lv_image_dsc_t *KisSegitoUI::img_(const std::string &key) {
  if (!key.empty() && key[0] == '@') {
    // An uploaded picture: shown once downloaded, the matching icon until then.
    auto photo = this->photos_.find(key);
    if (photo != this->photos_.end())
      return photo->second;
    this->request_photo_(key);
    const bool avatar = key.size() > 4 && key.compare(key.size() - 4, 4, "_180") == 0;
    return this->img_(avatar ? "placeholder_avatar_180" : "reward_gift_160");
  }
  auto it = this->images_.find(key);
  if (it == this->images_.end()) {
    ESP_LOGW(TAG, "Missing image %s", key.c_str());
    return nullptr;
  }
  return it->second->get_lv_image_dsc();
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

// Worker task: downloads queued pictures into PSRAM, one at a time.
void KisSegitoUI::photo_task_(void *arg) {
  auto *self = static_cast<KisSegitoUI *>(arg);
  while (true) {
    PhotoJob job;
    {
      std::lock_guard<std::mutex> lock(self->photo_mutex_);
      if (!self->photo_queue_.empty()) {
        job = self->photo_queue_.front();
        self->photo_queue_.pop_front();
      }
    }
    if (job.key.empty()) {
      vTaskDelay(pdMS_TO_TICKS(250));
      continue;
    }
    esp_http_client_config_t cfg{};
    cfg.url = job.url.c_str();
    cfg.timeout_ms = 10000;
    esp_http_client_handle_t client = esp_http_client_init(&cfg);
    if (client != nullptr)
      esp_http_client_set_header(client, "X-Kis-Segito-Token", job.token.c_str());
    uint8_t *buf = nullptr;
    int got = 0;
    if (client != nullptr && esp_http_client_open(client, 0) == ESP_OK) {
      const int64_t len = esp_http_client_fetch_headers(client);
      if (esp_http_client_get_status_code(client) == 200 && len > 8 && len < 512 * 1024) {
        buf = static_cast<uint8_t *>(heap_caps_malloc(len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
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
    std::lock_guard<std::mutex> lock(self->photo_mutex_);
    self->photo_done_.push_back({job.key, buf, static_cast<size_t>(buf != nullptr ? got : 0)});
  }
}

void KisSegitoUI::loop() {
  std::vector<Download> done;
  {
    std::lock_guard<std::mutex> lock(this->photo_mutex_);
    if (this->photo_done_.empty())
      return;
    done.swap(this->photo_done_);
  }
  bool changed = false;
  for (auto &d : done) {
    // b"KSI1" + width + height (uint16 LE) + RGB565 pixels + alpha bytes.
    if (d.data == nullptr || d.size < 8 || memcmp(d.data, "KSI1", 4) != 0) {
      ESP_LOGW(TAG, "Picture %s could not be downloaded", d.key.c_str());
      this->photo_failed_.insert(d.key);
      if (d.data != nullptr)
        heap_caps_free(d.data);
      continue;
    }
    const uint16_t w = d.data[4] | (d.data[5] << 8);
    const uint16_t h = d.data[6] | (d.data[7] << 8);
    if (d.size != 8 + static_cast<size_t>(w) * h * 3) {
      heap_caps_free(d.data);
      this->photo_failed_.insert(d.key);
      continue;
    }
    auto *dsc = new lv_image_dsc_t{};
    dsc->header.magic = LV_IMAGE_HEADER_MAGIC;
    dsc->header.cf = LV_COLOR_FORMAT_RGB565A8;
    dsc->header.w = w;
    dsc->header.h = h;
    dsc->header.stride = w * 2;
    dsc->data_size = static_cast<uint32_t>(w) * h * 3;
    dsc->data = d.data + 8;
    this->photos_[d.key] = dsc;
    changed = true;
    ESP_LOGI(TAG, "Picture %s ready (%ux%u)", d.key.c_str(), w, h);
  }
  if (changed && this->started_)
    this->pending_rebuild_ = true;  // shown on the next tick, after animations
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
  this->carousel_.release();  // its slots were just deleted
  this->task_big_ = this->timeline_ = this->piggy_label_ = nullptr;
  this->confirm_ring_ = this->confirm_no_ = this->confirm_yes_obj_ = nullptr;
  this->shown_reward_ = -1;
  this->pending_rebuild_ = false;
  this->screen_ = screen;
  if (this->children_.empty()) {
    // No children configured yet: only the track and the brand mark.
    this->screen_ = Screen::CHILDREN;
    lv_obj_set_style_bg_color(this->root_, lv_color_hex(BASE_BG), 0);
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
  if (!this->started_)
    return;
  this->last_input_ms_ = millis();
  this->cancel_idle_anim_();
  if (this->busy_ || this->children_.empty())
    return;
  switch (this->screen_) {
    case Screen::CHILDREN:
      this->carousel_.rotate(dir);
      this->select_child_(this->carousel_.selected());
      this->build_inner_track_();  // the inner track belongs to the centred child
      break;
    case Screen::FUNCTIONS:
      this->carousel_.rotate(dir);
      this->function_ = this->carousel_.selected();
      break;
    case Screen::REWARDS:
      this->carousel_.rotate(dir);
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

void KisSegitoUI::click() {
  if (!this->started_)
    return;
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
      // Slot from y = 60 to 470: avatar, token pile and number. Each slot is
      // rendered into one image (snapshot) so the pile slides smoothly (#10).
      this->screen_obj_, static_cast<int>(this->children_.size()), this->child_, 300, 410, 60, 250,
      [this](lv_obj_t *slot, int index) {
        const Child &c = this->children_[index];
        const int cx = 150;  // slot centre
        // Children of another knob: visible but greyed and locked here.
        const lv_color_t disc = c.selectable ? lv_color_hex(c.color) : lv_color_hex(0x4A4F6A);
        this->disc_(slot, cx, 105, 190, disc);
        lv_obj_t *avatar = this->image_(slot, c.avatar + "_180", cx, 105);
        this->pile_(slot, cx, 300, c.wallet, fnv1_hash(c.id), 12, 15, 19, 10);
        this->number_pill_(slot, cx, 342, c.wallet, true);
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
        if (this->images_.count(icon + "_160") == 0)
          icon = "routine_generic";
        this->image_(slot, icon + "_160", 120, 120);
      },
      this->anim_ms_(240));
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
  this->carousel_.create(
      this->screen_obj_, static_cast<int>(shop.size()), position, 260, 340, 60, 240,
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
        this->pile_(slot, 130, 290, r.cost, fnv1_hash(r.id), 4, 9, 16, 9);
        this->number_pill_(slot, 130, 320, r.cost, false);
      },
      this->anim_ms_(240));
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
  this->task_big_ = lv_image_create(this->screen_obj_);
  lv_image_set_pivot(this->task_big_, 75, 75);

  int current = -1;
  for (size_t i = 0; i < r.tasks.size(); i++) {
    if (!this->is_done_(r, r.tasks[i].id)) {
      current = static_cast<int>(i);
      break;
    }
  }
  const lv_image_dsc_t *big = current >= 0 ? this->img_(r.tasks[current].icon + "_150") : nullptr;
  lv_image_set_src(this->task_big_, big != nullptr ? big : this->img_("action_check_88"));
  lv_obj_update_layout(this->task_big_);
  lv_obj_set_pos(this->task_big_, CENTER - lv_obj_get_width(this->task_big_) / 2,
                 205 - lv_obj_get_height(this->task_big_) / 2);

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

void KisSegitoUI::build_track_() {
  lv_obj_clean(this->track_layer_);
  this->inner_layer_ = this->elapsed_arc_ = this->now_dot_ = this->top_gap_ = nullptr;
  this->shown_reward_ = -1;
  const lv_color_t bg = lv_obj_get_style_bg_color(this->root_, LV_PART_MAIN);

  // Homogeneous band in the background colour behind the arcs, with a soft
  // inner edge, so carousel content passing under it does not disturb them.
  for (int i = 0; i < 4; i++) {
    const int w = FADE_W / 4;
    lv_obj_t *fade = this->track_arc_(this->track_layer_, BAND_R - FADE_W + (i + 1) * w, w, 0.0f, 1.0f, bg);
    lv_arc_set_bg_angles(fade, 0, 360);
    lv_obj_set_style_arc_rounded(fade, false, LV_PART_MAIN);
    lv_obj_set_style_arc_opa(fade, static_cast<lv_opa_t>(50 + i * 50), LV_PART_MAIN);
  }
  lv_obj_t *band = this->track_arc_(this->track_layer_, CENTER, CENTER - BAND_R, 0.0f, 1.0f, bg);
  lv_arc_set_bg_angles(band, 0, 360);
  lv_obj_set_style_arc_rounded(band, false, LV_PART_MAIN);

  // Outer, shared track. The whole future colour structure is visible from
  // the start: the base colour, then each zone from its offset before the end.
  Routine *r = this->track_routine_();
  this->shown_routine_ = r;
  if (r != nullptr) {
    float from = 0.0f;
    lv_color_t color = lv_color_hex(r->base_color);
    for (const auto &zone : r->zones) {
      const float p = track_p(*r, r->end - zone.offset_s);
      if (p > from)
        this->track_arc_(this->track_layer_, OUTER_R, OUTER_W, from, p, color);
      from = std::max(from, p);
      color = lv_color_hex(zone.color);
    }
    if (from < 1.0f)
      this->track_arc_(this->track_layer_, OUTER_R, OUTER_W, from, 1.0f, color);
    // Elapsed time is dimmed; update_track_() moves it every second.
    this->elapsed_arc_ = this->track_arc_(this->track_layer_, OUTER_R + 1, OUTER_W + 2, 0.0f, 0.001f,
                                         lv_color_hex(TRACK_DIM));
  } else {
    // No routine running: an empty track.
    this->track_arc_(this->track_layer_, OUTER_R, OUTER_W, 0.0f, 1.0f, lv_color_hex(TRACK_DIM));
  }

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
      if (this->images_.count(key) == 0)
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
  this->track_arc_(this->inner_layer_, INNER_R, INNER_W, 0.0f, 1.0f,
                   lv_color_mix(lv_color_hex(child.color), lv_color_hex(BASE_BG), 200));
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
    if (this->images_.count(key) == 0)
      key = this->images_.count(cp.icon + "_32") ? cp.icon + "_32" : "checkpoint_flag_28";
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
  if (r != nullptr && this->elapsed_arc_ != nullptr) {
    const float p = std::max(0.001f, track_p(*r, this->now_()));
    float start = 240.0f - 300.0f * p;
    if (start < 0)
      start += 360;
    lv_arc_set_bg_angles(this->elapsed_arc_, static_cast<lv_value_precise_t>(start),
                         static_cast<lv_value_precise_t>(240));
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

}  // namespace esphome::kis_segito_ui
