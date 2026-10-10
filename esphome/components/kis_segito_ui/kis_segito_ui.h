// SPDX-License-Identifier: AGPL-3.0-only
//
// Kis Segito child UI for the round 480x480 knob display (LVGL 9).
// Input: rotate(+1/-1) per UI step, click(), long_press() (= back one level).

#pragma once

#include <deque>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <vector>

#include <lvgl.h>

#include "esphome/components/font/font.h"
#include "esphome/components/image/image.h"
#include "esphome/components/text_sensor/text_sensor.h"
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"

#include "picture_cache.h"

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

struct ItemPic;  // a drawn carousel item (kis_segito_ui.cpp)

// Infinite horizontal carousel with four slots (left, centre, right, spare).
class Carousel {
 public:
  using FillFn = std::function<void(lv_obj_t *slot, int index)>;

  // With snapshot = true each slot is rendered once into a single image, so a
  // slot with many objects (token piles) still slides smoothly.
  void create(lv_obj_t *parent, int count, int selected, int slot_w, int slot_h, int y, int spacing, FillFn fill,
              uint32_t anim_ms, bool snapshot = false);
  // One step; animate = false moves at once (several queued steps).
  void rotate(int dir, bool animate = true);
  // Moves several items at once, without animation (one redraw).
  void jump(int steps);
  int selected() const { return this->selected_; }
  lv_obj_t *center_slot() const;
  void refill();
  // Frees the slot snapshots; call after the slots were deleted.
  void release();
  // release() for slots that were deleted with their screen.
  void forget();
  // A downloaded picture arrived: slots rendered without it are drawn again.
  void refill_key(const std::string &key);
  // Whether a slot shows (or waits for) this downloaded picture.
  bool uses(const std::string &key) const;
  // Called when a slide has ended.
  std::function<void()> on_settled;
  // Optional: what an item's picture depends on; items with the same value
  // are drawn once and then copied (see fill_slot_).
  std::function<std::string(int index)> sig;

 protected:
  void fill_slot_(int slot);
  void place_(int slot, int offset, bool animate);
  int wrap_(int index) const;
  // After a slide, fills the spare slot with the next item in the same
  // direction, so the next turn starts at once.
  void prepare_spare_();
  void show_pic_(int i, const std::shared_ptr<ItemPic> &pic);

  lv_obj_t *slots_[4]{};
  int index_[4]{};
  int offset_[4]{};
  int count_{0};
  int selected_{0};
  int slot_w_{0};
  int slot_h_{0};
  int y_{0};
  int spacing_{0};
  uint32_t anim_ms_{250};
  bool snapshot_{false};
  lv_obj_t *window_{nullptr};
  std::shared_ptr<ItemPic> pic_[4];  // the picture each slot shows
  int win_y_{0};
  std::set<std::string> keys_[4];  // downloaded pictures each slot uses
  bool ready_[4]{};                // the slot holds item index_[i]
  int last_dir_{1};
  lv_timer_t *prepare_timer_{nullptr};
  FillFn fill_;
};

class KisSegitoUI : public Component {
 public:
  void setup() override;
  void loop() override;
  // Before a restart (e.g. after an update): the download task stops, so it
  // is not writing the flash cache while the knob restarts.
  void on_shutdown() override;
  float get_setup_priority() const override { return setup_priority::PROCESSOR; }

  void add_image(const std::string &key, image::Image *img) { this->images_[key] = img; }
  void set_number_font(font::Font *f) { this->number_font_ = f->get_lv_font(); }

  // Called from YAML. Input is queued and handled in loop(), so the input
  // callbacks return at once.
  void start();
  void rotate(int dir);
  void click();
  void long_press();
  void set_connected(bool connected);
  // Screen power timers from Home Assistant, in seconds (0 = never), and the
  // dimmed brightness in percent.
  uint32_t saver_after() const { return this->saver_after_; }
  uint32_t dim_after() const { return this->dim_after_; }
  uint8_t dim_level() const { return this->dim_level_; }
  uint32_t blank_after() const { return this->blank_after_; }
  uint32_t off_after() const { return this->off_after_; }
  bool started() const { return this->started_; }
  // Screensaver: "balls" (the loading screen's), "confetti" or "stars"; the
  // last two run on their own screen (start_confetti / stop_confetti).
  const std::string &saver_type() const { return this->saver_type_; }
  void start_confetti();
  void stop_confetti();
  // Shows the child UI again (after the screensaver).
  void show_ui();
  void set_animation_mode(const std::string &mode);
  // Language code from Home Assistant; picks language-specific artwork.
  void set_language(const std::string &language);
  // Data snapshot from Home Assistant (JSON, schema 1).
  void set_state(const std::string &json);
  // Text sensor the child's actions are published on (JSON) for Home Assistant.
  void set_action_sensor(text_sensor::TextSensor *sensor) { this->action_sensor_ = sensor; }

