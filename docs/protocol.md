<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# A gomb protokollja (1. séma) / Knob protocol (schema 1)

🇬🇧 English version below → [English](#english)

<a id="magyar"></a>

## Magyar

Hogyan beszél egymással az integráció és a gomb – annak, aki saját gombot vagy
kijelzőt szeretne építeni a Kis Segítőre. Kizárólag az ESPHome natív API-n
keresztül kommunikálnak.

### Home Assistant → gomb

A firmware API-műveletei (`esphome/kis-segito-core.yaml`), amelyeket az
integráció `esphome.<node>_<action>` néven hív:

| Művelet | Változók | Cél |
|---|---|---|
| `set_ui_strings` | `language`, `keys[]`, `values[]` | A képernyő szövegei a választott nyelven. A betöltési szöveget és a nyelvet a flash tárolja. |
| `set_state` | `data` (JSON-szöveg) | Adatpillanatkép, minden változáskor és (újra)csatlakozás után elküldve. |
| `set_sensor` | `kind`, `value` | Egy Home Assistant-entitásból továbbított érzékelőbemenet (panel → Beállítások → Gombok → Érzékelők a Home Assistantból): `presence` (1 vagy 0), `distance` (cm, negatív = senki) vagy `illuminance` (lx). Minden változáskor és (újra)csatlakozás után elküldve. |

Műveletek automatizálásokhoz (maga az integráció nem használja őket), lásd
[automations.md](automations.md):

| Művelet | Változók | Cél |
|---|---|---|
| `wake` | – | Lágy beúszással felébreszti a képernyőt, mint a gomb elforgatása. |
| `screensaver` | `enable` | Elindítja (`true`) vagy befejezi (`false`) a képernyővédőt. |
| `night_light` | `enable`, `brightness`, `kelvin` | Megjeleníti (`true`) vagy befejezi (`false`) az éjszakai fényt; `brightness` százalékban és `kelvin` (színhőmérséklet, 1500–6500); a 0 a panel beállításait használja. |

A `set_state` JSON-ja (rövid kulcsokkal, hogy a gomb kevés memóriát használjon;
az időpontok Unix epoch másodpercek, a színek `#RRGGBB`):

```json
{
  "v": 1,
  "now": 1791360000,
  "lang": "hu",
  "bg": "bg_2",
  "bgs": 3,
  "scr": {"saver": 0, "dim": 60, "lvl": 15, "blank": 0, "off": 120, "ss": "balls"},
  "sen": {"pw": true, "ps": true, "nl": true, "nlx": 5.0, "nb": 30, "nk": 2700,
          "noff": 60, "near": 80, "amb": true, "amin": 10, "amax": 100, "lf": 1.0},
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
     "m": 1791357300,
     "ch": [], "base": "#6BCB77", "z": [[900, "#FF9F43"], [300, "#FF6B6B"]],
     "cp": [{"id": "…", "i": "task_door_ready", "t": 1791355500, "ch": [],
             "b": [[600, 3], [0, 2]]}],
     "t": [{"id": "…", "i": "task_clothes", "cp": "…"}],
     "done": {"<child id>": ["<task id>"]},
     "cpd": {"<child id>": ["<checkpoint id>"]}}
  ]
}
```

- `children[].ai`, `rewards[].ii`: egy feltöltött kép azonosítója (üres: az
  ikon kell). Egy gyerek `ai` mezője sosem üres: egy feltöltött fénykép, vagy
  az avatar abban a témában, amelyből választották (`t_<theme>__avatar_<nn>`,
  a beépített megjelenésnél `t_kis_segito__…`), így egy témaváltás sosem
  változtatja meg. A gomb az `img.u` +
  `/api/kis_segito/knob_image/<id>/<size>` címről tölti le, a saját `img.t`
  titkával az `X-Kis-Segito-Token` kérésfejlécben (sosem az URL-ben). A válasz
  nyers RGB565A8 `KSI1` fejléccel; amíg meg nem érkezik, a gomb az ikont
  mutatja. A Home Assistantnek a belső URL-jén sima HTTP-n elérhetőnek kell
  lennie; a végpont csak a helyi hálózatról érkező kérésekre válaszol (Home
  Assistant Cloudon keresztül nem). Az `img` üres (`u` és `t` értéke `""`),
  amíg a gomb API-kapcsolata nincs titkosítva. Egy új kulcs (panel →
  Beállítások → Gombok) azonnal felváltja a régit; a gomb a következő
  pillanatképben kapja meg.
- `scr`: ennek a gombnak a képernyő-energiakezelése: tétlen másodpercek a
  képernyővédőig, a halványításig, a rajzolás kikapcsolásáig (fekete, LVGL
  szüneteltetve) és a háttérvilágítás kikapcsolásáig (0 = soha); `lvl` a
  halványított fényerő százalékban, `ss` a képernyővédő (`balls`, `confetti`
  vagy `stars`).
- `sen`: ennek a gombnak az érzékelővezérelt viselkedése (panel → Beállítások →
  Érzékelők). `pw`: jelenlétre felébred a képernyő; `ps`: az `scr` szakaszai
  attól számítanak, amikor utoljára volt valaki a közelben (nem csak az utolsó
  bevitel óta); `nl`: éjszakai fény `nlx` lx alatt (1,5 × `nlx` + 1 lx felett
  újra világos), `nb` százalékon és `nk` kelvinen, a jelenlét megszűnése után
  `noff` másodperccel ér véget; `near`: a gyerekfelület csak ennyi cm-nél
  közelebbről; `amb`: a háttérvilágítás a szoba fényét követi `amin` és `amax`
  százalék között; `lf`: fénykorrekció, a gomb a mért megvilágítás ezzel a
  szorzóval vett értékét használja. Mindegyik csak akkor működik, ha a gomb
  megkapja a hozzá tartozó bemenetet (lásd [sensors.md](sensors.md)).
- `bg`: minden képernyő háttere: `""` (nincs), egy beépített előbeállítás
  (`bg_1` … `bg_6`), egy téma előbeállítása (`t_<theme>__bg_<n>`) vagy egy
  feltöltött kép azonosítója. A gomb úgy tölti le, mint egy képet, a
  képernyője méretében (240, 360, 466 vagy 480), `KSI2` formában (RGB565 alfa
  nélkül, a teljes képernyő).
- `bgs`: a háttérváltásokat számolja. Ha a gomb működése közben a `bg` vagy a
  `bgs` megváltozik, a gomb az új hátteret a flash-gyorsítótárába menti, és 1
  perc bevitel nélküli idő után újraindul, onnantól azt mutatja.
- `children[].pi`: kifizetett, de a gyereknek még meg nem mutatott perselykamat;
  a gomb jelvényt mutat, és lejátssza, amikor a perselyt kinyitják.
- `children[].sel`: használható-e a gyerek ezen a gombon (a gombnál bepipálva a
  Beállítások → Gombok részen); a többiek zárolva látszanak. Az a gomb, amelyen
  a többiek elrejtése be van állítva, csak a saját gyerekeit kapja meg.
- `bg`, `bgs`: ennek a gombnak a háttere (a sajátja vagy a közös).
- A rutinok, feladatok és jutalmak ikonjai (`routine_…`, `task_…`, `reward_…`)
  nem részei a firmware-nek: a gomb úgy tölti le őket, mint egy képet, abban a
  méretben, amelyben megjeleníti őket (legfeljebb 240-es méretig)
  (`knob_image/<icon>/<size>`).
- Minden képválasz `ETag`-et hordoz. A gomb a képeket a flash-gyorsítótárában
  tárolja, és minden indulás után egyszer `If-None-Match`-csel újra
  rákérdez; a változatlan képre `304 Not Modified` a válasz.
- `children[].a`: a beépített avatarok (`avatar_01` … `avatar_12`) nem részei
  a firmware-nek; a gomb úgy tölti le őket, mint egy képet, 180-as méretben (a
  képernyővel arányosan: 180 × képernyőméret / 480).
- `children[].a`, `rewards[].i`, `routines[].i`, `cp[].i`, `t[].i`: a közös
  ikonkészlet ikonazonosítói (az `assets/device/` fájlnevei a méret nélkül).
- `routines`: a gombokon megjelenő mai rutinok. Üres `ch` = minden gyerek.
- `m`: a rutin a gomb funkciómenüjében `s`-től `m`-ig érhető el. Amíg a rutin
  valamelyik gyerekének van még nyitott feladata, `m` a vége, vagy ha az
  későbbi, az utolsó pillanat, amikor az utolsó ellenőrzőpont még fizet késve
  (negatív küszöbű sáv), plusz a `routine_menu_grace_s` beállítás (panel →
  Beállítások, alapértelmezés 30 perc). Ha minden gyerek minden feladatot
  befejezett, `m` egyenlő `e`-vel. `m` nélkül a gomb az `e`-t használja.
- `z`: színzónák, mindegyik `offset` másodperccel az `e` vége előtt kezdődik.
- `cp`: ellenőrzőpontok; üres `ch` = közös (külső sáv), egyébként a gyerekek
  sajátja (belső sáv). `b`: jutalomsávok `[másodperccel korábban, zseton]`;
  a legjobban illeszkedő sáv számít, késésnél 0.
- `t[].cp`: az ellenőrzőpont, amelyhez a feladat vezet; az összes hozzá tartozó
  feladat befejezésével érhető el.

A gomb az aktuális időt `now` + a pillanatkép megérkezése óta eltelt idő
alapján számolja, így a sáv további üzenetek nélkül is halad.

### Gomb → Home Assistant

A gomb minden gyerekműveletet JSON-ként tesz közzé az **Action** szöveges
érzékelőjén. Minden műveletnek egyedi `id`-je van; az integráció minden
azonosítót csak egyszer hajt végre, és a feldolgozott azonosítókat 7 napig
őrzi (legfeljebb 2000-et), így az újrapróbálkozások sosem könyvelnek kétszer
zsetont.

A Home Assistant csak a szabályos műveleteket fogadja el: legfeljebb 255 bájt
JSON, pontosan az alább felsorolt mezők (mások nem), 1–64 betűből, számjegyből
vagy `_ . : -` jelből álló azonosítók, és `n` nem nulla egész szám ±100000-en
belül. Gombonként legfeljebb percenként 20 művelet küldhető; minden mást
figyelmen kívül hagy és naplóz.

| `a` | Mezők | Jelentés |
|---|---|---|
| `task` | `c` gyerek, `r` rutin, `t` feladat | A mai rutin egy feladata kész. |
| `redeem` | `c` gyerek, `r` jutalom | A gyerek megvett egy jutalmat. |
| `piggy` | `c` gyerek, `n` összeg (+ befizetés, − kivétel) | Perselyátutalás. |
| `seen` | `c` gyerek | A gyerek kinyitotta a perselyt; a függő kamatot megmutatta. |

A gomb azonnal mutatja az eredményt; a Home Assistant ellenőrzi és könyveli,
majd új pillanatképet küld, amely kijavítja a gombot, ha a műveletet
elutasította (például: nincs elég zseton). Home Assistant-kapcsolat nélkül a
gomb elutasítja a zsetontranzakciókat.

### Virtuális gomb

A virtuális gomb kártya (`custom_components/kis_segito/frontend/kis-segito-knob-card.js`)
egy ESPHome nélküli gomb. A Home Assistant WebSocket API-n keresztül beszél az
integrációval, ugyanazokkal az adatokkal:

| Parancs | Mezők | Cél |
|---|---|---|
| `kis_segito/virtual/subscribe` | `device_id` | A fenti pillanatkép (az `img` képkulcsa nélkül), most és minden változás után elküldve, `static_url`, `version`, `small_icons` mezőkkel. |
| `kis_segito/virtual/action` | `device_id`, `action` (JSON-szöveg) | Egy művelet, mint a „Gomb → Home Assistant” részben: ugyanazok a mezők, korlátok és egyszer használható azonosítók. Csak olyan gyereknek, aki ezen a virtuális gombon kiválasztható. |
| `kis_segito/virtual/list` | – | A virtuális gombok (`id`, `name`). |
| `kis_segito/virtual/save`, `kis_segito/virtual/delete` | `device_id`, `name` | Létrehozás, átnevezés, törlés (csak rendszergazdáknak). |

A képek az integráció statikus fájljaiból (ikonok, hátterek) és a Home
Assistant képfeltöltéséből (`/api/image/serve/<id>/<size>`) érkeznek.

---

<a id="english"></a>

## English

🇭🇺 [Magyar változat](#magyar)

How the integration and the knob talk to each other, for anyone who wants to
build their own knob or display on top of Little Helper. They talk only through the
ESPHome native API.

### Home Assistant → knob

API actions of the firmware (`esphome/kis-segito-core.yaml`), called by the
integration as `esphome.<node>_<action>`:

| Action | Variables | Purpose |
|---|---|---|
| `set_ui_strings` | `language`, `keys[]`, `values[]` | On-screen texts in the chosen language. The loading text and the language are kept in flash. |
| `set_state` | `data` (JSON string) | Data snapshot, sent on every change and after (re)connecting. |
| `set_sensor` | `kind`, `value` | A sensor input forwarded from a Home Assistant entity (panel → Settings → Knobs → Sensors from Home Assistant): `presence` (1 or 0), `distance` (cm, negative = nobody) or `illuminance` (lx). Sent on every change and after (re)connecting. |

Actions for automations (not used by the integration itself), see
[automations.md](automations.md):

| Action | Variables | Purpose |
|---|---|---|
| `wake` | – | Wakes the screen with a soft fade-in, like a turn of the knob. |
| `screensaver` | `enable` | Starts (`true`) or ends (`false`) the screensaver. |
| `night_light` | `enable`, `brightness`, `kelvin` | Shows (`true`) or ends (`false`) the night light; `brightness` in percent and `kelvin` (colour temperature, 1500–6500); 0 uses the panel settings. |

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
  "sen": {"pw": true, "ps": true, "nl": true, "nlx": 5.0, "nb": 30, "nk": 2700,
          "noff": 60, "near": 80, "amb": true, "amin": 10, "amax": 100, "lf": 1.0},
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
     "m": 1791357300,
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
  icon). A child's `ai` is never empty: an uploaded photo, or the avatar in
  the theme it was chosen from (`t_<theme>__avatar_<nn>`, `t_kis_segito__…`
  for the built-in look), so a theme change never changes it. The knob downloads it from `img.u` +
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
- `sen`: sensor-driven behaviour of this knob (panel → Settings → Sensors).
  `pw`: presence wakes the screen; `ps`: the `scr` stages count from when
  someone was last near (not only from the last input); `nl`: night light
  below `nlx` lx (light again above 1.5 × `nlx` + 1 lx), at `nb` percent and
  `nk` kelvin, ending `noff` seconds after presence ended; `near`: the child
  UI only closer than this many cm; `amb`: the backlight follows the room
  light between `amin` and `amax` percent; `lf`: light correction, the knob
  uses the measured illuminance times this factor. Each works only when the knob gets
  the matching input (see [sensors.md](sensors.md)).
- `bg`: background of every screen: `""` (none), a built-in preset
  (`bg_1` … `bg_6`), a theme's preset (`t_<theme>__bg_<n>`) or an uploaded
  picture id. The knob
  downloads it like a picture, at the size of its screen (240, 360, 466 or
  480), as `KSI2` (RGB565 without alpha, the whole screen).
- `bgs`: counts the background changes. When `bg` or
  `bgs` changes while the knob runs, it stores the new background in its flash
  cache and restarts after 1 minute without input, then shows it from there.
- `children[].pi`: piggy-bank interest paid but not shown to the child yet; the
  knob shows a badge and plays it when the piggy bank is opened.
- `children[].sel`: whether the child can be used on this knob (ticked at
  the knob on Settings → Knobs); others are shown locked. A knob set to hide
  the others gets only its own children.
- `bg`, `bgs`: this knob's background (its own, or the common one).
- Icons of routines, tasks and rewards (`routine_…`, `task_…`, `reward_…`) are
  not part of the firmware: the knob downloads them like a picture, at the size
  it shows them (sizes up to 240) (`knob_image/<icon>/<size>`).
- Every picture answer carries an `ETag`. The knob stores the pictures in its
  flash cache and, once after each start, asks again with `If-None-Match`; an
  unchanged picture is answered with `304 Not Modified`.
- `children[].a`: the built-in avatars `avatar_01` … `avatar_12` are not part of
  the firmware; the knob downloads them like a picture, at size 180 (scaled
  with the screen: 180 × screen size / 480).
- `children[].a`, `rewards[].i`, `routines[].i`, `cp[].i`, `t[].i`: icon ids of
  the shared icon set (the file names in `assets/device/` without the size).
- `routines`: today's routines shown on knobs. `ch` empty = every child.
- `m`: the routine is offered in the knob's functions menu from `s` until
  `m`. While a task is still open for a child of the routine, `m` is the
  end, or the last moment the last checkpoint still pays late (a band with a
  negative threshold) if that is later, plus the `routine_menu_grace_s`
  setting (panel → Settings, default 30 minutes). Once every child has
  finished every task, `m` equals `e`. Without `m` the knob uses `e`.
- `z`: colour zones, each starting `offset` seconds before the end `e`.
- `cp`: checkpoints; `ch` empty = shared (outer track), otherwise the
  children's own (inner track). `b`: reward bands `[seconds early, tokens]`;
  the best matching band counts, late = 0.
- `t[].cp`: the checkpoint a task leads to; finishing all its tasks reaches it.

The knob computes the current time as `now` + the time since the snapshot
arrived, so the track moves without further messages.

### Knob → Home Assistant

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

### Virtual knob

The virtual knob card (`custom_components/kis_segito/frontend/kis-segito-knob-card.js`)
is a knob without ESPHome. It talks to the integration over the Home Assistant
WebSocket API with the same data:

| Command | Fields | Purpose |
|---|---|---|
| `kis_segito/virtual/subscribe` | `device_id` | The snapshot above (without `img`'s picture key), sent now and after every change, with `static_url`, `version`, `small_icons`. |
| `kis_segito/virtual/action` | `device_id`, `action` (JSON string) | One action as in "Knob → Home Assistant": the same fields, limits and once-only ids. Only for a child selectable on this virtual knob. |
| `kis_segito/virtual/list` | – | The virtual knobs (`id`, `name`). |
| `kis_segito/virtual/save`, `kis_segito/virtual/delete` | `device_id`, `name` | Create, rename, remove (administrators only). |

Pictures come from the integration's static files (icons, backgrounds) and Home
Assistant's image upload (`/api/image/serve/<id>/<size>`).
