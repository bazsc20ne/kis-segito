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
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"

namespace esphome::kis_segito_ui {

struct Child {
  std::string avatar;  // icon key without size
  uint32_t color;
  int wallet;
  int piggy;
  bool piggy_unlocked;
  int streak;
  int streak_target;
};

struct Reward {
  std::string icon;
  int cost;
};

struct RoutineTask {
  std::string icon;
  bool done;
};

struct Routine {
  std::string icon;
  uint32_t total_s;    // length of the routine window
  uint32_t started_s;  // seconds since boot when the window started
  std::vector<RoutineTask> tasks;
};

enum class Screen { NONE, CHILDREN, FUNCTIONS, REWARDS, CONFIRM, ROUTINE, TOKENS, PIGGY };

enum class Function { ROUTINE_MORNING, ROUTINE_EVENING, REWARDS, PIGGY, TOKENS };

// Infinite horizontal carousel with four slots (left, centre, right, spare).
class Carousel {
 public:
  using FillFn = std::function<void(lv_obj_t *slot, int index)>;

  void create(lv_obj_t *parent, int count, int selected, int slot_w, int slot_h, int y, int spacing, FillFn fill,
              uint32_t anim_ms);
  void rotate(int dir);
  int selected() const { return this->selected_; }
  lv_obj_t *center_slot() const;
  void refill();

 protected:
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
  void refuse_offline_(lv_obj_t *target);
  void select_child_(int index);

  // Building blocks.
  lv_obj_t *disc_(lv_obj_t *parent, int cx, int cy, int d, lv_color_t color);
  lv_obj_t *image_(lv_obj_t *parent, const std::string &key, int cx, int cy);
  lv_obj_t *number_pill_(lv_obj_t *parent, int cx, int cy, int value, bool with_coin);
  void pile_(lv_obj_t *parent, int cx, int base_y, int count, uint32_t seed, int max_rows, int max_width, int dx,
             int dy);
  lv_obj_t *track_arc_(lv_obj_t *parent, int radius, int width, float p_from, float p_to, lv_color_t color);
  void ring_point_(float p, int radius, int *x, int *y) const;

  // Routine screen.
  void update_routine_();
  void complete_task_();
  void celebrate_(int tokens);
  int routine_reward_now_() const;
  Routine &current_routine_();

  std::vector<Function> functions_for_(const Child &child) const;

  std::map<std::string, image::Image *> images_;
  const lv_font_t *number_font_{nullptr};

  std::vector<Child> children_;
  std::vector<Reward> rewards_;
  std::vector<Routine> routines_;  // [0] morning, [1] evening (test data)

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
  ESPPreferenceObject child_pref_;

  lv_obj_t *screen_obj_{nullptr};
  lv_obj_t *offline_icon_{nullptr};
  Carousel carousel_;

  // Confirm screen.
  lv_obj_t *confirm_ring_{nullptr};
  lv_obj_t *confirm_no_{nullptr};
  lv_obj_t *confirm_yes_obj_{nullptr};

  // Routine screen.
  lv_obj_t *elapsed_arc_{nullptr};
  lv_obj_t *now_dot_{nullptr};
  lv_obj_t *top_gap_{nullptr};
  lv_obj_t *task_big_{nullptr};
  lv_obj_t *timeline_{nullptr};
  int shown_reward_{-1};

  lv_timer_t *tick_timer_{nullptr};
};

}  // namespace esphome::kis_segito_ui
