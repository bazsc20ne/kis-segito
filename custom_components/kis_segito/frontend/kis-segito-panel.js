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
// Knob screen power settings (seconds; dim_level in percent).
const SCREEN_KEYS = ["saver_after", "dim_after", "dim_level", "blank_after", "off_after"];
const SAVER_TYPES = ["balls", "confetti", "stars"];
const PANEL_VERSION = "0.7.18";
const FALLBACK_LANGUAGE = "en";
const LANGUAGE_AUTO = "auto";
const TABS = [
  "today",
  "calendar",
  "children",
  "routines",
  "rewards",
  "tokens",
  "history",
  "notifications",
  "settings",
];
const TAB_ICONS = {
  today: "nav_today",
  calendar: "nav_calendar",
  notifications: "nav_notifications",
  children: "nav_children",
  routines: "nav_routines",
  rewards: "nav_rewards",
  tokens: "nav_tokens",
  history: "nav_history",
  settings: "nav_settings",
};
const PRESET_COLORS = [
  "#6CB8FF", "#FF8FB1", "#6BCB77", "#FFC94A", "#A78BFA", "#FF9F43", "#4DD4C6", "#F472B6",
];
// Colours the time track uses: a child colour close to these is harder to tell apart.
const SEMANTIC_COLORS = ["#6BCB77", "#FF9F43", "#FF6B6B", "#FFC94A"];
const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];

function uid() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) =>
    b.toString(16).padStart(2, "0")
  ).join("");
}

