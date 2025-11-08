// Inaktivitäts-Logout (Sicherheit für fremde PCs)
(function() {
  const INACTIVITY_TIMEOUT = 5 * 60 * 1000; // 5 Minuten in Millisekunden
  const WARNING_BEFORE = 30 * 1000; // 30 Sekunden Warnung vorher
  
  let inactivityTimer = null;
  let warningTimer = null;
  let warningShown = false;
  
  function resetTimers() {
    // Clear existing timers
    if (inactivityTimer) clearTimeout(inactivityTimer);
    if (warningTimer) clearTimeout(warningTimer);
    warningShown = false;
    
    // Hide warning if shown
    const warning = document.getElementById('inactivity-warning');
    if (warning) warning.remove();
    
    // Set warning timer (30 seconds before logout)
    warningTimer = setTimeout(() => {
      showWarning();
    }, INACTIVITY_TIMEOUT - WARNING_BEFORE);
    
    // Set logout timer
    inactivityTimer = setTimeout(() => {
      performLogout();
    }, INACTIVITY_TIMEOUT);
  }
  
  function showWarning() {
    if (warningShown) return;
    warningShown = true;
    
    const warning = document.createElement('div');
    warning.id = 'inactivity-warning';
    warning.innerHTML = `
      <div style="
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ff6b6b;
        color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        max-width: 300px;
        animation: slideIn 0.3s ease-out;
      ">
        <div style="font-weight: bold; margin-bottom: 10px;">⚠️ Inaktivitäts-Warnung</div>
        <div style="font-size: 14px; margin-bottom: 10px;">
          Du wirst in 30 Sekunden automatisch ausgeloggt.
        </div>
        <button onclick="window.resetInactivityTimer()" style="
          background: white;
          color: #ff6b6b;
          border: none;
          padding: 8px 16px;
          border-radius: 6px;
          cursor: pointer;
          font-weight: bold;
        ">
          Ich bin noch da!
        </button>
      </div>
    `;
    
    // Add animation
    const style = document.createElement('style');
    style.textContent = `
      @keyframes slideIn {
        from { transform: translateX(400px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
    `;
    document.head.appendChild(style);
    document.body.appendChild(warning);
  }
  
  function performLogout() {
    console.log('🔒 Auto-Logout wegen Inaktivität');
    
    // Logout API call
    fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include',
      keepalive: true
    }).catch(() => {});
    
    // Clear local data
    try {
      sessionStorage.clear();
      localStorage.removeItem('ki_token');
      localStorage.removeItem('kiana_username');
    } catch {}
    
    // Redirect to login with message
    window.location.href = '/static/login.html?reason=inactivity';
  }
  
  // Events that indicate user activity
  const activityEvents = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
  
  // Add event listeners
  activityEvents.forEach(event => {
    document.addEventListener(event, resetTimers, true);
  });
  
  // Make reset function globally accessible (for warning button)
  window.resetInactivityTimer = resetTimers;
  
  // Start initial timer
  resetTimers();
  
  console.log('✅ Inaktivitäts-Logout aktiviert (5 Minuten)');
})();
