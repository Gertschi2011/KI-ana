"""
System Tray Icon

KI-ana OS system tray integration.
"""

import sys
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer
import asyncio
from loguru import logger


class SystemTray:
    """
    System Tray Icon for KI-ana OS
    
    Provides quick access to KI-ana features from system tray.
    """
    
    def __init__(self, app: QApplication):
        self.app = app
        self.tray_icon = None
        self.menu = None
        
    def initialize(self):
        """Initialize system tray"""
        logger.info("🖥️  Initializing system tray...")
        
        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self.app)
        
        # Set icon (using default for now)
        # TODO: Add custom KI-ana icon
        self.tray_icon.setIcon(self.app.style().standardIcon(
            self.app.style().StandardPixmap.SP_ComputerIcon
        ))
        
        # Create menu
        self.menu = QMenu()
        
        # Add actions
        self._add_menu_actions()
        
        # Set menu
        self.tray_icon.setContextMenu(self.menu)
        
        # Show tray icon
        self.tray_icon.show()
        
        # Set tooltip
        self.tray_icon.setToolTip("KI-ana OS - Your AI Operating System")
        
        logger.success("✅ System tray ready")
    
    def _add_menu_actions(self):
        """Add menu actions"""
        
        # Quick Actions
        quick_scan = QAction("🔍 Quick Scan", self.app)
        quick_scan.triggered.connect(self._on_quick_scan)
        self.menu.addAction(quick_scan)
        
        optimize = QAction("🚀 Optimize System", self.app)
        optimize.triggered.connect(self._on_optimize)
        self.menu.addAction(optimize)
        
        health = QAction("🏥 Health Check", self.app)
        health.triggered.connect(self._on_health_check)
        self.menu.addAction(health)
        
        self.menu.addSeparator()
        
        # Voice Mode
        voice = QAction("🎙️ Voice Mode", self.app)
        voice.triggered.connect(self._on_voice_mode)
        self.menu.addAction(voice)
        
        self.menu.addSeparator()
        
        # Settings
        settings = QAction("⚙️ Settings", self.app)
        settings.triggered.connect(self._on_settings)
        self.menu.addAction(settings)
        
        # About
        about = QAction("ℹ️ About KI-ana OS", self.app)
        about.triggered.connect(self._on_about)
        self.menu.addAction(about)
        
        self.menu.addSeparator()
        
        # Quit
        quit_action = QAction("❌ Quit", self.app)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)
    
    def _on_quick_scan(self):
        """Quick hardware scan"""
        logger.info("Quick scan requested")
        self.show_notification("Scanning hardware...", "KI-ana OS")
        # TODO: Trigger actual scan
    
    def _on_optimize(self):
        """Optimize system"""
        logger.info("Optimization requested")
        self.show_notification("Optimizing system...", "KI-ana OS")
        # TODO: Trigger actual optimization
    
    def _on_health_check(self):
        """Health check"""
        logger.info("Health check requested")
        self.show_notification("Checking system health...", "KI-ana OS")
        # TODO: Trigger actual health check
    
    def _on_voice_mode(self):
        """Start voice mode"""
        logger.info("Voice mode requested")
        self.show_notification("Voice mode activated", "KI-ana OS")
        # TODO: Start voice mode
    
    def _on_settings(self):
        """Open settings"""
        logger.info("Settings requested")
        # TODO: Open settings window
    
    def _on_about(self):
        """Show about dialog"""
        logger.info("About requested")
        self.show_notification(
            "KI-ana OS v0.1.0-alpha\nThe first AI Operating System",
            "About KI-ana OS"
        )
    
    def show_notification(self, message: str, title: str = "KI-ana OS"):
        """Show desktop notification"""
        if self.tray_icon:
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                3000  # 3 seconds
            )
    
    def update_tooltip(self, text: str):
        """Update tray icon tooltip"""
        if self.tray_icon:
            self.tray_icon.setToolTip(text)
