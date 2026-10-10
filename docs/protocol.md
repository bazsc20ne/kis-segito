<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Knob protocol (schema 1)

How the integration and the knob talk to each other, for anyone who wants to
build their own knob or display on top of Kis Segítő. They talk only through the
ESPHome native API.

## Home Assistant → knob

API actions of the firmware (`esphome/kis-segito.yaml`), called by the
integration as `esphome.<node>_<action>`:

| Action | Variables | Purpose |
|---|---|---|
| `set_ui_strings` | `language`, `keys[]`, `values[]` | On-screen texts in the chosen language. The loading text and the language are kept in flash. |
| `set_state` | `data` (JSON string) | Data snapshot, sent on every change and after (re)connecting. |

`set_state` JSON (compact keys to keep the knob's memory use low; times are Unix
epoch seconds, colours `#RRGGBB`):

```json
{
  "v": 1,
  "now": 1791360000,
  "lang": "hu",
  "bg": "bg_2",
  "bgs": 3,
  "scr": {"saver": 0, "dim": 60, "lvl": 15, "blank": 0, "off": 120, "ss": "balls"},
  "anim": "full",
  "idle": 60,
  "children": [
    {"id": "…", "a": "avatar_01", "c": "#6CB8FF", "w": 17, "p": 23,
     "pu": true, "pi": 0, "s": 5, "st": 7, "sel": true}
  ],
  "rewards": [
    {"id": "…", "i": "reward_long_story", "c": 8, "k": "normal"}
  ],
  "routines": [
    {"id": "…", "i": "routine_morning", "s": 1791352800, "e": 1791355500,
     "ch": [], "base": "#6BCB77", "z": [[900, "#FF9F43"], [300, "#FF6B6B"]],
     "cp": [{"id": "…", "i": "task_door_ready", "t": 1791355500, "ch": [],
             "b": [[600, 3], [0, 2]]}],
     "t": [{"id": "…", "i": "task_clothes", "cp": "…"}],
     "done": {"<child id>": ["<task id>"]},
     "cpd": {"<child id>": ["<checkpoint id>"]}}
  ]
}
```

- `children[].ai`, `rewards[].ii`: id of an uploaded picture (empty: use the
  icon). The knob downloads it from `img.u` +
  `/api/kis_segito/knob_image/<id>/<size>` with its own secret `img.t` in the
  `X-Kis-Segito-Token` request header (never in the URL). The answer is raw
  RGB565A8 with a `KSI1` header; the knob shows the icon until it arrives.
  Home Assistant must be reachable over plain HTTP on its internal URL; the
  endpoint answers only requests from the local network (not through Home
  Assistant Cloud). `img` is empty (`u` and `t` are `""`) while the knob's API
  connection is not encrypted. A new key (panel → Settings → Knobs) replaces
  the old one at once; the knob gets it in the next snapshot.
- `scr`: screen power of this knob, idle seconds until the screensaver, dimming,
  drawing off (black, LVGL paused) and backlight off (0 = never); `lvl` is the
  dimmed brightness in percent, `ss` the screensaver (`balls`, `confetti` or `stars`).
- `bg`: background of every screen: `""` (none), a built-in preset
  (`bg_1` … `bg_6`) or an uploaded picture id. The knob
  downloads it like a picture, at size 480, as `KSI2` (RGB565 without alpha,
  the whole screen).
- `bgs`: counts the background choices, also of the same picture. When `bg` or
  `bgs` changes while the knob runs, it stores the new background in its flash
  cache and restarts after 1 minute without input, then shows it from there.
- `children[].pi`: piggy-bank interest paid but not shown to the child yet; the
  knob shows a badge and plays it when the piggy bank is opened.
- `children[].sel`: whether the child can be selected on this knob (device
  assignment); others are shown locked.
- Icons of routines, tasks and rewards (`routine_…`, `task_…`, `reward_…`) are
  not part of the firmware: the knob downloads them like a picture, at the size
  it shows them (`knob_image/<icon>/<size>`).
- Every picture answer carries an `ETag`. The knob stores the pictures in its
  flash cache and, once after each start, asks again with `If-None-Match`; an
  unchanged picture is answered with `304 Not Modified`.
- `children[].a`: the built-in avatars `avatar_01` … `avatar_12` are not part of
  the firmware; the knob downloads them like a picture, at size 180.
- `children[].a`, `rewards[].i`, `routines[].i`, `cp[].i`, `t[].i`: icon ids of
  the shared icon set (the file names in `assets/device/` without the size).
- `routines`: today's routines shown on knobs. `ch` empty = every child.
- `z`: colour zones, each starting `offset` seconds before the end `e`.
- `cp`: checkpoints; `ch` empty = shared (outer track), otherwise the
  children's own (inner track). `b`: reward bands `[seconds early, tokens]`;
  the best matching band counts, late = 0.
- `t[].cp`: the checkpoint a task leads to; finishing all its tasks reaches it.

The knob computes the current time as `now` + the time since the snapshot
arrived, so the track moves without further messages.

## Knob → Home Assistant

The knob publishes each child action as JSON on its **Action** text sensor.
Every action has a unique `id`; the integration runs each id only once and
keeps processed ids for 7 days (at most 2000), so retries never book tokens
twice.

Home Assistant accepts only well-formed actions: at most 255 bytes of JSON,
exactly the fields listed below (no others), ids of 1–64 letters, digits or
`_ . : -`, and `n` a non-zero integer within ±100000. Each knob may send at
most 20 actions per minute; anything else is ignored and logged.

| `a` | Fields | Meaning |
|---|---|---|
| `task` | `c` child, `r` routine, `t` task | A task of today's routine is done. |
| `redeem` | `c` child, `r` reward | The child bought a reward. |
| `piggy` | `c` child, `n` amount (+ deposit, − withdrawal) | Piggy-bank transfer. |
| `seen` | `c` child | The child opened the piggy bank; pending interest was shown. |

The knob shows the result at once; Home Assistant validates and books it and
sends a new snapshot, which corrects the knob if the action was refused (for
example: not enough tokens). Without a Home Assistant connection the knob
refuses token transactions.
