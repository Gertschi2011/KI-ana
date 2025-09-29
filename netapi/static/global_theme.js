(function(){
  function applyTheme(){
    try{
      let t = localStorage.getItem('kiana_theme') || 'system';
      if (t === 'system'){
        t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      document.body.classList.remove('theme-dark','theme-light');
      document.body.classList.add('theme-'+t);
    }catch{}
  }
  function applyLang(){
    try{
      const lang = (localStorage.getItem('kiana_lang') || 'de').toLowerCase();
      const html = document.documentElement || document.querySelector('html');
      if (html) html.setAttribute('lang', lang);
      // Custom event for live UI updates without reload
      try{ window.dispatchEvent(new CustomEvent('kiana_lang_change', { detail: { lang } })); }catch{}
    }catch{}
  }
  // Apply now and after DOM is ready
  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){ applyTheme(); applyLang(); });
  } else {
    applyTheme();
    applyLang();
  }
  // Listen to changes in localStorage across tabs
  window.addEventListener('storage', e=>{ try{
    if (e.key === 'kiana_theme') applyTheme();
    if (e.key === 'kiana_lang') applyLang();
  }catch{} });
  // Listen to system dark-mode change
  try{ window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme); }catch{}
})();
