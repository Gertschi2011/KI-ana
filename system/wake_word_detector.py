"""
Wake Word Detector für KI_ana

Features:
- Wake-Word Detection ("Hey KI_ana")
- Continuous Listening
- Low-Latency
- Privacy-Preserving (lokal)
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional, Callable
import threading
import time

# Add system path
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))

# Try to import porcupine (wake word detection)
try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False
    print("⚠️  Porcupine not available. Install with: pip install pvporcupine")

# Try to import pyaudio
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("⚠️  PyAudio not available. Install with: pip install pyaudio")


class WakeWordDetector:
    """
    Wake Word Detector using Porcupine.
    
    Listens for "Hey KI_ana" or custom wake word.
    """
    
    _instance: Optional['WakeWordDetector'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        if not PORCUPINE_AVAILABLE or not PYAUDIO_AVAILABLE:
            print("❌ Wake word detection not available")
            self._initialized = True
            return
        
        self._initialized = True
        
        # Porcupine instance
        self.porcupine = None
        self.audio_stream = None
        self.pa = None
        
        # State
        self.is_listening = False
        self.detection_thread = None
        
        # Callback
        self.on_wake_word: Optional[Callable] = None
        
        print(f"✅ Wake Word Detector initialized")
    
    def start(self, wake_word: str = "hey google", callback: Callable = None):
        """
        Start listening for wake word.
        
        Args:
            wake_word: Wake word to detect (default: "hey google")
                      Available: "hey google", "alexa", "computer", etc.
            callback: Function to call when wake word is detected
        """
        if not PORCUPINE_AVAILABLE or not PYAUDIO_AVAILABLE:
            print("❌ Cannot start: dependencies not available")
            return
        
        if self.is_listening:
            print("⚠️  Already listening")
            return
        
        self.on_wake_word = callback
        
        try:
            # Initialize Porcupine
            # Note: Requires access key from Picovoice Console
            # For demo, using built-in keywords
            self.porcupine = pvporcupine.create(
                keywords=[wake_word]
            )
            
            # Initialize PyAudio
            self.pa = pyaudio.PyAudio()
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length
            )
            
            self.is_listening = True
            
            # Start detection thread
            self.detection_thread = threading.Thread(target=self._detection_loop)
            self.detection_thread.daemon = True
            self.detection_thread.start()
            
            print(f"🎤 Listening for wake word: '{wake_word}'")
            
        except Exception as e:
            print(f"❌ Error starting wake word detection: {e}")
            self.stop()
    
    def _detection_loop(self):
        """Main detection loop."""
        while self.is_listening:
            try:
                # Read audio
                pcm = self.audio_stream.read(self.porcupine.frame_length)
                pcm = [int.from_bytes(pcm[i:i+2], byteorder='little', signed=True) 
                       for i in range(0, len(pcm), 2)]
                
                # Process audio
                keyword_index = self.porcupine.process(pcm)
                
                if keyword_index >= 0:
                    print("🎤 Wake word detected!")
                    
                    # Call callback
                    if self.on_wake_word:
                        self.on_wake_word()
                
            except Exception as e:
                print(f"⚠️  Detection error: {e}")
                time.sleep(0.1)
    
    def stop(self):
        """Stop listening."""
        self.is_listening = False
        
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.audio_stream = None
        
        if self.pa:
            self.pa.terminate()
            self.pa = None
        
        if self.porcupine:
            self.porcupine.delete()
            self.porcupine = None
        
        print("🛑 Wake word detection stopped")


# Singleton
_detector: Optional[WakeWordDetector] = None


def get_wake_word_detector() -> WakeWordDetector:
    """Get singleton wake word detector."""
    global _detector
    if _detector is None:
        _detector = WakeWordDetector()
    return _detector


if __name__ == "__main__":
    print("🎤 Wake Word Detector Test\n")
    
    if not PORCUPINE_AVAILABLE or not PYAUDIO_AVAILABLE:
        print("❌ Dependencies not available")
        print("\nInstall with:")
        print("  pip install pvporcupine pyaudio")
        exit(1)
    
    detector = get_wake_word_detector()
    
    def on_wake_word():
        print("✅ Wake word detected! KI_ana is listening...")
    
    print("Starting wake word detection...")
    print("Say 'Hey Google' to test (using built-in keyword)")
    print("Press Ctrl+C to stop\n")
    
    try:
        detector.start(wake_word="hey google", callback=on_wake_word)
        
        # Keep running
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\nStopping...")
        detector.stop()
    
    print("\n✅ Test complete!")
