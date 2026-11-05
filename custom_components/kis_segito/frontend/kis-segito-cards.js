// SPDX-License-Identifier: AGPL-3.0-only
//
// Kis Segítő dashboard cards for parents: child, today's routine, reward shop,
// approvals, weekly statistics, quick +/−, event log, knob status and a mini
// overview. They come with the integration (no separate install), follow the
// dashboard theme and the user's language, and each has a visual editor.

const STATIC_URL = "/kis_segito_static";
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// ---------------------------------------------------------------- shared data

// One data load and one change subscription for every card on the page.
const store = {
  hass: null,
  data: null,
  generation: 0,
  error: null,
  listeners: new Set(),
  texts: {},
  textsLoading: {},
  aliases: {},
  unsub: null,
  loading: null,
  timer: null,

  attach(hass, listener) {
    this.hass = hass;
    this.listeners.add(listener);
    if (!this.unsub) {
      this.unsub = true;
      hass.connection
        .subscribeMessage(() => this.reloadSoon(), { type: "kis_segito/subscribe" })
        .then((unsub) => {
          this.unsub = unsub;
          if (!this.listeners.size) {
            this.stop();
          }
        })
        .catch(() => {
          this.unsub = null;
        });
      fetch(`${STATIC_URL}/icons/aliases.json`)
        .then((r) => (r.ok ? r.json() : {}))
        .then((a) => {
          this.aliases = a || {};
        })
        .catch(() => {});
    }
    if (!this.data && !this.loading) {
      this.reload();
    }
    this.loadTexts(hass.language);
  },

  detach(listener) {
    this.listeners.delete(listener);
    if (!this.listeners.size) {
      this.stop();
    }
  },

  stop() {
    if (typeof this.unsub === "function") {
      this.unsub();
      this.unsub = null;
    }
  },

  reloadSoon() {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.reload(), 300);
  },

  reload() {
    if (!this.hass) {
      return Promise.resolve();
    }
    this.loading = this.hass
      .callWS({ type: "kis_segito/cards" })
      .then((data) => {
        this.data = data;
        this.generation += 1;
        this.error = null;
      })
      .catch((err) => {
        this.error = err?.message || String(err);
      })
      .finally(() => {
        this.loading = null;
        this.notify();
      });
    return this.loading;
  },

  notify() {
    this.listeners.forEach((l) => l());
  },

  // Panel translations of a language (English for missing texts).
  loadTexts(language) {
    const lang = (language || "en").split("-")[0];
    for (const l of new Set(["en", lang])) {
      if (this.texts[l] || this.textsLoading[l]) {
        continue;
      }
      this.textsLoading[l] = fetch(`${STATIC_URL}/translations/${l}.json`)
        .then((r) => (r.ok ? r.json() : {}))
        .catch(() => ({}))
        .then((t) => {
          this.texts[l] = t;
          this.notify();
        });
    }
  },

  t(language, key, vars = {}) {
    const lang = (language || "en").split("-")[0];
    let text = this.texts[lang]?.[key] ?? this.texts.en?.[key] ?? "";
    for (const [k, v] of Object.entries(vars)) {
      text = text.replaceAll(`{${k}}`, v);
    }
    return text;
  },
};

// ---------------------------------------------------------------- base card

