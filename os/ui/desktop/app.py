#!/usr/bin/env python3
"""
KI-ana OS Desktop App

Complete integrated desktop application.
"""

import sys
from PyQt5.QtWidgets import QApplication
from loguru import logger
from .tray import SystemTray
from .integrated_window import IntegratedMainWindow


def main():
    """Main entry point"""
    logger.info("🚀 Starting KI-ana OS Desktop...")
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("KI-ana OS")
    app.setOrganizationName("KI-ana")
    
    # Create system tray
    tray = SystemTray(app)
    tray.initialize()
    
    # Create integrated main window
    window = IntegratedMainWindow()
    window.show()
    
    # Welcome notification
    tray.show_notification(
        "KI-ana OS is running with full AI integration!\nTry chatting with me!",
        "Welcome to KI-ana OS"
    )
    
    logger.success("✅ Desktop ready with full integration!")
    
    # Run
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
