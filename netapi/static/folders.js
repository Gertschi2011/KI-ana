 // Folders Management System
(function() {
  'use strict';
  
  let folders = [];
  let currentFolderId = null;
  let multiSelectMode = false;
  let selectedConvIds = new Set();
  
  // === API Calls ===
  
  async function loadFolders() {
    try {
      const r = await fetch('/api/folders', { credentials: 'include' });
      if (!r.ok) return;
      const data = await r.json();
      if (data.ok && Array.isArray(data.folders)) {
        folders = data.folders;
        // Default: show all conversations (including those without folder)
        // Do NOT auto-select the first folder, to avoid hiding no-folder conversations.
        if (currentFolderId === null) {
          currentFolderId = null;
        }
        renderFolders();
      }
    } catch (e) {
      console.error('Failed to load folders:', e);
    }
  }
  
  async function createFolder(name, color = '#667eea', icon = '📁') {
    try {
      const r = await fetch('/api/folders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name, color, icon })
      });
      const data = await r.json();
      if (data.ok && data.folder) {
        folders.push(data.folder);
        renderFolders();
        return data.folder;
      }
    } catch (e) {
      console.error('Failed to create folder:', e);
    }
    return null;
  }
  
  async function updateFolder(id, updates) {
    try {
      const r = await fetch(`/api/folders/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(updates)
      });
      const data = await r.json();
      if (data.ok) {
        const idx = folders.findIndex(f => f.id === id);
        if (idx >= 0) {
          folders[idx] = { ...folders[idx], ...updates };
          renderFolders();
        }
      }
    } catch (e) {
      console.error('Failed to update folder:', e);
    }
  }
  
  async function deleteFolder(id) {
    try {
      const r = await fetch(`/api/folders/${id}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      const data = await r.json();
      if (data.ok) {
        folders = folders.filter(f => f.id !== id);
        if (currentFolderId === id) currentFolderId = null;
        renderFolders();
        // Reload conversations
        if (window.loadConversations) window.loadConversations();
      }
    } catch (e) {
      console.error('Failed to delete folder:', e);
    }
  }
  
  async function moveConversationsToFolder(convIds, folderId) {
    try {
      const r = await fetch('/api/folders/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          conversation_ids: convIds,
          folder_id: folderId
        })
      });
      const data = await r.json();
      if (data.ok) {
        // Reload folders to update counts
        await loadFolders();
        // Reload conversations
        if (window.loadConversations) window.loadConversations();
        return true;
      }
    } catch (e) {
      console.error('Failed to move conversations:', e);
    }
    return false;
  }
  
  // === UI Rendering ===
  
  function renderFolders() {
    const container = document.getElementById('foldersSection');
    if (!container) return;
    
    container.innerHTML = `
      <div class="folders-header" onclick="toggleFoldersCollapse()">
        <div class="folders-title">📁 Ordner</div>
        <div class="folders-actions">
          <button class="folder-btn" onclick="showCreateFolderModal(event)" title="Neuer Ordner">+</button>
          <button class="folder-btn" onclick="toggleFoldersCollapse(event)">▼</button>
        </div>
      </div>
      <div class="folders-list" id="foldersList">
        ${folders.map(f => `
          <div class="folder-item ${currentFolderId === f.id ? 'active' : ''}" 
               onclick="selectFolder(${f.id})"
               style="border-left: 3px solid ${f.color}">
            <span class="folder-icon">${f.icon}</span>
            <span class="folder-name">${escapeHtml(f.name)}</span>
            <span class="folder-count">${f.conversation_count || 0}</span>
            <div class="folder-actions">
              <button class="folder-action-btn" onclick="editFolder(event, ${f.id})" title="Bearbeiten">✏️</button>
              <button class="folder-action-btn" onclick="deleteFolderConfirm(event, ${f.id})" title="Löschen">🗑️</button>
            </div>
          </div>
        `).join('')}
        <div class="folder-item ${currentFolderId === null ? 'active' : ''}" 
             onclick="selectFolder(null)">
          <span class="folder-icon">📝</span>
          <span class="folder-name">Ohne Ordner</span>
          <span class="folder-count" id="noFolderCount">0</span>
        </div>
      </div>
    `;
  }
  
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  window.toggleFoldersCollapse = function(e) {
    if (e) e.stopPropagation();
    const list = document.getElementById('foldersList');
    if (list) list.classList.toggle('collapsed');
  };
  
  window.selectFolder = function(folderId) {
    currentFolderId = folderId;
    renderFolders();
    // Notify conversations renderer
    if (typeof window.renderConversationList === 'function') {
      try { window.renderConversationList(folderId); } catch {}
    } else if (typeof window.filterConversationsByFolder === 'function') {
      // backward compatibility
      try { window.filterConversationsByFolder(folderId); } catch {}
    }
  };
  
  // === Create Folder Modal ===
  
  window.showCreateFolderModal = function(e) {
    if (e) e.stopPropagation();
    
    const colors = ['#667eea', '#f093fb', '#4facfe', '#43e97b', '#fa709a', '#ff6b6b', '#feca57', '#48dbfb'];
    const icons = ['📁', '💼', '🎯', '⭐', '🔥', '💡', '📚', '🎨', '🚀', '💎'];
    
    let selectedColor = colors[0];
    let selectedIcon = icons[0];
    
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-header">Neuer Ordner</div>
        <div class="modal-body">
          <input type="text" id="folderNameInput" class="modal-input" placeholder="Ordnername..." />
          
          <div style="margin-top: 16px;">
            <strong>Farbe:</strong>
            <div class="color-picker">
              ${colors.map(c => `
                <div class="color-option ${c === selectedColor ? 'selected' : ''}" 
                     style="background: ${c}"
                     onclick="selectColor('${c}')"></div>
              `).join('')}
            </div>
          </div>
          
          <div style="margin-top: 16px;">
            <strong>Icon:</strong>
            <div class="icon-picker">
              ${icons.map(i => `
                <div class="icon-option ${i === selectedIcon ? 'selected' : ''}"
                     onclick="selectIcon('${i}')">${i}</div>
              `).join('')}
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="modal-btn secondary" onclick="closeModal()">Abbrechen</button>
          <button class="modal-btn primary" onclick="confirmCreateFolder()">Erstellen</button>
        </div>
      </div>
    `;
    
    document.body.appendChild(modal);
    document.getElementById('folderNameInput').focus();
    
    // Store selections
    window._selectedColor = selectedColor;
    window._selectedIcon = selectedIcon;
    
    window.selectColor = function(color) {
      window._selectedColor = color;
      document.querySelectorAll('.color-option').forEach(el => {
        el.classList.toggle('selected', el.style.background === color);
      });
    };
    
    window.selectIcon = function(icon) {
      window._selectedIcon = icon;
      document.querySelectorAll('.icon-option').forEach(el => {
        el.classList.toggle('selected', el.textContent === icon);
      });
    };
  };
  
  window.confirmCreateFolder = async function() {
    const name = document.getElementById('folderNameInput').value.trim();
    if (!name) {
      alert('Bitte gib einen Namen ein!');
      return;
    }
    
    await createFolder(name, window._selectedColor, window._selectedIcon);
    closeModal();
  };
  
  window.closeModal = function() {
    document.querySelector('.modal-backdrop')?.remove();
  };
  
  // === Edit Folder ===
  
  window.editFolder = function(e, folderId) {
    e.stopPropagation();
    const folder = folders.find(f => f.id === folderId);
    if (!folder) return;
    
    const newName = prompt('Neuer Name:', folder.name);
    if (newName && newName.trim() && newName !== folder.name) {
      updateFolder(folderId, { name: newName.trim() });
    }
  };
  
  window.deleteFolderConfirm = function(e, folderId) {
    e.stopPropagation();
    const folder = folders.find(f => f.id === folderId);
    if (!folder) return;
    
    const confirmed = confirm(`Ordner "${folder.name}" löschen?\n\nAlle Unterhaltungen werden in "Ohne Ordner" verschoben.`);
    if (confirmed) {
      deleteFolder(folderId);
    }
  };
  
  // === Multi-Select ===
  
  window.toggleMultiSelectMode = function() {
    multiSelectMode = !multiSelectMode;
    selectedConvIds.clear();
    
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
      sidebar.classList.toggle('multi-select-mode', multiSelectMode);
    }
    
    renderMultiSelectBar();
  };
  
  window.toggleConvSelection = function(convId) {
    if (selectedConvIds.has(convId)) {
      selectedConvIds.delete(convId);
    } else {
      selectedConvIds.add(convId);
    }
    renderMultiSelectBar();
  };
  
  function renderMultiSelectBar() {
    let bar = document.getElementById('multiSelectBar');
    
    if (!multiSelectMode || selectedConvIds.size === 0) {
      bar?.remove();
      return;
    }
    
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'multiSelectBar';
      bar.className = 'multi-select-bar';
      document.body.appendChild(bar);
    }
    
    bar.innerHTML = `
      <div class="multi-select-info">
        ${selectedConvIds.size} ausgewählt
      </div>
      <div class="multi-select-actions">
        <button class="multi-select-btn" onclick="showMoveToFolderDialog()">
          📁 In Ordner verschieben
        </button>
        <button class="multi-select-btn danger" onclick="deleteSelectedConversations()">
          🗑️ Löschen
        </button>
        <button class="multi-select-btn" onclick="toggleMultiSelectMode()">
          ✖️ Abbrechen
        </button>
      </div>
    `;
  }
  
  window.showMoveToFolderDialog = function() {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-header">In Ordner verschieben</div>
        <div class="modal-body">
          <div style="display: flex; flex-direction: column; gap: 8px;">
            ${folders.map(f => `
              <div class="folder-item" onclick="moveSelectedToFolder(${f.id})" style="border-left: 3px solid ${f.color}">
                <span class="folder-icon">${f.icon}</span>
                <span class="folder-name">${escapeHtml(f.name)}</span>
              </div>
            `).join('')}
            <div class="folder-item" onclick="moveSelectedToFolder(null)">
              <span class="folder-icon">📝</span>
              <span class="folder-name">Ohne Ordner</span>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="modal-btn secondary" onclick="closeModal()">Abbrechen</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  };
  
  window.moveSelectedToFolder = async function(folderId) {
    const convIds = Array.from(selectedConvIds);
    const success = await moveConversationsToFolder(convIds, folderId);
    if (success) {
      selectedConvIds.clear();
      multiSelectMode = false;
      renderMultiSelectBar();
      closeModal();
    }
  };
  
  window.deleteSelectedConversations = async function() {
    const count = selectedConvIds.size;
    const confirmed = confirm(`${count} Unterhaltungen wirklich löschen?`);
    if (!confirmed) return;
    
    // Call batch delete
    for (const convId of selectedConvIds) {
      // Use existing deleteConversation function if available
      if (window.deleteConversation) {
        await window.deleteConversation(convId);
      }
    }
    
    selectedConvIds.clear();
    multiSelectMode = false;
    renderMultiSelectBar();
    
    // Reload
    if (window.loadConversations) window.loadConversations();
  };
  
  // === Init ===
  
  function init() {
    // Add CSS
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/folders.css?v=20251104';
    document.head.appendChild(link);
    
    // Create folders section in sidebar if not exists
    const sidebar = document.querySelector('.sidebar');
    if (sidebar && !document.getElementById('foldersSection')) {
      const section = document.createElement('div');
      section.id = 'foldersSection';
      section.className = 'folders-section';
      sidebar.insertBefore(section, sidebar.firstChild);
    }
    
    // Add multi-select button to toolbar
    const toolbar = document.getElementById('convToolbar');
    if (toolbar && !document.getElementById('multiSelectBtn')) {
      const btn = document.createElement('button');
      btn.id = 'multiSelectBtn';
      btn.className = 'btn-icon';
      btn.innerHTML = '☑️';
      btn.title = 'Mehrfachauswahl';
      btn.onclick = toggleMultiSelectMode;
      btn.style.cssText = 'background:none;border:none;font-size:18px;cursor:pointer;padding:4px 8px;border-radius:4px;';
      btn.addEventListener('mouseenter', () => btn.style.background = 'rgba(0,0,0,0.05)');
      btn.addEventListener('mouseleave', () => btn.style.background = 'none');
      toolbar.appendChild(btn);
      console.log('✅ Multi-select button added to toolbar');
    } else {
      console.warn('⚠️ Toolbar not found or button already exists:', !!toolbar, !!document.getElementById('multiSelectBtn'));
    }
    
    // Load folders
    loadFolders();
  }
  
  // Auto-init with retry
  function tryInit() {
    const toolbar = document.getElementById('convToolbar');
    const foldersSection = document.getElementById('foldersSection');
    
    if (toolbar && foldersSection) {
      init();
    } else {
      console.warn('⚠️ Folders init: DOM not ready, retrying...', {toolbar: !!toolbar, foldersSection: !!foldersSection});
      setTimeout(tryInit, 100);
    }
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tryInit);
  } else {
    tryInit();
  }
  
  // Export functions
  window.FoldersManager = {
    loadFolders,
    createFolder,
    updateFolder,
    deleteFolder,
    moveConversationsToFolder,
    getCurrentFolderId: () => currentFolderId,
    isMultiSelectMode: () => multiSelectMode,
    // Expose simple state object for external orchestration
    state: {
      get folders() { return folders; },
      get activeFolderId() { return currentFolderId; },
      set activeFolderId(v) { currentFolderId = v; },
    },
  };
  
})();