 protected:
  const lv_image_dsc_t *img_(const std::string &key);
  // The downloaded-picture key ("@<id>_<size>") an image key is shown with,
  // or "" for a built-in image.
  std::string photo_key_(const std::string &key) const;
  std::string pic_state_(const std::string &key) const;
  // Remembers an image object that shows a downloaded picture, so it can be
  // updated when the picture arrives or changes.
  void bind_(lv_obj_t *obj, const std::string &key, int cx, int cy);
  static void unbind_cb_(lv_event_t *e);
  void picture_ready_(const std::string &key);
  // Frees downloaded pictures nothing shows (the least recently used last).
  void release_photos_(size_t need);
  void handle_input_();
  void do_rotate_(int dir, bool animate = true);
  void do_click_();
  void do_long_press_();
  void poll_connection_();
  void reconnect_();
  void confetti_step_();
  // The time track's ring, computed into pictures (see render_ring_).
  struct RingSpec {
    static constexpr int MAX_ZONES = 8;
    uint32_t bg_color{0};
    bool has_inner{false};
    uint32_t inner_color{0};
    const lv_image_dsc_t *bg_image{nullptr};
    bool has_routine{false};
    int zone_count{0};
    float zone_from[MAX_ZONES]{};
    uint32_t zone_colors[MAX_ZONES]{};
    float elapsed{0};
    std::string bg_key;  // which background picture (the same one loaded again is equal)
    // Equal apart from the parts on the tracks (the child's colour, the
    // elapsed time).
    bool same_but_tracks(const RingSpec &o) const {
      if (bg_color != o.bg_color || bg_key != o.bg_key || has_routine != o.has_routine ||
          zone_count != o.zone_count || has_inner != o.has_inner)
        return false;
      for (int i = 0; i < zone_count; i++) {
        if (zone_from[i] != o.zone_from[i] || zone_colors[i] != o.zone_colors[i])
          return false;
      }
      return true;
    }
    // Equal apart from the elapsed part.
    bool same_but_elapsed(const RingSpec &o) const {
      if (bg_color != o.bg_color || bg_key != o.bg_key || has_routine != o.has_routine ||
          zone_count != o.zone_count || has_inner != o.has_inner || inner_color != o.inner_color)
        return false;
      for (int i = 0; i < zone_count; i++) {
        if (zone_from[i] != o.zone_from[i] || zone_colors[i] != o.zone_colors[i])
          return false;
      }
      return true;
    }
    bool operator==(const RingSpec &o) const {
      if (!this->same_but_elapsed(o) || elapsed != o.elapsed)
        return false;
      for (int i = 0; i < zone_count; i++) {
        if (zone_from[i] != o.zone_from[i] || zone_colors[i] != o.zone_colors[i])
          return false;
      }
      return true;
    }
  };
  void render_ring_tile_(int index, float r_min, float r_max);
  bool ring_ready_();
  void update_ring_();
  RingSpec ring_spec_;
  bool ring_drawn_{false};
  // Uploaded pictures ("@<id>_<size>" keys), downloaded in the background.
  void request_photo_(const std::string &key);
  void log_reset_reason_();
  const lv_image_dsc_t *background_(const std::string &id);
  void apply_background_(const std::string &id);
  bool has_image_(const std::string &key) const;
  static void photo_task_(void *arg);
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

