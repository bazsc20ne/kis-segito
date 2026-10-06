<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Icon set / Ikonkészlet

The custom icons shared by the knob and the Home Assistant panel. Source files go to
`assets/icons/source/` as `<id>.png` (1024×1024, transparent background);
icons marked **small** also need a simplified `<id>_small.png` for the 44 px and smaller
places. `tools/build_device_assets.py` renders every size the knob uses.

A knob és a Home Assistant panel közös, egyedi ikonjai. A forrásfájlok helye az
`assets/icons/source/` mappa, `<id>.png` (1024×1024, átlátszó háttér) néven;
a **small** jelölésűekhez egy egyszerűsített `<id>_small.png` is kell a 44 px-es és kisebb
helyekre.

## Márka

A logó és a márkajel. A logóban lehet felirat, minden más ikonban ne legyen szöveg.

| id | Név | Leírás | Knob (px) | HA | Fájlok |
|---|---|---|---|---|---|
| `brand_logo` | Teljes logó | Napocska karakter + „Kis Segítő” felirat, a teljes márkajel. | 280×280 | SVG / 512 | `brand_logo.png` |
| `brand_mark` | Kis márkajel | A logó napocskája felirat nélkül, nagyon egyszerűsítve. Kis méreten is olvasható legyen: vastag körvonal, kevés részlet. | 52×52 | — | `brand_mark.png` |
| `brand_app_icon` | Integráció ikon | Négyzetes alkalmazásikon a HA integrációlistához és a HACS-hoz. Ez a jelenlegi ideiglenes ikon helyére kerül. | — | 256 és 512 PNG | `brand_app_icon.png` |

## Funkciókörhinta és rutinok

A gyerek funkciókörhintájának nagy elemei. Egy rutin ikonját a szülő választja ki a HA-ban.

| id | Név | Leírás | Knob (px) | HA | Fájlok |
|---|---|---|---|---|---|
| `fn_rewards` | Jutalmak | Ajándékdoboz masnival. | 180, 110 | SVG / 96 | `fn_rewards.png` |
| `fn_piggy` | Persely | Rózsaszín malacpersely, felette egy zseton. | 180, 110 | SVG / 96 | `fn_piggy.png` |
| `fn_tokens` | Zsetonok / haladás | Kisebb zsetonkupac csillaggal. | 180, 110 | SVG / 96 | `fn_tokens.png` |
| `routine_morning` | Reggeli rutin | Felkelő nap a horizonton. | 180, 110, 44 | SVG / 96 | `routine_morning.png` + `routine_morning_small.png` (small) |
| `routine_evening` | Esti rutin | Holdsarló csillagokkal. | 180, 110, 44 | SVG / 96 | `routine_evening.png` + `routine_evening_small.png` (small) |
| `routine_generic` | Általános rutin | Csíptetős tábla három pipálható sorral. | 180, 110, 44 | SVG / 96 | `routine_generic.png` + `routine_generic_small.png` (small) |

## Feladatok

A feladatképernyő nagy középső ikonja és a lenti félköríves idővonal kis ikonjai. Checkpointként a gyűrűn is megjelenhetnek.

