// SPDX-License-Identifier: AGPL-3.0-only
//
// Kis Segítő virtual knob: the knob's round screen as a dashboard card, for
// use without the physical knob. It shows the same screens, pictures and
// animations as the knob firmware (esphome/components/kis_segito_ui) from the
// same data snapshot (docs/protocol.md), and sends the same actions. Touch:
// swipe left/right = turn the knob, tap = press, press and hold = long press
// (back). A mouse wheel and the arrow, Enter and Escape keys work too.

// Geometry of the 480 px knob screen (the card scales it to its width).
const SCREEN = 480;
const CENTER = SCREEN / 2;
const WIN_X = 44;
const WIN_END = 436;
const OUTER_R = 222;
const OUTER_W = 14;
const OUTER_MID = OUTER_R - OUTER_W / 2;
const INNER_R = 203;
const INNER_W = 6;
const INNER_MID = INNER_R - INNER_W / 2;
const BAND_R = 196;
const FADE_W = 6;
const GLOW_W = INNER_W;

// Colours; a theme replaces them (state "tc", see applyThemeColours).
let BASE_BG = 0x1b2140;
let TRACK_DIM = 0x3a4066;
const LOCKED = 0x4a4f6a;
const GREY = 0x8c96a5;
let ZONE_DEPOSIT = 0x6bcb77;
let ZONE_WITHDRAW = 0xff9f43;
const BUILTIN_COLOURS = { bg: 0x1b2140, track: 0x3a4066, deposit: 0x6bcb77, withdraw: 0xff9f43, pill: 0x0f1330, number: 0xffe08a };
// The theme's knob colours ("#RRGGBB"); missing ones are the built-in ones.
const applyThemeColours = (tc, root) => {
  const c = (name) => parseColor(tc?.[name], BUILTIN_COLOURS[name]);
  BASE_BG = c("bg");
  TRACK_DIM = c("track");
  ZONE_DEPOSIT = c("deposit");
  ZONE_WITHDRAW = c("withdraw");
  root.style.setProperty("--pill", hex(c("pill")));
  root.style.setProperty("--num", hex(c("number")));
};
const CONFETTI_COLORS = [0xff6b6b, 0xffc94a, 0x6bcb77, 0x6cb8ff, 0xa78bfa, 0xff8fb1];

const SCREENS = { CHILDREN: "children", FUNCTIONS: "functions", REWARDS: "rewards", CONFIRM: "confirm", ROUTINE: "routine", TOKENS: "tokens", PIGGY: "piggy" };
const FN = { ROUTINE: 0, REWARDS: 1, PIGGY: 2, TOKENS: 3 };

// ---------------------------------------------------------------- helpers

