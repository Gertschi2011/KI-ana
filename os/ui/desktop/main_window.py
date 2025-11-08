"""
Main Window

KI-ana OS main desktop window.
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from loguru import logger


class MainWindow(QMainWindow):
    """
    Main Desktop Window for KI-ana OS
    
    Provides visual interface for interacting with KI-ana.
    """
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("KI-ana OS - AI Operating System")
        self.setGeometry(100, 100, 900, 600)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        layout = QVBoxLayout()
        central.setLayout(layout)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Tabs
        tabs = self._create_tabs()
        layout.addLayout(tabs)
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #667eea;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #764ba2;
            }
            QTextEdit, QLineEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 8px;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #2d2d2d;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px 16px;
                border: 1px solid #444;
            }
            QTabBar::tab:selected {
                background-color: #667eea;
            }
        """)
    
    def _create_header(self) -> QWidget:
        """Create header"""
        header = QWidget()
        layout = QHBoxLayout()
        header.setLayout(layout)
        
        # Logo/Title
        title = QLabel("🧠 KI-ana OS")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Status
        status = QLabel("● Online")
        status.setStyleSheet("color: #4ade80; font-weight: bold;")
        layout.addWidget(status)
        
        return header
    
    def _create_tabs(self) -> QVBoxLayout:
        """Create tab widget"""
        layout = QVBoxLayout()
        
        tabs = QTabWidget()
        
        # Chat Tab
        chat_tab = self._create_chat_tab()
        tabs.addTab(chat_tab, "💬 Chat")
        
        # System Tab
        system_tab = self._create_system_tab()
        tabs.addTab(system_tab, "📊 System")
        
        # Settings Tab
        settings_tab = self._create_settings_tab()
        tabs.addTab(settings_tab, "⚙️ Settings")
        
        layout.addWidget(tabs)
        return layout
    
    def _create_chat_tab(self) -> QWidget:
        """Create chat tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Chat history
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("Chat with KI-ana...")
        layout.addWidget(self.chat_history)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type your message...")
        self.chat_input.returnPressed.connect(self._on_send_message)
        input_layout.addWidget(self.chat_input)
        
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._on_send_message)
        input_layout.addWidget(send_btn)
        
        voice_btn = QPushButton("🎙️ Voice")
        voice_btn.clicked.connect(self._on_voice_input)
        input_layout.addWidget(voice_btn)
        
        layout.addLayout(input_layout)
        
        return widget
    
    def _create_system_tab(self) -> QWidget:
        """Create system tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # System info
        info = QLabel("System Information")
        info.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(info)
        
        self.system_info = QTextEdit()
        self.system_info.setReadOnly(True)
        self.system_info.setPlainText("Loading system information...")
        layout.addWidget(self.system_info)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        scan_btn = QPushButton("🔍 Scan Hardware")
        scan_btn.clicked.connect(self._on_scan)
        btn_layout.addWidget(scan_btn)
        
        optimize_btn = QPushButton("🚀 Optimize")
        optimize_btn.clicked.connect(self._on_optimize)
        btn_layout.addWidget(optimize_btn)
        
        health_btn = QPushButton("🏥 Health Check")
        health_btn.clicked.connect(self._on_health)
        btn_layout.addWidget(health_btn)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_settings_tab(self) -> QWidget:
        """Create settings tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        title = QLabel("Settings")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        settings_text = QLabel(
            "• Voice: Enabled\n"
            "• LLM: llama3.1:8b\n"
            "• Auto-Optimize: On\n"
            "• Notifications: On"
        )
        layout.addWidget(settings_text)
        
        layout.addStretch()
        
        return widget
    
    def _on_send_message(self):
        """Handle send message"""
        message = self.chat_input.text()
        if message.strip():
            self.chat_history.append(f"You: {message}")
            self.chat_input.clear()
            
            # TODO: Process with AI brain
            self.chat_history.append("KI-ana: [Processing...]")
    
    def _on_voice_input(self):
        """Handle voice input"""
        self.chat_history.append("🎙️ Listening...")
        # TODO: Activate voice input
    
    def _on_scan(self):
        """Handle scan"""
        self.system_info.setPlainText("Scanning hardware...")
        # TODO: Actual scan
    
    def _on_optimize(self):
        """Handle optimize"""
        self.system_info.append("\nOptimizing system...")
        # TODO: Actual optimization
    
    def _on_health(self):
        """Handle health check"""
        self.system_info.append("\nChecking system health...")
        # TODO: Actual health check
