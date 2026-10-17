<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Automations / Automatizálás

## Event `kis_segito_event`

Fired for every important change. Common fields: `event_type`, `child_id`,
`child_name`, `wallet_balance`, `piggy_balance`, `timestamp`; plus the fields
of the event type:

| `event_type` | Extra fields |
|---|---|
| `task_completed` | `routine_id`, `task_id` |
| `checkpoint_completed` | `routine_id`, `checkpoint_id`, `amount` |
| `reward_redeemed` | `transaction_id`, `reward_id`, `reward_name`, `amount` |
| `piggy_deposit`, `piggy_withdrawal` | `transaction_id`, `amount` |
| `piggy_interest` | `transaction_id`, `amount` |
| `streak_completed` | `transaction_id`, `amount` |
| `manual_adjustment` | `transaction_id`, `amount` |
| `transaction_reversed` | `transaction_id`, `reverses` |
| `transaction_revised` | `transaction_id`, `corrects`, `amount` |

Example: a notification when a reward is bought.

```yaml
triggers:
  - trigger: event
    event_type: kis_segito_event
    event_data:
      event_type: reward_redeemed
actions:
  - action: notify.notify
    data:
      message: "{{ trigger.event.data.child_name }}: {{ trigger.event.data.reward_name }}"
```

## Notification rules / Értesítési szabályok

On the panel's **Notifications** page each rule sends a short message through a Home
Assistant notify action (for example the companion app) for the chosen event types and
children. A failed notification never undoes a token transaction.

A panel **Értesítések** oldalán minden szabály egy Home Assistant értesítési célponton
(pl. mobilalkalmazás) keresztül rövid üzenetet küld a kiválasztott eseményekről és
gyerekekről. Sikertelen értesítés soha nem von vissza zsetontranzakciót.

## Actions

`kis_segito.complete_task`, `kis_segito.complete_checkpoint`,
`kis_segito.adjust_tokens`, `kis_segito.redeem_reward`,
`kis_segito.piggy_deposit`, `kis_segito.piggy_withdraw`,
`kis_segito.reverse_transaction`, `kis_segito.set_today_template`,
`kis_segito.set_background`. The ids are shown in the panel (routine
editor) and in the event data. Example: a checkpoint completed by your own
sensor:

```yaml
actions:
  - action: kis_segito.complete_checkpoint
    data:
      child_id: "…"
      routine_id: "…"
      checkpoint_id: "…"
```

### Background / Háttér

`kis_segito.set_background` chooses the background of every knob, like the
**Settings** page: `bg_1` … `bg_6`, the id of an uploaded picture (shown in
the address of the picture), or empty for no picture. After each change every
knob restarts once, after 1 minute without use, to show the new picture. With
it you can, for example, switch to a night background at sunset:

A `kis_segito.set_background` minden gomb hátterét választja ki, mint a
**Beállítások** oldal: `bg_1` … `bg_6`, egy feltöltött kép azonosítója, vagy
üresen: nincs kép. Minden csere után a gombok 1 perc használaton kívüli idő
után egyszer újraindulnak, hogy az új képet mutassák. Így például
napnyugtakor éjszakai háttérre válthatsz:

```yaml
triggers:
  - trigger: sun
    event: sunset
    id: night
  - trigger: sun
    event: sunrise
    id: day
actions:
  - action: kis_segito.set_background
    data:
      background: "{{ 'bg_1' if trigger.id == 'night' else 'bg_2' }}"
```

## Knob screen / A gomb képernyője

The knob's own ESPHome actions, named after its node name
(`esphome.<node>_<action>`; with the default name `kis-segito` for example
`esphome.kis_segito_wake`):

| Action | Data | What it does |
|---|---|---|
| `wake` | – | Wakes the screen with a soft fade-in. |
| `screensaver` | `enable: true` / `false` | Starts or ends the screensaver. |
| `night_light` | `enable`, `brightness` (%), `kelvin` | Shows or ends the night light; 0 uses the panel settings. |

Its state is on the knob's device: **Night light**, **Screensaver**, **Screen
brightness**, and the sensor inputs **Presence**, **Distance**, **Illuminance**
(see [sensors.md](sensors.md)).

A gomb saját ESPHome-műveletei a gomb nevével (`esphome.<név>_<művelet>`;
alapértelmezett névvel például `esphome.kis_segito_wake`): `wake` (lágy
felébresztés), `screensaver` (`enable`: képernyővédő be/ki), `night_light`
(`enable`, `brightness` %, `kelvin`; 0 = a panel beállítása). Az állapotuk a
gomb eszközén látható.

Example: night light at bedtime, off in the morning.

```yaml
triggers:
  - trigger: time
    at: "20:00:00"
    id: "on"
  - trigger: time
    at: "07:00:00"
    id: "off"
actions:
  - action: esphome.kis_segito_night_light
    data:
      enable: "{{ trigger.id == 'on' }}"
      brightness: 20
      kelvin: 2400
```

## Token history

Tokens are kept in an append-only ledger: nothing is deleted. Reversing adds an
opposite entry, changing an amount adds a correction; balances are always the
sum of the history.

A zsetonokat egy csak bővülő napló tárolja: semmi nem törlődik. A visszavonás
ellentétes tételt, az összeg módosítása korrekciós tételt ad hozzá; az egyenleg
mindig az előzmények összege.
