// SPDX-License-Identifier: AGPL-3.0-only
//
// Kis Segito child UI for the round 480x480 knob display (LVGL 9).
// Input: rotate(+1/-1) per UI step, click(), long_press() (= back one level).

#pragma once

#include <functional>
#include <map>
#include <string>
#include <vector>

#include <lvgl.h>

#include "esphome/components/font/font.h"
#include "esphome/components/image/image.h"
#include "esphome/components/text_sensor/text_sensor.h"
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"

namespace esphome::kis_segito_ui {

// Data model. Home Assistant sends it as a JSON snapshot (set_state, see
// docs/protocol.md); until then built-in test data is shown. Times are Unix
// epoch seconds.

struct Child {
  std::string id;
  std::string avatar;  // icon key without size
  uint32_t color{0x6CB8FF};
  int wallet{0};
  int piggy{0};
  bool piggy_unlocked{false};
  int streak{0};
  int streak_target{7};
  bool selectable{true};  // false: shown locked on this knob
  int pending_interest{0};  // interest not shown to the child yet
};

struct Reward {
  std::string id;
  std::string icon;
  int cost{0};
  bool piggy_unlock{false};
};

struct Band {
  int early_s;  // completing at least this early before the checkpoint ...
  int tokens;   // ... is worth this many tokens
};

struct Checkpoint {
  std::string id;
  std::string icon;
  int64_t t{0};
  std::vector<std::string> children;  // empty = everyone (outer track)
  std::vector<Band> bands;
};

struct RoutineTask {
  std::string id;
  std::string icon;
  std::string checkpoint;
};

struct Zone {
  int offset_s;  // starts this long before the routine end
  uint32_t color;
};

struct Routine {
  std::string id;
  std::string icon;
  int64_t start{0};
  int64_t end{0};
  std::vector<std::string> children;  // empty = everyone
  uint32_t base_color{0x6BCB77};
  std::vector<Zone> zones;
  std::vector<Checkpoint> checkpoints;
  std::vector<RoutineTask> tasks;
  std::map<std::string, std::vector<std::string>> done;      // child -> task ids
  std::map<std::string, std::vector<std::string>> cp_done;   // child -> checkpoint ids
};

enum class Screen { NONE, CHILDREN, FUNCTIONS, REWARDS, CONFIRM, ROUTINE, TOKENS, PIGGY };

enum class FnType { ROUTINE, REWARDS, PIGGY, TOKENS };

struct FnItem {
  FnType type;
  int routine;  // index into routines_ for FnType::ROUTINE
};

// Infinite horizontal carousel with four slots (left, centre, right, spare).
class Carousel {
 public:
  using FillFn = std::function<void(lv_obj_t *slot, int index)>;

  // With snapshot = true each slot is rendered once into a single image, so a
  // slot with many objects (token piles) still slides smoothly.
  void create(lv_obj_t *parent, int count, int selected, int slot_w, int slot_h, int y, int spacing, FillFn fill,
              uint32_t anim_ms, bool snapshot = false);
  void rotate(int dir);
  int selected() const { return this->selected_; }
  lv_obj_t *center_slot() const;
  void refill();
  // Frees the slot snapshots; call after the slots were deleted.
  void release();

 protected:
  void fill_slot_(int slot);
  void place_(int slot, int offset, bool animate);
  int wrap_(int index) const;

  lv_obj_t *slots_[4]{};
  int index_[4]{};
  int offset_[4]{};
  int count_{0};
  int selected_{0};
  int slot_w_{0};
  int y_{0};
  int spacing_{0};
  uint32_t anim_ms_{250};
  bool snapshot_{false};
  lv_draw_buf_t *snap_[4]{};
  FillFn fill_;
};

class KisSegitoUI : public Component {
 public:
  void setup() override;
  void loop() override {}
  float get_setup_priority() const override { return setup_priority::PROCESSOR; }

  void add_image(const std::string &key, image::Image *img) { this->images_[key] = img; }
  void set_number_font(font::Font *f) { this->number_font_ = f->get_lv_font(); }

  // Called from YAML.
  void start();
  void rotate(int dir);
  void click();
  void long_press();
  void set_connected(bool connected);
  void set_animation_mode(const std::string &mode);
  // Language code from Home Assistant; picks language-specific artwork.
  void set_language(const std::string &language);
  // Data snapshot from Home Assistant (JSON, schema 1).
  void set_state(const std::string &json);
  // Text sensor the child's actions are published on (JSON) for Home Assistant.
  void set_action_sensor(text_sensor::TextSensor *sensor) { this->action_sensor_ = sensor; }

