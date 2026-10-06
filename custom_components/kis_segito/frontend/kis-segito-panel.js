// SPDX-License-Identifier: AGPL-3.0-only
//
// Kis Segito sidebar panel. Plain web component, no build step.
// Texts come from translations/<language>.json next to this file; adding a
// language only needs a new JSON file. The language follows the Home Assistant
// user language unless one is chosen in the panel settings.

const FALLBACK_LANGUAGE = "en";
const LANGUAGE_AUTO = "auto";

class KisSegitoPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._strings = {};
    this._loadedLanguage = null;
    this._info = null;
    this._settings = null;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    this._updateLanguage();
    if (first) {
      this._loadInfo();
      this._loadSettings();
      this._render();
    } else {
      // Only the sidebar button needs the new hass object; re-rendering on
      // every state change would reset open controls.
      const menuButton = this.shadowRoot.querySelector("ha-menu-button");
      if (menuButton) {
        menuButton.hass = hass;
      }
    }
  }

  get _language() {
    const chosen = this._settings?.language;
    return chosen && chosen !== LANGUAGE_AUTO ? chosen : this._hass?.language;
  }

  _updateLanguage() {
    const language = this._language;
    if (language && language !== this._loadedLanguage) {
      this._loadTranslations(language);
    }
  }

  set narrow(narrow) {
    this._narrow = narrow;
    this._render();
  }

  set panel(panel) {
    this._panel = panel;
  }

  get _staticUrl() {
    return this._panel?.config?.static_url ?? "/kis_segito_static";
  }

  get _version() {
    return this._panel?.config?.version ?? "";
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
    const candidates = [language, language?.split("-")[0], FALLBACK_LANGUAGE];
    let strings = {};
    try {
      strings = await this._fetchStrings(FALLBACK_LANGUAGE);
    } catch (err) {
      console.warn("Kis Segito: missing fallback translations", err);
    }
    for (const candidate of candidates) {
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

  async _loadInfo() {
    try {
      this._info = await this._hass.callWS({ type: "kis_segito/info" });
    } catch (err) {
      console.warn("Kis Segito: info request failed", err);
    }
    this._render();
  }

  async _loadSettings() {
    try {
      this._settings = await this._hass.callWS({ type: "kis_segito/settings" });
    } catch (err) {
      console.warn("Kis Segito: settings request failed", err);
    }
    this._updateLanguage();
    this._render();
  }

  async _setLanguage(language) {
    try {
      this._settings = await this._hass.callWS({
        type: "kis_segito/settings/update",
        language,
      });
    } catch (err) {
      console.warn("Kis Segito: settings update failed", err);
    }
    this._updateLanguage();
    this._render();
  }

  _languageCard() {
    if (!this._settings) {
      return "";
    }
    const isAdmin = this._hass?.user?.is_admin ?? false;
    const current = this._settings.language;
    const options = [
      { code: LANGUAGE_AUTO, name: this._t("settings.language_auto") },
      ...this._settings.languages,
    ]
      .map(
        (lang) =>
          `<option value="${this._escape(lang.code)}" ${lang.code === current ? "selected" : ""}>${this._escape(lang.name)}</option>`
      )
      .join("");
    return `
      <div class="card">
        <h2>${this._escape(this._t("settings.title"))}</h2>
        <label for="language">${this._escape(this._t("settings.language"))}</label>
        <select id="language" ${isAdmin ? "" : "disabled"}>${options}</select>
        <p class="muted">
          ${this._escape(this._t(isAdmin ? "settings.language_hint" : "settings.admin_only"))}
        </p>
      </div>
    `;
  }

  _t(key) {
    return this._strings[key] ?? key;
  }

  _escape(text) {
    const div = document.createElement("div");
    div.textContent = String(text);
    return div.innerHTML;
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }
    const deviceCount = this._info?.devices?.length ?? 0;
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          min-height: 100vh;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font-family: var(--paper-font-body1_-_font-family, inherit);
        }
        .toolbar {
          display: flex;
          align-items: center;
          height: var(--header-height, 56px);
          padding: 0 16px;
          background: var(--app-header-background-color, var(--primary-color));
          color: var(--app-header-text-color, var(--text-primary-color));
          font-size: 20px;
        }
        .title {
          margin-left: 8px;
        }
        .content {
          max-width: 720px;
          margin: 0 auto;
          padding: 16px;
        }
        .card {
          background: var(--card-background-color);
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, none);
          border: 1px solid var(--divider-color);
          padding: 16px;
        }
        .card + .card {
          margin-top: 16px;
        }
        .card h2 {
          margin: 0 0 12px;
          font-size: 18px;
          font-weight: 500;
        }
        label {
          display: block;
          margin-bottom: 4px;
        }
        select {
          font: inherit;
          padding: 6px 8px;
          min-width: 240px;
          max-width: 100%;
          color: var(--primary-text-color);
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 4px;
        }
        .muted {
          color: var(--secondary-text-color);
        }
      </style>
      <div class="toolbar">
        <ha-menu-button></ha-menu-button>
        <span class="title">${this._escape(this._t("panel.title"))}</span>
      </div>
      <div class="content">
        <div class="card">
          <p>${this._escape(this._t("panel.empty"))}</p>
          <p class="muted">
            ${this._escape(this._t("panel.devices"))}: ${deviceCount}
            · ${this._escape(this._t("panel.version"))}: ${this._escape(this._version)}
          </p>
        </div>
        ${this._languageCard()}
      </div>
    `;
    this.shadowRoot
      .querySelector("#language")
      ?.addEventListener("change", (ev) => this._setLanguage(ev.target.value));
    // Sidebar toggle on narrow screens.
    const menuButton = this.shadowRoot.querySelector("ha-menu-button");
    if (menuButton) {
      menuButton.hass = this._hass;
      menuButton.narrow = this._narrow;
    }
  }
}

if (!customElements.get("kis-segito-panel")) {
  customElements.define("kis-segito-panel", KisSegitoPanel);
}
