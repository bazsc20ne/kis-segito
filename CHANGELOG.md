# Changelog

All notable changes to this project are documented here, in English and Hungarian.
The format follows [Keep a Changelog](https://keepachangelog.com/) and the project
uses [Semantic Versioning](https://semver.org/).

Minden lényeges változás itt szerepel, angolul és magyarul.

## [0.7.28] - 2026-10-10

### English

- Button: the press that goes straight back to the child selector is now
  three times as long as a long press (1.2 s with the default 400 ms, was
  0.8 s). The long press itself is unchanged.

### Magyar

- Gomb: a gyerekválasztóhoz egyenesen visszavivő nyomás most a hosszú nyomás
  háromszorosa (az alapértelmezett 400 ms-mal 1,2 mp, eddig 0,8 mp). Maga a
  hosszú nyomás nem változott.

## [0.7.27] - 2026-10-10

### English

- Less picture memory, less breaking up: downloaded pictures the new screen
  does not show are freed as soon as another screen opens (they come back
  from the flash cache when needed); while a screen is open at most 256 KB of
  unused pictures are kept (was 1 MB). Leaving the shop also frees its drawn
  items. A downloaded picture is no longer held once its item has been drawn.

### Magyar

- Kevesebb képmemória, kevesebb feldarabolódás: az új képernyőn nem látható
  letöltött képek egy másik képernyő megnyitásakor azonnal felszabadulnak
  (szükség esetén a flash-tárból jönnek vissza); egy képernyőn belül legfeljebb
  256 KB nem használt kép marad meg (eddig 1 MB). A bolt elhagyása a
  megrajzolt bolti elemeket is felszabadítja. Egy letöltött képet a gomb nem
  tart meg, ha az eleme már megrajzolódott.

## [0.7.26] - 2026-10-10

### English

- Routine templates keep the children: a template is saved with the
  routine's children (also those of its checkpoints), and filling a routine
  from it brings them back. A template saved earlier without children keeps
  the children chosen in the form.
- Stripes and steps on the track after opening the shop (#37), most likely
  cause: once the picture memory was broken up, every small picture the shop loaded counted as
  "not fitting" because a large fixed reserve was kept free besides it, and
  the knob kept freeing and reloading pictures, which disturbed the display.
  The reserve now depends on the picture's size, so small pictures fit. The
  knob logs when it has to make room for a picture.

### Magyar

- A rutinsablonok megtartják a gyerekeket: a sablon a rutin gyerekeivel (a
  checkpointjaiéval is) együtt mentődik, és a belőle kitöltött rutin
  visszakapja őket. Egy korábban gyerekek nélkül mentett sablon az űrlapon
  kiválasztott gyerekeket hagyja meg.
- Csíkok és lépcsők a pályán a bolt megnyitása után (#37), a legvalószínűbb
  ok: feldarabolódott képmemóriánál a bolt minden kis képe „nem fért el”, mert mellette egy nagy,
  rögzített tartalékot is szabadon kellett hagyni, és a gomb újra és újra
  felszabadított és újratöltött képeket, ami megzavarta a kijelzőt. A
  tartalék most a kép méretétől függ, így a kis képek elférnek. A gomb
  naplózza, amikor helyet kell csinálnia egy képnek.

## [0.7.25] - 2026-10-10

### English

- Background: choosing **no background** takes effect at once, without a
  restart; the old picture's memory is freed. A change to a picture still
  restarts each knob once, after 1 minute without use.
- Knob menu: a routine is shown only while it is running; with no routine
  running, the shop is the first item.
- Button: holding the press twice as long as a long press goes straight back
  to the child selector from anywhere in the menu (after the long press has
  stepped back one level).
- Panel: the avatars in the children list are twice as big, like on the
  child's page; the pencil and the red X there sit on a white circle with a
  thin border in the child's colour.
- Routine templates: filling a routine from a template keeps the children
  chosen in the form.
- Diagnostics: the knob logs its free memory every 10 minutes and when a new
  uploaded picture (photo, background) is loaded (picture memory and the
  memory the display transfer uses).

### Magyar

- Háttér: a **nincs háttér** választás azonnal érvényes, újraindulás nélkül;
  a régi kép memóriája felszabadul. Képre cserélésnél továbbra is minden gomb
  egyszer újraindul, 1 perc használaton kívüli idő után.
- A gomb menüje: egy rutin csak akkor látszik, amikor éppen fut; ha nem fut
  rutin, a bolt az első elem.
- Gomb: a hosszú nyomásnál kétszer hosszabb nyomás a menü bármely pontjáról
  egyenesen a gyerekválasztóhoz visz (miután a hosszú nyomás egy szintet
  visszalépett).
- Panel: a gyereklistában az avatarok kétszer akkorák, mint a gyerek
  oldalán; ott a ceruza és a piros X fehér körön ül, vékony, a gyerek
  színével megegyező szegéllyel.
- Rutinsablonok: sablonból kitöltéskor az űrlapon kiválasztott gyerekek
  megmaradnak.
- Diagnosztika: a gomb 10 percenként és minden új feltöltött kép (fénykép,
  háttér) betöltésekor naplózza a szabad memóriáját (a képmemóriát és a
  kijelző adatátviteléhez használt memóriát).

## [0.7.24] - 2026-10-10

### English

- New artwork for all rewards (toy car, doll, bricks, long story, extra
  story, choose a game, treat, family activity), for the green check (also its
  small version on the knob) and for the completed day of the streak; the old
  drawings are gone everywhere.
- Icons: rewards, tasks, routines and checkpoints offer the same pictures:
  every reward, task and routine picture can be chosen for any of them.
- Background: choosing the background that is already active again does
  nothing (no download, no restart). A real change still restarts each knob
  once, after 1 minute without use.
- Child photo: a picture with a transparent background stays transparent
  (uploaded as PNG). Framing can be skipped: **Upload without framing**
  uploads the picture as it is.
- Child form: the picture is about twice as big; a small pencil (change) sits
  in its lower left corner and, with a photo, a small red X (remove) in the
  lower right corner.
- Routine templates: a new routine and a routine changed for one day (in the
  calendar) can be filled from a saved template at the top of the form; a day
  keeps its children.

### Magyar

- Új rajz minden jutalomhoz (kisautó, baba, kockák, hosszú mese, extra mese,
  társasjáték választása, nasi, családi program), a zöld pipához (a gombon a
  kis változata is) és a sorozat teljesített napjához; a régi rajzok
  mindenhonnan kikerültek.
- Ikonok: a jutalmak, a feladatok, a rutinok és a checkpointok ugyanazokat a
  képeket kínálják: minden jutalom-, feladat- és rutinkép bármelyikhez
  választható.
- Háttér: a már aktív háttér újbóli kiválasztása nem csinál semmit (nincs
  letöltés, nincs újraindulás). Valódi cserénél továbbra is minden gomb
  egyszer újraindul, 1 perc használaton kívüli idő után.
- Gyerek fényképe: az átlátszó hátterű kép átlátszó marad (PNG-ként töltődik
  fel). A kivágás kihagyható: a **Feltöltés kivágás nélkül** a képet úgy
  tölti fel, ahogy van.
- Gyerek szerkesztőlapja: a kép kb. kétszer akkora; bal alsó sarkában egy kis
  ceruza (módosítás), fénykép esetén a jobb alsó sarkában egy kis piros X
  (törlés).
- Rutinsablonok: új rutin és a naptárban egy napra módosított rutin az űrlap
  tetején mentett sablonból tölthető ki; a nap megtartja a gyerekeit.

## [0.7.23] - 2026-10-10

### English

- Background change: after every background change each knob restarts once,
  also when the same picture is chosen again. It first stores the new
  picture in its flash cache and restarts only after it has not been used for
  1 minute (no turn, no press), so it never restarts in the middle of use. If
  the picture cannot be stored (e.g. no network), it does not restart.
- New action `kis_segito.set_background` to change the background from
  automations (for example a night background at sunset), with the same
  restart rule; see docs/automations.md.
- Settings: all times (back to the child selector, screensaver, dimming,
  drawing off, backlight off, also per knob) are set in minutes. The values
  already set are kept and shown in minutes.

### Magyar

- Háttércsere: minden háttércsere után minden gomb egyszer újraindul, akkor
  is, ha ugyanazt a képet választod újra. Előbb a flash-tárába menti az új
  képet, és csak akkor indul újra, ha 1 percig nem használták (se tekerés, se
  nyomás), így használat közben sosem. Ha a képet nem sikerül elmenteni (pl.
  nincs hálózat), nem indul újra.
- Új `kis_segito.set_background` művelet, amellyel automatizálásból lehet
  hátteret váltani (például napnyugtakor éjszakai háttérre), ugyanezzel az
  újraindítási szabállyal; lásd docs/automations.md.
- Beállítások: minden időérték (vissza a gyerekválasztóhoz, képernyővédő,
  halványítás, rajzolás leállítása, háttérvilágítás kikapcsolása, gombonként
  is) percben állítható. A már beállított értékek megmaradnak, percben
  jelennek meg.

## [0.7.22] - 2026-10-10

### English

- Child picture: one field shows the child's photo or avatar. A click on it
  or on the pencil opens the avatar list, which also offers a photo upload; a
  chosen avatar replaces the photo. The red X removes an uploaded photo and
  brings back the default avatar.
- Photo upload with framing: the photo is shown with a circle (what the knob
  and the panel show) and the rest dimmed; drag to move it, zoom with the
  slider or the mouse wheel. Only the framed square is uploaded (512 px).
- New artwork for the default avatar and the red X (also on the knob's
  confirm screen), and a pencil icon.
- Routine templates: **Save as template** is also on a routine opened from
  the calendar for one day, and saves that day's version of the routine.

### Magyar

- Gyerek képe: egyetlen mező mutatja a gyerek fényképét vagy avatarját. Rá
  vagy a ceruzára kattintva megnyílik az avatarlista, ahol fénykép is
  feltölthető; egy választott avatar a fénykép helyére lép. A piros X törli a
  feltöltött fényképet, és visszaállítja az alap avatart.
- Fényképfeltöltés kivágással: a fénykép egy körrel jelenik meg (ez látszik a
  gombon és a panelen), a többi elhalványítva; húzással mozgatható, a
  csúszkával vagy az egérgörgővel nagyítható. Csak a kivágott négyzet töltődik
  fel (512 px).
- Új rajz az alap avatarhoz és a piros X-hez (a gomb megerősítő képernyőjén
  is), valamint egy ceruza ikon.
- Rutinsablonok: a **Mentés sablonként** a naptárból egy napra megnyitott
  rutinnál is megvan, és a rutin aznapi változatát menti.

## [0.7.21] - 2026-10-10

### English

- Routine templates: a routine can be saved as a template under its own name
  (**Save as template** at the bottom of the routine form), with its tasks,
  their order, icons, times and checkpoints. The routine list shows the saved
  templates; **New routine from this** opens a new routine filled from the
  template, for any children (no children are preselected). Templates can be
  deleted there.

### Magyar

- Rutinsablonok: egy rutin saját néven sablonként menthető (**Mentés
  sablonként** a rutin űrlapjának alján), a feladataival, azok sorrendjével,
  ikonjaival, időzítésével és checkpointjaival. A rutinlista mutatja a mentett
  sablonokat; az **Új rutin ebből** a sablon tartalmával nyit meg egy új
  rutint, bármelyik gyereknek (gyerek nincs előre kiválasztva). A sablonok
  ugyanott törölhetők.

## [0.7.20] - 2026-10-10

### English

- Fixed: version 0.7.19 could crash at every start, so the knob went back to
  the previous firmware (#35). The cause was ESP-IDF's handling of the small
  unused piece of picture memory after the firmware's data; that piece is now
  left unused (at most 64 KB).
- New neutral avatar (neither a boy nor a girl). It is preselected for a new
  child and replaces the removed sample avatars.
- A new installation starts with the second built-in background; the choice
  on the **Settings** page is kept as before.
- Background change: the knob logs the restart and waits 2 s before it
  restarts, so the log line reaches Home Assistant.

### Magyar

- Javítva: a 0.7.19 minden induláskor összeomolhatott, ezért a gomb
  visszaállt az előző firmware-re (#35). Az oka az ESP-IDF kezelése volt a
  firmware adatai utáni kis, kihasználatlan képmemória-darabra; ez a darab
  most kihasználatlan marad (legfeljebb 64 KB).
- Új semleges avatar (se nem fiú, se nem lány). Új gyereknél ez van előre
  kiválasztva, és ez lép a megszűnt minta-avatarok helyére.
- Új telepítés a második beépített háttérrel indul; a **Beállítások** oldalon
  választott háttér ugyanúgy megmarad, mint eddig.
- Háttércsere: a gomb naplózza az újraindítást, és 2 mp-et vár előtte, így a
  naplósor eljut a Home Assistantig.

## [0.7.19] - 2026-10-10

### English

- One background for all children: a child can no longer have a background of
  their own. The child's page no longer has a background choice, and the knob
  keeps the same background when the selected child changes (it no longer
  restarts for a child's background). Backgrounds already set for a child
  are dropped; the background on the **Settings** page is used everywhere.
- Sample avatars removed: the grey silhouette and the three simple faces are
  gone from the avatar choice, the panel and the knob. Children that still
  used one get the first drawn avatar. While an avatar is still downloading,
  the knob shows the child's coloured circle without a placeholder.

### Magyar

- Egy háttér minden gyereknek: a gyereknek nem lehet többé saját háttere. A
  gyerek oldalán nincs háttérválasztás, és a gomb gyermekváltáskor nem cseréli
  a hátteret (a gyerek háttere miatt sem indul újra). A gyerekeknél már
  beállított hátterek megszűnnek; mindenhol a **Beállítások** oldalon
  választott háttér látszik.
- A minta-avatarok kikerültek: a szürke sziluett és a három egyszerű arc
  eltűnt az avatarválasztóból, a panelből és a gombról. Az ezeket használó
  gyerekek az első rajzolt avatart kapják. Amíg egy avatar letöltődik, a gomb
  a gyerek színes körét mutatja helyettesítő kép nélkül.

## [0.7.18] - 2026-10-10

### English

- Background change: a new or changed background now always shows the same
  way. The knob downloads it straight into its flash cache, which needs no
  free picture memory, and then restarts and shows it from there. It restarts
  only after the picture is stored. When several new backgrounds arrive
  together, it restarts once. It never restarts twice in a row for the same
  picture, and when the download fails (e.g. no network) it does not restart.
  A knob without the cache area loads backgrounds as before.

### Magyar

- Háttércsere: az új vagy megváltozott háttér most mindig ugyanúgy jelenik
  meg. A gomb közvetlenül a flash-tárába tölti le, amihez nem kell szabad
  képmemória, aztán újraindul, és onnan mutatja. Csak a kép mentése után
  indul újra. Ha egyszerre több új háttér érkezik, egyszer indul újra.
  Ugyanazért a képért sosem indul újra kétszer egymás után, és sikertelen
  letöltésnél (pl. nincs hálózat) nem indul újra. A gyorsítótár nélküli gomb
  a hátteret a korábbi módon tölti be.

## [0.7.17] - 2026-10-10

### English

- Display: the pixel clock is now 16 MHz (was 18 MHz). At the higher clock
  the panel showed short bright lines on the left half of the picture, seen
  as stepped edges on the left of the time track and an occasional flashing
  streak (#32).
- Panel: where a photo is uploaded (child avatar, reward), the edit form shows
  only the photo; the icon choice appears again when the photo is removed.
- A new background could fail to load (`Not enough PSRAM`) when memory was
  fragmented. The knob now first tries again with less room kept free; if
  there is still no room, it stores the background in its flash cache and
  restarts once to load it into empty memory. It restarts only after the
  picture is stored, and never twice in a row for this reason.

### Magyar

- Kijelző: a képpont-órajel most 16 MHz (eddig 18 MHz). A magasabb órajelen
  a panel rövid világos vonalkákat mutatott a kép bal felén; ez lépcsős
  élekként látszott az időpálya bal oldalán, és néha felvillanó csíkként
  (#32).
- Panel: ahol fénykép van feltöltve (gyermek avatarja, jutalom), a
  szerkesztőlap csak a fényképet mutatja; az ikonválasztó a fénykép
  eltávolítása után jelenik meg újra.
- Töredezett memóriánál egy új háttér betöltése meghiúsulhatott
  (`Not enough PSRAM`). A gomb most először kisebb tartalékkal próbálja újra;
  ha így sincs hely, a hátteret a flash-tárába menti, és egyszer újraindul,
  hogy üres memóriába töltse be. Csak a sikeres mentés után indul újra, és
  emiatt sosem kétszer egymás után.

## [0.7.16] - 2026-10-10

### English

- Stripes, the moving band and steps on the track after opening the shop
  (#26, #32): the knob measured its free memory on every pass of its main
  loop, which walks through the whole picture memory, and once the memory was
  fragmented (as after the shop) every picture it loaded made it free all
  pictures and drawn items not on screen, which were then loaded and drawn
  again. This kept the memory busy, and the panel briefly got no data. Free
  memory is now checked only when a picture actually needs room, and only as
  much is freed as that picture needs.
- Drawn carousel items take memory blocks close to their real size (in 32 KB
  steps) instead of 254 KB each, so more items stay ready and turning back
  draws less again.
- Time track: the ring is computed faster (pixels away from a track are
  skipped sooner).
- Pictures were loaded twice after every update of the integration: Home
  Assistant identified them by the file time, which an update changes, so the
  knob showed its stored copy and then downloaded the same picture again
  (redrawing everything showing it). Pictures are now identified by their
  content, and a downloaded picture identical to the stored one is not shown
  again.

### Magyar

- Csíkok, úszó sáv és lépcsők a pályán a bolt megnyitása után (#26, #32): a
  gomb a fő ciklusa minden körében megmérte a szabad memóriát, ami végigjárja a
  teljes képmemóriát, és töredezett memóriánál (mint a bolt után) minden
  betöltött kép miatt felszabadított minden nem látható képet és megrajzolt
  elemet, amelyeket aztán újra betöltött és megrajzolt. Ez lefoglalta a
  memóriát, és a panel egy pillanatra nem kapott adatot. A szabad memóriát
  most csak akkor méri, amikor egy képnek tényleg hely kell, és csak annyit
  szabadít fel, amennyi annak kell.
- A megrajzolt körhinta-elemek a valódi méretükhöz közeli memóriablokkot
  kapnak (32 KB-os lépcsőkben) elemenként 254 KB helyett, így több elem marad
  kész, és visszaforgatáskor kevesebbet kell újrarajzolni.
- Időpálya: a gyűrű gyorsabban számolódik (a pályáktól távoli képpontokat
  hamarabb átugorja).
- Az integráció minden frissítése után minden kép kétszer töltődött be: a
  Home Assistant a fájl idejével azonosította őket, ami frissítéskor
  megváltozik, így a gomb megmutatta a tárolt példányt, aztán ugyanazt a képet
  újra letöltötte (és újrarajzolt mindent, ami mutatta). A képeket most a
  tartalmuk azonosítja, és a tárolttal azonos letöltött kép nem jelenik meg
  újra.

## [0.7.15] - 2026-10-10

### English

- Stripes and the slowly moving band (#26, #32): the knob kept freeing
  pictures it needed again a moment later (shop icons, avatars, backgrounds)
  whenever memory was a little fragmented, then loaded and drew them again,
  every few seconds. This constant work kept the memory busy, and the panel
  then briefly got no data (rows shifted sideways, a band moving down, steps
  on the track). Pictures are now freed only when memory is really short, and
  the item store is no longer emptied in that case.
- Item store: an item drawn once with its picture stays valid even when the
  picture itself has left the memory; an item drawn with a stand-in (picture
  still on its way) is not stored and is drawn again when the picture
  arrives.
- Time track: on a child change and once a minute (elapsed time) only the
  band of the tracks and their glow is computed again, not the whole ring.

### Magyar

- Csíkok és a lassan lefelé úszó sáv (#26, #32): a gomb enyhén töredezett
  memóriánál folyton felszabadította azokat a képeket, amelyekre egy pillanat
  múlva újra szüksége volt (bolti ikonok, avatarok, hátterek), aztán
  újratöltötte és újrarajzolta őket, pár másodpercenként. Ez az állandó munka
  lefoglalta a memóriát, és a panel ilyenkor egy pillanatra nem kapott adatot
  (oldalra csúszott sorok, lefelé úszó sáv, lépcsők a pályán). A képek most
  csak valódi memóriahiánynál szabadulnak fel, és ilyenkor az elemtár sem
  ürül ki.
- Elemtár: egy képpel együtt megrajzolt elem akkor is érvényes marad, ha maga
  a kép már nincs a memóriában; a helyettesítővel rajzolt elem (a kép még úton
  van) nem tárolódik, és a kép megérkezésekor újra rajzolódik.
- Időpálya: gyermekváltáskor és percenként (eltelt idő) csak a pályák és a
  ragyogásuk sávja számolódik újra, nem az egész gyűrű.

## [0.7.14] - 2026-10-10

### English

- Faster drawing (#10, #26, #32): the time track was made of about 260 small
  pictures (the inner track and its glow alone in about 200 tiles), and every
  frame had to handle each of them. It is now 20 larger pictures with
  everything in them, so a moving frame has much less to do.
- The track ring is drawn again only when something on it changes (the
  background, the screen colour, the selected child, the routine) and the
  elapsed part once a minute, in one go instead of piece by piece over a few
  seconds. The band that ran down the screen came from the piecewise drawing.
- Item store: it no longer empties itself before drawing a new item when
  memory is fragmented, and all item pictures use blocks of the same size, so
  freed memory is reused. The function carousel is stored too. Items you turn
  back to are shown from the store.
- A background picture that does not fit at first is tried again for longer
  (memory is made free meanwhile) instead of being left out.

### Magyar

- Gyorsabb rajzolás (#10, #26, #32): az időpálya kb. 260 kis képből állt (a
  belső pálya és a ragyogása egyedül kb. 200 csempéből), és minden
  képkockának mindegyikkel foglalkoznia kellett. Most 20 nagyobb kép
  tartalmaz mindent, így egy mozgó képkockának jóval kevesebb a dolga.
- Az időpálya gyűrűje csak akkor rajzolódik újra, ha valami változik rajta (a
  háttér, a képernyő színe, a kiválasztott gyermek, a rutin), az eltelt rész
  percenként, egyben, nem pár másodperc alatt darabonként. A képernyőn
  lefelé futó sávot a darabonkénti rajzolás okozta.
- Elemtár: már nem ürül ki új elem rajzolása előtt, ha a memória töredezett,
  és minden elemkép egyforma méretű blokkot kap, így a felszabadult memória
  újra felhasználódik. A funkció-körhinta is tárolódik. A visszaforgatott
  elemek a tárból jelennek meg.
- Egy háttérkép, amely elsőre nem fér el, tovább próbálkozik (közben memória
  szabadul fel), nem marad el.

## [0.7.13] - 2026-10-10

### English

- Child selector and shop (#32): instead of a token pile, one coin and the
  number show the tokens (the full pile stays on the token screen). The
  pictures of these items are much smaller, so they are drawn and moved
  faster.
- The item store keeps its pictures when the same avatar or icon is loaded
  again; an item is drawn again only when its content really changes. Before,
  reloading a picture made every item that used it count as new.
- Time track (#26, #34): when only the dimmed elapsed part moves on, just the
  few tiles where it changed are drawn again, not the whole ring; loading the
  same background picture again no longer redraws the ring. This removes the
  band that moved down the home screen every minute or so.
- Display: the RGB transfer restarts at every vertical sync (substitution
  `display_restart_in_vsync`), so a picture shifted by a moment without data
  (the whole screen jumping up or down) is put right at the next frame.
- Before a restart (e.g. after an update) the picture download stops, so it
  is not writing the flash cache while the knob restarts.
- The debug log of a slide also shows how much of the frame time goes to
  sending to the panel and how many pixels are drawn per frame.

### Magyar

- Gyermekválasztó és bolt (#32): zsetonkupac helyett egy zseton és a szám
  mutatja a zsetonokat (a teljes kupac a zseton-képernyőn marad). Ezeknek az
  elemeknek a képe jóval kisebb, így gyorsabban rajzolódnak és mozognak.
- Az elemtár megtartja a képeit, ha ugyanaz az avatar vagy ikon újra
  betöltődik; egy elem csak akkor rajzolódik újra, ha a tartalma valóban
  változik. Eddig egy kép újratöltése miatt minden azt használó elem újnak
  számított.
- Időpálya (#26, #34): ha csak az eltelt idő halványított része lép tovább,
  csak az a néhány csempe rajzolódik újra, ahol változott, nem az egész
  gyűrű; ugyanannak a háttérképnek az újratöltése nem rajzolja újra a gyűrűt.
  Ez megszünteti a kezdőképernyőn kb. percenként lefelé futó sávot.
- Kijelző: az RGB-átvitel minden függőleges szinkronnál újraindul
  (`display_restart_in_vsync` helyettesítés), így ha egy pillanatra nem
  érkezik adat és a kép elcsúszik (az egész képernyő fel-le ugrik), a
  következő képkockánál helyreáll.
- Újraindulás előtt (pl. frissítés után) a képletöltés leáll, így nem ír a
  flash-gyorsítótárba, miközben a gomb újraindul.
- A csúszás hibakereső naplója azt is mutatja, a képkocka idejéből mennyi a
  panelre küldés, és hány pixel rajzolódik képkockánként.

## [0.7.12] - 2026-10-09

### English

- Memory (#32): 0.7.11 could run out of PSRAM within minutes, and then
  backgrounds and pictures failed to load or came and went.
  - The separate moving picture for slides (about 740 KB) is gone: as the
    background stays in place anyway, the sharp items themselves slide, at the
    same cost per frame and without blur.
  - The four fixed buffers for carousel items (about 1.4 MB) are gone: a slot
    shows the item's picture straight from the item store, at its real size.
    Items you turn back to are now really shown from the store instead of
    being drawn again.
  - Downloaded pictures come first: when one needs memory, unused item
    pictures and pictures not on screen are dropped and the download is tried
    again, instead of failing.
- After a restart the track ring is drawn at once, not piece by piece.
- Time track (#33): the glow around the shared track no longer leaves a thin
  gap next to it.
- Stars (#32): shooting stars always follow an arc bending up and left: they
  start almost level and curve down to the left.

### Magyar

- Memória (#32): a 0.7.11 percek alatt kifuthatott a PSRAM-ból, és ilyenkor a
  hátterek és képek nem töltődtek be, vagy eltűntek és visszajöttek.
  - Megszűnt a csúszáshoz használt külön mozgó kép (kb. 740 KB): mivel a háttér
    úgyis a helyén marad, maguk az éles elemek csúsznak, képkockánként
    ugyanakkora költséggel, elmosás nélkül.
  - Megszűnt a körhinta-elemek négy fix puffere (kb. 1,4 MB): egy hely az elem
    képét közvetlenül az elemtárból mutatja, valódi méretében. A visszaforgatott
    elemek most tényleg a tárból jelennek meg, nem rajzolódnak újra.
  - A letöltött képek az elsők: ha egynek memória kell, a nem használt
    elemképek és a nem látható képek felszabadulnak, és a letöltés újra
    próbálkozik ahelyett, hogy feladná.
- Újraindulás után az időpálya gyűrűje egyszerre rajzolódik ki, nem
  darabonként.
- Időpálya (#33): a közös pálya körüli ragyogás már nem hagy vékony rést
  mellette.
- Csillagok (#32): a hullócsillagok mindig fent-balra ívelő pályán haladnak:
  szinte vízszintesen indulnak, és balra lefelé kanyarodnak.

## [0.7.11] - 2026-10-09

### English

- Carousels (#10, #26, #32):
  - An item that was drawn once (a child with avatar, token pile and number,
    a reward) is kept as a picture and copied when it comes back, until its
    content changes (tokens, picture, colour). Before, every turn drew the
    next item again, token by token.
  - Turns that pile up while the knob is busy are added up: one jump and one
    slide, however many turns. Before, every turn was drawn one by one, which
    could block the knob for many seconds after waking.
  - While sliding, only the items move, blurred sideways; the background stays
    sharp and still, and there are no hard edges.
  - The parts of the time track that cover their area completely are copied
    instead of blended, which makes every frame cheaper.
- Display: the default pixel clock is 18 MHz (was 26 MHz). The panel is
  refreshed a little less often, which leaves more memory bandwidth for
  drawing: smoother movement and no flicker. A device config can still set
  `display_pclk_frequency`.
- Time track (#33): a glow in the selected child's colour around the inner
  track and the shared track (at most as wide as the inner track, under half
  as strong as the colour), and a narrow, soft edge between the ring and the
  screen content, instead of the dark shading.
- Knob (#27): after a rest the detent the knob sits in is taken as the
  reference again, so counts lost while the knob was busy do not shift it.
- Screensavers (#32): shooting stars always travel down and to the left; a
  confetti piece is redrawn in one go at its old and new place, so it never
  disappears for a moment.

### Magyar

- Körhinták (#10, #26, #32):
  - Egy egyszer már megrajzolt elem (gyermek avatarral, zsetonkupaccal és
    számmal, illetve jutalom) képként megmarad, és visszatéréskor csak
    másolódik, amíg a tartalma nem változik (zsetonok, kép, szín). Eddig
    minden forgatás újrarajzolta a következő elemet, zsetonról zsetonra.
  - A forgatások, amelyek a gomb elfoglaltsága alatt gyűltek össze,
    összeadódnak: egy ugrás és egy csúszás, akárhány forgatásról is van szó.
    Eddig mindegyik külön rajzolódott, ami ébredés után sok másodpercre
    megakaszthatta a gombot.
  - Csúszás közben csak az elemek mozognak, oldalirányban elmosva; a háttér
    éles marad és áll, és nincsenek éles szélek.
  - Az időpálya azon részei, amelyek a területüket teljesen fedik, másolódnak,
    nem keverednek, így minden képkocka olcsóbb.
- Kijelző: az alapértelmezett pixelórajel 18 MHz (eddig 26 MHz). A panel kicsit
  ritkábban frissül, így több memória-sávszélesség marad a rajzolásra:
  simább mozgás, villogás nélkül. Az eszközkonfigban a
  `display_pclk_frequency` továbbra is beállítható.
- Időpálya (#33): a kiválasztott gyermek színében halvány ragyogás a belső és a
  közös pálya körül (legfeljebb a belső pálya szélességében, a szín felénél
  halványabban), és keskeny, puha átmenet a gyűrű és a képernyő tartalma
  között a sötét árnyalás helyett.
- Forgatás (#27): pihenés után a rovátka, amelyben a gomb áll, újra a
  kiindulópont, így az elfoglaltság alatt elveszett jelek nem tolják el.
- Képernyővédők (#32): a hullócsillagok mindig lefelé és balra haladnak; egy
  konfettidarab régi és új helye egyszerre rajzolódik újra, így egy
  pillanatra sem tűnik el.

## [0.7.10] - 2026-10-09

### English

- Fix: waking the knob after a long idle time could restart it (task
  watchdog during the first, large redraw). The watchdog is now fed during
  long redraws and while the screen is built (#32).
- Time track (#32, #33):
  - The ring is computed several times faster and in small parts between
    other work, so turning and pressing are no longer held up (before: about
    0.6 s after every child change). The child's inner track is a separate
    layer; a new child only changes its colour.
  - The background picture behind the rings is shaded darker, so the smooth
    fade from the rings inwards is visible again.
- Carousels (#10, #26): the moving picture repeats the background sideways,
  so no black area appears while sliding. The sharp items are shown before the
  next slide is prepared, without a hitch.
- Knob (#27): the detent that wakes the screen is not a step, and the
  direction is kept, so the next detent counts in either direction.
- The default long press time is 0.4 s (a value you set yourself stays).
- Screensavers (#32):
  - Confetti pieces are small pictures like the bouncing balls, at the same
    frame rate.
  - Stars: they no longer fall. Stars of different sizes appear at random
    places, brighten and dim slowly, and vanish; now and then a shooting star
    crosses from top right to bottom left on a curve.
  - The log shows when the screensaver starts and after how many seconds
    without input.

### Magyar

- Javítás: hosszú tétlenség után az ébresztés újraindíthatta a gombot (task
  watchdog az első, nagy újrarajzolás közben). A watchdog most hosszú
  újrarajzolás és a képernyő felépítése közben is táplálva van (#32).
- Időpálya (#32, #33):
  - A gyűrű többszörösen gyorsabban és kis részletekben, más munka között
    számolódik ki, így a forgatás és a nyomás már nem akad meg (eddig minden
    gyermekváltás után kb. 0,6 mp-re). A gyermek belső pályája külön réteg; új
    gyermeknél csak a színe változik.
  - A gyűrűk mögötti háttérkép sötétebb árnyalatot kap, így a gyűrűktől befelé
    tartó sima átmenet újra látszik.
- Körhinták (#10, #26): a mozgó kép oldalirányban ismétli a hátteret, így
  csúszás közben nem jelenik meg fekete terület. Az éles elemek a következő
  csúszás előkészítése előtt megjelennek, akadás nélkül.
- Forgatás (#27): a képernyőt felébresztő rovátka nem lépés, és az irány
  megmarad, így a következő rovátka bármelyik irányba számít.
- A hosszú nyomás alapértelmezett ideje 0,4 mp (a saját beállított érték
  megmarad).
- Képernyővédők (#32):
  - A konfettidarabok kis képek, mint a pattogó labdák, ugyanazzal a
    képkockasebességgel.
  - Csillagok: már nem hullanak. Különböző méretű csillagok jelennek meg
    véletlen helyeken, lassan fényesednek és halványulnak, majd eltűnnek;
    időnként egy hullócsillag szeli át a képernyőt jobbról fentről balra le,
    ívben.
  - A naplóban látszik, mikor indul a képernyővédő, és hány másodperc
    tétlenség után.

## [0.7.9] - 2026-10-09

### English

- Sliding carousels (#10, #26):
  - While a carousel slides, one prepared picture of the whole strip moves,
    blurred sideways like a fast movement; when it stops, the sharp items are
    shown again. Each frame is a plain copy, so the slide gets many frames. The
    picture for the next turn in the same direction is prepared while the
    knob rests.
  - Starting a slide no longer redraws the whole screen (the child's inner
    track is no longer hidden during the slide).
  - Turns that pile up while the screen is busy are done at once, all but the
    last without animation, so the carousel stops when the knob stops.
- Time track (#32, #33):
  - The ring (band, zones, elapsed part, the child's inner track) is computed
    pixel by pixel in a fraction of the time, only when something on it
    changes, and the old ring stays on screen meanwhile. Before, it took up to
    2 s, also during the screensaver, and the knob did not react in that time,
    which is why a press sometimes did not wake it.
  - The background picture now reaches the outer edge of the screen, behind
    the rings too.
  - The fade from the rings inwards is smooth, without visible steps.
- Knob (#27): turning is followed detent by detent. The first detent after a
  change of direction arrives one count early, and now always counts.
- Screensavers (#32):
  - Stars brighten and dim slowly, like breathing, instead of flickering.
  - Confetti and stars move at about 50 frames a second, in smaller steps.
- Panel: number and text settings (e.g. the screensaver time) are saved 2 s
  after you stop typing, or when you leave the field; pressing Enter is no
  longer needed. The field keeps the focus while it is saved.

### Magyar

- Csúszó körhinták (#10, #26):
  - Csúszás közben az egész sáv egyetlen előkészített képe mozog, oldalirányban
    elmosva, mint egy gyors mozdulat; megálláskor újra az éles elemek
    látszanak. Minden képkocka egy egyszerű másolás, így a csúszás sok
    képkockából áll. Az ugyanarra következő forgatás képe akkor készül el,
    amikor a gomb pihen.
  - A csúszás kezdete már nem rajzolja újra az egész képernyőt (a gyermek
    belső pályája csúszás közben nem tűnik el).
  - A forgatások, amelyek sorba álltak, amíg a képernyő dolgozott, egyszerre
    hajtódnak végre, az utolsó kivételével animáció nélkül, így a körhinta
    megáll, amikor a gomb megáll.
- Időpálya (#32, #33):
  - A gyűrű (sáv, zónák, eltelt rész, a gyermek belső pályája) pixelenként,
    töredék idő alatt számolódik ki, csak ha valami változik rajta, és
    közben a régi gyűrű látszik. Eddig akár 2 mp-ig tartott, képernyővédő
    közben is, és a gomb addig nem reagált, ezért nem ébresztett néha a
    nyomás.
  - A háttérkép most a képernyő külső széléig ér, a gyűrűk mögött is.
  - A gyűrűktől befelé az átmenet sima, látható lépcsők nélkül.
- Forgatás (#27): a gomb rovátkánként követi a forgatást. Irányváltás után az
  első rovátka egy jellel korábban érkezik, és most mindig számít.
- Képernyővédők (#32):
  - A csillagok villogás helyett lassan, lélegzésszerűen fényesednek és
    halványulnak.
  - A konfetti és a csillagok kb. 50 képkocka/mp sebességgel, kisebb
    lépésekben mozognak.
- Panel: a szám- és szövegbeállítások (pl. a képernyővédő ideje) 2 mp-cel az
  utolsó gépelés után, vagy a mező elhagyásakor mentődnek; Entert nyomni már
  nem kell. Mentés közben a mező megtartja a fókuszt.

## [0.7.8] - 2026-10-09

### English

- Faster sliding carousels (#10, #26):
  - The time track's band and arcs are drawn once into small pictures along
    the ring, instead of on every frame; these arcs took most of the time of a
    frame. They are drawn again only when the track changes; the dimmed
    elapsed part follows in steps of 1 %, while nobody uses the knob.
  - The carousel items are drawn only inside the inner circle (everything
    outside is under the track band), as compact pictures cut to their
    content. The memory for them is reserved once and reused.
  - The function and reward carousels slide as pictures too.
  - The child's inner track is hidden while a carousel slides and comes back
    when it stops.
  - A token pile is one picture instead of hundreds of separate coins; the
    newest few coins stay separate in front of it. This also removes the long
    pauses (up to 3 s) after turning on the child screen.
- Knob (#27): the first click after a change of direction now always counts.
  The encoder reports that click one count early; this is taken into account.
  With "Encoder clicks per step" above 1, the first click after a change of
  direction or a rest makes a step at once.
- A long press on the home screen connects to Home Assistant again only when
  it is not connected; while connected it does nothing (#32).
- Screensavers (#32):
  - Confetti runs on its own screen, so nothing else is drawn under it, and
    the pieces only move: no flicker. They fall faster, on swaying paths with
    a sideways drift that changes direction now and then; gusts blow a few
    pieces away, each differently.
  - New screensaver: stars (falling small stars, at most the size of a
    confetti piece). Choose it in the panel: Settings → Knob screen.
- The knob logs button presses with the screen state (debug log), to find out
  why a press does not wake it from the screensaver.

### Magyar

- Gyorsabban csúszó körhinták (#10, #26):
  - Az időpálya sávja és ívei egyszer rajzolódnak meg, kis képekként a gyűrű
    mentén, nem minden képkockánál újra; ezek az ívek vitték el egy képkocka
    idejének nagy részét. Csak akkor rajzolódnak újra, ha a pálya változik; az
    eltelt idő halványított része 1%-os lépésekben követi, amikor senki nem
    használja a gombot.
  - A körhinta elemei csak a belső körön belül rajzolódnak (ami kívül esik, az
    a pálya sávja alatt van), a tartalmukra vágott, tömör képekként. A
    memóriájuk egyszer foglalódik le, és újra felhasználódik.
  - A funkció- és a jutalom-körhinta is képként csúszik.
  - A gyermek belső pályája csúszás közben rejtve van, és megálláskor
    visszajön.
  - Egy zsetonkupac egyetlen kép több száz külön zseton helyett; a legújabb
    néhány zseton külön marad előtte. Ez a gyermekképernyőn forgatás utáni
    hosszú (akár 3 mp-es) szüneteket is megszünteti.
- Forgatás (#27): irányváltás után az első kattintás mindig számít. A gomb ezt
  a kattintást egy jellel korábban jelzi; ezt most figyelembe veszi. Ha a
  „Encoder clicks per step” 1-nél nagyobb, irányváltás vagy pihenés után az
  első kattintás azonnal lép.
- Hosszú nyomás a kezdőképernyőn csak akkor csatlakoztat újra a Home
  Assistanthez, ha nincs kapcsolat; kapcsolat közben nem csinál semmit (#32).
- Képernyővédők (#32):
  - A konfetti saját képernyőn fut, így semmi más nem rajzolódik alatta, és a
    darabok csak mozognak: nincs villogás. Gyorsabban hullanak, lengő pályán,
    időnként irányt váltó oldalirányú sodródással; a szélrohamok néhány darabot
    elfújnak, mindegyiket másképp.
  - Új képernyővédő: csillagok (hulló kis csillagok, legfeljebb akkorák, mint
    egy konfettidarab). A panelen választható: Beállítások → Gomb
    képernyője.
- A gomb a hibakereső naplóban a képernyő állapotával együtt naplózza a
  gombnyomásokat, hogy kiderüljön, miért nem ébreszt a nyomás a
  képernyővédőből.

## [0.7.7] - 2026-10-08

### English

- Pictures (#31):
  - A picture that is replaced or no longer shown now leaves the memory. Before,
    every background change kept about 450 KB of PSRAM until the carousels
    could not slide smoothly any more.
  - The knob keeps the downloaded pictures in a 4 MB cache in its flash: after a
    restart they appear at once and are not downloaded again. Once after each
    start it asks Home Assistant whether a picture changed; an unchanged one is
    not sent again. A knob first installed with 0.7.6 or older needs the
    factory firmware flashed over USB once for the cache (see
    docs/hardware.md); without it everything works as before.
  - An arriving picture is drawn only where it is shown, instead of building
    the whole screen again, and a snapshot from Home Assistant in which only
    the time changed no longer redraws the screen.
  - Less PSRAM is held back (384 KB instead of 768 KB), so the carousel
    snapshots fit more often.
- Carousels (#10): the next item is prepared while the knob rests, so a slide
  starts at once. The debug log shows how long a frame takes while sliding.
- Moving pictures are no longer drawn in two halves with a visible cut (#26):
  the full-screen draw buffer is back as the default (substitution
  `lvgl_buffer_size`).
- Knob and button (#27, #32):
  - Turns and presses are queued and handled by the screen right after, so the
    knob's input never waits for drawing; after a busy moment the encoder
    counts from the detent it came from, so no step is lost.
  - A long press acts as soon as the button has been held long enough, without
    waiting for the release. The time is a new setting, "Long press time"
    (default 0.5 s).
  - A press wakes the knob from the screensaver, dimming or a dark screen, and
    does nothing else.
  - A long press on the home screen connects to Home Assistant again: Home
    Assistant sends the texts and the data anew.
- The offline mark (crossed-out cloud) shows only when Home Assistant is not
  connected; another connection, such as a log viewer, no longer switches it on
  or off (#32).
- No light patches at the outer rim of the screen: the background picture no
  longer shows through at the edge (#32).
- New confetti screensaver: pieces fall faster and smoothly on swaying paths,
  each at its own speed and with its own flutter, in slightly different sizes;
  now and then a gust blows a few of them away, each a little differently.
- The knob logs its screen power settings (screensaver, dimming, drawing off,
  backlight off) when they arrive from Home Assistant.

### Magyar

- Képek (#31):
  - A lecserélt vagy már nem látható kép felszabadítja a memóriát. Eddig minden
    háttércsere kb. 450 KB PSRAM-ot foglalt le, amíg a körhinták már nem tudtak
    simán csúszni.
  - A gomb a letöltött képeket a flash 4 MB-os gyorsítótárában tartja:
    újraindulás után azonnal megjelennek, és nem kell újra letölteni őket.
    Indulásonként egyszer megkérdezi a Home Assistanttől, változott-e egy kép;
    a változatlant nem kapja meg újra. A 0.7.6-os vagy régebbi verzióval
    telepített gombhoz a gyorsítótárhoz egyszer USB-n fel kell írni a gyári
    firmware-t (lásd docs/hardware.md); nélküle minden úgy működik, mint eddig.
  - A beérkező kép csak ott rajzolódik újra, ahol látszik, nem épül újra az
    egész képernyő, és ha a Home Assistant adataiban csak az idő változott,
    a képernyő nem rajzolódik újra.
  - Kevesebb PSRAM marad tartalékban (768 KB helyett 384 KB), így a körhinták
    pillanatképei gyakrabban elférnek.
- Körhinták (#10): a következő elem előre elkészül, amíg a gomb nyugalomban
  van, így a csúszás azonnal indul. A hibakereső napló mutatja, mennyi ideig
  tart egy képkocka csúszás közben.
- A mozgó képek nem rajzolódnak két részletben, látható vágással (#26): újra a
  teljes képernyős rajzolási puffer az alapértelmezés (`lvgl_buffer_size`
  helyettesítés).
- Forgatás és gomb (#27, #32):
  - A forgatások és nyomások sorba állnak, és a képernyő rögtön utánuk kezeli
    őket, így a bemenet sosem vár a rajzolásra; egy terhelt pillanat után a
    forgatás attól a rovátkától számol, ahonnan a gomb elindult, így nem vész el
    lépés.
  - A hosszú nyomás azonnal hat, amint elég ideig nyomva tartod, nem kell
    elengedni. Az idő új beállítás: „Long press time” (alapérték 0,5 mp).
  - Egy nyomás felébreszti a gombot a képernyővédőből, a halványításból vagy a
    sötét képernyőből, és mást nem csinál.
  - Hosszú nyomás a kezdőképernyőn újra csatlakoztat a Home Assistanthez: az
    újra elküldi a szövegeket és az adatokat.
- Az offline jel (áthúzott felhő) csak akkor látszik, ha a Home Assistant nincs
  csatlakozva; más kapcsolat, például egy naplónéző, már nem kapcsolja be vagy
  ki (#32).
- Nincsenek világos foltok a képernyő külső peremén: a háttérkép nem látszik át
  a szélén (#32).
- Új konfetti-képernyővédő: a darabok gyorsabban és folyamatosan hullanak, lengő
  pályán, mindegyik a saját sebességével és libbenésével, kicsit eltérő
  méretben; időnként egy szélroham elfúj közülük néhányat, mindegyiket kicsit
  másképp.
- A gomb naplózza a képernyő-beállításait (képernyővédő, halványítás, rajzolás
  ki, háttérvilágítás ki), amikor megérkeznek a Home Assistanttől.

## [0.7.6] - 2026-10-08

### English

- Fix (#31): the knob restarted about every 40 seconds (task watchdog), and
  avatars and backgrounds did not show because PSRAM ran out.
  - Most icons (routines, tasks, rewards) are no longer part of the firmware:
    the knob downloads the ones it shows from Home Assistant. The firmware
    keeps only the few images it needs before Home Assistant answers (brand
    mark, loading screen, coins and symbols), which frees about 3.7 MB of
    PSRAM.
  - The drawing buffer is a quarter of the screen instead of a full screen,
    which frees another 340 KB.
  - When memory is short, the carousels draw at most 30 coins per pile, so a
    slide never takes long enough to trigger the watchdog.
  - When the background changes, the old one stays until the new one has
    arrived; if it cannot be loaded, the plain colour is shown.

### Magyar

- Javítás (#31): a gomb kb. 40 másodpercenként újraindult (task watchdog), és
  az avatarok meg a hátterek nem jelentek meg, mert elfogyott a PSRAM.
  - Az ikonok többsége (rutinok, feladatok, jutalmak) már nem része a
    firmware-nek: a gomb a megjelenítetteket a Home Assistanttől tölti le. A
    firmware csak azt a néhány képet tartja meg, amely a Home Assistant
    válasza előtt kell (márkajel, betöltőképernyő, zsetonok, jelek), így kb.
    3,7 MB PSRAM szabadul fel.
  - A rajzolási puffer a teljes képernyő helyett negyed képernyőnyi, ez
    további 340 KB.
  - Kevés memória esetén a körhinták kupaconként legfeljebb 30 zsetont
    rajzolnak, így egy csúszás soha nem tart olyan sokáig, hogy a watchdog
    közbelépjen.
  - Háttércserénél a régi háttér marad, amíg az új meg nem érkezik; ha nem
    tölthető be, a sima szín látszik.

## [0.7.5] - 2026-10-08

### English

- Fix (#30): 0.7.4 did not start on the knob; it restarted before the start
  was confirmed, and the knob went back to 0.7.3. The firmware runs from PSRAM
  again, as in 0.7.3 (running it from flash is now an experimental option,
  `psram_xip: "n"`). Everything else from 0.7.4 stays: smoother carousels,
  the detent-based encoder and the screen settings in the panel.
- New artwork for every task icon and the checkpoint flag (each with a
  simplified small variant), new tasks: pyjamas and coat for boys and for
  girls, and the six built-in backgrounds.
- Icons that are the same picture for a task and a routine (bath, tidying up,
  ready to leave, dinner, bed, play, packing) are stored once; existing
  routines keep working, and every routine icon can be chosen for tasks and
  checkpoints and the other way round. The firmware got smaller.
- A second screensaver: continuous confetti, next to the bouncing balls
  (Settings → Knob screen, also per knob).
- After a restart the knob logs why its previous run ended (for example a
  crash or a power dip), also to Home Assistant.
- Hardware notes: how to read the knob's serial log with a USB-UART adapter.

### Magyar

- Javítás (#30): a 0.7.4 nem indult el a gombon; a sikeres indulás jelzése
  előtt újraindult, és a gomb visszaállt a 0.7.3-ra. A firmware ismét a
  PSRAM-ból fut, mint a 0.7.3-ban (a flashből futtatás most kísérleti
  beállítás: `psram_xip: "n"`). A 0.7.4 többi része megmarad: simább
  körhinták, kattanás alapú enkóder és a képernyő-beállítások a panelen.
- Új rajzok minden feladatikonhoz és a checkpoint zászlóhoz (mindegyik
  egyszerűsített kis változattal), új feladatok: fiú és lány pizsama és kabát,
  valamint a hat beépített háttér.
- A feladatnál és rutinnál ugyanazt a képet használó ikonok (fürdés,
  rendrakás, indulás, vacsora, alvás, játék, összekészülés) csak egyszer
  tárolódnak; a meglévő rutinok változatlanul működnek, és minden rutinikon
  választható feladathoz és checkpointhoz, és fordítva. A firmware kisebb lett.
- Második képernyővédő: folyamatos konfetti a pattogó labdák mellett
  (Beállítások → Gomb képernyője, gombonként is).
- Újraindulás után a gomb naplózza, miért ért véget az előző futása (például
  összeomlás vagy feszültségesés), a Home Assistant felé is.
- Hardverleírás: a gomb soros naplójának kiolvasása USB-UART adapterrel.

## [0.7.4] - 2026-10-08

### English

- More memory on the knob (#26): the firmware now runs from flash instead of
  being copied into PSRAM, which leaves several MB of PSRAM for drawing, the
  carousels' pre-rendered slots and backgrounds. The display keeps working
  while the knob writes to its flash, and recovers at the next frame if a
  frame was disturbed (against the horizontal flicker line while animating).
- Smoother carousels (#10): the side items no longer fade through an extra
  rendering pass on every frame, which made the child carousel jump instead
  of sliding.
- Encoder (#27): a step counts only after a full detent, so the knob no
  longer snaps back when released; after a pause the first detent always
  counts; the first turn or press wakes a dimmed or dark screen at once (a
  press wakes it on pressing, not on releasing). `encoder_debug: "true"` logs
  the raw encoder counts.
- Screen power in the panel (#28): Settings → Knob screen sets the idle times
  of the screensaver (the bouncing balls), dimming (with its brightness),
  drawing off (black screen) and backlight off, 0 = never; each knob can have
  its own values. The "Screen dim after" and "Screen off after" device
  settings of the knob are replaced by these.

### Magyar

- Több memória a gombon (#26): a firmware most a flashből fut, nem másolódik
  a PSRAM-ba, így több MB PSRAM marad a rajzolásra, a körhinták előre
  kirajzolt elemeire és a hátterekre. A kijelző akkor is működik, amikor a
  gomb a flashbe ír, és ha egy képkocka megzavarodik, a következővel helyreáll
  (a mozgás közbeni vízszintes villanó csík ellen).
- Simább körhinták (#10): a szélső elemek halványítása már nem jár minden
  képkockánál egy külön rajzolási menettel, ami miatt a gyerek-körhinta
  csúszás helyett ugrált.
- Enkóder (#27): egy lépés csak egy teljes kattanás után számít, így
  elengedéskor nem ugrik vissza; szünet után az első kattanás is mindig
  számít; az első tekerés vagy nyomás azonnal felébreszti a halványított vagy
  sötét képernyőt (nyomásnál már a lenyomáskor, nem az elengedéskor). Az
  `encoder_debug: "true"` naplózza az enkóder nyers számlálását.
- Képernyő-beállítások a panelen (#28): Beállítások → Gomb képernyője: a
  képernyővédő (pattogó labdák), a halványítás (és annak fényereje), a rajzolás
  leállítása (fekete képernyő) és a háttérvilágítás kikapcsolása tétlenségi
  ideje, 0 = soha; gombonként saját értékek is megadhatók. Ezek váltják a gomb
  „Screen dim after” és „Screen off after” eszközbeállításait.

## [0.7.3] - 2026-10-08

### English

- Fix (#23): with 0.7.1 the knob's screen stayed black, because the firmware
  ran out of PSRAM. The knob keeps its program and built-in images in PSRAM,
  and the twelve new avatars took about 1.2 MB of it. The avatars are no longer
  part of the firmware: the knob downloads the chosen avatar from Home
  Assistant like an uploaded picture (the firmware is about 1.2 MB smaller).
- The knob always keeps 768 KB of PSRAM free for drawing: when memory is
  short, the carousels draw their content directly instead of keeping
  pre-rendered copies, and a picture or background that does not fit is
  skipped. Either case is logged once as an error.
- The knob logs its free PSRAM and the largest free block at boot and after
  each update from Home Assistant.
- Backgrounds are shown only on the knob; the panel keeps its normal look.

### Magyar

- Javítás (#23): a 0.7.1-gyel a gomb képernyője fekete maradt, mert a
  firmware-nek elfogyott a PSRAM-ja. A gomb a programját és a beépített képeit
  a PSRAM-ban tartja, és a tizenkét új avatar kb. 1,2 MB-ot foglalt belőle. Az
  avatarok már nem részei a firmware-nek: a gomb a kiválasztott avatart a
  feltöltött képekhez hasonlóan a Home Assistanttől tölti le (a firmware kb.
  1,2 MB-tal kisebb).
- A gomb mindig 768 KB PSRAM-ot szabadon hagy a rajzoláshoz: ha kevés a
  memória, a körhinták előre kirajzolt másolat helyett közvetlenül rajzolják a
  tartalmukat, a be nem férő kép vagy háttér pedig kimarad. Mindkettőt egyszer,
  hibaként naplózza.
- A gomb induláskor és a Home Assistant minden frissítése után naplózza a szabad
  PSRAM-ot és a legnagyobb szabad blokkot.
- A háttér csak a gombon látszik; a panel a megszokott kinézetű marad.

## [0.7.2] - 2026-10-08

### English

- Fix (#22): the summary and child sensors refreshed their state every minute
  from a worker thread instead of Home Assistant's event loop. Home Assistant
  warned about it at every start, and it could have led to a crash or
  corrupted state. They now refresh from the event loop.

### Magyar

- Javítás (#22): az összesítő és a gyerekenkénti szenzorok percenkénti
  frissítése a Home Assistant eseményhurka helyett egy mellékszálon futott. A
  Home Assistant minden induláskor figyelmeztetett erre, és ez összeomláshoz
  vagy sérült állapothoz vezethetett volna. Most az eseményhurokból
  frissülnek.

## [0.7.1] - 2026-10-08

### English

- Backgrounds: a general background for the knobs and the panel (Settings),
  and each child can have their own (child's page), shown on that child's
  screens on the knob and on the child's card in the panel. Six built-in
  backgrounds (temporary artwork for now) or your own uploaded picture. The
  knob downloads the background from Home Assistant like the pictures.
- New artwork: twelve avatars to choose for the children, the routine icons
  (each with a simplified small variant), the function icons, the piggy bank,
  the brand mark, the logo and the integration icon.
- The routine icons can also be chosen for tasks and checkpoints; small
  places on the knob and in the panel use their simplified variant.
- Pictures for the knob are prepared several times faster.

### Magyar

- Hátterek: általános háttér a gombokra és a panelre (Beállítások), és
  gyerekenként saját háttér is megadható (a gyerek oldalán), amely a gombon az
  adott gyerek képernyőin és a panelen a gyerek kártyáján látszik. Hat beépített
  háttér (egyelőre ideiglenes rajzokkal) vagy saját feltöltött kép. A gomb a
  hátteret a képekhez hasonlóan a Home Assistanttől tölti le.
- Új rajzok: tizenkét választható avatar a gyerekeknek, a rutinikonok (mindegyik
  egyszerűsített kis változattal), a funkcióikonok, a persely, a márkajel, a
  logó és az integráció ikonja.
- A rutinikonok feladathoz és checkpointhoz is választhatók; a gombon és a
  panelen a kis helyeken az egyszerűsített változatuk látszik.
- A gombnak szánt képek többszörösen gyorsabban készülnek el.

## [0.7.0] - 2026-10-08

### English

Security hardening (#21). **Update the knob firmware together with the
integration**, otherwise uploaded pictures do not appear on the knob.

- Knob firmware: the example config requires an OTA password
  (`ota_password`) and a password for the fallback access point
  (`ap_password`), and uses one API encryption key per knob (see the
  README). Adopting the ready-made firmware in the ESPHome Builder uses the
  released version.
- Picture key only over an encrypted connection: Home Assistant sends a knob
  its picture key only when the knob's API is encrypted; otherwise the knob
  shows icons and a repair issue explains how to add a key.
- Pictures reach the knob only from the local network, never through Home
  Assistant Cloud or the internet. The knob sends its key in a request header
  instead of the address (so it stays out of logs), and keys are compared in
  constant time. Panel → Settings → Knobs → "New picture key" gives a knob a
  new key at once.
- Messages from a knob are checked strictly (size, exact fields, types and
  ranges), at most 20 per minute per knob; the list of already booked actions
  is limited in age and size.
- Uploaded pictures: the real image type is checked, files over 30 MB and
  images over 100 megapixels are refused before they are read, large photos
  are read at a reduced resolution; the knob's copy contains no metadata
  (EXIF, location).
- Release builds use build steps pinned to exact versions.
- 15 new routine icons (temporary artwork for now).
- README: new "Security" section, details in docs/security.md.

### Magyar

Biztonsági megerősítés (#21). **A gomb firmware-ét az integrációval együtt
frissítsd**, különben a feltöltött képek nem jelennek meg a gombon.

- Gomb-firmware: a mintakonfiguráció OTA-jelszót (`ota_password`) és a
  tartalék hozzáférési ponthoz jelszót (`ap_password`) kér, és gombonként
  külön API titkosítási kulcsot használ (lásd a README-t). A kész firmware
  ESPHome Builderbe való átvételekor a kiadott verzió kerül be.
- Képkulcs csak titkosított kapcsolaton: a Home Assistant csak akkor küldi el
  a gombnak a képkulcsát, ha a gomb API-kapcsolata titkosított; különben a
  gomb ikonokat mutat, és egy javítási értesítés elmagyarázza, hogyan kell
  kulcsot beállítani.
- A képek csak a helyi hálózatról jutnak el a gombra, Home Assistant Cloudon
  és az interneten át soha. A gomb a kulcsát a kérés fejlécében küldi a cím
  helyett (így nem kerül naplóba), a kulcsok összehasonlítása konstans idejű.
  Panel → Beállítások → Gombok → „Új képkulcs”: a gomb azonnal új kulcsot kap.
- A gomb üzeneteit szigorúan ellenőrzi (méret, pontosan a várt mezők, típusok
  és tartományok), gombonként legfeljebb 20-at percenként; a már könyvelt
  műveletek listája kor és méret szerint korlátozott.
- Feltöltött képek: a valódi képtípust ellenőrzi, a 30 MB-nál nagyobb fájlokat
  és a 100 megapixelnél nagyobb képeket beolvasás előtt elutasítja, a nagy
  fotókat csökkentett felbontásban olvassa be; a gombra kerülő példányban
  nincs metaadat (EXIF, helyadat).
- A kiadások pontos verzióra rögzített build-lépésekkel készülnek.
- 15 új rutinikon (egyelőre ideiglenes rajzokkal).
- README: új „Biztonság” szakasz, részletek a docs/security.md-ben.

## [0.6.0] - 2026-10-07

### English

- Calendar (#17, #19): day, 3-day and week views in a Google Calendar-like
  style; the last chosen view is remembered per user, phones start with the
  day view.
- Only this occurrence or the whole series (#17): clicking a routine in the
  calendar asks, like Outlook. "This occurrence only" opens the full routine
  editor for that date (times, colour zones, checkpoints with reward bands,
  tasks, children) with the changed parts marked, "Restore the original",
  and everything logged; the routine itself is unchanged. Clicking an empty
  place adds a routine for that day only. Past days are read-only. The Today
  page has the same editor for today.
- Dragging in the calendar (#17): drag a routine to move it for that day
  (its checkpoints move with it), drag its top or bottom edge to change the
  start or end; 5-minute grid, live time label, Undo; long press on touch
  screens.
- Routine colours (#18): every routine gets its own calendar colour (palette
  and colour picker, a distinct colour for new routines, a hint for similar
  colours), separate from the knob's time track base colour. Changed
  occurrences carry a badge and a dashed outline, not only a colour.
- Mobile (#19): the whole panel works on phones: one column, no sideways
  scrolling, 44 px touch targets, editors as full-screen sheets.

### Magyar

- Naptár (#17, #19): nap, 3 nap és hét nézet Google Naptár-szerű
  megjelenéssel; az utoljára választott nézetet felhasználónként megjegyzi,
  telefonon napi nézettel indul.
- Csak ez az alkalom vagy a teljes sorozat (#17): a naptárban egy rutinra
  kattintva Outlook-szerűen rákérdez. A „csak ez az alkalom” az adott dátumra
  szóló teljes rutinszerkesztőt nyitja meg (idők, színzónák, checkpointok
  jutalomsávokkal, feladatok, gyerekek), a módosított részek jelölve,
  „Visszaállítás eredetire”, minden naplózva; maga a rutin nem változik. Üres
  helyre kattintva csak arra a napra szóló rutin vehető fel. A múltbeli napok
  csak olvashatók. A Ma oldalon ugyanez a szerkesztő mára érhető el.
- Húzás a naptárban (#17): a rutin áthúzható az adott napon (a checkpointok
  vele mozognak), a teteje vagy alja húzásával a kezdés vagy a vége
  módosul; 5 perces rács, élő időcímke, Visszavonás; érintőképernyőn hosszú
  nyomással indul.
- Rutinszínek (#18): minden rutin saját naptárszínt kap (paletta és
  színválasztó, új rutinnál automatikusan eltérő szín, figyelmeztetés hasonló
  színnél), külön a gomb időívének alapszínétől. A módosított alkalmakat jelvény
  és szaggatott keret jelöli, nem csak szín.
- Mobil (#19): az egész panel jól használható telefonon: egy oszlop, nincs
  vízszintes görgetés, 44 px-es érintési célok, a szerkesztők teljes képernyős
  lapként nyílnak.

## [0.5.0] - 2026-10-07

### English

- Day templates (e.g. weekday, weekend, holiday) say which routines run on a
  day; each weekday can have a default template and a single date its own
  (also on the Today page and with the `kis_segito.set_today_template`
  action). Days without a template use each routine's own days.
- Home Assistant entities: `sensor.kis_segito` (active/idle, day template,
  running routines, next checkpoint), one sensor per child (wallet balance
  with piggy bank, streak, routine progress, next checkpoint, last
  transaction) and `calendar.kis_segito` with the routines as events.
- Own pictures: a photo for each child and a picture for each reward,
  uploaded in the panel (Home Assistant image_upload); the knob downloads
  them from Home Assistant in the background and shows the icon until then.
- Knob: interest paid while the child was away shows a piggy badge on the
  child selector; opening the piggy bank drops exactly that many tokens in.
- Knob (full animations): now and then a token rolls off the pile and a
  cartoon hand puts it back; any input cancels it.
- Notifications through scripts (#15): a rule can target a script, with the
  script fields for message and title and fixed values for the others; only
  scripts with the configured label are listed; a Send test button.
- History (#16): every entry shows its own booked amount; the effective
  value of a corrected entry is in its expandable chain.

### Magyar

- Napsablonok (pl. hétköznap, hétvége, szünet): megmondják, mely rutinok
  futnak egy napon; a hét napjaihoz alapértelmezett sablon, egy-egy dátumhoz
  saját sablon rendelhető (a Ma oldalon és a `kis_segito.set_today_template`
  művelettel is). Sablon nélküli napokon minden rutin a saját napjait követi.
- Home Assistant entitások: `sensor.kis_segito` (aktív/tétlen, napsablon,
  futó rutinok, következő checkpoint), gyerekenként egy szenzor (pénztárca
  egyenlege, persely, sorozat, rutin-előrehaladás, következő checkpoint,
  utolsó tranzakció) és a rutinokat eseményként mutató `calendar.kis_segito`.
- Saját képek: minden gyerekhez fénykép, minden jutalomhoz kép tölthető fel
  a panelen (Home Assistant image_upload); a gomb a háttérben letölti őket,
  addig az ikont mutatja.
- Gomb: ha a gyerek távollétében kamat érkezett, a gyerekválasztón persely-
  jelvény látszik; a persely megnyitásakor pontosan annyi zseton hullik bele.
- Gomb (teljes animáció): időnként egy zseton legurul a kupacról, és egy
  rajzolt kéz visszateszi; bármilyen mozdulat megszakítja.
- Értesítés scripten keresztül (#15): egy szabály célpontja script is lehet,
  megadható, melyik mezőbe menjen az üzenet és a cím, a többi mezőbe fix
  érték; csak a beállított címkéjű scriptek jelennek meg; „Teszt küldése” gomb.
- Előzmények (#16): minden bejegyzés a saját könyvelt összegét mutatja; a
  módosított bejegyzés érvényes értéke a kinyitható láncban látszik.

## [0.4.0] - 2026-10-07

### English

- Calendar: a week view in the panel with the routines as blocks at their
  times, checkpoints, a child filter and one-day changes highlighted.
- Modify today (on the Today page): skip a routine or shift all its times for
  today only; the routine itself stays unchanged; changes are logged.
- Notification rules: any number of rules, each with a Home Assistant notify
  target, event types and children; texts in English and Hungarian.
- History: filter by child, type, account and date range, and search by name,
  note or #number (#13). Entry references (#n) are links that jump to the
  entry and highlight it, also via a link like …/kis-segito#tx-12; corrected
  entries show their original amount; old/new amounts of corrections made
  before 0.3.1 are computed from the ledger (#14).
- Piggy bank on the knob: turning chooses how many tokens move (clockwise into
  the piggy bank, anticlockwise out), pressing moves exactly that many.
- The knob returns to the child selector after the inactivity time set in the
  panel.
- Settings: JSON export of all settings and the full token history.
- The panel shows a reload bar when the browser still runs an older copy after
  an update.
- Configuration audit log (settings, one-day changes, notification rules).

### Magyar

- Naptár: heti nézet a panelen, a rutinok idő szerinti blokkokként, a
  checkpointokkal, gyerekszűrővel; az egynapos módosítások kiemelve.
- Mai nap módosítása (a Ma oldalon): egy rutin mára kihagyható, vagy minden
  időpontja eltolható; maga a rutin nem változik; a módosítások naplózódnak.
- Értesítési szabályok: tetszőleges számú szabály, mindegyik saját Home
  Assistant értesítési célponttal, eseménytípusokkal és gyerekekkel; magyar és
  angol szövegek.
- Előzmények: szűrés gyerek, típus, számla és dátum szerint, keresés névre,
  megjegyzésre vagy #számra (#13). A bejegyzés-hivatkozások (#n) linkek, a
  célbejegyzésre ugranak és kiemelik, …/kis-segito#tx-12 formájú linkkel is; a
  módosított bejegyzés az eredeti összeget is mutatja; a 0.3.1 előtti
  korrekciók régi és új összegét a napló alapján számolja (#14).
- Persely a gombon: tekeréssel választható ki, hány zseton menjen (óramutató
  irányában a perselybe, visszafelé onnan ki), a gombnyomás pontosan annyit mozgat.
- A gomb a panelen beállított inaktivitási idő után tér vissza a
  gyerekválasztóhoz.
- Beállítások: JSON-export az összes beállításról és a teljes zseton-előzményről.
- A panel frissítés-sávot mutat, ha a böngésző frissítés után még a régi
  változatot futtatja.
- Beállítás-napló (beállítások, egynapos módosítások, értesítési szabályok).

## [0.3.2] - 2026-10-07

### English

- Once a child's piggy bank is unlocked, the piggy-bank unlock reward no
  longer appears in that child's shop on the knob at all (#11; replaces the
  "owned" check of 0.3.1).

### Magyar

- Ha a gyerek perselye már fel van oldva, a perselyfeloldó jutalom egyáltalán
  nem jelenik meg az ő boltjában a gombon (#11; a 0.3.1 „megvan” pipája
  helyett).

## [0.3.1] - 2026-10-07

### English

- Piggy-bank unlock reward (#11): once the piggy bank is unlocked, the knob
  shows the reward with a check ("owned") instead of a lock and a price; the
  lock now only means "not enough tokens". A new child's piggy bank starts
  locked when a reward can unlock it (open when no such reward exists).
- History (#12): every entry has a sequence number. Corrections and reversals
  are entries of their own that point to the original ("Correction of #1:
  +3 → +5", "Reversal of #2") with who, when and an optional note; the
  original lists its corrections and its reversal and shows the effective
  amount.

### Magyar

- Perselyfeloldó jutalom (#11): ha a persely már fel van oldva, a gombon a
  jutalom pipával („megvan”) látszik lakat és ár helyett; a lakat már csak azt
  jelenti, hogy nincs elég zseton. Új gyereknél a persely alapból zárva van, ha
  van feloldó jutalom (ha nincs, nyitva).
- Előzmények (#12): minden bejegyzés sorszámot kap. A módosítás és a sztornó
  önálló bejegyzés, amely az eredetire hivatkozik („#1 korrekciója: +3 → +5”,
  „#2 sztornója”), azzal, hogy ki, mikor és opcionális megjegyzéssel; az eredeti
  bejegyzés felsorolja a módosításait és a sztornóját, és az érvényes összeget
  mutatja.

## [0.3.0] - 2026-10-07

### English

Real data: the knob now shows what is set up in Home Assistant instead of test
data (the test data remains only until Home Assistant first sends data).

- Home Assistant panel with Today, Children, Routines, Rewards, Tokens, History
  and Settings pages:
  - children: name, birth date, colour (presets, colour picker, hint when it is
    close to a time-zone colour), avatar, knob assignment, piggy bank, order;
  - routines: days of the week, start and end, children, colour zones,
    checkpoints (shared or per child, reward bands by how early, counts for the
    streak), tasks linked to checkpoints; one-click example routines;
  - rewards: icon, price shown as a token pile, piggy-bank unlock; examples;
  - tokens: manual bonus and debit; history with reversal and amount change;
  - settings: language, animations, daily streak, weekly piggy-bank interest,
    knobs with the avatars of their children.
- Append-only token ledger (wallet and piggy bank): balances are always the
  sum of the history; reversals and corrections never delete anything.
- Checkpoint rewards by time bands, daily streak (evaluated after midnight,
  bonus at the target), weekly compound piggy-bank interest with optional
  minimum and maximum.
- Device-child assignment: a child belongs to at most one knob; on a knob with
  assigned children the others are shown greyed and locked; a knob without
  children (or with all of them) works for everyone.
- The knob gets its data from Home Assistant and reports completed tasks and
  bought rewards back; each is booked at most once, even after a reconnect.
- On the knob: the function carousel lists the child's routines of today; the
  time track shows the routine's colour zones, shared checkpoints on the outer
  and the child's own on the inner track, and the reward available now.
- Home Assistant actions for automations (`kis_segito.complete_task`,
  `complete_checkpoint`, `adjust_tokens`, `redeem_reward`, `piggy_deposit`,
  `piggy_withdraw`, `reverse_transaction`) and the `kis_segito_event` event
  (docs/automations.md).
- Every icon of the set is now available on the knob and in the panel.

### Magyar

Valódi adatok: a knob most a Home Assistantben beállított adatokat mutatja a
tesztadatok helyett (a tesztadatok csak addig látszanak, amíg a Home Assistant
először adatot nem küld).

- Home Assistant panel Ma, Gyerekek, Rutinok, Jutalmak, Zsetonok, Előzmények és
  Beállítások oldallal:
  - gyerekek: név, születési dátum, szín (előre megadott színek, színválasztó,
    figyelmeztetés, ha közel van egy időzóna-színhez), avatar, gomb-hozzárendelés,
    persely, sorrend;
  - rutinok: a hét napjai, kezdés és vége, gyerekek, színzónák, checkpointok
    (közös vagy gyerekenkénti, jutalomsávok aszerint, mennyivel előtte, beleszámít-e
    a sorozatba), checkpointokhoz kötött feladatok; példa-rutinok egy gombnyomásra;
  - jutalmak: ikon, zsetonkupacként mutatott ár, perselyfeloldás; példák;
  - zsetonok: kézi jóváírás és levonás; előzmények visszavonással és
    összegmódosítással;
  - beállítások: nyelv, animációk, napi sorozat, heti perselykamat, a gombok a
    hozzájuk rendelt gyerekek avatarjaival.
- Csak bővülő zsetonnapló (pénztárca és persely): az egyenleg mindig az
  előzmények összege; visszavonás és módosítás soha nem töröl semmit.
- Checkpoint-jutalom időbeli sávok szerint, napi sorozat (éjfél után értékelve,
  a cél elérésekor jutalommal), heti kamatos perselykamat opcionális minimummal
  és maximummal.
- Eszköz–gyerek hozzárendelés: egy gyerek legfeljebb egy gombhoz tartozik; ha egy
  gombhoz vannak gyerekek rendelve, a többiek szürkén, zárolva látszanak; a gyerek
  nélküli (vagy mindenkihez rendelt) gomb mindenkinek működik.
- A knob a Home Assistanttől kapja az adatait, és visszajelzi az elvégzett
  feladatokat és a beváltott jutalmakat; mindegyik legfeljebb egyszer
  könyvelődik, újracsatlakozás után is.
- A knobon a funkció-körhinta a gyerek mai rutinjait mutatja; az időív a rutin
  színzónáit, a közös checkpointokat a külső, a gyerek sajátjait a belső íven, és az
  éppen elérhető jutalmat.
- Home Assistant műveletek automatizáláshoz (`kis_segito.complete_task`,
  `complete_checkpoint`, `adjust_tokens`, `redeem_reward`, `piggy_deposit`,
  `piggy_withdraw`, `reverse_transaction`) és a `kis_segito_event` esemény
  (docs/automations.md).
- Az ikonkészlet minden ikonja elérhető a knobon és a panelen.

## [0.2.2] - 2026-10-07

### English

- The time track is shown on every screen, above the content, on a band in
  the background colour with a soft inner edge, so sliding carousel items do
  not disturb it: the shared outer track (colour zones, elapsed time, now
  marker, global checkpoints) and the selected child's inner track (also on
  the child carousel, following the centred child).
- The top gap shows the brand mark on every screen; on a routine it shows
  the reward available now instead. Screen content moved inside the track.
- The child carousel slides smoothly: each slot (avatar, token pile, number)
  is rendered into one image (#10).
- Language changes apply live (texts, brand mark, boot screen) without a
  restart, and are written to flash right away.
- The offline marker moved to the right of the top gap.
- Screen saver against burn-in: the backlight dims after 60 s and switches
  off after 120 s without knob input; any input wakes it without acting.
  "Screen dim after" and "Screen off after" are adjustable from Home
  Assistant (0 disables a step).
- Whenever the backlight is off (switch, screen saver, automation), the screen
  content is black and drawing pauses; it comes back when the backlight is on.

### Magyar

- Az időív minden képernyőn látszik, a tartalom fölött, egy háttérszínű,
  átmenetes peremű sávon, így a csúszó körhinta-elemek nem zavarják: a közös
  külső ív (színzónák, eltelt idő, „most” jelölő, közös checkpointok) és a
  kiválasztott gyerek belső íve (a gyerek-körhintán is, a középső gyerekhez
  igazodva).
- A felső résben minden képernyőn a márkajel látszik; rutin közben helyette
  az éppen elérhető jutalom. A képernyők tartalma az íven belülre került.
- A gyerek-körhinta egyenletesen csúszik: minden hely (avatar, zsetonkupac,
  szám) egyetlen képpé renderelődik (#10).
- A nyelvváltás élőben érvényesül (feliratok, márkajel, indítóképernyő)
  újraindítás nélkül, és azonnal flash-be íródik.
- A kapcsolat-hiány jelzése a felső rés jobb oldalára került.
- Képernyővédő a beégés ellen: 60 s tétlenség után a háttérvilágítás
  elhalványul, 120 s után kikapcsol; bármilyen tekerés vagy gombnyomás
  felébreszti, de nem lép vele. A „Screen dim after” és „Screen off after” idő
  a Home Assistantből állítható (a 0 kikapcsolja az adott lépést).
- Ha a háttérvilágítás bármilyen módon kikapcsol (kapcsoló, képernyővédő,
  automatizmus), a kijelző tartalma fekete, és a rajzolás szünetel;
  bekapcsoláskor visszajön.

## [0.2.1] - 2026-10-07

### English

- Boot screen: the Kis Segítő brand mark in the middle, the loading text below
  it, the balls bouncing behind them. The brand mark is Hungarian when the
  language is Hungarian and English ("Little Helper") otherwise. The language
  is kept in flash for the next boot.
- The routine screen's top gap uses the same language-specific brand mark.
- Logo at the top of the README (Hungarian and English section).

### Magyar

- Indítóképernyő: középen a Kis Segítő márkajel, alatta a betöltés felirat,
  mögöttük pattognak a labdák. Magyar nyelv esetén a magyar, minden más
  nyelven az angol („Little Helper”) márkajel látszik. A nyelvet a knob a
  következő indításhoz flash-ben tárolja.
- Az időív felső résében is ez a nyelvfüggő márkajel látszik.
- Logó a README tetején (a magyar és az angol részben is).

## [0.2.0] - 2026-10-06

### English

First version of the child UI on the knob, with built-in test data (Home
Assistant data follows in a later version):

- Child carousel (infinite) with avatar and a real token pile of exactly the
  wallet balance; large balances spread sideways and "flow" off the screen.
  The last selected child is remembered across reboots.
- Function carousel per child: morning and evening routine, rewards, piggy bank
  (when unlocked), tokens and streak.
- Routine screen: open time track from 11 to 1 o'clock with the future colour
  zones visible from the start, elapsed time dimmed, checkpoint markers on the
  outer and inner track, the reward available now in the top gap, the current
  task large and the others on a curved timeline (done on the left, grey).
  Completing a task bounces and checks it; finishing the routine celebrates.
- Reward store carousel with prices shown as token piles, locked rewards
  greyed out, and an X/✓ confirmation with a ring around the selected choice;
  the exact number of spent tokens fly away.
- Short press selects, long press goes back one level; after 60 s without input
  the knob returns to the child carousel. Without a Home Assistant connection an
  offline marker is shown and token transactions are refused.
- Animation level (full / reduced / off) as a setting in Home Assistant.
- Loading screen balls are now layered images: a recoloured round ball that
  briefly turns into a dented ball on impact (the dent faces the contact point),
  and a highlight that never rotates or deforms. The highlight position is
  adjustable with the `ball_highlight_dx` / `ball_highlight_dy` substitutions.
- Language setting in the Kis Segítő panel: "Automatic" (the Home Assistant
  language, English when there is no translation) or any available
  translation. It applies to the knobs and to the panel; the list comes from the
  translation files.
- The icons are temporary sketches for now.

### Magyar

A knob gyerekfelületének első változata, beépített tesztadatokkal (a Home
Assistant adatai egy későbbi verzióban jönnek):

- Gyerek-körhinta (végtelen) avatarral és valódi zsetonkupaccal, pontosan a tárca
  egyenlegével; nagy egyenlegnél a kupac szétterül, majd „lefolyik” a
  kijelzőről. Az utoljára kiválasztott gyerek újraindítás után is megmarad.
- Gyerekenkénti funkció-körhinta: reggeli és esti rutin, jutalmak, persely (ha
  feloldották), zsetonok és sorozat.
- Rutinképernyő: nyitott időív 11 órától 1 óráig, a jövőbeli színzónák az
  elejétől látszanak, az eltelt idő elhalványul, checkpoint-jelölők a külső és a
  belső íven, a most járó jutalom a felső résben, az aktuális feladat nagyban, a
  többi egy íves idővonalon (a kész feladatok balra, szürkén). Feladat
  teljesítésekor pattanás és pipa, a rutin végén ünneplés.
- Jutalombolt-körhinta, az árak zsetonkupacként, a nem megfizethető jutalmak
  szürkén, X/✓ megerősítés gyűrűvel a kiválasztott elem körül; a pontos számú
  elköltött zseton elrepül.
- Rövid nyomás: kiválasztás, hosszú nyomás: egy szinttel vissza; 60 s tétlenség
  után vissza a gyerek-körhintára. Home Assistant-kapcsolat nélkül offline jelzés
  látszik, és a zseton-tranzakciók le vannak tiltva.
- Animációs szint (teljes / csökkentett / ki) beállításként a Home Assistantben.
- A betöltőképernyő labdái rétegzett képek: színezett kerek labda, amely
  ütközéskor rövid időre horpadt labdára vált (a horpadás az ütközési pont felé
  néz), és egy csillanás, amely sosem forog és nem torzul. A csillanás helye a
  `ball_highlight_dx` / `ball_highlight_dy` helyettesítésekkel állítható.
- Nyelvválasztó a Kis Segítő panelen: „Automatikus” (a Home Assistant nyelve,
  fordítás hiányában angol) vagy bármelyik elérhető fordítás. A knobokra és a
  panelre is érvényes; a lista a fordítási fájlokból jön.
- Az ikonok egyelőre ideiglenes vázlatok.

## [0.1.11] - 2026-10-06

### English

- Loading screen: five bouncing balls (one more), and they now also bounce off
  each other, not only off the round edge.

### Magyar

- Betöltőképernyő: öt pattogó labda (eggyel több), és most már egymásról is
  visszapattannak, nem csak a kerek szélről.

## [0.1.10] - 2026-10-06

### English

- Fix: the display stayed blank on USB chargers and only worked with a PC (#8).
  The cause was ESP-IDF's secondary console on the native USB port. It is now
  off, and the serial log moved to UART0 (GPIO43/44); `logger_baud_rate: "0"`
  turns it off and frees UART0 for other hardware. Logs remain available over
  the network.
- Improv over USB is removed (it needs the native USB port); Wi-Fi is set up
  through the knob's own access point (captive portal).
- The `no-usb-console.yaml` diagnostic package is removed, as this is now the
  default.
- The loading screen shows colourful bouncing balls instead of the spinner
  (#9). They bounce off the round edge with a small squash; the animation stops
  and its timer is freed once the content arrives.

### Magyar

- Javítás: töltőről a kijelző üres maradt, csak számítógépről működött (#8). Az
  ok az ESP-IDF másodlagos konzolja volt a natív USB-porton. Ez most ki van
  kapcsolva, a soros napló az UART0-ra (GPIO43/44) került; a
  `logger_baud_rate: "0"` kikapcsolja, és felszabadítja az UART0-t más
  hardvernek. A napló hálózaton továbbra is elérhető.
- Az USB-s Improv kikerült (a natív USB-portot használná); a WiFi a knob saját
  hozzáférési pontján (captive portal) állítható be.
- A `no-usb-console.yaml` diagnosztikai package kikerült, mert ez lett az
  alapállapot.
- A betöltőképernyőn a forgó jel helyett színes pattogó labdák vannak (#9). A
  kerek kijelző szélén pattannak vissza, kicsit összenyomódva; a tartalom
  megérkezésekor az animáció leáll, és az időzítője felszabadul.

## [0.1.9] - 2026-10-06

### English

- Diagnostic packages for the display staying blank on USB chargers (#8, still
  open), in `esphome/diagnostics/`: `no-usb-console.yaml` (native USB port
  unused, logs over the network only), `jtag-pins.yaml` (GPIO39–42 reset to
  plain GPIO before the RGB panel starts) and `verbose-display-log.yaml`
  (verbose display/LVGL logs). See `docs/hardware.md`. The normal firmware is
  unchanged.

### Magyar

- Diagnosztikai package-ek ahhoz a hibához, hogy töltőről a kijelző nem
  működik (#8, még nyitott), az `esphome/diagnostics/` mappában:
  `no-usb-console.yaml` (a natív USB-port nincs használatban, napló csak
  hálózaton), `jtag-pins.yaml` (a GPIO39–42 sima GPIO-ra állítása az RGB-panel
  indulása előtt) és `verbose-display-log.yaml` (részletes kijelző/LVGL-napló).
  Lásd: `docs/hardware.md`. A normál firmware nem változott.

## [0.1.8] - 2026-10-06

### English

- The encoder sensitivity is adjustable from Home Assistant (#7): a new
  **Encoder clicks per step** setting (1–5, default 1) on the device, kept
  across reboots. The encoder now counts at full resolution and the firmware
  turns clicks into steps. The `encoder_resolution` substitution is replaced by
  `encoder_counts_per_click` (default `"2"`) for other encoders. The raw
  encoder counter is no longer exposed to Home Assistant.

### Magyar

- Az enkóder érzékenysége a Home Assistantből állítható (#7): új **Encoder
  clicks per step** beállítás (1–5, alapból 1) az eszközön, újraindítás után is
  megmarad. Az enkóder most teljes felbontással számol, a kattanásokat a
  firmware alakítja lépésekké. Az `encoder_resolution` substitution helyett
  más enkóderhez az `encoder_counts_per_click` állítható (alapból `"2"`). A nyers
  enkóderszámláló már nem jelenik meg a Home Assistantben.

## [0.1.7] - 2026-10-06

### English

- Fix: one encoder click is now one step; `encoder_resolution` defaults to `"2"`
  (#7). The README explains how to tune it for other encoders.
- Display diagnostics for the faint stripes on black (#6, still open):
  `display-test.yaml` can show solid black, white, grey, very dark grey or a
  grey ramp (`display_test_pattern`), and the new `display_drive_strength`
  substitution sets the drive strength of the RGB bus pins. COLMOD 0x77 can be
  tested with `display_colmod: "0x77"`.

### Magyar

- Javítás: egy kattanás most egy lépés; az `encoder_resolution` alapértéke `"2"`
  (#7). A README leírja, hogyan hangolható más enkóderhez.
- Kijelző-diagnosztika a fekete háttér halvány csíkjaihoz (#6, még nyitott): a
  `display-test.yaml` teli fekete, fehér, szürke, nagyon sötét szürke képet vagy
  szürke átmenetet tud mutatni (`display_test_pattern`), és az új
  `display_drive_strength` substitution az RGB-busz lábainak meghajtóerejét
  állítja. A COLMOD 0x77 a `display_colmod: "0x77"` beállítással próbálható.

## [0.1.6] - 2026-10-06

### English

- Fix attempt for wrong mid-tone colours on the MD80E (#4). The panel init now
  follows the factory demo exactly: init table, 120 ms, DISPON, with **no
  COLMOD**, so the panel stays in its 24-bit power-on mode, which matches the
  board wiring. ESPHome's own COLMOD/MADCTL/INVOFF are no longer sent (the
  sequence is replaced at boot, before the display starts).
- New substitution `display_colmod` (`"0"` = none, default; `"0x55"` restores
  the v0.1.5 behaviour). It replaces `display_pixel_mode`; the no-longer-used
  `display_color_order` and `display_invert_colors` are removed.
- Fix: the encoder counted down when turned clockwise; A/B pins swapped (#5).

### Magyar

- Javítási kísérlet a rossz középtónusokra az MD80E-n (#4). A panel initje most
  pontosan a gyári demót követi: init tábla, 120 ms, DISPON, **COLMOD nélkül**,
  így a panel a bekapcsolási 24 bites módjában marad, ami egyezik a lap
  bekötésével. Az ESPHome saját COLMOD/MADCTL/INVOFF parancsai már nem mennek
  ki (a szekvencia bootkor, a kijelző indulása előtt cserélődik).
- Új substitution: `display_colmod` (`"0"` = nincs, alapértelmezett; `"0x55"`
  a v0.1.5 viselkedését adja vissza). Ez váltja a `display_pixel_mode`-ot; a
  használaton kívüli `display_color_order` és `display_invert_colors` kikerült.
- Javítás: az enkóder jobbra forgatásra csökkent; az A/B láb felcserélve (#5).

## [0.1.5] - 2026-10-06

### English

- Fix: correct colours on the MD80E display (#3). The cause was the COLMOD the
  display driver sends after the init table: 18-bit (0x66) breaks the colours
  on this panel, 16-bit (0x55) gives a correct picture. `display_pixel_mode` now
  defaults to `16bit`.
- The v0.1.4 change (sending the init with custom bit-banged SPI) is reverted:
  the init already reached the panel. The board definition is the tested v0.1.3
  one again (GC9503 table, 26 MHz, non-inverted PCLK, 8/20/40, 8/20/50).

### Magyar

- Javítás: helyes színek az MD80E kijelzőn (#3). Az ok a kijelző-meghajtó által
  az init tábla után küldött COLMOD volt: a 18 bit (0x66) elrontja a színeket
  ezen a panelen, a 16 bit (0x55) helyes képet ad. A `display_pixel_mode`
  alapértéke most `16bit`.
- A v0.1.4 változtatása (az init saját, bit-bang SPI-vel) visszavonva: az init
  eddig is eljutott a panelhez. A lapdefiníció újra a tesztelt v0.1.3-as (GC9503
  tábla, 26 MHz, nem invertált PCLK, 8/20/40, 8/20/50).

## [0.1.4] - 2026-10-06

### English

- Fix attempt for the MD80E display (#3): the panel init is now sent exactly the
  way the vendor code does it (bit-banged 9-bit 3-wire SPI with idle-high lines
  at about 50 kHz, no reset pulse, 120 ms, DISPON, then GPIO12/13 released) from
  an `on_boot` step before the display starts. The `mipi_rgb` display uses
  ESPHome's generic `RPI` model and sends no init of its own.
- New diagnostic substitution `display_init_test_invert`: sends INVON after the
  init table, so a colour inversion proves the init reaches the panel.
- Removed the substitutions that no longer have an effect
  (`display_pixel_mode`, `display_color_order`, `display_invert_colors`).

### Magyar

- Javítási kísérlet az MD80E kijelzőhöz (#3): a panel initje most pontosan úgy
  megy ki, mint a gyártói kódban (bit-bang 9 bites 3-vezetékes SPI, magas
  nyugalmi szint, kb. 50 kHz, reset-impulzus nélkül, 120 ms, DISPON, utána a
  GPIO12/13 felszabadítása), egy `on_boot` lépésből a kijelző indulása előtt. A
  `mipi_rgb` kijelző az ESPHome általános `RPI` modelljét használja, saját init
  nélkül.
- Új diagnosztikai substitution: `display_init_test_invert`. Az init tábla után
  INVON-t küld, így ha a színek megfordulnak, az init eljut a panelhez.
- Kikerültek a már hatástalan substitutionök (`display_pixel_mode`,
  `display_color_order`, `display_invert_colors`).

## [0.1.3] - 2026-10-06

### English

- Fix: red was missing and the test card was wrong on the MD80E (#2). The panel
  has a GC9503CV controller; the display now uses the vendor's GC9503 init
  table (the one the factory demo runs) with the vendor timings (26 MHz,
  non-inverted PCLK, 8/20/40, 8/20/50). The previous ST7701-style table stays
  available with `display_controller: st7701`.

### Magyar

- Javítás: az MD80E-n hiányzott a piros szín, és hibás volt a tesztkép (#2). A
  panel vezérlője GC9503CV; a kijelző most a gyártói GC9503 init táblát
  használja (ezt futtatja a gyári demó is), a gyártói időzítésekkel (26 MHz,
  nem invertált PCLK, 8/20/40, 8/20/50). Az előző, ST7701-es tábla
  `display_controller: st7701` beállítással továbbra is elérhető.

## [0.1.2] - 2026-10-06

### English

- Fix: the MD80E (non-touch) panel showed only stripes. The display now uses
  the vendor's MD80E ESP-IDF example setup instead of ESPHome's built-in
  `UEDX48480021-MD80ET` model: 26 MHz non-inverted PCLK, porches 8/20/40 and
  8/20/50, the vendor init sequence, and the vendor's PSRAM/cache settings.
  All timing values are substitutions, so they can be tuned from the device
  config (#1).
- New `esphome/display-test.yaml`: the same board without LVGL, showing
  ESPHome's test card, for checking the panel on its own.

### Magyar

- Javítás: az MD80E (nem érintős) kijelzőn csak csíkok látszottak. A kijelző
  most a gyártói MD80E ESP-IDF példa beállításait használja az ESPHome beépített
  `UEDX48480021-MD80ET` modellje helyett: 26 MHz, nem invertált PCLK, 8/20/40 és
  8/20/50 porch, a gyártói init szekvencia, valamint a gyártói PSRAM/cache
  beállítások. Minden időzítés substitution, így az eszközkonfigból hangolható (#1).
- Új `esphome/display-test.yaml`: ugyanaz a lap LVGL nélkül, az ESPHome
  tesztképével (test card), a kijelző önálló ellenőrzéséhez.

## [0.1.1] - 2026-10-06

### English

- Knob: loading screen from boot until Home Assistant sends the content
  (spinner; place for a future logo). Its text ("Loading...") is kept in flash
  in the last language received from Home Assistant, so it is shown in that
  language after a power cut too. Empty before the first connection.

### Magyar

- Knob: betöltőképernyő a bekapcsolástól addig, amíg a Home Assistant el nem
  küldi a tartalmat (forgó jel; később ide kerül a logó). A felirata
  („Betöltés...”) a Home Assistanttől utoljára kapott nyelven a flash-ben
  marad, így áramszünet után is ezen a nyelven jelenik meg. Az első
  csatlakozás előtt üres.

## [0.1.0] - 2026-10-06

### English

First testable skeleton.

- **ESPHome firmware** (`esphome/kis-segito.yaml`), usable as a package: ST7701S
  480×480 display (built-in `UEDX48480021-MD80ET` model), dimmable backlight,
  rotary encoder, push button, and an LVGL test screen: turning changes a number,
  pressing gives visual feedback. On-screen texts come from Home Assistant in its
  language (`set_ui_strings` API action); fonts cover Latin, Greek and Cyrillic.
- **Home Assistant integration** `kis_segito` (HACS): config flow that links an
  ESPHome knob, an empty "Kis Segítő" sidebar panel, versioned storage, English
  and Hungarian translations. Sends the knob texts on connect and on language change.
- Each release has the ready-made factory and OTA firmware attached.

### Magyar

Első, tesztelhető váz.

- **ESPHome firmware** (`esphome/kis-segito.yaml`), package-ként behúzható:
  ST7701S 480×480 kijelző (beépített `UEDX48480021-MD80ET` modell), dimmelhető
  háttérvilágítás, forgó enkóder, nyomógomb és LVGL tesztképernyő: forgatásra
  változó szám, nyomásra visszajelzés. A kijelző szövegeit a Home Assistant küldi
  a saját nyelvén (`set_ui_strings` API action); a betűkészlet latin, görög és
  cirill betűket tartalmaz.
- **Home Assistant integráció** `kis_segito` (HACS): config flow az ESPHome-os
  knob kiválasztásához, üres „Kis Segítő” oldalsáv-panel, verziózott adattárolás,
  angol és magyar fordítás. Csatlakozáskor és nyelvváltáskor elküldi a knob szövegeit.
- Minden release-hez csatolva van a kész factory és OTA firmware.

[0.2.0]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.2.0
[0.1.11]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.11
[0.1.10]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.10
[0.1.9]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.9
[0.1.8]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.8
[0.1.7]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.7
[0.1.6]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.6
[0.1.5]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.5
[0.1.4]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.4
[0.1.3]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.3
[0.1.2]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.2
[0.1.1]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.1
[0.1.0]: https://github.com/bazsc20ne/kis-segito/releases/tag/v0.1.0