const hex = (c) => `#${(c & 0xffffff).toString(16).padStart(6, "0")}`;
const parseColor = (text, fallback) => (/^#[0-9a-fA-F]{6}$/.test(text || "") ? parseInt(text.slice(1), 16) : fallback);
// LVGL's lv_color_mix: `mix`/255 of a over b.
const mix = (a, b, m) => {
  const ch = (s) => Math.round((((a >> s) & 255) * m + ((b >> s) & 255) * (255 - m)) / 255);
  return (ch(16) << 16) | (ch(8) << 8) | ch(0);
};
// The knob's pseudo-random numbers (token pile jitter).
const hash32 = (x) => {
  x = x >>> 0;
  x ^= x >>> 16;
  x = Math.imul(x, 0x7feb352d) >>> 0;
  x ^= x >>> 15;
  x = Math.imul(x, 0x846ca68b) >>> 0;
  x ^= x >>> 16;
  return x >>> 0;
};
const applies = (children, childId) => !children || !children.length || children.includes(childId);
const rewardFor = (bands, early) => {
  let best = 0;
  let threshold = -Infinity;
  for (const [s, tokens] of bands || []) {
    if (early >= s && s > threshold) {
      best = Math.max(tokens, 0);
      threshold = s;
    }
  }
  return best;
};
// Track position p (0 = start at 11 o'clock, 1 = end at 1 o'clock, counter-
// clockwise the long way round) as a point at the given radius.
const angle = (p) => ((240 - 300 * p) * Math.PI) / 180;
const ringPoint = (p, r) => [CENTER + r * Math.cos(angle(p)), CENTER + r * Math.sin(angle(p))];
const arcPath = (r, p0, p1) => {
  if (p1 - p0 < 0.0005) {
    p1 = p0 + 0.0005;
  }
  const [x0, y0] = ringPoint(p0, r);
  const [x1, y1] = ringPoint(p1, r);
  const large = (p1 - p0) * 300 > 180 ? 1 : 0;
  return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${r} ${r} 0 ${large} 0 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
};
const newActionId = () => {
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
};

const STYLE = `
:host { display: block; }
ha-card { overflow: visible; background: none; border: none; box-shadow: none; }
.wrap { position: relative; width: 100%; aspect-ratio: 1; touch-action: none; user-select: none; -webkit-user-select: none; outline: none; }
.knob { position: absolute; left: 0; top: 0; width: 480px; height: 480px; transform-origin: 0 0; border-radius: 50%; overflow: hidden; background: #1b2140; }
.layer { position: absolute; inset: 0; }
.bg { background-size: cover; background-position: center; }
.band { -webkit-mask-image: radial-gradient(circle at center, transparent ${BAND_R - FADE_W}px, #000 ${BAND_R}px); mask-image: radial-gradient(circle at center, transparent ${BAND_R - FADE_W}px, #000 ${BAND_R}px); background-size: cover; background-position: center; pointer-events: none; }
.abs { position: absolute; }
.disc { position: absolute; border-radius: 50%; }
img.abs { pointer-events: none; -webkit-user-drag: none; }
.pill { position: absolute; height: 48px; border-radius: 24px; background: color-mix(in srgb, var(--pill, #0f1330) 78.4%, transparent); padding: 0 14px; display: flex; align-items: center; gap: 6px; transform: translateX(-50%); white-space: nowrap; }
.num { font-family: "KS Baloo 2", "Baloo 2", system-ui, sans-serif; font-weight: 800; font-size: 34px; line-height: 1; color: var(--num, #ffe08a); }
.window { position: absolute; overflow: hidden; }
.slot { position: absolute; top: 0; will-change: transform, opacity; }
.grey { filter: grayscale(1) brightness(0.85); }
.dim { filter: grayscale(1) brightness(0.85); opacity: 0.67; }
.back { position: absolute; right: 1%; bottom: 1%; width: 13%; aspect-ratio: 1; border-radius: 50%; border: 0; padding: 0; cursor: pointer; display: flex; align-items: center; justify-content: center; background: var(--card-background-color, var(--ha-card-background)); color: var(--primary-color); box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0, 0, 0, 0.2)); }
.back[hidden] { display: none; }
.back ha-icon { display: flex; }
.empty { padding: 24px; text-align: center; color: var(--secondary-text-color); }
`;

// ---------------------------------------------------------------- the card

class KisSegitoKnobCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._state = null;
    this._receivedAt = 0;
    this._screen = SCREENS.CHILDREN;
    this._child = 0;
    this._childId = "";
    this._function = 0;
    this._functionKey = "";
    this._functionChild = "";
    this._routineId = "";
    this._rewardId = "";
    this._confirmYes = false;
    this._piggyAmount = 0;
    this._busy = false;
    this._pendingRebuild = false;
    this._lastInput = Date.now();
    this._connected = true;
    this._aliases = {};
    this._shownReward = -1;
    this._ringMinute = -1;
  }

  static getConfigElement() {
    return document.createElement("kis-segito-knob-card-editor");
  }

  static getStubConfig() {
    return { knob: "" };
  }

  setConfig(config) {
    this._config = { back_button: false, ...config };
    if (this._backButton) {
      this._backButton.hidden = !this._config.back_button;
    }
    if (this._hass) {
      this._resubscribe();
    }
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, rows: "auto", min_columns: 4 };
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._build();
      this._resubscribe();
      hass.connection.addEventListener("ready", () => this._setConnected(true));
      hass.connection.addEventListener("disconnected", () => this._setConnected(false));
    }
  }

  connectedCallback() {
    if (this._hass && !this._unsub) {
      this._resubscribe();
    }
    if (!this._tick) {
      this._tick = setInterval(() => this._onTick(), 1000);
    }
  }

  disconnectedCallback() {
    clearInterval(this._tick);
    this._tick = null;
    this._unsubscribe();
  }

  // ------------------------------------------------------------ plumbing

  _unsubscribe() {
    if (this._unsub) {
      this._unsub.then((unsub) => unsub()).catch(() => {});
      this._unsub = null;
    }
  }

  _resubscribe() {
    this._unsubscribe();
    const knob = this._config?.knob;
    if (!knob) {
      this._showMessage("Choose a virtual knob in the card settings. / Válassz virtuális gombot a kártya beállításaiban.");
      return;
    }
    this._unsub = this._hass.connection.subscribeMessage((msg) => this._onMessage(msg), {
      type: "kis_segito/virtual/subscribe",
      device_id: knob,
    });
    this._unsub.catch(() => this._showMessage("This virtual knob does not exist (any more). / Ez a virtuális gomb nem létezik."));
  }

  _onMessage(msg) {
    if (msg.removed) {
      this._showMessage("This virtual knob was removed. / Ezt a virtuális gombot törölték.");
      return;
    }
    const first = !this._state;
    this._staticUrl = msg.static_url;
    this._version = msg.version;
    this._longPressMs = msg.long_press_ms || 500;
    this._state = msg.state;
    applyThemeColours(this._state?.tc, this);
    this._small = new Set(msg.small_icons || []);
    this._theme = msg.theme || null;
    this._ownIcons = msg.own_icons || {};
    this._receivedAt = Date.now();
    if (first) {
      this._loadFonts();
      fetch(`${this._staticUrl}/icons/aliases.json?v=${this._version}`)
        .then((r) => (r.ok ? r.json() : {}))
        .then((aliases) => {
          this._aliases = aliases || {};
          this._rebuild();
        })
        .catch(() => {});
    }
    this._applyState();
  }

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

  _showMessage(text) {
    if (!this._root) {
      this._build();
    }
    this._wrap.hidden = true;
    this._message.hidden = false;
    this._message.textContent = text;
  }

  _send(kind, extra) {
    const child = this._children[this._child];
    const action = { a: kind, id: newActionId(), c: child.id, ...extra };
    this._hass
      .callWS({ type: "kis_segito/virtual/action", device_id: this._config.knob, action: JSON.stringify(action) })
      .catch(() => {});
  }

  _setConnected(connected) {
    this._connected = connected;
    if (this._offline) {
      this._offline.style.display = connected ? "none" : "";
    }
  }

  // ------------------------------------------------------------ data

  get _children() {
    return this._state?.children || [];
  }

  get _rewards() {
    return this._state?.rewards || [];
  }

  get _routines() {
    return this._state?.routines || [];
  }

  _now() {
    return (this._state?.now || 0) + Math.floor((Date.now() - this._receivedAt) / 1000);
  }

  _animMs(full) {
    const mode = this._state?.anim || "full";
    return mode === "off" ? 0 : mode === "reduced" ? full / 2 : full;
  }

  _applyState() {
    this._wrap.hidden = false;
    this._message.hidden = true;
    // Keep the selected child, routine and reward by id.
    const index = this._children.findIndex((c) => c.id === this._childId);
    this._child = index >= 0 ? index : Math.min(this._child, Math.max(this._children.length - 1, 0));
    this._childId = this._children[this._child]?.id || "";
    if (this._busy) {
      this._pendingRebuild = true;
      return;
    }
    this._rebuild();
  }

  _rebuild() {
    if (this._state) {
      this._show(this._screen);
    }
  }

  _routine() {
    return this._routines.find((r) => r.id === this._routineId) || this._routines[0];
  }

  _isDone(routine, taskId) {
    return (routine.done?.[this._childId] || []).includes(taskId);
  }

  _cpDone(routine, cpId) {
    return (routine.cpd?.[this._childId] || []).includes(cpId);
  }

  _nextCheckpoint(routine) {
    let best = null;
    for (const cp of routine.cp || []) {
      if (!applies(cp.ch, this._childId) || this._cpDone(routine, cp.id)) {
        continue;
      }
      if (!best || cp.t < best.t) {
        best = cp;
      }
    }
    return best;
  }

  _shop() {
    const child = this._children[this._child];
    return this._rewards.filter((r) => !(r.k === "piggy_unlock" && child?.pu));
  }

  _functionsFor(child) {
    const now = this._now();
    const fns = [];
    this._routines.forEach((r, i) => {
      if (applies(r.ch, child.id) && now >= r.s && now < (r.m || r.e)) {
        fns.push({ type: FN.ROUTINE, routine: i });
      }
    });
    fns.push({ type: FN.REWARDS });
    if (child.pu) {
      fns.push({ type: FN.PIGGY });
    }
    fns.push({ type: FN.TOKENS });
    return fns;
  }

  _functionKeyOf(fn) {
    return fn.type === FN.ROUTINE ? `r:${this._routines[fn.routine].id}` : String(fn.type);
  }

  _trackRoutine() {
    if (!this._routines.length) {
      return null;
    }
    if (this._screen === SCREENS.ROUTINE) {
      return this._routine();
    }
    const now = this._now();
    let any = null;
    for (const r of this._routines) {
      if (now < r.s || now >= r.e) {
        continue;
      }
      if (applies(r.ch, this._childId)) {
        return r;
      }
      any = any || r;
    }
    return any;
  }

  // ------------------------------------------------------------ pictures

  _iconUrl(name, size) {
    // An own (uploaded) icon is a picture of Home Assistant's image upload.
    if (name && name.startsWith("own_")) {
      const image = this._ownIcons?.[name];
      return image ? `/api/image/serve/${encodeURIComponent(image)}/256x256` : "";
    }
    name = this._aliases[name] || name;
    // Small places use the simplified variant, when the icon has one.
    const small = size <= 44 && this._small?.has(name) ? "small/" : "";
    return this._asset(`icons/${small}${name}.png`);
  }

  // A picture of the chosen theme, or the built-in one (an own theme may
  // leave pictures out).
  _asset(path) {
    const theme = this._theme;
    if (theme?.base && (!theme.has || theme.has.includes(path))) {
      return `${theme.base}/${path}?v=${this._version}&r=${theme.rev || 0}`;
    }
    return `${this._staticUrl}/${path}?v=${this._version}`;
  }

  _img(parent, name, cx, cy, size, cls = "") {
    const img = document.createElement("img");
    img.className = `abs ${cls}`;
    img.width = size;
    img.height = size;
    img.style.left = `${cx - size / 2}px`;
    img.style.top = `${cy - size / 2}px`;
    img.alt = "";
    img.draggable = false;
    img.src = this._iconUrl(name, size);
    parent.appendChild(img);
    return img;
  }

  _picture(parent, id, cx, cy, size, cls = "") {
    const img = document.createElement("img");
    img.className = `abs ${cls}`;
    img.width = size;
    img.height = size;
    img.style.left = `${cx - size / 2}px`;
    img.style.top = `${cy - size / 2}px`;
    img.style.objectFit = "contain";
    img.alt = "";
    img.draggable = false;
    img.src = `/api/image/serve/${encodeURIComponent(id)}/256x256`;
    parent.appendChild(img);
    return img;
  }

  _avatar(parent, child, cx, cy, size, cls = "") {
    return child.ai ? this._picture(parent, child.ai, cx, cy, size, cls) : this._img(parent, child.a, cx, cy, size, cls);
  }

  _rewardIcon(parent, reward, cx, cy, size, cls = "") {
    return reward.ii ? this._picture(parent, reward.ii, cx, cy, size, cls) : this._img(parent, reward.i, cx, cy, size, cls);
  }

  _disc(parent, cx, cy, d, color) {
    const disc = document.createElement("div");
    disc.className = "disc";
    disc.style.cssText = `left:${cx - d / 2}px;top:${cy - d / 2}px;width:${d}px;height:${d}px;background:${hex(color)}`;
    parent.appendChild(disc);
    return disc;
  }

  _pill(parent, cx, cy, value) {
    const pill = document.createElement("div");
    pill.className = "pill";
    pill.style.left = `${cx}px`;
    pill.style.top = `${cy - 24}px`;
    const coin = document.createElement("img");
    coin.width = 28;
    coin.height = 28;
    coin.src = this._iconUrl("token_coin_front", 28);
    coin.draggable = false;
    const num = document.createElement("span");
    num.className = "num";
    num.textContent = String(value);
    pill.append(coin, num);
    parent.appendChild(pill);
    return pill;
  }

  _backgroundUrl() {
    const bg = this._state?.bg || "";
    if (!bg) {
      return "";
    }
    // A theme's preset: "t_<theme>__bg_<n>".
    const themed = /^t_([a-z0-9_]+?)__(bg_[1-6])$/.exec(bg);
    if (themed) {
      return this._asset(`backgrounds/${themed[2]}.jpg`);
    }
    return bg.startsWith("bg_") ? `${this._staticUrl}/backgrounds/${bg}.jpg?v=${this._version}` : `/api/image/serve/${encodeURIComponent(bg)}/512x512`;
  }

  // ------------------------------------------------------------ layout

  _build() {
    if (this._root) {
      return;
    }
    const root = this.shadowRoot;
    root.innerHTML = `<style>${STYLE}</style><ha-card><div class="wrap" tabindex="0"><div class="knob">
      <div class="layer bg"></div><div class="layer screen"></div><div class="layer band"></div>
      <svg class="layer ring" viewBox="0 0 480 480"></svg><div class="layer track"></div><div class="layer top"></div>
      </div><button class="back" hidden aria-label="Back"><ha-icon icon="mdi:arrow-u-left-bottom"></ha-icon></button></div><div class="empty" hidden></div></ha-card>`;
    this._root = root;
    this._wrap = root.querySelector(".wrap");
    this._knob = root.querySelector(".knob");
    this._bgLayer = root.querySelector(".bg");
    this._screenLayer = root.querySelector(".screen");
    this._band = root.querySelector(".band");
    this._ring = root.querySelector(".ring");
    this._trackLayer = root.querySelector(".track");
    this._topLayer = root.querySelector(".top");
    this._message = root.querySelector(".empty");
    this._wrap.hidden = true;
    this._backButton = root.querySelector(".back");
    this._backButton.addEventListener("click", () => this._input("long"));
    this._backButton.hidden = !this._config?.back_button;
    new ResizeObserver(() => this._scale()).observe(this._wrap);
    this._bindInput();
  }

  _scale() {
    const w = this._wrap.clientWidth;
    if (w > 0) {
      this._knob.style.transform = `scale(${w / SCREEN})`;
      this._backButton.style.setProperty("--mdc-icon-size", `${Math.round(w * 0.13 * 0.6)}px`);
    }
  }

  // ------------------------------------------------------------ input

  _bindInput() {
    const wrap = this._wrap;
    let start = null;
    let timer = null;
    let homeTimer = null;
    let longFired = false;
    const clear = () => {
      clearTimeout(timer);
      clearTimeout(homeTimer);
      timer = homeTimer = null;
    };
    wrap.addEventListener("pointerdown", (ev) => {
      if (ev.button > 0 || ev.target.closest(".back")) {
        return;
      }
      wrap.setPointerCapture(ev.pointerId);
      start = { x: ev.clientX, y: ev.clientY, t: performance.now() };
      longFired = false;
      // Held: a long press (back); held three times as long: home.
      timer = setTimeout(() => {
        longFired = true;
        this._input("long");
        homeTimer = setTimeout(() => this._input("home"), 2 * this._longPressMs);
      }, this._longPressMs || 500);
    });
    wrap.addEventListener("pointermove", (ev) => {
      if (start && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) > 12) {
        clear();
      }
    });
    const end = (ev, cancelled) => {
      if (!start) {
        return;
      }
      const dx = ev.clientX - start.x;
      const dy = ev.clientY - start.y;
      const dt = Math.max(performance.now() - start.t, 1);
      const scale = SCREEN / Math.max(wrap.clientWidth, 1);
      start = null;
      clear();
      if (cancelled || longFired) {
        return;
      }
      const dist = Math.abs(dx) * scale;
      if (dist >= 30 && Math.abs(dx) > Math.abs(dy)) {
        // One swipe is one step; a fast, long flick several.
        const speed = dist / dt;
        const steps = speed > 0.9 ? Math.min(6, 1 + Math.floor((dist - 30) / 110)) : 1;
        for (let i = 0; i < steps; i++) {
          this._input(dx < 0 ? 1 : -1);
        }
      } else if (Math.hypot(dx, dy) * scale < 20) {
        this._input("click");
      }
    };
    wrap.addEventListener("pointerup", (ev) => end(ev, false));
    wrap.addEventListener("pointercancel", (ev) => end(ev, true));
    wrap.addEventListener(
      "wheel",
      (ev) => {
        ev.preventDefault();
        const now = performance.now();
        if (now - (this._lastWheel || 0) < 120) {
          return;
        }
        this._lastWheel = now;
        this._input(ev.deltaY + ev.deltaX > 0 ? 1 : -1);
      },
      { passive: false },
    );
    wrap.addEventListener("keydown", (ev) => {
      const map = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1, Enter: "click", " ": "click", Escape: "long", Backspace: "long" };
      if (ev.key in map) {
        ev.preventDefault();
        this._input(map[ev.key]);
      }
    });
    wrap.addEventListener("contextmenu", (ev) => ev.preventDefault());
  }

  _input(what) {
    if (!this._state) {
      return;
    }
    this._lastInput = Date.now();
    if (what === "click") {
      this._click();
    } else if (what === "long") {
      this._longPress();
    } else if (what === "home") {
      if (this._screen !== SCREENS.CHILDREN) {
        this._show(SCREENS.CHILDREN);
      }
    } else {
      this._rotate(what);
    }
  }

  _onTick() {
    if (!this._state) {
      return;
    }
    if (this._pendingRebuild && !this._busy) {
      this._pendingRebuild = false;
      this._rebuild();
      return;
    }
    this._updateTrack();
    const idle = Math.max(10, this._state.idle || 60) * 1000;
    if (this._screen !== SCREENS.CHILDREN && !this._busy && Date.now() - this._lastInput > idle) {
      this._show(SCREENS.CHILDREN);
    }
  }

  // ------------------------------------------------------------ navigation

  _show(screen) {
    this._busy = false;
    this._pendingRebuild = false;
    this._carousel = null;
    this._screenLayer.replaceChildren();
    this._confirm = null;
    this._piggyLabel = null;
    this._taskBig = null;
    const previous = this._screen;
    this._screen = screen;
    const children = this._children;
    if (!children.length) {
      this._screen = SCREENS.CHILDREN;
      this._applyBackground(BASE_BG);
      this._buildTrack();
      return;
    }
    if ((screen === SCREENS.ROUTINE && !this._routines.length) || ((screen === SCREENS.REWARDS || screen === SCREENS.CONFIRM) && !this._shop().length)) {
      screen = this._screen = SCREENS.FUNCTIONS;
    }
    if (screen !== SCREENS.CHILDREN && !children[this._child].sel) {
      screen = this._screen = SCREENS.CHILDREN;
    }
    const child = children[this._child];
    this._applyBackground(screen === SCREENS.CHILDREN ? BASE_BG : mix(parseColor(child.c, 0x6cb8ff), BASE_BG, 46));
    this._buildTrack();
    if (screen === SCREENS.REWARDS && previous !== SCREENS.CONFIRM && previous !== SCREENS.REWARDS && this._shop().length) {
      this._rewardId = this._shop()[0].id;
    }
    const build = {
      [SCREENS.CHILDREN]: () => this._buildChildren(),
      [SCREENS.FUNCTIONS]: () => this._buildFunctions(),
      [SCREENS.REWARDS]: () => this._buildRewards(),
      [SCREENS.CONFIRM]: () => this._buildConfirm(),
      [SCREENS.ROUTINE]: () => this._buildRoutine(),
      [SCREENS.TOKENS]: () => this._buildTokens(),
      [SCREENS.PIGGY]: () => this._buildPiggy(),
    }[screen];
    build();
  }

  _applyBackground(color) {
    const url = this._backgroundUrl();
    for (const el of [this._bgLayer, this._band]) {
      el.style.backgroundColor = hex(color);
      el.style.backgroundImage = url ? `url("${url}")` : "";
    }
    this._knob.style.background = hex(color);
  }

  _rotate(dir) {
    if (this._busy || !this._children.length) {
      return;
    }
    const child = this._children[this._child];
    switch (this._screen) {
      case SCREENS.CHILDREN:
        this._carousel?.rotate(dir);
        this._selectChild(this._carousel?.selected ?? this._child);
        this._buildTrack();
        break;
      case SCREENS.FUNCTIONS: {
        this._carousel?.rotate(dir);
        this._function = this._carousel?.selected ?? 0;
        const fns = this._functionsFor(child);
        this._functionKey = this._functionKeyOf(fns[this._function % fns.length]);
        this._functionChild = child.id;
        break;
      }
      case SCREENS.REWARDS:
        this._carousel?.rotate(dir);
        this._rewardId = this._shop()[this._carousel?.selected ?? 0]?.id || "";
        break;
      case SCREENS.PIGGY:
        // Turning chooses how many tokens move: clockwise into the piggy bank
        // (up to the wallet), anticlockwise out of it (up to the piggy bank).
        this._piggyAmount = Math.max(-child.p, Math.min(child.w, this._piggyAmount + dir));
        this._updatePiggyAmount();
        break;
      case SCREENS.CONFIRM:
        this._confirmYes = !this._confirmYes;
        this._placeConfirmRing();
        break;
      default:
        break;
    }
  }

  _selectChild(index) {
    this._child = index;
    this._childId = this._children[index]?.id || "";
  }

  _click() {
    if (this._busy || !this._children.length) {
      return;
    }
    const child = this._children[this._child];
    switch (this._screen) {
      case SCREENS.CHILDREN:
        if (!child.sel) {
          this._shake(this._carousel?.centerSlot());
          return;
        }
        this._functionKey = "";
        this._show(SCREENS.FUNCTIONS);
        break;
      case SCREENS.FUNCTIONS: {
        const fns = this._functionsFor(child);
        const fn = fns[this._function % fns.length];
        if (fn.type === FN.ROUTINE) {
          this._routineId = this._routines[fn.routine].id;
          this._show(SCREENS.ROUTINE);
        } else if (fn.type === FN.REWARDS) {
          if (this._shop().length) {
            this._show(SCREENS.REWARDS);
          }
        } else if (fn.type === FN.PIGGY) {
          this._show(SCREENS.PIGGY);
        } else {
          this._show(SCREENS.TOKENS);
        }
        break;
      }
      case SCREENS.REWARDS: {
        const reward = this._shop().find((r) => r.id === this._rewardId);
        if (!reward || reward.c > child.w) {
          this._shake(this._carousel?.centerSlot());
          return;
        }
        this._confirmYes = false;
        this._show(SCREENS.CONFIRM);
        break;
      }
      case SCREENS.CONFIRM:
        this._redeem(child);
        break;
      case SCREENS.ROUTINE:
        if (!this._connected) {
          this._refuseOffline(this._taskBig);
          return;
        }
        this._completeTask(child);
        break;
      case SCREENS.PIGGY:
        this._piggyTransfer(child);
        break;
      default:
        break;
    }
  }

  _longPress() {
    switch (this._screen) {
      case SCREENS.CHILDREN:
        if (!this._connected) {
          this._refuseOffline(null);
        }
        break;
      case SCREENS.FUNCTIONS:
        this._show(SCREENS.CHILDREN);
        break;
      case SCREENS.CONFIRM:
        this._show(SCREENS.REWARDS);
        break;
      case SCREENS.REWARDS:
      case SCREENS.ROUTINE:
      case SCREENS.TOKENS:
      case SCREENS.PIGGY:
        this._show(SCREENS.FUNCTIONS);
        break;
      default:
        break;
    }
  }

  // ------------------------------------------------------------ effects

  _shake(el) {
    if (!el || !this._animMs(300)) {
      return;
    }
    el.animate(
      [{ translate: "0 0" }, { translate: "-10px 0" }, { translate: "10px 0" }, { translate: "-10px 0" }, { translate: "10px 0" }, { translate: "0 0" }],
      { duration: 300 },
    );
  }

  _refuseOffline(target) {
    // Token transactions need Home Assistant: a shake and a pulse of the
    // offline marker instead of acting on old data.
    if (this._offline && this._animMs(300)) {
      this._offline.animate([{ scale: 1 }, { scale: 1.64 }, { scale: 1 }, { scale: 1.64 }, { scale: 1 }], { duration: 640 });
    }
    this._shake(target);
  }

  _flyCoins(count, from, to, ease, spread, delayStep = 45, duration = 450, xFor = () => CENTER) {
    const flying = Math.min(count, 40);
    const ms = this._animMs(duration);
    for (let i = 0; i < flying && ms > 0; i++) {
      const coin = this._img(this._screenLayer, "token_coin_front", xFor(i), from, 28);
      const target = to + spread(i);
      coin.animate([{ transform: "translateY(0)" }, { transform: `translateY(${target - from}px)` }], {
        duration: ms,
        delay: i * delayStep,
        easing: ease,
        fill: "forwards",
      }).onfinish = () => coin.remove();
    }
    return ms ? ms + flying * delayStep + 300 : 300;
  }

  _celebrate(child, tokens) {
    child.w += tokens;
    if ((this._state.anim || "full") !== "full") {
      return;
    }
    for (let i = 0; i < 36; i++) {
      const h = hash32(i + 77);
      const piece = document.createElement("div");
      piece.className = "abs";
      piece.style.cssText = `left:${60 + (h % 360)}px;top:-20px;width:8px;height:14px;border-radius:2px;background:${hex(CONFETTI_COLORS[i % 6])}`;
      this._topLayer.appendChild(piece);
      piece.animate([{ transform: "translateY(0)" }, { transform: `translateY(${320 + ((h >>> 8) % 180)}px)` }], {
        duration: 1200,
        delay: (h >>> 16) % 400,
        easing: "ease-in",
        fill: "forwards",
      }).onfinish = () => piece.remove();
    }
  }

  _later(ms, fn) {
    this._busy = true;
    setTimeout(() => {
      this._busy = false;
      fn();
    }, ms);
  }

  // ------------------------------------------------------------ actions

  _redeem(child) {
    if (!this._confirmYes) {
      this._show(SCREENS.REWARDS);
      return;
    }
    if (!this._connected) {
      this._refuseOffline(this._confirm?.yes);
      return;
    }
    const reward = this._shop().find((r) => r.id === this._rewardId);
    if (!reward) {
      return;
    }
    // Shown at once; Home Assistant books it and sends the real balance.
    child.w -= reward.c;
    if (reward.k === "piggy_unlock") {
      child.pu = true;
    }
    this._send("redeem", { r: reward.id });
    const wait = this._flyCoins(reward.c, 420, 164, "ease-in", (i) => hash32(i) % 30);
    this._later(wait, () => this._show(SCREENS.REWARDS));
  }

  _piggyTransfer(child) {
    const amount = this._piggyAmount;
    if (amount === 0) {
      return;
    }
    if (!this._connected) {
      this._refuseOffline(this._piggyLabel);
      return;
    }
    child.w -= amount;
    child.p += amount;
    this._piggyAmount = 0;
    this._send("piggy", { n: amount });
    const from = amount > 0 ? 410 : 185;
    const to = amount > 0 ? 185 : 410;
    const wait = this._flyCoins(Math.abs(amount), from, to, "ease-in-out", (i) => (hash32(i) % 20) - 10);
    this._later(wait, () => this._show(SCREENS.PIGGY));
  }

  _completeTask(child) {
    const routine = this._routine();
    const task = (routine.t || []).find((t) => !this._isDone(routine, t.id));
    if (!task) {
      return;
    }
    // Shown at once; Home Assistant books it and sends the real state.
    routine.done = routine.done || {};
    (routine.done[child.id] = routine.done[child.id] || []).push(task.id);
    this._send("task", { r: routine.id, t: task.id });
    // The last task before its checkpoint reaches it, worth its reward now.
    let reward = 0;
    const cp = (routine.cp || []).find((c) => c.id === task.cp);
    if (cp && applies(cp.ch, child.id) && !this._cpDone(routine, cp.id)) {
      const all = (routine.t || []).every((t) => t.cp !== cp.id || this._isDone(routine, t.id));
      if (all) {
        reward = rewardFor(cp.b, cp.t - this._now());
        routine.cpd = routine.cpd || {};
        (routine.cpd[child.id] = routine.cpd[child.id] || []).push(cp.id);
      }
    }
    const ms = this._animMs(420);
    if (ms && this._taskBig) {
      this._taskBig.animate([{ scale: 1 }, { scale: 1.17 }, { scale: 1 }], { duration: (ms * 2) / 3 });
    }
    this._img(this._screenLayer, "action_check", CENTER, 205, 88);
    this._later(ms + 250, () => this._show(SCREENS.ROUTINE));
    if (reward > 0) {
      this._celebrate(child, reward);
    }
  }

  // ------------------------------------------------------------ screens

  _buildChildren() {
    const children = this._children;
    this._carousel = new Carousel(this, this._screenLayer, children.length, this._child, 300, 280, 60, 250, this._animMs(260), (slot, index) => {
      const c = children[index];
      const cx = 150;
      // Children of another knob: visible but greyed and locked here.
      this._disc(slot, cx, 105, 190, c.sel ? parseColor(c.c, 0x6cb8ff) : LOCKED);
      this._avatar(slot, c, cx, 105, 180, c.sel ? "" : "grey");
      this._pill(slot, cx, 236, c.w);
      if (c.pi > 0 && c.pu) {
        this._img(slot, "badge_piggy_plus", cx - 72, 40, 48);
      }
      if (!c.sel) {
        this._img(slot, "status_lock", cx + 70, 170, 64);
      }
    });
  }

  _buildFunctions() {
    const child = this._children[this._child];
    const fns = this._functionsFor(child);
    this._function = 0;
    if (this._functionChild === child.id) {
      const i = fns.findIndex((fn) => this._functionKeyOf(fn) === this._functionKey);
      this._function = Math.max(i, 0);
    }
    this._functionChild = child.id;
    this._functionKey = this._functionKeyOf(fns[this._function]);
    const disc = mix(parseColor(child.c, 0x6cb8ff), 0xffffff, 90);
    this._carousel = new Carousel(this, this._screenLayer, fns.length, this._function, 240, 240, 145, 230, this._animMs(240), (slot, index) => {
      this._disc(slot, 120, 120, 210, disc);
      const fn = fns[index];
      const icon = fn.type === FN.ROUTINE ? this._routines[fn.routine].i : { [FN.REWARDS]: "fn_rewards", [FN.PIGGY]: "fn_piggy", [FN.TOKENS]: "fn_tokens" }[fn.type];
      this._img(slot, icon || "fn_rewards", 120, 120, 160);
    });
    // Small child marker at the top centre: context only, not the focus.
    this._disc(this._screenLayer, CENTER, 96, 76, parseColor(child.c, 0x6cb8ff));
    this._avatar(this._screenLayer, child, CENTER, 96, 65);
  }

  _buildRewards() {
    const child = this._children[this._child];
    const shop = this._shop();
    const position = Math.max(
      shop.findIndex((r) => r.id === this._rewardId),
      0,
    );
    this._rewardId = shop[position].id;
    const disc = mix(parseColor(child.c, 0x6cb8ff), 0xffffff, 80);
    this._carousel = new Carousel(this, this._screenLayer, shop.length, position, 260, 290, 60, 240, this._animMs(240), (slot, index) => {
      const r = shop[index];
      // The lock only means "not enough tokens".
      const locked = r.c > child.w;
      this._disc(slot, 130, 120, 200, locked ? LOCKED : disc);
      this._rewardIcon(slot, r, 130, 120, 160, locked ? "grey" : "");
      if (locked) {
        this._img(slot, "status_lock", 205, 190, 64);
      }
      this._pill(slot, 130, 252, r.c);
    });
    this._pill(this._screenLayer, CENTER, 420, child.w);
  }

  _buildConfirm() {
    const child = this._children[this._child];
    const reward = this._shop().find((r) => r.id === this._rewardId) || this._shop()[0];
    const layer = this._screenLayer;
    this._disc(layer, CENTER, 160, 180, mix(parseColor(child.c, 0x6cb8ff), 0xffffff, 80));
    this._rewardIcon(layer, reward, CENTER, 160, 160);
    this._pill(layer, CENTER, 272, reward.c);
    const no = this._img(layer, "action_x", 160, 345, 88);
    const yes = this._img(layer, "action_check", 320, 345, 88);
    // The selected choice is circled (not only coloured).
    const ring = document.createElement("div");
    ring.className = "disc";
    ring.style.cssText = "width:116px;height:116px;box-sizing:border-box;border:6px solid #fff";
    layer.appendChild(ring);
    this._confirm = { no, yes, ring };
    this._placeConfirmRing();
    this._pill(layer, CENTER, 420, child.w);
  }

  _placeConfirmRing() {
    if (!this._confirm) {
      return;
    }
    const { no, yes, ring } = this._confirm;
    const target = this._confirmYes ? yes : no;
    const cx = this._confirmYes ? 320 : 160;
    ring.style.left = `${cx - 58}px`;
    ring.style.top = `${345 - 58}px`;
    target.style.opacity = "1";
    (this._confirmYes ? no : yes).style.opacity = String(140 / 255);
  }

  _buildTokens() {
    const child = this._children[this._child];
    const layer = this._screenLayer;
    this._pile(layer, CENTER, 290, child.w, 500 + this._child, 11, 18, 19, 10);
    this._pill(layer, CENTER, 335, child.w);
    // Streak: flame + one marker per day of the target.
    this._img(layer, "streak_flame", CENTER, 100, 64);
    const n = Math.max(child.st || 7, 1);
    const x0 = CENTER - ((n - 1) * 30) / 2;
    for (let i = 0; i < n; i++) {
      const x = x0 + i * 30;
      if (i < child.s) {
        this._img(layer, "action_check_small", x, 392, 24);
      } else {
        this._img(layer, "streak_day_empty", x, 392, 24);
      }
    }
  }

  // A heap of exactly `count` coins: a pyramid up to max_rows, then wider up
  // to max_width, then spilling below the base (off the screen if needed).
  _pile(parent, cx, baseY, count, seed, maxRows, maxWidth, dx, dy) {
    if (count <= 0) {
      return;
    }
    const variants = ["token_coin_front", "token_coin_tilt_left", "token_coin_tilt_right"];
    const capacity = (width) => {
      let cap = 0;
      for (let r = 0; r < maxRows && r < width; r++) {
        cap += width - r;
      }
      return cap;
    };
    let width = 1;
    while (width < maxWidth && capacity(width) < count) {
      width++;
    }
    const rows = [];
    let left = count;
    for (let r = 0; r < maxRows && r < width && left > 0; r++) {
      const n = Math.min(width - r, left);
      rows.push({ y: baseY - r * dy, n });
      left -= n;
    }
    let spill = 0;
    while (left > 0) {
      spill++;
      const n = Math.min(width + spill, left);
      rows.push({ y: baseY + spill * dy, n });
      left -= n;
    }
    const order = rows.map((_, i) => i).sort((a, b) => rows[a].y - rows[b].y);
    for (const idx of order) {
      const row = rows[idx];
      if (row.y - 14 > SCREEN + 16) {
        continue;
      }
      for (let i = 0; i < row.n; i++) {
        const h = hash32((Math.imul(seed, 7919) + Math.imul(idx, 131) + i) >>> 0);
        const jx = (h % 7) - 3;
        const jy = ((h >>> 8) % 5) - 2;
        const x = cx + Math.trunc((i - (row.n - 1) / 2) * dx) + jx;
        this._img(parent, variants[(h >>> 16) % 3], x, row.y + jy, 28);
      }
    }
  }

  _buildPiggy() {
    const child = this._children[this._child];
    const layer = this._screenLayer;
    this._piggyAmount = 0;
    if (child.pi > 0) {
      // Interest paid while the child was away: that many tokens drop into
      // the piggy bank once, then Home Assistant is told it was shown.
      const coins = Math.min(child.pi, 40);
      child.pi = 0;
      this._send("seen", {});
      this._flyCoins(coins, 60, 174, "ease-in", () => 0, 80, 500, (i) => CENTER - 40 + (hash32(i) % 80));
    }
    this._img(layer, "piggy_large", CENTER, 175, 180);
    this._pill(layer, CENTER, 268, child.p);
    const label = document.createElement("div");
    label.className = "abs num";
    label.style.cssText = "left:0;width:480px;top:322px;text-align:center";
    layer.appendChild(label);
    this._piggyLabel = label;
    this._updatePiggyAmount();
    this._pill(layer, CENTER, 410, child.w);
  }

  _updatePiggyAmount() {
    if (!this._piggyLabel) {
      return;
    }
    const n = this._piggyAmount;
    this._piggyLabel.textContent = n === 0 ? "+/-" : `${n > 0 ? "+" : ""}${n}`;
    this._piggyLabel.style.color = hex(n === 0 ? GREY : n > 0 ? ZONE_DEPOSIT : ZONE_WITHDRAW);
  }

  _buildRoutine() {
    const routine = this._routine();
    const layer = this._screenLayer;
    const tasks = routine.t || [];
    const current = tasks.findIndex((t) => !this._isDone(routine, t.id));
    this._taskBig = current >= 0 ? this._img(layer, tasks[current].i, CENTER, 205, 150) : this._img(layer, "action_check", CENTER, 205, 88);
    // Completed tasks collect on the left (grey), future ones on the right.
    let doneSlot = 0;
    let futureSlot = 0;
    tasks.forEach((t, i) => {
      if (i === current) {
        return;
      }
      const done = this._isDone(routine, t.id);
      const deg = done ? 120 + 20 * doneSlot++ : 60 - 20 * futureSlot++;
      const rad = (deg * Math.PI) / 180;
      this._img(layer, t.i, CENTER + Math.trunc(150 * Math.cos(rad)), CENTER + Math.trunc(150 * Math.sin(rad)), 40, done ? "dim" : "");
    });
  }

  // ------------------------------------------------------------ time track

  _buildTrack() {
    this._trackLayer.replaceChildren();
    this._shownReward = -1;
    this._nowDot = null;
    const routine = this._trackRoutine();
    this._shownRoutine = routine;
    this._drawRing();
    const child = this._children[this._child];
    if (routine) {
      for (const cp of routine.cp || []) {
        if (cp.ch && cp.ch.length) {
          // This child's own checkpoints on the inner track.
          if (child && applies(cp.ch, child.id)) {
            const [x, y] = ringPoint(this._trackP(routine, cp.t), INNER_MID);
            this._img(this._trackLayer, cp.i || "checkpoint_flag", x, y, 28, this._cpDone(routine, cp.id) ? "grey" : "");
          }
          continue;
        }
        // Shared checkpoints on the outer track; reached ones are grey.
        const [x, y] = ringPoint(this._trackP(routine, cp.t), OUTER_MID);
        this._img(this._trackLayer, cp.i || "checkpoint_flag", x, y, 32, child && this._cpDone(routine, cp.id) ? "grey" : "");
      }
      this._nowDot = this._disc(this._trackLayer, 0, 0, 18, 0xffffff);
    }
    // Top gap: the brand mark, or the reward available now on a routine screen.
    this._topGap = document.createElement("div");
    this._topGap.className = "abs";
    this._topGap.style.cssText = `left:${CENTER - 80}px;top:4px;width:160px;height:56px`;
    this._trackLayer.appendChild(this._topGap);
    // Always visible while offline, at the right edge of the top gap.
    this._offline = this._img(this._trackLayer, "status_disconnected", CENTER + 64, 32, 28);
    this._offline.style.display = this._connected ? "none" : "";
    this._updateTrack();
  }

  _trackP(routine, t) {
    const total = Math.max(routine.e - routine.s, 1);
    return Math.max(0, Math.min(1, (t - routine.s) / total));
  }

  _drawRing() {
    const routine = this._shownRoutine;
    const child = this._children[this._child];
    const svg = [];
    const arc = (r, p0, p1, color, width, cap = "round", extra = "") =>
      `<path d="${arcPath(r, p0, p1)}" fill="none" stroke="${hex(color)}" stroke-width="${width}" stroke-linecap="${cap}" ${extra}/>`;
    if (child) {
      // A glow in the selected child's colour around both tracks.
      const glow = hex(mix(parseColor(child.c, 0x6cb8ff), BASE_BG, 200));
      svg.push(`<defs><filter id="glow" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="3"/></filter></defs>`);
      svg.push(`<g filter="url(#glow)" opacity="${115 / 255}">${arc(INNER_MID, 0, 1, parseInt(glow.slice(1), 16), INNER_W + 2 * GLOW_W)}${arc(OUTER_MID, 0, 1, parseInt(glow.slice(1), 16), OUTER_W + GLOW_W)}</g>`);
      svg.push(arc(INNER_MID, 0, 1, parseInt(glow.slice(1), 16), INNER_W));
    }
    if (routine) {
      const zones = [...(routine.z || [])].sort((a, b) => b[0] - a[0]);
      svg.push(arc(OUTER_MID, 0, 1, parseColor(routine.base, 0x6bcb77), OUTER_W));
      zones.forEach(([offset, color], i) => {
        const from = this._trackP(routine, routine.e - offset);
        const next = zones[i + 1];
        const to = next ? this._trackP(routine, routine.e - next[0]) : 1;
        const c = parseColor(color, 0xff9f43);
        svg.push(arc(OUTER_MID, from, to, c, OUTER_W, "butt"));
        if (!next) {
          const [x, y] = ringPoint(1, OUTER_MID);
          svg.push(`<circle cx="${x}" cy="${y}" r="${OUTER_W / 2}" fill="${hex(c)}"/>`);
        }
      });
      // The elapsed part is dimmed; it moves on once a minute.
      const now = this._now();
      const elapsed = this._trackP(routine, now - (now % 60));
      if (elapsed > 0) {
        svg.push(arc(OUTER_MID, 0, elapsed, TRACK_DIM, OUTER_W + 2));
      }
    } else {
      svg.push(arc(OUTER_MID, 0, 1, TRACK_DIM, OUTER_W));
    }
    this._ring.innerHTML = svg.join("");
    this._ringMinute = Math.floor(this._now() / 60);
  }

  _updateTrack() {
    if (!this._trackLayer) {
      return;
    }
    if (this._screen !== SCREENS.ROUTINE && this._trackRoutine() !== this._shownRoutine && !this._busy) {
      this._buildTrack();
      return;
    }
    const routine = this._shownRoutine;
    if (routine && this._nowDot) {
      if (Math.floor(this._now() / 60) !== this._ringMinute && !this._busy) {
        this._drawRing();
      }
      const [x, y] = ringPoint(Math.max(0.001, this._trackP(routine, this._now())), OUTER_MID);
      this._nowDot.style.left = `${x - 9}px`;
      this._nowDot.style.top = `${y - 9}px`;
    }
    let reward = 0;
    if (this._screen === SCREENS.ROUTINE && routine && this._children.length) {
      const cp = this._nextCheckpoint(routine);
      reward = cp ? rewardFor(cp.b, cp.t - this._now()) : 0;
    }
    if (reward !== this._shownReward && this._topGap) {
      this._shownReward = reward;
      this._topGap.replaceChildren();
      if (reward > 0) {
        // The reward available now, as that many tokens.
        const x0 = 80 - ((reward - 1) * 18) / 2;
        for (let i = 0; i < reward; i++) {
          this._img(this._topGap, "token_coin_front", x0 + i * 18, 30, 28);
        }
      } else {
        this._img(this._topGap, this._state.lang === "hu" ? "brand_mark" : "brand_mark_en", 80, 28, 48);
      }
    }
  }
}