  // Picture downloads: the worker task fills done_, loop() turns them into
  // LVGL images (LVGL is only touched from the main loop).
  struct PhotoJob {
    std::string key;
    std::string url;
    std::string token;
    int tries{0};  // waits for memory so far
  };
  struct Download {
    std::string key;
    uint8_t *data{nullptr};
    size_t size{0};
    bool fresh{false};  // downloaded now, not read from the flash cache
  };
  struct Photo {
    lv_image_dsc_t *dsc{nullptr};
    uint8_t *raw{nullptr};  // the downloaded buffer (header + pixels)
    size_t bytes{0};
    uint32_t used_ms{0};
  };
  struct Binding {
    lv_obj_t *obj;
    std::string key;
    int16_t cx, cy;
  };
  std::string img_base_;   // Home Assistant address for pictures
  std::string img_token_;  // this knob's picture secret
  std::string general_bg_;  // general background picture id (empty: none)
  std::string wanted_bg_;   // background id the current screen asks for
  std::string shown_bg_;    // picture key of the background on screen
  std::map<std::string, Photo> photos_;
  // Bumped when a picture's content changes (a new version downloaded), not
  // when the same picture is loaded again.
  std::map<std::string, uint32_t> photo_version_;
  std::set<std::string> photo_seen_;  // pictures loaded at least once
  std::vector<Binding> bindings_;
  std::set<std::string> photo_requested_;
  std::set<std::string> photo_failed_;  // retried with the next picture key
  std::deque<PhotoJob> photo_queue_;
  std::vector<Download> photo_done_;
  std::mutex photo_mutex_;
  bool photo_task_started_{false};
  // Set by the download task when a picture needs memory; the main loop
  // makes room (unused carousel pictures, unused downloaded pictures).
  volatile size_t need_memory_{0};
  // Set by the download task when a new background was stored in the flash
  // cache: the main loop restarts the knob to show it.
  volatile bool restart_for_picture_{false};
  volatile uint32_t restart_key_{0};
  // The picture the restart before this start was made for (0: none).
  uint32_t restarted_for_{0};
  bool picture_restart_allowed_(const std::string &key) const;
  volatile bool stopping_{false};
  volatile bool worker_idle_{true};
  // Download task only: the flash cache and the pictures checked with Home
  // Assistant since the start.
  PictureCache cache_;
  std::set<std::string> validated_;
  uint32_t state_sig_{0};  // the last snapshot without its time
  std::deque<int> input_;  // queued input: +1/-1 turn, 2 click, 3 long press
  uint32_t last_poll_ms_{0};

  bool started_{false};
  bool boot_info_logged_{false};
  uint32_t saver_after_{0};
  uint32_t dim_after_{60};
  uint8_t dim_level_{15};
  uint32_t blank_after_{0};
  uint32_t off_after_{120};
  std::string saver_type_{"balls"};
  static constexpr int CONFETTI = 40;
  static constexpr int CONFETTI_MIN = 36;  // blown-away pieces come back below this
  struct Piece {
    lv_obj_t *obj{nullptr};
    bool on_screen{false};
    float x{0}, y{0};             // top left, px
    float vy{0};                  // falling speed, px/s
    float drift{0}, drift_to{0};  // sideways speed now and where it heads, px/s
    uint32_t drift_ms{0};         // when it picks a new direction
    float gust{0}, gust_vy{0};    // extra speed from a gust, px/s
    float sway{0}, sway_hz{0}, phase{0};
    int w{0}, h{0};
  };
  void spawn_piece_(Piece &p, bool anywhere);
  struct Star {
    lv_obj_t *obj{nullptr};
    float t{0};  // time in its cycle, s
    float fade_in{2}, hold{1}, fade_out{2}, gap{1};
    uint8_t peak{255}, opa{0};
  };
  static constexpr int STARS = 28;
  static constexpr int SHOOT_PARTS = 6;
  void spawn_star_(Star &st, bool first);
  void stars_step_();
  static lv_draw_buf_t *star_image(int color, int size);
  Star stars_list_[STARS];
  lv_obj_t *shoot_[SHOOT_PARTS]{};
  float shoot_p_[6]{};  // start, curve and end point
  uint32_t shoot_start_ms_{0}, shoot_ms_{1500}, next_shoot_ms_{0};
  Piece confetti_[CONFETTI];
  lv_obj_t *saver_screen_{nullptr};
  bool stars_{false};
  lv_timer_t *confetti_timer_{nullptr};
  uint32_t confetti_ms_{0};
  uint32_t next_gust_ms_{0};
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
  lv_obj_t *ring_layer_{nullptr};   // the track ring's pictures
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
