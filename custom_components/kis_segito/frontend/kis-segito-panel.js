// SPDX-License-Identifier: AGPL-3.0-only
//
// Kis Segito sidebar panel. Plain web component, no build step.
// Texts come from translations/<language>.json next to this file; adding a
// language only needs a new JSON file. The language follows the Home Assistant
// user language unless one is chosen in the panel settings.
//
// Data comes from the kis_segito/* WebSocket commands; the panel re-reads it
// after every change (kis_segito/subscribe).

// Must equal the integration version (scripts/check_versions.py checks it):
// a browser that still runs an older copy of this file shows a reload bar.
const PANEL_VERSION = "0.7.32";
const FALLBACK_LANGUAGE = "en";
const LANGUAGE_AUTO = "auto";
const TABS = ["today", "calendar", "children", "routines", "rewards", "tokens", "history", "notifications", "settings"];
// Phones: these tabs in the bottom bar, the rest under "More".
const BOTTOM_TABS = ["today", "calendar", "routines", "rewards"];
// Knob screen power settings (stored in seconds, edited in minutes;
// dim_level in percent).
const SCREEN_KEYS = ["saver_after", "dim_after", "dim_level", "blank_after", "off_after"];
const SAVER_TYPES = ["balls", "confetti", "stars"];
const REASONS = ["checkpoint_reward", "reward_redemption", "piggy_transfer", "piggy_interest", "streak_reward", "manual_adjustment", "reversal", "correction"];
// Logged events without a token movement (history page, statistics).
const EVENT_REASONS = ["task_done", "checkpoint_done", "checkpoint_missed"];
// Photo crop: the view (canvas px), the margin around the circle, and the
// size of the uploaded square.
const CROP_VIEW = 360;
const CROP_MARGIN = 20;
const CROP_OUT = 512;
const PRESET_COLORS = ["#6CB8FF", "#FF8FB1", "#6BCB77", "#FFC94A", "#A78BFA", "#FF9F43", "#4DD4C6", "#F472B6"];
// Colours the time track uses: a child colour close to these is harder to tell apart.
const SEMANTIC_COLORS = ["#6BCB77", "#FF9F43", "#FF6B6B", "#FFC94A"];
// Calendar colours offered for routines.
const ROUTINE_COLORS = ["#6BCB77", "#6CB8FF", "#A78BFA", "#FF8FB1", "#FFC94A", "#4DD4C6", "#FF9F43", "#8C96A5"];
const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];
// Calendar: shown hours, pixels per minute, drag step (minutes).
const CAL_FROM = 5 * 60;
const CAL_TO = 23 * 60;
const CAL_PX = 0.75;
const CAL_STEP = 5;
const THEME_KEY = "kis_segito_theme";
const LANG_KEY = "kis_segito_language";

// Times are stored in seconds and shown in minutes.
const secondsToMinutes = (seconds) => (seconds === null || seconds === undefined || seconds === "" ? "" : Math.round((seconds / 60) * 100) / 100);

function uid() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
}

function toMinutes(hhmm) {
  const [h, m] = String(hhmm || "0:0").split(":").map(Number);
  return h * 60 + m;
}

