"""
Voice Integration Patch

Add these methods to integrated_window.py after _speak_response method
"""

def _on_voice_input(self):
    """Handle voice input - WORKING VERSION"""
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