| id | Név | Leírás | Knob (px) | HA | Fájlok |
|---|---|---|---|---|---|
| `task_wake_up` | Felkelés | Csörgő ébresztőóra. | 180, 44, 36, 30 | SVG / 96 | `task_wake_up.png` + `task_wake_up_small.png` (small) |
| `task_clothes` | Öltözködés | Póló (általános ruha). | 180, 44 | SVG / 96 | `task_clothes.png` + `task_clothes_small.png` (small) |
| `task_pants` | Nadrág | Hosszú nadrág. | 180, 44 | SVG / 96 | `task_pants.png` + `task_pants_small.png` (small) |
| `task_socks` | Zokni | Pár zokni, két színben. | 180, 44 | SVG / 96 | `task_socks.png` + `task_socks_small.png` (small) |
| `task_breakfast` | Reggeli | Tál müzlivel/gyümölccsel, kanállal. | 180, 44, 36, 30 | SVG / 96 | `task_breakfast.png` + `task_breakfast_small.png` (small) |
| `task_toothbrush` | Fogmosás | Fogkefe fogkrémmel és buborékokkal. | 180, 44 | SVG / 96 | `task_toothbrush.png` + `task_toothbrush_small.png` (small) |
| `task_shoes` | Cipő | Gyerekcipő/sportcipő. | 180, 44 | SVG / 96 | `task_shoes.png` + `task_shoes_small.png` (small) |
| `task_bag` | Táska | Hátizsák az oviba/iskolába. | 180, 44 | SVG / 96 | `task_bag.png` + `task_bag_small.png` (small) |
| `task_door_ready` | Indulásra kész | Ajtó kis pipával. | 180, 44, 36, 30 | SVG / 96 | `task_door_ready.png` + `task_door_ready_small.png` (small) |
| `task_dinner` | Vacsora | Tányér étellel, villa és kés. | 180, 44, 36, 30 | SVG / 96 | `task_dinner.png` + `task_dinner_small.png` (small) |
| `task_bath` | Fürdés | Kád habbal. | 180, 44, 36, 30 | SVG / 96 | `task_bath.png` + `task_bath_small.png` (small) |
| `task_pajamas` | Pizsama | Pizsamafelső holddal és csillaggal. | 180, 44 | SVG / 96 | `task_pajamas.png` + `task_pajamas_small.png` (small) |
| `task_story` | Mese | Nyitott mesekönyv. | 180, 44 | SVG / 96 | `task_story.png` + `task_story_small.png` (small) |
| `task_bed` | Alvás | Ágy párnával, „z z”. Az egyetlen „szöveg” a z betű, az grafikai elem. | 180, 44, 36, 30 | SVG / 96 | `task_bed.png` + `task_bed_small.png` (small) |
| `task_wash_hands` | Kézmosás | Kéz vízcseppekkel. Javaslat. | 180, 44 | SVG / 96 | `task_wash_hands.png` + `task_wash_hands_small.png` (small) |
| `task_toilet` | WC | Vécé tartállyal. Javaslat. | 180, 44 | SVG / 96 | `task_toilet.png` + `task_toilet_small.png` (small) |
| `task_tidy_up` | Pakolás | Játékos doboz, benne kocka, labda. Javaslat. | 180, 44 | SVG / 96 | `task_tidy_up.png` + `task_tidy_up_small.png` (small) |
| `task_hair` | Fésülködés | Hajkefe és fésű. Javaslat. | 180, 44 | SVG / 96 | `task_hair.png` + `task_hair_small.png` (small) |
| `task_coat` | Kabát | Kabát gombokkal. Javaslat. | 180, 44 | SVG / 96 | `task_coat.png` + `task_coat_small.png` (small) |
| `task_play` | Játék | Labda és dobókocka. Javaslat. | 180, 44 | SVG / 96 | `task_play.png` + `task_play_small.png` (small) |
| `checkpoint_flag` | Általános checkpoint | Kis zászló rúdon. | 36, 30 | SVG / 48 | `checkpoint_flag.png` + `checkpoint_flag_small.png` (small) |

## Jutalmak

Alapértelmezett jutalomikonok. A szülő saját képet is feltölthet, ezek a tartalékok és a példák.

