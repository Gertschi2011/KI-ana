(() => {
  // Support both old and new markup variants
  const form = document.getElementById('loginForm') || document.getElementById('login-form');
  const msg  = document.getElementById('msg') || document.getElementById('login-msg');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (msg) msg.textContent = '🔐 Anmelden…';

    const uEl = document.getElementById('username') || form.querySelector('[name="username"]');
    const pEl = document.getElementById('password') || form.querySelector('[name="password"]');
    const rEl = document.getElementById('remember') || form.querySelector('[name="remember"]');
    const payload = {
      username: (uEl && 'value' in uEl ? (uEl as HTMLInputElement).value.trim() : ''),
      password: (pEl && 'value' in pEl ? (pEl as HTMLInputElement).value : ''),
      remember: !!(rEl && 'checked' in rEl ? (rEl as HTMLInputElement).checked : false),
    };

    try {
      const r = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || !data || data.ok === false) {
        if (msg) msg.textContent = (data && (data.detail || data.error)) || '❌ Login fehlgeschlagen';
        return;
      }
      if (msg) msg.textContent = '👋 Willkommen!';
      const next = new URLSearchParams(location.search).get('next') || '/static/chat.html';
      setTimeout(() => { location.href = next; }, 250);
    } catch (err) {
      console.error(err);
      if (msg) msg.textContent = '⚠️ Netzwerk- oder Serverfehler';
    }
  });
})();
