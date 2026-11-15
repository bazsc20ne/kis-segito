<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Assist

🇬🇧 English version below → [English](#english)

<a id="magyar"></a>

## Magyar

A Home Assistant asszisztensei (Assist) válaszolnak egy gyerekről, egyszerre
mindegyikről vagy arról a gyerekről, aki kérdez. A válaszok csak olvassák a
Kis Segítőt: semmit nem változtatnak, könyvelnek vagy pipálnak.

Amit kérdezni lehet:

- a tárca zsetonjai (és a persely, ha nyitva van);
- a mostani feladat: a futó rutin, a következő feladat és hány van még hátra
  (vagy hogy most nincs feladata, és mikor jön a következő ellenőrzőpont);
- mi van még hátra mára: a futó rutin minden hátralévő feladata;
- mikor van a következő ellenőrzőpont: mennyi idő múlva és hány órakor;
- mikor kezdődik a következő rutin;
- hány zsetont szerezhet még ma: amennyit a hátralévő ellenőrzőpontok érnek,
  ha most mindent befejez, a mostani jutalomszabályok szerint (és ebből mennyi
  a most futó rutinban);
- a sorozat és a célja;
- milyen feladatok vezetnek egy ellenőrzőponthoz („milyen lépések vannak a
  vacsorában”);
- mi van még hátra egy rutinból, minden gyereknek, akié.

A gyereket a nevével vagy a gyerekszerkesztőben megadott másik nevével lehet
megnevezni (**Gyerekek → szerkesztés → Más nevek**, vesszővel
elválasztva, például becenév). A kis- és nagybetű, az ékezetek és az írásjelek
nem számítanak, és a nevet ragozva is érti (Alex, Alexnek, Alexnél, Alexé). A
név nélküli kérdésre („kinek mennyi zsetonja van”, „mi a következő
ellenőrzőpont a gyerekeknek”) minden gyerekről válaszol.

A válaszok felolvasásra készülnek: a számok és az időpontok szóval szerepelnek,
számjegyek és jelek nélkül („negyed óra múlva, fél nyolckor”), így minden
felolvasó (Piper, Home Assistant Cloud és a többi) jól mondja ki őket. Minden
válasznak több megfogalmazása van, ezek közül véletlenszerűen választ, és
kétszer egymás után sosem ugyanazt. A nullának saját megfogalmazása van
(„Alexnek most nincs zsetonja”). Az általad beírt neveket (rutin, feladat,
ellenőrzőpont) pontosan úgy mondja, ahogy beírtad, rag nélkül.

Ha minden gyerekről kérdezel, a válasz rövid: egy mondat, ha mindenkinek
ugyanannyi van („Mindkét gyereknek öt zsetonja van”), egy mondat, ha senkinek
sincs, egyébként pedig egy felsorolás, a legtöbbel kezdve („Alexnek öt
zsetonja van, Arinak kettő és Bogyónak egy sincs”).

Magyar kérdésre magyarul válaszol, minden más nyelven angolul. A kérdés elején
álló töltelékszavak („őőő”, „és”, „hé”, „itt”) nem zavarják.

### Melyik ügynök válaszol

| Beállítás | Mi történik |
|---|---|
| Csak a beépített „Home Assistant” ügynök | A lenti mondatokra a Kis Segítő azonnal válaszol. |
| LLM-ügynök, **Helyi parancsok előnyben részesítése** bekapcsolva | A lenti mondatokra továbbra is helyben a Kis Segítő válaszol (gyorsan, LLM nélkül); minden más az LLM-hez kerül, amely használhatja a Kis Segítő eszközét. |
| LLM-ügynök, **Helyi parancsok előnyben részesítése** kikapcsolva | Minden kérdés az LLM-hez kerül, amely lekérdezi a Kis Segítő eszközét (*Kis Segítő child status*), és a saját szavaival válaszol. |

Ha a mondatban olyan név van, amelyet a Kis Segítő nem ismer, nem a Kis
Segítő válaszol: a kérdés továbbmegy a többi mondathoz és ügynökhöz, mintha a
Kis Segítő ott sem lenne.

### Első személyű kérdések

„Mennyi zsetonom van?”, „Mi a következő feladatom?”: a Kis Segítő annak a
gyereknek válaszol, aki kérdez. Így tudja meg, ki az:

1. **Hangfelismerés (nem kötelező).** Ha a Home Assistantban van olyan
   hangfelismerő integráció, amely megmondja, ki beszélt egy beszélgetésben
   (ezt az `async_get_turn_result(hass, conversation_id, timeout)` függvénnyel
   kínálja), a Kis Segítő először azt kérdezi meg, és a felismert gyereknek
   válaszol (a gyerek neve vagy másik neve alapján). Nélküle is ugyanúgy
   működik.
2. **A hangszóró.** A **Beállítások → Általános → Hangszórók (Assist)**
   részben minden hangszóróhoz vagy egy egész területhez egy vagy több gyerek
   rendelhető. Ha egy gyerek tartozik hozzá, neki válaszol. Ha több,
   mindegyikükről.
3. **Ha senki nem ismert.** Ha van hangfelismerő integráció, de nem ismerte fel
   a hangot, és a hangszóróhoz nincs gyerek rendelve, megkérdezi, ki beszél.
   Az „Alex vagyok” után Alexnek válaszol a kérdésre. Hangfelismerés és
   hozzárendelt hangszóró nélkül minden gyerekről válaszol.

A Kis Segítő egy gyereket sosem talál ki.

### Visszakérdezések

Egy kérdés után körülbelül egy percig, ugyanazon a hangszórón, egy rövid
visszakérdezés ugyanarra a témára vonatkozik: „és nekem?”, „és Alexnek?”, „és a
gyerekeknek?”. Ha a visszakérdezés mennyiséget kérdez („és nekem mennyi?”), és
előtte nem volt kérdés, a zsetonokról válaszol.

### A beépített ügynök mondatai

Egy Alex nevű gyerekkel. A zárójeles szavak elhagyhatók, a perjel jelentése
„vagy”; a legtöbb mondatban a szórend szabad. Ezek példák: minden sornak sok
további változata van.

| | Példamondatok |
|---|---|
| Zsetonok | hány / mennyi zsetonja van Alexnek; Alexnek hány zsetonja van; mennyi pénze / pontja / érméje van Alexnek; Alex egyenlege; van még zsetonja Alexnek |
| Zsetonok, minden gyerek | kinek mennyi zsetonja van; kinek mennyi; mennyi zseton van a gyerekeknek; mennyi zseton van a perselyekben |
| Zsetonok, én | mennyi zsetonom van; nekem mennyi van; mennyi zseton van a perselyemben |
| Feladat | van most feladata Alexnek; mi Alex feladata most; mi a dolga most Alexnek; mit kell most csinálnia Alexnek; mivel tart most Alex; mi következik Alexnél |
| Feladat, minden gyerek | kinek van most feladata; mi a következő feladat a gyerekeknek; mit csinálnak most a gyerekek |
| Feladat, én | mi a feladatom most; mi a következő feladatom; mit kell most csinálnom |
| Mára hátralévő | mi van még hátra Alexnek; hány feladata van még Alexnek; hogy áll Alex a mai feladataival; hogy állnak a gyerekek a feladataikkal; mi van még hátra nekem |
| Ellenőrzőpont | mikor van Alex következő ellenőrzőpontja; mennyi idő van még Alex következő ellenőrzőpontjáig; meddig van még ideje Alexnek |
| Ellenőrzőpont, minden gyerek / én | mi a következő ellenőrzőpont (a gyerekeknek); mennyi idő van a gyerekeknek a következő ellenőrzőpontig; mikor lesz a következő ellenőrzőpontom; mennyi időm van még |
| Következő rutin | mikor kezdődik Alex következő rutinja; mikor indul a következő rutin; mikor kezdődik a következő rutinom |
| Szerezhető zsetonok | hány zsetont kaphat / szerezhet még ma Alex; hány zsetont kaphatnak még ma a gyerekek; hány zsetont kaphatok még ma |
| Sorozat | hány napos Alex sorozata; hány napja hibátlan Alex; hány napos a gyerekek sorozata; hány napos a sorozatom |
| Összefoglaló | hogy áll Alex; hogy állnak a gyerekek; hogy állok |
| Egy ellenőrzőpont feladatai | milyen lépések vannak a vacsorában; mik a vacsora feladatai; mit kell csinálni a vacsora előtt |
| Egy rutin hátralévő feladatai (minden gyereknek, akié) | mennyi van még hátra az esti rutinból; hány feladat van még hátra a reggeliből |
| Visszakérdezések | és nekem?; és Alexnek?; és a gyerekeknek?; Alex vagyok |

A „checkpoint”, „csekkpont”, „check pont” és „határidő” is jó az
„ellenőrzőpont” helyett, a „jeton”, „pénz”, „pont”, „érme” és „tallér” a
„zseton” helyett, a „teendő” és a „dolga” a „feladat” helyett. Néhány gyakori
beszédfelismerési hibát is ért (például „mennyei” a „mennyi”, „se tomje” a
„zsetonja” helyett).

### LLM-ügynökök

Az LLM-et használó ügynökök (ha a „Home Assistant vezérlése” alatt az „Assist”
van kiválasztva) kapnak egy csak olvasó eszközt (*Kis Segítő child status*),
ha legalább egy Kis Segítő entitás ki van téve az asszisztensnek. Az eszköz egy
gyerekről (a nevével vagy másik nevével), név nélkül mindegyikről, első
személyű kérdésnél pedig a hangszóróhoz rendelt gyerekekről válaszol (ha
nincs ilyen, mindegyikről). Minden adatot megad az LLM-nek: neveket és más
neveket, egyenlegeket, a mostani rutint és feladatot, a hátralévő feladatokat,
a következő ellenőrzőpontot és rutint az idejükkel, a most és a ma még
szerezhető zsetonokat, valamint a sorozatot és a célját. Az időpontokat
kimondott formában is megkapja (`next_checkpoint_time_spoken`,
`next_checkpoint_in_spoken`, `next_routine_time_spoken`, például „este
háromnegyed nyolckor”), hogy az LLM úgy mondja ki őket, ahogy vannak.

### Megosztás az Assisttal

Minden gyerek Kis Segítő szenzora (`sensor.…`, a gyerek zsetonegyenlegével)
egyszer, a létrehozásakor meg lesz osztva az Assisttal, hogy az asszisztens
rögtön tudjon válaszolni. Kikapcsolni egy gyereknél: **Beállítások →
Hangasszisztensek → Kitétel**, és vedd ki a gyerek szenzorát. A Kis Segítő nem
osztja meg újra.

A gyerekszenzorok attribútumként is tartalmazzák ugyanezeket az adatokat, így
egy ügynök a kitett entitásokból is kiolvashatja őket:

| Attribútum | Jelentés |
|---|---|
| `piggy_balance`, `piggy_unlocked` | Persely. |
| `task_status` | `task` (most van feladat), `done` (a futó rutin kész) vagy `none` (nincs futó rutin). |
| `current_routine`, `current_task`, `tasks_left` | A futó rutin, a következő feladat, a még hátralévő feladatok. |
| `next_checkpoint`, `next_checkpoint_minutes` | A mai következő ellenőrzőpont és az addig hátralévő percek. |
| `next_routine`, `next_routine_time` | A mai következő, még el nem kezdődött rutin, és mikor kezdődik. |
| `tokens_earnable_now`, `tokens_earnable_today` | A futó rutinban és a ma még szerezhető zsetonok. |
| `streak`, `streak_target` | A sorozat és a célja. |

### Új nyelv

A mondatok és a válaszok a
`custom_components/kis_segito/assist_translations/<language>.json` fájlokban
vannak. Egy új nyelvhez elég egy új fájl, ugyanazokkal a részekkel, mint az
`en.json`: `prefix` (töltelékszavak), `words`, `sentences` (hatókör szerint:
`child`, `all`, `speaker`, `followup`, `routine`, `checkpoint`), `nouns`,
`lists`, `groups` és `answers` (hatókör, téma és eset szerint, mindegyik több
megfogalmazással). Ha a Kis Segítőben nincs saját nyelvtana, a nyelv a
számokat és az időpontokat számjeggyel mondja.

A válaszokban a `{name}` a gyerek neve, a `{routine}`, a `{task}` és a `{cp}`
az általad beírt nevek, a `{cp_clock}` és a `{cp_in}` a következő
ellenőrzőpont időpontja és az, hogy mennyi idő van addig, a `{start_clock}` és
a `{start_in}` ugyanez a következő rutinra, a `{tasks_list}` pedig a még
hátralévő feladatok. A számok kettőspont után főnevet kapnak a `nouns` részből:
a `{wallet:token}` azt mondja, hogy „öt zseton”, a `{wallet:num}` csak a
számot.

---

<a id="english"></a>

## English

🇭🇺 [Magyar változat](#magyar)

Home Assistant's assistants (Assist) can answer questions about a child,
about every child at once, or about the child who is asking. The answers only
read Little Helper: nothing is changed, booked or ticked.

What can be asked:

- tokens in the wallet (and the piggy bank, when it is unlocked);
- the task now: the routine running, the next task and how many are left (or
  that there is no task right now, and when the next checkpoint is);
- what is still left today: every task still to do in the routine running;
- when the next checkpoint is: how long until it and at what time;
- when the next routine starts;
- the tokens still to earn today: what the remaining checkpoints are worth if
  everything is finished now, under the current reward rules (and how much of
  it is in the routine running now);
- the streak and its target;
- which tasks lead to a checkpoint ("what are the steps of dinner");
- what is left of a routine, for every child it is for.

The child is named by name, or by another name given in the child editor
(**Children → edit → Other names**, comma separated, for example
a nickname). Upper and lower case, accents and punctuation do not matter. In
Hungarian the name is understood with its case endings too. A question without
a name ("how many tokens do the kids have", "what's the next checkpoint for
the kids") is answered for every child.

The answers are written to be spoken: numbers and times are words, without
digits or symbols ("in a quarter of an hour, at half past seven"), so every
text-to-speech voice (Piper, Home Assistant Cloud, others) reads them right.
Each answer has a few wordings, picked at random and never the same one twice
in a row. Zero has its own wording ("Alex has no tokens right now"). Names you
typed (routines, tasks, checkpoints) are said exactly as typed, never with an
ending glued on.

For every child at once, the answer is short: one sentence when every child
has the same (for example "Both kids have five tokens"), one sentence when
nobody has any, and otherwise a list, largest first ("Alex has five tokens,
Ari has two and Bogyó has none").

Hungarian questions get Hungarian answers; every other language gets English
answers. Filler words at the start of a question ("um", "so", "hey") are fine.

### Which agent answers

| Setup | What happens |
|---|---|
| Only the built-in "Home Assistant" agent | The sentences below are answered by Little Helper right away. |
| LLM agent, **Prefer handling commands locally** on | The sentences below are still answered locally by Little Helper (fast, no LLM needed); everything else goes to the LLM, which can use Little Helper's tool. |
| LLM agent, **Prefer handling commands locally** off | Every question goes to the LLM, which asks Little Helper's tool (*Kis Segítő child status*) and answers in its own words. |

A sentence with a name Little Helper does not know is not answered by Little
Helper: it goes on to the other sentences and agents as if Little Helper were
not there.

### Questions in the first person

"How many tokens do I have?", "What's my next task?": Little Helper answers
for the child who is asking. It finds out who that is like this:

1. **Speaker recognition (optional).** When Home Assistant has a speaker
   recognition integration that tells who spoke in a conversation (it offers
   `async_get_turn_result(hass, conversation_id, timeout)`), Little Helper
   asks it first and answers for the child it recognised (by the child's name
   or another name). Little Helper works the same without one.
2. **The voice satellite.** In **Settings → General → Voice satellites
   (Assist)** each voice satellite, or a whole area, can be given one or more
   children. With one child, the answer is for that child. With several, it
   answers for each of them.
3. **Nobody known.** If a speaker recognition integration is installed but did
   not recognise the voice, and the satellite has no children, it asks who is
   speaking. "I'm Alex" then answers the question for Alex. Without speaker
   recognition and without an assigned satellite, it answers for every child.

Little Helper never guesses one child.

### Follow-ups

For about a minute after a question, on the same voice satellite, a short
follow-up reuses its topic: "and me?", "and Alex?", "what about the kids?". A
follow-up that asks how many ("and how many do I have?") asks about tokens
when there was no question before.

### Sentences the built-in agent understands

With a child called Alex. The words in brackets are optional, a slash means
"or". These are examples: each line has many more forms.

| | Example sentences |
|---|---|
| Tokens | how many tokens / coins / points does Alex have; how many coins has Alex got; what's Alex's balance; Alex's wallet |
| Tokens, every child | how many tokens do the kids have; how many tokens does everyone have; who has how many coins |
| Tokens, me | how many tokens do I have; what's my balance |
| Task | does Alex have a task now; what's Alex's task; what should Alex be doing now; what does Alex have to do now; what's next for Alex |
| Task, every child | does anyone have a task now; what is next for the kids |
| Task, me | what's my next task; what should I do now |
| Left today | what's left for Alex today; how many tasks does Alex have left; how are the kids doing with their tasks; what do I still have to do today |
| Checkpoint | when is Alex's next checkpoint; how long until Alex's next checkpoint; how much time does Alex have left |
| Checkpoint, every child / me | what's the next checkpoint (for the kids); how long until the next checkpoint; when is my next checkpoint; how much time do I have left |
| Next routine | when does Alex's next routine start; when does the next routine start; what's my next routine |
| Tokens to earn | how many tokens can Alex still earn today; how many tokens can the kids still earn today; how many tokens can I still earn today |
| Streak | what is Alex's streak; how are the streaks going; how long is my streak |
| Summary | how is Alex doing; how are the kids doing; how am I doing |
| A checkpoint's tasks | what are the steps of dinner; what's in dinner; what do the kids have to do before dinner |
| Tasks left in a routine (every child it is for) | how many tasks are left in the evening routine; how much is left of the morning routine |
| Follow-ups | and me?; what about Alex?; and the kids?; I'm Alex |

Hungarian sentences also accept a few synonyms for "checkpoint", "token" and
"task", and some common speech-recognition mistakes are understood too.

### LLM agents

Agents that use an LLM (with "Assist" chosen under "Control Home Assistant")
get a read-only tool, *Kis Segítő child status*, when at least one Little
Helper entity is exposed to the assistant. The tool answers about one child
(by name or another name), without a name about every child, or, for a
question in the first person, about the children of the voice satellite
(every child when it has none). It gives the LLM all the data: names and other
names, balances, the routine and task now, the tasks left, the next checkpoint
and the next routine with their times, the tokens still to earn now and today,
and the streak with its target. Times also come already in spoken form
(`next_checkpoint_time_spoken`, `next_checkpoint_in_spoken`,
`next_routine_time_spoken`, for example "at quarter to eight in the evening"),
so the LLM can say them as they are.

### Sharing with Assist

Each child's Little Helper sensor (`sensor.…` with the child's token balance)
is shared with Assist once, when it is created, so the assistant can answer
from the start. To turn this off for a child: **Settings → Voice assistants →
Expose**, and remove the child's sensor. Little Helper does not share it
again.

The child sensors carry the same data as attributes, so an agent can also read
them from the exposed entities:

| Attribute | Meaning |
|---|---|
| `piggy_balance`, `piggy_unlocked` | Piggy bank. |
| `task_status` | `task` (there is a task now), `done` (the routine running is finished) or `none` (no routine running). |
| `current_routine`, `current_task`, `tasks_left` | The routine running, the next task, the tasks still to do. |
| `next_checkpoint`, `next_checkpoint_minutes` | The next checkpoint today and the minutes until it. |
| `next_routine`, `next_routine_time` | The next routine today that has not started yet, and when it starts. |
| `tokens_earnable_now`, `tokens_earnable_today` | Tokens still to earn in the routine running and today. |
| `streak`, `streak_target` | Streak and its target. |

### Another language

The sentences and answers are in
`custom_components/kis_segito/assist_translations/<language>.json`. A new
language needs only a new file with the same parts as `en.json`: `prefix`
(filler words), `words`, `sentences` (by scope: `child`, `all`, `speaker`,
`followup`, `routine`, `checkpoint`), `nouns`, `lists`, `groups` and `answers`
(by scope, topic and case, each with a few wordings). Without a grammar of its
own in Little Helper, a language says numbers and times as digits.

In the answers, `{name}` is the child's name, `{routine}`, `{task}` and `{cp}`
the names you typed, `{cp_clock}` and `{cp_in}` the next checkpoint's time and
how long until it, `{start_clock}` and `{start_in}` the same for the next
routine, `{tasks_list}` the tasks still left. Numbers take a noun from `nouns`
after a colon: `{wallet:token}` says "five tokens", `{wallet:num}` the number
alone.