const STYLE = `
:host { display: block; }
ha-card { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
h2 { margin: 0; font-size: 1.15em; font-weight: 500; display: flex; align-items: center; gap: 8px; }
.row { display: flex; align-items: center; gap: 10px; }
.grow { flex: 1; min-width: 0; }
.wrap { flex-wrap: wrap; }
.muted { color: var(--secondary-text-color); }
.small { font-size: 0.86em; }
.big { font-size: 1.6em; font-weight: 600; line-height: 1.1; }
.av { flex: none; border-radius: 50%; overflow: hidden; background: var(--c, var(--primary-color)); display: inline-flex; align-items: center; justify-content: center; }
.av img { width: 100%; height: 100%; object-fit: cover; }
.ic { flex: none; object-fit: contain; }
.stat { display: inline-flex; align-items: center; gap: 4px; font-weight: 600; }
.bar { height: 8px; border-radius: 4px; background: var(--divider-color, rgba(127,127,127,.25)); overflow: hidden; }
.bar > span { display: block; height: 100%; background: var(--c, var(--primary-color)); border-radius: 4px; }
.list { display: flex; flex-direction: column; gap: 8px; }
.item { display: flex; align-items: center; gap: 10px; padding: 8px; border-radius: 10px; background: var(--secondary-background-color, rgba(127,127,127,.08)); }
.item.done { opacity: 0.6; }
.item.off { opacity: 0.45; }
button { font: inherit; cursor: pointer; border: none; border-radius: 18px; padding: 6px 14px; background: var(--primary-color); color: var(--text-primary-color, #fff); }
button.flat { background: transparent; color: var(--primary-color); border: 1px solid var(--divider-color, rgba(127,127,127,.4)); }
button.ok { background: var(--success-color, #43a047); }
button.bad { background: var(--error-color, #db4437); }
button:disabled { opacity: 0.45; cursor: default; }
button.chip { padding: 2px 4px 2px 2px; display: inline-flex; align-items: center; gap: 6px; background: transparent; color: var(--primary-text-color); border: 2px solid transparent; }
button.chip.on { border-color: var(--primary-color); }
.check { width: 26px; height: 26px; border-radius: 50%; border: 2px solid var(--divider-color, rgba(127,127,127,.5)); display: inline-flex; align-items: center; justify-content: center; padding: 0; background: transparent; color: var(--primary-color); flex: none; }
.check.on { background: var(--success-color, #43a047); border-color: var(--success-color, #43a047); color: #fff; }
input, select { font: inherit; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--divider-color, rgba(127,127,127,.4)); background: var(--card-background-color); color: var(--primary-text-color); min-width: 0; }
.chart { display: flex; align-items: flex-end; gap: 6px; height: 110px; }
.chart .col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; height: 100%; justify-content: flex-end; }
.chart .pillar { width: 100%; max-width: 34px; border-radius: 6px 6px 2px 2px; background: var(--c, var(--primary-color)); min-height: 2px; }
.chart .pillar.none { background: var(--divider-color, rgba(127,127,127,.25)); }
.empty { color: var(--secondary-text-color); text-align: center; padding: 8px; }
.err { color: var(--error-color, #db4437); }
`;

class KsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._update = () => this._render();
    this._ui = {};
  }

  setConfig(config) {
    this._config = { ...(this.constructor.defaults || {}), ...config };
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first && this.isConnected) {
      store.attach(hass, this._update);
    }
    if (this.constructor.usesStates) {
      this._render();
    }
  }

  connectedCallback() {
    if (this._hass) {
      store.attach(this._hass, this._update);
    }
    this._render();
  }

  disconnectedCallback() {
    store.detach(this._update);
  }

  getCardSize() {
    return 3;
  }

  // Sections view: a sensible default size.
  getGridOptions() {
    return { columns: 6, min_columns: 3 };
  }

  t(key, vars) {
    return store.t(this._hass?.language, key, vars);
  }

  get data() {
    return store.data;
  }

  child(id) {
    return (this.data?.children || []).find((c) => c.id === id);
  }

  iconUrl(name) {
    if (!name) {
      return "";
    }
    if (name.startsWith("own_")) {
      const own = (this.data?.own_icons || []).find((i) => i.key === name);
      return own ? `/api/image/serve/${esc(own.image)}/256x256` : "";
    }
    name = store.aliases[name] || name;
    const base = this.data?.theme ? `${STATIC_URL}/themes/${esc(this.data.theme)}` : STATIC_URL;
    return `${base}/icons/${esc(name)}.png?v=${esc(this.data?.version || "")}`;
  }

  icon(name, size = 24) {
    const src = this.iconUrl(name);
    return src ? `<img class="ic" src="${src}" width="${size}" height="${size}" alt="">` : "";
  }

  avatar(c, size = 36) {
    const src = c.avatar_image ? `/api/image/serve/${esc(c.avatar_image)}/256x256` : this.iconUrl(c.avatar || "avatar_00");
    return `<span class="av" style="--c:${esc(c.color || "")};width:${size}px;height:${size}px" title="${esc(c.name)}"><img src="${src}" alt=""></span>`;
  }

  coins(n, size = 22) {
    return `<span class="stat">${this.icon("token_coin_front", size)}${esc(n)}</span>`;
  }

  // Renders the card; ``body()`` returns its inner HTML.
  _render() {
    if (!this._config) {
      return;
    }
    let inner;
    if (store.error && !this.data) {
      inner = `<div class="err">${esc(store.error)}</div>`;
    } else if (!this.data) {
      inner = `<div class="empty">\u2026</div>`;
    } else {
      inner = this.body();
    }
    const title = this._config.title ?? this.defaultTitle();
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>${title ? `<h2>${esc(title)}</h2>` : ""}${inner}</ha-card>`;
    this.shadowRoot.querySelectorAll("[data-act]").forEach((el) => {
      const handler = () => this.act(el.dataset.act, el.dataset, el);
      el.addEventListener(el.tagName === "SELECT" || el.tagName === "INPUT" ? "change" : "click", handler);
    });
  }

  defaultTitle() {
    return "";
  }

  // A child chosen in the config that no longer exists.
  missingChild() {
    return `<div class="empty">${esc(this.t("cards.choose_child"))}</div>`;
  }

  act() {}

  async call(msg) {
    try {
      await this._hass.callWS(msg);
      await store.reload();
      return true;
    } catch (err) {
      const code = err?.code ? this.t(`error.${err.code}`) : "";
      window.alert(code || err?.message || String(err));
      return false;
    }
  }

  static getConfigElement() {
    const editor = document.createElement("kis-segito-cards-editor");
    editor.schema = this.schema || [];
    return editor;
  }

  static getStubConfig() {
    const first = store.data?.children?.[0]?.id;
    const config = { ...(this.defaults || {}) };
    if ((this.schema || []).some((f) => f.name === "child" && f.required)) {
      config.child = first || "";
    }
    if ((this.schema || []).some((f) => f.name === "knob")) {
      config.knob = store.data?.knobs?.[0]?.device_id || "";
    }
    return config;
  }
}

// ---------------------------------------------------------------- 1. child

class ChildCard extends KsCard {
  static defaults = { show: ["wallet", "piggy", "streak", "today"] };
  static schema = [{ name: "child", required: true }, { name: "show", type: "show", options: ["wallet", "piggy", "streak", "today"] }, { name: "title" }];

  body() {
    const c = this.child(this._config.child);
    if (!c) {
      return this.missingChild();
    }
    const s = c.status;
    const show = new Set(this._config.show || []);
    const stats = [];
    if (show.has("wallet")) {
      stats.push(`<div><div class="muted small">${esc(this.t("tokens.wallet"))}</div>${this.coins(s.wallet, 26)}</div>`);
    }
    if (show.has("piggy") && s.piggy_unlocked) {
      stats.push(`<div><div class="muted small">${esc(this.t("tokens.piggy"))}</div><span class="stat">${this.icon("fn_piggy", 26)}${esc(s.piggy)}</span></div>`);
    }
    if (show.has("streak")) {
      stats.push(`<div><div class="muted small">${esc(this.t("cards.show_streak"))}</div><span class="stat">${this.icon("streak_flame", 24)}${esc(s.streak)}/${esc(s.streak_target)}</span></div>`);
    }
    let today = "";
    if (show.has("today")) {
      today = c.today.length
        ? `<div class="list">${c.today
            .map((r) => {
              const pct = r.tasks.length ? Math.round((r.done * 100) / r.tasks.length) : 100;
              return `<div class="row">${this.icon(r.icon, 28)}<div class="grow"><div class="row"><span class="grow">${esc(r.name)}</span><span class="muted small">${r.done}/${r.tasks.length}</span></div><div class="bar" style="--c:${esc(c.color || "")}"><span style="width:${pct}%"></span></div></div></div>`;
            })
            .join("")}</div>`
        : `<div class="muted small">${esc(this.t("cards.no_routines"))}</div>`;
    }
    return `<div class="row">${this.avatar(c, 56)}<div class="grow"><div class="big">${esc(c.name)}</div><div class="muted small">${esc(this.statusLine(s))}</div></div></div>
      ${stats.length ? `<div class="row wrap" style="gap:24px">${stats.join("")}</div>` : ""}${today}`;
  }

  statusLine(s) {
    if (s.task_status === "task") {
      return this.t("cards.now_task", { routine: s.current_routine, task: s.current_task });
    }
    if (s.task_status === "done") {
      return this.t("cards.now_done", { routine: s.current_routine });
    }
    return this.t("cards.now_none");
  }
}

// ---------------------------------------------------------------- 2. routine

class RoutineCard extends KsCard {
  static defaults = { status_only: false };
  static schema = [{ name: "child", required: true }, { name: "status_only", type: "boolean" }, { name: "title" }];

  defaultTitle() {
    return this.t("cards.routine_title");
  }

  body() {
    const c = this.child(this._config.child);
    if (!c) {
      return this.missingChild();
    }
    if (!c.today.length) {
      return `<div class="row">${this.avatar(c)}<span class="muted">${esc(this.t("cards.no_routines"))}</span></div>`;
    }
    const readonly = this._config.status_only;
    return `<div class="row">${this.avatar(c)}<b>${esc(c.name)}</b></div>${c.today
      .map(
        (r) => `<div class="list"><div class="row">${this.icon(r.icon, 28)}<b class="grow">${esc(r.name)}</b><span class="muted small">${esc(r.start || "")}\u2013${esc(r.end || "")} \u00b7 ${r.done}/${r.tasks.length}</span></div>
          ${r.tasks
            .map(
              (t) => `<div class="item ${t.done ? "done" : ""}">${this.icon(t.icon, 32)}<span class="grow">${esc(t.label)}</span>${
                readonly
                  ? `<span class="check ${t.done ? "on" : ""}">${t.done ? "\u2713" : ""}</span>`
                  : `<button class="check ${t.done ? "on" : ""}" ${t.done ? "disabled" : ""} data-act="tick" data-routine="${esc(r.id)}" data-task="${esc(t.id)}" title="${esc(this.t("cards.tick"))}">${t.done ? "\u2713" : ""}</button>`
              }</div>`,
            )
            .join("")}
          ${r.checkpoints.map((cp) => `<div class="row small muted">${this.icon("checkpoint_flag", 18)}<span class="grow">${esc(cp.name)} ${esc(cp.time || r.end || "")}</span>${cp.reached ? "\u2713" : ""}</div>`).join("")}</div>`,
      )
      .join("")}`;
  }

  act(action, ds) {
    if (action === "tick" && window.confirm(this.t("cards.tick_confirm"))) {
      this.call({ type: "kis_segito/cards/task", child_id: this._config.child, routine_id: ds.routine, task_id: ds.task });
    }
  }
}

// ---------------------------------------------------------------- 3. shop

class ShopCard extends KsCard {
  static schema = [{ name: "child" }, { name: "title" }];

  defaultTitle() {
    return this.t("cards.shop_title");
  }

  // Whether a child can get a reward now.
  canBuy(c, r) {
    if (r.kind === "piggy_unlock" && c.status.piggy_unlocked) {
      return false;
    }
    return c.status.wallet >= r.cost;
  }

  body() {
    const rewards = this.data.rewards;
    if (!rewards.length) {
      return `<div class="empty">${esc(this.t("cards.no_rewards"))}</div>`;
    }
    const fixed = this._config.child ? this.child(this._config.child) : null;
    if (this._config.child && !fixed) {
      return this.missingChild();
    }
    if (fixed) {
      return `<div class="row">${this.avatar(fixed)}<b class="grow">${esc(fixed.name)}</b>${this.coins(fixed.status.wallet)}</div><div class="list">${rewards
        .filter((r) => !(r.kind === "piggy_unlock" && fixed.status.piggy_unlocked))
        .map((r) => {
          const ok = this.canBuy(fixed, r);
          return `<div class="item ${ok ? "" : "off"}">${this.icon(r.icon, 36)}<span class="grow">${esc(r.name)}</span>${this.coins(r.cost, 18)}<button ${ok ? "" : "disabled"} data-act="redeem" data-child="${esc(fixed.id)}" data-reward="${esc(r.id)}">${esc(this.t("cards.redeem"))}</button></div>`;
        })
        .join("")}</div>`;
    }
    const children = this.data.children;
    return `<div class="list">${rewards
      .map((r) => {
        const able = children.filter((c) => this.canBuy(c, r));
        const sel = this._ui[r.id];
        const valid = able.some((c) => c.id === sel);
        return `<div class="item ${able.length ? "" : "off"}" style="flex-wrap:wrap">${this.icon(r.icon, 36)}<span class="grow">${esc(r.name)}</span>${this.coins(r.cost, 18)}
          <div class="row wrap" style="width:100%;gap:4px">${able.length ? able.map((c) => `<button class="chip ${c.id === sel ? "on" : ""}" data-act="pick" data-reward="${esc(r.id)}" data-child="${esc(c.id)}">${this.avatar(c, 28)}<span class="small">${esc(c.name)}</span></button>`).join("") : `<span class="muted small">${esc(this.t("cards.nobody_affords"))}</span>`}
          ${able.length ? `<span class="grow"></span><button ${valid ? "" : "disabled"} data-act="redeem" data-child="${esc(sel || "")}" data-reward="${esc(r.id)}" title="${esc(valid ? "" : this.t("cards.pick_child"))}">${esc(this.t("cards.redeem"))}</button>` : ""}</div></div>`;
      })
      .join("")}</div>`;
  }

  act(action, ds) {
    if (action === "pick") {
      this._ui[ds.reward] = this._ui[ds.reward] === ds.child ? "" : ds.child;
      this._render();
      return;
    }
    if (action === "redeem" && ds.child) {
      const c = this.child(ds.child);
      const r = this.data.rewards.find((x) => x.id === ds.reward);
      if (c && r && window.confirm(this.t("cards.redeem_confirm", { reward: r.name, child: c.name, n: r.cost }))) {
        this._ui[ds.reward] = "";
        this.call({ type: "kis_segito/cards/redeem", child_id: c.id, reward_id: r.id });
      }
    }
  }
}

// ---------------------------------------------------------------- 4. approvals

class ApprovalsCard extends KsCard {
  static schema = [{ name: "title" }];

  defaultTitle() {
    return this.t("cards.approvals_title");
  }

  body() {
    const items = this.data.approvals;
    if (!items.length) {
      return `<div class="empty">${esc(this.t("cards.no_approvals"))}</div>`;
    }
    return `<div class="list">${items
      .map((a) => {
        const c = this.child(a.child_id) || { name: "?" };
        const what = a.kind === "reward" ? a.reward_name : `${a.routine_name}: ${(a.task_names || []).join(", ")}`;
        const amount = a.kind === "reward" ? `\u2212${a.amount}` : a.amount ? `+${a.amount}` : "";
        return `<div class="item">${this.avatar(c, 32)}${this.icon(a.icon, 32)}<div class="grow"><div>${esc(what)}</div><div class="muted small">${esc(c.name)} \u00b7 ${esc(this.t(a.kind === "reward" ? "cards.kind_reward" : "cards.kind_task"))}${amount ? ` \u00b7 ${esc(amount)}` : ""}</div></div>
          <button class="ok" data-act="resolve" data-id="${esc(a.id)}" data-ok="1" title="${esc(this.t("cards.approve"))}">\u2713</button><button class="bad" data-act="resolve" data-id="${esc(a.id)}" data-ok="" title="${esc(this.t("cards.reject"))}">\u2715</button></div>`;
      })
      .join("")}</div>`;
  }

  act(action, ds) {
    if (action === "resolve") {
      this.call({ type: "kis_segito/approval/resolve", approval_id: ds.id, approve: Boolean(ds.ok) });
    }
  }
}

// ---------------------------------------------------------------- 5. week

class WeekCard extends KsCard {
  static schema = [{ name: "child", required: true }, { name: "title" }];

  defaultTitle() {
    return this.t("cards.week_title");
  }

  body() {
    const c = this.child(this._config.child);
    if (!c) {
      return this.missingChild();
    }
    const w = c.week;
    const lang = this._hass?.language || "en";
    const day = (d) => new Date(`${d}T12:00:00`).toLocaleDateString(lang, { weekday: "short" });
    return `<div class="row">${this.avatar(c)}<b class="grow">${esc(c.name)}</b><span class="stat">${this.icon("streak_flame", 22)}${esc(c.status.streak)}/${esc(c.status.streak_target)}</span><span class="big">${w.percent ?? "\u2014"}${w.percent !== null ? "%" : ""}</span></div>
      <div class="chart" style="--c:${esc(c.color || "")}">${w.days
        .map((d) => `<div class="col" title="${esc(d.done)}/${esc(d.total)}"><span class="small">${d.percent ?? ""}${d.percent !== null ? "%" : ""}</span><div class="pillar ${d.percent === null ? "none" : ""}" style="height:${d.percent ?? 0}%"></div><span class="muted small">${esc(day(d.date))}</span></div>`)
        .join("")}</div>
      <div class="list">${w.routines
        .map((r) => `<div class="row">${this.icon(r.icon, 24)}<span class="grow">${esc(r.name)}</span><span class="small">${r.percent ?? "\u2014"}${r.percent !== null ? "%" : ""}</span></div><div class="bar" style="--c:${esc(c.color || "")}"><span style="width:${r.percent || 0}%"></span></div>`)
        .join("")}</div>`;
  }
}

// ---------------------------------------------------------------- 6. quick +/−

class TokensCard extends KsCard {
  static defaults = { step: 1 };
  static schema = [{ name: "child", required: true }, { name: "step", type: "number" }, { name: "title" }];

  body() {
    const c = this.child(this._config.child);
    if (!c) {
      return this.missingChild();
    }
    const amount = this._ui.amount ?? (Number(this._config.step) || 1);
    return `<div class="row">${this.avatar(c, 44)}<b class="grow">${esc(c.name)}</b>${this.coins(c.status.wallet, 26)}</div>
      <div class="row"><input type="number" min="1" value="${esc(amount)}" data-act="amount" style="width:80px"><input class="grow" placeholder="${esc(this.t("cards.note"))}" value="${esc(this._ui.note || "")}" data-act="note">
      <button class="bad" data-act="adjust" data-sign="-1">\u2212</button><button class="ok" data-act="adjust" data-sign="1">+</button></div>`;
  }

  act(action, ds, el) {
    if (action === "amount") {
      this._ui.amount = Math.max(1, parseInt(el.value, 10) || 1);
    } else if (action === "note") {
      this._ui.note = el.value;
    } else if (action === "adjust") {
      const root = this.shadowRoot;
      const amount = Math.max(1, parseInt(root.querySelector('[data-act="amount"]').value, 10) || 1);
      const note = root.querySelector('[data-act="note"]').value.trim();
      const signed = amount * Number(ds.sign);
      const c = this.child(this._config.child);
      if (window.confirm(this.t("cards.adjust_confirm", { n: signed > 0 ? `+${signed}` : signed, child: c?.name || "" }))) {
        this._ui = {};
        this.call({ type: "kis_segito/tokens/adjust", child_id: this._config.child, amount: signed, note });
      }
    }
  }
}

// ---------------------------------------------------------------- 7. event log

class LogCard extends KsCard {
  static defaults = { count: 10 };
  static schema = [{ name: "count", type: "number" }, { name: "child" }, { name: "title" }];

  defaultTitle() {
    return this.t("cards.log_title");
  }

  _render() {
    const key = `${store.generation}|${this._config?.count}|${this._config?.child}`;
    if (this.data && this._hass && key !== this._loadedKey) {
      this._loadedKey = key;
      const n = Math.max(1, Math.min(200, Number(this._config.count) || 10));
      const child = this._config.child || null;
      Promise.all([
        this._hass.callWS({ type: "kis_segito/events", limit: n, child_id: child }),
        this._hass.callWS({ type: "kis_segito/history", limit: n, child_id: child }),
      ])
        .then(([events, txs]) => {
          this._rows = [
            // A checkpoint that paid tokens is in the token history already.
            ...events.filter((e) => !(e.type === "checkpoint_done" && e.tokens > 0)).map((e) => ({ at: e.timestamp, child: e.child_id, icon: e.icon, text: this.eventText(e), amount: null })),
            ...txs.map((tx) => ({ at: tx.timestamp, child: tx.child_id, icon: tx.reason === "reward_redemption" ? "fn_rewards" : "token_coin_front", text: this.txText(tx), amount: (tx.effective_lines || tx.lines).reduce((sum, l) => sum + l.amount, 0) })),
          ]
            .sort((a, b) => (a.at < b.at ? 1 : -1))
            .slice(0, n);
          this._err = null;
          super._render();
        })
        .catch((err) => {
          this._rows = null;
          this._err = err?.message || String(err);
          super._render();
        });
    }
    super._render();
  }

  eventText(e) {
    const type = this.t(`reason.${e.type}`) || e.type;
    const name = e.task_name || e.checkpoint_name || e.name || "";
    return `${type}${name ? `: ${name}` : ""}${e.by ? ` (${e.by})` : ""}`;
  }

  txText(tx) {
    const reason = this.t(`reason.${tx.reason}`) || tx.reason;
    const what = tx.refs?.reward_name || tx.refs?.checkpoint_name || tx.note || "";
    return `${reason}${what ? `: ${what}` : ""}${tx.creator && !["child", "device", "system"].includes(tx.creator) ? ` (${tx.creator})` : ""}`;
  }

  body() {
    if (this._err && !this._rows) {
      return `<div class="err">${esc(this._err)}</div>`;
    }
    if (!this._rows) {
      return `<div class="empty">\u2026</div>`;
    }
    if (!this._rows.length) {
      return `<div class="empty">${esc(this.t("cards.no_events"))}</div>`;
    }
    const lang = this._hass?.language || "en";
    return `<div class="list">${this._rows
      .map((r) => {
        const c = this.child(r.child) || { name: "?" };
        const when = new Date(r.at).toLocaleString(lang, { weekday: "short", hour: "2-digit", minute: "2-digit" });
        return `<div class="row small">${this.avatar(c, 26)}${this.icon(r.icon, 22)}<span class="grow">${esc(r.text)}</span>${r.amount ? `<b>${r.amount > 0 ? "+" : ""}${esc(r.amount)}</b>` : ""}<span class="muted">${esc(when)}</span></div>`;
      })
      .join("")}</div>`;
  }
}

// ---------------------------------------------------------------- 8. knob status

class KnobCard extends KsCard {
  static usesStates = true;
  static schema = [{ name: "knob" }, { name: "title" }];

  defaultTitle() {
    return this.t("cards.knobs_title");
  }

  state(id) {
    return id ? this._hass?.states?.[id] : undefined;
  }

  body() {
    const knobs = this.data.knobs.filter((k) => !this._config.knob || k.device_id === this._config.knob);
    if (!knobs.length) {
      return `<div class="empty">${esc(this.t("cards.no_knobs"))}</div>`;
    }
    const value = (id, unit = "") => {
      const s = this.state(id);
      if (!s || ["unknown", "unavailable"].includes(s.state)) {
        return "\u2014";
      }
      return `${s.state}${unit || s.attributes?.unit_of_measurement ? ` ${unit || s.attributes.unit_of_measurement}` : ""}`;
    };
    const on = (id) => this.state(id)?.state === "on";
    return knobs
      .map((k) => {
        const e = k.entities;
        const presence = this.state(e.presence);
        return `<div class="list"><div class="row"><b class="grow">${esc(k.name)}</b><span class="muted small">${esc(k.sw_version || "")}</span></div>
          <div class="row wrap small" style="gap:16px">
            <span>${esc(this.t("cards.brightness"))}: <b>${esc(value(e.brightness))}</b></span>
            <span>${esc(this.t("cards.illuminance"))}: <b>${esc(value(e.illuminance))}</b></span>
            <span>${esc(this.t("cards.presence"))}: <b>${esc(!presence || ["unknown", "unavailable"].includes(presence.state) ? "\u2014" : this.t(presence.state === "on" ? "cards.present" : "cards.absent"))}</b></span></div>
          <div class="row wrap"><button class="flat" data-act="knob" data-id="${esc(k.device_id)}" data-a="wake">${esc(this.t("cards.wake"))}</button>
            <button class="${on(e.screensaver) ? "" : "flat"}" data-act="knob" data-id="${esc(k.device_id)}" data-a="screensaver" data-on="${on(e.screensaver) ? "" : "1"}">${esc(this.t("cards.screensaver"))}</button>
            <button class="${on(e.night_light) ? "" : "flat"}" data-act="knob" data-id="${esc(k.device_id)}" data-a="night_light" data-on="${on(e.night_light) ? "" : "1"}">${esc(this.t("cards.night_light"))}</button></div></div>`;
      })
      .join("");
  }

  act(action, ds) {
    if (action === "knob") {
      this.call({ type: "kis_segito/cards/knob", device_id: ds.id, action: ds.a, enable: ds.a === "wake" || Boolean(ds.on) });
    }
  }
}

// ---------------------------------------------------------------- 9. mini

class MiniCard extends KsCard {
  static schema = [{ name: "title" }];

  getCardSize() {
    return 1 + (this.data?.children?.length || 1);
  }

  body() {
    const children = this.data.children;
    if (!children.length) {
      return `<div class="empty">${esc(this.t("today.no_children"))}</div>`;
    }
    return `<div class="list">${children
      .map((c) => {
        const all = c.today.reduce((s, r) => s + r.tasks.length, 0);
        const done = c.today.reduce((s, r) => s + r.done, 0);
        const pct = all ? Math.round((done * 100) / all) : 0;
        return `<div class="row">${this.avatar(c, 32)}<div class="grow"><div class="row small"><span class="grow">${esc(c.name)}</span><span class="muted">${all ? `${done}/${all}` : ""}</span></div><div class="bar" style="--c:${esc(c.color || "")}"><span style="width:${pct}%"></span></div></div>${this.coins(c.status.wallet)}</div>`;
      })
      .join("")}</div>`;
  }
}

// ---------------------------------------------------------------- editor

// One editor for every card, built from the card's ``schema`` with Home
// Assistant's own form (themed like the other card editors).
class CardsEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._attached) {
      this._attached = true;
      this._listener = () => this._render();
      store.attach(hass, this._listener);
    }
    this._render();
  }

  disconnectedCallback() {
    if (this._listener) {
      store.detach(this._listener);
      this._attached = false;
    }
  }

  t(key) {
    return store.t(this._hass?.language, key);
  }

  _schema() {
    const children = (store.data?.children || []).map((c) => ({ value: c.id, label: c.name }));
    const knobs = (store.data?.knobs || []).map((k) => ({ value: k.device_id, label: k.name }));
    return (this.schema || []).map((f) => {
      if (f.name === "child") {
        const options = f.required ? children : [{ value: "", label: this.t("cards.all_children") }, ...children];
        return { name: "child", required: Boolean(f.required), selector: { select: { mode: "dropdown", options } } };
      }
      if (f.name === "knob") {
        return { name: "knob", selector: { select: { mode: "dropdown", options: [{ value: "", label: this.t("cards.all_knobs") }, ...knobs] } } };
      }
      if (f.type === "show") {
        return { name: f.name, selector: { select: { multiple: true, mode: "list", options: f.options.map((o) => ({ value: o, label: this.t(`cards.show_${o}`) })) } } };
      }
      if (f.type === "boolean") {
        return { name: f.name, selector: { boolean: {} } };
      }
      if (f.type === "number") {
        return { name: f.name, selector: { number: { min: 1, max: f.name === "count" ? 200 : 1000, mode: "box" } } };
      }
      return { name: f.name, selector: { text: {} } };
    });
  }

  _render() {
    if (!this._hass || !this._config) {
      return;
    }
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => this.t(`cards.field_${s.name}`) || s.name;
      this._form.addEventListener("value-changed", (ev) => {
        const config = { ...ev.detail.value };
        for (const key of ["child", "knob", "title"]) {
          if (config[key] === "") {
            delete config[key];
          }
        }
        this._config = config;
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = this._schema();
    this._form.data = this._config;
  }
}

// ---------------------------------------------------------------- registration

const CARDS = [
  ["kis-segito-child-card", ChildCard, "Child", "Gyerek"],
  ["kis-segito-routine-card", RoutineCard, "Today's routine", "Mai rutin"],
  ["kis-segito-shop-card", ShopCard, "Reward shop", "Jutalombolt"],
  ["kis-segito-approvals-card", ApprovalsCard, "Approvals", "J\u00f3v\u00e1hagy\u00e1sok"],
  ["kis-segito-week-card", WeekCard, "Weekly statistics", "Heti statisztika"],
  ["kis-segito-tokens-card", TokensCard, "Quick +/\u2212", "Gyors +/\u2212"],
  ["kis-segito-log-card", LogCard, "Event log", "Esem\u00e9nynapl\u00f3"],
  ["kis-segito-knob-status-card", KnobCard, "Knob status", "Gomb \u00e1llapota"],
  ["kis-segito-mini-card", MiniCard, "Children at a glance", "Gyerekek r\u00f6viden"],
];

// Like the virtual knob card: defined once the frontend's root element
// exists, when the custom element registry is final.
const register = () => {
  const registry = window.customElements;
  for (const [tag, cls] of CARDS) {
    if (!registry.get(tag)) {
      registry.define(tag, class extends cls {});
    }
  }
  if (!registry.get("kis-segito-cards-editor")) {
    registry.define("kis-segito-cards-editor", CardsEditor);
  }
};
const frontendReady = () => Boolean(window.customElements.get("home-assistant"));
if (frontendReady()) {
  register();
} else {
  window.customElements.whenDefined("home-assistant").then(register);
  const timer = setInterval(() => {
    if (frontendReady()) {
      clearInterval(timer);
      register();
    }
  }, 250);
  setTimeout(() => clearInterval(timer), 120000);
}
window.customCards = window.customCards || [];
for (const [tag, , en, hu] of CARDS) {
  if (!window.customCards.some((c) => c.type === tag)) {
    window.customCards.push({ type: tag, name: `Kis Seg\u00edt\u0151: ${en}`, description: `${en} / ${hu}`, preview: true });
  }
}
