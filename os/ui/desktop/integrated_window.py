"""
Integrated Main Window

Main window with full AI Brain integration.
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QTabWidget, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from loguru import logger
import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class BrainWorker(QThread):
    """Worker thread for AI Brain operations"""
    finished = pyqtSignal(dict)
    
    def __init__(self, command: str):
        super().__init__()
        self.command = command
        
    def run(self):
        """Run brain processing in thread"""
        try:
            # Import here to avoid issues
            from core.ai_engine.smart_brain import get_smart_brain
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Process command
            async def process():
                brain = await get_smart_brain()
                return await brain.process_command(self.command)
            
            result = loop.run_until_complete(process())
            self.finished.emit(result)
            
        except Exception as e:
            logger.error(f"Brain worker error: {e}")
            self.finished.emit({
                "success": False,
                "error": str(e),
                "response": f"Error: {e}"
            })


class IntegratedMainWindow(QMainWindow):
    """
    Integrated Main Window
    
    Full integration with AI Brain, real system info, working features.
    """
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()
        self.start_monitoring()
        
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("KI-ana OS - AI Operating System")
        self.setGeometry(100, 100, 1000, 700)
        
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
        layout.addWidget(tabs)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Apply theme
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
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #764ba2;
            }
            QPushButton:pressed {
                background-color: #5a67d8;
            }
            QTextEdit, QLineEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #2d2d2d;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 10px 20px;
                border: 1px solid #444;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #667eea;
            }
            QProgressBar {
                border: 1px solid #444;
                border-radius: 6px;
                text-align: center;
                background-color: #2d2d2d;
            }
            QProgressBar::chunk {
                background-color: #667eea;
                border-radius: 6px;
            }
        """)
    
    def _create_header(self) -> QWidget:
        """Create header"""
        header = QWidget()
        layout = QHBoxLayout()
        header.setLayout(layout)
        
        # Logo/Title
        title = QLabel("🧠 KI-ana OS")
        title.setFont(QFont("Arial", 26, QFont.Weight.Bold))
        layout.addWidget(title)
        
        layout.addStretch()
        
        # System status
        self.status_label = QLabel("● System Ready")
        self.status_label.setStyleSheet("color: #4ade80; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.status_label)
        
        return header
    
    def _create_tabs(self) -> QTabWidget:
        """Create tab widget"""
        tabs = QTabWidget()
        
        # Chat Tab
        chat_tab = self._create_chat_tab()
        tabs.addTab(chat_tab, "💬 Chat")
        
        # Dashboard Tab
        dashboard_tab = self._create_dashboard_tab()
        tabs.addTab(dashboard_tab, "📊 Dashboard")
        
        # System Tab
        system_tab = self._create_system_tab()
        tabs.addTab(system_tab, "🖥️ System")
        
        return tabs
    
    def _create_chat_tab(self) -> QWidget:
        """Create integrated chat tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Welcome message
        welcome = QLabel("👋 Hi! I'm KI-ana. Ask me anything about your system!")
        welcome.setFont(QFont("Arial", 12))
        welcome.setStyleSheet("padding: 10px; background-color: #667eea; border-radius: 6px;")
        layout.addWidget(welcome)
        
        # Chat history
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("Chat history will appear here...")
        layout.addWidget(self.chat_history)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type your message... (Try: 'Zeige System Info')")
        self.chat_input.returnPressed.connect(self._on_send_message)
        input_layout.addWidget(self.chat_input)
        
        voice_btn = QPushButton("🎙️ Voice")
        voice_btn.clicked.connect(self._on_voice_input)
        voice_btn.setToolTip("Click to speak (requires microphone)")
        input_layout.addWidget(voice_btn)
        self.voice_btn = voice_btn
        
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._on_send_message)
        input_layout.addWidget(send_btn)
        
        layout.addLayout(input_layout)
        
        return widget
    
    def _create_dashboard_tab(self) -> QWidget:
        """Create dashboard tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        title = QLabel("📊 System Dashboard")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # CPU
        cpu_label = QLabel("CPU Usage:")
        layout.addWidget(cpu_label)
        self.cpu_bar = QProgressBar()
        layout.addWidget(self.cpu_bar)
        
        # Memory
        mem_label = QLabel("Memory Usage:")
        layout.addWidget(mem_label)
        self.mem_bar = QProgressBar()
        layout.addWidget(self.mem_bar)
        
        # Disk
        disk_label = QLabel("Disk Usage:")
        layout.addWidget(disk_label)
        self.disk_bar = QProgressBar()
        layout.addWidget(self.disk_bar)
        
        layout.addStretch()
        
        return widget
    
    def _create_system_tab(self) -> QWidget:
        """Create system tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Info display
        self.system_info = QTextEdit()
        self.system_info.setReadOnly(True)
        self.system_info.setPlainText("Loading system information...")
        layout.addWidget(self.system_info)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        scan_btn = QPushButton("🔍 Scan Hardware")
        scan_btn.clicked.connect(lambda: self._run_command("Scanne Hardware"))
        btn_layout.addWidget(scan_btn)
        
        optimize_btn = QPushButton("🚀 Optimize System")
        optimize_btn.clicked.connect(lambda: self._run_command("Optimiere System"))
        btn_layout.addWidget(optimize_btn)
        
        health_btn = QPushButton("🏥 Health Check")
        health_btn.clicked.connect(lambda: self._run_command("Zeige System Health"))
        btn_layout.addWidget(health_btn)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def _on_send_message(self):
        """Handle send message"""
        message = self.chat_input.text().strip()
        if not message:
            return
        
        # Show user message
        self.chat_history.append(f"<b>You:</b> {message}")
        self.chat_input.clear()
        self.chat_input.setEnabled(False)
        
        # Show thinking
        self.chat_history.append("<i>KI-ana: Thinking...</i>")
        self.statusBar().showMessage("Processing...")
        
        # Process with AI Brain in background
        self._run_command(message)
    
    def _run_command(self, command: str):
        """Run command with AI Brain"""
        # Create worker thread
        self.worker = BrainWorker(command)
        self.worker.finished.connect(self._on_command_finished)
        self.worker.start()
    
    def _on_command_finished(self, result: dict):
        """Handle command completion"""
        self.chat_input.setEnabled(True)
        self.statusBar().showMessage("Ready")
        
        # Remove "thinking" message
        text = self.chat_history.toPlainText()
        if "Thinking..." in text:
            lines = text.split('\n')
            text = '\n'.join(lines[:-1])
            self.chat_history.setPlainText(text)
        
        # Show response
        if result.get("success"):
            response = result.get("response", "No response")
            self.chat_history.append(f"<b style='color: #667eea;'>KI-ana:</b> {response}")
            
            # Speak response if voice was used
            if hasattr(self, '_last_was_voice') and self._last_was_voice:
                self._speak_response(response)
                self._last_was_voice = False
            
            # Update system info if available
            if result.get("result", {}).get("data"):
                data = result["result"]["data"]
                self.system_info.setPlainText(str(data))
        else:
            error = result.get("error", "Unknown error")
            error_html = f"<span style='color: #ef4444; font-weight: bold;'>❌ Error:</span> {error}"
            
            # Add recovery suggestions if available
            suggestions = result.get("recovery_suggestions", [])
            if suggestions:
                error_html += "<br><br><span style='color: #fbbf24;'>💡 Vorschläge:</span><ul>"
                for suggestion in suggestions[:3]:
                    error_html += f"<li>{suggestion}</li>"
                error_html += "</ul>"
            
            self.chat_history.append(error_html)
    
    def _speak_response(self, text: str):
        """Speak response via TTS"""
        try:
            from PyQt5.QtCore import QThread
            
            class TTSWorker(QThread):
                def __init__(self, text):
                    super().__init__()
                    self.text = text
                
                def run(self):
                    try:
                        import asyncio
                        from core.voice.text_to_speech import get_tts
                        
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        async def speak():
                            tts = await get_tts()
                            if tts.is_available:
                                await tts.speak(self.text, play=True)
                        
                        loop.run_until_complete(speak())
                    except Exception as e:
                        logger.error(f"TTS error: {e}")
            
            worker = TTSWorker(text)
            worker.start()
        except Exception as e:
            logger.error(f"Speak response error: {e}")
    
    def _on_voice_input(self):
        """Handle voice input"""
        self.chat_history.append("🎙️ Listening... (5 seconds)")
        self.voice_btn.setEnabled(False)
        self.statusBar().showMessage("🎤 Listening...")
        
        # Start voice input in thread
        from PyQt5.QtCore import QThread, pyqtSignal
        
        class VoiceWorker(QThread):
            finished = pyqtSignal(str)
            error = pyqtSignal(str)
            
            def run(self):
                try:
                    import asyncio
                    import sys
                    from pathlib import Path
                    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                    from core.voice.speech_to_text import get_stt
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    async def listen():
                        stt = await get_stt()
                        if stt.is_available:
                            return await stt.listen_and_transcribe(duration=5)
                        else:
                            return None
                    
                    result = loop.run_until_complete(listen())
                    if result:
                        self.finished.emit(result)
                    else:
                        self.error.emit("Voice recognition not available. Install: pip install openai-whisper sounddevice soundfile")
                except Exception as e:
                    self.error.emit(f"Voice error: {str(e)}")
        
        self.voice_worker = VoiceWorker()
        self.voice_worker.finished.connect(self._on_voice_finished)
        self.voice_worker.error.connect(self._on_voice_error)
        self.voice_worker.start()
    
    def _on_voice_finished(self, text: str):
        """Handle voice recognition result"""
        self.voice_btn.setEnabled(True)
        self.statusBar().showMessage("Ready")
        self._last_was_voice = True
        
        # Set text and send
        self.chat_input.setText(text)
        self._on_send_message()
    
    def _on_voice_error(self, error: str):
        """Handle voice error"""
        self.voice_btn.setEnabled(True)
        self.statusBar().showMessage("Ready")
        
        # Remove "Listening..." message
        text = self.chat_history.toPlainText()
        lines = text.split('\n')
        if lines and "Listening..." in lines[-1]:
            text = '\n'.join(lines[:-1])
            self.chat_history.setPlainText(text)
        
        self.chat_history.append(f"<span style='color: #fbbf24;'>⚠️ {error}</span>")
    
    def start_monitoring(self):
        """Start real-time monitoring"""
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self._update_dashboard)
        self.monitor_timer.start(2000)  # Update every 2 seconds
        
    def _update_dashboard(self):
        """Update dashboard with real data"""
        try:
            import psutil
            
            # CPU
            cpu = psutil.cpu_percent(interval=0.1)
            self.cpu_bar.setValue(int(cpu))
            
            # Memory
            mem = psutil.virtual_memory().percent
            self.mem_bar.setValue(int(mem))
            
            # Disk
            disk = psutil.disk_usage('/').percent
            self.disk_bar.setValue(int(disk))
            
            # Update status
            if cpu > 80 or mem > 85:
                self.status_label.setText("⚠️ High Usage")
                self.status_label.setStyleSheet("color: #fbbf24; font-weight: bold;")
            else:
                self.status_label.setText("● System Healthy")
                self.status_label.setStyleSheet("color: #4ade80; font-weight: bold;")
                
        except Exception as e:
            logger.error(f"Monitor update error: {e}")


def main():
    """Launch integrated window"""
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    app.setApplicationName("KI-ana OS")
    
    window = IntegratedMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
