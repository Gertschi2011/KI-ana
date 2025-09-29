(async function(){
  const host = document.getElementById('nav');
  if(!host) return;
  const nav = await (await fetch('/static/nav.html?v=5',{cache:'no-cache'})).text();
  host.innerHTML = nav;

  // Mark active
  const here = location.pathname + location.search;
  for (const a of host.querySelectorAll('a[data-match]')) {
    const rx = new RegExp(a.getAttribute('data-match'));
    if (rx.test(here)) a.classList.add('active');
  }

  // Auth gate
  try{
    const me = await (await fetch('/api/me',{credentials:'include'})).json();
    const auth = me && me.auth;
    const role = me?.role || 'user';
    for (const el of host.querySelectorAll('[data-auth]')) el.style.display = auth?'':'none';
    for (const el of host.querySelectorAll('[data-guest]')) el.style.display = auth?'none':'';
    for (const el of host.querySelectorAll('[data-role]')) {
      el.style.display = (auth && role===el.getAttribute('data-role'))?'':'none';
    }
  }catch(e){}
})();
