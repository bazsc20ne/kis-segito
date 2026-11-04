<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Assist

Home Assistant's assistants (Assist) can answer questions about a child. The
answers only read Kis Segítő: nothing is changed, booked or ticked.

What can be asked about a child:

- tokens in the wallet (and the piggy bank, when it is unlocked);
- whether there is a task now: the routine running, the next task and how many
  are left (or that there is no task right now);
- the time until the next checkpoint, in minutes;
- the tokens still to earn today: what the remaining checkpoints are worth if
  everything is finished now, under the current reward rules (and how much of
  it is in the routine running now);
- the streak and its target.

The child is named in the sentence by name, or by another name given in the
child editor (**Children → edit → Other names (for Assist)**, comma separated,
for example a nickname). Upper and lower case and accents do not matter, and in
Hungarian the case endings are understood (a name + "-nak/-nek", "-nál/-nél" …).

## Built-in Assist (no LLM)

Works right away, in English and Hungarian, with the default "Home Assistant"
conversation agent. Example sentences (with a child called Alex):

| English | Magyar |
|---|---|
| how many tokens does Alex have | hány zsetonja van Alexnek |
| does Alex have a task now | van most feladata Alexnek |
| what is Alex's task right now | mi Alex feladata most |
| how long until Alex's next checkpoint | mennyi idő van Alex következő checkpointjáig |
| how many tokens can Alex still get today | hány zsetont kaphat még ma Alex |
| what is Alex's streak | hány napos Alex sorozata |

"coins" works in place of "tokens" in the English sentences.

## LLM agents

Agents that use an LLM (with "Assist" chosen under "Control Home Assistant")
get a read-only tool, *Kis Segítő child status*, when at least one Kis Segítő
entity is exposed to the assistant. To expose them: **Settings → Voice
assistants → Expose**, and add the children's Kis Segítő sensors (`sensor.…`
with the child's token balance).

The child sensors carry the same data as attributes, so an agent can also read
them from the exposed entities:

| Attribute | Meaning |
|---|---|
| `piggy_balance`, `piggy_unlocked` | Piggy bank. |
| `task_status` | `task` (there is a task now), `done` (the routine running is finished) or `none` (no routine running). |
| `current_routine`, `current_task`, `tasks_left` | The routine running, the next task, the tasks still to do. |
| `next_checkpoint`, `next_checkpoint_minutes` | The next checkpoint today and the minutes until it. |
| `tokens_earnable_now`, `tokens_earnable_today` | Tokens still to earn in the routine running and today. |
| `streak`, `streak_target` | Streak and its target. |

---

# Assist (magyarul)

A Home Assistant asszisztensei (Assist) válaszolnak egy gyerekről. A válaszok
csak olvassák a Kis Segítőt: semmit nem változtatnak, könyvelnek vagy pipálnak.

Amit egy gyerekről kérdezni lehet:

- a tárca zsetonjai (és a persely, ha nyitva van);
- van-e most feladata: a futó rutin, a következő feladat és hány van még hátra
  (vagy hogy most nincs feladata);
- mennyi idő van a következő checkpointig, percben;
- hány zsetont szerezhet még ma: amennyit a hátralévő checkpointok érnek, ha
  most mindent befejez, a mostani jutalomszabályok szerint (és ebből mennyi a
  most futó rutinban);
- a sorozat és a célja.

A gyereket a mondatban a nevével, vagy a gyerekszerkesztőben megadott másik
nevével lehet megnevezni (**Gyerekek → szerkesztés → Más nevek (az
Assisthoz)**, vesszővel elválasztva, például becenév). A kis- és nagybetű és az
ékezetek nem számítanak, és a ragos alakot is érti ("-nak/-nek", "-nál/-nél" …).

## Beépített Assist (LLM nélkül)

Azonnal működik magyarul és angolul, az alapértelmezett „Home Assistant”
beszélgetési ügynökkel. A példamondatok a fenti táblázatban vannak.

## LLM-ügynökök

Az LLM-et használó ügynökök (ha a „Home Assistant vezérlése” alatt az „Assist”
van kiválasztva) kapnak egy csak olvasó eszközt (*Kis Segítő child status*),
ha legalább egy Kis Segítő entitás ki van téve az asszisztensnek. Kitenni:
**Beállítások → Hangasszisztensek → Kitétel**, és add hozzá a gyerekek Kis
Segítő szenzorait (`sensor.…`, a gyerek zsetonegyenlegével).

A gyerekszenzorok attribútumként is tartalmazzák ugyanezt (lásd a fenti
táblázatot), így egy ügynök a kitett entitásokból is kiolvashatja.
