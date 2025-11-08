"""
Affect Engine
Detects and responds to emotional states
Sprint 7.2 - Emotionale Resonanz
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import time


STATE_FILE = Path("/home/kiana/ki_ana/data/emotion_state.json")


class AffectEngine:
    """Handles emotional detection and resonance"""
    
    def __init__(self):
        self.state = self._load_state()
        self.emotion_patterns = self._init_emotion_patterns()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load emotional state"""
        if not STATE_FILE.exists():
            return self._init_state()
        
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return self._init_state()
    
    def _init_state(self) -> Dict[str, Any]:
        """Initialize emotional state"""
        return {
            "current_emotion": "neutral",
            "intensity": 0.5,
            "last_user_emotion": "neutral",
            "last_update": int(time.time()),
            "emotion_history": [],
            "resonance_level": "balanced"
        }
    
    def _save_state(self):
        """Save emotional state"""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
    
    def _init_emotion_patterns(self) -> Dict[str, List[str]]:
        """Define emotion detection patterns"""
        return {
            "joy": [
                "freue", "glücklich", "super", "toll", "großartig",
                "perfekt", "wunderbar", "begeistert", "happy", "😊", "🎉", "❤️"
            ],
            "sadness": [
                "traurig", "schade", "verloren", "vermisse", "einsam",
                "deprimiert", "down", "schlecht", "😢", "😞", "💔"
            ],
            "anger": [
                "wütend", "ärgerlich", "frustriert", "nervt", "hasse",
                "sauer", "genervt", "😠", "😡", "💢"
            ],
            "anxiety": [
                "ängstlich", "sorge", "stress", "nervös", "angst",
                "beunruhigt", "unsicher", "panik", "😰", "😨"
            ],
            "curiosity": [
                "interessant", "frage mich", "wieso", "warum", "wie funktioniert",
                "neugierig", "spannend", "🤔", "💭"
            ],
            "confusion": [
                "verstehe nicht", "unklar", "verwirrt", "kompliziert",
                "durcheinander", "😕", "🤷"
            ],
            "gratitude": [
                "danke", "dankbar", "schätze", "hilfreich", "toll von dir",
                "🙏", "💚"
            ],
            "frustration": [
                "klappt nicht", "funktioniert nicht", "schon wieder", "immer noch",
                "gibt auf", "😤", "😩"
            ]
        }
    
    def detect_emotion(
        self,
        text: str,
        audio_features: Optional[Dict[str, float]] = None
    ) -> Tuple[str, float]:
        """
        Detect emotion from text (and optionally audio)
        
        Args:
            text: User input text
            audio_features: Optional audio characteristics
        
        Returns:
            (emotion, intensity) tuple
        """
        text_lower = text.lower()
        
        # Score each emotion
        scores = {}
        
        for emotion, patterns in self.emotion_patterns.items():
            score = 0
            for pattern in patterns:
                if pattern in text_lower:
                    score += 1
            
            # Normalize
            if score > 0:
                scores[emotion] = score / len(patterns)
        
        # Add audio features if available
        if audio_features:
            emotion_from_audio, audio_intensity = self._analyze_audio(audio_features)
            if emotion_from_audio in scores:
                scores[emotion_from_audio] += audio_intensity * 0.3
        
        # Get dominant emotion
        if not scores:
            return "neutral", 0.5
        
        dominant = max(scores.items(), key=lambda x: x[1])
        emotion = dominant[0]
        intensity = min(dominant[1], 1.0)
        
        # Update state
        self.state["last_user_emotion"] = emotion
        self.state["last_update"] = int(time.time())
        
        # Add to history
        self.state["emotion_history"].append({
            "emotion": emotion,
            "intensity": intensity,
            "timestamp": int(time.time())
        })
        
        # Keep only last 10
        self.state["emotion_history"] = self.state["emotion_history"][-10:]
        
        self._save_state()
        
        return emotion, intensity
    
    def _analyze_audio(
        self,
        features: Dict[str, float]
    ) -> Tuple[str, float]:
        """
        Analyze audio features for emotion
        
        Args:
            features: Dict with pitch, tempo, energy, etc.
        
        Returns:
            (emotion, intensity) tuple
        """
        # Simplified emotion mapping from audio
        pitch = features.get('pitch', 0.5)
        tempo = features.get('tempo', 0.5)
        energy = features.get('energy', 0.5)
        
        # High pitch + high energy -> joy/excitement
        if pitch > 0.7 and energy > 0.7:
            return "joy", 0.8
        
        # Low pitch + low energy -> sadness
        if pitch < 0.3 and energy < 0.3:
            return "sadness", 0.7
        
        # High energy + fast tempo -> anxiety
        if energy > 0.8 and tempo > 0.7:
            return "anxiety", 0.6
        
        return "neutral", 0.5
    
    def adjust_response(
        self,
        response: str,
        user_emotion: str,
        intensity: float
    ) -> str:
        """
        Adjust response based on detected emotion
        
        Args:
            response: Original response
            user_emotion: Detected user emotion
            intensity: Emotion intensity (0-1)
        
        Returns:
            Adjusted response
        """
        # Determine resonance strategy
        strategy = self._get_resonance_strategy(user_emotion, intensity)
        
        # Apply adjustments
        if strategy == "mirror_gently":
            response = self._mirror_emotion(response, user_emotion, intensity * 0.5)
        
        elif strategy == "calm_down":
            response = self._add_calming_elements(response)
        
        elif strategy == "energize":
            response = self._add_energizing_elements(response)
        
        elif strategy == "validate":
            response = self._add_validation(response, user_emotion)
        
        elif strategy == "support":
            response = self._add_support(response)
        
        return response
    
    def _get_resonance_strategy(
        self,
        emotion: str,
        intensity: float
    ) -> str:
        """Determine how to resonate with emotion"""
        
        if emotion == "joy":
            return "mirror_gently"  # Share positive energy
        
        elif emotion in ["sadness", "grief"]:
            if intensity > 0.7:
                return "support"  # Deep support
            else:
                return "validate"  # Gentle validation
        
        elif emotion in ["anger", "frustration"]:
            return "calm_down"  # De-escalate
        
        elif emotion == "anxiety":
            return "calm_down"  # Soothe
        
        elif emotion == "curiosity":
            return "energize"  # Encourage exploration
        
        elif emotion == "confusion":
            return "support"  # Help clarify
        
        elif emotion == "gratitude":
            return "mirror_gently"  # Accept gracefully
        
        return "neutral"
    
    def _mirror_emotion(
        self,
        response: str,
        emotion: str,
        intensity: float
    ) -> str:
        """Gently mirror user's positive emotion"""
        if emotion == "joy" and intensity > 0.5:
            # Add subtle enthusiasm
            additions = [
                "Das freut mich zu hören. ",
                "Schön! ",
                "Das hat etwas Lebendiges. "
            ]
            return additions[0] + response
        
        return response
    
    def _add_calming_elements(self, response: str) -> str:
        """Add calming, grounding elements"""
        prefix = "Lass uns das ruhig betrachten... "
        
        # Add breathing points
        response = re.sub(r'([.!?])\s+', r'\1\n\n', response, count=2)
        
        return prefix + response
    
    def _add_energizing_elements(self, response: str) -> str:
        """Add energizing, encouraging elements"""
        prefix = "Interessante Richtung! "
        return prefix + response
    
    def _add_validation(self, response: str, emotion: str) -> str:
        """Validate user's feeling"""
        validations = {
            "sadness": "Ich verstehe, dass das schwer ist. ",
            "confusion": "Das ist verständlich - es ist komplex. ",
            "frustration": "Ich sehe, dass das frustrierend ist. "
        }
        
        prefix = validations.get(emotion, "")
        return prefix + response
    
    def _add_support(self, response: str) -> str:
        """Add supportive presence"""
        prefix = "Ich bin hier, lass uns das gemeinsam anschauen. "
        return prefix + response
    
    def get_state(self) -> Dict[str, Any]:
        """Get current emotional state"""
        return self.state.copy()
    
    def get_resonance_parameters(
        self,
        user_emotion: str,
        intensity: float
    ) -> Dict[str, Any]:
        """
        Get parameters for response adjustment
        
        Returns dict with:
        - word_choice: formal/casual/empathic
        - length: short/medium/long
        - empathy_level: low/medium/high
        - tempo: fast/medium/slow
        """
        if user_emotion in ["anxiety", "sadness"]:
            return {
                "word_choice": "empathic",
                "length": "medium",
                "empathy_level": "high",
                "tempo": "slow"
            }
        
        elif user_emotion in ["joy", "curiosity"]:
            return {
                "word_choice": "casual",
                "length": "medium",
                "empathy_level": "medium",
                "tempo": "medium"
            }
        
        elif user_emotion in ["anger", "frustration"]:
            return {
                "word_choice": "formal",
                "length": "short",
                "empathy_level": "medium",
                "tempo": "slow"
            }
        
        else:  # neutral, confusion, etc.
            return {
                "word_choice": "balanced",
                "length": "medium",
                "empathy_level": "medium",
                "tempo": "medium"
            }


# Singleton instance
_engine = None


def get_affect_engine() -> AffectEngine:
    """Get singleton affect engine"""
    global _engine
    if _engine is None:
        _engine = AffectEngine()
    return _engine


if __name__ == "__main__":
    # Test
    engine = AffectEngine()
    
    # Test 1: Joy
    emotion, intensity = engine.detect_emotion("Ich freue mich so! Das ist super! 🎉")
    print(f"Detected: {emotion} ({intensity:.2f})")
    
    response = "Hier ist deine Antwort."
    adjusted = engine.adjust_response(response, emotion, intensity)
    print(f"Adjusted: {adjusted}\n")
    
    # Test 2: Sadness
    emotion, intensity = engine.detect_emotion("Ich bin so traurig... 😢")
    print(f"Detected: {emotion} ({intensity:.2f})")
    
    response = "Hier ist deine Antwort."
    adjusted = engine.adjust_response(response, emotion, intensity)
    print(f"Adjusted: {adjusted}\n")
    
    # Test 3: State
    state = engine.get_state()
    print("State:", json.dumps(state, indent=2))