| id | Név | Leírás | Knob (px) | HA | Fájlok |
|---|---|---|---|---|---|
| `reward_toy_car` | Kisautó | Piros játékautó. | 180, 110 | SVG / 96 | `reward_toy_car.png` |
| `reward_doll` | Baba | Játékbaba szoknyában. | 180, 110 | SVG / 96 | `reward_doll.png` |
| `reward_bricks` | Építőkocka | LEGO/Duplo jellegű kockák (márkajel nélkül). Ne legyen rajta márkanév vagy logó. | 180, 110 | SVG / 96 | `reward_bricks.png` |
| `reward_long_story` | Hosszú mese | Vastag könyv holddal. | 180, 110 | SVG / 96 | `reward_long_story.png` |
| `reward_extra_story` | Még egy mese | Könyv plusz jellel. | 180, 110 | SVG / 96 | `reward_extra_story.png` |
| `reward_choose_game` | Játékválasztás | Dobókockák / társasjáték. Ne konzol vagy kontroller legyen. | 180, 110 | SVG / 96 | `reward_choose_game.png` |
| `reward_treat` | Nasi | Fagylalttölcsér (vagy süti). | 180, 110 | SVG / 96 | `reward_treat.png` |
| `reward_family_activity` | Családi program | Család (felnőtt + gyerekek) együtt. | 180, 110 | SVG / 96 | `reward_family_activity.png` |
| `reward_gift` | Általános jutalom | Ajándékdoboz; azonos lehet a fn_rewards ikonnal. | 180, 110 | SVG / 96 | — (= `fn_rewards`) |

## Zsetonok, tárca, persely

A zsetonkupac és az animációk elemei. A kupacot ezekből a sprite-okból rakom össze, pontos darabszámmal.

| id | Név | Leírás | Knob (px) | HA | Fájlok |
|---|---|---|---|---|---|
| `token_coin_front` | Zseton – szemből | Arany zseton szemből, peremmel. Mind az öt változat ugyanannak a zsetonnak a nézete legyen. | 28, 40 | SVG / 32 | `token_coin_front.png` + `token_coin_front_small.png` (small) |
| `token_coin_tilt_left` | Zseton – balra döntve | Ugyanaz a zseton balra döntve. | 28, 40 | — | `token_coin_tilt_left.png` + `token_coin_tilt_left_small.png` (small) |
| `token_coin_tilt_right` | Zseton – jobbra döntve | Ugyanaz a zseton jobbra döntve. | 28, 40 | — | `token_coin_tilt_right.png` + `token_coin_tilt_right_small.png` (small) |
| `token_coin_edge` | Zseton – élről | A zseton oldalnézetből, éllel. | 28, 40 | — | `token_coin_edge.png` + `token_coin_edge_small.png` (small) |
| `token_coin_top` | Zseton – felülről | Fekvő zseton enyhe perspektívában. | 28, 40 | — | `token_coin_top.png` + `token_coin_top_small.png` (small) |
| `token_pile_shadow` | Kupac árnyéka | Lágy, ovális vetett árnyék. Kódból is rajzolható; csak akkor kell kép, ha szebb. | 200×60 | — | `token_pile_shadow.png` |
| `piggy_large` | Malacpersely | Nagy rózsaszín malac, oldalnézetből. | 200 | SVG / 128 | `piggy_large.png` |
| `badge_piggy_plus` | Kamat jelvény | Kis malac zöld plusz jellel. Nagyon egyszerű legyen; kis méretre. | 28 | — | `badge_piggy_plus.png` + `badge_piggy_plus_small.png` (small) |
| `wallet` | Tárca | Erszény/pénztárca. | 120 | SVG / 96 | `wallet.png` |
| `arrow_flow` | Áramlás nyíl | Ívelt nyíl. | 72 | SVG / 48 | `arrow_flow.png` |
| `hand_cartoon` | Rajzfilm-kéz | Fehér kesztyűs kéz; két állapot: nyitott és fogó. Két fájl: hand_cartoon_open, hand_cartoon_grab. | 96 | — | `hand_cartoon.png` |

## Állapot és műveletek

Megerősítés, zár, kapcsolat, sorozat és ünneplés.

