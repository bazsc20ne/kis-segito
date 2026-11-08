<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Themes / Témák

A theme is the look of Kis Segítő: the colours and fonts of the panel, and the
icons, avatars, backgrounds and logo of the panel, the dashboard cards and the
knobs. Choose one in the panel under **Settings → Theme**. The physical knobs
restart once to switch (after a minute without use).

Under **Settings → Theme → Manage themes** every theme can be switched off (it
is then not offered), and your own themes can be uploaded and deleted.

## Your own theme in three steps

1. **Download the template:** Settings → Theme → Manage themes → *Download the
   template*. The ZIP has a `theme.json`, a short guide and a `pictures`
   folder with every picture Kis Segítő shows, under its file name.
2. **Make it yours:**
   - In `theme.json` set the name (`en` and `hu`); this also gives the theme
     its id, so uploading a theme with the same name again updates it.
   - Replace any pictures in `pictures` with your own, **under the same file
     name**. Delete the ones you do not want to change: those stay the
     built-in pictures. A theme can be just a background and a few icons.
   - If you like, change the colours in `theme.json` (see below).
3. **Upload it:** zip `theme.json` and the pictures (folders inside the ZIP do
   not matter) and choose *Upload a theme*. Home Assistant makes every size
   the panel, the cards and the knobs need. The theme then appears in the
   theme picker.

### Pictures

| Pictures | What they are | Format |
|---|---|---|
| `task_…`, `routine_…`, `reward_…`, `fn_…`, `nav_…`, `checkpoint_flag`, `piggy_large`, `wallet`, `status_…`, `streak_…`, `action_…`, `celebrate_…`, `badge_piggy_plus`, `hand_cartoon` | Icons of tasks, routines, rewards, the knob's functions, the panel's tabs and status signs | Square PNG with a transparent background, 512 × 512 or larger |
| `avatar_00` … `avatar_12` | Children's pictures (`avatar_00`: "no picture yet") | As above; head and shoulders, the face inside the middle 80 % (the knob shows them in a circle) |
| `avatar_13` … `avatar_24` (optional) | A second set of children's pictures; the avatar list then offers 24 | As above |
| `token_coin_front`, `token_coin_tilt_left`, `token_coin_tilt_right` | The token, from the front and turned to each side | As above; simple, it is shown small, in piles |
| `ball_base`, `ball_dent`, `ball_highlight` | The bouncing balls of the knob's loading screen | As above; grey shading only, the knob colours them |
| `brand_mark`, `brand_mark_en` | Round logo: knob loading screen and top bar (Hungarian / other languages) | As above |
| `brand_logo`, `brand_logo_en` | The panel header's logo | PNG with a transparent background, any width |
| `bg_1` … `bg_6` | Backgrounds of the panel and the knobs: `bg_1` … `bg_3` by day, `bg_4` … `bg_6` by night | Square PNG or JPEG, no transparency, 1024 × 1024 or larger |
| `<name>_small` (optional) | A simpler version of a picture for small places | As the picture |

Tips:

- The knob shows icons as small as 28 pixels: bold shapes and outlines work
  best, fine details get lost.
- Keep the middle of a background calm: the knob draws avatars, icons and
  numbers there, and its time ring covers the outer edge.
- No text in the pictures, except the logos.
- Use only pictures you made or may use, without other brands' logos or
  characters.

### Colours

`theme.json` (all parts except the name are optional):

```json
{
  "name": {"en": "Ocean", "hu": "Óceán"},
  "panel": {
    "light": {"--bg": "#F2F6FC", "--accent": "#2C78F0"},
    "dark": {"--bg": "#0A0F24", "--accent": "#7DB2FF"}
  },
  "knob": {"bg": "#1B2140", "track": "#3A4066", "pill": "#0F1330", "number": "#FFE08A"}
}
```

- `panel`: colours of the panel in light and dark mode. The most useful ones:
  `--bg` (page), `--surface` and `--surface-2` (cards), `--ink` (text),
  `--muted` (secondary text), `--line` (borders), `--accent`, `--accent-ink`
  and `--accent-soft` (buttons and highlights). The template lists them with
  the built-in values.
- `knob`: `bg` (screen background without a picture), `track` (time ring),
  `pill` and `number` (the number pills), `deposit` and `withdraw` (piggy
  bank amounts), and `ok`, `warn`, `late` (ring zones).

Colours are `#RRGGBB`. Anything Kis Segítő does not know is ignored.

### Limits

A ZIP up to 150 MB; pictures up to 4096 pixels per side. Own themes are kept in
Home Assistant's configuration folder (`kis_segito/themes`), so updating Kis
Segítő keeps them; they are part of Home Assistant's backups.

## Bundled themes

The bundled style themes are fan-made style homages.

**Disclaimer:** Kis Segítő is not affiliated with, endorsed by or sponsored by The Walt Disney
Company, Disney Enterprises, Inc., Pixar, 20th Television, 20th Century Studios (formerly
Twentieth Century Fox), Warner Bros. Discovery, Turner Entertainment Co. or any other rights
holder. The Simpsons, Frozen, Cars, Toy Story, Planes, Winnie the Pooh, Tom and Jerry and Mickey
Mouse are trademarks of their respective owners. The names are used only
to describe the visual style that a theme is inspired by. All artwork in the themes is
original, and no characters, logos or other elements from the originals are included.

