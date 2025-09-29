// Simple client-side i18n for KI_ana
// - Loads /static/i18n/<lang>.json with fallback to 'de'
// - Applies translations to elements with data-i18n and data-i18n-<attr>
// - Persists language in localStorage('lang')
(function(){
  const LS_KEY = 'lang';
  const I18N_DIR = '/static/i18n';

  function getPreferredLang(){
    const ls = localStorage.getItem(LS_KEY);
    if (ls) return ls;
    const nav = (navigator.language || 'de').toLowerCase();
    if (nav.startsWith('en')) return 'en';
    if (nav.startsWith('de')) return 'de';
    return 'en';
  }

  function deepGet(obj, path){
    if (!obj) return undefined;
    const parts = String(path).split('.');
    let cur = obj;
    for (const p of parts){
      if (cur && Object.prototype.hasOwnProperty.call(cur, p)) cur = cur[p];
      else return undefined;
    }
    return cur;
  }

  const i18n = {
    lang: 'de',
    dict: {},
    fallback: {},
    _ready: Promise.resolve(),

    async init(){
      // initialize with preferred language
      const lang = getPreferredLang();
      await this.setLang(lang);
    },

    async loadDict(lang){
      const url = `${I18N_DIR}/${lang}.json`;
      const r = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
      if (!r.ok) throw new Error(`i18n load ${lang}: ${r.status}`);
      return await r.json();
    },

    async setLang(lang){
      try {
        // always load fallback (de)
        if (!Object.keys(this.fallback).length){
          try { this.fallback = await this.loadDict('de'); }
          catch { this.fallback = {}; }
        }
        this.dict = await this.loadDict(lang);
        this.lang = lang;
        localStorage.setItem(LS_KEY, lang);
        document.documentElement.setAttribute('lang', lang);
        document.documentElement.setAttribute('data-lang', lang);
        // direction support placeholder (ltr for de/en)
        document.documentElement.setAttribute('dir', (['ar','he','fa','ur'].some(p => lang.startsWith(p)) ? 'rtl' : 'ltr'));
        this.apply(document);
        window.dispatchEvent(new CustomEvent('i18n:change', { detail: { lang } }));
      } catch (e) {
        console.warn('i18n setLang failed', e);
      }
    },

    t(key, fallback){
      const v = deepGet(this.dict, key);
      if (v != null) return String(v);
      const fb = deepGet(this.fallback, key);
      if (fb != null) return String(fb);
      return fallback != null ? String(fallback) : key;
    },

    apply(root){
      const scope = root || document;
      // Content nodes
      scope.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (!key) return;
        const txt = this.t(key, el.textContent || '');
        // if element asks for html via data-i18n-html="1"
        if (el.hasAttribute('data-i18n-html')) el.innerHTML = txt; else el.textContent = txt;
      });
      // Attribute-based translations: data-i18n-title, data-i18n-placeholder, data-i18n-aria-label, data-i18n-value
      const ATTRS = ['title','placeholder','aria-label','value'];
      ATTRS.forEach(attr => {
        scope.querySelectorAll(`[data-i18n-${attr}]`).forEach(el => {
          const key = el.getAttribute(`data-i18n-${attr}`);
          if (!key) return;
          const txt = this.t(key, el.getAttribute(attr) || '');
          el.setAttribute(attr, txt);
        });
      });
    }
  };

  function boot(){
    i18n._ready = i18n.init().catch(() => {});
    // Observe DOM mutations so dynamically injected nodes (e.g., nav) get translated
    const mo = new MutationObserver((list) => {
      for (const m of list){
        if (m.addedNodes && m.addedNodes.length){
          m.addedNodes.forEach(n => { if (n.nodeType === 1) i18n.apply(n); });
        }
      }
    });
    mo.observe(document.documentElement, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.i18n = i18n;
})();
