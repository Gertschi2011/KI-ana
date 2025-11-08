// Chat Initialization - Runs after DOM is ready
(function() {
  'use strict';
  
  // Wait for DOM to be fully loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
  
  function init() {
    console.log('🚀 Chat init starting...');
    
    // Check if elements exist
    const convList = document.getElementById('convList');
    const messagesArea = document.getElementById('messagesArea');
    const foldersSection = document.getElementById('foldersSection');
    
    console.log('📋 Elements check:', {
      convList: !!convList,
      messagesArea: !!messagesArea,
      foldersSection: !!foldersSection
    });
    
    // Call main chat UI init (from chat.js)
    if (window.initChatUI && typeof window.initChatUI === 'function') {
      console.log('🎯 Initializing chat UI...');
      window.initChatUI();
    } else {
      console.warn('⚠️ window.initChatUI not found - chat.js may not be loaded');
    }
    
    // Load folders after a short delay
    if (window.FoldersManager && window.FoldersManager.loadFolders) {
      setTimeout(() => {
        console.log('📁 Loading folders...');
        window.FoldersManager.loadFolders();
      }, 100);
    }
  }
})();