function fromMinutes(total) {
  const m = Math.min(Math.max(Math.round(total), 0), 23 * 60 + 59);
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

function shiftTime(hhmm, minutes) {
  return fromMinutes(toMinutes(hhmm) + minutes);
}

function nowMinutes() {
  const d = new Date();
  return d.getHours() * 60 + d.getMinutes();
}

function localDate(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function addDays(dateStr, days) {
  const d = new Date(`${dateStr}T12:00:00`);
  d.setDate(d.getDate() + days);
  return localDate(d);
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function colorDistance(a, b) {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [p(a), p(b)];
  return Math.sqrt(x.reduce((s, v, i) => s + (v - y[i]) ** 2, 0));
}

const sign = (n) => (n > 0 ? `+${n}` : `${n}`);

// New start and end of a routine occurrence: its checkpoints keep their
// distance from the end (clamped into the routine), so changing only the start
// leaves them in place and moving it moves them along.
function applyTimes(item, start, end) {
  const shift = end - toMinutes(item.end);
  item.checkpoints = (item.checkpoints || []).map((c) =>
    c.time ? { ...c, time: fromMinutes(Math.min(end, Math.max(start, toMinutes(c.time) + shift))) } : c
  );
  item.start = fromMinutes(start);
  item.end = fromMinutes(end);
  return item;
}

function applies(list, childId) {
  return !list?.length || list.includes(childId);
}

class KisSegitoPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._strings = {};
    this._loadedLanguage = null;
    this._data = null;
    this._today = null;
    this._week = null;
    this._weekStart = null; // null = this week
    this._tab = "today";
    this._edit = null;
    this._sec = "basics";
    this._picker = null; // {path, filter}
    this._dialog = null;
    this._crop = null;
    this._history = [];
    this._historyEvents = [];
    this._historyFilter = {};
    this._showEvents = false;
    this._calendarChild = "";
    this._rules = null;
    this._adjust = {};
    this._shift = {};
    this._demo = null;
    this._statPeriod = { kind: "7" };
    this._stats = null;
    this._childWeek = null;
    this._expanded = new Set();
    this._error = "";
    try {
      this._theme = localStorage.getItem(THEME_KEY) || "";
      this._localLanguage = localStorage.getItem(LANG_KEY) || "";
    } catch (_err) {
      this._theme = "";
      this._localLanguage = "";
    }
  }

  // ------------------------------------------------------------ HA plumbing

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    this._updateLanguage();
    if (first) {
      this._loadFonts();
      this._subscribe();
      this._load();
      this._render();
      // The time ring and "minutes left" move on.
      this._clock = setInterval(() => {
        if (this._tab === "today" && !this._edit && !this._dialog && !this._picker && !this._crop) {
          this._render();
        }
      }, 60000);
    } else {
      const menuButton = this.shadowRoot.querySelector("ha-menu-button");
      if (menuButton) {
        menuButton.hass = hass;
      }
      const dark = Boolean(hass.themes?.darkMode);
      if (dark !== this._haDark) {
        this._haDark = dark;
        this._applyTheme();
      }
    }
  }

  set narrow(narrow) {
    this._narrow = narrow;
    const menuButton = this.shadowRoot.querySelector("ha-menu-button");
    if (menuButton) {
      menuButton.narrow = narrow;
    }
  }

  set panel(panel) {
    this._panel = panel;
  }

  disconnectedCallback() {
    if (this._unsub) {
      this._unsub.then((unsub) => unsub()).catch(() => {});
      this._unsub = null;
    }
    clearInterval(this._clock);
    this._clock = null;
  }

  connectedCallback() {
    if (this._hass && !this._unsub) {
      this._subscribe();
      this._load();
    }
  }

  get _staticUrl() {
    return this._panel?.config?.static_url ?? "/kis_segito_static";
  }

  get _version() {
    return this._panel?.config?.version ?? "";
  }

  get _isAdmin() {
    return this._hass?.user?.is_admin ?? false;
  }

  get _isNarrow() {
    return Boolean(this._narrow) || window.innerWidth <= 720;
  }

  get _language() {
    const chosen = this._localLanguage || this._data?.settings?.language;
    return chosen && chosen !== LANGUAGE_AUTO ? chosen : this._hass?.language;
  }

  get _locale() {
    return this._language || "en";
  }

  // The display fonts ship with the panel (no external download); a font
  // face only works when declared in the page itself.
  _loadFonts() {
    if (document.getElementById("kis-segito-fonts")) {
      return;
    }
    const style = document.createElement("style");
    style.id = "kis-segito-fonts";
    const base = `${this._staticUrl}/fonts`;
    style.textContent = `@font-face{font-family:"KS Baloo 2";src:url("${base}/baloo2.woff2") format("woff2");font-weight:400 800;font-display:swap}
@font-face{font-family:"KS Figtree";src:url("${base}/figtree.woff2") format("woff2");font-weight:300 900;font-display:swap}`;
    document.head.appendChild(style);
  }

  get _night() {
    if (this._theme) {
      return this._theme === "dark";
    }
    return Boolean(this._hass?.themes?.darkMode);
  }

  _applyTheme() {
    this.setAttribute("data-theme", this._night ? "dark" : "light");
  }

  _updateLanguage() {
    const language = this._language;
    if (language && language !== this._loadedLanguage) {
      this._loadTranslations(language);
    }
  }

  async _fetchStrings(language) {
    const url = `${this._staticUrl}/translations/${language}.json?v=${this._version}`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
  }

  async _loadTranslations(language) {
    this._loadedLanguage = language;
    let strings = {};
    try {
      strings = await this._fetchStrings(FALLBACK_LANGUAGE);
    } catch (err) {
      console.warn("Kis Segito: missing fallback translations", err);
    }
    for (const candidate of [language, language?.split("-")[0]]) {
      if (!candidate || candidate === FALLBACK_LANGUAGE) {
        continue;
      }
      try {
        strings = { ...strings, ...(await this._fetchStrings(candidate)) };
        break;
      } catch (_err) {
        // Try the next candidate.
      }
    }
    this._strings = strings;
    this._render();
  }

  _subscribe() {
    this._unsub = this._hass.connection
      .subscribeMessage(() => this._load(), { type: "kis_segito/subscribe" })
      .catch((err) => console.warn("Kis Segito: subscribe failed", err));
  }

  async _load() {
    try {
      const [data, today] = await Promise.all([
        this._hass.callWS({ type: "kis_segito/data" }),
        this._hass.callWS({ type: "kis_segito/today" }),
      ]);
      this._data = data;
      this._today = today;
      this._shift = {};
      await this._loadForTab(this._tab);
    } catch (err) {
      console.warn("Kis Segito: loading data failed", err);
    }
    this._updateLanguage();
    this._render();
    // A link like …/kis-segito#tx-12 opens that history entry.
    const anchor = /^#tx-(\d+)$/.exec(location.hash);
    if (anchor && !this._anchorDone) {
      this._anchorDone = true;
      this._tab = "history";
      await this._loadHistory();
      this._render();
      await this._goto(anchor[1]);
    }
  }

  async _loadForTab(tab) {
    if (tab === "today") {
      this._todayWeek = await this._hass.callWS({ type: "kis_segito/week" });
    }
    if (tab === "calendar") {
      await this._loadWeek();
    }
    if (tab === "history" || tab === "tokens") {
      await this._loadHistory();
    }
    if (tab === "children") {
      await this._loadChildWeek();
    }
    if (tab === "notifications") {
      await this._loadRules();
    }
    if (this._stats) {
      await this._loadStats();
    }
  }

  async _loadHistory() {
    const f = this._historyFilter;
    const search = (f.search || "").trim();
    const wantEvents = this._showEvents || Boolean(search);
    const [history, events] = await Promise.all([
      f.reason && EVENT_REASONS.includes(f.reason)
        ? Promise.resolve([])
        : this._hass.callWS({
            type: "kis_segito/history",
            child_id: f.child || null,
            reasons: f.reason ? [f.reason] : null,
            account: f.account || null,
            date_from: f.from || null,
            date_to: f.to || null,
            search: search || null,
            limit: 500,
          }),
      wantEvents && !f.account && (!f.reason || EVENT_REASONS.includes(f.reason))
        ? this._hass.callWS({
            type: "kis_segito/events",
            child_id: f.child || null,
            date_from: f.from || null,
            date_to: f.to || null,
            search: search || null,
            limit: 500,
          })
        : Promise.resolve([]),
    ]);
    this._history = history;
    this._historyEvents = events.filter(
      (ev) => !(ev.type === "checkpoint_done" && ev.tokens > 0) && (!f.reason || ev.type === f.reason)
    );
  }

  async _loadWeek() {
    const msg = { type: "kis_segito/week" };
    if (this._weekStart) {
      msg.start = this._weekStart;
    }
    this._week = await this._hass.callWS(msg);
  }

  // The last 7 days of every child (Children page cards).
  async _loadChildWeek() {
    const from = addDays(this._todayStr(), -6);
    const [history, events] = await Promise.all([
      this._hass.callWS({ type: "kis_segito/history", date_from: from, limit: 20000 }),
      this._hass.callWS({ type: "kis_segito/events", date_from: from, limit: 20000 }),
    ]);
    this._childWeek = { history, events };
  }

  async _loadStats() {
    const s = this._stats;
    if (!s) {
      return;
    }
    const range = this._statRange();
    const [history, events] = await Promise.all([
      this._hass.callWS({ type: "kis_segito/history", child_id: s.childId, date_from: range.from, date_to: range.to, limit: 20000 }),
      this._hass.callWS({ type: "kis_segito/events", child_id: s.childId, date_from: range.from, date_to: range.to, limit: 20000 }),
    ]);
    if (this._stats === s) {
      s.history = history;
      s.events = events;
    }
  }

  async _loadRules() {
    const [rules, targets] = await Promise.all([
      this._hass.callWS({ type: "kis_segito/notifications" }),
      this._hass.callWS({ type: "kis_segito/notify_targets" }),
    ]);
    this._rules = rules;
    this._targets = targets;
  }

  async _ws(msg) {
    this._error = "";
    try {
      return await this._hass.callWS(msg);
    } catch (err) {
      const code = err?.code || "error";
      this._error = this._t(`error.${code}`, err?.message || code);
      this._render();
      throw err;
    }
  }

  _toast(text) {
    this._toastText = text;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toastText = null;
      this._render();
    }, 2600);
  }

  // ------------------------------------------------------------ helpers

  _t(key, fallback) {
    return this._strings[key] ?? fallback ?? key;
  }

  _e(text) {
    return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }

  _iconUrl(name, size = 40) {
    // An alias shares another icon's artwork.
    name = this._data?.icon_aliases?.[name] || name;
    // Small places use the simplified variant, when the icon has one.
    const small = size <= 44 && this._data?.small_icons?.includes(name) ? "small/" : "";
    return `${this._staticUrl}/icons/${small}${this._e(name)}.png?v=${this._version}`;
  }

  _icon(name, size = 40, cls = "") {
    if (!name) {
      return "";
    }
    return `<img class="ic ${cls}" src="${this._iconUrl(name, size)}" width="${size}" height="${size}" alt="">`;
  }

  // A background value: "" (none), a preset ("bg_1" …) or an uploaded picture id.
  _backgroundUrl(value) {
    if (!value) {
      return "";
    }
    return value.startsWith("bg_")
      ? `${this._staticUrl}/backgrounds/${this._e(value)}.jpg?v=${this._version}`
      : `/api/image/serve/${this._e(value)}/512x512`;
  }

  // An uploaded picture (Home Assistant image_upload), served at a fixed size.
  _photoUrl(id) {
    return `/api/image/serve/${this._e(id)}/256x256`;
  }

  _child(id) {
    return this._data?.children?.find((c) => c.id === id);
  }

  _childName(id) {
    return this._child(id)?.name || this._t("history.unknown_child");
  }

  _routine(id) {
    return this._data?.routines?.find((r) => r.id === id);
  }

  _avatar(child, size = 48) {
    const src = child.avatar_image ? this._photoUrl(child.avatar_image) : this._iconUrl(child.avatar || "avatar_00", size);
    return `<span class="av" style="--c:${this._e(child.color || "#6CB8FF")};width:${size}px;height:${size}px"><img src="${src}" alt=""></span>`;
  }

  _coin(n, size = 22) {
    return `<span class="coin">${this._icon("token_coin_front", size)}<span class="num">${n}</span></span>`;
  }

  _pile(count, max = 12) {
    const k = Math.min(Math.max(Number(count) || 0, 0), max);
    let html = "";
    for (let i = 0; i < k; i++) {
      html += `<img src="${this._iconUrl("token_coin_front", 26)}" width="26" height="26" style="left:${i * 9}px;bottom:${(i % 3) * 3}px" alt="">`;
    }
    const more = count > max ? `<span class="muted small" style="position:absolute;left:${k * 9 + 26}px;bottom:4px">+${count - max}</span>` : "";
    return `<span class="pile" style="width:${k ? 26 + (k - 1) * 9 + (more ? 30 : 0) : 0}px">${html}${more}</span>`;
  }

  _age(birth) {
    if (!birth) {
      return "";
    }
    const b = new Date(`${birth}T12:00:00`);
    const n = new Date();
    let a = n.getFullYear() - b.getFullYear();
    if (n < new Date(n.getFullYear(), b.getMonth(), b.getDate())) {
      a--;
    }
    return a >= 0 ? this._t("children.age").replace("{n}", a) : "";
  }

  _fmtDate(dateStr, options) {
    return new Date(`${dateStr}T12:00:00`).toLocaleDateString(this._locale, options);
  }

  _fmtTime(iso) {
    return new Date(iso).toLocaleTimeString(this._locale, { hour: "2-digit", minute: "2-digit" });
  }

  _todayStr() {
    return this._today?.date || this._todayWeek?.days?.find((d) => d.today)?.date || localDate();
  }

  _todayDay() {
    return (this._todayWeek || this._week)?.days?.find((d) => d.today) || null;
  }

  // Reads/writes a nested value in the edit buffer by path like "tasks.2.icon".
  _get(path) {
    return path.split(".").reduce((obj, key) => obj?.[key], this._edit?.item);
  }

  _set(path, value) {
    const keys = path.split(".");
    let obj = this._edit.item;
    for (const key of keys.slice(0, -1)) {
      obj = obj[key];
    }
    obj[keys[keys.length - 1]] = value;
  }

  _dis() {
    return this._isAdmin ? "" : "disabled";
  }

  _minuteInput(attrs, seconds, placeholder = "", min = 0) {
    return `<input type="number" min="${min}" max="1440" step="0.5" data-minutes ${attrs} value="${secondsToMinutes(seconds)}" placeholder="${placeholder === "" ? "" : secondsToMinutes(placeholder)}" ${this._dis()}>`;
  }

  // ------------------------------------------------------------ time ring

  // The knob's time ring as an upside-down horseshoe: it starts at 11 o'clock,
  // runs counter-clockwise through 6 o'clock and ends at 1 o'clock. Base
  // colour, time-colour zones, checkpoint dots, the "now" marker; the elapsed
  // part is faded.
  _dial(r, size = 160, opts = {}) {
    const s = toMinutes(r.start);
    const en = Math.max(toMinutes(r.end), s + 1);
    const tot = en - s;
    const cx = size / 2;
    const R = size / 2 - 10;
    const sw = Math.max(6, size / 14);
    const ang = (m) => ((330 - (300 * (Math.min(Math.max(m, s), en) - s)) / tot) * Math.PI) / 180;
    const pt = (a, rr = R) => [cx + rr * Math.sin(a), cx - rr * Math.cos(a)];
    const arc = (m1, m2, color, op = 1) => {
      if (m2 <= m1) {
        return "";
      }
      const [x1, y1] = pt(ang(m1));
      const [x2, y2] = pt(ang(m2));
      const large = ang(m1) - ang(m2) > Math.PI ? 1 : 0;
      return `<path d="M${x1.toFixed(1)} ${y1.toFixed(1)} A${R} ${R} 0 ${large} 0 ${x2.toFixed(1)} ${y2.toFixed(1)}" stroke="${this._e(color)}" stroke-width="${sw}" fill="none" stroke-linecap="round" opacity="${op}"/>`;
    };
    const zones = [...(r.zones || [])].sort((a, b) => Number(b.offset_min) - Number(a.offset_min));
    const pts = [s, ...zones.map((z) => Math.max(s, en - Number(z.offset_min || 0))), en];
    const cols = [r.base_color || "#6BCB77", ...zones.map((z) => z.color)];
    const now = opts.now ?? null;
    const [bx1, by1] = pt(ang(s));
    const [bx2, by2] = pt(ang(en));
    let segs = `<path d="M${bx1} ${by1} A${R} ${R} 0 1 0 ${bx2} ${by2}" stroke="var(--surface-2)" stroke-width="${sw + 6}" fill="none" stroke-linecap="round"/>`;
    for (let i = 0; i < cols.length; i++) {
      const a = pts[i];
      const b = pts[i + 1];
      if (now !== null && now > s) {
        segs += arc(a, Math.min(b, now), cols[i], 0.28);
        segs += arc(Math.max(a, now), b, cols[i]);
      } else {
        segs += arc(a, b, cols[i]);
      }
    }
    let marks = "";
    for (const c of (r.checkpoints || []).filter((c) => c.time)) {
      const [x, y] = pt(ang(toMinutes(c.time)));
      marks += `<circle cx="${x}" cy="${y}" r="${sw / 2 + 2}" fill="var(--surface)" stroke="var(--ink)" stroke-width="2"/>`;
    }
    if (now !== null && now >= s && now <= en) {
      const [x, y] = pt(ang(now));
      marks += `<circle cx="${x}" cy="${y}" r="${sw / 2 + 4}" fill="var(--ink)"/><circle cx="${x}" cy="${y}" r="${sw / 2}" fill="var(--surface)"/>`;
    }
    const isz = size * 0.42;
    const label = opts.label ?? `${r.start}–${r.end}`;
    return `<svg class="dial" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${this._e(r.name)} ${this._e(label)}">
      <circle cx="${cx}" cy="${cx}" r="${R - sw}" fill="var(--surface-2)"/>
      ${segs}${marks}
      <image href="${this._iconUrl(r.icon || "routine_generic", 96)}" x="${cx - isz / 2}" y="${cx - isz / 2 - size * 0.04}" width="${isz}" height="${isz}"/>
      <text x="${cx}" y="${cx + isz / 2 + size * 0.07}" text-anchor="middle" font-size="${Math.max(9, size * (label.length > 6 ? 0.072 : 0.09))}" font-weight="700">${this._e(label)}</text>
    </svg>`;
  }

  // ------------------------------------------------------------ today

  _viewToday() {
    const kids = this._data.children.filter((c) => c.active !== false);
    if (!kids.length) {
      return `<div class="card empty">${this._e(this._t("today.no_children"))}<br><br>
        ${this._isAdmin ? `<button class="btn primary" data-act="tab" data-arg="children">${this._e(this._t("today.add_child"))}</button>` : ""}</div>`;
    }
    const day = this._todayDay();
    const real = nowMinutes();
    const todays = day?.routines || [];
    const n = this._demo ?? real;
    const isDemo = this._demo !== null && this._demo !== real;
    const running = todays.find((r) => toMinutes(r.start) <= n && n <= toMinutes(r.end));
    const next = todays.filter((r) => toMinutes(r.start) > n).sort((a, b) => toMinutes(a.start) - toMinutes(b.start))[0];
    const focus = running || next;
    let nowCard;
    if (focus) {
      const full = { ...focus.routine, name: focus.name, icon: focus.icon, start: focus.start, end: focus.end };
      const cps = (full.checkpoints || []).filter((c) => c.time).sort((a, b) => toMinutes(a.time) - toMinutes(b.time));
      const nextCp = cps.find((c) => toMinutes(c.time) >= n);
      const flow = cps
        .map((c, i) => {
          const last = i === cps.length - 1;
          const tasks = (full.tasks || []).filter(
            (x) => x.checkpoint_id === c.id || (last && !cps.some((y) => y.id === x.checkpoint_id))
          );
          const past = toMinutes(c.time) < n;
          return `${tasks.map((x) => `<span class="task-dot ${past ? "past" : ""}" data-tip="${this._e(x.label || this._t("routines.tasks"))} → ${this._e(c.name)}">${this._icon(x.icon, 30)}</span>`).join("")}<span class="cp-chip ${past ? "done" : ""}" data-tip="${this._e(c.name)} · ${this._e(c.time)}">${this._icon(c.icon || "checkpoint_flag", 20)} ${this._e(c.name)} <span class="num">${this._e(c.time)}</span></span>${last ? "" : `<span class="flow-sep"></span>`}`;
        })
        .join("");
      const left = running
        ? this._t("today.left").replace("{n}", toMinutes(full.end) - n)
        : this._t("today.in").replace("{n}", toMinutes(full.start) - n);
      nowCard = `<div class="now-card">${this._dial(full, 190, { now: n })}
        <div class="stack" style="gap:8px">
          <span class="tag ${running ? "good" : "sun"}" style="align-self:flex-start">${this._e(this._t(running ? "today.now" : "today.next"))}</span>
          <h2 style="font-size:1.9rem">${this._e(full.name || this._t("routines.unnamed"))}</h2>
          <div class="muted num" style="font-weight:600">${this._e(full.start)}–${this._e(full.end)} · ${this._e(left)}</div>
          ${running && nextCp ? `<div class="row wrap" style="gap:6px"><span class="lbl">${this._e(this._t("today.next_cp"))}</span><span class="cp-chip">${this._icon(nextCp.icon || "checkpoint_flag", 20)} ${this._e(nextCp.name)} <span class="num">${this._e(nextCp.time)}</span> · <b class="num">${toMinutes(nextCp.time) - n}′</b></span></div>` : ""}
          ${flow ? `<div class="flow">${flow}</div>` : ""}
          <div class="hint">${this._e(this._t("today.on_knob"))}</div>
        </div></div>`;
    } else {
      nowCard = `<div class="row">${this._icon("celebrate_star", 48)}<b>${this._e(this._t(todays.length ? "today.done_all" : "today.idle"))}</b></div>`;
    }
    const rewind = `<div class="demo-bar"><span class="tag ${isDemo ? "sun" : "good"}">${this._e(this._t(isDemo ? "today.demo" : "today.realtime"))}</span>
        <span class="num" style="font-weight:800;min-width:46px">${fromMinutes(n)}</span>
        <input type="range" min="300" max="1380" step="1" value="${n}" data-demo aria-label="${this._e(this._t("today.demo_time"))}">
        ${isDemo ? `<button class="btn sm" data-act="demo-now">${this._e(this._t("today.back_now"))}</button>` : ""}</div>
        <div class="hint" style="margin-top:4px">${this._e(this._t("today.rewind_hint"))}</div>`;
    const progress = this._today?.progress || {};
    const upTo = (ts) => !isDemo || (ts && toMinutes(this._fmtClock(ts)) <= n);
    const target = this._data.settings.streak_target || 7;
    const cards = kids
      .map((c) => {
        const rows = todays
          .filter((r) => applies(r.children, c.id))
          .map((r) => {
            const p0 = progress[r.id]?.[c.id] || { tasks: {}, checkpoints: {} };
            const doneTasks = Object.values(p0.tasks || {}).filter(upTo).length;
            const total = (r.routine?.tasks || []).length;
            const pct = total ? Math.round((doneTasks / total) * 100) : 0;
            const cps = (r.routine?.checkpoints || [])
              .filter((cp) => applies(cp.children, c.id) && cp.time)
              .sort((a, b) => toMinutes(a.time) - toMinutes(b.time))
              .map((cp) => {
                const d = p0.checkpoints?.[cp.id];
                const shown = d && upTo(d.at) ? d : null;
                const cls = shown ? (shown.on_time ? "done" : "late") : "";
                return `<span class="cp-chip ${cls}" data-tip="${this._e(cp.name)}">${this._icon(cp.icon || "checkpoint_flag", 18)} <span class="num">${this._e(cp.time)}</span>${shown ? ` · ${shown.tokens ? `+${shown.tokens}` : "✓"}` : ""}</span>`;
              })
              .join("");
            return `<div class="rp">${this._icon(r.icon, 34)}<div><b>${this._e(r.name || this._t("routines.unnamed"))}</b> <span class="muted num small">${this._e(r.start)}–${this._e(r.end)}</span></div>
              <span class="num muted small"><b style="color:var(--ink)">${doneTasks}</b>/${total}</span>
              <div class="bar"><span style="width:${pct}%"></span></div><div class="cps">${cps}</div></div>`;
          })
          .join("");
        let dots = "";
        for (let i = 0; i < Math.min(target, 14); i++) {
          dots += `<img src="${this._iconUrl(i < c.streak ? "streak_day_done" : "streak_day_empty", 20)}" alt="">`;
        }
        return `<div class="card child-hero clickable" style="--c:${this._e(c.color)}" data-act="child-stats" data-arg="${c.id}" tabindex="0" title="${this._e(this._t("stats.title"))}">
          <div class="child-top">${this._avatar(c, 84)}
            <div><div class="name">${this._e(c.name)}</div>
              <div class="row small muted" style="gap:4px;margin-top:4px">${this._icon("streak_flame", 18)} <b class="num">${c.streak}/${target}</b></div>
              <div class="streak">${dots}</div></div>
            <div class="balances"><span class="bal">${this._icon("wallet", 30)}<span class="num">${c.balances.wallet}</span></span>
              ${c.piggy_unlocked ? `<span class="bal">${this._icon("fn_piggy", 30)}<span class="num">${c.balances.piggy}</span></span>` : ""}</div>
          </div>
          ${rows || `<div class="muted">${this._e(this._t("today.no_routines"))}</div>`}
        </div>`;
      })
      .join("");
    return `<div class="card">${nowCard}${rewind}</div>
      <div class="grid g2" style="margin-top:16px">${cards}</div>${this._viewModifyToday(day)}`;
  }

  // "HH:MM" of an ISO timestamp in local time.
  _fmtClock(iso) {
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  }

  _viewModifyToday(day) {
    // One-day changes: skip a routine or shift all its times, only for today.
    if (!day) {
      return "";
    }
    const weekday = (new Date(`${day.date}T12:00:00`).getDay() + 6) % 7;
    const template = (this._data.templates || []).find((t) => t.id === day.template);
    const scheduled = this._data.routines.filter(
      (r) => r.active !== false && (template ? template.routines.includes(r.id) : !r.weekdays?.length || r.weekdays.includes(weekday))
    );
    const admin = this._isAdmin;
    const nameBlock = (r, times, state) => {
      const attrs = admin ? `data-act="day-edit" data-arg="${this._e(r.id)}" data-date="${day.date}" tabindex="0" title="${this._e(this._t("modify.edit"))}"` : "";
      return `<div class="grow row nameblk" ${attrs}>${this._icon(r.icon, 36)}<div class="grow"><b class="name">${this._e(r.name || this._t("routines.unnamed"))}</b> <span class="muted num">${this._e(times)}</span> ${state} ${admin ? `<span class="pen">✎</span>` : ""}</div></div>`;
    };
    const rows = scheduled
      .map((r) => {
        const running = day.routines.find((x) => x.id === r.id);
        const skipped = day.skipped.includes(r.id);
        const stored = running?.override?.shift_min || 0;
        const shift = this._shift[r.id] ?? stored;
        const times = running ? `${shiftTime(running.start, shift - stored)}–${shiftTime(running.end, shift - stored)}` : "";
        const state = skipped
          ? `<span class="tag warn">${this._e(this._t("modify.skipped"))}</span>`
          : shift
            ? `<span class="tag warn">${this._e(this._t("modify.shifted").replace("{n}", sign(shift)))}</span>`
            : running?.edited
              ? `<span class="badge" title="${this._e(this._t("calendar.changed"))}">✎</span>`
              : "";
        // The Restore button sits left of the stepper, so "+" never moves.
        const controls = !admin
          ? ""
          : skipped
            ? `<button class="btn sm" data-act="ov-restore" data-arg="${this._e(r.id)}">${this._e(this._t("modify.restore"))}</button>`
            : `${shift ? `<button class="btn sm ghost" data-act="ov-restore" data-arg="${this._e(r.id)}">↺ ${this._e(this._t("modify.restore"))}</button>` : ""}
               <span class="stepper"><button data-act="ov-shift" data-arg="${this._e(r.id)}" data-d="-5" aria-label="-5">−</button><span>${sign(shift)} ${this._e(this._t("modify.minutes"))}</span><button data-act="ov-shift" data-arg="${this._e(r.id)}" data-d="5" aria-label="+5">+</button></span>
               <button class="btn sm" data-act="ov-skip" data-arg="${this._e(r.id)}">${this._e(this._t("modify.skip"))}</button>`;
        return `<div class="mod-row ${skipped ? "skipped" : ""}">${nameBlock(r, times, state)}${controls}</div>`;
      })
      .join("");
    const oneDay = day.routines
      .filter((r) => r.one_day)
      .map((r) => `<div class="mod-row">${nameBlock(r, `${r.start}–${r.end}`, r.moved_from ? `<span class="badge" title="${this._e(this._t("calendar.changed"))}">✎</span>` : `<span class="badge" title="${this._e(this._t("calendar.one_day"))}">1</span>`)}</div>`)
      .join("");
    const templates = this._data.templates || [];
    const chosen = this._data.date_templates?.[day.date];
    const select = templates.length
      ? `<label class="field" style="max-width:340px"><span>${this._e(this._t("modify.template"))}</span><select data-date-template="${day.date}" ${this._dis()}>
          <option value="" ${chosen === undefined ? "selected" : ""}>${this._e(this._t("modify.template_default"))}</option>
          <option value="-" ${chosen === "" ? "selected" : ""}>${this._e(this._t("templates.own_days"))}</option>
          ${templates.map((t) => `<option value="${this._e(t.id)}" ${t.id === chosen ? "selected" : ""}>${this._e(t.name)}</option>`).join("")}</select></label>`
      : "";
    return `<div class="section-title">${this._icon("nav_calendar", 34)}<h2>${this._e(this._t("modify.title"))}</h2></div>
      <div class="card"><div class="hint" style="margin-bottom:12px">${this._e(this._t("modify.hint"))}</div>${select}${rows}${oneDay}
      ${admin ? `<div class="row" style="margin-top:12px"><button class="btn" data-act="day-new" data-date="${day.date}">＋ ${this._e(this._t("modify.add_one_day"))}</button></div>` : ""}</div>`;
  }

  // ------------------------------------------------------------ calendar

  get _calViewKey() {
    return `kis_segito_calendar_view_${this._hass?.user?.id || ""}`;
  }

  // Day, 3 days or week: the user's last choice, else by screen width.
  get _calModeNow() {
    if (!this._calMode) {
      try {
        this._calMode = localStorage.getItem(this._calViewKey) || "";
      } catch (_err) {
        this._calMode = "";
      }
    }
    return this._calMode || (this._isNarrow ? "day" : "week");
  }

  _calDayDate() {
    return this._calDay || this._todayStr();
  }

  async _syncCalendarRange() {
    // Week view starts on Monday; day and 3-day views start on the chosen day.
    if (this._calModeNow === "week") {
      const d = new Date(`${this._calDayDate()}T12:00:00`);
      d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
      this._weekStart = this._calDay ? localDate(d) : null;
    } else {
      this._weekStart = this._calDayDate();
    }
    await this._loadWeek();
  }

  _calDays() {
    const mode = this._calModeNow;
    const all = this._week?.days || [];
    if (mode === "week") {
      return all;
    }
    const first = Math.max(all.findIndex((d) => d.date === this._calDayDate()), 0);
    return all.slice(first, first + (mode === "3day" ? 3 : 1));
  }

  // An occurrence that differs from its routine on that day.
  _changedOccurrence(r) {
    return Boolean(r.edited || r.override?.shift_min || r.moved_from);
  }

  _viewCalendar() {
    if (!this._week) {
      return `<div class="card empty">${this._e(this._t("common.loading"))}</div>`;
    }
    const H = (CAL_TO - CAL_FROM) * CAL_PX;
    const mode = this._calModeNow;
    const days = this._calDays();
    const today = this._todayStr();
    const filter = this._calendarChild;
    let hours = "";
    for (let h = 6; h <= 22; h += 2) {
      hours += `<div style="top:${(h * 60 - CAL_FROM) * CAL_PX}px">${String(h).padStart(2, "0")}:00</div>`;
    }
    const heads = days
      .map((d) => {
        const dt = new Date(`${d.date}T12:00:00`);
        return `<div class="cal-head ${d.date === today ? "today" : ""}"><span class="wd">${this._e(dt.toLocaleDateString(this._locale, { weekday: "short" }))}</span><span class="dn">${dt.getDate()}</span>${d.template_name ? `<div class="tpl">${this._e(d.template_name)}</div>` : ""}</div>`;
      })
      .join("");
    const cols = days
      .map((d) => {
        const past = d.date < today;
        const blocks = d.routines
          .filter((r) => !filter || applies(r.children, filter))
          .map((r) => {
            const st = toMinutes(r.start);
            const en = Math.max(toMinutes(r.end), st + 1);
            const top = Math.max(0, (st - CAL_FROM) * CAL_PX);
            const h = Math.max(22, (en - st) * CAL_PX);
            const color = r.routine?.color || this._routine(r.id)?.color || "#6BCB77";
            const changed = this._changedOccurrence(r);
            const oneDay = r.one_day && !r.moved_from;
            const who = r.children.length ? r.children.map((id) => this._child(id)?.name).filter(Boolean).join(", ") : this._t("routines.everyone");
            const cps = (r.checkpoints || [])
              .filter((c) => c.time)
              .map((c) => `<img class="cpm" data-t="${toMinutes(c.time)}" src="${this._iconUrl(c.icon || "checkpoint_flag", 16)}" style="top:${(Math.max(st, toMinutes(c.time)) - st) * CAL_PX - 8}px" title="${this._e(c.name)} ${this._e(c.time)}" alt="">`)
              .join("");
            const badge = oneDay
              ? `<span class="badge" title="${this._e(this._t("calendar.one_day"))}">1</span>`
              : changed
                ? `<span class="badge" title="${this._e(this._t(r.moved_from ? "calendar.moved_here" : "calendar.changed"))}">✎</span>`
                : "";
            return `<div class="blk ${changed ? "changed" : ""} ${oneDay ? "oneday" : ""}" style="top:${top}px;height:${h}px;--rc:${this._e(color)}"
              data-block data-routine="${this._e(r.id)}" data-date="${d.date}" data-st="${st}" data-en="${en}" data-past="${past ? 1 : ""}" tabindex="0">
              <span class="grip t"></span><span class="grip b"></span>
              <div class="bt">${badge}${this._icon(r.icon, 18)} ${this._e(r.name || this._t("routines.unnamed"))}</div>
              <div class="bs num">${this._e(r.start)}–${this._e(r.end)} · ${this._e(who)}</div>${cps}</div>`;
          })
          .join("");
        const nowLine = d.date === today ? `<div class="now-line" style="top:${(nowMinutes() - CAL_FROM) * CAL_PX}px"></div>` : "";
        return `<div class="cal-col ${d.date === today ? "today" : ""} ${past ? "past" : ""}" data-col="${d.date}" data-past="${past ? 1 : ""}" style="height:${H}px;--hpx:${120 * CAL_PX}px">${blocks}${nowLine}</div>`;
      })
      .join("");
    const month = new Date(`${days[0]?.date || today}T12:00:00`).toLocaleDateString(this._locale, { year: "numeric", month: "long" });
    const nav = mode === "week"
      ? `<button class="iconbtn" data-act="week" data-arg="prev" aria-label="‹">‹</button><button class="btn sm" data-act="week" data-arg="now">${this._e(this._t("calendar.this_week"))}</button><button class="iconbtn" data-act="week" data-arg="next" aria-label="›">›</button>`
      : `<button class="iconbtn" data-act="cal-day" data-arg="prev" aria-label="‹">‹</button><button class="btn sm" data-act="cal-day" data-arg="today">${this._e(this._t("calendar.today"))}</button><button class="iconbtn" data-act="cal-day" data-arg="next" aria-label="›">›</button>`;
    const childSel = `<select data-calendar-child style="width:auto"><option value="">${this._e(this._t("history.all_children"))}</option>${this._data.children.map((c) => `<option value="${this._e(c.id)}" ${c.id === filter ? "selected" : ""}>${this._e(c.name)}</option>`).join("")}</select>`;
    return `<div class="cal-toolbar">${nav}<span class="cal-month">${this._e(month)}</span><span class="grow"></span>
        <span class="seg">${["day", "3day", "week"].map((m) => `<button class="${mode === m ? "on" : ""}" data-act="cal-mode" data-arg="${m}">${this._e(this._t(`calendar.${m}`))}</button>`).join("")}</span>${childSel}</div>
      ${this._undo ? `<div class="banner"><span class="grow">${this._e(this._undo.text)}</span><button class="btn sm" data-act="undo">${this._e(this._t("calendar.undo"))}</button></div>` : ""}
      <div class="card" style="padding:10px 10px 14px"><div class="cal-scroll"><div class="cal ${days.length === 1 ? "n1" : ""}" style="--n:${days.length}">
        <div></div>${heads}<div class="cal-hours" style="height:${H}px">${hours}</div>${cols}</div></div></div>
      <div class="row wrap small muted" style="margin:10px 4px;gap:14px"><span class="row" style="gap:6px"><span class="badge">✎</span>${this._e(this._t("calendar.legend_changed"))}</span><span class="row" style="gap:6px"><span class="badge">1</span>${this._e(this._t("calendar.legend_one"))}</span></div>
      <div class="hint">${this._e(this._t(this._isAdmin ? "calendar.drag_hint" : "calendar.hint"))}</div>
      ${this._viewTemplates()}`;
  }

  _viewTemplates() {
    const templates = this._data.templates || [];
    const rows = templates
      .map((x) => `<div class="mod-row"><div class="grow row nameblk" data-act="edit" data-coll="templates" data-arg="${this._e(x.id)}" tabindex="0">${this._icon(x.icon || "nav_calendar", 34)}<div class="grow"><b>${this._e(x.name)}</b> ${this._isAdmin ? `<span class="pen">✎</span>` : ""}<div class="muted small">${this._e(x.routines.map((id) => this._routine(id)?.name).filter(Boolean).join(" · ") || "—")}</div></div></div></div>`)
      .join("");
    const defaults = WEEKDAYS.map((d) => {
      const current = this._data.weekday_templates?.[String(d)] || "";
      return `<label class="field"><span>${this._e(this._t(`weekday.${d}`))}</span><select data-weekday-template="${d}" ${this._dis()}><option value="">${this._e(this._t("templates.own_days"))}</option>${templates.map((x) => `<option value="${this._e(x.id)}" ${x.id === current ? "selected" : ""}>${this._e(x.name)}</option>`).join("")}</select></label>`;
    }).join("");
    return `<div class="section-title">${this._icon("nav_routines", 34)}<h2>${this._e(this._t("templates.title"))}</h2>${this._isAdmin ? `<button class="btn primary" data-act="new" data-arg="templates">＋ ${this._e(this._t("templates.add"))}</button>` : ""}</div>
      <div class="card"><div class="hint">${this._e(this._t("templates.hint"))}</div>${rows || `<div class="empty">${this._e(this._t("templates.none"))}</div>`}
      ${templates.length ? `<h3 style="margin:18px 0 10px">${this._e(this._t("templates.weekdays"))}</h3><div class="form-grid" style="grid-template-columns:repeat(auto-fill,minmax(120px,1fr))">${defaults}</div>` : ""}</div>`;
  }

  // ------------------------------------------------------------ statistics

  _statRange() {
    const p = this._statPeriod;
    const today = this._todayStr();
    if (p.kind === "30") {
      return { from: addDays(today, -29), to: today };
    }
    if (p.kind === "all") {
      return { from: null, to: today };
    }
    if (p.kind === "custom" && p.from && p.to) {
      return p.from <= p.to ? { from: p.from, to: p.to } : { from: p.to, to: p.from };
    }
    return { from: addDays(today, -6), to: today };
  }

  // Tokens a transaction moved in the wallet (with its corrections).
  _walletAmount(tx) {
    return (tx.effective_lines || tx.lines).reduce((s, l) => s + (l.account === "wallet" ? l.amount : 0), 0);
  }

  _computeStats(child, history, events, from, to) {
    const today = this._todayStr();
    const dates = [...history.map((h) => h.timestamp.slice(0, 10)), ...events.map((e) => e.day || e.timestamp.slice(0, 10))].sort();
    let start = from || dates[0] || today;
    const end = to || today;
    const days = [];
    for (let d = start; d <= end && days.length < 400; d = addDays(d, 1)) {
      days.push(d);
    }
    start = days[0];
    const earned = Object.fromEntries(days.map((d) => [d, 0]));
    let spent = 0;
    let saved = 0;
    const bought = {};
    for (const h of history) {
      if (h.reversed_by || h.reverses || h.corrects) {
        continue;
      }
      const d = h.timestamp.slice(0, 10);
      const amount = this._walletAmount(h);
      if ((h.reason === "checkpoint_reward" || h.reason === "streak_reward") && d in earned) {
        earned[d] += Math.max(0, amount);
      }
      if (h.reason === "reward_redemption") {
        spent += -amount;
        const name = h.refs?.reward_name || this._t("reason.reward_redemption");
        bought[name] = (bought[name] || 0) + 1;
      }
      if (h.reason === "piggy_transfer") {
        saved += (h.effective_lines || h.lines).filter((l) => l.account === "piggy").reduce((s, l) => s + l.amount, 0);
      }
    }
    const per = {};
    let mOk = 0;
    let mN = 0;
    let eOk = 0;
    let eN = 0;
    for (const ev of events) {
      if (ev.type !== "checkpoint_done" && ev.type !== "checkpoint_missed") {
        continue;
      }
      const due = ev.due ? this._fmtClock(ev.due) : "";
      const p = per[ev.checkpoint_id] || (per[ev.checkpoint_id] = { name: ev.checkpoint_name, rname: ev.routine_name, icon: ev.icon, time: due, list: [], missed: 0 });
      if (ev.type === "checkpoint_missed") {
        p.missed += 1;
      } else {
        p.list.push(Math.round((ev.early_s || 0) / 60));
      }
      const ok = ev.type === "checkpoint_done" && ev.on_time;
      if (toMinutes(due) < 12 * 60) {
        mN++;
        mOk += ok ? 1 : 0;
      } else {
        eN++;
        eOk += ok ? 1 : 0;
      }
    }
    const cps = Object.values(per)
      .map((p) => {
        const n = p.list.length;
        const all = n + p.missed;
        return {
          ...p,
          n,
          avg: n ? Math.round(p.list.reduce((a, b) => a + b, 0) / n) : null,
          ok: all ? Math.round((100 * p.list.filter((x) => x >= 0).length) / all) : 0,
        };
      })
      .sort((a, b) => toMinutes(a.time) - toMinutes(b.time));
    const minutes = cps.flatMap((p) => p.list);
    const reached = cps.reduce((s, p) => s + p.list.filter((x) => x >= 0).length, 0);
    const counted = cps.reduce((s, p) => s + p.n + p.missed, 0);
    let tDone = 0;
    let tAll = 0;
    const progress = this._today?.progress || {};
    for (const r of this._todayDay()?.routines || []) {
      if (!applies(r.children, child.id)) {
        continue;
      }
      tAll += (r.routine?.tasks || []).length;
      tDone += Object.keys(progress[r.id]?.[child.id]?.tasks || {}).length;
    }
    return {
      days,
      earned,
      spent,
      saved,
      bought,
      cps,
      tDone,
      tAll,
      onTime: counted ? Math.round((100 * reached) / counted) : null,
      avg: minutes.length ? Math.round(minutes.reduce((a, b) => a + b, 0) / minutes.length) : null,
      morning: mN ? Math.round((100 * mOk) / mN) : null,
      evening: eN ? Math.round((100 * eOk) / eN) : null,
      total: Object.values(earned).reduce((a, b) => a + b, 0),
      from: start,
      to: end,
    };
  }

  _barChart(st, color) {
    const W = 560;
    const H = 170;
    const pad = 26;
    const bw = (W - 20) / Math.max(st.days.length, 1);
    const max = Math.max(1, ...Object.values(st.earned));
    const top = Object.entries(st.earned).sort((a, b) => b[1] - a[1])[0]?.[0];
    const today = this._todayStr();
    const many = st.days.length > 10;
    const step = Math.ceil(st.days.length / 10);
    let g = `<line x1="0" x2="${W}" y1="${H - pad}" y2="${H - pad}" stroke="var(--line)"/>`;
    st.days.forEach((d, i) => {
      const v = st.earned[d];
      const h = ((H - pad - 22) * v) / max;
      const x = 10 + i * bw + bw * 0.22;
      const w = bw * 0.56;
      const y = H - pad - h;
      const isToday = d === today;
      const label = many
        ? i % step === 0 || isToday ? String(new Date(`${d}T12:00:00`).getDate()) : ""
        : this._fmtDate(d, { weekday: "short" });
      const bar = !v
        ? ""
        : w >= 8
          ? `<path class="bar-m" d="M${x} ${H - pad} V${y + 4} Q${x} ${y} ${x + 4} ${y} H${x + w - 4} Q${x + w} ${y} ${x + w} ${y + 4} V${H - pad} Z" fill="${this._e(color)}"/>`
          : `<rect class="bar-m" x="${x}" y="${y}" width="${Math.max(w, 2)}" height="${h}" fill="${this._e(color)}"/>`;
      g += `<g data-tip="${this._e(this._fmtDate(d, { weekday: "long", month: "short", day: "numeric" }))}: ${v}">
        <rect class="hit" x="${10 + i * bw}" y="0" width="${bw}" height="${H}"/>${bar}
        ${(d === top && v) || isToday ? `<text class="v" x="${x + w / 2}" y="${y - 6}" text-anchor="middle">${v}</text>` : ""}
        <text x="${x + w / 2}" y="${H - 8}" text-anchor="middle" ${isToday ? `class="v"` : ""}>${this._e(label)}</text></g>`;
    });
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${this._e(this._t("stats.daily"))}">${g}</svg>`;
  }

  _cpChart(st) {
    if (!st.cps.length) {
      return `<div class="muted small">${this._e(this._t("stats.ins_none"))}</div>`;
    }
    const W = 560;
    const row = 44;
    const H = st.cps.length * row + 10;
    const mid = 400;
    const half = 140;
    const max = Math.max(10, ...st.cps.map((p) => Math.abs(p.avg || 0)));
    let g = `<line x1="${mid}" x2="${mid}" y1="0" y2="${H}" stroke="var(--line)" stroke-dasharray="3 3"/>`;
    st.cps.forEach((p, i) => {
      const y = 6 + i * row;
      const avg = p.avg ?? 0;
      const len = (half * Math.abs(avg)) / max;
      const ok = avg >= 0;
      const x = ok ? mid : mid - len;
      const counts = `${this._t("stats.done_count").replace("{n}", p.n)}${p.missed ? ` · ${this._t("stats.missed_count").replace("{n}", p.missed)}` : ""}`;
      g += `<g data-tip="${this._e(p.name)} · ${this._e(p.rname)} (${this._e(p.time)}): ${p.avg === null ? "—" : `${sign(avg)} ${this._e(this._t("stats.min"))}`} · ${p.ok}% · ${this._e(counts)}">
        <rect class="hit" x="0" y="${y - 4}" width="${W}" height="${row}"/>
        <image href="${this._iconUrl(p.icon || "checkpoint_flag", 26)}" x="0" y="${y}" width="26" height="26"/>
        <text x="32" y="${y + 11}" class="v">${this._e(p.name)}</text><text x="32" y="${y + 24}">${this._e(p.rname)}</text><text x="32" y="${y + 37}">${this._e(p.time)} · ${this._e(counts)} · ${p.ok}% ✓</text>
        ${len ? `<rect class="bar-m" x="${x}" y="${y + 5}" width="${Math.max(len, 3)}" height="16" rx="4" fill="var(${ok ? "--good" : "--warn"})"/>` : ""}
        ${p.avg === null ? "" : `<text class="v" x="${ok ? mid + len + 6 : mid - len - 6}" y="${y + 18}" text-anchor="${ok ? "start" : "end"}">${sign(avg)}′</text>`}</g>`;
    });
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${this._e(this._t("stats.by_cp"))}">${g}</svg>`;
  }

  _periodPicker() {
    const p = this._statPeriod;
    return `<div class="card flat stack" style="gap:10px"><div class="row wrap"><span class="lbl">${this._e(this._t("stats.period"))}</span>
      <span class="seg">${[["7", "stats.p7"], ["30", "stats.p30"], ["all", "stats.pall"], ["custom", "stats.pcustom"]].map(([k, l]) => `<button class="${p.kind === k ? "on" : ""}" data-act="period" data-arg="${k}">${this._e(this._t(l))}</button>`).join("")}</span></div>
      ${p.kind === "custom" ? `<div class="form-grid"><label class="field"><span>${this._e(this._t("history.from"))}</span><input type="date" data-period="from" value="${this._e(p.from || "")}"></label>
        <label class="field"><span>${this._e(this._t("history.to"))}</span><input type="date" data-period="to" value="${this._e(p.to || "")}"></label></div>` : ""}</div>`;
  }

  _viewStats(c) {
    const s = this._stats;
    if (!s || !s.history) {
      return `<div class="card empty">${this._e(this._t("common.loading"))}</div>`;
    }
    const range = this._statRange();
    const st = this._computeStats(c, s.history, s.events, range.from, range.to);
    const ins = [];
    const late = st.cps.filter((p) => p.avg !== null && p.avg < 0).sort((a, b) => a.avg - b.avg)[0];
    const best = st.cps.filter((p) => p.avg !== null && p.avg >= 0).sort((a, b) => b.avg - a.avg)[0];
    const missed = st.cps.filter((p) => p.missed).sort((a, b) => b.missed - a.missed)[0];
    if (late) {
      ins.push(["status_lock", this._t("stats.ins_late").replace("{cp}", this._e(late.name)).replace("{m}", -late.avg)]);
    }
    if (missed) {
      ins.push(["checkpoint_flag", this._t("stats.ins_missed").replace("{cp}", this._e(missed.name)).replace("{n}", missed.missed)]);
    }
    if (best) {
      ins.push(["celebrate_star", this._t("stats.ins_best").replace("{cp}", this._e(best.name)).replace("{m}", best.avg)]);
    }
    if (st.morning !== null && st.evening !== null) {
      ins.push(["routine_morning", this._t("stats.ins_mornev").replace("{a}", st.morning).replace("{b}", st.evening)]);
    }
    const bd = Object.entries(st.earned).sort((a, b) => b[1] - a[1])[0];
    if (bd && bd[1]) {
      ins.push(["streak_flame", this._t("stats.ins_bestday").replace("{d}", this._e(this._fmtDate(bd[0], { weekday: "long", month: "short", day: "numeric" }))).replace("{n}", bd[1])]);
    }
    const bought = Object.entries(st.bought);
    const target = this._data.settings.streak_target || 7;
    return `<div class="row" style="gap:14px">${this._avatar(c, 72)}<div class="grow"><div class="rt-title">${this._e(c.name)}</div><div class="muted small">${this._e(this._age(c.birth_date))}</div></div>
        <span class="bal">${this._icon("wallet", 28)}<span class="num">${c.balances.wallet}</span></span>${c.piggy_unlocked ? `<span class="bal">${this._icon("fn_piggy", 28)}<span class="num">${c.balances.piggy}</span></span>` : ""}</div>
      ${this._periodPicker()}
      <div class="kpis">
        <div class="kpi"><span class="lbl">${this._e(this._t("stats.today"))}</span><b>${st.tDone}/${st.tAll}</b><span class="small muted">${this._e(this._t("stats.tasks_today"))}</span></div>
        <div class="kpi"><span class="lbl">${this._e(this._t("stats.period"))}</span><b>+${st.total}</b><span class="small muted">${this._e(this._t("stats.tokens_period"))}</span></div>
        <div class="kpi"><span class="lbl">%</span><b>${st.onTime ?? "—"}${st.onTime !== null ? "%" : ""}</b><span class="small muted">${this._e(this._t("stats.on_time"))}</span></div>
        <div class="kpi"><span class="lbl">Ø</span><b>${st.avg !== null ? `${sign(st.avg)}′` : "—"}</b><span class="small muted">${this._e(this._t("stats.avg_early"))}</span></div>
        <div class="kpi"><span class="lbl">${this._icon("streak_flame", 14)}</span><b>${c.streak}/${target}</b><span class="small muted">${this._e(this._t("stats.streak"))}</span></div>
      </div>
      <div class="card flat"><h3 style="margin-bottom:6px">${this._e(this._t("stats.daily"))}</h3>${this._barChart(st, c.color || "#6CB8FF")}</div>
      <div class="card flat"><h3 style="margin-bottom:6px">${this._e(this._t("stats.by_cp"))}</h3>${this._cpChart(st)}</div>
      <div class="stack" style="gap:8px"><h3>${this._e(this._t("stats.insights"))}</h3>${ins.length ? ins.map(([i, text]) => `<div class="insight">${this._icon(i, 26)}<span>${text}</span></div>`).join("") : `<div class="muted">${this._e(this._t("stats.ins_none"))}</div>`}</div>
      <div class="kpis"><div class="kpi"><span class="lbl">${this._e(this._t("stats.spent"))}</span><b>${st.spent}</b></div><div class="kpi"><span class="lbl">${this._e(this._t("stats.saved"))}</span><b>${st.saved}</b></div></div>
      ${bought.length ? `<div class="field"><span>${this._e(this._t("stats.bought"))}</span><div class="row wrap" style="gap:6px">${bought.map(([n, k]) => `<span class="tag sun">${this._e(n)} ×${k}</span>`).join("")}</div></div>` : ""}
      <div class="src">${this._e(this._t("stats.source").replace("{from}", this._fmtDate(st.from, { month: "short", day: "numeric" })).replace("{to}", this._fmtDate(st.to, { month: "short", day: "numeric" })))}</div>`;
  }

  // ------------------------------------------------------------ children

  _viewChildren() {
    const week = this._childWeek;
    const today = this._todayStr();
    const cards = this._data.children
      .map((c, i) => {
        const device = c.device_id ? this._data.devices.find((d) => d.device_id === c.device_id)?.name || "?" : this._t("children.any_knob");
        const st = week
          ? this._computeStats(c, week.history.filter((h) => h.child_id === c.id), week.events.filter((e) => e.child_id === c.id), addDays(today, -6), today)
          : null;
        const pct = st?.tAll ? Math.round((100 * st.tDone) / st.tAll) : 0;
        const max = st ? Math.max(1, ...Object.values(st.earned)) : 1;
        const spark = st
          ? st.days.map((d) => `<span data-tip="${this._e(this._fmtDate(d, { weekday: "short" }))}: ${st.earned[d]}" style="flex:1;align-self:flex-end;height:${Math.max(3, (28 * st.earned[d]) / max)}px;border-radius:3px 3px 0 0;background:${this._e(c.color)};opacity:${d === today ? 1 : 0.65}"></span>`).join("")
          : "";
        return `<div class="card child-hero clickable ${c.active === false ? "inactive" : ""}" style="--c:${this._e(c.color)}" data-act="edit" data-coll="children" data-arg="${this._e(c.id)}" tabindex="0">
          <div class="child-top" style="margin-bottom:10px">${this._avatar(c, 88)}
            <div class="grow"><div class="name">${this._e(c.name)}</div><div class="muted small">${this._e(this._age(c.birth_date))}${c.active === false ? ` · ${this._e(this._t("common.inactive"))}` : ""}</div>
              <div class="row small" style="gap:4px;margin-top:4px">${this._icon("streak_flame", 18)}<b class="num">${c.streak}/${this._data.settings.streak_target}</b></div></div></div>
          <div class="balances" style="margin:0 0 12px;justify-content:flex-start"><span class="bal">${this._icon("wallet", 28)}<span class="num">${c.balances.wallet}</span></span>
            ${c.piggy_unlocked ? `<span class="bal">${this._icon("fn_piggy", 28)}<span class="num">${c.balances.piggy}</span></span>` : `<span class="bal">${this._icon("status_lock", 28)}<span class="muted small">${this._e(this._t("tokens.piggy"))}</span></span>`}</div>
          ${st ? `<div class="stack" style="gap:6px;margin-bottom:12px">
            <div class="row small"><span class="lbl grow">${this._e(this._t("children.today_prog"))}</span><b class="num">${st.tDone}/${st.tAll}</b></div><div class="mini-prog" style="--c:${this._e(c.color)}"><span style="width:${pct}%"></span></div>
            <div class="row small"><span class="lbl grow">${this._e(this._t("children.week"))}</span><b class="num">+${st.total}</b>${this._icon("token_coin_front", 16)}<span class="muted">· ${st.onTime ?? "—"}${st.onTime !== null ? "%" : ""} ✓</span></div>
            <div style="display:flex;gap:3px;height:28px">${spark}</div></div>` : ""}
          <div class="row wrap" style="gap:6px"><span class="tag">${this._icon("nav_settings", 16)} ${this._e(device)}</span><span class="grow"></span>
          ${this._isAdmin ? `<button class="iconbtn" data-act="move" data-arg="children:${this._e(c.id)}:-1" ${i === 0 ? "disabled" : ""} aria-label="▲">▲</button>
            <button class="iconbtn" data-act="move" data-arg="children:${this._e(c.id)}:1" ${i === this._data.children.length - 1 ? "disabled" : ""} aria-label="▼">▼</button>` : ""}</div>
        </div>`;
      })
      .join("");
    return `<div class="section-title" style="margin-top:6px">${this._icon("nav_children", 40)}<h2>${this._e(this._t("tab.children"))}</h2>${this._isAdmin ? `<button class="btn primary" data-act="new" data-arg="children">＋ ${this._e(this._t("children.add"))}</button>` : ""}</div>
      ${cards ? `<div class="grid g3">${cards}</div>` : `<div class="card empty">${this._e(this._t("children.none"))}</div>`}`;
  }

  // ------------------------------------------------------------ routines

  _viewRoutines() {
    const dots = (r) => WEEKDAYS.map((d) => `<span class="${!r.weekdays?.length || r.weekdays.includes(d) ? "on" : ""}">${this._e(this._t(`weekday.${d}`))}</span>`).join("");
    const cards = this._data.routines
      .map((r) => {
        const who = r.children?.length
          ? r.children.map((id) => this._child(id)).filter(Boolean).map((c) => this._avatar(c, 26)).join("")
          : `<span class="muted small">${this._e(this._t("routines.everyone"))}</span>`;
        const tasks = r.tasks || [];
        return `<div class="card rt-card ${r.active === false ? "inactive" : ""}" data-act="edit" data-coll="routines" data-arg="${this._e(r.id)}" tabindex="0">
          ${this._dial(r, 112, { label: r.start })}
          <div class="grow"><div class="rt-title">${this._e(r.name || this._t("routines.unnamed"))}</div>
            <div class="muted num small" style="font-weight:600">${this._e(r.start)}–${this._e(r.end)} · ${tasks.length} ${this._e(this._t("routines.tasks_count"))}${r.active === false ? ` · ${this._e(this._t("common.inactive"))}` : ""}</div>
            <div class="days">${dots(r)}</div>
            <div class="row" style="gap:4px">${who}<span class="grow"></span><span style="width:14px;height:14px;border-radius:4px;background:${this._e(r.color || "#6BCB77")}" title="${this._e(this._t("routines.color"))}"></span></div>
            <div class="strip" style="margin-top:6px">${tasks.slice(0, 10).map((x) => `<img src="${this._iconUrl(x.icon, 26)}" alt="">`).join("")}${tasks.length > 10 ? `<span class="muted small">+${tasks.length - 10}</span>` : ""}</div>
          </div></div>`;
      })
      .join("");
    const templates = (this._data.routine_templates || [])
      .map((x) => `<div class="mod-row">${this._icon(x.routine?.icon || "routine_generic", 36)}<b class="grow">${this._e(x.name)}</b>
        ${this._isAdmin ? `<button class="btn sm primary" data-act="from-rtemplate" data-arg="${this._e(x.id)}">＋ ${this._e(this._t("rtemplates.create"))}</button><button class="btn sm danger" data-act="delete-rtemplate" data-arg="${this._e(x.id)}">${this._e(this._t("common.delete"))}</button>` : ""}</div>`)
      .join("");
    return `<div class="section-title" style="margin-top:6px">${this._icon("nav_routines", 40)}<h2>${this._e(this._t("tab.routines"))}</h2>${this._isAdmin ? `<button class="btn primary" data-act="new" data-arg="routines">＋ ${this._e(this._t("routines.add"))}</button>` : ""}</div>
      ${cards ? `<div class="grid g2">${cards}</div>` : `<div class="card empty">${this._e(this._t("routines.none"))}${this._isAdmin ? `<br><br><button class="btn" data-act="defaults" data-arg="routines">${this._e(this._t("routines.add_defaults"))}</button>` : ""}</div>`}
      ${templates ? `<div class="section-title">${this._icon("routine_helper", 34)}<h2>${this._e(this._t("rtemplates.title"))}</h2></div><div class="card">${templates}</div>` : ""}`;
  }

  // ------------------------------------------------------------ rewards

  _rewardPicture(r, size = 96) {
    return r.image
      ? `<img src="${this._photoUrl(r.image)}" style="width:${size}px;height:${size}px;border-radius:50%;object-fit:cover" alt="">`
      : this._icon(r.icon || "fn_rewards", size);
  }

  _viewRewards() {
    const list = this._data.rewards;
    const cards = list
      .map((r, i) => `<div class="card rw ${r.active === false ? "inactive" : ""}" data-act="edit" data-coll="rewards" data-arg="${this._e(r.id)}" tabindex="0">
        ${r.kind === "piggy_unlock" ? `<span class="corner tag good" title="${this._e(this._t("rewards.piggy_unlock"))}">${this._icon("badge_piggy_plus", 16)}</span>` : ""}
        <div class="img">${this._rewardPicture(r)}</div>
        <div class="nm">${this._e(r.name)}</div>
        <div class="price">${this._icon("token_coin_front", 26)}<span class="num">${r.cost}</span></div>
        ${this._isAdmin ? `<div class="order"><button class="iconbtn" data-act="move" data-arg="rewards:${this._e(r.id)}:-1" ${i === 0 ? "disabled" : ""} aria-label="▲">▲</button><button class="iconbtn" data-act="move" data-arg="rewards:${this._e(r.id)}:1" ${i === list.length - 1 ? "disabled" : ""} aria-label="▼">▼</button></div>` : ""}
      </div>`)
      .join("");
    return `<div class="section-title" style="margin-top:6px">${this._icon("nav_rewards", 40)}<h2>${this._e(this._t("tab.rewards"))}</h2>${this._isAdmin ? `<button class="btn primary" data-act="new" data-arg="rewards">＋ ${this._e(this._t("rewards.add"))}</button>` : ""}</div>
      <div class="hint" style="margin-bottom:12px">${this._e(this._t("rewards.shop_hint"))}</div>
      ${cards ? `<div class="shop">${cards}</div>` : `<div class="card empty">${this._e(this._t("rewards.none"))}${this._isAdmin ? `<br><br><button class="btn" data-act="defaults" data-arg="rewards">${this._e(this._t("rewards.add_defaults"))}</button>` : ""}</div>`}`;
  }

  // ------------------------------------------------------------ tokens

  _viewTokens() {
    const cards = this._data.children
      .map((c) => {
        const a = this._adjust[c.id] || { amount: "", account: "wallet", note: "" };
        const quick = [-5, -1, 1, 2, 5, 10]
          .map((n) => `<button class="${n > 0 ? "pos" : "neg"} ${Number(a.amount) === n ? "on" : ""}" data-act="quick" data-arg="${this._e(c.id)}" data-n="${n}">${sign(n)}</button>`)
          .join("");
        return `<div class="card child-hero" style="--c:${this._e(c.color)}">
          <div class="child-top" style="margin-bottom:0">${this._avatar(c, 64)}<div class="name grow">${this._e(c.name)}</div></div>
          <div class="bigbal"><div>${this._icon("wallet", 44)}<div><div class="lbl">${this._e(this._t("tokens.wallet"))}</div><b>${c.balances.wallet}</b></div></div>
            <div ${c.piggy_unlocked ? "" : `class="inactive"`}>${this._icon(c.piggy_unlocked ? "fn_piggy" : "status_lock", 44)}<div><div class="lbl">${this._e(this._t("tokens.piggy"))}</div><b>${c.piggy_unlocked ? c.balances.piggy : "—"}</b></div></div></div>
          ${this._isAdmin ? `<div class="stack" style="gap:10px"><div class="lbl">${this._e(this._t("tokens.quick"))}</div><div class="quick">${quick}</div>
            <div class="form-grid" style="grid-template-columns:110px 1fr"><label class="field"><span>${this._e(this._t("tokens.amount"))}</span><input type="number" data-adj="${this._e(c.id)}:amount" value="${this._e(a.amount)}" placeholder="±"></label>
              <label class="field"><span>${this._e(this._t("tokens.account"))}</span><select data-adj="${this._e(c.id)}:account"><option value="wallet">${this._e(this._t("tokens.wallet"))}</option>${c.piggy_unlocked ? `<option value="piggy" ${a.account === "piggy" ? "selected" : ""}>${this._e(this._t("tokens.piggy"))}</option>` : ""}</select></label></div>
            <input data-adj="${this._e(c.id)}:note" value="${this._e(a.note)}" placeholder="${this._e(this._t("tokens.note"))}">
            <button class="btn sun" data-act="adjust" data-arg="${this._e(c.id)}" ${a.amount && Number(a.amount) !== 0 ? "" : "disabled"}>${this._icon("token_coin_front", 20)} ${this._e(this._t("tokens.apply"))}</button></div>` : ""}
        </div>`;
      })
      .join("");
    return `<div class="section-title" style="margin-top:6px">${this._icon("nav_tokens", 40)}<h2>${this._e(this._t("tab.tokens"))}</h2></div>
      <div class="wallets">${cards || `<div class="card empty">${this._e(this._t("children.none"))}</div>`}</div><p class="hint">${this._e(this._t("tokens.hint"))}</p>`;
  }

  // ------------------------------------------------------------ history

  _viewHistory() {
    const f = this._historyFilter;
    const opt = (value, label, current) => `<option value="${this._e(value)}" ${value === (current || "") ? "selected" : ""}>${this._e(label)}</option>`;
    const reasons = [...REASONS, ...(this._showEvents ? EVENT_REASONS : [])];
    const filters = `<div class="filters">
      <select data-filter="child">${opt("", this._t("history.all_children"), f.child)}${this._data.children.map((c) => opt(c.id, c.name, f.child)).join("")}</select>
      <select data-filter="reason">${opt("", this._t("history.all_types"), f.reason)}${reasons.map((r) => opt(r, this._t(`reason.${r}`, r), f.reason)).join("")}</select>
      <select data-filter="account">${opt("", this._t("history.all_accounts"), f.account)}${opt("wallet", this._t("tokens.wallet"), f.account)}${opt("piggy", this._t("tokens.piggy"), f.account)}</select>
      <label class="field"><span>${this._e(this._t("history.from"))}</span><input type="date" data-filter="from" value="${this._e(f.from || "")}"></label>
      <label class="field"><span>${this._e(this._t("history.to"))}</span><input type="date" data-filter="to" value="${this._e(f.to || "")}"></label>
      <input type="search" class="search" data-filter="search" placeholder="${this._e(this._t("history.search"))}" value="${this._e(f.search || "")}"></div>`;
    const entries = [
      ...this._history,
      ...this._historyEvents.map((ev) => ({ ...ev, event: true })),
    ].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    const link = (n) => `<a href="#tx-${n}" class="ref" data-act="goto" data-arg="${n}">#${n}</a>`;
    let last = "";
    let html = "";
    for (const tx of entries) {
      const d = localDate(new Date(tx.timestamp));
      if (d !== last) {
        html += `<div class="day-sep">${this._e(this._fmtDate(d, { weekday: "long", month: "long", day: "numeric" }))}</div>`;
        last = d;
      }
      const c = this._child(tx.child_id);
      const who = c ? `${this._avatar(c, 18)} ${this._e(c.name)}` : this._e(this._t("history.unknown_child"));
      if (tx.event) {
        html += `<div class="tx event"><span class="amt">${this._icon(tx.icon || (tx.type === "task_done" ? "routine_generic" : "checkpoint_flag"), 26)}</span>
          <div style="min-width:0"><div class="what">${this._e(tx.task_name || tx.checkpoint_name || this._t(`reason.${tx.type}`))}</div>
          <div class="meta">${this._e(this._fmtTime(tx.timestamp))} · ${who} · ${this._e(this._t(`reason.${tx.type}`))} · ${this._e(tx.routine_name || "")}</div></div><div></div></div>`;
        continue;
      }
      const amounts = tx.lines.map((l) => `<span class="amt ${l.amount < 0 ? "neg" : "pos"}">${sign(l.amount)}${l.account === "piggy" ? this._icon("fn_piggy", 18) : ""}</span>`).join("");
      let what = this._e(tx.refs?.reward_name || tx.refs?.checkpoint_name || tx.note || this._t(`reason.${tx.reason}`, tx.reason));
      if (tx.corrects) {
        what = `${this._e(this._t("history.correction_of")).replace("{n}", link(tx.target_seq))} <span class="num">${sign(tx.old_amount ?? 0)} → ${sign(tx.new_amount ?? 0)}</span>`;
      } else if (tx.reverses) {
        what = this._e(this._t("history.reversal_of")).replace("{n}", link(tx.target_seq));
      }
      let revisions = "";
      if (tx.correction_seqs?.length) {
        revisions += ` · ${this._e(this._t("history.revised_by"))} ${tx.correction_seqs.map(link).join(", ")} · <a class="ref" data-act="chain" data-arg="${this._e(tx.id)}">${this._e(this._t(this._expanded.has(tx.id) ? "history.chain_hide" : "history.chain"))}</a>`;
      }
      if (tx.reversal_seq) {
        revisions += ` · ${this._e(this._t("history.reversed_by"))} ${link(tx.reversal_seq)}`;
      }
      let chain = "";
      if (this._expanded.has(tx.id)) {
        const steps = this._history
          .filter((h) => h.corrects === tx.id)
          .sort((a, b) => a.seq - b.seq)
          .map((h) => `<div>${link(h.seq)} ${sign(h.old_amount ?? 0)} → ${sign(h.new_amount ?? 0)} · ${this._e(new Date(h.timestamp).toLocaleString(this._locale))} · ${this._e(this._t(`creator.${h.creator}`, h.creator))}${h.note ? ` · „${this._e(h.note)}”` : ""}</div>`)
          .join("");
        chain = `<div class="chain"><div>#${tx.seq} ${this._e(this._t("history.booked"))} ${tx.lines.map((l) => sign(l.amount)).join(" ")}</div>${steps}<b>${this._e(this._t("history.effective"))} ${tx.effective_lines.map((l) => sign(l.amount)).join(" ")}</b></div>`;
      }
      const actions = this._isAdmin && !tx.reversed_by && !tx.reverses && !tx.corrects
        ? `<div class="tx-actions"><button class="btn sm" data-act="correct" data-arg="${this._e(tx.id)}">${this._e(this._t("history.correct"))}</button><button class="btn sm danger" data-act="reverse" data-arg="${this._e(tx.id)}">${this._e(this._t("history.reverse"))}</button></div>`
        : `<div></div>`;
      html += `<div class="tx ${tx.reversed_by ? "dim" : ""} ${tx.corrects || tx.reverses ? "rev" : ""}" id="tx-${tx.seq}"><div class="row" style="gap:4px">${amounts}</div>
        <div style="min-width:0"><div class="what">${what}${(tx.corrects || tx.reverses) && tx.note ? ` · „${this._e(tx.note)}”` : ""}</div>
          <div class="meta"><span class="seq">#${tx.seq}</span> · ${this._e(this._fmtTime(tx.timestamp))} · ${who} · ${this._e(this._t(`reason.${tx.reason}`, tx.reason))} · ${this._e(this._t(`creator.${tx.creator}`, tx.creator))}${revisions}</div>${chain}</div>${actions}</div>`;
    }
    return `<div class="section-title" style="margin-top:6px">${this._icon("nav_history", 40)}<h2>${this._e(this._t("tab.history"))}</h2><span class="tag">${this._e(this._t("history.count").replace("{n}", entries.length))}</span></div>
      ${filters}<div class="row wrap" style="margin:-4px 0 12px"><label class="switch small"><input type="checkbox" data-show-events ${this._showEvents ? "checked" : ""}>${this._e(this._t("history.events"))}</label><span class="hint">${this._e(this._t("history.events_hint"))}</span></div>
      ${html || `<div class="card empty">${this._e(this._t("history.none"))}</div>`}`;
  }

  // ------------------------------------------------------------ notifications

  _viewNotifications() {
    if (!this._rules || !this._targets) {
      return `<div class="card empty">${this._e(this._t("common.loading"))}</div>`;
    }
    const dis = this._dis();
    const scripts = this._targets.scripts;
    const rules = this._rules.rules
      .map((rule, i) => {
        // Targets: notify actions, and scripts labelled for notifications
        // (all scripts with "show all").
        const shown = scripts.filter((sc) => sc.labelled || this._showAllScripts || sc.service === rule.service);
        const option = (value, label) => `<option value="${this._e(value)}" ${value === rule.service ? "selected" : ""}>${this._e(label)}</option>`;
        const notifyOptions = [...new Set([...this._targets.notify, ...(rule.service?.startsWith("notify.") ? [rule.service] : [])])].map((svc) => option(svc, svc)).join("");
        const scriptOptions = shown.map((sc) => option(sc.service, `${sc.name} (${sc.service})`)).join("");
        const target = `<select data-rule="${i}:service" data-rerender ${dis}><option value="">—</option>
          <optgroup label="${this._e(this._t("notifications.notify_group"))}">${notifyOptions}</optgroup>
          ${scriptOptions ? `<optgroup label="${this._e(this._t("notifications.script_group"))}">${scriptOptions}</optgroup>` : ""}</select>`;
        let mapping = "";
        const script = scripts.find((sc) => sc.service === rule.service);
        if (script) {
          const names = Object.keys(script.fields);
          const fieldOptions = (current, allowNone) =>
            (allowNone ? [`<option value="">—</option>`] : [])
              .concat(names.map((f) => `<option value="${this._e(f)}" ${f === current ? "selected" : ""}>${this._e(script.fields[f].name)} (${this._e(f)})</option>`))
              .join("");
          const messageField = rule.message_field || (names.find((f) => /message|text|uzenet|üzenet|body/i.test(f)) ?? "");
          if (!rule.message_field && messageField) {
            rule.message_field = messageField;
          }
          const extras = names
            .filter((f) => f !== rule.message_field && f !== rule.title_field)
            .map((f) => {
              const field = script.fields[f];
              const value = rule.extra?.[f] ?? "";
              const options = field.selector?.select?.options;
              const input = Array.isArray(options)
                ? `<select data-rule-extra="${i}:${this._e(f)}" ${dis}><option value="">—</option>${options
                    .map((o) => (typeof o === "string" ? { value: o, label: o } : o))
                    .map((o) => `<option value="${this._e(o.value)}" ${String(o.value) === String(value) ? "selected" : ""}>${this._e(o.label)}</option>`)
                    .join("")}</select>`
                : `<input data-rule-extra="${i}:${this._e(f)}" value="${this._e(value)}" ${dis}>`;
              return `<label class="field"><span>${this._e(field.name)} <span class="muted">(${this._e(f)}) ${this._e(field.description)}</span></span>${input}</label>`;
            })
            .join("");
          mapping = `<div class="card flat stack">
            <label class="field"><span>${this._e(this._t("notifications.message_field"))}</span><select data-rule="${i}:message_field" data-rerender ${dis}>${fieldOptions(rule.message_field, false)}</select></label>
            <label class="field"><span>${this._e(this._t("notifications.title_field"))}</span><select data-rule="${i}:title_field" data-rerender ${dis}>${fieldOptions(rule.title_field, true)}</select></label>
            ${extras ? `<div class="hint">${this._e(this._t("notifications.fixed_values"))}</div>${extras}` : ""}</div>`;
        }
        const events = this._rules.event_types
          .map((ev) => `<button class="chip noimg ${rule.events.includes(ev) ? "on" : ""}" data-act="rule-event" data-arg="${i}:${ev}" ${dis}>${this._e(this._t(`event.${ev}`, ev))}</button>`)
          .join("");
        const children = this._data.children
          .map((c) => `<button class="chip ${rule.children.includes(c.id) ? "on" : ""}" data-act="rule-child" data-arg="${i}:${this._e(c.id)}" ${dis}>${this._avatar(c, 22)}${this._e(c.name)}</button>`)
          .join("");
        const result = this._testResult?.[i];
        return `<div class="card stack ${rule.enabled !== false ? "" : "inactive"}">
          <div class="row">${this._icon("nav_notifications", 36)}<input class="grow" data-rule="${i}:name" value="${this._e(rule.name)}" placeholder="${this._e(this._t("notifications.rule_name"))}" ${dis} style="font-weight:700">
            <label class="switch" title="${this._e(this._t("common.active"))}"><input type="checkbox" data-rule="${i}:enabled" data-rerender ${rule.enabled !== false ? "checked" : ""} ${dis}></label>
            ${this._isAdmin ? `<button class="iconbtn" data-act="rule-remove" data-arg="${i}" aria-label="${this._e(this._t("common.delete"))}">✕</button>` : ""}</div>
          <label class="field"><span>${this._e(this._t("notifications.target"))}</span>${target}</label>
          ${mapping}
          <div class="field"><span>${this._e(this._t("notifications.events"))}</span><div class="row wrap" style="gap:6px">${events}</div></div>
          <div class="field"><span>${this._e(this._t("notifications.children"))}</span><div class="row wrap" style="gap:6px">${children}<span class="muted small">${this._e(this._t(rule.children.length ? "routines.only_these" : "routines.everyone"))}</span></div></div>
          ${this._isAdmin ? `<div class="row wrap"><button class="btn sm" data-act="rule-test" data-arg="${i}" ${rule.service ? "" : "disabled"}>✈ ${this._e(this._t("notifications.test"))}</button>
            ${result ? `<span class="tag ${result.ok ? "good" : "bad"}">${this._e(result.text)}</span>` : ""}</div>` : ""}
        </div>`;
      })
      .join("");
    const label = this._targets.label;
    const labelState = !label
      ? ""
      : this._targets.label_found
        ? `<span class="tag good">✓ ${this._e(this._t("notifications.label_ok"))}</span>`
        : `<span class="tag warn">${this._e(this._t("notifications.label_missing"))}</span>`;
    return `<div class="section-title" style="margin-top:6px">${this._icon("nav_notifications", 40)}<h2>${this._e(this._t("tab.notifications"))}</h2>
        ${this._isAdmin ? `<button class="btn" data-act="rule-add">＋ ${this._e(this._t("notifications.add"))}</button><button class="btn primary" data-act="rules-save">${this._e(this._t("common.save"))}</button>` : ""}</div>
      <p class="hint">${this._e(this._t("notifications.hint"))}</p>
      <div class="grid g2">
        <div class="card stack"><label class="field"><span>${this._e(this._t("notifications.label"))}</span><input data-setting="notification_label" value="${this._e(label)}" ${dis}></label>
          <div class="row wrap">${labelState}<span class="grow"></span>
          <label class="switch small"><input type="checkbox" data-show-all-scripts ${this._showAllScripts ? "checked" : ""}>${this._e(this._t("notifications.show_all"))}</label></div>
          <div class="hint">${this._e(this._t("notifications.label_hint"))}</div></div>
        ${rules || `<div class="card empty">${this._e(this._t("notifications.none"))}</div>`}
      </div>`;
  }

  // ------------------------------------------------------------ settings

  _viewSettings() {
    const s = this._data.settings;
    const sc = s.screen || {};
    const dis = this._dis();
    const languages = [{ code: LANGUAGE_AUTO, name: this._t("settings.language_auto") }, ...s.languages]
      .map((l) => `<option value="${this._e(l.code)}" ${l.code === s.language ? "selected" : ""}>${this._e(l.name)}</option>`)
      .join("");
    const num = (key, min, max, step = 1) => `<input type="number" min="${min}" max="${max}" step="${step}" data-setting="${key}" value="${s[key] ?? ""}" ${dis}>`;
    // The idle steps of the knob screen on one line.
    const maxT = Math.max(sc.off_after || 0, sc.blank_after || 0, sc.dim_after || 0, sc.saver_after || 0, 60);
    const mark = (k, label) => (sc[k] ? `<div class="mk" style="left:${(sc[k] / maxT) * 100}%"><i></i>${this._e(label)}<br><span class="num">${secondsToMinutes(sc[k])}′</span></div>` : "");
    const devices = this._data.devices
      .map((d) => {
        const kids = this._data.children.filter((c) => c.device_id === d.device_id);
        const own = d.screen || {};
        const bg = this._backgroundUrl(s.background || "");
        const fields = SCREEN_KEYS.map((k) =>
          k === "dim_level"
            ? `<label class="field"><span>${this._e(this._t(`screen.${k}`))}</span><input type="number" min="1" max="100" data-device-screen="${k}" data-device="${this._e(d.device_id)}" value="${own[k] ?? ""}" placeholder="${this._e(String(sc[k] ?? ""))}" ${dis}></label>`
            : `<label class="field"><span>${this._e(this._t(`screen.${k}`))}</span>${this._minuteInput(`data-device-screen="${k}" data-device="${this._e(d.device_id)}"`, own[k], sc[k] ?? "")}</label>`
        ).join("");
        return `<div class="knob-card stack" style="gap:10px"><div class="row wrap"><span class="knob-face" style="${bg ? `background-image:url('${bg}')` : ""}"></span>
          <div class="grow"><label class="field"><span>${this._e(this._t("settings.knob_name"))}</span><input data-devname="${this._e(d.device_id)}" value="${this._e(d.name)}" ${dis} style="font-weight:700"></label></div>
          <div class="row" style="gap:4px">${kids.length ? kids.map((c) => this._avatar(c, 30)).join("") : `<span class="tag">${this._e(this._t("settings.knob_everyone"))}</span>`}</div></div>
          ${d.encrypted ? "" : `<div class="warnbox">${this._e(this._t("settings.knob_unencrypted"))}</div>`}
          ${this._isAdmin ? `<div class="row wrap"><button class="btn sm" data-act="rotate-token" data-arg="${this._e(d.device_id)}">🔑 ${this._e(this._t("settings.knob_new_key"))}</button>${d.can_restart ? `<button class="btn sm" data-act="restart-knob" data-arg="${this._e(d.device_id)}">↻ ${this._e(this._t("settings.knob_restart"))}</button>` : ""}</div>` : ""}
          <details><summary>${this._e(this._t("screen.own"))}</summary><div class="hint">${this._e(this._t("screen.own_hint"))}</div>
            <div class="form-grid" style="margin-top:10px">${fields}
            <label class="field"><span>${this._e(this._t("screen.saver_type"))}</span><select data-device-screen-type data-device="${this._e(d.device_id)}" ${dis}><option value="">${this._e(this._t("screen.general"))}</option>${SAVER_TYPES.map((x) => `<option value="${x}" ${own.saver_type === x ? "selected" : ""}>${this._e(this._t(`screen.saver_${x}`))}</option>`).join("")}</select></label></div></details></div>`;
      })
      .join("");
    const uploaded = s.background && !s.background.startsWith("bg_") ? s.background : "";
    const backgrounds = `<div class="bgs"><button class="bg ${!s.background ? "on" : ""}" data-act="bg-set" data-arg="" ${dis}>${this._e(this._t("background.none"))}</button>
      ${(this._data.backgrounds || []).map((b) => `<button class="bg ${s.background === b ? "on" : ""}" style="background-image:url('${this._backgroundUrl(b)}')" data-act="bg-set" data-arg="${this._e(b)}" aria-label="${this._e(b)}" ${dis}></button>`).join("")}
      ${uploaded ? `<button class="bg on" style="background-image:url('${this._backgroundUrl(uploaded)}')" data-act="bg-set" data-arg="${this._e(uploaded)}" aria-label="${this._e(this._t("background.own"))}" ${dis}></button>` : ""}
      ${this._isAdmin ? `<label class="bg upload" title="${this._e(this._t("background.upload"))}">＋<br>${this._e(this._t("background.own"))}<input type="file" accept="image/*" data-upload-bg hidden></label>` : ""}</div>`;
    const weekdays = WEEKDAYS.map((d) => `<option value="${d}" ${Number(s.piggy_interest_weekday) === d ? "selected" : ""}>${this._e(this._t(`weekday.${d}`))}</option>`).join("");
    return `<div class="section-title" style="margin-top:6px">${this._icon("nav_settings", 40)}<h2>${this._e(this._t("settings.title"))}</h2></div>
      ${this._isAdmin ? "" : `<div class="banner">${this._icon("status_lock", 28)} ${this._e(this._t("settings.admin_only"))}</div>`}
      <div class="set-grid">
        <div class="card"><h3>${this._e(this._t("settings.general"))}</h3>
          <label class="field"><span>${this._e(this._t("settings.language"))}</span><select data-setting="language" ${dis}>${languages}</select></label>
          <div class="hint">${this._e(this._t("settings.language_hint"))}</div>
          <div class="field"><span>${this._e(this._t("settings.animation"))}</span><div class="seg">${["full", "reduced", "off"].map((m) => `<button class="${s.animation_mode === m ? "on" : ""}" data-act="set-setting" data-key="animation_mode" data-arg="${m}" ${dis}>${this._e(this._t(`settings.animation_${m}`))}</button>`).join("")}</div></div>
          <label class="field"><span>${this._e(this._t("settings.inactivity"))}</span>${this._minuteInput(`data-setting="inactivity_s"`, s.inactivity_s, "", 0.5)}</label>
          <label class="field"><span>${this._e(this._t("settings.routine_menu_grace"))}</span>${this._minuteInput(`data-setting="routine_menu_grace_s"`, s.routine_menu_grace_s)}</label>
        </div>
        <div class="card"><h3>${this._e(this._t("screen.title"))}</h3>
          <div class="timeline"><div class="track"></div>${mark("saver_after", this._t("screen.saver_type"))}${mark("dim_after", "☾")}${mark("blank_after", "■")}${mark("off_after", "⏻")}</div>
          <div class="form-grid">${SCREEN_KEYS.map((k) => `<label class="field"><span>${this._e(this._t(`screen.${k}`))}</span>${k === "dim_level" ? `<input type="number" min="1" max="100" data-screen="${k}" value="${sc[k] ?? ""}" ${dis}>` : this._minuteInput(`data-screen="${k}"`, sc[k])}</label>`).join("")}</div>
          <div class="field"><span>${this._e(this._t("screen.saver_type"))}</span><div class="seg">${SAVER_TYPES.map((x) => `<button class="${(sc.saver_type || "balls") === x ? "on" : ""}" data-act="saver" data-arg="${x}" ${dis}>${this._e(this._t(`screen.saver_${x}`))}</button>`).join("")}</div></div>
          <div class="hint">${this._e(this._t("screen.hint"))}</div></div>
        <div class="card"><h3>${this._e(this._t("background.title"))}</h3>${backgrounds}<div class="hint">${this._e(this._t("background.hint"))}</div></div>
        <div class="card"><h3>${this._e(this._t("settings.knobs"))}</h3>${devices || `<div class="muted">${this._e(this._t("settings.no_knobs"))}</div>`}<div class="hint">${this._e(this._t("settings.knobs_hint"))}</div></div>
        <div class="card"><h3>${this._icon("streak_flame", 26)} ${this._e(this._t("settings.streak"))}</h3><div class="form-grid">
          <label class="field"><span>${this._e(this._t("settings.streak_target"))}</span>${num("streak_target", 0, 365)}</label>
          <label class="field"><span>${this._e(this._t("settings.streak_reward"))}</span>${num("streak_reward", 0, 1000)}</label></div></div>
        <div class="card"><h3>${this._icon("fn_piggy", 26)} ${this._e(this._t("settings.piggy"))}</h3><div class="form-grid">
          <label class="field"><span>${this._e(this._t("settings.interest_percent"))}</span>${num("piggy_interest_percent", 0, 100, 0.5)}</label>
          <label class="field"><span>${this._e(this._t("settings.interest_day"))}</span><select data-setting="piggy_interest_weekday" ${dis}>${weekdays}</select></label>
          <label class="field"><span>${this._e(this._t("settings.interest_time"))}</span><input type="time" data-setting="piggy_interest_time" value="${this._e(s.piggy_interest_time)}" ${dis}></label>
          <label class="field"><span>${this._e(this._t("settings.interest_min"))}</span>${num("piggy_interest_min", 0, 1000)}</label>
          <label class="field"><span>${this._e(this._t("settings.interest_max"))}</span>${num("piggy_interest_max", 0, 1000)}</label></div></div>
        ${this._isAdmin ? `<div class="card"><h3>${this._e(this._t("settings.data"))}</h3><div class="hint">${this._e(this._t("settings.export_hint"))}</div><div><button class="btn" data-act="export">⇩ ${this._e(this._t("settings.export"))}</button></div></div>` : ""}
      </div>
      <p class="muted small">${this._e(this._t("panel.version"))}: <span class="num">${this._e(this._version)}</span></p>`;
  }

  // ------------------------------------------------------------ editors

  _newItem(collection) {
    switch (collection) {
      case "children":
        return {
          name: "",
          color: PRESET_COLORS[(this._data.children.length || 0) % PRESET_COLORS.length],
          avatar: "avatar_00",
          birth_date: "",
          active: true,
          // Locked when a reward can unlock it, open otherwise.
          piggy_unlocked: !this._data.rewards.some((r) => r.kind === "piggy_unlock" && r.active !== false),
        };
      case "rewards":
        return { name: "", icon: "fn_rewards", cost: 5, active: true, kind: "normal" };
      case "templates":
        return { name: "", icon: "nav_calendar", routines: [] };
      default:
        return {
          name: "",
          icon: "routine_generic",
          active: true,
          on_device: true,
          weekdays: [...WEEKDAYS],
          start: "07:00",
          end: "08:00",
          children: [],
          base_color: "#6BCB77",
          zones: [
            { offset_min: 15, color: "#FF9F43" },
            { offset_min: 5, color: "#FF6B6B" },
          ],
          checkpoints: [],
          tasks: [],
          color: ROUTINE_COLORS.find((c) => !this._data.routines.some((r) => r.color === c)) || ROUTINE_COLORS[this._data.routines.length % ROUTINE_COLORS.length],
        };
    }
  }

  _newRow(kind) {
    switch (kind) {
      case "zone":
        return { offset_min: 10, color: "#FF9F43" };
      case "checkpoint":
        return {
          id: uid(),
          name: "",
          icon: "checkpoint_flag",
          time: this._edit.item.end || "08:00",
          children: [],
          required_for_streak: true,
          reward_bands: [
            { min_early_min: 10, tokens: 3 },
            { min_early_min: 0, tokens: 2 },
          ],
        };
      case "band":
        return { min_early_min: 0, tokens: 1 };
      default:
        return { id: uid(), icon: "task_clothes", label: "", checkpoint_id: "" };
    }
  }

  // A new routine from a saved routine template: its own ids, the template's
  // children (also on its checkpoints).
  _fromRoutineTemplate(id) {
    const template = (this._data.routine_templates || []).find((t) => t.id === id);
    const item = { ...this._newItem("routines"), ...clone(template?.routine || {}) };
    item.children = item.children || [];
    const cpIds = {};
    item.checkpoints = (item.checkpoints || []).map((cp) => {
      const copy = { ...cp, id: uid(), children: cp.children || [] };
      cpIds[cp.id] = copy.id;
      return copy;
    });
    item.tasks = (item.tasks || []).map((t) => ({ ...t, id: uid(), checkpoint_id: t.checkpoint_id ? cpIds[t.checkpoint_id] || "" : "" }));
    return item;
  }

  // Fills the routine form from a saved template: a new routine, or one day of
  // a routine (that day keeps its id).
  _applyRoutineTemplate(id) {
    const current = this._edit.item;
    const filled = this._fromRoutineTemplate(id);
    // The template's children; a template saved without any keeps the form's.
    const children = filled.children.length ? filled.children : current.children || [];
    this._edit.item =
      this._edit.coll === "day"
        ? { ...current, ...filled, id: current.id, children, weekdays: current.weekdays }
        : { ...filled, color: current.color, children };
  }

  async _createDefaults(kind) {
    const t = (k) => this._t(k);
    if (kind === "routines") {
      const tasks = (icons) => icons.map((icon) => ({ id: uid(), icon, label: "", checkpoint_id: "" }));
      const band = [
        { min_early_min: 10, tokens: 3 },
        { min_early_min: 0, tokens: 2 },
      ];
      const routines = [
        {
          ...this._newItem("routines"),
          name: t("defaults.morning"),
          icon: "routine_morning",
          weekdays: [0, 1, 2, 3, 4],
          start: "07:00",
          end: "07:45",
          checkpoints: [{ id: uid(), name: t("defaults.ready"), icon: "task_door_ready", time: "07:45", children: [], required_for_streak: true, reward_bands: band }],
          tasks: tasks(["task_wake_up", "task_toilet", "task_clothes", "task_breakfast", "task_toothbrush", "task_shoes", "task_coat"]),
        },
        {
          ...this._newItem("routines"),
          name: t("defaults.evening"),
          icon: "routine_evening",
          start: "19:00",
          end: "20:00",
          checkpoints: [{ id: uid(), name: t("defaults.bed"), icon: "task_bed", time: "20:00", children: [], required_for_streak: true, reward_bands: band }],
          tasks: tasks(["task_tidy_up", "task_bath", "task_pajamas", "task_toothbrush", "task_story"]),
        },
      ];
      for (const item of routines) {
        await this._ws({ type: "kis_segito/save", collection: "routines", item });
      }
    } else {
      const rewards = [
        ["reward_long_story", 5],
        ["reward_treat", 3],
        ["reward_choose_game", 8],
        ["reward_family_activity", 15],
        ["reward_toy_car", 25],
        ["fn_piggy", 10, "piggy_unlock"],
      ];
      for (const [icon, cost, kind2] of rewards) {
        await this._ws({
          type: "kis_segito/save",
          collection: "rewards",
          item: { name: t(`defaults.${icon}`), icon, cost, active: true, kind: kind2 || "normal" },
        });
      }
    }
    this._toast(t("toast.saved"));
    await this._load();
  }

  async _openEdit(coll, id, extra = {}) {
    const found = id ? this._data[coll].find((x) => x.id === id) : null;
    const item = found ? clone(found) : this._newItem(coll);
    delete item.balances;
    delete item.streak;
    this._edit = { coll, item, isNew: !found, readonly: !this._isAdmin, ...extra };
    this._picker = null;
    this._more = false;
    this._drawerScroll = 0;
    this._rtplSaved = null;
    this._sec = extra.sec || (coll === "children" ? (this._isAdmin && found ? "data" : found ? "stats" : "data") : "basics");
    if (coll === "children" && found) {
      this._stats = { childId: found.id };
      this._render();
      await this._loadStats();
    } else {
      this._stats = null;
    }
    this._render();
  }

  // The day of the shown week (or this week) for a date.
  _dayData(dateStr) {
    return this._week?.days?.find((d) => d.date === dateStr) || this._todayWeek?.days?.find((d) => d.date === dateStr) || null;
  }

  // Opens the routine editor for one date ("only this day").
  _openDayEditor(dateStr, routineId, time) {
    const day = this._dayData(dateStr);
    const running = routineId ? day?.routines?.find((r) => r.id === routineId) : null;
    const source = routineId ? this._routine(routineId) : null;
    let item;
    if (running) {
      item = clone(running.routine);
    } else if (source) {
      item = clone(source);
    } else {
      const start = time || "16:00";
      item = { ...this._newItem("routines"), start, end: shiftTime(start, 60) };
    }
    delete item.one_day;
    item.zones = item.zones || [];
    item.checkpoints = item.checkpoints || [];
    item.tasks = item.tasks || [];
    item.children = item.children || [];
    this._edit = {
      coll: "day",
      date: dateStr,
      newDate: dateStr,
      routine_id: routineId || null,
      item,
      base: running?.one_day && !running?.moved_from ? null : source ? clone(source) : null,
      changed: Boolean(running && this._changedOccurrence(running)),
      oneDay: Boolean(running?.one_day && !running?.moved_from),
      isNew: !routineId,
      readonly: dateStr < this._todayStr() || !this._isAdmin,
    };
    this._sec = "basics";
    this._picker = null;
    this._more = false;
    this._drawerScroll = 0;
    this._rtplSaved = null;
    this._render();
  }

  // A click on a calendar block: an occurrence changed for its day opens in
  // the "only this day" editor; an unchanged one asks first (this occurrence
  // or the whole series). Past days and read-only users only view it.
  _openFromCalendar(dateStr, routineId) {
    const day = this._dayData(dateStr);
    const running = day?.routines?.find((r) => r.id === routineId);
    const isSeries = Boolean(this._routine(routineId));
    if (this._isAdmin && dateStr >= this._todayStr() && isSeries && running && !running.one_day && !this._changedOccurrence(running)) {
      this._dialog = { type: "scope", date: dateStr, routineId };
      this._render();
      return;
    }
    this._openDayEditor(dateStr, routineId);
  }

  _childChips(path) {
    const list = this._get(path) || [];
    const chips = this._data.children
      .map((c) => `<button class="chip ${list.includes(c.id) ? "on" : ""}" data-act="toggle-child" data-path="${path}" data-arg="${this._e(c.id)}">${this._avatar(c, 22)}${this._e(c.name)}</button>`)
      .join("");
    return `<div class="row wrap" style="gap:6px">${chips}<span class="muted small">${this._e(this._t(list.length ? "routines.only_these" : "routines.everyone"))}</span></div>`;
  }

  // The child's picture (uploaded photo, else the chosen avatar): a click or
  // the pencil opens the avatar list (with photo upload); the red X removes
  // the photo, which brings back the avatar.
  _avatarField(c) {
    const picture = c.avatar_image
      ? `<img class="photo" src="${this._photoUrl(c.avatar_image)}" width="132" height="132" alt="">`
      : this._icon(c.avatar || "avatar_00", 132);
    const edit = this._t("children.avatar_change");
    return `<div class="avatar-edit" style="--c:${this._e(c.color || "#6CB8FF")}">
        <button class="plain face" data-act="pick" data-path="avatar" data-arg="avatar" title="${this._e(edit)}">${picture}</button>
        <button class="plain corner left" data-act="pick" data-path="avatar" data-arg="avatar" title="${this._e(edit)}">${this._icon("action_edit", 24)}</button>
        ${c.avatar_image ? `<button class="plain corner right" data-act="clear-picture" data-arg="avatar_image" title="${this._e(this._t("children.photo_remove"))}">${this._icon("action_x", 24)}</button>` : ""}
      </div>`;
  }

  _editChild() {
    const c = this._edit.item;
    const nav = this._edit.isNew
      ? ""
      : `<div class="sec-nav">${[["stats", this._t("stats.title")], ["data", this._t("stats.data")]].map(([k, l]) => `<button class="${this._sec === k ? "on" : ""}" data-act="sec" data-arg="${k}">${this._e(l)}</button>`).join("")}</div>`;
    if (this._sec === "stats" && !this._edit.isNew) {
      return { title: c.name, nav, body: this._viewStats(this._child(c.id) || c), plain: true };
    }
    const close = SEMANTIC_COLORS.some((x) => colorDistance(x, c.color || "#000000") < 60);
    const knobs = [`<option value="">${this._e(this._t("children.any_knob"))}</option>`]
      .concat(this._data.devices.map((d) => `<option value="${this._e(d.device_id)}" ${d.device_id === c.device_id ? "selected" : ""}>${this._e(d.name)}</option>`))
      .join("");
    return {
      title: this._edit.readonly ? c.name : this._t(this._edit.isNew ? "children.add" : "children.edit"),
      nav,
      body: `<div class="row wrap" style="gap:16px">${this._avatarField(c)}<div class="grow stack" style="gap:10px;min-width:200px">
          <label class="field"><span>${this._e(this._t("common.name"))}</span><input data-path="name" value="${this._e(c.name)}"></label>
          <label class="field"><span>${this._e(this._t("children.birth_date"))}</span><input type="date" data-path="birth_date" value="${this._e(c.birth_date || "")}"></label></div></div>
        <div class="field"><span>${this._e(this._t("children.color"))}</span><div class="row wrap">${PRESET_COLORS.map((x) => `<button class="swatch ${x === c.color ? "on" : ""}" style="background:${x}" data-act="set" data-path="color" data-v="${x}" aria-label="${x}"></button>`).join("")}<input type="color" data-path="color" data-rerender value="${this._e(c.color)}"></div>
          ${close ? `<div class="warnbox">${this._e(this._t("children.color_warning"))}</div>` : ""}</div>
        <label class="field"><span>${this._e(this._t("children.knob"))}</span><select data-path="device_id">${knobs}</select></label>
        <div class="hint">${this._e(this._t("children.knob_hint"))}</div>
        <label class="switch"><input type="checkbox" data-path="piggy_unlocked" ${c.piggy_unlocked ? "checked" : ""}>${this._icon("fn_piggy", 26)} ${this._e(this._t("children.piggy_unlocked"))}</label>
        <label class="switch"><input type="checkbox" data-path="active" ${c.active !== false ? "checked" : ""}>${this._e(this._t("common.active"))}</label>`,
    };
  }

  _editReward() {
    const r = this._edit.item;
    return {
      title: this._edit.readonly ? r.name : this._t(this._edit.isNew ? "rewards.add" : "rewards.edit"),
      body: `<div class="card flat stack" style="align-items:center;text-align:center">
          <div class="rw preview"><div class="img">${this._rewardPicture(r)}</div>
          <div class="nm">${this._e(r.name || "…")}</div><div class="price">${this._icon("token_coin_front", 26)}<span class="num">${Number(r.cost) || 0}</span></div></div>
          <div class="row wrap" style="justify-content:center">${r.image ? "" : `<button class="btn sm" data-act="pick" data-path="icon" data-arg="reward">${this._e(this._t("picture.icon"))}</button>`}
            <label class="btn sm">📷 ${this._e(this._t(r.image ? "picture.replace" : "picture.upload"))}<input type="file" accept="image/*" data-crop-upload="image" hidden></label>
            ${r.image ? `<button class="btn sm ghost" data-act="photo-icon">${this._e(this._t("picture.remove"))}</button>` : ""}</div>
          <div class="hint">${this._e(this._t("picture.hint"))}</div></div>
        <label class="field"><span>${this._e(this._t("common.name"))}</span><input data-path="name" data-live value="${this._e(r.name)}"></label>
        <div class="field"><span>${this._e(this._t("rewards.cost"))}</span><div class="row wrap"><span class="stepper"><button data-act="cost" data-d="-1" aria-label="-1">−</button><span>${Number(r.cost) || 0}</span><button data-act="cost" data-d="1" aria-label="+1">+</button></span>
          <input type="number" class="short" min="0" data-path="cost" data-live value="${this._e(r.cost)}"><span class="grow">${this._pile(Number(r.cost) || 0, 20)}</span></div></div>
        <div class="field"><span>${this._e(this._t("rewards.kind"))}</span><div class="seg"><button class="${r.kind !== "piggy_unlock" ? "on" : ""}" data-act="set" data-path="kind" data-v="normal">${this._e(this._t("rewards.normal"))}</button><button class="${r.kind === "piggy_unlock" ? "on" : ""}" data-act="set" data-path="kind" data-v="piggy_unlock">${this._icon("fn_piggy", 20)} ${this._e(this._t("rewards.piggy_unlock"))}</button></div></div>
        <label class="switch"><input type="checkbox" data-path="active" ${r.active !== false ? "checked" : ""}>${this._e(this._t("common.active"))}</label>`,
    };
  }

  _editTemplate() {
    const x = this._edit.item;
    return {
      title: this._edit.readonly ? x.name : this._t(this._edit.isNew ? "templates.add" : "templates.edit"),
      body: `<label class="field"><span>${this._e(this._t("common.name"))}</span><input data-path="name" value="${this._e(x.name)}"></label>
        <div class="field"><span>${this._e(this._t("templates.routines"))}</span><div class="row wrap" style="gap:6px">${this._data.routines.map((r) => `<button class="chip ${x.routines.includes(r.id) ? "on" : ""}" data-act="toggle-routine" data-arg="${this._e(r.id)}">${this._icon(r.icon, 22)} ${this._e(r.name || this._t("routines.unnamed"))}</button>`).join("")}</div></div>`,
    };
  }

  _editRoutine() {
    const ed = this._edit;
    const r = ed.item;
    const dayMode = ed.coll === "day";
    const base = ed.base;
    // In "only this day" mode, sections that differ from the routine are marked.
    const diff = (key) =>
      dayMode && base && JSON.stringify(r[key] ?? null) !== JSON.stringify(base[key] ?? null)
        ? ` <span class="badge" title="${this._e(this._t("calendar.changed"))}">✎</span>`
        : "";
    const templates = this._data.routine_templates || [];
    const chooser = (dayMode || ed.isNew) && !ed.readonly && templates.length
      ? `<label class="field"><span>${this._e(this._t("rtemplates.use"))}</span><select data-rtemplate-apply><option value="">—</option>${templates.map((x) => `<option value="${this._e(x.id)}">${this._e(x.name)}</option>`).join("")}</select></label>`
      : "";
    const similar = r.color && this._data.routines.some((x) => x.id !== r.id && x.color && colorDistance(x.color, r.color) < 50);
    const basics = `${chooser}
      <div class="row" style="gap:14px"><button class="pick" data-act="pick" data-path="icon" data-arg="routine">${this._icon(r.icon, 64)}</button>
        <label class="field grow"><span>${this._e(this._t("common.name"))}${diff("name")}</span><input data-path="name" data-live value="${this._e(r.name)}"></label></div>
      ${dayMode ? `<label class="field" style="max-width:240px"><span>${this._e(this._t("day.date"))}</span><input type="date" data-edit-date min="${this._e(this._todayStr())}" value="${this._e(ed.newDate)}"></label>` : ""}
      <div class="form-grid"><label class="field"><span>${this._e(this._t("routines.start"))}${diff("start")}</span><input type="time" data-path="start" data-live value="${this._e(r.start)}"></label>
        <label class="field"><span>${this._e(this._t("routines.end"))}${diff("end")}</span><input type="time" data-path="end" data-live value="${this._e(r.end)}"></label></div>
      ${dayMode ? "" : `<div class="field"><span>${this._e(this._t("routines.days"))}</span><div class="row wrap" style="gap:6px">${WEEKDAYS.map((d) => `<button class="chip noimg ${(r.weekdays || []).includes(d) ? "on" : ""}" data-act="weekday" data-arg="${d}">${this._e(this._t(`weekday.${d}`))}</button>`).join("")}</div></div>`}
      <div class="field"><span>${this._e(this._t("routines.children"))}${diff("children")}</span>${this._childChips("children")}</div>
      <label class="switch"><input type="checkbox" data-path="on_device" ${r.on_device !== false ? "checked" : ""}>${this._e(this._t("routines.on_device"))}</label>
      ${dayMode ? "" : `<label class="switch"><input type="checkbox" data-path="active" ${r.active !== false ? "checked" : ""}>${this._e(this._t("common.active"))}</label>`}`;
    const look = `<div class="field"><span>${this._e(this._t("routines.color"))}${diff("color")}</span><div class="row wrap">${ROUTINE_COLORS.map((x) => `<button class="swatch ${x === r.color ? "on" : ""}" style="background:${x}" data-act="set" data-path="color" data-v="${x}" aria-label="${x}"></button>`).join("")}<input type="color" data-path="color" data-rerender value="${this._e(r.color || "#6BCB77")}"></div>
        ${similar ? `<div class="warnbox">${this._e(this._t("routines.color_similar"))}</div>` : ""}<div class="hint">${this._e(this._t("routines.color_hint"))}</div></div>
      <h3>${this._e(this._t("routines.zones"))}${diff("zones")}</h3><div class="hint">${this._e(this._t("routines.zones_hint"))}</div>
      <div class="row"><input type="color" data-path="base_color" data-rerender value="${this._e(r.base_color || "#6BCB77")}"><span>${this._e(this._t("routines.base_color"))}${diff("base_color")}</span></div>
      ${r.zones.map((z, i) => `<div class="row wrap"><input type="color" data-path="zones.${i}.color" data-rerender value="${this._e(z.color)}"><span>${this._e(this._t("routines.zone_from"))}</span><input type="number" class="short" min="0" data-path="zones.${i}.offset_min" data-live value="${this._e(z.offset_min)}"><span class="muted">${this._e(this._t("routines.min_before_end"))}</span><span class="grow"></span><button class="iconbtn" data-act="remove" data-path="zones" data-arg="${i}" aria-label="✕">✕</button></div>`).join("")}
      <button class="btn sm" data-act="add" data-path="zones" data-arg="zone" style="align-self:flex-start">＋ ${this._e(this._t("routines.add_zone"))}</button>`;
    const cps = `<div class="hint">${this._e(this._t("routines.checkpoints_hint"))}</div>
      ${r.checkpoints.map((cp, i) => `<div class="card flat stack" style="gap:10px">
        <div class="row wrap"><button class="pick" data-act="pick" data-path="checkpoints.${i}.icon" data-arg="checkpoint">${this._icon(cp.icon || "checkpoint_flag", 44)}</button>
          <input class="grow" style="min-width:120px" data-path="checkpoints.${i}.name" value="${this._e(cp.name)}" placeholder="${this._e(this._t("common.name"))}">
          <input type="time" style="width:120px" data-path="checkpoints.${i}.time" data-live value="${this._e(cp.time)}">
          <button class="iconbtn" data-act="remove" data-path="checkpoints" data-arg="${i}" aria-label="✕">✕</button></div>
        ${this._childChips(`checkpoints.${i}.children`)}
        <label class="switch small"><input type="checkbox" data-path="checkpoints.${i}.required_for_streak" ${cp.required_for_streak ? "checked" : ""}>${this._icon("streak_flame", 20)} ${this._e(this._t("routines.streak_required"))}</label>
        <div class="lbl">${this._e(this._t("routines.bands"))}</div>
        ${cp.reward_bands.map((b, j) => `<div class="row wrap"><input type="number" class="short" data-path="checkpoints.${i}.reward_bands.${j}.min_early_min" value="${this._e(b.min_early_min)}"><span class="muted">${this._e(this._t("routines.min_early"))} →</span>
          <input type="number" class="short" min="0" data-path="checkpoints.${i}.reward_bands.${j}.tokens" data-live value="${this._e(b.tokens)}">${this._pile(Number(b.tokens) || 0, 6)}<span class="grow"></span><button class="iconbtn" data-act="remove" data-path="checkpoints.${i}.reward_bands" data-arg="${j}" aria-label="✕">✕</button></div>`).join("")}
        <button class="btn sm" data-act="add" data-path="checkpoints.${i}.reward_bands" data-arg="band" style="align-self:flex-start">＋ ${this._e(this._t("routines.add_band"))}</button></div>`).join("")}
      <button class="btn sm" data-act="add" data-path="checkpoints" data-arg="checkpoint" style="align-self:flex-start">＋ ${this._e(this._t("routines.add_checkpoint"))}</button>`;
    const cpOptions = (sel) => `<option value="">${this._e(this._t("routines.last_checkpoint"))}</option>` + r.checkpoints.map((c) => `<option value="${this._e(c.id)}" ${c.id === sel ? "selected" : ""}>${this._e(c.name || c.time)}</option>`).join("");
    const tasks = `${r.tasks.map((x, i) => `<div class="row wrap task-row">
        <button class="pick" data-act="pick" data-path="tasks.${i}.icon" data-arg="task">${this._icon(x.icon, 44)}</button>
        <input class="grow" style="min-width:120px" data-path="tasks.${i}.label" value="${this._e(x.label || "")}" placeholder="${this._e(this._t("routines.label_optional"))}">
        <select style="width:auto;max-width:170px" data-path="tasks.${i}.checkpoint_id">${cpOptions(x.checkpoint_id)}</select>
        <button class="iconbtn" data-act="up" data-path="tasks" data-arg="${i}" ${i === 0 ? "disabled" : ""} aria-label="▲">▲</button><button class="iconbtn" data-act="down" data-path="tasks" data-arg="${i}" ${i === r.tasks.length - 1 ? "disabled" : ""} aria-label="▼">▼</button><button class="iconbtn" data-act="remove" data-path="tasks" data-arg="${i}" aria-label="✕">✕</button></div>`).join("")}
      <button class="btn sm" data-act="add" data-path="tasks" data-arg="task" style="align-self:flex-start">＋ ${this._e(this._t("routines.add_task"))}</button>`;
    const template = `<div class="field"><span>${this._e(this._t("rtemplates.save_title"))}</span><div class="row"><input id="rtpl-name" value="${this._e(r.name || "")}" placeholder="${this._e(this._t("rtemplates.name"))}"><button class="btn" data-act="save-rtemplate">${this._e(this._t("rtemplates.save"))}</button></div>
      <div class="hint">${this._e(this._t("rtemplates.hint"))}</div>${this._rtplSaved ? `<div class="tag good">${this._e(this._t("rtemplates.saved"))}: ${this._e(this._rtplSaved)}</div>` : ""}</div>`;
    const sections = {
      basics: [this._t("ed.basics"), basics, "name"],
      look: [this._t("routines.zones"), look, "zones"],
      cps: [`${this._t("routines.checkpoints")} · ${r.checkpoints.length}`, cps, "checkpoints"],
      tasks: [`${this._t("routines.tasks")} · ${r.tasks.length}`, tasks, "tasks"],
      ...(ed.readonly ? {} : { tpl: [this._t("rtemplates.save_title"), template, null] }),
    };
    const sec = sections[this._sec] ? this._sec : "basics";
    const date = dayMode ? this._fmtDate(ed.newDate || ed.date, { weekday: "long", month: "long", day: "numeric" }) : "";
    const isToday = dayMode && ed.newDate === this._todayStr();
    return {
      title: dayMode ? `${this._t(ed.oneDay || ed.isNew ? "day.one_day_title" : "day.title")}: ${date}` : ed.readonly ? r.name : this._t(ed.isNew ? "routines.add" : "routines.edit"),
      nav: `<div class="sec-nav">${Object.entries(sections).map(([k, [label, , key]]) => `<button class="${sec === k ? "on" : ""}" data-act="sec" data-arg="${k}">${this._e(label)}${key ? diff(key) : ""}</button>`).join("")}</div>`,
      body: `${dayMode ? `<div class="infobox">${this._e(this._t(ed.readonly ? "day.readonly" : "day.hint"))}</div>` : ""}
        <div class="card flat row wrap" style="gap:16px">${this._dial(r, 132, { now: isToday ? nowMinutes() : null })}<div class="grow"><div class="lbl">${this._e(this._t("ed.preview"))}</div><div class="rt-title" style="margin:4px 0">${this._e(r.name || this._t("routines.unnamed"))}</div><div class="muted num">${this._e(r.start)}–${this._e(r.end)} · ${r.tasks.length} ${this._e(this._t("routines.tasks_count"))}</div><div class="strip" style="margin-top:6px">${r.tasks.slice(0, 12).map((x) => `<img src="${this._iconUrl(x.icon, 26)}" alt="">`).join("")}</div></div></div>
        ${sections[sec][1]}`,
    };
  }

  _viewDrawer() {
    const ed = this._edit;
    if (!ed) {
      return "";
    }
    const view = { children: () => this._editChild(), rewards: () => this._editReward(), templates: () => this._editTemplate(), routines: () => this._editRoutine(), day: () => this._editRoutine() }[ed.coll]();
    const close = `<button class="btn" data-act="cancel">${this._e(this._t("common.close"))}</button>`;
    let foot;
    if (view.plain) {
      foot = `${close}<span class="grow"></span>${this._isAdmin ? `<button class="btn primary" data-act="sec" data-arg="data">✎ ${this._e(this._t("common.edit"))}</button>` : ""}`;
    } else if (ed.readonly) {
      foot = close;
    } else if (ed.coll === "day") {
      foot = `<button class="btn primary" data-act="save">${this._e(this._t("day.save"))}</button><button class="btn" data-act="cancel">${this._e(this._t("common.cancel"))}</button><span class="grow"></span>
        ${ed.changed && !ed.oneDay ? `<button class="btn" data-act="day-restore">${this._e(this._t("day.restore"))}</button>` : ""}${ed.oneDay && !ed.isNew ? `<button class="btn danger" data-act="day-restore">${this._e(this._t("day.remove"))}</button>` : ""}`;
    } else {
      foot = `<button class="btn primary" data-act="save">${this._e(this._t("common.save"))}</button><button class="btn" data-act="cancel">${this._e(this._t("common.cancel"))}</button><span class="grow"></span>${ed.isNew ? "" : `<button class="btn danger" data-act="delete">${this._e(this._t("common.delete"))}</button>`}`;
    }
    const body = view.plain ? view.body : `<fieldset ${ed.readonly ? "disabled" : ""}>${view.body}</fieldset>`;
    const id = !ed.isNew && ed.item.id && ed.coll !== "day" ? `<div class="muted small">ID: ${this._e(ed.item.id)}</div>` : "";
    return `<div class="backdrop" data-act="cancel"></div><aside class="drawer" role="dialog" aria-modal="true" aria-label="${this._e(view.title)}">
      <div class="drawer-h"><h2>${this._e(view.title)}</h2><button class="iconbtn" data-act="cancel" aria-label="${this._e(this._t("common.close"))}">✕</button></div>${view.nav || ""}
      <div class="drawer-b">${body}${id}</div>
      <div class="drawer-f">${foot}</div></aside>`;
  }

  _viewPicker() {
    if (!this._picker) {
      return "";
    }
    // Rewards, tasks, routines and checkpoints all offer the same pictures.
    const content = (n) => n.startsWith("routine_") || n.startsWith("task_") || n.startsWith("reward_");
    const filters = {
      avatar: (n) => n.startsWith("avatar_"),
      task: content,
      checkpoint: (n) => content(n) || n === "checkpoint_flag",
      routine: content,
      reward: (n) => content(n) || n === "fn_rewards" || n === "fn_piggy",
    };
    const filter = filters[this._picker.filter] || (() => true);
    const current = this._get(this._picker.path);
    const icons = this._data.icons
      .filter(filter)
      .map((n) => `<button class="${n === current ? "on" : ""}" title="${this._e(n)}" data-act="pick-icon" data-arg="${this._e(n)}">${this._icon(n, 56)}</button>`)
      .join("");
    const upload = this._picker.filter === "avatar"
      ? `<label class="upload-tile" title="${this._e(this._t("picture.upload"))}"><span style="font-size:1.6rem">📷</span><span class="small">${this._e(this._t("picture.upload"))}</span><input type="file" accept="image/*" data-crop-upload="avatar_image" hidden></label>`
      : "";
    return `<div class="backdrop over" data-act="pick-close"></div><div class="dialog wide over" role="dialog" aria-modal="true">
      <div class="row"><h2 class="grow">${this._e(this._t(this._picker.filter === "avatar" ? "children.avatar_choose" : "common.choose_icon"))}</h2><button class="iconbtn" data-act="pick-close" aria-label="✕">✕</button></div>
      <div class="icon-grid">${upload}${icons}</div></div>`;
  }

  _viewDialog() {
    const d = this._dialog;
    if (!d) {
      return "";
    }
    const cancel = `<button class="btn" data-act="dlg-cancel">${this._e(this._t("common.cancel"))}</button>`;
    let inner = "";
    if (d.type === "confirm") {
      inner = `<h2>${this._e(d.title || this._t("common.delete"))}</h2><p class="muted" style="margin:0">${this._e(d.text)}</p>
        <div class="row wrap" style="justify-content:flex-end">${cancel}<button class="btn ${d.danger ? "danger" : "primary"}" data-act="dlg-ok">${this._e(d.ok || this._t("confirm.yes"))}</button></div>`;
    } else if (d.type === "scope") {
      inner = `<h2>${this._e(this._t("scope.title"))}</h2><p class="muted" style="margin:0">${this._e(this._t("scope.hint"))}</p>
        <div class="stack" style="gap:8px"><button class="btn primary" data-act="scope" data-arg="once">${this._e(this._t("scope.once"))}</button><button class="btn" data-act="scope" data-arg="series">${this._e(this._t("scope.series"))}</button><button class="btn ghost" data-act="dlg-cancel">${this._e(this._t("common.cancel"))}</button></div>`;
    } else if (d.type === "correct") {
      inner = `<h2>${this._e(this._t("history.correct"))} · #${d.seq}</h2>
        <label class="field"><span>${this._e(this._t("history.correct_prompt"))}</span><input type="number" id="dlg-amount" value="${d.amount}"></label>
        <label class="field"><span>${this._e(this._t("history.note_prompt"))}</span><input id="dlg-note"></label>
        <div class="row wrap" style="justify-content:flex-end">${cancel}<button class="btn primary" data-act="dlg-ok">${this._e(this._t("common.save"))}</button></div>`;
    } else if (d.type === "reverse") {
      inner = `<h2>${this._e(this._t("history.reverse"))} · #${d.seq}</h2><p class="muted" style="margin:0">${this._e(this._t("history.confirm_reverse"))}</p>
        <div class="row wrap" style="justify-content:flex-end">${cancel}<button class="btn danger" data-act="dlg-ok">${this._e(this._t("history.reverse"))}</button></div>`;
    }
    return `<div class="backdrop over" data-act="dlg-cancel"></div><div class="dialog over" role="dialog" aria-modal="true">${inner}</div>`;
  }

  // ------------------------------------------------------------ photo crop

  // A chosen photo is framed in a circle (what the knob and the panel show):
  // drag to move it, the slider or the mouse wheel to zoom. The square around
  // the circle is uploaded.
  _openCrop(field, file) {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      this._picker = null;
      this._crop = { field, url, img, file, zoom: 1, x: 0, y: 0 };
      this._render();
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      this._error = this._t("picture.failed");
      this._render();
    };
    img.src = url;
  }

  _viewCrop() {
    if (!this._crop) {
      return "";
    }
    return `<div class="backdrop top" data-crop-cancel></div><div class="dialog top" role="dialog" aria-modal="true">
      <h2>${this._e(this._t("crop.title"))}</h2>
      <canvas class="crop-canvas" width="${CROP_VIEW}" height="${CROP_VIEW}"></canvas>
      <label class="field crop-zoom"><span>${this._e(this._t("crop.zoom"))}</span><input type="range" min="1" max="4" step="0.01" value="${this._crop.zoom}"></label>
      <div class="hint">${this._e(this._t("crop.hint"))}</div>
      <div class="row wrap" style="justify-content:flex-end"><button class="btn ghost" data-crop-whole>${this._e(this._t("crop.whole"))}</button><button class="btn" data-crop-cancel>${this._e(this._t("common.cancel"))}</button><button class="btn primary" data-crop-done>${this._e(this._t("crop.done"))}</button></div></div>`;
  }

  // Scale of the photo at zoom 1: its shorter side fills the circle.
  _cropBase() {
    const { img } = this._crop;
    return (CROP_VIEW - 2 * CROP_MARGIN) / Math.min(img.naturalWidth, img.naturalHeight);
  }

  // Keeps the circle inside the photo.
  _clampCrop() {
    const c = this._crop;
    const scale = this._cropBase() * c.zoom;
    const maxX = Math.max(0, (c.img.naturalWidth * scale - (CROP_VIEW - 2 * CROP_MARGIN)) / 2);
    const maxY = Math.max(0, (c.img.naturalHeight * scale - (CROP_VIEW - 2 * CROP_MARGIN)) / 2);
    c.x = Math.max(-maxX, Math.min(maxX, c.x));
    c.y = Math.max(-maxY, Math.min(maxY, c.y));
  }

  // Draws the photo (x, y: offset of its centre from the view's centre).
  _drawCrop(ctx, size, scale, offsetX, offsetY) {
    const { img } = this._crop;
    const w = img.naturalWidth * scale;
    const h = img.naturalHeight * scale;
    ctx.drawImage(img, size / 2 - w / 2 + offsetX, size / 2 - h / 2 + offsetY, w, h);
  }

  _paintCrop(canvas) {
    const c = this._crop;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, CROP_VIEW, CROP_VIEW);
    this._drawCrop(ctx, CROP_VIEW, this._cropBase() * c.zoom, c.x, c.y);
    // Dimmed outside the circle.
    ctx.save();
    ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
    ctx.beginPath();
    ctx.rect(0, 0, CROP_VIEW, CROP_VIEW);
    ctx.arc(CROP_VIEW / 2, CROP_VIEW / 2, CROP_VIEW / 2 - CROP_MARGIN, 0, Math.PI * 2, true);
    ctx.fill("evenodd");
    ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(CROP_VIEW / 2, CROP_VIEW / 2, CROP_VIEW / 2 - CROP_MARGIN, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  _setupCrop() {
    const root = this.shadowRoot;
    const canvas = root.querySelector(".crop-canvas");
    const slider = root.querySelector(".crop-zoom input");
    if (!canvas || !slider) {
      return;
    }
    const c = this._crop;
    const paint = () => this._paintCrop(canvas);
    const setZoom = (zoom) => {
      c.zoom = Math.max(1, Math.min(4, zoom));
      slider.value = String(c.zoom);
      this._clampCrop();
      paint();
    };
    // Canvas pixels per CSS pixel (the canvas may be shown smaller).
    const ratio = () => CROP_VIEW / canvas.getBoundingClientRect().width;
    let drag = null;
    canvas.addEventListener("pointerdown", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      canvas.setPointerCapture(ev.pointerId);
      drag = { x: ev.clientX, y: ev.clientY, cx: c.x, cy: c.y };
    });
    canvas.addEventListener("pointermove", (ev) => {
      if (!drag) {
        return;
      }
      ev.stopPropagation();
      c.x = drag.cx + (ev.clientX - drag.x) * ratio();
      c.y = drag.cy + (ev.clientY - drag.y) * ratio();
      this._clampCrop();
      paint();
    });
    const stop = (ev) => {
      ev.stopPropagation();
      drag = null;
    };
    canvas.addEventListener("pointerup", stop);
    canvas.addEventListener("pointercancel", stop);
    canvas.addEventListener(
      "wheel",
      (ev) => {
        ev.preventDefault();
        setZoom(c.zoom * (ev.deltaY < 0 ? 1.1 : 1 / 1.1));
      },
      { passive: false }
    );
    slider.addEventListener("input", (ev) => {
      ev.stopPropagation();
      setZoom(Number(slider.value));
    });
    slider.addEventListener("change", (ev) => ev.stopPropagation());
    for (const el of root.querySelectorAll("[data-crop-cancel]")) {
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._closeCrop();
      });
    }
    root.querySelector("[data-crop-done]").addEventListener("click", (ev) => {
      ev.stopPropagation();
      this._finishCrop().catch(() => {});
    });
    root.querySelector("[data-crop-whole]").addEventListener("click", (ev) => {
      ev.stopPropagation();
      this._finishUncropped().catch(() => {});
    });
    this._clampCrop();
    paint();
  }

  _closeCrop() {
    if (this._crop) {
      URL.revokeObjectURL(this._crop.url);
    }
    this._crop = null;
    this._render();
  }

  // The square around the circle, CROP_OUT px, uploaded to Home Assistant.
  async _finishCrop() {
    const c = this._crop;
    const out = document.createElement("canvas");
    out.width = out.height = CROP_OUT;
    const k = CROP_OUT / (CROP_VIEW - 2 * CROP_MARGIN);
    const ctx = out.getContext("2d");
    ctx.imageSmoothingQuality = "high";
    this._drawCrop(ctx, CROP_OUT, this._cropBase() * c.zoom * k, c.x * k, c.y * k);
    // PNG: a transparent background stays transparent.
    const blob = await new Promise((resolve) => out.toBlob(resolve, "image/png"));
    await this._uploadCropped(blob, "photo.png");
  }

  // The chosen file as it is, without framing.
  async _finishUncropped() {
    await this._uploadCropped(this._crop.file, this._crop.file.name || "photo");
  }

  async _upload(blob, name) {
    const form = new FormData();
    form.append("file", blob, name);
    const response = await this._hass.fetchWithAuth("/api/image/upload", { method: "POST", body: form });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return (await response.json()).id;
  }

  async _uploadCropped(blob, name) {
    const c = this._crop;
    try {
      const id = await this._upload(blob, name);
      if (this._edit) {
        this._edit.item[c.field] = id;
      }
    } catch (err) {
      this._error = this._t("picture.failed");
      console.warn("Kis Segito: upload failed", err);
    }
    this._closeCrop();
  }

  // ------------------------------------------------------------ render

  // Identifies a form field across redraws (its data attributes or id).
  _fieldKey(el) {
    const data = Object.entries(el.dataset || {})
      .filter(([k]) => k !== "saved")
      .map(([k, v]) => `${k}=${v}`)
      .sort()
      .join("&");
    return data || el.id ? `${el.tagName}|${el.id}|${data}` : null;
  }

  _scheduleRender(ms = 0) {
    clearTimeout(this._renderTimer);
    this._renderTimer = setTimeout(() => this._render(), ms);
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }
    this._applyTheme();
    let body = `<div class="card empty">${this._e(this._t("common.loading"))}</div>`;
    if (this._data) {
      const view = {
        today: () => this._viewToday(),
        calendar: () => this._viewCalendar(),
        children: () => this._viewChildren(),
        routines: () => this._viewRoutines(),
        rewards: () => this._viewRewards(),
        tokens: () => this._viewTokens(),
        history: () => this._viewHistory(),
        notifications: () => this._viewNotifications(),
        settings: () => this._viewSettings(),
      }[this._tab];
      try {
        body = view();
      } catch (err) {
        // Never leave the old screen silently: show what went wrong.
        console.error("Kis Segito: render failed", err);
        body = `<div class="card error">${this._e(String(err))}</div>`;
      }
    }
    let overlays = "";
    try {
      overlays = `${this._data ? this._viewDrawer() + this._viewPicker() + this._viewDialog() : ""}${this._viewCrop()}`;
    } catch (err) {
      console.error("Kis Segito: render failed", err);
      overlays = `<div class="toast error">${this._e(String(err))}</div>`;
    }
    const night = this._night;
    const languageNow = this._language || "";
    const logo = languageNow.startsWith("hu") ? "brand_logo" : "brand_logo_en";
    const languages = this._data?.settings?.languages || [];
    const tabs = TABS.map((x) => `<button class="tab ${x === this._tab ? "on" : ""}" data-act="tab" data-arg="${x}">${this._icon(`nav_${x}`, 30)}${this._e(this._t(`tab.${x}`))}</button>`).join("");
    const inMore = !BOTTOM_TABS.includes(this._tab);
    const bnav = [
      ...BOTTOM_TABS.map((x) => `<button class="${x === this._tab ? "on" : ""}" data-act="tab" data-arg="${x}">${this._icon(`nav_${x}`, 30)}${this._e(this._t(`tab.${x}`))}</button>`),
      `<button class="${inMore ? "on" : ""}" data-act="more">${inMore ? this._icon(`nav_${this._tab}`, 30) : `<span class="dots">•••</span>`}${this._e(inMore ? this._t(`tab.${this._tab}`) : this._t("nav.more"))}</button>`,
    ].join("");
    const stars = [[12, 8], [24, 22], [40, 10], [52, 26], [60, 6]].map(([x, y], i) => `<span class="st" style="left:${x}px;top:${y}px;animation-duration:${1.5 + i * 0.4}s"></span>`).join("");
    const page = this.shadowRoot.querySelector(".page");
    const scroll = page?.scrollTop ?? 0;
    const drawer = this.shadowRoot.querySelector(".drawer-b");
    const drawerScroll = this._drawerScroll ?? drawer?.scrollTop ?? 0;
    this._drawerScroll = null;
    // The field being edited keeps the focus and the cursor across a redraw.
    const focused = this.shadowRoot.activeElement;
    const focusKey = focused?.matches?.("input, textarea, select") ? this._fieldKey(focused) : null;
    const selection = focusKey && typeof focused.selectionStart === "number" ? [focused.selectionStart, focused.selectionEnd] : null;
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <div class="page">
        <header class="hero" style="background-image:url('${this._backgroundUrl(night ? "bg_6" : "bg_2")}')">
          <div class="topbar">
            ${this._isNarrow ? `<ha-menu-button></ha-menu-button>` : ""}
            <div class="brand"><img class="logo" src="${this._staticUrl}/icons/${logo}.webp?v=${this._version}" alt="${this._e(this._t("panel.title"))}"></div>
            <div class="top-actions">
              ${languages.length > 1 ? `<div class="pill-switch" role="group" aria-label="${this._e(this._t("settings.language"))}">${languages.map((l) => `<button class="${languageNow.split("-")[0] === l.code ? "on" : ""}" data-act="lang" data-arg="${this._e(l.code)}" title="${this._e(l.name)}">${this._e(l.code.toUpperCase())}</button>`).join("")}</div>` : ""}
              <button class="daynight ${night ? "night" : ""}" data-act="theme" aria-label="${this._e(this._t(night ? "theme.day" : "theme.night"))}" title="${this._e(this._t(night ? "theme.night" : "theme.day"))}">${stars}<span class="knob"></span></button>
            </div>
          </div>
          <nav class="tabs" aria-label="tabs">${tabs}</nav>
        </header>
        <main>
          ${this._data?.version && this._data.version !== PANEL_VERSION
            ? `<div class="banner">${this._icon("celebrate_confetti", 32)}<span class="grow">${this._e(this._t("panel.outdated"))}</span><button class="btn primary sm" data-act="reload">${this._e(this._t("panel.reload"))}</button></div>`
            : ""}
          ${this._error ? `<div class="banner bad"><span class="grow">${this._e(this._error)}</span><button class="iconbtn" data-act="error-close" aria-label="✕">✕</button></div>` : ""}
          ${body}
        </main>
      </div>
      <nav class="bnav" aria-label="tabs">${bnav}</nav>
      ${this._more ? `<div class="backdrop" data-act="more"></div><div class="more-sheet">${TABS.filter((x) => !BOTTOM_TABS.includes(x)).map((x) => `<button data-act="tab" data-arg="${x}">${this._icon(`nav_${x}`, 40)}${this._e(this._t(`tab.${x}`))}</button>`).join("")}</div>` : ""}
      ${overlays}
      <div class="tip" hidden></div>
      ${this._toastText ? `<div class="toast" role="status">${this._icon("action_check", 22)} ${this._e(this._toastText)}</div>` : ""}`;
    const newPage = this.shadowRoot.querySelector(".page");
    if (newPage) {
      newPage.scrollTop = scroll;
    }
    const newDrawer = this.shadowRoot.querySelector(".drawer-b");
    if (newDrawer) {
      newDrawer.scrollTop = drawerScroll;
    }
    if (focusKey) {
      const field = [...this.shadowRoot.querySelectorAll("input, textarea, select")].find((el) => this._fieldKey(el) === focusKey);
      if (field) {
        field.focus({ preventScroll: true });
        if (selection) {
          try {
            field.setSelectionRange(...selection);
          } catch (_err) {
            // number fields have no cursor position
          }
        }
      }
    }
    if (this._crop) {
      this._setupCrop();
    }
    const menuButton = this.shadowRoot.querySelector("ha-menu-button");
    if (menuButton) {
      menuButton.hass = this._hass;
      menuButton.narrow = this._narrow;
    }
    this._listen();
  }

  // ------------------------------------------------------------ actions

  async _switchTab(tab) {
    this._tab = tab;
    this._edit = null;
    this._picker = null;
    this._more = false;
    this._stats = null;
    this._dialog = null;
    this._render();
    if (tab === "calendar") {
      await this._syncCalendarRange();
    } else {
      await this._loadForTab(tab);
    }
    this.shadowRoot.querySelector(".page")?.scrollTo({ top: 0 });
  }

  // Closes the topmost layer; false when nothing was open.
  _closeTop() {
    if (this._crop) {
      this._closeCrop();
      return true;
    }
    if (this._dialog) {
      this._dialog = null;
    } else if (this._picker) {
      this._picker = null;
    } else if (this._edit) {
      this._edit = null;
      this._stats = null;
    } else if (this._more) {
      this._more = false;
    } else {
      return false;
    }
    this._render();
    return true;
  }

  _confirm(title, text, run, { danger = false, ok = null } = {}) {
    this._dialog = { type: "confirm", title, text, run, danger, ok };
    this._render();
  }

  async _goto(seq) {
    // Jump to a history entry (#n): clear filters that would hide it.
    let row = this.shadowRoot.getElementById(`tx-${seq}`);
    if (!row) {
      this._historyFilter = {};
      await this._loadHistory();
      this._render();
      row = this.shadowRoot.getElementById(`tx-${seq}`);
    }
    history.replaceState(null, "", `#tx-${seq}`);
    if (row) {
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      row.classList.add("flash");
      setTimeout(() => row.classList.remove("flash"), 1600);
    }
  }

  async _saveEdit() {
    const ed = this._edit;
    if (ed.coll === "day") {
      const msg = { type: "kis_segito/day_routine", date: ed.date, routine_id: ed.routine_id, routine: ed.item };
      if (ed.newDate && ed.newDate !== ed.date) {
        msg.target_date = ed.newDate;
      }
      await this._ws(msg);
    } else {
      await this._ws({ type: "kis_segito/save", collection: ed.coll, item: ed.item });
    }
    this._edit = null;
    this._stats = null;
    this._picker = null;
    this._toast(this._t("toast.saved"));
    await this._load();
  }

  async _onClick(ev) {
    const el = ev.target.closest("[data-act]");
    if (!el || el.disabled) {
      return;
    }
    const { act, arg, path } = el.dataset;
    if (act === "goto" && ev.preventDefault) {
      ev.preventDefault();
    }
    if (el.closest(".drawer-b")) {
      this._drawerScroll = this.shadowRoot.querySelector(".drawer-b")?.scrollTop ?? 0;
    }
    switch (act) {
      case "tab":
        await this._switchTab(arg);
        return;
      case "more":
        this._more = !this._more;
        break;
      case "lang":
        if (this._isAdmin) {
          this._localLanguage = "";
          try {
            localStorage.removeItem(LANG_KEY);
          } catch (_err) {
            // Not remembered.
          }
          await this._ws({ type: "kis_segito/settings/update", language: arg });
          await this._load();
        } else {
          this._localLanguage = arg;
          try {
            localStorage.setItem(LANG_KEY, arg);
          } catch (_err) {
            // Not remembered.
          }
          this._updateLanguage();
        }
        return;
      case "theme":
        this._theme = this._night ? "light" : "dark";
        try {
          localStorage.setItem(THEME_KEY, this._theme);
        } catch (_err) {
          // Not remembered.
        }
        break;
      case "reload":
        location.reload();
        return;
      case "error-close":
        this._error = "";
        break;
      case "demo-now":
        this._demo = null;
        break;
      case "child-stats":
        await this._openEdit("children", arg, { sec: "stats" });
        return;
      case "edit":
        await this._openEdit(el.dataset.coll, arg);
        return;
      case "new":
        await this._openEdit(arg, null);
        return;
      case "from-rtemplate":
        await this._openEdit("routines", null);
        this._edit.item = this._fromRoutineTemplate(arg);
        break;
      case "delete-rtemplate":
        this._confirm(this._t("common.delete"), this._t("common.confirm_delete"), async () => {
          await this._ws({ type: "kis_segito/delete", collection: "routine_templates", item_id: arg });
          this._toast(this._t("toast.deleted"));
          await this._load();
        }, { danger: true, ok: this._t("common.delete") });
        return;
      case "save-rtemplate": {
        const name = (this.shadowRoot.querySelector("#rtpl-name")?.value || "").trim() || this._edit.item.name || this._t("routines.unnamed");
        const routine = clone(this._edit.item);
        for (const key of ["id", "sort_order"]) {
          delete routine[key];
        }
        await this._ws({ type: "kis_segito/save", collection: "routine_templates", item: { name, routine } });
        this._rtplSaved = name;
        this._toast(this._t("toast.rtpl"));
        await this._load();
        return;
      }
      case "cancel":
        this._edit = null;
        this._picker = null;
        this._stats = null;
        break;
      case "sec":
        this._sec = arg;
        this._drawerScroll = 0;
        if (arg === "stats" && this._edit?.coll === "children" && !this._stats) {
          this._stats = { childId: this._edit.item.id };
          this._render();
          await this._loadStats();
        }
        break;
      case "save":
        await this._saveEdit();
        return;
      case "delete":
        this._confirm(this._t("common.delete"), this._t("common.confirm_delete"), async () => {
          await this._ws({ type: "kis_segito/delete", collection: this._edit.coll, item_id: this._edit.item.id });
          this._edit = null;
          this._toast(this._t("toast.deleted"));
          await this._load();
        }, { danger: true, ok: this._t("common.delete") });
        return;
      case "day-restore": {
        const ed = this._edit;
        await this._ws({ type: "kis_segito/day_routine", date: ed.date, routine_id: ed.routine_id, routine: null });
        this._edit = null;
        this._toast(this._t(ed.oneDay ? "toast.deleted" : "day.restore"));
        await this._load();
        return;
      }
      case "day-edit":
        this._openDayEditor(el.dataset.date, arg || null);
        return;
      case "day-new":
        this._openDayEditor(el.dataset.date, null, el.dataset.time);
        return;
      case "set":
        this._set(path, el.dataset.v);
        break;
      case "pick":
        this._picker = { path, filter: arg };
        break;
      case "pick-close":
        this._picker = null;
        break;
      case "pick-icon":
        this._set(this._picker.path, arg);
        if (this._picker.filter === "avatar") {
          this._edit.item.avatar_image = ""; // the chosen avatar replaces the photo
        }
        this._picker = null;
        break;
      case "photo-icon":
        // Back to an icon: the picker opens right away.
        this._edit.item.image = "";
        this._picker = { path: "icon", filter: "reward" };
        break;
      case "clear-picture":
        this._edit.item[arg] = "";
        if (arg === "avatar_image") {
          this._edit.item.avatar = "avatar_00"; // back to the default avatar
        }
        break;
      case "add":
        this._get(path).push(this._newRow(arg));
        break;
      case "remove":
        this._get(path).splice(Number(arg), 1);
        break;
      case "up":
      case "down": {
        const list = this._get(path);
        const i = Number(arg);
        const j = act === "up" ? i - 1 : i + 1;
        if (j >= 0 && j < list.length) {
          [list[i], list[j]] = [list[j], list[i]];
        }
        break;
      }
      case "weekday": {
        const days = this._edit.item.weekdays || [];
        const d = Number(arg);
        this._edit.item.weekdays = days.includes(d) ? days.filter((x) => x !== d) : [...days, d].sort();
        break;
      }
      case "toggle-child": {
        const list = this._get(path) || [];
        this._set(path, list.includes(arg) ? list.filter((x) => x !== arg) : [...list, arg]);
        break;
      }
      case "toggle-routine": {
        const list = this._edit.item.routines;
        this._edit.item.routines = list.includes(arg) ? list.filter((x) => x !== arg) : [...list, arg];
        break;
      }
      case "cost":
        this._edit.item.cost = Math.max(0, (Number(this._edit.item.cost) || 0) + Number(el.dataset.d));
        break;
      case "move": {
        const [collection, id, dir] = arg.split(":");
        const ids = this._data[collection].map((i) => i.id);
        const i = ids.indexOf(id);
        const j = i + Number(dir);
        if (j >= 0 && j < ids.length) {
          [ids[i], ids[j]] = [ids[j], ids[i]];
          await this._ws({ type: "kis_segito/reorder", collection, ids });
          await this._load();
        }
        return;
      }
      case "defaults":
        await this._createDefaults(arg);
        return;
      // ---- today
      case "ov-shift": {
        const day = this._todayDay();
        const running = day?.routines.find((x) => x.id === arg);
        const shift = (this._shift[arg] ?? running?.override?.shift_min ?? 0) + Number(el.dataset.d);
        this._shift[arg] = shift;
        this._render();
        await this._ws({ type: "kis_segito/override", routine_id: arg, skip: false, shift_min: shift });
        this._toast(this._t("toast.override"));
        return;
      }
      case "ov-skip":
        await this._ws({ type: "kis_segito/override", routine_id: arg, skip: true, shift_min: 0 });
        this._toast(this._t("toast.override"));
        return;
      case "ov-restore":
        delete this._shift[arg];
        await this._ws({ type: "kis_segito/override", routine_id: arg, skip: false, shift_min: 0 });
        this._toast(this._t("toast.override"));
        return;
      // ---- calendar
      case "cal-mode":
        this._calMode = arg;
        try {
          localStorage.setItem(this._calViewKey, arg);
        } catch (_err) {
          // Private mode: not remembered.
        }
        await this._syncCalendarRange();
        break;
      case "cal-day": {
        const step = this._calModeNow === "3day" ? 3 : 1;
        this._calDay = arg === "today" ? null : addDays(this._calDayDate(), arg === "next" ? step : -step);
        await this._syncCalendarRange();
        break;
      }
      case "week": {
        const start = this._week?.start || this._todayStr();
        this._weekStart = arg === "now" ? null : addDays(start, arg === "next" ? 7 : -7);
        this._calDay = this._weekStart;
        await this._loadWeek();
        break;
      }
      case "undo": {
        const undo = this._undo;
        this._undo = null;
        if (undo) {
          await this._ws({ type: "kis_segito/day_routine", ...undo.msg });
          await this._load();
        }
        return;
      }
      case "scope": {
        const d = this._dialog;
        this._dialog = null;
        if (arg === "series") {
          await this._openEdit("routines", d.routineId);
        } else {
          this._openDayEditor(d.date, d.routineId);
        }
        return;
      }
      // ---- dialogs
      case "dlg-cancel":
        this._dialog = null;
        break;
      case "dlg-ok": {
        const d = this._dialog;
        const amount = this.shadowRoot.querySelector("#dlg-amount")?.value;
        const note = this.shadowRoot.querySelector("#dlg-note")?.value || "";
        this._dialog = null;
        this._render();
        await d.run?.({ amount, note });
        return;
      }
      // ---- statistics
      case "period": {
        const prev = this._statPeriod;
        this._statPeriod = arg === "custom"
          ? { kind: "custom", from: prev.from || addDays(this._todayStr(), -13), to: prev.to || this._todayStr() }
          : { kind: arg };
        if (this._stats) {
          this._stats.history = null;
          this._render();
          await this._loadStats();
        }
        break;
      }
      // ---- tokens
      case "quick":
        (this._adjust[arg] ||= { amount: "", account: "wallet", note: "" }).amount = Number(el.dataset.n);
        break;
      case "adjust": {
        const a = this._adjust[arg] || {};
        const amount = Math.trunc(Number(a.amount || 0));
        if (!amount) {
          return;
        }
        await this._ws({ type: "kis_segito/tokens/adjust", child_id: arg, amount, account: a.account || "wallet", note: a.note || "" });
        this._adjust[arg] = { amount: "", account: "wallet", note: "" };
        if (amount > 0) {
          const rect = el.getBoundingClientRect();
          this._confetti(rect.left + rect.width / 2, rect.top);
        }
        this._toast(this._t("toast.applied").replace("{n}", sign(amount)));
        await this._load();
        return;
      }
      // ---- history
      case "goto":
        await this._goto(arg);
        return;
      case "chain":
        if (this._expanded.has(arg)) {
          this._expanded.delete(arg);
        } else {
          this._expanded.add(arg);
        }
        if (ev.preventDefault) {
          ev.preventDefault();
        }
        break;
      case "reverse": {
        const tx = this._history.find((h) => h.id === arg);
        this._dialog = {
          type: "reverse",
          seq: tx.seq,
          run: async () => {
            await this._ws({ type: "kis_segito/tokens/reverse", transaction_id: arg });
            this._toast(this._t("toast.reversed"));
            await this._load();
          },
        };
        break;
      }
      case "correct": {
        const tx = this._history.find((h) => h.id === arg);
        const line = tx.effective_lines[0];
        this._dialog = {
          type: "correct",
          seq: tx.seq,
          amount: line.amount,
          run: async ({ amount, note }) => {
            if (amount === "" || amount === undefined || Number.isNaN(Number(amount)) || Math.trunc(Number(amount)) === line.amount) {
              return;
            }
            await this._ws({ type: "kis_segito/tokens/correct", transaction_id: arg, account: line.account, amount: Math.trunc(Number(amount)), note });
            this._toast(this._t("toast.corrected"));
            await this._load();
          },
        };
        break;
      }
      // ---- notifications
      case "rule-add":
        this._rules.rules.push({ name: "", service: "", events: ["reward_redeemed"], children: [], enabled: true, message_field: "", title_field: "", extra: {} });
        break;
      case "rule-test": {
        const i = Number(arg);
        this._testResult = this._testResult || {};
        try {
          await this._hass.callWS({ type: "kis_segito/notify_test", rule: this._rules.rules[i] });
          this._testResult[i] = { ok: true, text: this._t("notifications.test_sent") };
        } catch (err) {
          this._testResult[i] = { ok: false, text: `${this._t("notifications.test_failed")} ${err?.message || ""}` };
        }
        break;
      }
      case "rule-remove":
        this._rules.rules.splice(Number(arg), 1);
        break;
      case "rule-event": {
        const [i, name] = arg.split(":");
        const list = this._rules.rules[Number(i)].events;
        const k = list.indexOf(name);
        if (k >= 0) list.splice(k, 1);
        else list.push(name);
        break;
      }
      case "rule-child": {
        const [i, child] = arg.split(":");
        const list = this._rules.rules[Number(i)].children;
        const k = list.indexOf(child);
        if (k >= 0) list.splice(k, 1);
        else list.push(child);
        break;
      }
      case "rules-save":
        this._rules = await this._ws({ type: "kis_segito/notifications", rules: this._rules.rules });
        this._toast(this._t("toast.saved"));
        break;
      // ---- settings
      case "set-setting":
        await this._ws({ type: "kis_segito/settings/update", [el.dataset.key]: arg });
        this._toast(this._t("toast.saved"));
        await this._load();
        return;
      case "saver":
        await this._ws({ type: "kis_segito/settings/update", screen: { saver_type: arg } });
        this._toast(this._t("toast.saved"));
        await this._load();
        return;
      case "bg-set":
        await this._ws({ type: "kis_segito/settings/update", background: arg });
        this._toast(this._t("toast.bg"));
        await this._load();
        return;
      case "rotate-token":
        this._confirm(this._t("settings.knob_new_key"), this._t("settings.knob_new_key_confirm"), async () => {
          await this._ws({ type: "kis_segito/device/rotate_token", device_id: arg });
          this._toast(this._t("toast.key"));
        });
        return;
      case "restart-knob":
        this._confirm(this._t("settings.knob_restart"), this._t("settings.knob_restart_confirm"), async () => {
          await this._ws({ type: "kis_segito/device/restart", device_id: arg });
          this._toast(this._t("toast.restart"));
        });
        return;
      case "export": {
        const data = await this._ws({ type: "kis_segito/export" });
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `kis-segito-${localDate()}.json`;
        a.click();
        URL.revokeObjectURL(a.href);
        return;
      }
      default:
        return;
    }
    this._render();
  }

  _confetti(x, y) {
    const colors = ["#FFC94A", "#6BCB77", "#6CB8FF", "#FF8FB1", "#A78BFA"];
    for (let i = 0; i < 26; i++) {
      const d = document.createElement("i");
      d.className = "confetti";
      d.style.left = `${x}px`;
      d.style.top = `${y}px`;
      d.style.background = colors[i % 5];
      d.style.setProperty("--dx", `${Math.random() * 220 - 110}px`);
      d.style.setProperty("--dy", `${Math.random() * -160 - 20}px`);
      this.shadowRoot.appendChild(d);
      setTimeout(() => d.remove(), 1200);
    }
  }

  // Typing in an editor field: the value goes into the edit buffer; fields
  // that change the preview redraw it after a short pause.
  _onInput(ev) {
    const el = ev.target;
    if (el.dataset.path !== undefined && this._edit) {
      if (el.type === "checkbox" || el.tagName === "SELECT") {
        return; // handled on "change"
      }
      this._set(el.dataset.path, el.type === "number" ? (el.value === "" ? "" : Number(el.value)) : el.value);
      if (el.dataset.live !== undefined) {
        this._scheduleRender(400);
      } else if (el.dataset.rerender !== undefined) {
        this._scheduleRender(100);
      }
      return;
    }
    if (el.dataset.demo !== undefined) {
      this._demo = Number(el.value);
      this._scheduleRender(30);
      return;
    }
    if (el.dataset.editDate !== undefined && this._edit) {
      this._edit.newDate = el.value || this._edit.date;
      this._scheduleRender(400);
      return;
    }
    if (el.dataset.adj) {
      const [id, key] = el.dataset.adj.split(":");
      (this._adjust[id] ||= { amount: "", account: "wallet", note: "" })[key] = el.value;
      if (key === "amount") {
        this._scheduleRender(500);
      }
      return;
    }
    if (el.dataset.filter === "search") {
      this._historyFilter.search = el.value;
      clearTimeout(this._searchTimer);
      this._searchTimer = setTimeout(async () => {
        await this._loadHistory();
        this._render();
      }, 300);
      return;
    }
    // Settings fields are saved 2 s after the last keystroke, and when the
    // field is left (the "change" event); no Enter or button needed.
    if ((el.dataset.setting || el.dataset.screen || el.dataset.deviceScreen) && el.matches("input") && !["checkbox", "radio", "file", "range"].includes(el.type)) {
      clearTimeout(this._inputTimer);
      this._inputTimer = setTimeout(() => {
        if (!el.isConnected || el.dataset.saved === el.value) {
          return;
        }
        el.dataset.saved = el.value;
        this._onChange({ target: el }).catch(() => {});
      }, 2000);
    }
  }

  async _onChange(ev) {
    const el = ev.target;
    // Already saved while typing: nothing new.
    if (el.dataset?.saved !== undefined && el.dataset.saved === el.value && ev.type === "change") {
      return;
    }
    // Minutes in the field, seconds in the settings.
    const number = (v) => (el.dataset.minutes !== undefined ? Math.round(Number(v) * 60) : Number(v));
    if (el.dataset.path !== undefined && this._edit) {
      let value = el.value;
      if (el.type === "checkbox") {
        value = el.checked;
      } else if (el.type === "number") {
        value = el.value === "" ? 0 : Number(el.value);
      }
      this._set(el.dataset.path, value);
      this._drawerScroll = this.shadowRoot.querySelector(".drawer-b")?.scrollTop ?? 0;
      this._render();
      return;
    }
    if (el.dataset.cropUpload && el.files?.length) {
      this._openCrop(el.dataset.cropUpload, el.files[0]);
      return;
    }
    if (el.dataset.uploadBg !== undefined && el.files?.length) {
      try {
        const id = await this._upload(el.files[0], el.files[0].name || "background");
        await this._ws({ type: "kis_segito/settings/update", background: id });
        this._toast(this._t("toast.bg"));
        await this._load();
      } catch (err) {
        this._error = this._t("picture.failed");
        console.warn("Kis Segito: upload failed", err);
        this._render();
      }
      return;
    }
    if (el.dataset.rtemplateApply !== undefined) {
      if (el.value) {
        this._applyRoutineTemplate(el.value);
        this._toast(this._t("toast.template"));
      }
      this._render();
      return;
    }
    if (el.dataset.period) {
      this._statPeriod[el.dataset.period] = el.value;
      if (this._stats) {
        this._stats.history = null;
        this._render();
        await this._loadStats();
      }
      this._render();
      return;
    }
    if (el.dataset.adj) {
      const [id, key] = el.dataset.adj.split(":");
      (this._adjust[id] ||= { amount: "", account: "wallet", note: "" })[key] = el.value;
      this._render();
      return;
    }
    if (el.dataset.filter) {
      this._historyFilter[el.dataset.filter] = el.value;
      await this._loadHistory();
      this._render();
      return;
    }
    if (el.dataset.showEvents !== undefined) {
      this._showEvents = el.checked;
      if (!this._showEvents && EVENT_REASONS.includes(this._historyFilter.reason)) {
        this._historyFilter.reason = "";
      }
      await this._loadHistory();
      this._render();
      return;
    }
    if (el.dataset.calendarChild !== undefined) {
      this._calendarChild = el.value;
      this._render();
      return;
    }
    if (el.dataset.devname) {
      await this._ws({ type: "kis_segito/device/rename", device_id: el.dataset.devname, name: el.value });
      this._toast(this._t("toast.renamed"));
      await this._load();
      return;
    }
    if (el.dataset.screen) {
      if (el.value !== "") {
        await this._ws({ type: "kis_segito/settings/update", screen: { [el.dataset.screen]: number(el.value) } });
        this._toast(this._t("toast.saved"));
      }
      await this._load();
      return;
    }
    if (el.dataset.deviceScreenType !== undefined) {
      await this._ws({ type: "kis_segito/device/screen", device_id: el.dataset.device, screen: { saver_type: el.value || null } });
      this._toast(this._t("toast.saved"));
      await this._load();
      return;
    }
    if (el.dataset.deviceScreen) {
      await this._ws({ type: "kis_segito/device/screen", device_id: el.dataset.device, screen: { [el.dataset.deviceScreen]: el.value === "" ? null : number(el.value) } });
      this._toast(this._t("toast.saved"));
      await this._load();
      return;
    }
    if (el.dataset.setting) {
      const value = el.type === "number" ? (el.value === "" ? null : number(el.value)) : el.value;
      const msg = { type: "kis_segito/settings/update", [el.dataset.setting]: value };
      if (el.dataset.setting === "piggy_interest_weekday") {
        msg.piggy_interest_weekday = Number(el.value);
      }
      if (el.dataset.setting === "language") {
        this._localLanguage = "";
      }
      await this._ws(msg);
      this._toast(this._t("toast.saved"));
      if (el.dataset.setting === "notification_label") {
        await this._loadRules();
      }
      await this._load();
      return;
    }
    if (el.dataset.weekdayTemplate !== undefined) {
      await this._ws({ type: "kis_segito/day_template", weekday: Number(el.dataset.weekdayTemplate), template_id: el.value || null });
      this._toast(this._t("toast.saved"));
      await this._load();
      return;
    }
    if (el.dataset.dateTemplate !== undefined) {
      // "" = the weekday default; "-" = no template that day.
      await this._ws({ type: "kis_segito/day_template", date: el.dataset.dateTemplate, template_id: el.value === "" ? null : el.value === "-" ? "" : el.value });
      this._toast(this._t("toast.template"));
      await this._load();
      return;
    }
    if (el.dataset.rule) {
      const [i, key] = el.dataset.rule.split(":");
      const rule = this._rules.rules[Number(i)];
      rule[key] = el.type === "checkbox" ? el.checked : el.value;
      if (key === "service") {
        rule.message_field = "";
        rule.title_field = "";
        rule.extra = {};
      }
      if (el.dataset.rerender !== undefined) {
        this._render();
      }
      return;
    }
    if (el.dataset.ruleExtra) {
      const [i, field] = el.dataset.ruleExtra.split(":");
      const rule = this._rules.rules[Number(i)];
      rule.extra = { ...(rule.extra || {}), [field]: el.value };
      return;
    }
    if (el.dataset.showAllScripts !== undefined) {
      this._showAllScripts = el.checked;
      this._render();
    }
  }

  // ------------------------------------------------------------ calendar drag

  // Drag a block: the middle moves it (also to another shown day), the top or
  // bottom edge changes its start or end; 5-minute steps. Every drag changes
  // only that occurrence. Touch starts dragging after a long press.
  _pointerDown(ev) {
    const block = ev.target.closest?.("[data-block]");
    if (!block || ev.button > 0) {
      return;
    }
    const editable = this._isAdmin && !block.dataset.past;
    const rect = block.getBoundingClientRect();
    const y = ev.clientY - rect.top;
    const cols = [...this.shadowRoot.querySelectorAll(".cal-col")].map((c) => ({ date: c.dataset.col, past: Boolean(c.dataset.past), el: c, r: c.getBoundingClientRect() }));
    const home = cols.find((c) => c.date === block.dataset.date);
    this._drag = {
      block,
      editable,
      mode: y < 9 ? "start" : y > rect.height - 9 ? "end" : "move",
      x0: ev.clientX,
      y0: ev.clientY,
      st: Number(block.dataset.st),
      en: Number(block.dataset.en),
      cols,
      home,
      target: home,
      active: false,
      touch: ev.pointerType === "touch",
      pointerId: ev.pointerId,
    };
    if (ev.pointerType !== "touch") {
      ev.preventDefault(); // no native image dragging or text selection
    } else if (editable) {
      this._pressTimer = setTimeout(() => {
        if (this._drag) {
          this._drag.active = true;
          block.classList.add("dragging");
          try {
            block.setPointerCapture(this._drag.pointerId);
          } catch (_err) {
            // The pointer is gone.
          }
        }
      }, 400);
    }
  }

  _pointerMove(ev) {
    const d = this._drag;
    if (!d) {
      this._moveTip(ev);
      const block = ev.target.closest?.("[data-block]");
      if (block && this._isAdmin && !block.dataset.past) {
        const r = block.getBoundingClientRect();
        const y = ev.clientY - r.top;
        block.style.cursor = y < 9 || y > r.height - 9 ? "ns-resize" : "grab";
      }
      return;
    }
    if (!d.editable) {
      return;
    }
    if (!d.active) {
      if (d.touch) {
        // Moving before the long press: the page scrolls, no drag.
        if (Math.abs(ev.clientY - d.y0) > 8 || Math.abs(ev.clientX - d.x0) > 8) {
          clearTimeout(this._pressTimer);
          this._drag = null;
        }
        return;
      }
      if (Math.abs(ev.clientY - d.y0) < 5 && Math.abs(ev.clientX - d.x0) < 5) {
        return;
      }
      d.active = true;
      d.block.classList.add("dragging");
      try {
        d.block.setPointerCapture(d.pointerId);
      } catch (_err) {
        // The pointer is gone.
      }
    }
    ev.preventDefault();
    const dm = Math.round((ev.clientY - d.y0) / CAL_PX / CAL_STEP) * CAL_STEP;
    if (d.mode === "move" && d.cols.length > 1) {
      const over = d.cols.find((c) => ev.clientX >= c.r.left && ev.clientX < c.r.right && !c.past) || d.target;
      if (over !== d.target) {
        d.target?.el.classList.remove("drop");
        d.target = over;
        if (over !== d.home) {
          over.el.classList.add("drop");
        }
      }
      d.block.style.transform = `translateX(${d.target.r.left - d.home.r.left}px)`;
    }
    let st = d.st;
    let en = d.en;
    if (d.mode === "start") {
      st = Math.min(st + dm, en - 10);
    } else if (d.mode === "end") {
      en = Math.max(en + dm, st + 10);
    } else {
      st += dm;
      en += dm;
    }
    if (st < CAL_FROM) {
      en += d.mode === "move" ? CAL_FROM - st : 0;
      st = CAL_FROM;
    }
    if (en > CAL_TO) {
      st -= d.mode === "move" ? en - CAL_TO : 0;
      en = CAL_TO;
    }
    d.nst = st;
    d.nen = en;
    d.block.style.top = `${(st - CAL_FROM) * CAL_PX}px`;
    d.block.style.height = `${Math.max(22, (en - st) * CAL_PX)}px`;
    // Checkpoints keep their distance from the end, inside the routine.
    for (const img of d.block.querySelectorAll(".cpm")) {
      const t = Math.min(en, Math.max(st, Number(img.dataset.t) + (en - d.en)));
      img.style.top = `${(t - st) * CAL_PX - 8}px`;
    }
    const sub = d.block.querySelector(".bs");
    if (sub) {
      sub.textContent = sub.textContent.replace(/^\S+–\S+/, `${fromMinutes(st)}–${fromMinutes(en)}`);
    }
  }

  async _pointerUp() {
    clearTimeout(this._pressTimer);
    const d = this._drag;
    this._drag = null;
    if (!d) {
      return;
    }
    d.target?.el.classList.remove("drop");
    if (!d.active || d.nst === undefined) {
      if (!d.active) {
        this._openFromCalendar(d.block.dataset.date, d.block.dataset.routine);
      } else {
        this._render();
      }
      return;
    }
    const from = d.block.dataset.date;
    const to = d.target?.date || from;
    const routineId = d.block.dataset.routine;
    const r = this._dayData(from)?.routines?.find((x) => x.id === routineId);
    if (!r) {
      this._render();
      return;
    }
    const previous = clone(r.routine);
    delete previous.one_day;
    const item = applyTimes(clone(previous), d.nst, d.nen);
    const name = r.name || this._t("routines.unnamed");
    try {
      if (to !== from) {
        const newId = await this._ws({ type: "kis_segito/day_routine", date: from, routine_id: routineId, routine: item, target_date: to });
        this._undo = {
          text: this._t("calendar.moved_day").replace("{name}", name).replace("{date}", this._fmtDate(to, { weekday: "long", month: "short", day: "numeric" })).replace("{from}", item.start).replace("{to}", item.end),
          // A routine of the series goes back home by restoring the copy;
          // a one-day routine moves back.
          msg: r.one_day ? { date: to, routine_id: newId, routine: previous, target_date: from } : { date: to, routine_id: newId, routine: null },
        };
      } else {
        await this._ws({ type: "kis_segito/day_routine", date: from, routine_id: routineId, routine: item });
        this._undo = {
          text: this._t("calendar.moved_to").replace("{name}", name).replace("{from}", item.start).replace("{to}", item.end),
          msg: r.one_day || this._changedOccurrence(r) ? { date: from, routine_id: routineId, routine: previous } : { date: from, routine_id: routineId, routine: null },
        };
      }
    } catch (_err) {
      // Shown by _ws.
    }
    await this._load();
  }

  _moveTip(ev) {
    const tip = this.shadowRoot.querySelector(".tip");
    if (!tip) {
      return;
    }
    const target = ev.target.closest?.("[data-tip]");
    if (!target) {
      tip.hidden = true;
      return;
    }
    tip.textContent = target.dataset.tip;
    tip.hidden = false;
    tip.style.left = `${Math.min(Math.max(ev.clientX, 130), window.innerWidth - 130)}px`;
    tip.style.top = `${ev.clientY}px`;
  }

  _listen() {
    if (this._listening) {
      return;
    }
    this._listening = true;
    const root = this.shadowRoot;
    root.addEventListener("click", (ev) => {
      if (ev.target.closest?.("[data-block]")) {
        return; // handled by the pointer events
      }
      // Empty calendar space: a routine for that day only, at that time.
      const col = ev.target.closest?.(".cal-col");
      if (col && !ev.target.closest("[data-act]") && this._isAdmin && !col.dataset.past) {
        const y = ev.clientY - col.getBoundingClientRect().top;
        const minutes = Math.min(Math.round((CAL_FROM + y / CAL_PX) / 15) * 15, 22 * 60);
        this._openDayEditor(col.dataset.col, null, fromMinutes(minutes));
        return;
      }
      this._onClick(ev).catch(() => {});
    });
    root.addEventListener("input", (ev) => this._onInput(ev));
    root.addEventListener("change", (ev) => {
      if (ev.target.dataset?.path !== undefined && ev.target.type !== "checkbox" && ev.target.tagName !== "SELECT" && ev.target.type !== "color") {
        return; // typed values are already in the edit buffer
      }
      this._onChange(ev).catch(() => {});
    });
    root.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && ev.target.matches?.("[data-act][tabindex]")) {
        ev.target.click();
      }
    });
    root.addEventListener("pointerdown", (ev) => this._pointerDown(ev));
    root.addEventListener("pointermove", (ev) => this._pointerMove(ev));
    root.addEventListener("pointerup", () => this._pointerUp().catch(() => {}));
    root.addEventListener("pointercancel", () => {
      clearTimeout(this._pressTimer);
      if (this._drag?.active) {
        this._render();
      }
      this._drag = null;
    });
    // Esc closes the topmost menu, drawer or dialog.
    window.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && this.isConnected && this._closeTop()) {
        ev.stopPropagation();
      }
    });
    window.addEventListener("resize", () => {
      const narrow = this._isNarrow;
      if (narrow !== this._wasNarrow) {
        this._wasNarrow = narrow;
        this._render();
      }
    });
  }
}

