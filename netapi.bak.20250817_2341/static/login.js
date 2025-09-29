(async function(){
  const form = document.querySelector('form#login');
  const msg  = document.getElementById('login-msg');
  if(!form) return;

  form.addEventListener('submit', async (ev)=>{
    ev.preventDefault();
    const fd = new FormData(form);
    msg.textContent = "Anmeldung…";
    try {
      const res = await fetch('/auth/login', { method:'POST', body: fd, credentials:'include' });
      const j = await res.json();
      if(!res.ok || !j.ok){
        msg.textContent = (j && j.error) ? j.error : 'Login fehlgeschlagen';
        return;
      }
      // erfolgreich: weiter in den Chat
      window.location.href = '/static/chat.html';
    } catch(e){
      msg.textContent = 'Netzwerkfehler';
    }
  });
})();