 protected:
  const lv_image_dsc_t *img_(const std::string &key);
  uint32_t anim_ms_(uint32_t full_ms) const;
  lv_color_t tint_(uint32_t color, uint8_t amount) const;

  void show_(Screen screen);
  void build_children_();
  void build_functions_();
  void build_rewards_();
  void build_confirm_();
  void build_routine_();
  void build_tokens_();
  void build_piggy_();
  void update_piggy_amount_();
  // Idle micro-animation on the child carousel: a token rolls off the pile
  // and a hand puts it back (full animation mode only).
  void idle_pile_anim_();
  void cancel_idle_anim_();
  // Time track shown behind every screen: the shared outer track, the selected
  // child's inner track and the top gap.
  void build_track_();
  void build_inner_track_();
  void update_track_();
  Routine *track_routine_();
  void refuse_offline_(lv_obj_t *target);
  void shake_(lv_obj_t *target);
  void select_child_(int index);
  void send_action_(const char *kind, const std::string &extra);
  int64_t now_() const;
  void load_test_data_();
  bool is_done_(const Routine &r, const std::string &task_id) const;
  bool cp_done_(const Routine &r, const std::string &cp_id) const;
  const Checkpoint *next_checkpoint_(const Routine &r) const;

  // Building blocks.
  lv_obj_t *disc_(lv_obj_t *parent, int cx, int cy, int d, lv_color_t color);
  lv_obj_t *image_(lv_obj_t *parent, const std::string &key, int cx, int cy);
  lv_obj_t *number_pill_(lv_obj_t *parent, int cx, int cy, int value, bool with_coin);
  void pile_(lv_obj_t *parent, int cx, int base_y, int count, uint32_t seed, int max_rows, int max_width, int dx,
             int dy);
  lv_obj_t *track_arc_(lv_obj_t *parent, int radius, int width, float p_from, float p_to, lv_color_t color);
  void ring_point_(float p, int radius, int *x, int *y) const;

  // Routine screen.
  void complete_task_();
  void celebrate_(int tokens);
  int routine_reward_now_() const;
  Routine &current_routine_();

  std::vector<FnItem> functions_for_(const Child &child) const;
  std::vector<int> shop_() const;

  std::map<std::string, image::Image *> images_;
  const lv_font_t *number_font_{nullptr};

  std::vector<Child> children_;
  std::vector<Reward> rewards_;
  std::vector<Routine> routines_;  // today's routines
  bool have_state_{false};         // a snapshot from Home Assistant arrived
  bool pending_rebuild_{false};    // new data while an animation ran
  int64_t state_now_{0};           // epoch time in the snapshot ...
  uint32_t state_ms_{0};           // ... and millis() when it arrived
  uint32_t action_seq_{0};
  text_sensor::TextSensor *action_sensor_{nullptr};

  bool started_{false};
  Screen screen_{Screen::NONE};
  int child_{0};
  int function_{0};
  int reward_{0};
  bool confirm_yes_{false};
  int routine_{0};
  int anim_mode_{2};  // 0 off, 1 reduced, 2 full
  uint32_t last_input_ms_{0};
  bool busy_{false};  // an action animation is running
  bool connected_{true};
  uint32_t inactivity_ms_{60000};  // back to the child carousel after this
  int piggy_amount_{0};            // tokens to move: + into, - out of the piggy bank
  lv_obj_t *piggy_label_{nullptr};
  lv_obj_t *idle_coin_{nullptr};
  lv_obj_t *idle_hand_{nullptr};
  uint32_t next_idle_anim_ms_{0};
  std::string language_;
  ESPPreferenceObject child_pref_;  // hash of the last selected child id

  lv_obj_t *root_{nullptr};        // the LVGL screen
  lv_obj_t *track_layer_{nullptr};  // time track, kept across screens
  lv_obj_t *inner_layer_{nullptr};  // the selected child's part of the track
  lv_obj_t *screen_obj_{nullptr};   // content of the current screen
  lv_obj_t *offline_icon_{nullptr};
  Carousel carousel_;

  // Confirm screen.
  lv_obj_t *confirm_ring_{nullptr};
  lv_obj_t *confirm_no_{nullptr};
  lv_obj_t *confirm_yes_obj_{nullptr};

  // Time track.
  lv_obj_t *elapsed_arc_{nullptr};
  lv_obj_t *now_dot_{nullptr};
  lv_obj_t *top_gap_{nullptr};
  const Routine *shown_routine_{nullptr};
  // Routine screen.
  lv_obj_t *task_big_{nullptr};
  lv_obj_t *timeline_{nullptr};
  int shown_reward_{-1};

  lv_timer_t *tick_timer_{nullptr};
};

}  // namespace esphome::kis_segito_ui