// ---------------------------------------------------------------- carousel

// Infinite horizontal carousel: the selected item in the middle, one on each
// side (faded), sliding by one item per step, clipped to the inner circle's
// square like on the knob.
class Carousel {
  constructor(card, parent, count, selected, slotW, slotH, y, spacing, animMs, fill) {
    this.card = card;
    this.count = Math.max(count, 1);
    this.selected = ((selected % this.count) + this.count) % this.count;
    this.slotW = slotW;
    this.y = y;
    this.spacing = spacing;
    this.animMs = animMs;
    this.fill = fill;
    const top = Math.max(y, 44);
    this.window = document.createElement("div");
    this.window.className = "window";
    this.window.style.cssText = `left:${WIN_X}px;top:${top}px;width:${WIN_END - WIN_X}px;height:${Math.max(1, Math.min(y + slotH, WIN_END) - top)}px`;
    this.slotTop = y - top;
    this.slotH = slotH;
    parent.appendChild(this.window);
    this.slots = [];
    for (const offset of this.count > 1 ? [-1, 0, 1] : [0]) {
      this.slots.push(this.makeSlot(offset));
    }
  }

  wrap(i) {
    return ((i % this.count) + this.count) % this.count;
  }

  makeSlot(offset) {
    const el = document.createElement("div");
    el.className = "slot";
    el.style.width = `${this.slotW}px`;
    el.style.height = `${this.slotH}px`;
    el.style.top = `${this.slotTop}px`;
    this.fill(el, this.wrap(this.selected + offset));
    this.window.appendChild(el);
    const slot = { el, offset };
    this.place(slot, false);
    return slot;
  }