| id | Név | Leírás | Knob (px) | HA | Fájlok |
|---|---|---|---|---|---|
| `action_check` | Pipa (nagy) | Zöld kör fehér pipával. | 96, 180 | SVG / 48 | `action_check.png` |
| `action_check_small` | Pipa (kicsi) | Egyszerűsített pipa, sötétebb zöld. | 20 | — | `action_check_small.png` + `action_check_small_small.png` (small) |
| `action_x` | X (mégse) | Piros kör fehér X-szel. | 96 | SVG / 48 | `action_x.png` |
| `status_lock` | Lakat | Sárga lakat. | 72 | SVG / 48 | `status_lock.png` |
| `status_disconnected` | Nincs kapcsolat | Felhő áthúzva. | 28, 120 | SVG / 48 | `status_disconnected.png` + `status_disconnected_small.png` (small) |
| `streak_flame` | Sorozat láng | Narancs-sárga láng. | 120, 28 | SVG / 48 | `streak_flame.png` + `streak_flame_small.png` (small) |
| `streak_day_done` | Sikeres nap | Kis zöld pipás kör. Kódból is rajzolható. | 24 | — | `streak_day_done.png` + `streak_day_done_small.png` (small) |
| `streak_day_empty` | Hátralévő nap | Üres szürke kör. Kódból is rajzolható. | 24 | — | `streak_day_empty.png` + `streak_day_empty_small.png` (small) |
| `celebrate_star` | Ünneplő csillag | Arany csillag. | 48 | SVG / 48 | `celebrate_star.png` |
| `celebrate_confetti` | Konfetti | Színes konfettidarabok. Kódból rajzolom (6–8 szín, kis téglalapok); nem kell kép. | — | — | `celebrate_confetti.png` |
| `placeholder_avatar` | Avatar helyettesítő | Semleges gyereksziluett. | 200, 110 | SVG / 96 | `placeholder_avatar.png` |
| `placeholder_image` | Kép helyettesítő | Semleges képjel. | 180 | SVG / 96 | `placeholder_image.png` |

## Betöltőképernyő labdái

A betöltőképernyő pattogó labdái két rétegből állnak. A színt a knob adja, ezért az alapréteg szürkeárnyalatos.

| id | Név | Leírás | Knob (px) | HA | Fájlok |
|---|---|---|---|---|---|
| `ball_base` | Labda – alapréteg | Fehér–világosszürke labda, szimmetrikus, középről kifelé sötétedő (radiális) árnyalással, irányfüggő fény nélkül. A knob ezt színezi és ütközéskor összenyomja. Ne legyen rajta csillanás vagy egyoldalú fény: a forgatás nem látszódhat rajta. | 48 | — | `ball_base.png` |
| `ball_highlight` | Labda – csillanás | Átlátszó réteg, rajta csak egy fehér csillanás jobb felül, ugyanakkora vásznon, mint az alapréteg. Ez nem forog és nem nyomódik össze, csak együtt mozog a labdával. | 48 | — | `ball_highlight.png` |

## A HA-panel navigációja

A szülői panel menüjének saját ikonjai. Ahol a funkció ugyanaz, a knob ikonját használja.

| id | Név | Leírás | Knob (px) | HA | Fájlok |
|---|---|---|---|---|---|
| `nav_today` | Ma | Napocska. | — | SVG / 48 | `nav_today.png` |
| `nav_calendar` | Naptár | Naptárlap színes napokkal. | — | SVG / 48 | `nav_calendar.png` |
| `nav_children` | Gyerekek | Két gyerekarc. | — | SVG / 48 | `nav_children.png` |
| `nav_routines` | Rutinok | Azonos a routine_generic ikonnal. Újrahasznosítás. | — | SVG / 48 | — (= `routine_generic`) |
| `nav_rewards` | Jutalmak | Azonos a fn_rewards ikonnal. Újrahasznosítás. | — | SVG / 48 | — (= `fn_rewards`) |
| `nav_tokens` | Zsetonok / persely | Azonos a fn_tokens ikonnal. Újrahasznosítás. | — | SVG / 48 | — (= `fn_tokens`) |
| `nav_history` | Előzmények | Óra visszafelé mutató nyíllal. | — | SVG / 48 | `nav_history.png` |
| `nav_notifications` | Értesítések | Csengő. | — | SVG / 48 | `nav_notifications.png` |
| `nav_settings` | Beállítások | Fogaskerék. | — | SVG / 48 | `nav_settings.png` |
