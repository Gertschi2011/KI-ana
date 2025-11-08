"""
Multimodal Module - Vision, Audio, and Video Processing

Provides the AI with multi-modal understanding capabilities.
"""
from .vision_processor import VisionProcessor, get_vision_processor
from .audio_processor import AudioProcessor, get_audio_processor

__all__ = [
    "VisionProcessor",
    "get_vision_processor",
    "AudioProcessor",
    "get_audio_processor",
]