  place(slot, animate) {
    const centre = CENTER + slot.offset * this.spacing;
    const x = centre - this.slotW / 2 - WIN_X;
    const dist = Math.abs(centre - CENTER);
    const opacity = Math.max(0, 255 - (Math.min(dist, 240) * 150) / 240) / 255;
    slot.el.style.transition = animate && this.animMs ? `transform ${this.animMs}ms ease-out, opacity ${this.animMs}ms ease-out` : "none";
    slot.el.style.transform = `translateX(${x}px)`;
    slot.el.style.opacity = String(opacity);
  }

  centerSlot() {
    return this.slots.find((s) => s.offset === 0)?.el;
  }

  rotate(dir) {
    if (this.count <= 1 || !dir) {
      return;
    }
    dir = dir > 0 ? 1 : -1;
    // Finish a running slide at once, so input never waits.
    this.slots = this.slots.filter((s) => {
      if (Math.abs(s.offset) > 1) {
        s.el.remove();
        return false;
      }
      return true;
    });
    const incoming = this.makeSlot(2 * dir);
    this.slots.push(incoming);
    this.selected = this.wrap(this.selected + dir);
    // Let the incoming slot be laid out at its start before it slides.
    void incoming.el.offsetWidth;
    for (const s of this.slots) {
      s.offset -= dir;
      this.place(s, true);
    }
    const leaving = this.slots.filter((s) => Math.abs(s.offset) > 1);
    setTimeout(() => {
      for (const s of leaving) {
        if (Math.abs(s.offset) > 1) {
          s.el.remove();
          this.slots = this.slots.filter((x) => x !== s);
        }
      }
    }, this.animMs + 50);
  }
}

