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

## Actions

`kis_segito.complete_task`, `kis_segito.complete_checkpoint`,
`kis_segito.adjust_tokens`, `kis_segito.redeem_reward`,
`kis_segito.piggy_deposit`, `kis_segito.piggy_withdraw`,
`kis_segito.reverse_transaction`. The ids are shown in the panel (routine
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

## Token history

Tokens are kept in an append-only ledger: nothing is deleted. Reversing adds an
opposite entry, changing an amount adds a correction; balances are always the
sum of the history.

A zsetonokat egy csak bővülő napló tárolja: semmi nem törlődik. A visszavonás
ellentétes tételt, az összeg módosítása korrekciós tételt ad hozzá; az egyenleg
mindig az előzmények összege.
