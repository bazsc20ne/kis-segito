// SPDX-License-Identifier: AGPL-3.0-only
//
// Kis Segito sidebar panel. Plain web component, no build step.
// Texts come from translations/<language>.json next to this file; adding a
// language only needs a new JSON file. The language follows the Home Assistant
// user language unless one is chosen in the panel settings.
//
// Data comes from the kis_segito/* WebSocket commands; the panel re-reads it
// after every change (kis_segito/subscribe).

const FALLBACK_LANGUAGE = "en";
const LANGUAGE_AUTO = "auto";
const TABS = ["today", "children", "routines", "rewards", "tokens", "history", "settings"];
const TAB_ICONS = {
  today: "nav_today",
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
    this._historyChild = "";
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
    } catch (err) {
      console.warn("Kis Segito: loading data failed", err);
    }
    this._updateLanguage();
    this._render();
  }

  async _loadHistory() {
    this._history = await this._hass.callWS({
      type: "kis_segito/history",
      child_id: this._historyChild || null,
      limit: 300,
    });
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
    return `<img class="icon" src="${this._staticUrl}/icons/${this._e(name)}.png?v=${this._version}" width="${size}" height="${size}" alt="">`;
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
    return `<span class="avatar" style="--c:${this._e(child.color || "#6CB8FF")};width:${size}px;height:${size}px">${this._icon(child.avatar || "placeholder_avatar", size - 6)}</span>`;
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
    switch (action) {
      case "tab":
        this._tab = arg;
        this._edit = null;
        this._picker = null;
        if (arg === "history" || arg === "tokens") {
          await this._loadHistory();
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
        await this._ws({
          type: "kis_segito/save",
          collection: this._edit.collection,
          item: this._edit.item,
        });
        this._edit = null;
        this._picker = null;
        await this._load();
        return;
      case "delete":
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
    if (el.dataset.filter === "history") {
      this._historyChild = el.value;
      await this._loadHistory();
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
    return `<div class="grid">${cards}</div>`;
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
      <div class="field"><span>${this._e(this._t("children.avatar"))}</span>
        <button class="pick" data-action="pick" data-path="avatar" data-arg="avatar">${this._icon(c.avatar, 56)}</button></div>
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
    const weekdays = WEEKDAYS.map(
      (d) => `<button class="chip ${r.weekdays.includes(d) ? "sel" : ""}" data-action="weekday" data-arg="${d}">${this._e(this._t(`weekday.${d}`))}</button>`
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
    return `<div class="card form">
      <h2>${this._e(this._t(r.id ? "routines.edit" : "routines.add"))}</h2>
      <div class="row"><button class="pick" data-action="pick" data-path="icon" data-arg="routine">${this._icon(r.icon, 56)}</button>
        <label class="grow">${this._e(this._t("common.name"))}<input data-path="name" value="${this._e(r.name)}"></label></div>
      <div class="row"><label>${this._e(this._t("routines.start"))}<input type="time" data-path="start" value="${this._e(r.start)}"></label>
        <label>${this._e(this._t("routines.end"))}<input type="time" data-path="end" value="${this._e(r.end)}"></label></div>
      <div class="field"><span>${this._e(this._t("routines.days"))}</span><div class="row wrap">${weekdays}</div></div>
      <div class="field"><span>${this._e(this._t("routines.children"))}</span>${this._childChips("children")}</div>
      <label class="check"><input type="checkbox" data-path="on_device" ${r.on_device !== false ? "checked" : ""}>${this._e(this._t("routines.on_device"))}</label>
      <label class="check"><input type="checkbox" data-path="active" ${r.active !== false ? "checked" : ""}>${this._e(this._t("common.active"))}</label>
      <h3>${this._e(this._t("routines.zones"))}</h3>
      <div class="muted">${this._e(this._t("routines.zones_hint"))}</div>
      <div class="row"><span>${this._e(this._t("routines.base_color"))}</span><input type="color" data-path="base_color" value="${this._e(r.base_color || "#6BCB77")}"></div>
      ${zones}
      <button data-action="add" data-path="zones" data-arg="zone">+ ${this._e(this._t("routines.add_zone"))}</button>
      <h3>${this._e(this._t("routines.checkpoints"))}</h3>
      <div class="muted">${this._e(this._t("routines.checkpoints_hint"))}</div>
      ${checkpoints}
      <button data-action="add" data-path="checkpoints" data-arg="checkpoint" data-rerender>+ ${this._e(this._t("routines.add_checkpoint"))}</button>
      <h3>${this._e(this._t("routines.tasks"))}</h3>
      ${tasks}
      <button data-action="add" data-path="tasks" data-arg="task">+ ${this._e(this._t("routines.add_task"))}</button>
      ${r.id ? `<div class="muted small">ID: ${this._e(r.id)}</div>` : ""}
      ${this._formButtons(Boolean(r.id))}
    </div>`;
  }

  _viewRewards() {
    if (this._edit?.collection === "rewards") {
      return this._editReward();
    }
    const rows = this._data.rewards
      .map(
        (r, i) => `<div class="card row">${this._icon(r.icon, 56)}
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
      <div class="row"><button class="pick" data-action="pick" data-path="icon" data-arg="reward">${this._icon(r.icon, 56)}</button>
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
    const options = [`<option value="">${this._e(this._t("history.all_children"))}</option>`]
      .concat(
        this._data.children.map(
          (c) => `<option value="${c.id}" ${c.id === this._historyChild ? "selected" : ""}>${this._e(c.name)}</option>`
        )
      )
      .join("");
    const sign = (n) => `${n > 0 ? "+" : ""}${n}`;
    const rows = this._history
      .map((tx) => {
        const target = tx.target_seq ? `#${tx.target_seq}` : "";
        const amounts = (tx.reverses || tx.corrects ? tx.lines : tx.effective_lines)
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
        if (tx.correction_seqs?.length) {
          revisions += ` · ${this._t("history.revised_by")} ${tx.correction_seqs.map((n) => `#${n}`).join(", ")}`;
        }
        if (tx.reversal_seq) {
          revisions += ` · ${this._t("history.reversed_by")} #${tx.reversal_seq}`;
        }
        const actions =
          this._isAdmin && !tx.reversed_by && !tx.reverses && !tx.corrects
            ? `<button class="small" data-action="correct" data-arg="${tx.id}">${this._e(this._t("history.correct"))}</button>
               <button class="small" data-action="reverse" data-arg="${tx.id}">${this._e(this._t("history.reverse"))}</button>`
            : "";
        return `<div class="card row ${tx.reversed_by ? "dim" : ""} ${tx.corrects || tx.reverses ? "revision" : ""}">
          <span class="seq">#${tx.seq}</span>
          <div class="grow"><div>${amounts} · ${this._e(what)}${this._e(note)}</div>
            <div class="muted small">${this._e(when)} · ${this._e(this._childName(tx.child_id))} · ${this._e(this._t(`reason.${tx.reason}`, tx.reason))} · ${this._e(this._t(`creator.${tx.creator}`, tx.creator))}${this._e(revisions)}</div></div>
          ${actions}</div>`;
      })
      .join("");
    return `<div class="row"><select data-filter="history">${options}</select></div>
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
        return `<div class="row">${this._icon("nav_settings", 28)}<span class="grow">${this._e(d.name)}</span>${avatars}</div>`;
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
      avatar: (n) => n.startsWith("test_avatar") || n === "placeholder_avatar",
      task: (n) => n.startsWith("task_"),
      checkpoint: (n) => n.startsWith("task_") || n === "checkpoint_flag",
      routine: (n) => n.startsWith("routine_"),
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
      }[this._tab];
      body = view();
    }
    const tabs = TABS.map(
      (tab) => `<button class="tab ${tab === this._tab ? "sel" : ""}" data-action="tab" data-arg="${tab}">${this._icon(TAB_ICONS[tab], 28)}<span>${this._e(this._t(`tab.${tab}`))}</span></button>`
    ).join("");
    const scroll = this.shadowRoot.querySelector(".content")?.scrollTop ?? 0;
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="toolbar">
        <ha-menu-button></ha-menu-button>
        <span class="title">${this._e(this._t("panel.title"))}</span>
      </div>
      <nav class="tabs">${tabs}</nav>
      <div class="content">
        ${this._error ? `<div class="card error">${this._e(this._error)}</div>` : ""}
        ${body}
      </div>
      ${this._viewPicker()}
    `;
    const content = this.shadowRoot.querySelector(".content");
    if (content) {
      content.scrollTop = scroll;
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
      this.shadowRoot.addEventListener("change", (ev) => this._onChange(ev).catch(() => {}));
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
  .row { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
  .row.wrap { flex-wrap: wrap; }
  .row.small, .small { font-size: 12px; }
  .grow { flex: 1; min-width: 0; }
  .title { font-weight: 500; font-size: 16px; }
  .muted { color: var(--secondary-text-color, #727272); font-size: 13px; }
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
