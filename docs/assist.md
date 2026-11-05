<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Assist

Home Assistant's assistants (Assist) can answer questions about a child, or
about every child at once. The answers only read Kis Segítő: nothing is
changed, booked or ticked.

What can be asked:

- tokens in the wallet (and the piggy bank, when it is unlocked);
- whether there is a task now: the routine running, the next task and how many
  are left (or that there is no task right now);
- when the next checkpoint is: how long until it and at what time;
- the tokens still to earn today: what the remaining checkpoints are worth if
  everything is finished now, under the current reward rules (and how much of
  it is in the routine running now);
- the streak and its target.

The child is named by name, or by another name given in the child editor
(**Children → edit → Other names (for Assist)**, comma separated, for example
a nickname). Upper and lower case, accents and punctuation do not matter. In
Hungarian the name is understood with its endings too (Alex, Alexnek, Alexnél,
Alexé). A question without a name ("how many tokens do the kids have") is
answered for every child.

The answers are written to be spoken: numbers and times are words, without
digits or symbols ("in a quarter of an hour, at half past seven", „negyed óra
múlva, fél nyolckor”), so every text-to-speech voice (Piper, Home Assistant
Cloud, others) reads them right. Each answer has a few wordings, so they do not
sound the same every time. Hungarian questions get Hungarian answers; every
other language gets English answers.

## Which agent answers

| Setup | What happens |
|---|---|
| Only the built-in "Home Assistant" agent | The sentences below are answered by Kis Segítő right away. |
| LLM agent, **Prefer handling commands locally** on | The sentences below are still answered locally by Kis Segítő (fast, no LLM needed); everything else goes to the LLM, which can use Kis Segítő's tool. |
| LLM agent, **Prefer handling commands locally** off | Every question goes to the LLM, which asks Kis Segítő's tool (*Kis Segítő child status*) and answers in its own words. |

A sentence with a name Kis Segítő does not know is not answered by Kis Segítő:
it goes on to the other sentences and agents as if Kis Segítő were not there.

## Sentences the built-in agent understands

With a child called Alex. The words in brackets are optional, a slash means
"or"; word order is free in most Hungarian sentences.

| | Magyar | English |
|---|---|---|
| Tokens | hány / mennyi zsetonja van Alexnek; Alexnek hány zsetonja van; mennyi pénze / pontja / érméje van Alexnek; Alex egyenlege; van még zsetonja Alexnek | how many tokens / coins / points does Alex have; how many coins has Alex got; what's Alex's balance; Alex's wallet |
| Tokens, every child | kinek mennyi zsetonja van; mennyi zseton van a gyerekeknek; hogy állnak a gyerekek; kinek mennyi van | how many tokens do the kids have; who has how many coins; how are the kids doing |
| Task | van most feladata Alexnek; mi Alex feladata most; mi a feladata Alexnek; mit kell most csinálnia Alexnek; mivel tart most Alex | does Alex have a task now; what's Alex's task; what should Alex be doing now; what is Alex doing now |
| Task, every child | kinek van most feladata; mik a feladatok most | does anyone have a task now; who has something to do now |
| Checkpoint | mikor van Alex következő ellenőrzőpontja; mikor jön Alexnek a következő ellenőrzőpontja; mennyi idő van még Alex következő ellenőrzőpontjáig; meddig van még ideje Alexnek | when is Alex's next checkpoint; how long until Alex's next checkpoint; how much time does Alex have left |
| Checkpoint, every child | mikor van a következő ellenőrzőpont; mennyi idő van még a következő ellenőrzőpontig | when is the next checkpoint; how long until the next checkpoint |
| Tokens to earn | hány zsetont kaphat / szerezhet még ma Alex; Alex mennyit kaphat még ma | how many tokens can Alex still earn today; how much can Alex still get |
| Tokens to earn, every child | hány zsetont kaphatnak még ma a gyerekek; ki hány zsetont kaphat még ma | how many tokens can the kids still earn today |
| Streak | hány napos Alex sorozata; hány napja hibátlan Alex; hogy áll Alex sorozata | what is Alex's streak; how many perfect days does Alex have |
| Streak, every child | milyen hosszú a sorozat; hogy állnak a sorozatok | what are the streaks; how are the streaks going |

In Hungarian "checkpoint", "csekkpont", "check pont" and "határidő" work in
place of "ellenőrzőpont", "jeton", "pénz", "pont", "érme" and "tallér" in place
of "zseton", "teendő" and "dolga" in place of "feladat". Some common
speech-recognition mistakes are understood too (for example „mennyei” for
„mennyi”).

## LLM agents

Agents that use an LLM (with "Assist" chosen under "Control Home Assistant")
get a read-only tool, *Kis Segítő child status*, when at least one Kis Segítő
entity is exposed to the assistant. The tool answers about one child (by name
or another name) or, without a name, about every child, and gives the LLM all
the data: names and other names, balances, the routine and task now, the tasks
left, the next checkpoint with its time and the minutes until it, the tokens
still to earn now and today, and the streak with its target.