// Layout: a sky header (day meadow or night sky, the knob backgrounds) with
// the logo and pill tabs (desktop) or a bottom bar (phones); the content is a
// card grid; editors open as a right-hand drawer (desktop) or a full sheet
// (phones). Every overlay is fixed at the top level of the panel, above the
// page, so nothing clips it.
const STYLE = `
  :host {
    --bg: #F2F6FC; --surface: #FFFFFF; --surface-2: #EAF1FA; --surface-3: #DFE9F6;
    --ink: #18213D; --muted: #5A6684; --faint: #8C96B0; --line: #D9E2EF;
    --accent: #2C78F0; --accent-ink: #FFFFFF; --accent-soft: #DCE9FF;
    --sun: #F5A70F; --sun-soft: #FFF1CF; --good: #2FA866; --good-soft: #DDF4E6;
    --warn: #E57E1C; --warn-soft: #FFEBD6; --bad: #DD4248; --bad-soft: #FDE3E4;
    --shadow: 0 1px 2px rgb(24 33 61 / .06), 0 6px 20px rgb(24 33 61 / .07);
    --shadow-lg: 0 20px 60px rgb(24 33 61 / .22);
    --hero-veil: linear-gradient(180deg, rgb(242 246 252 / 0) 0%, rgb(242 246 252 / .55) 60%, var(--bg) 100%);
    --f-display: "KS Baloo 2", "Baloo 2", "Trebuchet MS", system-ui, sans-serif;
    --f-body: "KS Figtree", "Figtree", system-ui, -apple-system, "Segoe UI", sans-serif;
    --r-lg: 24px;
    --ease: cubic-bezier(.2, .8, .2, 1);
    display: block;
    position: relative;
    height: 100vh;
    background: var(--bg);
    color: var(--ink);
    font-family: var(--f-body);
    font-size: 15px;
    line-height: 1.45;
    -webkit-font-smoothing: antialiased;
    color-scheme: light;
  }
  :host([data-theme="dark"]) {
    --bg: #0A0F24; --surface: #131A35; --surface-2: #1A2244; --surface-3: #232D57;
    --ink: #EDF0FF; --muted: #A2ABCF; --faint: #6F79A3; --line: #29335F;
    --accent: #7DB2FF; --accent-ink: #0A1230; --accent-soft: #1F3466;
    --sun: #FFC94A; --sun-soft: #3A3014; --good: #5BD38F; --good-soft: #163828;
    --warn: #FFAA5A; --warn-soft: #3D2814; --bad: #FF7A7F; --bad-soft: #401A22;
    --shadow: 0 1px 2px rgb(0 0 0 / .3), 0 8px 24px rgb(0 0 0 / .25);
    --shadow-lg: 0 24px 70px rgb(0 0 0 / .55);
    --hero-veil: linear-gradient(180deg, rgb(10 15 36 / .1) 0%, rgb(10 15 36 / .6) 60%, var(--bg) 100%);
    color-scheme: dark;
  }
  * { box-sizing: border-box; }
  button, input, select, textarea { font: inherit; color: inherit; }
  h1, h2, h3 { font-family: var(--f-display); line-height: 1.1; margin: 0; font-weight: 700; }
  h2 { font-size: 1.45rem; }
  h3 { font-size: 1.1rem; }
  img.ic { display: inline-block; object-fit: contain; vertical-align: middle; flex: none; }
  .num { font-variant-numeric: tabular-nums; }
  .muted { color: var(--muted); }
  .small { font-size: .85rem; }
  .grow { flex: 1; min-width: 0; }
  .row { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .wrap { flex-wrap: wrap; }
  .stack { display: flex; flex-direction: column; gap: 12px; }
  :focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; border-radius: 8px; }
  .page { height: 100%; overflow-y: auto; overflow-x: hidden; }

  /* header */
  .hero { position: relative; padding: max(14px, env(safe-area-inset-top, 0px)) 16px 0; background-size: cover; background-position: center 70%; isolation: isolate; }
  .hero::before { content: ""; position: absolute; inset: 0; background: var(--hero-veil); z-index: -1; }
  .topbar { display: flex; align-items: center; gap: 10px; max-width: 1240px; margin: 0 auto; }
  .topbar ha-menu-button { color: var(--ink); background: var(--surface); border-radius: 12px; box-shadow: var(--shadow); }
  .brand { display: flex; align-items: center; min-width: 0; flex: 1 1 auto; }
  .brand .logo { height: 68px; width: auto; max-width: min(300px, 50vw); object-fit: contain; filter: drop-shadow(0 4px 10px rgb(0 0 0 / .18)); transition: transform .5s var(--ease); transform-origin: 20% 60%; }
  .brand:hover .logo { transform: rotate(-3deg) scale(1.03); }
  .top-actions { margin-left: auto; display: flex; gap: 8px; align-items: center; flex: none; }
  .pill-switch { display: flex; background: var(--surface); border-radius: 999px; padding: 4px; box-shadow: var(--shadow); gap: 2px; }
  .pill-switch button { border: 0; background: none; border-radius: 999px; padding: 6px 10px; font-weight: 700; font-size: .82rem; cursor: pointer; color: var(--muted); }
  .pill-switch button.on { background: var(--accent); color: var(--accent-ink); }
  .daynight { position: relative; width: 74px; height: 38px; border-radius: 999px; border: 0; cursor: pointer; background: linear-gradient(180deg, #8FD0FF, #CFEFFF); box-shadow: inset 0 2px 6px rgb(0 0 0 / .15), var(--shadow); overflow: hidden; transition: background .5s; flex: none; }
  .daynight .knob { position: absolute; top: 4px; left: 4px; width: 30px; height: 30px; border-radius: 50%; background: radial-gradient(circle at 35% 35%, #FFE37A, #FFB21E); box-shadow: 0 0 14px #FFD45A; transition: transform .5s var(--ease), background .5s, box-shadow .5s; }
  .daynight .st { position: absolute; width: 3px; height: 3px; border-radius: 50%; background: #fff; opacity: 0; transition: opacity .5s; animation: twinkle 2s infinite; }
  .daynight.night { background: linear-gradient(180deg, #1B2350, #30387A); }
  .daynight.night .knob { transform: translateX(36px); background: radial-gradient(circle at 60% 40%, #F4F1E6, #C9C6BA); box-shadow: 0 0 12px rgb(255 255 255 / .35); }
  .daynight.night .knob::after { content: ""; position: absolute; width: 9px; height: 9px; border-radius: 50%; background: rgb(0 0 0 / .1); left: 7px; top: 15px; box-shadow: 9px -7px 0 -2px rgb(0 0 0 / .1); }
  .daynight.night .st { opacity: .9; }
  .tabs { max-width: 1240px; margin: 14px auto 0; display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; padding: 4px 2px 12px; }
  .tabs::-webkit-scrollbar { display: none; }
  .tab { flex: none; display: flex; align-items: center; gap: 7px; border: 0; background: var(--surface); border-radius: 999px; padding: 6px 14px 6px 6px; font-weight: 700; cursor: pointer; color: var(--muted); box-shadow: var(--shadow); transition: transform .2s var(--ease), background .2s; }
  .tab img { width: 30px; height: 30px; transition: transform .3s var(--ease); }
  .tab:hover img { transform: translateY(-2px) rotate(-6deg); }
  .tab.on { background: var(--ink); color: var(--bg); }

  /* content */
  main { max-width: 1240px; margin: 0 auto; padding: 8px 16px 120px; }
  .card { background: var(--surface); border-radius: var(--r-lg); box-shadow: var(--shadow); padding: 18px; min-width: 0; }
  .card.flat { box-shadow: none; background: var(--surface-2); }
  .card.error { color: var(--bad); }
  .grid { display: grid; gap: 16px; }
  .g2 { grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr)); }
  .g3 { grid-template-columns: repeat(auto-fill, minmax(min(100%, 250px), 1fr)); }
  .section-title { display: flex; align-items: center; gap: 10px; margin: 26px 0 12px; flex-wrap: wrap; }
  .section-title h2 { flex: 1; }
  .hint { color: var(--muted); font-size: .88rem; max-width: 72ch; }
  .empty { text-align: center; padding: 36px; color: var(--muted); }
  .inactive { opacity: .55; }
  .clickable { cursor: pointer; transition: transform .2s var(--ease), box-shadow .2s; }
  .clickable:hover { transform: translateY(-2px); box-shadow: 0 2px 4px rgb(24 33 61 / .08), 0 14px 30px rgb(24 33 61 / .12); }

  /* buttons */
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; border: 1.5px solid var(--line); background: var(--surface); border-radius: 999px; padding: 8px 16px; font-weight: 700; cursor: pointer; color: var(--ink); transition: transform .15s var(--ease), background .15s, border-color .15s; white-space: nowrap; }
  .btn:hover { border-color: var(--accent); }
  .btn:active { transform: scale(.97); }
  .btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
  .btn.sun { background: var(--sun); border-color: var(--sun); color: #3B2A00; }
  .btn.danger { color: var(--bad); border-color: color-mix(in srgb, var(--bad) 40%, transparent); }
  .btn.ghost { border-color: transparent; background: transparent; }
  .btn.sm { padding: 5px 11px; font-size: .84rem; }
  .btn[disabled], button[disabled] { opacity: .45; cursor: not-allowed; }
  .iconbtn { width: 34px; height: 34px; border-radius: 50%; border: 1.5px solid var(--line); background: var(--surface); cursor: pointer; display: grid; place-items: center; color: var(--muted); flex: none; font-size: .9rem; padding: 0; }
  .iconbtn:hover { border-color: var(--accent); color: var(--ink); }
  .chip { display: inline-flex; align-items: center; gap: 6px; border: 1.5px solid var(--line); background: var(--surface); border-radius: 999px; padding: 4px 12px 4px 4px; font-weight: 600; font-size: .88rem; cursor: pointer; color: var(--muted); }
  .chip.noimg { padding-left: 12px; }
  .chip.on { background: var(--accent-soft); border-color: var(--accent); color: var(--ink); }
  .seg { display: inline-flex; background: var(--surface-2); border-radius: 999px; padding: 3px; gap: 2px; flex-wrap: wrap; }
  .seg button { border: 0; background: none; padding: 6px 14px; border-radius: 999px; font-weight: 700; cursor: pointer; color: var(--muted); display: inline-flex; align-items: center; gap: 6px; }
  .seg button.on { background: var(--surface); color: var(--ink); box-shadow: var(--shadow); }
  .badge { display: inline-grid; place-items: center; min-width: 20px; height: 20px; padding: 0 6px; border-radius: 999px; background: var(--warn-soft); color: var(--warn); font-size: .75rem; font-weight: 800; }
  .tag { display: inline-flex; align-items: center; gap: 4px; padding: 2px 9px; border-radius: 999px; font-size: .78rem; font-weight: 700; background: var(--surface-2); color: var(--muted); }
  .tag.good { background: var(--good-soft); color: var(--good); }
  .tag.warn { background: var(--warn-soft); color: var(--warn); }
  .tag.bad { background: var(--bad-soft); color: var(--bad); }
  .tag.sun { background: var(--sun-soft); color: color-mix(in srgb, var(--sun) 70%, var(--ink)); }

  /* forms */
  fieldset { border: 0; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 16px; min-width: 0; }
  .field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
  .field > span, .lbl { font-size: .78rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
  input:not([type]), input[type=text], input[type=number], input[type=date], input[type=time], input[type=search], select, textarea { width: 100%; border: 1.5px solid var(--line); background: var(--surface); border-radius: 12px; padding: 9px 12px; min-width: 0; }
  input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
  input:disabled, select:disabled { opacity: .6; }
  input.short { width: 86px; }
  input[type=color] { width: 40px; height: 40px; border: 0; border-radius: 50%; padding: 0; background: none; cursor: pointer; flex: none; }
  input[type=color]::-webkit-color-swatch-wrapper { padding: 0; }
  input[type=color]::-webkit-color-swatch { border: 3px solid var(--surface); border-radius: 50%; box-shadow: 0 0 0 1.5px var(--line); }
  input[type=range] { accent-color: var(--accent); }
  .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 200px), 1fr)); gap: 14px; }
  .switch { display: flex; align-items: center; gap: 10px; cursor: pointer; font-weight: 600; }
  .switch input { appearance: none; width: 44px; height: 26px; border-radius: 999px; background: var(--surface-3); position: relative; cursor: pointer; transition: background .2s; flex: none; margin: 0; }
  .switch input::after { content: ""; position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: var(--surface); box-shadow: 0 1px 3px rgb(0 0 0 / .25); transition: transform .25s var(--ease); }
  .switch input:checked { background: var(--good); }
  .switch input:checked::after { transform: translateX(18px); }
  .swatch { width: 34px; height: 34px; border-radius: 50%; border: 3px solid var(--surface); box-shadow: 0 0 0 1.5px var(--line); cursor: pointer; flex: none; transition: transform .15s; padding: 0; }
  .swatch.on { box-shadow: 0 0 0 3px var(--ink); transform: scale(1.08); }
  .warnbox { background: var(--warn-soft); color: var(--warn); border-radius: 12px; padding: 8px 12px; font-size: .88rem; font-weight: 600; }
  .infobox { background: var(--surface-2); border-radius: 12px; padding: 10px 14px; font-size: .88rem; color: var(--muted); }
  .pick { border: 2px dashed var(--line); background: var(--surface-2); border-radius: 16px; padding: 4px; cursor: pointer; display: grid; place-items: center; flex: none; transition: border-color .15s, transform .15s; }
  .pick:hover { border-color: var(--accent); transform: rotate(-3deg); }
  label.btn input[type=file] { display: none; }
  .task-row { padding: 6px 0; border-bottom: 1px dashed var(--line); }

  /* avatars and coins */
  .av { position: relative; display: inline-grid; place-items: center; border-radius: 50%; background: var(--surface-2); box-shadow: 0 0 0 3px var(--c, var(--line)); flex: none; overflow: hidden; }
  .av img { width: 100%; height: 100%; object-fit: cover; }
  .chip .av { box-shadow: 0 0 0 2px var(--c, var(--line)); }
  .coin { display: inline-flex; align-items: center; gap: 4px; font-weight: 800; }
  .pile { position: relative; display: inline-block; height: 34px; vertical-align: middle; }
  .pile img { position: absolute; bottom: 0; }
  .avatar-edit { position: relative; display: inline-block; width: 150px; flex: none; }
  .avatar-edit .face { border-radius: 50%; overflow: hidden; width: 140px; height: 140px; display: grid; place-items: center; background: var(--surface-2); box-shadow: 0 0 0 4px var(--c); }
  .avatar-edit .face img { width: 132px; height: 132px; object-fit: cover; border-radius: 50%; }
  .avatar-edit .corner { position: absolute; bottom: 2px; background: #fff; border: 1.5px solid var(--c); border-radius: 50%; padding: 3px; line-height: 0; box-shadow: 0 1px 2px rgb(0 0 0 / .2); cursor: pointer; }
  .avatar-edit .corner.left { left: 2px; }
  .avatar-edit .corner.right { right: 8px; }
  button.plain { background: none; border: 0; padding: 0; cursor: pointer; }

  /* today */
  .now-card { display: grid; grid-template-columns: auto 1fr; gap: 20px; align-items: center; }
  .demo-bar { display: flex; align-items: center; gap: 10px; margin-top: 12px; flex-wrap: wrap; }
  .demo-bar input[type=range] { flex: 1; min-width: 160px; }
  .flow { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
  .task-dot { display: inline-grid; place-items: center; width: 36px; height: 36px; border-radius: 12px; background: var(--surface-2); transition: transform .15s var(--ease); }
  .task-dot:hover { transform: translateY(-3px) scale(1.1); background: var(--accent-soft); }
  .task-dot.past { opacity: .45; }
  .flow-sep { width: 14px; height: 2px; background: var(--line); margin: 0 2px; }
  .child-hero { position: relative; overflow: hidden; }
  .child-hero::before { content: ""; position: absolute; inset: 0 0 auto 0; height: 86px; background: linear-gradient(135deg, color-mix(in srgb, var(--c) 32%, transparent), color-mix(in srgb, var(--c) 6%, transparent)); z-index: 0; }
  .child-hero > * { position: relative; }
  .child-top { display: flex; gap: 14px; align-items: flex-end; margin-bottom: 14px; }
  .child-top .name { font-family: var(--f-display); font-size: 1.6rem; font-weight: 800; line-height: 1; }
  .streak { display: flex; gap: 3px; margin-top: 6px; flex-wrap: wrap; }
  .streak img { width: 20px; height: 20px; }
  .balances { display: flex; gap: 8px; margin-left: auto; flex-wrap: wrap; justify-content: flex-end; }
  .bal { display: flex; align-items: center; gap: 6px; background: var(--surface); border-radius: 14px; padding: 4px 10px 4px 4px; box-shadow: var(--shadow); font-weight: 800; font-size: 1.05rem; }
  .rp { display: grid; grid-template-columns: 34px 1fr auto; gap: 4px 10px; align-items: center; padding: 10px 0; border-top: 1px dashed var(--line); }
  .rp .bar { grid-column: 2/4; height: 8px; border-radius: 99px; background: var(--surface-2); overflow: hidden; }
  .rp .bar > span { display: block; height: 100%; border-radius: 99px; background: linear-gradient(90deg, var(--good), color-mix(in srgb, var(--good) 60%, var(--sun))); transition: width .6s var(--ease); }
  .cps { grid-column: 2/4; display: flex; gap: 6px; flex-wrap: wrap; }
  .cp-chip { display: inline-flex; align-items: center; gap: 4px; font-size: .78rem; font-weight: 700; border-radius: 999px; padding: 2px 8px 2px 3px; background: var(--surface-2); color: var(--muted); }
  .cp-chip.done { background: var(--good-soft); color: var(--good); }
  .cp-chip.late { background: var(--warn-soft); color: var(--warn); }
  .mod-row { display: flex; align-items: center; gap: 10px; padding: 12px 0; border-top: 1px solid var(--line); flex-wrap: wrap; }
  .mod-row.skipped { opacity: .55; }
  .mod-row.skipped .name { text-decoration: line-through; }
  .nameblk[data-act] { cursor: pointer; border-radius: 12px; padding: 4px 6px; margin: -4px -6px; }
  .nameblk[data-act]:hover { background: var(--surface-2); }
  .nameblk .pen { opacity: 0; color: var(--accent); font-weight: 800; transition: opacity .15s; }
  .nameblk:hover .pen { opacity: 1; }
  .stepper { display: inline-flex; align-items: center; border: 1.5px solid var(--line); border-radius: 999px; overflow: hidden; }
  .stepper button { border: 0; background: var(--surface-2); width: 32px; height: 32px; cursor: pointer; font-weight: 800; }
  .stepper span { min-width: 62px; text-align: center; font-weight: 700; font-variant-numeric: tabular-nums; font-size: .9rem; }
  .dial { flex: none; display: block; }
  .dial text { font-family: var(--f-body); fill: var(--ink); }
  .mini-prog { height: 8px; border-radius: 99px; background: var(--surface-2); overflow: hidden; }
  .mini-prog span { display: block; height: 100%; background: var(--c, var(--good)); border-radius: 99px; }

  /* statistics */
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
  .kpi { background: var(--surface-2); border-radius: 16px; padding: 10px 12px; display: flex; flex-direction: column; gap: 2px; }
  .kpi b { font-family: var(--f-display); font-size: 1.6rem; line-height: 1.1; font-variant-numeric: tabular-nums; }
  .kpi .lbl { font-size: .7rem; }
  .chart { width: 100%; height: auto; display: block; overflow: visible; }
  .chart text { font-family: var(--f-body); fill: var(--muted); font-size: 11px; }
  .chart .v { fill: var(--ink); font-weight: 700; }
  .chart .hit { fill: transparent; }
  .chart g:hover .bar-m { opacity: .8; }
  .insight { display: flex; gap: 10px; align-items: flex-start; background: var(--surface-2); border-radius: 14px; padding: 10px 12px; font-size: .9rem; }
  .src { font-size: .75rem; color: var(--faint); }
  .rt-title { font-family: var(--f-display); font-size: 1.25rem; font-weight: 700; line-height: 1.1; }

  /* calendar */
  .cal-toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
  .cal-month { font-family: var(--f-display); font-weight: 700; font-size: 1.3rem; text-transform: capitalize; margin: 0 6px; }
  .cal-scroll { overflow-x: auto; }
  .cal { display: grid; grid-template-columns: 52px repeat(var(--n), minmax(110px, 1fr)); min-width: calc(52px + var(--n) * 110px); }
  .cal.n1 { grid-template-columns: 52px 1fr; min-width: 0; }
  .cal-head { position: sticky; top: 0; background: var(--surface); z-index: 2; text-align: center; padding: 6px 0 8px; border-bottom: 1px solid var(--line); }
  .cal-head .wd { display: block; font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); font-weight: 700; }
  .cal-head .dn { display: inline-grid; place-items: center; width: 36px; height: 36px; border-radius: 50%; font-family: var(--f-display); font-weight: 700; font-size: 1.25rem; }
  .cal-head.today .dn { background: var(--accent); color: var(--accent-ink); }
  .cal-head .tpl { font-size: .72rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .cal-hours { position: relative; }
  .cal-hours div { position: absolute; right: 8px; font-size: .72rem; color: var(--faint); transform: translateY(-50%); font-variant-numeric: tabular-nums; }
  .cal-col { position: relative; border-left: 1px solid var(--line); background-image: repeating-linear-gradient(180deg, transparent 0, transparent calc(var(--hpx) - 1px), var(--line) calc(var(--hpx) - 1px), var(--line) var(--hpx)); }
  .cal-col.today { background-color: color-mix(in srgb, var(--accent) 5%, transparent); }
  .cal-col.past .blk { filter: saturate(.5); opacity: .75; }
  .cal-col.drop { background-color: color-mix(in srgb, var(--accent) 14%, transparent); outline: 2px dashed var(--accent); outline-offset: -2px; }
  .blk { position: absolute; left: 4px; right: 4px; border-radius: 12px; padding: 5px 8px; background: color-mix(in srgb, var(--rc) 22%, var(--surface)); border-left: 4px solid var(--rc); cursor: pointer; overflow: hidden; font-size: .8rem; transition: transform .15s var(--ease), box-shadow .15s; user-select: none; touch-action: pan-y; }
  .blk:hover { box-shadow: var(--shadow); z-index: 3; }
  .blk.changed { border: 2px dashed var(--rc); border-left-width: 4px; }
  .blk.oneday { background-image: repeating-linear-gradient(135deg, transparent 0 6px, color-mix(in srgb, var(--rc) 18%, transparent) 6px 12px); }
  .blk.dragging { box-shadow: var(--shadow-lg); z-index: 6; transition: none; opacity: .95; touch-action: none; }
  .blk img { pointer-events: none; -webkit-user-drag: none; }
  .blk .grip { position: absolute; left: 30%; right: 30%; height: 4px; border-radius: 4px; background: var(--rc); opacity: 0; transition: opacity .15s; pointer-events: none; }
  .blk .grip.t { top: 2px; }
  .blk .grip.b { bottom: 2px; }
  .blk:hover .grip { opacity: .8; }
  .blk .bt { font-weight: 800; display: flex; gap: 4px; align-items: center; color: var(--ink); white-space: nowrap; overflow: hidden; }
  .blk .bs { color: var(--muted); font-size: .74rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .blk .cpm { position: absolute; right: 5px; width: 16px; height: 16px; }
  .now-line { position: absolute; left: 0; right: 0; height: 2px; background: var(--bad); z-index: 4; pointer-events: none; }
  .now-line::before { content: ""; position: absolute; left: -5px; top: -4px; width: 10px; height: 10px; border-radius: 50%; background: var(--bad); }

  /* routines */
  .rt-card { display: flex; gap: 16px; align-items: center; cursor: pointer; transition: transform .2s var(--ease); }
  .rt-card:hover { transform: translateY(-2px); }
  .days { display: flex; gap: 3px; margin: 6px 0; flex-wrap: wrap; }
  .days span { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; font-size: .66rem; font-weight: 800; background: var(--surface-2); color: var(--faint); }
  .days span.on { background: var(--accent-soft); color: var(--accent); }
  .strip { display: flex; gap: 2px; flex-wrap: wrap; align-items: center; }
  .strip img { width: 26px; height: 26px; }

  /* rewards */
  .shop { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 190px), 1fr)); gap: 16px; }
  .rw { position: relative; text-align: center; padding: 16px 14px 14px; cursor: pointer; transition: transform .25s var(--ease); }
  .rw:hover { transform: translateY(-4px) rotate(-.6deg); }
  .rw.preview { cursor: default; transform: none; }
  .rw .img { width: 112px; height: 112px; margin: 0 auto 6px; border-radius: 50%; display: grid; place-items: center; background: radial-gradient(circle, var(--sun-soft) 0%, transparent 70%); }
  .rw .nm { font-weight: 700; min-height: 2.8em; display: flex; align-items: center; justify-content: center; line-height: 1.25; }
  .price { display: inline-flex; align-items: center; gap: 6px; background: var(--sun-soft); border-radius: 999px; padding: 3px 12px 3px 4px; font-weight: 800; margin-top: 8px; }
  .rw .order { position: absolute; top: 8px; right: 8px; display: flex; flex-direction: column; gap: 4px; opacity: 0; transition: opacity .2s; }
  .rw:hover .order, .rw:focus-within .order { opacity: 1; }
  .rw .corner { position: absolute; top: 10px; left: 10px; }

  /* tokens */
  .wallets { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap: 16px; }
  .bigbal { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 14px 0; }
  .bigbal > div { background: var(--surface-2); border-radius: 18px; padding: 12px 14px; display: flex; align-items: center; gap: 10px; }
  .bigbal b { font-family: var(--f-display); font-size: 2rem; line-height: 1; font-variant-numeric: tabular-nums; }
  .quick { display: flex; gap: 6px; flex-wrap: wrap; }
  .quick button { border: 1.5px solid var(--line); background: var(--surface); border-radius: 12px; padding: 6px 12px; font-weight: 800; cursor: pointer; font-variant-numeric: tabular-nums; }
  .quick button.pos { color: var(--good); }
  .quick button.neg { color: var(--bad); }
  .quick button.on { background: var(--ink); color: var(--bg); border-color: var(--ink); }
  .confetti { position: fixed; pointer-events: none; z-index: 90; width: 10px; height: 10px; border-radius: 2px; animation: conf 1.1s ease-out forwards; }

  /* history */
  .filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr)); gap: 8px; margin-bottom: 14px; align-items: end; }
  .filters .search { grid-column: 1/-1; }
  .day-sep { font-family: var(--f-display); font-weight: 700; color: var(--muted); margin: 18px 4px 6px; text-transform: capitalize; }
  .tx { display: grid; grid-template-columns: auto 1fr auto; gap: 12px; align-items: center; padding: 12px 14px; background: var(--surface); border-radius: 16px; margin-bottom: 6px; box-shadow: var(--shadow); }
  .tx.dim { opacity: .5; }
  .tx.rev { background: var(--surface-2); box-shadow: none; }
  .tx.event { background: transparent; box-shadow: none; border: 1.5px dashed var(--line); padding-block: 8px; }
  .tx.event .amt { background: var(--surface-2); }
  .tx .what { font-weight: 700; }
  .tx .meta { font-size: .8rem; color: var(--muted); }
  .tx .meta .av { vertical-align: middle; }
  .tx .seq { font-size: .75rem; color: var(--faint); font-weight: 700; }
  .amt { min-width: 52px; height: 40px; padding: 0 10px; border-radius: 12px; display: grid; grid-auto-flow: column; align-items: center; justify-content: center; gap: 2px; font-weight: 800; font-family: var(--f-display); font-size: 1.15rem; font-variant-numeric: tabular-nums; }
  .amt.pos { background: var(--good-soft); color: var(--good); }
  .amt.neg { background: var(--bad-soft); color: var(--bad); }
  .ref { color: var(--accent); font-weight: 700; cursor: pointer; text-decoration: none; }
  .ref:hover { text-decoration: underline; }
  .chain { margin-top: 6px; padding: 8px 10px; border-radius: 10px; background: var(--surface-2); font-size: .82rem; }
  .tx-actions { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
  .flash { animation: flash 1.6s ease-out; }

  /* settings */
  .set-grid { columns: 2 380px; column-gap: 16px; }
  .set-grid > .card { break-inside: avoid; margin-bottom: 16px; display: flex; flex-direction: column; gap: 14px; }
  .timeline { position: relative; height: 56px; margin: 4px 16px 20px; }
  .timeline .track { position: absolute; left: 0; right: 0; top: 24px; height: 8px; border-radius: 99px; background: linear-gradient(90deg, var(--good), var(--sun) 40%, var(--surface-3) 80%, #000 100%); }
  .timeline .mk { position: absolute; top: 0; transform: translateX(-50%); text-align: center; font-size: .7rem; font-weight: 700; color: var(--muted); white-space: nowrap; }
  .timeline .mk i { display: block; width: 16px; height: 16px; border-radius: 50%; margin: 20px auto 2px; background: var(--surface); border: 3px solid var(--ink); }
  .bgs { display: grid; grid-template-columns: repeat(auto-fill, minmax(84px, 1fr)); gap: 10px; }
  .bg { aspect-ratio: 1; border-radius: 50%; border: 3px solid transparent; cursor: pointer; background-size: cover; background-position: center; box-shadow: var(--shadow); position: relative; display: grid; place-items: center; text-align: center; font-size: .75rem; font-weight: 700; color: var(--muted); background-color: var(--surface-2); transition: transform .2s; padding: 4px; }
  .bg:hover { transform: scale(1.05); }
  .bg.on { border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); }
  .bg.on::after { content: "✓"; position: absolute; right: -2px; bottom: -2px; width: 24px; height: 24px; border-radius: 50%; background: var(--accent); color: var(--accent-ink); display: grid; place-items: center; font-size: .8rem; }
  .bg.upload { border: 2px dashed var(--line); box-shadow: none; }
  .knob-card { border: 1.5px solid var(--line); border-radius: 18px; padding: 12px; }
  .knob-face { width: 54px; height: 54px; border-radius: 50%; background: #0E1430 center / cover; box-shadow: 0 0 0 4px #2A2F45, 0 0 0 6px #9AA0B5; flex: none; }
  details summary { cursor: pointer; font-weight: 700; color: var(--accent); margin-top: 4px; }
  details[open] summary { margin-bottom: 10px; }
  .banner { display: flex; align-items: center; gap: 12px; background: var(--sun-soft); border-radius: 16px; padding: 10px 14px; margin-bottom: 14px; font-weight: 600; flex-wrap: wrap; }
  .banner.bad { background: var(--bad-soft); color: var(--bad); }

  /* overlays: drawer 51, picker and dialogs 61, photo crop 71 */
  .backdrop { position: fixed; inset: 0; background: rgb(10 15 36 / .45); backdrop-filter: blur(2px); z-index: 50; animation: fade .2s; }
  .backdrop.over { z-index: 60; }
  .backdrop.top { z-index: 70; }
  .drawer { position: fixed; top: 0; right: 0; bottom: 0; width: min(640px, 100%); background: var(--bg); z-index: 51; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); animation: slide .3s var(--ease); }
  .drawer-h { display: flex; align-items: center; gap: 12px; padding: calc(14px + env(safe-area-inset-top, 0px)) 18px 12px; border-bottom: 1px solid var(--line); background: var(--surface); }
  .drawer-h h2 { flex: 1; font-size: 1.3rem; }
  .drawer-b { flex: 1; overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 16px; }
  .drawer-f { display: flex; gap: 8px; align-items: center; padding: 12px 18px calc(12px + env(safe-area-inset-bottom, 0px)); border-top: 1px solid var(--line); background: var(--surface); flex-wrap: wrap; }
  .sec-nav { display: flex; gap: 6px; overflow-x: auto; padding: 10px 18px; border-bottom: 1px solid var(--line); background: var(--surface); scrollbar-width: none; }
  .sec-nav button { flex: none; border: 0; background: var(--surface-2); border-radius: 999px; padding: 5px 12px; font-weight: 700; font-size: .85rem; cursor: pointer; color: var(--muted); display: inline-flex; gap: 4px; align-items: center; }
  .sec-nav button.on { background: var(--ink); color: var(--bg); }
  .dialog { position: fixed; left: 50%; top: 50%; transform: translate(-50%, -50%); width: min(440px, calc(100% - 32px)); background: var(--surface); border-radius: var(--r-lg); z-index: 61; padding: 22px; box-shadow: var(--shadow-lg); animation: pop .25s var(--ease); display: flex; flex-direction: column; gap: 12px; max-height: calc(100% - 40px); overflow: auto; }
  .dialog.wide { width: min(720px, calc(100% - 32px)); }
  .dialog.top { z-index: 71; }
  .icon-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(72px, 1fr)); gap: 8px; }
  .icon-grid button, .icon-grid .upload-tile { border: 2px solid transparent; background: var(--surface-2); border-radius: 16px; padding: 6px; cursor: pointer; display: grid; place-items: center; aspect-ratio: 1; transition: transform .15s; }
  .icon-grid button:hover { transform: scale(1.08) rotate(-4deg); border-color: var(--accent); }
  .icon-grid button.on { border-color: var(--accent); background: var(--accent-soft); }
  .icon-grid .upload-tile { border: 2px dashed var(--line); text-align: center; gap: 2px; }
  .crop-canvas { width: 100%; max-width: 360px; aspect-ratio: 1; align-self: center; touch-action: none; cursor: grab; border-radius: 12px; background: repeating-conic-gradient(#ccc 0 25%, #fff 0 50%) 50% / 16px 16px; }
  .toast { position: fixed; left: 50%; bottom: calc(24px + env(safe-area-inset-bottom, 0px)); transform: translateX(-50%); background: var(--ink); color: var(--bg); padding: 10px 18px; border-radius: 999px; font-weight: 700; z-index: 80; box-shadow: var(--shadow-lg); animation: toast .35s var(--ease); display: flex; gap: 8px; align-items: center; max-width: calc(100% - 32px); }
  .toast.error { background: var(--bad); }
  .tip { position: fixed; z-index: 95; pointer-events: none; background: var(--ink); color: var(--bg); font-size: .8rem; font-weight: 600; padding: 6px 10px; border-radius: 10px; box-shadow: var(--shadow-lg); max-width: 240px; transform: translate(-50%, calc(-100% - 10px)); }
  .tip[hidden] { display: none; }

  /* bottom bar (phones) */
  .bnav { display: none; }
  @keyframes fade { from { opacity: 0; } }
  @keyframes slide { from { transform: translateX(40px); opacity: 0; } }
  @keyframes pop { from { transform: translate(-50%, -46%) scale(.96); opacity: 0; } }
  @keyframes toast { from { transform: translate(-50%, 20px); opacity: 0; } }
  @keyframes conf { to { transform: translate(var(--dx), var(--dy)) rotate(540deg); opacity: 0; } }
  @keyframes twinkle { 50% { opacity: .25; } }
  @keyframes up { from { transform: translateY(40px); opacity: 0; } }
  @keyframes flash { 0% { box-shadow: 0 0 0 4px var(--sun); } 100% { box-shadow: var(--shadow); } }

  @media (max-width: 720px) {
    .brand .logo { height: auto; max-height: 46px; max-width: 100%; }
    .daynight { width: 62px; }
    .daynight.night .knob { transform: translateX(24px); }
    .pill-switch button { padding: 6px 8px; }
    .tabs { display: none; }
    .hero { padding-bottom: 12px; }
    main { padding-bottom: 110px; }
    .bnav { display: flex; position: fixed; left: 0; right: 0; bottom: 0; z-index: 30; background: var(--surface); border-top: 1px solid var(--line); padding: 6px 6px calc(6px + env(safe-area-inset-bottom, 0px)); justify-content: space-around; box-shadow: 0 -8px 24px rgb(0 0 0 / .08); }
    .bnav button { flex: 1; border: 0; background: none; display: flex; flex-direction: column; align-items: center; gap: 2px; font-size: .7rem; font-weight: 700; color: var(--muted); cursor: pointer; padding: 4px 0; border-radius: 14px; }
    .bnav button img { width: 30px; height: 30px; }
    .bnav button .dots { font-size: 1.5rem; line-height: 30px; }
    .bnav button.on { color: var(--ink); background: var(--surface-2); }
    .more-sheet { position: fixed; left: 0; right: 0; bottom: 0; z-index: 51; background: var(--surface); border-radius: 24px 24px 0 0; padding: 18px 16px calc(18px + env(safe-area-inset-bottom, 0px)); display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; animation: up .3s var(--ease); }
    .more-sheet button { border: 0; background: var(--surface-2); border-radius: 18px; padding: 12px 4px; display: flex; flex-direction: column; align-items: center; gap: 4px; font-weight: 700; font-size: .82rem; cursor: pointer; color: var(--ink); }
    .more-sheet button img { width: 40px; height: 40px; }
    .now-card { grid-template-columns: 1fr; justify-items: center; text-align: center; }
    .child-top { flex-wrap: wrap; }
    .balances { margin-left: 0; justify-content: flex-start; width: 100%; }
    .tx { grid-template-columns: auto 1fr; }
    .tx-actions { grid-column: 1/-1; justify-content: flex-start; }
    .drawer { width: 100%; }
    .rt-card { flex-wrap: wrap; justify-content: center; }
  }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
`;

if (!customElements.get("kis-segito-panel")) {
  customElements.define("kis-segito-panel", KisSegitoPanel);
}
