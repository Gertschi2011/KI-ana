#!/usr/bin/env python3
"""
KI-ana OS Desktop Environment

Launch the desktop interface.
"""

import sys
from PyQt5.QtWidgets import QApplication
from loguru import logger
from .tray import SystemTray
from .main_window import MainWindow


def main():
    """Main entry point"""
    logger.info("🚀 Starting KI-ana OS Desktop Environment...")
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("KI-ana OS")
    app.setOrganizationName("KI-ana")
    
    # Create system tray
    tray = SystemTray(app)
    tray.initialize()
    
    # Create main window
    window = MainWindow()
    window.show()
    
    # Show startup notification
    tray.show_notification(
        "KI-ana OS is running!\nClick the tray icon for quick actions.",
        "Welcome"
    )
    
    logger.success("✅ Desktop environment ready!")
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