## Sharing with Assist

Each child's Kis Segítő sensor (`sensor.…` with the child's token balance) is
shared with Assist once, when it is created, so the assistant can answer from
the start. To turn this off for a child: **Settings → Voice assistants →
Expose**, and remove the child's sensor. Kis Segítő does not share it again.

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

A Home Assistant asszisztensei (Assist) válaszolnak egy gyerekről vagy
egyszerre mindegyikről. A válaszok csak olvassák a Kis Segítőt: semmit nem
változtatnak, könyvelnek vagy pipálnak.

Amit kérdezni lehet:

- a tárca zsetonjai (és a persely, ha nyitva van);
- van-e most feladata: a futó rutin, a következő feladat és hány van még hátra
  (vagy hogy most nincs feladata);
- mikor van a következő ellenőrzőpont: mennyi idő múlva és hány órakor;
- hány zsetont szerezhet még ma: amennyit a hátralévő ellenőrzőpontok érnek,
  ha most mindent befejez, a mostani jutalomszabályok szerint (és ebből mennyi
  a most futó rutinban);
- a sorozat és a célja.

A gyereket a nevével vagy a gyerekszerkesztőben megadott másik nevével lehet
megnevezni (**Gyerekek → szerkesztés → Más nevek (az Assisthoz)**, vesszővel
elválasztva, például becenév). A kis- és nagybetű, az ékezetek és az írásjelek
nem számítanak, és a nevet ragozva is érti (Alex, Alexnek, Alexnél, Alexé). A
név nélküli kérdésre („kinek mennyi zsetonja van”) minden gyerekről válaszol.

A válaszok felolvasásra készülnek: a számok és az időpontok szóval szerepelnek,
számjegyek és jelek nélkül („negyed óra múlva, fél nyolckor”), így minden
felolvasó (Piper, Home Assistant Cloud és a többi) jól mondja ki őket. Minden
válasznak több megfogalmazása van, hogy ne hangozzon mindig ugyanúgy. Magyar
kérdésre magyarul válaszol, minden más nyelven angolul.

## Melyik ügynök válaszol

| Beállítás | Mi történik |
|---|---|
| Csak a beépített „Home Assistant” ügynök | A lenti mondatokra a Kis Segítő azonnal válaszol. |
| LLM-ügynök, **Helyi parancsok előnyben részesítése** (Prefer handling commands locally) bekapcsolva | A lenti mondatokra továbbra is helyben a Kis Segítő válaszol (gyorsan, LLM nélkül); minden más az LLM-hez kerül, amely használhatja a Kis Segítő eszközét. |
| LLM-ügynök, ugyanez kikapcsolva | Minden kérdés az LLM-hez kerül, amely lekérdezi a Kis Segítő eszközét (*Kis Segítő child status*), és a saját szavaival válaszol. |

Ha a mondatban olyan név van, amelyet a Kis Segítő nem ismer, nem a Kis
Segítő válaszol: a kérdés továbbmegy a többi mondathoz és ügynökhöz, mintha a
Kis Segítő ott sem lenne.

## A beépített ügynök mondatai

A mondatok a fenti táblázatban vannak (magyar oszlop). A „checkpoint”,
„csekkpont”, „check pont” és „határidő” is jó az „ellenőrzőpont” helyett, a
„jeton”, „pénz”, „pont”, „érme” és „tallér” a „zseton” helyett, a „teendő” és a
„dolga” a „feladat” helyett. Néhány gyakori beszédfelismerési hibát is ért
(például „mennyei” a „mennyi” helyett).

## LLM-ügynökök

Az LLM-et használó ügynökök (ha a „Home Assistant vezérlése” alatt az „Assist”
van kiválasztva) kapnak egy csak olvasó eszközt (*Kis Segítő child status*),
ha legalább egy Kis Segítő entitás ki van téve az asszisztensnek. Az eszköz egy
gyerekről (a nevével vagy másik nevével), vagy név nélkül mindegyikről
válaszol, és minden adatot megad az LLM-nek: neveket és más neveket,
egyenlegeket, a mostani rutint és feladatot, a hátralévő feladatokat, a
következő ellenőrzőpontot az idejével és a hátralévő percekkel, a most és a ma
még szerezhető zsetonokat, valamint a sorozatot és a célját.

## Megosztás az Assisttal

Minden gyerek Kis Segítő szenzora (`sensor.…`, a gyerek zsetonegyenlegével)
egyszer, a létrehozásakor meg lesz osztva az Assisttal, hogy az asszisztens
rögtön tudjon válaszolni. Kikapcsolni egy gyereknél: **Beállítások →
Hangasszisztensek → Kitétel**, és vedd ki a gyerek szenzorát. A Kis Segítő nem
osztja meg újra.

A gyerekszenzorok attribútumként is tartalmazzák ugyanezt (lásd a fenti
táblázatot), így egy ügynök a kitett entitásokból is kiolvashatja.