---

# Témák (magyarul)

A téma a Kis Segítő kinézete: a panel színei és betűi, valamint a panel, az
irányítópult-kártyák és a gombok ikonjai, avatarjai, hátterei és logója. A
panelen a **Beállítások → Téma** részen választható. A fizikai gombok a
váltáshoz egyszer újraindulnak (egy perc használaton kívüli idő után).

A **Beállítások → Téma → Témák kezelése** részen bármelyik téma kikapcsolható
(akkor nem jelenik meg a választóban), a saját témák pedig feltölthetők és
törölhetők.

## Saját téma három lépésben

1. **Töltsd le a sablont:** Beállítások → Téma → Témák kezelése → *Sablon
   letöltése*. A ZIP-ben van egy `theme.json`, egy rövid útmutató és egy
   `pictures` mappa a Kis Segítő összes képével, a fájlnevükkel.
2. **Alakítsd a sajátodra:**
   - A `theme.json`-ban add meg a nevet (`en` és `hu`); ebből lesz a téma
     azonosítója is, így ugyanazzal a névvel újra feltöltve a téma frissül.
   - Cseréld le a `pictures` mappa bármelyik képét a sajátodra, **ugyanazzal
     a fájlnévvel**. Amit nem akarsz megváltoztatni, töröld: azok a beépített
     képek maradnak. Egy téma lehet csak egy háttér és néhány ikon is.
   - Ha szeretnéd, változtasd meg a színeket a `theme.json`-ban (lásd fent az
     angol részben a mintát és a színek listáját).
3. **Töltsd fel:** tömörítsd ZIP-be a `theme.json`-t és a képeket (a ZIP-en
   belüli mappák nem számítanak), és válaszd a *Téma feltöltése* gombot. A
   Home Assistant elkészíti a panelhez, a kártyákhoz és a gombokhoz szükséges
   összes méretet. A téma ezután megjelenik a témaválasztóban.

### Képek

- **Ikonok** (`task_…`, `routine_…`, `reward_…`, `fn_…`, `nav_…` és a többi):
  négyzetes PNG átlátszó háttérrel, legalább 512 × 512.
- **Avatarok** (`avatar_00` … `avatar_12`; az `avatar_00` a „még nincs kép”):
  fej és váll, az arc a középső 80%-on belül (a gomb körben mutatja). Egy
  második avatarkészlet is lehet (`avatar_13` … `avatar_24`, nem kötelező):
  ilyenkor az avatarlista 24 avatart kínál.
- **Zseton** (`token_coin_…`): egyszerű, mert kicsiben, kupacban látszik.
- **Labdák** (`ball_…`): a gomb betöltőképernyőjének labdái, csak szürke
  árnyalás, a gomb színezi őket.
- **Logók:** `brand_mark` / `brand_mark_en` (kerek, a gomb betöltőképernyőjén
  és felső sávjában), `brand_logo` / `brand_logo_en` (a panel fejléce,
  bármilyen széles).
- **Hátterek** (`bg_1` … `bg_6`; a `bg_1` … `bg_3` nappali, a `bg_4` … `bg_6`
  éjszakai): négyzetes PNG vagy JPEG, átlátszóság nélkül, legalább
  1024 × 1024. A közepük legyen nyugodt: oda rajzol a gomb, a szélét
  pedig az időgyűrű takarja.
- **`<név>_small`** (nem kötelező): egyszerűbb változat kis helyekre.

Tippek: a gomb az ikonokat akár 28 pixelesen is mutatja, ezért a határozott
formák és körvonalak működnek a legjobban. A képeken ne legyen szöveg (a
logókon kívül). Csak saját vagy felhasználható képet használj, más márkák
logója és szereplői nélkül.

### Korlátok

A ZIP legfeljebb 150 MB, egy kép oldalanként legfeljebb 4096 pixel. A saját
témák a Home Assistant konfigurációs mappájában vannak (`kis_segito/themes`),
így a Kis Segítő frissítése megtartja őket, és a Home Assistant mentéseibe is
bekerülnek.

## Beépített témák

A beépített stílustémák rajongói stílus-tisztelgések.

**Jogi nyilatkozat:** a Kis Segítő nem áll kapcsolatban a The Walt Disney Company, a Disney
Enterprises, Inc., a Pixar, a 20th Television, a 20th Century Studios (korábban Twentieth
Century Fox), a Warner Bros. Discovery, a Turner Entertainment Co. vagy más jogtulajdonos
vállalattal, és azok nem támogatják vagy szponzorálják. A The Simpsons, a Frozen, a Cars, a
Toy Story, a Planes, a Winnie the Pooh, a Tom and Jerry és a Mickey Mouse a jogtulajdonosaik
védjegyei. A nevek csak azt a vizuális stílust jelölik, amelyből egy téma ihletet merít. A
témák minden rajza eredeti: nem tartalmaznak szereplőket, logókat vagy más elemeket az
eredetiekből.