// ---------------------------------------------------------------- editor

class KisSegitoKnobCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      hass
        .callWS({ type: "kis_segito/virtual/list" })
        .then((knobs) => {
          this._knobs = knobs;
          this._render();
        })
        .catch(() => {});
    }
  }

  _render() {
    if (!this._config) {
      return;
    }
    const knobs = this._knobs || [];
    const hu = (this._hass?.language || "").startsWith("hu");
    const t = hu
      ? { knob: "Virtuális gomb", none: "Nincs még virtuális gomb: a Kis Segítő panelen hozható létre (Beállítások → Gombok).", back: "Vissza gomb is látszik" }
      : { knob: "Virtual knob", none: "No virtual knob yet: create one on the Kis Segítő panel (Settings → Knobs).", back: "Show a back button too" };
    this.innerHTML = `<div style="display:flex;flex-direction:column;gap:12px;padding:4px 0">
      ${knobs.length ? `<label style="display:flex;flex-direction:column;gap:4px">${t.knob}<select data-k="knob" style="padding:8px">${knobs.map((k) => `<option value="${k.id}" ${k.id === this._config.knob ? "selected" : ""}>${k.name.replace(/[<&"]/g, "")}</option>`).join("")}</select></label>` : `<div>${t.none}</div>`}
      <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" data-k="back_button" ${this._config.back_button ? "checked" : ""}>${t.back}</label></div>`;
    if (knobs.length && !knobs.some((k) => k.id === this._config.knob)) {
      this._changed({ knob: knobs[0].id });
    }
    this.querySelectorAll("[data-k]").forEach((el) =>
      el.addEventListener("change", () => this._changed({ [el.dataset.k]: el.type === "checkbox" ? el.checked : el.value })),
    );
  }

  _changed(values) {
    this._config = { ...this._config, ...values };
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
  }
}

// The Home Assistant frontend can replace the custom element registry after
// this module has run; a card defined before that is unknown to the
// dashboards. So the elements are defined once the frontend's root element
// exists, when the registry is final.
const register = () => {
  const registry = window.customElements;
  if (!registry.get("kis-segito-knob-card")) {
    registry.define("kis-segito-knob-card", KisSegitoKnobCard);
  }
  if (!registry.get("kis-segito-knob-card-editor")) {
    registry.define("kis-segito-knob-card-editor", KisSegitoKnobCardEditor);
  }
};
const frontendReady = () => Boolean(window.customElements.get("home-assistant"));
if (frontendReady()) {
  register();
} else {
  window.customElements.whenDefined("home-assistant").then(register);
  // Also checks the current registry now and then, in case it was replaced
  // after this module ran.
  const timer = setInterval(() => {
    if (frontendReady()) {
      clearInterval(timer);
      register();
    }
  }, 250);
  setTimeout(() => clearInterval(timer), 120000);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "kis-segito-knob-card")) {
  window.customCards.push({
    type: "kis-segito-knob-card",
    name: "Kis Segítő",
    description: "The knob screen as a card / A gomb képernyője kártyaként",
    preview: false,
  });
}
