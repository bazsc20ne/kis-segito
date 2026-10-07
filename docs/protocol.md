<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Knob protocol (schema 1)

The integration and the knob talk only through the ESPHome native API.

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
  "anim": "full",
  "idle": 60,
  "children": [
    {"id": "…", "a": "test_avatar_1", "c": "#6CB8FF", "w": 17, "p": 23,
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

- `children[].pi`: piggy-bank interest paid but not shown to the child yet; the
  knob shows a badge and plays it when the piggy bank is opened.
- `children[].sel`: whether the child can be selected on this knob (device
  assignment); others are shown locked.
- `children[].a`, `rewards[].i`, `routines[].i`, `cp[].i`, `t[].i`: icon ids of
  the shared icon set (`docs/icons.md`).
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
keeps processed ids for 7 days, so retries never book tokens twice.

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