function shiftTime(hhmm, minutes) {
  const [h, m] = String(hhmm || "0:0").split(":").map(Number);
  const total = Math.min(Math.max(h * 60 + m + minutes, 0), 23 * 60 + 59);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function toMinutes(hhmm) {
  const [h, m] = String(hhmm || "0:0").split(":").map(Number);
  return h * 60 + m;
}

// Calendar colours offered for routines (#18).
const ROUTINE_COLORS = ["#6BCB77", "#6CB8FF", "#A78BFA", "#FF8FB1", "#FFC94A", "#4DD4C6", "#FF9F43", "#8C96A5"];

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function colorDistance(a, b) {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [p(a), p(b)];
  return Math.sqrt(x.reduce((s, v, i) => s + (v - y[i]) ** 2, 0));
}

class KisSegitoPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._strings = {};
    this._loadedLanguage = null;
    this._data = null;
    this._history = [];
    this._today = null;
    this._tab = "today";
    this._edit = null; // {collection, item}
    this._picker = null; // {path, filter}
    this._historyFilter = {};
    this._week = null;
    this._weekStart = null; // null = this week
    this._calendarChild = "";
    this._rules = null;
    this._error = "";
  }

  // ------------------------------------------------------------ HA plumbing

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    this._updateLanguage();
    if (first) {
      this._subscribe();
      this._load();
      this._render();
    } else {
      const menuButton = this.shadowRoot.querySelector("ha-menu-button");
      if (menuButton) {
        menuButton.hass = hass;
      }
    }
  }

  get _isNarrow() {
    return Boolean(this._narrow) || window.innerWidth < 600;
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

  get _language() {
    const chosen = this._data?.settings?.language;
    return chosen && chosen !== LANGUAGE_AUTO ? chosen : this._hass?.language;
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
      if (this._tab === "history" || this._tab === "tokens") {
        await this._loadHistory();
      }
      if (this._tab === "today" || this._tab === "calendar") {
        await this._loadWeek();
      }
      if (this._tab === "notifications" && !this._rules) {
        await this._loadRules();
      }
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
      this._onClick({ target: { closest: () => ({ dataset: { action: "goto", arg: anchor[1] } }) } });
    }
  }

  async _loadHistory() {
    const f = this._historyFilter;
    this._history = await this._hass.callWS({
      type: "kis_segito/history",
      child_id: f.child || null,
      reasons: f.reason ? [f.reason] : null,
      account: f.account || null,
      date_from: f.from || null,
      date_to: f.to || null,
      search: f.search || null,
      limit: 500,
    });
  }

  async _loadWeek() {
    const msg = { type: "kis_segito/week" };
    if (this._weekStart) {
      msg.start = this._weekStart;
    }
    this._week = await this._hass.callWS(msg);
  }

  get _viewKey() {
    return `kis_segito_calendar_view_${this._hass?.user?.id || ""}`;
  }

  // Day, 3 days or week (#19): the user's last choice, else by screen width.
  get _calModeNow() {
    if (!this._calMode) {
      try {
        this._calMode = localStorage.getItem(this._viewKey) || "";
      } catch (_err) {
        this._calMode = "";
      }
    }
    return this._calMode || (this._isNarrow ? "day" : "week");
  }

  async _syncCalendarRange() {
    // Week view starts on Monday; day and 3-day views start on the chosen day.
    if (this._calModeNow === "week") {
      const d = new Date(`${this._calDayDate()}T12:00:00`);
      d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
      this._weekStart = this._calDay ? d.toISOString().slice(0, 10) : null;
    } else {
      this._weekStart = this._calDay || null;
      if (!this._calDay) {
        this._weekStart = new Date().toISOString().slice(0, 10);
      }
    }
    await this._loadWeek();
  }

  _calDayDate() {
    return this._calDay || this._week?.days?.find((d) => d.today)?.date || new Date().toISOString().slice(0, 10);
  }

  async _ensureWeekFor(dateStr) {
    if (this._week?.days?.some((d) => d.date === dateStr)) {
      return;
    }
    const d = new Date(`${dateStr}T12:00:00`);
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    this._weekStart = d.toISOString().slice(0, 10);
    await this._loadWeek();
  }

  _todayStr() {
    return this._week?.days?.find((d) => d.today)?.date || new Date().toISOString().slice(0, 10);
  }

  // Opens the routine editor for one date ("only this day", #17).
  _openDayEditor(dateStr, routineId, time) {
    const day = this._week?.days?.find((d) => d.date === dateStr);
    const running = day?.routines?.find((r) => r.id === routineId);
    const source = this._data.routines.find((r) => r.id === routineId) || null;
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
      collection: "day_routine",
      date: dateStr,
      routine_id: routineId,
      item,
      base: running?.one_day ? null : source ? clone(source) : null,
      edited: Boolean(running?.edited),
      one_day: Boolean(running?.one_day),
      readonly: dateStr < this._todayStr() || !this._isAdmin,
    };
  }

  // A click on a calendar block asks, like Outlook: this occurrence only, or
  // the whole series (the routine itself). One-day routines and past days
  // open directly.
  _openFromCalendar(dateStr, routineId) {
    const day = this._week?.days?.find((d) => d.date === dateStr);
    const running = day?.routines?.find((r) => r.id === routineId);
    const isSeries = this._data.routines.some((r) => r.id === routineId);
    if (!running?.one_day && isSeries && this._isAdmin && dateStr >= this._todayStr()) {
      this._askScope = { date: dateStr, routineId };
    } else {
      this._openDayEditor(dateStr, routineId);
    }
    this._render();
  }

  // Calendar drag (#17): move a block, or drag its top/bottom edge; 5-minute
  // grid, live time label; the drop becomes a change for that day only.
  _startDrag(ev, block) {
    const date = block.dataset.date;
    if (!this._isAdmin || date < this._todayStr()) {
      // Read-only: a click still opens the (read-only) editor.
      this._drag = { block, date, routineId: block.dataset.routine, readonly: true, moved: false };
      return;
    }
    const rect = block.getBoundingClientRect();
    const offset = ev.clientY - rect.top;
    const mode = offset < 8 ? "start" : rect.height - offset < 8 ? "end" : "move";
    this._drag = {
      block,
      date,
      routineId: block.dataset.routine,
      mode,
      y0: ev.clientY,
      top0: block.offsetTop,
      height0: block.offsetHeight,
      minutes: 0,
      moved: false,
      pointerId: ev.pointerId,
    };
    block.setPointerCapture?.(ev.pointerId);
  }

  _moveDrag(ev) {
    const d = this._drag;
    if (!d || d.readonly) {
      return;
    }
    const PX = 0.7;
    const minutes = Math.round((ev.clientY - d.y0) / PX / 5) * 5;
    if (!d.moved && Math.abs(ev.clientY - d.y0) < 4) {
      return;
    }
    d.moved = true;
    d.minutes = minutes;
    const day = this._week.days.find((x) => x.date === d.date);
    const r = day.routines.find((x) => x.id === d.routineId);
    let start = r.start;
    let end = r.end;
    if (d.mode === "move") {
      start = shiftTime(r.start, minutes);
      end = shiftTime(r.end, minutes);
      d.block.style.top = `${d.top0 + minutes * PX}px`;
    } else if (d.mode === "start") {
      start = shiftTime(r.start, Math.min(minutes, toMinutes(r.end) - toMinutes(r.start) - 5));
      d.block.style.top = `${d.top0 + (toMinutes(start) - toMinutes(r.start)) * PX}px`;
      d.block.style.height = `${(toMinutes(end) - toMinutes(start)) * PX}px`;
    } else {
      end = shiftTime(r.end, Math.max(minutes, toMinutes(r.start) - toMinutes(r.end) + 5));
      d.block.style.height = `${(toMinutes(end) - toMinutes(start)) * PX}px`;
    }
    d.start = start;
    d.end = end;
    const label = d.block.querySelector(".block-sub");
    if (label) {
      label.textContent = `${start}–${end}`;
    }
    d.block.classList.add("dragging");
  }

  async _endDrag() {
    const d = this._drag;
    this._drag = null;
    if (!d) {
      return;
    }
    if (!d.moved) {
      this._openFromCalendar(d.date, d.routineId);
      return;
    }
    const day = this._week.days.find((x) => x.date === d.date);
    const r = day.routines.find((x) => x.id === d.routineId);
    const routine = clone(r.routine);
    delete routine.one_day;
    if (d.mode === "move") {
      // The whole routine moves: checkpoints with it (tasks have no times).
      routine.start = d.start;
      routine.end = d.end;
      routine.checkpoints = (routine.checkpoints || []).map((c) => (c.time ? { ...c, time: shiftTime(c.time, d.minutes) } : c));
    } else {
      routine.start = d.start;
      routine.end = d.end;
    }
    // Undo puts back exactly the previous state of that day.
    this._undo = {
      date: d.date,
      routine_id: d.routineId,
      routine: r.edited || r.one_day ? (() => { const p = clone(r.routine); delete p.one_day; return p; })() : null,
    };
    await this._ws({ type: "kis_segito/day_routine", date: d.date, routine_id: d.routineId, routine });
    await this._load();
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

  // ------------------------------------------------------------ helpers

  _t(key, fallback) {
    return this._strings[key] ?? fallback ?? key;
  }

  _e(text) {
    const div = document.createElement("div");
    div.textContent = String(text ?? "");
    return div.innerHTML;
  }

  _icon(name, size = 40) {
    if (!name) {
      return "";
    }
    // An alias shares another icon's artwork.
    name = this._data?.icon_aliases?.[name] || name;
    // Small places use the simplified variant, when the icon has one.
    const small = size <= 44 && this._data?.small_icons?.includes(name) ? "small/" : "";
    return `<img class="icon" src="${this._staticUrl}/icons/${small}${this._e(name)}.png?v=${this._version}" width="${size}" height="${size}" alt="">`;
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

  // Background chooser; scope "settings" (the general one) or "child" (edit buffer).
  _backgroundField(scope, value) {
    const presets = this._data.backgrounds || [];
    const uploaded = value && !value.startsWith("bg_") ? value : "";
    const tile = (v, label) => {
      const url = this._backgroundUrl(v);
      const style = url ? `background-image:url('${url}')` : "";
      return `<button class="bg-tile ${v === (value || "") ? "sel" : ""}" style="${style}" data-action="bg-set" data-scope="${scope}" data-arg="${this._e(v)}" title="${this._e(label)}">${url ? "" : this._e(label)}</button>`;
    };
    const none = this._t(scope === "child" ? "background.general" : "background.none");
    const tiles = [tile("", none), ...presets.map((p, i) => tile(p, `${this._t("background.preset")} ${i + 1}`))];
    if (uploaded) {
      tiles.push(tile(uploaded, this._t("background.own")));
    }
    const upload = this._isAdmin
      ? `<label class="upload">${this._e(this._t("background.upload"))}<input type="file" accept="image/*" data-upload-bg="${scope}" hidden></label>`
      : "";
    return `<div class="field"><span>${this._e(this._t("background.title"))}</span>
      <div class="row wrap bg-tiles">${tiles.join("")}</div>
      <div class="row wrap">${upload}</div>
      <div class="muted">${this._e(this._t(scope === "child" ? "background.child_hint" : "background.hint"))}</div></div>`;
  }

  async _setBackground(scope, value) {
    if (scope === "child") {
      this._edit.item.background = value;
      this._render();
      return;
    }
    await this._ws({ type: "kis_segito/settings/update", background: value });
    await this._load();
  }

  _child(id) {
    return this._data?.children?.find((c) => c.id === id);
  }

  _childName(id) {
    return this._child(id)?.name || this._t("history.unknown_child");
  }

  _pile(count, max = 30) {
    // A small visual heap: up to `max` coins, then "+n".
    const shown = Math.min(count, max);
    let html = "";
    for (let i = 0; i < shown; i++) {
      html += `<span class="coin" style="--i:${i}"></span>`;
    }
    const more = count > max ? `<span class="more">+${count - max}</span>` : "";
    return `<span class="pile">${html}${more}</span>`;
  }

  _avatar(child, size = 48) {
    const inner = child.avatar_image
      ? this._photo(child.avatar_image, size - 6, true)
      : this._icon(child.avatar || "placeholder_avatar", size - 6);
    return `<span class="avatar" style="--c:${this._e(child.color || "#6CB8FF")};width:${size}px;height:${size}px">${inner}</span>`;
  }

  // An uploaded picture (Home Assistant image_upload), served at a fixed size.
  _photo(id, size, round = false) {
    return `<img class="photo ${round ? "round" : ""}" src="/api/image/serve/${this._e(id)}/256x256" width="${size}" height="${size}" alt="">`;
  }

  _pictureField(field, iconPath, filter, iconName) {
    const id = this._edit.item[field];
    const preview = id ? this._photo(id, 56, field === "avatar_image") : this._icon(iconName, 56);
    return `<div class="field"><span>${this._e(this._t("picture.title"))}</span>
      <div class="row wrap">
        ${id ? preview : `<button class="pick" data-action="pick" data-path="${iconPath}" data-arg="${filter}" title="${this._e(this._t("picture.icon"))}">${preview}</button>`}
        <label class="upload">${this._e(this._t(id ? "picture.replace" : "picture.upload"))}<input type="file" accept="image/*" data-upload="${field}" hidden></label>
        ${id ? `<button class="small" data-action="clear-picture" data-arg="${field}">${this._e(this._t("picture.remove"))}</button>` : ""}
      </div>
      <div class="muted">${this._e(this._t("picture.hint"))}</div></div>`;
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

  // ------------------------------------------------------------ actions

  async _onClick(ev) {
    const el = ev.target.closest("[data-action]");
    if (!el) {
      return;
    }
    const { action, arg, path } = el.dataset;
    if (action === "goto" && ev.preventDefault) {
      ev.preventDefault();
    }
    switch (action) {
      case "tab":
        this._tab = arg;
        this._edit = null;
        this._picker = null;
        if (arg === "history" || arg === "tokens") {
          await this._loadHistory();
        }
        if (arg === "calendar") {
          await this._syncCalendarRange();
        } else if (arg === "today") {
          await this._loadWeek();
        }
        if (arg === "notifications") {
          await this._loadRules();
        }
        break;
      case "new":
        this._edit = { collection: arg, item: this._newItem(arg) };
        break;
      case "edit": {
        const item = this._data[el.dataset.collection].find((i) => i.id === arg);
        this._edit = { collection: el.dataset.collection, item: clone(item) };
        delete this._edit.item.balances;
        delete this._edit.item.streak;
        break;
      }
      case "cancel":
        this._edit = null;
        this._picker = null;
        break;
      case "save":
        if (this._edit.collection === "day_routine") {
          await this._ws({
            type: "kis_segito/day_routine",
            date: this._edit.date,
            routine_id: this._edit.routine_id,
            routine: this._edit.item,
          });
          this._edit = null;
          this._picker = null;
          await this._load();
          return;
        }
        await this._ws({
          type: "kis_segito/save",
          collection: this._edit.collection,
          item: this._edit.item,
        });
        this._edit = null;
        this._picker = null;
        await this._load();
        return;
      case "day-restore":
      case "delete":
        if (this._edit?.collection === "day_routine") {
          // Restore the routine for that day (or remove a one-day routine).
          await this._ws({
            type: "kis_segito/day_routine",
            date: this._edit.date,
            routine_id: this._edit.routine_id,
            routine: null,
          });
          this._edit = null;
          await this._load();
          return;
        }
        if (!confirm(this._t("common.confirm_delete"))) {
          return;
        }
        await this._ws({
          type: "kis_segito/delete",
          collection: this._edit.collection,
          item_id: this._edit.item.id,
        });
        this._edit = null;
        await this._load();
        return;
      case "pick":
        this._picker = { path, filter: arg };
        break;
      case "pick-icon":
        this._set(this._picker.path, arg);
        this._picker = null;
        break;
      case "color":
        this._set(path, arg);
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
        const j = action === "up" ? i - 1 : i + 1;
        if (j >= 0 && j < list.length) {
          [list[i], list[j]] = [list[j], list[i]];
        }
        break;
      }
      case "weekday": {
        const days = this._edit.item.weekdays;
        const d = Number(arg);
        this._edit.item.weekdays = days.includes(d)
          ? days.filter((x) => x !== d)
          : [...days, d].sort();
        break;
      }
      case "chain":
        this._expanded = this._expanded || new Set();
        if (this._expanded.has(arg)) this._expanded.delete(arg);
        else this._expanded.add(arg);
        if (ev.preventDefault) ev.preventDefault();
        break;
      case "day-edit":
        this._openDayEditor(el.dataset.date, arg || null);
        break;
      case "day-new":
        this._openDayEditor(el.dataset.date, null, el.dataset.time);
        break;
      case "cal-mode":
        this._calMode = arg;
        try {
          localStorage.setItem(this._viewKey, arg);
        } catch (_err) {
          // Private mode: not remembered.
        }
        await this._syncCalendarRange();
        break;
      case "scope": {
        const ask = this._askScope;
        this._askScope = null;
        if (arg === "series") {
          const item = this._data.routines.find((r) => r.id === ask.routineId);
          this._tab = "routines";
          this._edit = { collection: "routines", item: clone(item) };
        } else if (arg === "once") {
          this._openDayEditor(ask.date, ask.routineId);
        }
        break;
      }
      case "cal-day": {
        const step = this._calModeNow === "3day" ? 3 : 1;
        const d = new Date(`${this._calDayDate()}T12:00:00`);
        d.setDate(d.getDate() + (arg === "next" ? step : arg === "prev" ? -step : 0));
        this._calDay = arg === "today" ? null : d.toISOString().slice(0, 10);
        await this._syncCalendarRange();
        break;
      }
      case "undo": {
        const undo = this._undo;
        this._undo = null;
        if (undo) {
          await this._ws({ type: "kis_segito/day_routine", date: undo.date, routine_id: undo.routine_id, routine: undo.routine });
          await this._load();
        }
        return;
      }
      case "clear-picture":
        this._edit.item[arg] = "";
        break;
      case "toggle-routine": {
        const list = this._edit.item.routines;
        const i = list.indexOf(arg);
        if (i >= 0) {
          list.splice(i, 1);
        } else {
          list.push(arg);
        }
        break;
      }
      case "toggle-child": {
        const list = this._get(path);
        const i = list.indexOf(arg);
        if (i >= 0) {
          list.splice(i, 1);
        } else {
          list.push(arg);
        }
        break;
      }
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
      case "adjust":
        await this._adjust(arg);
        return;
      case "week": {
        const base = new Date(`${this._week.start}T12:00:00`);
        base.setDate(base.getDate() + (arg === "next" ? 7 : arg === "prev" ? -7 : 0));
        this._weekStart = arg === "now" ? null : base.toISOString().slice(0, 10);
        await this._loadWeek();
        break;
      }
      case "override": {
        const shift = this.shadowRoot.querySelector(`[data-shift="${arg}"]`);
        await this._ws({
          type: "kis_segito/override",
          routine_id: arg,
          skip: el.dataset.skip === "1",
          shift_min: el.dataset.skip === "1" || el.dataset.reset === "1" ? 0 : Math.trunc(Number(shift?.value || 0)),
        });
        await this._load();
        return;
      }
      case "rule-add":
        this._rules.rules.push({
          name: "",
          service: "",
          events: ["reward_redeemed"],
          children: [],
          enabled: true,
          message_field: "",
          title_field: "",
          extra: {},
        });
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
        const [i, ev2] = arg.split(":");
        const list = this._rules.rules[Number(i)].events;
        const k = list.indexOf(ev2);
        if (k >= 0) list.splice(k, 1);
        else list.push(ev2);
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
        break;
      case "reload":
        location.reload();
        return;
      case "goto": {
        // Jump to a history entry (#n): clear filters that would hide it.
        let row = this.shadowRoot.getElementById(`tx-${arg}`);
        if (!row) {
          this._historyFilter = {};
          await this._loadHistory();
          this._render();
          row = this.shadowRoot.getElementById(`tx-${arg}`);
        }
        history.replaceState(null, "", `#tx-${arg}`);
        if (row) {
          row.scrollIntoView({ behavior: "smooth", block: "center" });
          row.classList.add("flash");
          setTimeout(() => row.classList.remove("flash"), 1600);
        }
        return;
      }
      case "export": {
        const data = await this._ws({ type: "kis_segito/export" });
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `kis-segito-${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(a.href);
        return;
      }
      case "bg-set":
        await this._setBackground(el.dataset.scope, arg);
        return;
      case "rotate-token":
        if (!confirm(this._t("settings.knob_new_key_confirm"))) {
          return;
        }
        await this._ws({ type: "kis_segito/device/rotate_token", device_id: arg });
        return;
      case "reverse":
        if (!confirm(this._t("history.confirm_reverse"))) {
          return;
        }
        await this._ws({ type: "kis_segito/tokens/reverse", transaction_id: arg });
        await this._load();
        return;
      case "correct": {
        const tx = this._history.find((t) => t.id === arg);
        const line = tx.effective_lines[0];
        const value = prompt(this._t("history.correct_prompt"), String(line.amount));
        if (value === null || value.trim() === "" || Number.isNaN(Number(value))) {
          return;
        }
        const note = prompt(this._t("history.note_prompt"), "");
        if (note === null) {
          return;
        }
        await this._ws({
          type: "kis_segito/tokens/correct",
          transaction_id: arg,
          account: line.account,
          amount: Math.trunc(Number(value)),
          note,
        });
        await this._load();
        return;
      }
      default:
        return;
    }
    this._render();
  }

  async _onChange(ev) {
    const el = ev.target;
    if (el.dataset.screen) {
      if (el.value !== "") {
        await this._ws({ type: "kis_segito/settings/update", screen: { [el.dataset.screen]: Number(el.value) } });
      }
      await this._load();
      return;
    }
    if (el.dataset.screenType !== undefined) {
      await this._ws({ type: "kis_segito/settings/update", screen: { saver_type: el.value } });
      await this._load();
      return;
    }
    if (el.dataset.deviceScreenType !== undefined) {
      await this._ws({
        type: "kis_segito/device/screen",
        device_id: el.dataset.device,
        screen: { saver_type: el.value || null },
      });
      await this._load();
      return;
    }
    if (el.dataset.deviceScreen) {
      await this._ws({
        type: "kis_segito/device/screen",
        device_id: el.dataset.device,
        screen: { [el.dataset.deviceScreen]: el.value === "" ? null : Number(el.value) },
      });
      await this._load();
      return;
    }
    if (el.dataset.setting) {
      const value =
        el.type === "number"
          ? el.value === ""
            ? null
            : Number(el.value)
          : el.value;
      const msg = { type: "kis_segito/settings/update", [el.dataset.setting]: value };
      if (el.dataset.setting === "piggy_interest_weekday") {
        msg.piggy_interest_weekday = Number(el.value);
      }
      await this._ws(msg);
      if (el.dataset.setting === "notification_label") {
        await this._loadRules();
      }
      await this._load();
      return;
    }
    if (el.dataset.assign) {
      await this._ws({
        type: "kis_segito/assign",
        child_id: el.dataset.assign,
        device_id: el.value || null,
      });
      await this._load();
      return;
    }
    if (el.dataset.filter) {
      this._historyFilter[el.dataset.filter] = el.value;
      await this._loadHistory();
      this._render();
      return;
    }
    if (el.dataset.uploadBg && el.files?.length) {
      const form = new FormData();
      form.append("file", el.files[0]);
      try {
        const response = await this._hass.fetchWithAuth("/api/image/upload", { method: "POST", body: form });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        await this._setBackground(el.dataset.uploadBg, (await response.json()).id);
      } catch (err) {
        this._error = this._t("picture.failed");
        console.warn("Kis Segito: upload failed", err);
        this._render();
      }
      return;
    }
    if (el.dataset.upload && el.files?.length) {
      // Upload through Home Assistant's image_upload; keep its id.
      const form = new FormData();
      form.append("file", el.files[0]);
      try {
        const response = await this._hass.fetchWithAuth("/api/image/upload", { method: "POST", body: form });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const image = await response.json();
        this._edit.item[el.dataset.upload] = image.id;
      } catch (err) {
        this._error = this._t("picture.failed");
        console.warn("Kis Segito: upload failed", err);
      }
      this._render();
      return;
    }
    if (el.dataset.weekdayTemplate !== undefined) {
      await this._ws({
        type: "kis_segito/day_template",
        weekday: Number(el.dataset.weekdayTemplate),
        template_id: el.value || null,
      });
      await this._load();
      return;
    }
    if (el.dataset.dateTemplate !== undefined) {
      // "" = the weekday default; "-" = no template that day.
      await this._ws({
        type: "kis_segito/day_template",
        date: el.dataset.dateTemplate,
        template_id: el.value === "" ? null : el.value === "-" ? "" : el.value,
      });
      await this._load();
      return;
    }
    if (el.dataset.calendarChild !== undefined) {
      this._calendarChild = el.value;
      this._render();
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
      return;
    }
    if (!el.dataset.path || !this._edit) {
      return;
    }
    let value = el.value;
    if (el.type === "checkbox") {
      value = el.checked;
    } else if (el.type === "number") {
      value = el.value === "" ? 0 : Number(el.value);
    }
    this._set(el.dataset.path, value);
    if (el.dataset.rerender !== undefined) {
      this._render();
    }
  }

  async _adjust(childId) {
    const amountEl = this.shadowRoot.querySelector(`[data-adjust-amount="${childId}"]`);
    const accountEl = this.shadowRoot.querySelector(`[data-adjust-account="${childId}"]`);
    const noteEl = this.shadowRoot.querySelector(`[data-adjust-note="${childId}"]`);
    const amount = Math.trunc(Number(amountEl?.value || 0));
    if (!amount) {
      return;
    }
    if (accountEl.value === "transfer") {
      // Not a ledger "adjust": a transfer between the child's own accounts.
      return;
    }
    await this._ws({
      type: "kis_segito/tokens/adjust",
      child_id: childId,
      amount,
      account: accountEl?.value || "wallet",
      note: noteEl?.value || "",
    });
    await this._load();
  }

  _newItem(collection) {
    switch (collection) {
      case "children":
        return {
          name: "",
          color: PRESET_COLORS[(this._data.children.length || 0) % PRESET_COLORS.length],
          avatar: "placeholder_avatar",
          birth_date: "",
          active: true,
          // Locked when a reward can unlock it, open otherwise (#11).
          piggy_unlocked: !this._data.rewards.some(
            (r) => r.kind === "piggy_unlock" && r.active !== false
          ),
        };
      case "rewards":
        return { name: "", icon: "reward_gift", cost: 5, active: true, kind: "normal" };
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
          color:
            ROUTINE_COLORS.find((c) => !this._data.routines.some((r) => r.color === c)) ||
            ROUTINE_COLORS[this._data.routines.length % ROUTINE_COLORS.length],
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
          checkpoints: [
            { id: uid(), name: t("defaults.ready"), icon: "task_door_ready", time: "07:45", children: [], required_for_streak: true, reward_bands: band },
          ],
          tasks: tasks(["task_wake_up", "task_toilet", "task_clothes", "task_breakfast", "task_toothbrush", "task_shoes", "task_coat"]),
        },
        {
          ...this._newItem("routines"),
          name: t("defaults.evening"),
          icon: "routine_evening",
          start: "19:00",
          end: "20:00",
          checkpoints: [
            { id: uid(), name: t("defaults.bed"), icon: "task_bed", time: "20:00", children: [], required_for_streak: true, reward_bands: band },
          ],
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
          item: {
            name: t(`defaults.${icon}`),
            icon,
            cost,
            active: true,
            kind: kind2 || "normal",
          },
        });
      }
    }
    await this._load();
  }

  // ------------------------------------------------------------ views

  _viewToday() {
    const children = this._data.children.filter((c) => c.active !== false);
    if (!children.length) {
      return `<div class="card empty">${this._e(this._t("today.no_children"))}
        <button data-action="tab" data-arg="children">${this._e(this._t("today.add_child"))}</button></div>`;
    }
    const progress = this._today?.progress || {};
    const cards = children
      .map((c) => {
        const routines = this._data.routines
          .filter((r) => r.active !== false && (!r.children?.length || r.children.includes(c.id)))
          .map((r) => {
            const p = progress[r.id]?.[c.id] || { tasks: {}, checkpoints: {} };
            const done = Object.keys(p.tasks).length;
            const total = (r.tasks || []).length;
            const pct = total ? Math.round((done / total) * 100) : 0;
            return `<div class="routine-progress">${this._icon(r.icon, 28)}
              <span class="grow">${this._e(r.name || this._t("routines.unnamed"))} <span class="muted">${this._e(r.start)}–${this._e(r.end)}</span></span>
              <span class="bar"><span style="width:${pct}%"></span></span>
              <span class="muted">${done}/${total}</span></div>`;
          })
          .join("");
        return `<div class="card child-card" style="--c:${this._e(c.color)}">
          <div class="row">${this._avatar(c, 64)}
            <div class="grow"><div class="title">${this._e(c.name)}</div>
              <div class="muted">${this._icon("streak_flame", 18)} ${c.streak}/${this._data.settings.streak_target}</div></div>
            <div class="balance">${this._pile(c.balances.wallet)}<b>${c.balances.wallet}</b></div>
          </div>
          ${c.piggy_unlocked ? `<div class="row small">${this._icon("fn_piggy", 24)} ${this._e(this._t("tokens.piggy"))}: <b>${c.balances.piggy}</b></div>` : ""}
          ${routines || `<div class="muted">${this._e(this._t("today.no_routines"))}</div>`}
        </div>`;
      })
      .join("");
    if (this._edit?.collection === "day_routine") {
      return this._editRoutine();
    }
    return `<div class="grid">${cards}</div>${this._viewModifyToday()}`;
  }

  _viewModifyToday() {
    // One-day changes: skip a routine or shift all its times, only for today.
    const day = this._week?.days?.find((d) => d.today);
    if (!day) {
      return "";
    }
    const weekday = (new Date(`${day.date}T12:00:00`).getDay() + 6) % 7;
    const template = (this._data.templates || []).find((t) => t.id === day.template);
    const scheduled = this._data.routines.filter(
      (r) =>
        r.active !== false &&
        (template ? template.routines.includes(r.id) : !r.weekdays?.length || r.weekdays.includes(weekday))
    );
    const rows = scheduled
      .map((r) => {
        const running = day.routines.find((x) => x.id === r.id);
        const skipped = day.skipped.includes(r.id);
        const shift = running?.override?.shift_min || 0;
        const times = running ? `${running.start}–${running.end}` : "";
        const state = skipped
          ? `<span class="warn">${this._e(this._t("modify.skipped"))}</span>`
          : shift
            ? `<span class="warn">${this._e(this._t("modify.shifted").replace("{n}", shift > 0 ? `+${shift}` : shift))}</span>`
            : "";
        const controls = this._isAdmin
          ? skipped
            ? `<button class="small" data-action="override" data-reset="1" data-arg="${r.id}">${this._e(this._t("modify.restore"))}</button>`
            : `<label class="inline"><input type="number" step="5" class="short" data-shift="${r.id}" value="${shift}"> ${this._e(this._t("modify.minutes"))}</label>
               <button class="small" data-action="override" data-arg="${r.id}">${this._e(this._t("modify.shift"))}</button>
               <button class="small" data-action="override" data-skip="1" data-arg="${r.id}">${this._e(this._t("modify.skip"))}</button>
               ${shift ? `<button class="small" data-action="override" data-reset="1" data-arg="${r.id}">${this._e(this._t("modify.restore"))}</button>` : ""}
               <button class="small" data-action="day-edit" data-date="${day.date}" data-arg="${r.id}">${this._e(this._t("modify.edit"))}</button>`
          : "";
        return `<div class="row wrap ${skipped ? "dim" : ""}">${this._icon(r.icon, 32)}
          <span class="grow">${this._e(r.name || this._t("routines.unnamed"))} <span class="muted">${this._e(times)}</span> ${state}</span>
          ${controls}</div>`;
      })
      .join("");
    const templates = this._data.templates || [];
    const chosen = this._data.date_templates?.[day.date];
    const templateSelect = templates.length
      ? `<label>${this._e(this._t("modify.template"))}<select data-date-template="${day.date}" ${this._isAdmin ? "" : "disabled"}>
          <option value="" ${chosen === undefined ? "selected" : ""}>${this._e(this._t("modify.template_default"))}</option>
          <option value="-" ${chosen === "" ? "selected" : ""}>${this._e(this._t("templates.own_days"))}</option>
          ${templates.map((t) => `<option value="${t.id}" ${t.id === chosen ? "selected" : ""}>${this._e(t.name)}</option>`).join("")}
        </select></label>`
      : "";
    const oneDay = day.routines
      .filter((r) => r.one_day)
      .map((r) => `<div class="row wrap">${this._icon(r.icon, 32)}<span class="grow">${this._e(r.name || this._t("routines.unnamed"))} <span class="muted">${this._e(r.start)}–${this._e(r.end)}</span> <span class="badge">1</span></span>
        ${this._isAdmin ? `<button class="small" data-action="day-edit" data-date="${day.date}" data-arg="${r.id}">${this._e(this._t("common.edit"))}</button>` : ""}</div>`)
      .join("");
    return `<div class="card form"><h2>${this._e(this._t("modify.title"))}</h2>
      <div class="muted">${this._e(this._t("modify.hint"))}</div>${templateSelect}${rows}${oneDay}
      ${this._isAdmin ? `<div class="row"><button class="small" data-action="day-new" data-date="${day.date}">+ ${this._e(this._t("modify.add_one_day"))}</button></div>` : ""}</div>`;
  }

  _viewCalendar() {
    if (this._edit?.collection === "day_routine") {
      return this._editRoutine();
    }
    if (!this._week) {
      return `<div class="card empty">${this._e(this._t("common.loading"))}</div>`;
    }
    const FROM = 5 * 60;
    const TO = 23 * 60;
    const PX = 0.7; // pixels per minute
    const filter = this._calendarChild;
    // Phones start with the day view (#19).
    const mode = this._calModeNow;
    const today = this._todayStr();
    const first = this._week.days.findIndex((d) => d.date === this._calDayDate());
    const days =
      mode === "week"
        ? this._week.days
        : this._week.days.slice(Math.max(first, 0), Math.max(first, 0) + (mode === "3day" ? 3 : 1));
    const hours = [];
    for (let h = FROM / 60; h <= TO / 60; h += 2) {
      hours.push(`<div class="hour" style="top:${(h * 60 - FROM) * PX}px">${String(h).padStart(2, "0")}:00</div>`);
    }
    const columns = days
      .map((day) => {
        const date = new Date(`${day.date}T12:00:00`);
        // Google Calendar style head: short weekday above a big day number.
        const head = `<span class="wd">${this._e(date.toLocaleDateString(this._language, { weekday: "short" }))}</span><span class="dn">${date.getDate()}</span>`;
        const past = day.date < today;
        const blocks = day.routines
          .filter((r) => !filter || !r.children.length || r.children.includes(filter))
          .map((r) => {
            const top = Math.max(0, (toMinutes(r.start) - FROM) * PX);
            const height = Math.max(18, (toMinutes(r.end) - toMinutes(r.start)) * PX);
            const who = r.children.length
              ? r.children.map((id) => this._child(id)?.name).filter(Boolean).join(", ")
              : this._t("routines.everyone");
            const cps = r.checkpoints
              .filter((c) => c.time)
              .map((c) => `<span class="cp" style="top:${(toMinutes(c.time) - toMinutes(r.start)) * PX - 7}px" title="${this._e(c.name)} ${this._e(c.time)}">${this._icon(c.icon || "checkpoint_flag", 14)}</span>`)
              .join("");
            const color = r.routine?.color || "#6BCB77";
            // Changed for this day: dashed border and a badge, not only colour (#18).
            const changed = r.edited || r.override?.shift_min || r.override?.skip;
            const badge = r.one_day
              ? `<span class="badge" title="${this._e(this._t("calendar.one_day"))}">1</span>`
              : changed
                ? `<span class="badge" title="${this._e(this._t("calendar.changed"))}">✎</span>`
                : "";
            return `<div class="block ${changed ? "changed" : ""} ${r.one_day ? "one-day" : ""} ${past ? "past" : ""}" style="top:${top}px;height:${height}px;--rc:${this._e(color)}"
              data-block data-date="${day.date}" data-routine="${this._e(r.id)}">
              <div class="block-title">${badge}${this._icon(r.icon, 16)} ${this._e(r.name || this._t("routines.unnamed"))}</div>
              <div class="block-sub">${this._e(r.start)}–${this._e(r.end)} · ${this._e(who)}</div>${cps}</div>`;
          })
          .join("");
        const tpl = day.template_name ? `<div class="tpl">${this._e(day.template_name)}</div>` : "";
        return `<div class="day ${day.today ? "is-today" : ""} ${past ? "past" : ""}"><div class="day-head">${head}${tpl}</div>
          <div class="day-body" data-day-body data-date="${day.date}" style="height:${(TO - FROM) * PX}px">${blocks}</div></div>`;
      })
      .join("");
    const options = [`<option value="">${this._e(this._t("history.all_children"))}</option>`]
      .concat(this._data.children.map((c) => `<option value="${c.id}" ${c.id === filter ? "selected" : ""}>${this._e(c.name)}</option>`))
      .join("");
    const nav = mode !== "week"
      ? `<button data-action="cal-day" data-arg="prev">‹</button>
         <button data-action="cal-day" data-arg="today">${this._e(this._t("calendar.today"))}</button>
         <button data-action="cal-day" data-arg="next">›</button>`
      : `<button data-action="week" data-arg="prev">‹</button>
         <button data-action="week" data-arg="now">${this._e(this._t("calendar.this_week"))}</button>
         <button data-action="week" data-arg="next">›</button>`;
    const month = new Date(`${days[0]?.date || today}T12:00:00`).toLocaleDateString(this._language, { year: "numeric", month: "long" });
    const ask = this._askScope
      ? `<div class="overlay"><div class="card dialog">
          <h2>${this._e(this._t("scope.title"))}</h2>
          <div class="muted">${this._e(this._t("scope.hint"))}</div>
          <div class="row wrap buttons">
            <button class="primary" data-action="scope" data-arg="once">${this._e(this._t("scope.once"))}</button>
            <button data-action="scope" data-arg="series">${this._e(this._t("scope.series"))}</button>
            <button data-action="scope" data-arg="cancel">${this._e(this._t("common.cancel"))}</button>
          </div></div></div>`
      : "";
    const undo = this._undo
      ? `<div class="card row update"><span class="grow">${this._e(this._t("calendar.moved"))}</span><button data-action="undo">${this._e(this._t("calendar.undo"))}</button></div>`
      : "";
    return `<div class="row wrap">${nav}
        <span class="month">${this._e(month)}</span>
        <span class="grow"></span>
        <span class="seg">${["day", "3day", "week"].map((m) => `<button class="${mode === m ? "sel" : ""}" data-action="cal-mode" data-arg="${m}">${this._e(this._t(`calendar.${m}`))}</button>`).join("")}</span>
        <select data-calendar-child>${options}</select></div>
      ${undo}
      <div class="card calendar ${mode}"><div class="hours" style="height:${(TO - FROM) * PX}px">${hours.join("")}</div>${columns}</div>${ask}
      <div class="muted">${this._e(this._t(this._isAdmin ? "calendar.hint_edit" : "calendar.hint"))}</div>
      ${this._viewTemplates()}`;
  }

  _viewTemplates() {
    if (this._edit?.collection === "templates") {
      const t = this._edit.item;
      const chips = this._data.routines
        .map((r) => `<button class="chip ${t.routines.includes(r.id) ? "sel" : ""}" data-action="toggle-routine" data-arg="${r.id}">${this._icon(r.icon, 18)} ${this._e(r.name || this._t("routines.unnamed"))}</button>`)
        .join("");
      return `<div class="card form"><h2>${this._e(this._t(t.id ? "templates.edit" : "templates.add"))}</h2>
        <label>${this._e(this._t("common.name"))}<input data-path="name" value="${this._e(t.name)}"></label>
        <div class="field"><span>${this._e(this._t("templates.routines"))}</span><div class="row wrap">${chips}</div></div>
        ${t.id ? `<div class="muted small">ID: ${this._e(t.id)}</div>` : ""}
        ${this._formButtons(Boolean(t.id))}</div>`;
    }
    const templates = this._data.templates || [];
    const rows = templates
      .map(
        (t) => `<div class="row"><span class="grow"><b>${this._e(t.name)}</b>
          <span class="muted">${this._e(t.routines.map((id) => this._data.routines.find((r) => r.id === id)?.name).filter(Boolean).join(", ") || "—")}</span></span>
          ${this._isAdmin ? `<button class="small" data-action="edit" data-collection="templates" data-arg="${t.id}">${this._e(this._t("common.edit"))}</button>` : ""}</div>`
      )
      .join("");
    const disabled = this._isAdmin ? "" : "disabled";
    const defaults = WEEKDAYS.map((d) => {
      const current = this._data.weekday_templates?.[String(d)] || "";
      const options = [`<option value="">${this._e(this._t("templates.own_days"))}</option>`]
        .concat(templates.map((t) => `<option value="${t.id}" ${t.id === current ? "selected" : ""}>${this._e(t.name)}</option>`))
        .join("");
      return `<label class="inline">${this._e(this._t(`weekday.${d}`))}<select data-weekday-template="${d}" ${disabled}>${options}</select></label>`;
    }).join("");
    return `<div class="card form"><h2>${this._e(this._t("templates.title"))}</h2>
      <div class="muted">${this._e(this._t("templates.hint"))}</div>
      ${rows || `<div class="muted">${this._e(this._t("templates.none"))}</div>`}
      ${this._isAdmin ? `<button data-action="new" data-arg="templates">+ ${this._e(this._t("templates.add"))}</button>` : ""}
      ${templates.length ? `<h3>${this._e(this._t("templates.weekdays"))}</h3><div class="row wrap">${defaults}</div>` : ""}
    </div>`;
  }

  _viewNotifications() {
    if (!this._rules || !this._targets) {
      return `<div class="card empty">${this._e(this._t("common.loading"))}</div>`;
    }
    const disabled = this._isAdmin ? "" : "disabled";
    const scripts = this._targets.scripts;
    const rules = this._rules.rules
      .map((rule, i) => {
        // Targets: notify actions, and scripts labelled for notifications
        // (all scripts with "show all").
        const shown = scripts.filter((sc) => sc.labelled || this._showAllScripts || sc.service === rule.service);
        const option = (value, label) =>
          `<option value="${this._e(value)}" ${value === rule.service ? "selected" : ""}>${this._e(label)}</option>`;
        const notifyOptions = [...new Set([...this._targets.notify, ...(rule.service?.startsWith("notify.") ? [rule.service] : [])])]
          .map((svc) => option(svc, svc))
          .join("");
        const scriptOptions = shown.map((sc) => option(sc.service, `${sc.name} (${sc.service})`)).join("");
        const target = `<select data-rule="${i}:service" data-rerender ${disabled}><option value="">—</option>
          <optgroup label="${this._e(this._t("notifications.notify_group"))}">${notifyOptions}</optgroup>
          ${scriptOptions ? `<optgroup label="${this._e(this._t("notifications.script_group"))}">${scriptOptions}</optgroup>` : ""}</select>`;
        let mapping = "";
        const script = scripts.find((sc) => sc.service === rule.service);
        if (script) {
          const fieldNames = Object.keys(script.fields);
          const fieldOptions = (current, allowNone) =>
            (allowNone ? [`<option value="">—</option>`] : [])
              .concat(fieldNames.map((f) => `<option value="${this._e(f)}" ${f === current ? "selected" : ""}>${this._e(script.fields[f].name)} (${this._e(f)})</option>`))
              .join("");
          const messageField = rule.message_field || (fieldNames.find((f) => /message|text|uzenet|üzenet|body/i.test(f)) ?? "");
          if (!rule.message_field && messageField) {
            rule.message_field = messageField;
          }
          const extras = fieldNames
            .filter((f) => f !== rule.message_field && f !== rule.title_field)
            .map((f) => {
              const field = script.fields[f];
              const value = rule.extra?.[f] ?? "";
              const options = field.selector?.select?.options;
              const input = Array.isArray(options)
                ? `<select data-rule-extra="${i}:${this._e(f)}" ${disabled}><option value="">—</option>${options
                    .map((o) => (typeof o === "string" ? { value: o, label: o } : o))
                    .map((o) => `<option value="${this._e(o.value)}" ${String(o.value) === String(value) ? "selected" : ""}>${this._e(o.label)}</option>`)
                    .join("")}</select>`
                : `<input data-rule-extra="${i}:${this._e(f)}" value="${this._e(value)}" ${disabled}>`;
              return `<label>${this._e(field.name)} <span class="muted">(${this._e(f)}) ${this._e(field.description)}</span>${input}</label>`;
            })
            .join("");
          mapping = `<div class="sub card">
            <label>${this._e(this._t("notifications.message_field"))}<select data-rule="${i}:message_field" data-rerender ${disabled}>${fieldOptions(rule.message_field, false)}</select></label>
            <label>${this._e(this._t("notifications.title_field"))}<select data-rule="${i}:title_field" data-rerender ${disabled}>${fieldOptions(rule.title_field, true)}</select></label>
            ${extras ? `<div class="muted">${this._e(this._t("notifications.fixed_values"))}</div>${extras}` : ""}
          </div>`;
        }
        const events = this._rules.event_types
          .map((ev) => `<button class="chip ${rule.events.includes(ev) ? "sel" : ""}" data-action="rule-event" data-arg="${i}:${ev}" ${disabled}>${this._e(this._t(`event.${ev}`, ev))}</button>`)
          .join("");
        const children = this._data.children
          .map((c) => `<button class="chip ${rule.children.includes(c.id) ? "sel" : ""}" data-action="rule-child" data-arg="${i}:${c.id}" ${disabled}>${this._e(c.name)}</button>`)
          .join("");
        return `<div class="card form">
          <div class="row"><input class="grow" placeholder="${this._e(this._t("notifications.rule_name"))}" data-rule="${i}:name" value="${this._e(rule.name)}" ${disabled}>
            <label class="check"><input type="checkbox" data-rule="${i}:enabled" ${rule.enabled !== false ? "checked" : ""} ${disabled}>${this._e(this._t("common.active"))}</label>
            ${this._isAdmin ? `<button class="icon-btn" data-action="rule-remove" data-arg="${i}">✕</button>` : ""}</div>
          <label>${this._e(this._t("notifications.target"))}${target}</label>
          ${mapping}
          <div class="field"><span>${this._e(this._t("notifications.events"))}</span><div class="row wrap">${events}</div></div>
          <div class="field"><span>${this._e(this._t("notifications.children"))}</span><div class="row wrap">${children}
            <span class="muted">${this._e(this._t(rule.children.length ? "routines.only_these" : "routines.everyone"))}</span></div></div>
          ${this._isAdmin ? `<div class="row"><button class="small" data-action="rule-test" data-arg="${i}" ${rule.service ? "" : "disabled"}>${this._e(this._t("notifications.test"))}</button>
            ${this._testResult?.[i] ? `<span class="${this._testResult[i].ok ? "muted" : "warn"}">${this._e(this._testResult[i].text)}</span>` : ""}</div>` : ""}
        </div>`;
      })
      .join("");
    const label = this._targets.label;
    const labelState = !label
      ? ""
      : this._targets.label_found
        ? `<span class="muted">${this._e(this._t("notifications.label_ok"))}</span>`
        : `<span class="warn">${this._e(this._t("notifications.label_missing"))}</span>`;
    return `<div class="muted">${this._e(this._t("notifications.hint"))}</div>
      <div class="card form">
        <label>${this._e(this._t("notifications.label"))}<input data-setting="notification_label" value="${this._e(label)}" ${disabled}></label>
        <div class="row wrap">${labelState}
          <label class="check"><input type="checkbox" data-show-all-scripts ${this._showAllScripts ? "checked" : ""}>${this._e(this._t("notifications.show_all"))}</label></div>
        <div class="muted">${this._e(this._t("notifications.label_hint"))}</div>
      </div>
      ${rules || `<div class="card empty">${this._e(this._t("notifications.none"))}</div>`}
      ${this._isAdmin ? `<div class="row"><button data-action="rule-add">+ ${this._e(this._t("notifications.add"))}</button>
        <button class="primary" data-action="rules-save">${this._e(this._t("common.save"))}</button></div>` : ""}`;
  }

  _viewChildren() {
    if (this._edit?.collection === "children") {
      return this._editChild();
    }
    const devices = this._data.devices;
    const rows = this._data.children
      .map(
        (c, i) => `<div class="card row">
          ${this._avatar(c, 48)}
          <div class="grow"><div class="title">${this._e(c.name)}${c.active === false ? ` <span class="muted">(${this._e(this._t("common.inactive"))})</span>` : ""}</div>
            <div class="muted">${this._e(c.device_id ? devices.find((d) => d.device_id === c.device_id)?.name || "?" : this._t("children.any_knob"))}</div></div>
          ${this._isAdmin ? `<button class="icon-btn" data-action="move" data-arg="children:${c.id}:-1" ${i === 0 ? "disabled" : ""}>▲</button>
          <button class="icon-btn" data-action="move" data-arg="children:${c.id}:1" ${i === this._data.children.length - 1 ? "disabled" : ""}>▼</button>
          <button data-action="edit" data-collection="children" data-arg="${c.id}">${this._e(this._t("common.edit"))}</button>` : ""}
        </div>`
      )
      .join("");
    return `${rows || `<div class="card empty">${this._e(this._t("children.none"))}</div>`}
      ${this._isAdmin ? `<button class="primary" data-action="new" data-arg="children">+ ${this._e(this._t("children.add"))}</button>` : ""}`;
  }

  _editChild() {
    const c = this._edit.item;
    const close = SEMANTIC_COLORS.some((s) => colorDistance(s, c.color || "#000000") < 60);
    const swatches = PRESET_COLORS.map(
      (col) => `<button class="swatch ${col === c.color ? "sel" : ""}" style="background:${col}" data-action="color" data-path="color" data-arg="${col}"></button>`
    ).join("");
    const knobs = [`<option value="">${this._e(this._t("children.any_knob"))}</option>`]
      .concat(
        this._data.devices.map(
          (d) => `<option value="${this._e(d.device_id)}" ${d.device_id === c.device_id ? "selected" : ""}>${this._e(d.name)}</option>`
        )
      )
      .join("");
    return `<div class="card form">
      <h2>${this._e(this._t(c.id ? "children.edit" : "children.add"))}</h2>
      <label>${this._e(this._t("common.name"))}<input data-path="name" value="${this._e(c.name)}"></label>
      <label>${this._e(this._t("children.birth_date"))}<input type="date" data-path="birth_date" value="${this._e(c.birth_date || "")}"></label>
      <div class="field"><span>${this._e(this._t("children.color"))}</span>
        <div class="row">${swatches}<input type="color" data-path="color" data-rerender value="${this._e(c.color)}"></div>
        ${close ? `<div class="warn">${this._e(this._t("children.color_warning"))}</div>` : ""}</div>
      ${c.avatar_image ? "" : `<div class="field"><span>${this._e(this._t("children.avatar"))}</span>
        <button class="pick" data-action="pick" data-path="avatar" data-arg="avatar">${this._icon(c.avatar, 56)}</button></div>`}
      ${this._pictureField("avatar_image", "avatar", "avatar", c.avatar)}
      ${this._backgroundField("child", c.background || "")}
      <label>${this._e(this._t("children.knob"))}<select data-path="device_id">${knobs}</select></label>
      <div class="muted">${this._e(this._t("children.knob_hint"))}</div>
      <label class="check"><input type="checkbox" data-path="piggy_unlocked" ${c.piggy_unlocked ? "checked" : ""}>${this._e(this._t("children.piggy_unlocked"))}</label>
      <label class="check"><input type="checkbox" data-path="active" ${c.active !== false ? "checked" : ""}>${this._e(this._t("common.active"))}</label>
      ${this._formButtons(Boolean(c.id))}
    </div>`;
  }

  _viewRoutines() {
    if (this._edit?.collection === "routines") {
      return this._editRoutine();
    }
    const days = (r) =>
      (r.weekdays?.length ? r.weekdays : WEEKDAYS).map((d) => this._t(`weekday.${d}`)).join(" ");
    const rows = this._data.routines
      .map(
        (r) => `<div class="card row">${this._icon(r.icon, 48)}
          <div class="grow"><div class="title">${this._e(r.name || this._t("routines.unnamed"))}${r.active === false ? ` <span class="muted">(${this._e(this._t("common.inactive"))})</span>` : ""}</div>
            <div class="muted">${this._e(r.start)}–${this._e(r.end)} · ${this._e(days(r))} · ${(r.tasks || []).length} ${this._e(this._t("routines.tasks_count"))}</div></div>
          ${this._isAdmin ? `<button data-action="edit" data-collection="routines" data-arg="${r.id}">${this._e(this._t("common.edit"))}</button>` : ""}
        </div>`
      )
      .join("");
    const defaults =
      !this._data.routines.length && this._isAdmin
        ? `<button data-action="defaults" data-arg="routines">${this._e(this._t("routines.add_defaults"))}</button>`
        : "";
    return `${rows || `<div class="card empty">${this._e(this._t("routines.none"))}</div>`}
      ${this._isAdmin ? `<button class="primary" data-action="new" data-arg="routines">+ ${this._e(this._t("routines.add"))}</button> ${defaults}` : ""}`;
  }

  _childChips(path) {
    const list = this._get(path) || [];
    const chips = this._data.children
      .map(
        (c) => `<button class="chip ${list.includes(c.id) ? "sel" : ""}" data-action="toggle-child" data-path="${path}" data-arg="${c.id}">${this._e(c.name)}</button>`
      )
      .join("");
    return `<div class="row wrap">${chips}<span class="muted">${this._e(this._t(list.length ? "routines.only_these" : "routines.everyone"))}</span></div>`;
  }

  _editRoutine() {
    const r = this._edit.item;
    const dayMode = this._edit.collection === "day_routine";
    const base = this._edit.base;
    // In "only this day" mode, sections that differ from the routine are marked.
    const diff = (key) =>
      dayMode && base && JSON.stringify(r[key] ?? null) !== JSON.stringify(base[key] ?? null)
        ? ` <span class="badge" title="${this._e(this._t("calendar.changed"))}">✎</span>`
        : "";
    const others = this._data.routines.filter((x) => x.id !== r.id && x.color);
    const similar = r.color && others.some((x) => colorDistance(x.color, r.color) < 50);
    const colorField = `<div class="field"><span>${this._e(this._t("routines.color"))}${diff("color")}</span>
      <div class="row wrap">${ROUTINE_COLORS.map((col) => `<button class="swatch ${col === r.color ? "sel" : ""}" style="background:${col}" data-action="color" data-path="color" data-arg="${col}"></button>`).join("")}
        <input type="color" data-path="color" data-rerender value="${this._e(r.color || "#6BCB77")}"></div>
      ${similar ? `<div class="warn">${this._e(this._t("routines.color_similar"))}</div>` : ""}
      <div class="muted">${this._e(this._t("routines.color_hint"))}</div></div>`;
    const weekdays = WEEKDAYS.map(
      (d) => `<button class="chip ${(r.weekdays || []).includes(d) ? "sel" : ""}" data-action="weekday" data-arg="${d}">${this._e(this._t(`weekday.${d}`))}</button>`
    ).join("");
    const zones = r.zones
      .map(
        (z, i) => `<div class="row">
          <label class="inline">${this._e(this._t("routines.zone_from"))}<input type="number" min="0" data-path="zones.${i}.offset_min" value="${z.offset_min}"> ${this._e(this._t("routines.min_before_end"))}</label>
          <input type="color" data-path="zones.${i}.color" value="${this._e(z.color)}">
          <button class="icon-btn" data-action="remove" data-path="zones" data-arg="${i}">✕</button></div>`
      )
      .join("");
    const cpOptions = (sel) =>
      [`<option value="">${this._e(this._t("routines.last_checkpoint"))}</option>`]
        .concat(
          r.checkpoints.map(
            (cp) => `<option value="${cp.id}" ${cp.id === sel ? "selected" : ""}>${this._e(cp.name || cp.time)}</option>`
          )
        )
        .join("");
    const checkpoints = r.checkpoints
      .map(
        (cp, i) => `<div class="sub card">
          <div class="row"><button class="pick" data-action="pick" data-path="checkpoints.${i}.icon" data-arg="checkpoint">${this._icon(cp.icon, 40)}</button>
            <input class="grow" placeholder="${this._e(this._t("common.name"))}" data-path="checkpoints.${i}.name" value="${this._e(cp.name)}">
            <input type="time" data-path="checkpoints.${i}.time" value="${this._e(cp.time)}">
            <button class="icon-btn" data-action="remove" data-path="checkpoints" data-arg="${i}">✕</button></div>
          ${this._childChips(`checkpoints.${i}.children`)}
          <label class="check"><input type="checkbox" data-path="checkpoints.${i}.required_for_streak" ${cp.required_for_streak ? "checked" : ""}>${this._e(this._t("routines.streak_required"))}</label>
          <div class="muted">${this._e(this._t("routines.bands"))}</div>
          ${cp.reward_bands
            .map(
              (b, j) => `<div class="row"><label class="inline"><input type="number" data-path="checkpoints.${i}.reward_bands.${j}.min_early_min" value="${b.min_early_min}"> ${this._e(this._t("routines.min_early"))}</label>
                <label class="inline">→ <input type="number" min="0" data-path="checkpoints.${i}.reward_bands.${j}.tokens" value="${b.tokens}"> ${this._icon("token_coin_front", 20)}</label>
                <button class="icon-btn" data-action="remove" data-path="checkpoints.${i}.reward_bands" data-arg="${j}">✕</button></div>`
            )
            .join("")}
          <button data-action="add" data-path="checkpoints.${i}.reward_bands" data-arg="band">+ ${this._e(this._t("routines.add_band"))}</button>
        </div>`
      )
      .join("");
    const tasks = r.tasks
      .map(
        (t, i) => `<div class="row">
          <button class="pick" data-action="pick" data-path="tasks.${i}.icon" data-arg="task">${this._icon(t.icon, 40)}</button>
          <input class="grow" placeholder="${this._e(this._t("routines.label_optional"))}" data-path="tasks.${i}.label" value="${this._e(t.label || "")}">
          <select data-path="tasks.${i}.checkpoint_id">${cpOptions(t.checkpoint_id)}</select>
          <button class="icon-btn" data-action="up" data-path="tasks" data-arg="${i}">▲</button>
          <button class="icon-btn" data-action="down" data-path="tasks" data-arg="${i}">▼</button>
          <button class="icon-btn" data-action="remove" data-path="tasks" data-arg="${i}">✕</button></div>`
      )
      .join("");
    const dateLabel = dayMode
      ? new Date(`${this._edit.date}T12:00:00`).toLocaleDateString(this._language, { weekday: "long", year: "numeric", month: "long", day: "numeric" })
      : "";
    const title = dayMode
      ? `${this._t(this._edit.one_day || !this._edit.routine_id ? "day.one_day_title" : "day.title")}: ${dateLabel}`
      : this._t(r.id ? "routines.edit" : "routines.add");
    const dayNote = dayMode
      ? `<div class="card sub">${this._e(this._t(this._edit.readonly ? "day.readonly" : "day.hint"))}</div>`
      : "";
    return `<div class="card form sheet ${dayMode ? "day-mode" : ""}">
      <h2>${this._e(title)}</h2>${dayNote}
      <fieldset ${this._edit.readonly ? "disabled" : ""}>
      <div class="row"><button class="pick" data-action="pick" data-path="icon" data-arg="routine">${this._icon(r.icon, 56)}</button>
        <label class="grow">${this._e(this._t("common.name"))}${diff("name")}<input data-path="name" value="${this._e(r.name)}"></label></div>
      <div class="row wrap"><label>${this._e(this._t("routines.start"))}${diff("start")}<input type="time" data-path="start" value="${this._e(r.start)}"></label>
        <label>${this._e(this._t("routines.end"))}${diff("end")}<input type="time" data-path="end" value="${this._e(r.end)}"></label></div>
      ${dayMode ? "" : `<div class="field"><span>${this._e(this._t("routines.days"))}</span><div class="row wrap">${weekdays}</div></div>`}
      <div class="field"><span>${this._e(this._t("routines.children"))}${diff("children")}</span>${this._childChips("children")}</div>
      ${colorField}
      <label class="check"><input type="checkbox" data-path="on_device" ${r.on_device !== false ? "checked" : ""}>${this._e(this._t("routines.on_device"))}</label>
      ${dayMode ? "" : `<label class="check"><input type="checkbox" data-path="active" ${r.active !== false ? "checked" : ""}>${this._e(this._t("common.active"))}</label>`}
      <h3>${this._e(this._t("routines.zones"))}${diff("zones")}</h3>
      <div class="muted">${this._e(this._t("routines.zones_hint"))}</div>
      <div class="row"><span>${this._e(this._t("routines.base_color"))}${diff("base_color")}</span><input type="color" data-path="base_color" value="${this._e(r.base_color || "#6BCB77")}"></div>
      ${zones}
      <button data-action="add" data-path="zones" data-arg="zone">+ ${this._e(this._t("routines.add_zone"))}</button>
      <h3>${this._e(this._t("routines.checkpoints"))}${diff("checkpoints")}</h3>
      <div class="muted">${this._e(this._t("routines.checkpoints_hint"))}</div>
      ${checkpoints}
      <button data-action="add" data-path="checkpoints" data-arg="checkpoint" data-rerender>+ ${this._e(this._t("routines.add_checkpoint"))}</button>
      <h3>${this._e(this._t("routines.tasks"))}${diff("tasks")}</h3>
      ${tasks}
      <button data-action="add" data-path="tasks" data-arg="task">+ ${this._e(this._t("routines.add_task"))}</button>
      ${r.id && !dayMode ? `<div class="muted small">ID: ${this._e(r.id)}</div>` : ""}
      </fieldset>
      ${dayMode ? this._dayButtons() : this._formButtons(Boolean(r.id))}
    </div>`;
  }

  _dayButtons() {
    const e = this._edit;
    if (e.readonly) {
      return `<div class="row buttons"><button data-action="cancel">${this._e(this._t("common.close"))}</button></div>`;
    }
    return `<div class="row buttons">
      <button class="primary" data-action="save">${this._e(this._t("day.save"))}</button>
      <button data-action="cancel">${this._e(this._t("common.cancel"))}</button>
      <span class="grow"></span>
      ${e.routine_id && e.edited && !e.one_day ? `<button data-action="day-restore">${this._e(this._t("day.restore"))}</button>` : ""}
      ${e.one_day ? `<button class="danger" data-action="delete">${this._e(this._t("day.remove"))}</button>` : ""}
    </div>`;
  }

  _viewRewards() {
    if (this._edit?.collection === "rewards") {
      return this._editReward();
    }
    const rows = this._data.rewards
      .map(
        (r, i) => `<div class="card row">${r.image ? this._photo(r.image, 56) : this._icon(r.icon, 56)}
          <div class="grow"><div class="title">${this._e(r.name)}${r.kind === "piggy_unlock" ? ` · ${this._e(this._t("rewards.piggy_unlock"))}` : ""}${r.active === false ? ` <span class="muted">(${this._e(this._t("common.inactive"))})</span>` : ""}</div>
            <div class="balance left">${this._pile(r.cost, 20)}<b>${r.cost}</b></div></div>
          ${this._isAdmin ? `<button class="icon-btn" data-action="move" data-arg="rewards:${r.id}:-1" ${i === 0 ? "disabled" : ""}>▲</button>
          <button class="icon-btn" data-action="move" data-arg="rewards:${r.id}:1" ${i === this._data.rewards.length - 1 ? "disabled" : ""}>▼</button>
          <button data-action="edit" data-collection="rewards" data-arg="${r.id}">${this._e(this._t("common.edit"))}</button>` : ""}
        </div>`
      )
      .join("");
    const defaults =
      !this._data.rewards.length && this._isAdmin
        ? `<button data-action="defaults" data-arg="rewards">${this._e(this._t("rewards.add_defaults"))}</button>`
        : "";
    return `${rows || `<div class="card empty">${this._e(this._t("rewards.none"))}</div>`}
      ${this._isAdmin ? `<button class="primary" data-action="new" data-arg="rewards">+ ${this._e(this._t("rewards.add"))}</button> ${defaults}` : ""}`;
  }

  _editReward() {
    const r = this._edit.item;
    return `<div class="card form">
      <h2>${this._e(this._t(r.id ? "rewards.edit" : "rewards.add"))}</h2>
      ${this._pictureField("image", "icon", "reward", r.icon)}
      <div class="row">${r.image ? "" : `<button class="pick" data-action="pick" data-path="icon" data-arg="reward">${this._icon(r.icon, 56)}</button>`}
        <label class="grow">${this._e(this._t("common.name"))}<input data-path="name" value="${this._e(r.name)}"></label></div>
      <label>${this._e(this._t("rewards.cost"))}<input type="number" min="0" data-path="cost" data-rerender value="${r.cost}"></label>
      <div class="balance left">${this._pile(Number(r.cost) || 0, 40)}</div>
      <label>${this._e(this._t("rewards.kind"))}<select data-path="kind">
        <option value="normal" ${r.kind !== "piggy_unlock" ? "selected" : ""}>${this._e(this._t("rewards.normal"))}</option>
        <option value="piggy_unlock" ${r.kind === "piggy_unlock" ? "selected" : ""}>${this._e(this._t("rewards.piggy_unlock"))}</option>
      </select></label>
      <label class="check"><input type="checkbox" data-path="active" ${r.active !== false ? "checked" : ""}>${this._e(this._t("common.active"))}</label>
      ${this._formButtons(Boolean(r.id))}
    </div>`;
  }

  _viewTokens() {
    const rows = this._data.children
      .map(
        (c) => `<div class="card">
          <div class="row">${this._avatar(c, 48)}<div class="grow title">${this._e(c.name)}</div>
            <div class="balance">${this._icon("wallet", 24)} ${this._pile(c.balances.wallet, 20)}<b>${c.balances.wallet}</b></div>
            ${c.piggy_unlocked ? `<div class="balance">${this._icon("fn_piggy", 24)}<b>${c.balances.piggy}</b></div>` : ""}</div>
          ${this._isAdmin ? `<div class="row wrap">
            <input type="number" class="short" data-adjust-amount="${c.id}" placeholder="±">
            <select data-adjust-account="${c.id}"><option value="wallet">${this._e(this._t("tokens.wallet"))}</option>
              ${c.piggy_unlocked ? `<option value="piggy">${this._e(this._t("tokens.piggy"))}</option>` : ""}</select>
            <input class="grow" data-adjust-note="${c.id}" placeholder="${this._e(this._t("tokens.note"))}">
            <button data-action="adjust" data-arg="${c.id}">${this._e(this._t("tokens.apply"))}</button></div>` : ""}
        </div>`
      )
      .join("");
    return `${rows || `<div class="card empty">${this._e(this._t("children.none"))}</div>`}
      <div class="muted">${this._e(this._t("tokens.hint"))}</div>`;
  }

  _viewHistory() {
    const f = this._historyFilter;
    const opt = (value, label, current) =>
      `<option value="${this._e(value)}" ${value === (current || "") ? "selected" : ""}>${this._e(label)}</option>`;
    const children = [opt("", this._t("history.all_children"), f.child)]
      .concat(this._data.children.map((c) => opt(c.id, c.name, f.child)))
      .join("");
    const reasons = [opt("", this._t("history.all_types"), f.reason)]
      .concat(
        ["checkpoint_reward", "reward_redemption", "piggy_transfer", "piggy_interest", "streak_reward", "manual_adjustment", "reversal", "correction"].map((r) =>
          opt(r, this._t(`reason.${r}`, r), f.reason)
        )
      )
      .join("");
    const accounts = [opt("", this._t("history.all_accounts"), f.account), opt("wallet", this._t("tokens.wallet"), f.account), opt("piggy", this._t("tokens.piggy"), f.account)].join("");
    const filters = `<div class="row wrap filters">
      <select data-filter="child">${children}</select>
      <select data-filter="reason">${reasons}</select>
      <select data-filter="account">${accounts}</select>
      <label class="inline">${this._e(this._t("history.from"))}<input type="date" data-filter="from" value="${this._e(f.from || "")}"></label>
      <label class="inline">${this._e(this._t("history.to"))}<input type="date" data-filter="to" value="${this._e(f.to || "")}"></label>
      <input class="grow" type="search" data-filter="search" placeholder="${this._e(this._t("history.search"))}" value="${this._e(f.search || "")}">
    </div>`;
    const sign = (n) => `${n > 0 ? "+" : ""}${n}`;
    const rows = this._history
      .map((tx) => {
        const link = (n) => `<a href="#tx-${n}" class="ref" data-action="goto" data-arg="${n}">#${n}</a>`;
        const target = tx.target_seq ? `[[ref:${tx.target_seq}]]` : "";
        // Every entry shows its own booked amount (#16); the effective value of a
        // corrected entry is only in its chain view.
        const amounts = tx.lines
          .map((l) => `<span class="amount ${l.amount < 0 ? "neg" : "pos"}">${sign(l.amount)}${l.account === "piggy" ? " 🐷" : ""}</span>`)
          .join(" ");
        let what = tx.refs?.reward_name || tx.refs?.checkpoint_name || tx.note || this._t(`reason.${tx.reason}`, tx.reason);
        if (tx.corrects) {
          // A correction: its own entry, pointing to the original.
          what = `${this._t("history.correction_of").replace("{n}", target)}: ${sign(tx.old_amount ?? 0)} → ${sign(tx.new_amount ?? 0)}`;
        } else if (tx.reverses) {
          what = this._t("history.reversal_of").replace("{n}", target);
        }
        const note = (tx.corrects || tx.reverses) && tx.note ? ` · „${tx.note}”` : "";
        const when = new Date(tx.timestamp).toLocaleString(this._language);
        let revisions = "";
        let chain = "";
        if (tx.correction_seqs?.length) {
          revisions += ` · ${this._e(this._t("history.revised_by"))} ${tx.correction_seqs.map(link).join(", ")}`;
          const open = this._expanded?.has(tx.id);
          revisions += ` · <a class="ref" data-action="chain" data-arg="${tx.id}">${this._e(this._t(open ? "history.chain_hide" : "history.chain"))}</a>`;
          if (open) {
            const steps = this._history
              .filter((h) => h.corrects === tx.id)
              .sort((a, b) => a.seq - b.seq)
              .map((h) => `<div>${link(h.seq)} ${this._e(sign(h.old_amount ?? 0))} → ${this._e(sign(h.new_amount ?? 0))} · ${this._e(new Date(h.timestamp).toLocaleString(this._language))} · ${this._e(this._t(`creator.${h.creator}`, h.creator))}${h.note ? ` · „${this._e(h.note)}”` : ""}</div>`)
              .join("");
            const effective = tx.effective_lines.map((l) => sign(l.amount)).join(" ");
            chain = `<div class="chain small"><div>#${tx.seq} ${this._e(this._t("history.booked"))} ${this._e(tx.lines.map((l) => sign(l.amount)).join(" "))}</div>${steps}
              <div><b>${this._e(this._t("history.effective"))} ${this._e(effective)}</b></div></div>`;
          }
        }
        if (tx.reversal_seq) {
          revisions += ` · ${this._e(this._t("history.reversed_by"))} ${link(tx.reversal_seq)}`;
        }
        // Escape the text, then turn the target placeholder into a link.
        const whatHtml = this._e(what).replace(/\[\[ref:(\d+)\]\]/g, (_m, n) => link(n));
        const actions =
          this._isAdmin && !tx.reversed_by && !tx.reverses && !tx.corrects
            ? `<button class="small" data-action="correct" data-arg="${tx.id}">${this._e(this._t("history.correct"))}</button>
               <button class="small" data-action="reverse" data-arg="${tx.id}">${this._e(this._t("history.reverse"))}</button>`
            : "";
        return `<div id="tx-${tx.seq}" class="card row ${tx.reversed_by ? "dim" : ""} ${tx.corrects || tx.reverses ? "revision" : ""}">
          <span class="seq">#${tx.seq}</span>
          <div class="grow"><div>${amounts} · ${whatHtml}${this._e(note)}</div>
            <div class="muted small">${this._e(when)} · ${this._e(this._childName(tx.child_id))} · ${this._e(this._t(`reason.${tx.reason}`, tx.reason))} · ${this._e(this._t(`creator.${tx.creator}`, tx.creator))}${revisions}</div>${chain}</div>
          ${actions}</div>`;
      })
      .join("");
    return `${filters}
      ${rows || `<div class="card empty">${this._e(this._t("history.none"))}</div>`}`;
  }

  _viewSettings() {
    const s = this._data.settings;
    const disabled = this._isAdmin ? "" : "disabled";
    const languages = [{ code: LANGUAGE_AUTO, name: this._t("settings.language_auto") }, ...s.languages]
      .map((l) => `<option value="${this._e(l.code)}" ${l.code === s.language ? "selected" : ""}>${this._e(l.name)}</option>`)
      .join("");
    const num = (key, min, max, step = 1) =>
      `<input type="number" min="${min}" max="${max}" step="${step}" data-setting="${key}" value="${s[key] ?? ""}" ${disabled}>`;
    const devices = this._data.devices
      .map((d) => {
        const assigned = this._data.children.filter((c) => c.device_id === d.device_id);
        const avatars = assigned.length
          ? assigned.map((c) => this._avatar(c, 32)).join("")
          : `<span class="muted">${this._e(this._t("settings.knob_everyone"))}</span>`;
        const warning = d.encrypted ? "" : `<div class="muted warn">${this._e(this._t("settings.knob_unencrypted"))}</div>`;
        const rotate = this._isAdmin
          ? `<button class="small" data-action="rotate-token" data-arg="${this._e(d.device_id)}">${this._e(this._t("settings.knob_new_key"))}</button>`
          : "";
        const own = d.screen || {};
        const screen = SCREEN_KEYS.map(
          (k) => `<label>${this._e(this._t(`screen.${k}`))}<input type="number" min="${k === "dim_level" ? 1 : 0}" max="${k === "dim_level" ? 100 : 86400}"
            data-device-screen="${k}" data-device="${this._e(d.device_id)}" value="${own[k] ?? ""}" placeholder="${this._e(String(s.screen?.[k] ?? ""))}" ${disabled}></label>`
        ).join("");
        return `<div class="row">${this._icon("nav_settings", 28)}<span class="grow">${this._e(d.name)}</span>${avatars}${rotate}</div>${warning}
          <details class="knob-screen"><summary>${this._e(this._t("screen.own"))}</summary>
            <div class="muted">${this._e(this._t("screen.own_hint"))}</div>${screen}
            <label>${this._e(this._t("screen.saver_type"))}<select data-device-screen-type data-device="${this._e(d.device_id)}" ${disabled}>
              <option value="">${this._e(this._t("screen.general"))}</option>
              ${SAVER_TYPES.map((t) => `<option value="${t}" ${own.saver_type === t ? "selected" : ""}>${this._e(this._t(`screen.saver_${t}`))}</option>`).join("")}
            </select></label></details>`;
      })
      .join("");
    const weekdays = WEEKDAYS.map(
      (d) => `<option value="${d}" ${Number(s.piggy_interest_weekday) === d ? "selected" : ""}>${this._e(this._t(`weekday.${d}`))}</option>`
    ).join("");
    return `<div class="card form">
        <h2>${this._e(this._t("settings.title"))}</h2>
        <label>${this._e(this._t("settings.language"))}<select data-setting="language" ${disabled}>${languages}</select></label>
        <div class="muted">${this._e(this._t("settings.language_hint"))}</div>
        <label>${this._e(this._t("settings.animation"))}<select data-setting="animation_mode" ${disabled}>
          ${["full", "reduced", "off"].map((m) => `<option value="${m}" ${s.animation_mode === m ? "selected" : ""}>${this._e(this._t(`settings.animation_${m}`))}</option>`).join("")}
        </select></label>
        <label>${this._e(this._t("settings.inactivity"))}${num("inactivity_s", 10, 3600, 10)}</label>
      </div>
      <div class="card form">
        <h2>${this._e(this._t("screen.title"))}</h2>
        ${SCREEN_KEYS.map(
          (k) => `<label>${this._e(this._t(`screen.${k}`))}<input type="number" min="${k === "dim_level" ? 1 : 0}" max="${k === "dim_level" ? 100 : 86400}" data-screen="${k}" value="${s.screen?.[k] ?? ""}" ${disabled}></label>`
        ).join("")}
        <label>${this._e(this._t("screen.saver_type"))}<select data-screen-type ${disabled}>
          ${SAVER_TYPES.map((t) => `<option value="${t}" ${(s.screen?.saver_type || "balls") === t ? "selected" : ""}>${this._e(this._t(`screen.saver_${t}`))}</option>`).join("")}
        </select></label>
        <div class="muted">${this._e(this._t("screen.hint"))}</div>
      </div>
      <div class="card form">
        <h2>${this._e(this._t("background.title"))}</h2>
        ${this._backgroundField("settings", s.background || "")}
      </div>
      <div class="card form">
        <h2>${this._e(this._t("settings.knobs"))}</h2>
        ${devices || `<div class="muted">${this._e(this._t("settings.no_knobs"))}</div>`}
        <div class="muted">${this._e(this._t("settings.knobs_hint"))}</div>
      </div>
      <div class="card form">
        <h2>${this._e(this._t("settings.streak"))}</h2>
        <label>${this._e(this._t("settings.streak_target"))}${num("streak_target", 0, 365)}</label>
        <label>${this._e(this._t("settings.streak_reward"))}${num("streak_reward", 0, 1000)}</label>
      </div>
      <div class="card form">
        <h2>${this._e(this._t("settings.piggy"))}</h2>
        <label>${this._e(this._t("settings.interest_percent"))}${num("piggy_interest_percent", 0, 100, 0.5)}</label>
        <div class="row"><label>${this._e(this._t("settings.interest_day"))}<select data-setting="piggy_interest_weekday" ${disabled}>${weekdays}</select></label>
          <label>${this._e(this._t("settings.interest_time"))}<input type="time" data-setting="piggy_interest_time" value="${this._e(s.piggy_interest_time)}" ${disabled}></label></div>
        <div class="row"><label>${this._e(this._t("settings.interest_min"))}${num("piggy_interest_min", 0, 1000)}</label>
          <label>${this._e(this._t("settings.interest_max"))}${num("piggy_interest_max", 0, 1000)}</label></div>
      </div>
      ${this._isAdmin ? "" : `<div class="muted">${this._e(this._t("settings.admin_only"))}</div>`}
      ${this._isAdmin ? `<div class="card form"><h2>${this._e(this._t("settings.data"))}</h2>
        <div class="muted">${this._e(this._t("settings.export_hint"))}</div>
        <div class="row"><button data-action="export">${this._e(this._t("settings.export"))}</button></div></div>` : ""}
      <div class="muted small">${this._e(this._t("panel.version"))}: ${this._e(this._version)}</div>`;
  }

  _formButtons(existing) {
    return `<div class="row buttons">
      <button class="primary" data-action="save">${this._e(this._t("common.save"))}</button>
      <button data-action="cancel">${this._e(this._t("common.cancel"))}</button>
      <span class="grow"></span>
      ${existing ? `<button class="danger" data-action="delete">${this._e(this._t("common.delete"))}</button>` : ""}
    </div>`;
  }

  _viewPicker() {
    if (!this._picker) {
      return "";
    }
    const filters = {
      avatar: (n) => n.startsWith("avatar_") || n.startsWith("test_avatar") || n === "placeholder_avatar",
      task: (n) => n.startsWith("task_") || n.startsWith("routine_"),
      checkpoint: (n) => n.startsWith("task_") || n.startsWith("routine_") || n === "checkpoint_flag",
      routine: (n) => n.startsWith("routine_") || n.startsWith("task_"),
      reward: (n) => n.startsWith("reward_") || n === "fn_piggy",
    };
    const filter = filters[this._picker.filter] || (() => true);
    const icons = this._data.icons
      .filter(filter)
      .map((n) => `<button class="pick" title="${this._e(n)}" data-action="pick-icon" data-arg="${this._e(n)}">${this._icon(n, 56)}</button>`)
      .join("");
    return `<div class="overlay"><div class="card picker">
      <div class="row"><h2 class="grow">${this._e(this._t("common.choose_icon"))}</h2>
        <button data-action="cancel-picker">✕</button></div>
      <div class="icons">${icons}</div></div></div>`;
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

  _render() {
    if (!this.shadowRoot) {
      return;
    }
    let body = `<div class="card empty">${this._e(this._t("common.loading"))}</div>`;
    if (this._data) {
      const view = {
        today: () => this._viewToday(),
        children: () => this._viewChildren(),
        routines: () => this._viewRoutines(),
        rewards: () => this._viewRewards(),
        tokens: () => this._viewTokens(),
        history: () => this._viewHistory(),
        settings: () => this._viewSettings(),
        calendar: () => this._viewCalendar(),
        notifications: () => this._viewNotifications(),
      }[this._tab];
      try {
        body = view();
      } catch (err) {
        // Never leave the old screen silently: show what went wrong.
        console.error("Kis Segito: render failed", err);
        body = `<div class="card error">${this._e(String(err))}</div>`;
      }
    }
    const tabs = TABS.map(
      (tab) => `<button class="tab ${tab === this._tab ? "sel" : ""}" data-action="tab" data-arg="${tab}">${this._icon(TAB_ICONS[tab], 28)}<span>${this._e(this._t(`tab.${tab}`))}</span></button>`
    ).join("");
    const scroll = this.shadowRoot.querySelector(".content")?.scrollTop ?? 0;
    // The field being edited keeps the focus and the cursor across a redraw
    // (settings are saved while you type, see the "input" listener).
    const focused = this.shadowRoot.activeElement;
    const focusKey = focused?.matches?.("input, textarea, select") ? this._fieldKey(focused) : null;
    const selection = focusKey && typeof focused.selectionStart === "number"
      ? [focused.selectionStart, focused.selectionEnd]
      : null;
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="toolbar">
        <ha-menu-button></ha-menu-button>
        <span class="title">${this._e(this._t("panel.title"))}</span>
      </div>
      <nav class="tabs">${tabs}</nav>
      <div class="content">
        ${this._data?.version && this._data.version !== PANEL_VERSION
          ? `<div class="card update row"><span class="grow">${this._e(this._t("panel.outdated"))}</span>
              <button class="primary" data-action="reload">${this._e(this._t("panel.reload"))}</button></div>`
          : ""}
        ${this._error ? `<div class="card error">${this._e(this._error)}</div>` : ""}
        ${body}
      </div>
      ${this._viewPicker()}
    `;
    const content = this.shadowRoot.querySelector(".content");
    if (content) {
      content.scrollTop = scroll;
    }
    if (focusKey) {
      const field = [...this.shadowRoot.querySelectorAll("input, textarea, select")].find(
        (el) => this._fieldKey(el) === focusKey
      );
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
    const menuButton = this.shadowRoot.querySelector("ha-menu-button");
    if (menuButton) {
      menuButton.hass = this._hass;
      menuButton.narrow = this._narrow;
    }
    if (!this._listening) {
      this._listening = true;
      this.shadowRoot.addEventListener("click", (ev) => {
        if (ev.target.closest('[data-action="cancel-picker"]')) {
          this._picker = null;
          this._render();
          return;
        }
        this._onClick(ev).catch(() => {});
      });
      this.shadowRoot.addEventListener("change", (ev) => {
        // Already saved while typing (see below): nothing new.
        if (ev.target.dataset?.saved !== undefined && ev.target.dataset.saved === ev.target.value) {
          return;
        }
        this._onChange(ev).catch(() => {});
      });
      // Settings fields are saved 2 s after the last keystroke, and when the
      // field is left (the "change" event above); no Enter or button needed.
      this.shadowRoot.addEventListener("input", (ev) => {
        const el = ev.target;
        if (!el.matches?.("input, textarea") || ["checkbox", "radio", "file", "range"].includes(el.type)) {
          return;
        }
        clearTimeout(this._inputTimer);
        this._inputTimer = setTimeout(() => {
          if (!el.isConnected || el.dataset.saved === el.value) {
            return;
          }
          el.dataset.saved = el.value;
          this._onChange({ target: el }).catch(() => {});
        }, 2000);
      });
      // Calendar: drag blocks (mouse at once, touch after a long press).
      this.shadowRoot.addEventListener("pointerdown", (ev) => {
        const block = ev.target.closest?.("[data-block]");
        if (block) {
          // No native image dragging or text selection inside blocks.
          if (ev.pointerType !== "touch") {
            ev.preventDefault();
          }
          if (ev.pointerType === "touch") {
            this._pressTimer = setTimeout(() => this._startDrag(ev, block), 400);
            this._pressBlock = block;
          } else {
            this._startDrag(ev, block);
          }
          return;
        }
      });
      this.shadowRoot.addEventListener("click", (ev) => {
        // Empty calendar space: a routine for that day only, at that time.
        if (ev.target.closest?.("[data-block]")) {
          return;
        }
        const body = ev.target.closest?.("[data-day-body]");
        if (body && this._isAdmin && body.dataset.date >= this._todayStr()) {
          const y = ev.clientY - body.getBoundingClientRect().top;
          const minutes = Math.min(Math.round((5 * 60 + y / 0.7) / 15) * 15, 22 * 60);
          this._openDayEditor(body.dataset.date, null, `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`);
          this._render();
        }
      });
      this.shadowRoot.addEventListener("pointermove", (ev) => {
        if (this._pressTimer && !this._drag) {
          return;
        }
        if (this._drag) {
          ev.preventDefault();
          this._moveDrag(ev);
        }
      });
      const end = () => {
        if (this._pressTimer && !this._drag) {
          // A short tap on a block opens it.
          clearTimeout(this._pressTimer);
          this._pressTimer = null;
          const block = this._pressBlock;
          this._pressBlock = null;
          if (block) {
            this._openFromCalendar(block.dataset.date, block.dataset.routine);
          }
          return;
        }
        this._pressTimer = null;
        this._endDrag().catch(() => {});
      };
      this.shadowRoot.addEventListener("pointerup", end);
      this.shadowRoot.addEventListener("pointercancel", () => {
        clearTimeout(this._pressTimer);
        this._pressTimer = null;
        this._drag = null;
      });
    }
  }
}

const STYLE = `
  :host {
    display: block;
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--primary-background-color, #fafafa);
    color: var(--primary-text-color, #212121);
    font-family: var(--paper-font-body1_-_font-family, inherit);
  }
  .toolbar {
    display: flex;
    align-items: center;
    height: var(--header-height, 56px);
    padding: 0 16px;
    background: var(--app-header-background-color, var(--primary-color, #03a9f4));
    color: var(--app-header-text-color, var(--text-primary-color));
    font-size: 20px;
    flex: none;
  }
  .toolbar .title { margin-left: 8px; }
  .tabs {
    display: flex;
    gap: 4px;
    overflow-x: auto;
    padding: 8px 12px;
    flex: none;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
    background: var(--card-background-color, #fff);
  }
  .tab {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    min-width: 72px;
    border: none;
    background: none;
    color: var(--secondary-text-color, #727272);
    padding: 6px 8px;
    border-radius: 12px;
    font-size: 12px;
  }
  .tab.sel { background: var(--secondary-background-color, #f5f5f5); color: var(--primary-text-color, #212121); font-weight: 500; }
  .content { flex: 1; overflow-y: auto; padding: 16px; max-width: 960px; width: 100%; box-sizing: border-box; margin: 0 auto; }
  .card {
    background: var(--card-background-color, #fff);
    border-radius: var(--ha-card-border-radius, 12px);
    border: 1px solid var(--divider-color, #e0e0e0);
    padding: 12px 16px;
    margin-bottom: 12px;
  }
  .card.sub { background: var(--secondary-background-color, #f5f5f5); }
  .card.empty { color: var(--secondary-text-color, #727272); }
  .card.error { border-color: var(--error-color, #db4437); color: var(--error-color, #db4437); }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
  .grid .card { margin: 0; }
  .child-card { border-top: 4px solid var(--c); }
  .bg-tiles { gap: 8px; }
  .knob-screen { margin: 0 0 12px 40px; }
  .knob-screen summary { cursor: pointer; color: var(--primary-color, #03a9f4); }
  .bg-tile {
    width: 72px; height: 72px; border-radius: 12px; padding: 4px; font-size: 12px;
    background: var(--secondary-background-color, #eee) center / cover;
    border: 2px solid var(--divider-color, #e0e0e0); color: var(--primary-text-color);
  }
  .bg-tile.sel { border: 3px solid var(--primary-color, #03a9f4); }
  .row { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
  .row.wrap { flex-wrap: wrap; }
  .row.small, .small { font-size: 12px; }
  .grow { flex: 1; min-width: 0; }
  .title { font-weight: 500; font-size: 16px; }
  .muted { color: var(--secondary-text-color, #727272); font-size: 13px; }
  .muted.warn { color: var(--error-color, #db4437); }
  .warn { color: var(--warning-color, #FF9F43); font-size: 13px; }
  .dim { opacity: 0.55; }
  h2 { margin: 0 0 8px; font-size: 18px; font-weight: 500; }
  h3 { margin: 16px 0 4px; font-size: 15px; font-weight: 500; }
  .form label, .field { display: flex; flex-direction: column; gap: 4px; margin: 8px 0; }
  .form label.check, label.check { flex-direction: row; align-items: center; gap: 8px; }
  label.inline { flex-direction: row !important; align-items: center; gap: 6px; margin: 0 !important; }
  input, select {
    font: inherit;
    padding: 6px 8px;
    color: var(--primary-text-color, #212121);
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: 6px;
    max-width: 100%;
    box-sizing: border-box;
  }
  input[type="number"] { width: 90px; }
  input.short { width: 80px; }
  input[type="color"] { width: 44px; height: 32px; padding: 2px; }
  input[type="checkbox"] { width: 18px; height: 18px; }
  button {
    font: inherit;
    cursor: pointer;
    padding: 6px 12px;
    border-radius: 18px;
    border: 1px solid var(--divider-color, #e0e0e0);
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color, #212121);
  }
  button:disabled { opacity: 0.4; cursor: default; }
  button.primary { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); border-color: var(--primary-color, #03a9f4); }
  button.danger { color: var(--error-color, #db4437); border-color: var(--error-color, #db4437); }
  button.small { padding: 2px 10px; font-size: 12px; }
  button.icon-btn { padding: 4px 8px; border-radius: 8px; }
  button.pick { padding: 4px; border-radius: 12px; line-height: 0; }
  .chip { padding: 4px 10px; font-size: 13px; }
  .chip.sel { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); border-color: var(--primary-color, #03a9f4); }
  .swatch { width: 28px; height: 28px; padding: 0; border-radius: 50%; border: 2px solid transparent; }
  .swatch.sel { border-color: var(--primary-text-color, #212121); }
  .buttons { margin-top: 16px; }
  .icon { display: inline-block; vertical-align: middle; object-fit: contain; }
  .avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--c);
    flex: none;
  }
  .balance { display: flex; align-items: center; gap: 6px; font-size: 18px; }
  .balance.left { justify-content: flex-start; }
  .pile { display: inline-flex; flex-wrap: wrap-reverse; max-width: 120px; justify-content: flex-end; }
  .coin {
    width: 10px;
    height: 10px;
    margin: -1px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, #FFE7A0, #E8B730 60%, #B8860B);
    box-shadow: 0 1px 0 rgba(0, 0, 0, 0.3);
  }
  .more { font-size: 12px; color: var(--secondary-text-color, #727272); margin-left: 4px; }
  .routine-progress { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 14px; }
  .bar { width: 80px; height: 8px; border-radius: 4px; background: var(--divider-color, #e0e0e0); overflow: hidden; }
  .bar span { display: block; height: 100%; background: var(--success-color, #6BCB77); }
  .seq { font-variant-numeric: tabular-nums; color: var(--secondary-text-color, #727272); min-width: 40px; }
  .revision { border-left: 4px solid var(--warning-color, #FF9F43); }
  .amount.pos { color: var(--success-color, #2e7d32); font-weight: 500; }
  .amount.neg { color: var(--error-color, #db4437); font-weight: 500; }
  .calendar { display: flex; overflow-x: auto; padding: 8px; gap: 4px; }
  .hours { position: relative; width: 44px; flex: none; margin-top: 66px; }
  .hour { position: absolute; font-size: 11px; color: var(--secondary-text-color, #727272); transform: translateY(-50%); }
  .day { flex: 1; min-width: 96px; }
  .day-head { height: 24px; text-align: center; font-size: 13px; color: var(--secondary-text-color, #727272); }
  .day.is-today .day-head { color: var(--primary-color, #03a9f4); font-weight: 500; }
  .day-body { position: relative; border-left: 1px solid var(--divider-color, #e0e0e0); background: repeating-linear-gradient(to bottom, transparent 0, transparent 83px, var(--divider-color, #e0e0e0) 83px, var(--divider-color, #e0e0e0) 84px); }
  /* Google Calendar-like: solid colour blocks with white text. */
  .block { position: absolute; left: 2px; right: 4px; border-radius: 6px; padding: 2px 6px; overflow: hidden;
    background: var(--rc, #6BCB77); color: #fff; border: 2px solid var(--rc, #6BCB77);
    font-size: 12px; box-sizing: border-box; cursor: grab; touch-action: pan-y; user-select: none;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2); }
  .block .block-sub { color: rgba(255, 255, 255, 0.9); }
  .block.changed { border-color: #fff; outline: 2px dashed var(--rc, #6BCB77); outline-offset: -1px; }
  .block .badge { background: #fff; color: #222; }
  .day-head { display: flex; flex-direction: column; align-items: center; gap: 2px; height: 66px; min-height: 0; box-sizing: border-box; overflow: hidden; }
  .day-head .wd { font-size: 11px; text-transform: uppercase; color: var(--secondary-text-color, #727272); }
  .day-head .dn { font-size: 20px; width: 34px; height: 34px; line-height: 34px; text-align: center; border-radius: 50%; }
  .day.is-today .day-head .dn { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
  .month { font-size: 18px; font-weight: 500; }
  .dialog { max-width: 420px; margin: 16px; }
  .block img { pointer-events: none; -webkit-user-drag: none; }
  .block::before, .block::after { content: ""; position: absolute; left: 0; right: 0; height: 6px; cursor: ns-resize; }
  .block::before { top: 0; }
  .block::after { bottom: 0; }

  .block.one-day { border-style: dotted; background-image: repeating-linear-gradient(45deg, transparent 0 6px, rgba(255, 255, 255, 0.25) 6px 12px); }
  .block.past, .day.past .day-head { opacity: 0.55; cursor: default; }
  .block.dragging { opacity: 0.85; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25); z-index: 2; }
  .badge { display: inline-block; min-width: 16px; padding: 0 4px; margin-right: 3px; border-radius: 8px; font-size: 10px; text-align: center;
    background: var(--primary-text-color, #212121); color: var(--card-background-color, #fff); }
  .seg { display: inline-flex; }
  .seg button { border-radius: 0; }
  .seg button:first-child { border-radius: 18px 0 0 18px; }
  .seg button:last-child { border-radius: 0 18px 18px 0; }
  .seg button.sel { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
  fieldset { border: none; margin: 0; padding: 0; min-width: 0; }
  .calendar.day .day { min-width: 0; }
  .block-title { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .block-sub { color: var(--secondary-text-color, #727272); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .cp { position: absolute; right: 2px; line-height: 0; }
  .tpl { font-size: 11px; color: var(--primary-color, #03a9f4); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .day-head { height: auto; min-height: 24px; }
  .filters select, .filters input { max-width: 180px; }
  .filters input[type="search"] { min-width: 180px; max-width: none; }
  .photo { object-fit: cover; border-radius: 10px; vertical-align: middle; }
  .photo.round { border-radius: 50%; }
  label.upload { display: inline-block; cursor: pointer; padding: 6px 12px; border-radius: 18px; border: 1px solid var(--divider-color, #e0e0e0); }
  .chain { margin-top: 6px; padding: 6px 10px; border-left: 3px solid var(--divider-color, #e0e0e0); }
  .update { border-color: var(--primary-color, #03a9f4); }
  a.ref { color: var(--primary-color, #03a9f4); text-decoration: none; font-weight: 500; cursor: pointer; }
  a.ref:hover { text-decoration: underline; }
  .flash { animation: flash 1.6s ease-out; }
  @keyframes flash { 0% { background: rgba(255, 201, 74, 0.6); } 100% { background: var(--card-background-color, #fff); } }
  /* Phones and narrow windows (#19): one column, no sideways scrolling,
     44 px touch targets, editors as full-screen sheets. */
  @media (max-width: 600px) {
    .content { padding: 8px; }
    .grid { grid-template-columns: 1fr; }
    .card { padding: 10px 12px; }
    button, select, input:not([type="checkbox"]):not([type="color"]) { min-height: 44px; }
    button.icon-btn, button.pick { min-width: 44px; }
    .form label, .form input:not([type="checkbox"]):not([type="color"]), .form select { width: 100%; }
    label.inline { flex-wrap: wrap; }
    .row { flex-wrap: wrap; }
    .tab { min-width: 64px; }
    .sheet { position: fixed; inset: 0; z-index: 5; margin: 0; border-radius: 0; overflow-y: auto; }
    .filters select, .filters input { max-width: none; width: 100%; }
    .calendar { padding: 4px; }
    .calendar.week .day { min-width: 84px; }
    .pile { max-width: 80px; }
    button.swatch { width: 44px; height: 44px; min-height: 44px; }
  }
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
  }
  .picker { width: min(720px, 92vw); max-height: 80vh; overflow-y: auto; }
  .icons { display: grid; grid-template-columns: repeat(auto-fill, minmax(72px, 1fr)); gap: 8px; }
`;

if (!customElements.get("kis-segito-panel")) {
  customElements.define("kis-segito-panel", KisSegitoPanel);
}
