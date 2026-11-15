<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Irányítópult-kártyák / Dashboard cards

🇬🇧 English version below → [English](#english)

<a id="magyar"></a>

## Magyar

A Kis Segítő a szülőknek szóló irányítópult-kártyákkal érkezik. Az integrációval
együtt települnek: az irányítópulton válaszd a **Kártya hozzáadása** lehetőséget,
és keress rá: „Kis Segítő”. Minden kártyának vizuális szerkesztője van, az
irányítópult témájához igazodik, és a felhasználó nyelvén jeleníti meg a
szövegeit.

| Kártya | Mit mutat |
|---|---|
| **Gyerek** (`kis-segito-child-card`) | Egy gyerek: tárca, persely, sorozat és a mai rutinok (választható, mi látszik). |
| **Mai rutin** (`kis-segito-routine-card`) | Egy gyerek mai rutinjai a feladatokkal. A feladatok kipipálhatók; a pipa a szülő nevével kerül a naplóba. *Csak állapot* beállítással semmi nem pipálható. |
| **Jutalombolt** (`kis-segito-shop-card`) | Kiválasztott gyerekkel: mit tud megvenni a gyerek, Beváltás gombbal. Gyerek nélkül: jutalmanként, mely gyerekeknek van rá elég zsetonja; előbb gyereket kell választani, utána Beváltás. |
| **Jóváhagyások** (`kis-segito-approvals-card`) | A jóváhagyásra váró jutalmak és ellenőrzőpontok, jóváhagyás és elutasítás gombbal. |
| **Heti statisztika** (`kis-segito-week-card`) | Egy gyerek utolsó 7 napja: az elvégzett feladatok aránya százalékban naponként és rutinonként, és a sorozat. |
| **Gyors +/−** (`kis-segito-tokens-card`) | Zseton egy gyereknek, megjegyzéssel; minden zsetonmozgáshoz hasonlóan naplózva. |
| **Eseménynapló** (`kis-segito-log-card`) | Az utolsó események (feladatok, ellenőrzőpontok, jóváhagyások, zsetonok); a darabszám a kártyán állítható. Szűrhető egy gyerekre. |
| **Gomb állapota** (`kis-segito-knob-status-card`) | Minden fizikai gomb (vagy egy gomb): fényerő, fény, jelenlét és firmware-verzió, ébresztés, képernyővédő és éjszakai fény gombbal. |
| **Gyerekek röviden** (`kis-segito-mini-card`) | Gyerekenként egy sor: kép, mai haladás és zsetonok. |

A pipálás, beváltás, jóváhagyás, zsetonadás és a gombok vezérlése – a panelhez
hasonlóan – Home Assistant rendszergazda felhasználót igényel.

YAML-ben például:

```yaml
type: custom:kis-segito-shop-card
child: <a gyerek azonosítója, a kártyaszerkesztőben választható>
```

A virtuális gomb kártya (`kis-segito-knob-card`) a gyerekeknek mutatja a gomb
képernyőjét; lásd a README-t.

---

<a id="english"></a>

## English

🇭🇺 [Magyar változat](#magyar)

Little Helper comes with dashboard cards for parents. They are installed with the
integration: on a dashboard choose **Add card** and search for "Little Helper".
Every card has a visual editor, follows the dashboard theme and shows its texts
in the user's language.

| Card | What it shows |
|---|---|
| **Child** (`kis-segito-child-card`) | One child: wallet, piggy bank, streak and today's routines (choose which). |
| **Today's routine** (`kis-segito-routine-card`) | One child's routines today with their tasks. Tasks can be ticked; the tick is logged with the parent's name. With *Status only* nothing can be ticked. |
| **Reward shop** (`kis-segito-shop-card`) | With a child chosen: what the child can afford, with a Redeem button. Without a child: for each reward, which children can afford it; choose a child, then Redeem. |
| **Approvals** (`kis-segito-approvals-card`) | Rewards and checkpoints waiting for approval, with approve and reject. |
| **Weekly statistics** (`kis-segito-week-card`) | One child, the last 7 days: tasks done in percent per day and per routine, and the streak. |
| **Quick +/−** (`kis-segito-tokens-card`) | Tokens for one child, with a note; logged like every token movement. |
| **Event log** (`kis-segito-log-card`) | The last events (tasks, checkpoints, approvals, tokens); how many is set in the card. Optionally for one child. |
| **Knob status** (`kis-segito-knob-status-card`) | Each physical knob (or one): brightness, light, presence and firmware version, with buttons to wake it and to switch the screensaver and the night light. |
| **Children at a glance** (`kis-segito-mini-card`) | One line per child: picture, today's progress and tokens. |

Ticking, redeeming, approving, giving tokens and the knob buttons need a Home
Assistant administrator user, like the panel.

In YAML, for example:

```yaml
type: custom:kis-segito-shop-card
child: <child id, chosen in the card editor>
```

The virtual knob card (`kis-segito-knob-card`) shows the knob screen for
children; see the README.
