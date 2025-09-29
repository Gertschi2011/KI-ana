"""
Placeholder for voice input integration (Whisper).

MVP scope:
- Define interfaces to transcribe audio to text.
- Allow passing language hints and diarization placeholders.
- Actual runtime integration with whisper.cpp or faster-whisper to be added later.
"""
from typing import Optional, Dict

class VoiceTranscriber:
    def __init__(self, engine: str = "none", model_path: Optional[str] = None):
        self.engine = engine
        self.model_path = model_path

    def transcribe(self, audio_path: str, *, lang_hint: str = "de", diarize: bool = False) -> Dict:
        """
        Returns a dict with keys:
          - text: str
          - segments: list (optional)
          - lang: str
        """
        # TODO: integrate with whisper.cpp or faster-whisper
        return {
            "text": "",  # real transcription to be implemented
            "segments": [],
            "lang": lang_hint or "de",
        }
