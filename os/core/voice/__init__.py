"""
KI-ana OS - Voice Interface

Speech-to-Text and Text-to-Speech for conversational OS.
"""

from .speech_to_text import SpeechToText
from .text_to_speech import TextToSpeech
from .voice_controller import VoiceController

__all__ = ["SpeechToText", "TextToSpeech", "VoiceController"]
