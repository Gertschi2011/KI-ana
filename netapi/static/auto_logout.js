// Auto-Logout beim Tab-Schließen (Sicherheit!)
(function() {
  // Helper: Token aus beiden Storages lesen
  function getToken() {
    try {
      return sessionStorage.getItem('ki_token') || localStorage.getItem('ki_token');
    } catch {
      return null;
    }
  }
  
  // Migrate old localStorage token to sessionStorage on page load
  try {
    const oldToken = localStorage.getItem('ki_token');
    if (oldToken) {
      sessionStorage.setItem('ki_token', oldToken);
      localStorage.removeItem('ki_token');
      console.log('✅ Token migriert zu sessionStorage');
    }
  } catch {}
  
  // Make getToken available globally
  window.getAuthToken = getToken;
  
  // DEAKTIVIERT: pagehide feuert auch beim Seitenwechsel!
  // Auto-Logout nur über Inaktivitäts-Timer (inactivity_logout.js)
  // Oder manuellen Logout-Button
  
  // Session-Cookie wird automatisch beim Browser-Schließen gelöscht (Session-Cookie!)
  console.log('✅ Auto-Logout: Session-Cookie wird beim Browser-Schließen gelöscht');
})();
