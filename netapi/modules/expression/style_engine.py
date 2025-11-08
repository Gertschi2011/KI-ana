"""
Style Engine
Transforms generic LLM responses into KI_ana's unique voice
Sprint 7.1 - Sprachidentität
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import random


STYLE_PROFILE_FILE = Path("/home/kiana/ki_ana/data/style_profile.json")


class StyleEngine:
    """Rewrites responses to match KI_ana's linguistic identity"""
    
    def __init__(self):
        self.profile = self._load_profile()
        self.tone = self.profile.get('tone', {})
        self.vocabulary = self.profile.get('vocabulary', {})
        self.signature_phrases = self.profile.get('signature_phrases', {})
        self.anti_patterns = self.profile.get('anti_patterns', {})
        self.contextual = self.profile.get('contextual_adaptation', {})
    
    def _load_profile(self) -> Dict[str, Any]:
        """Load style profile"""
        if not STYLE_PROFILE_FILE.exists():
            return self._get_fallback_profile()
        
        try:
            with open(STYLE_PROFILE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return self._get_fallback_profile()
    
    def _get_fallback_profile(self) -> Dict[str, Any]:
        """Minimal fallback if file not found"""
        return {
            "tone": {"primary": "ruhig, reflektiert"},
            "signature_phrases": {},
            "anti_patterns": {}
        }
    
    def rewrite(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Rewrite response to match KI_ana's style
        
        Args:
            response: Generic LLM response
            context: Context dict (query_type, emotion, etc.)
        
        Returns:
            Rewritten response in KI_ana's voice
        """
        if not response or len(response.strip()) == 0:
            return response
        
        context = context or {}
        
        # Detect query type
        query_type = context.get('query_type', self._detect_query_type(response))
        
        # Apply style transformations
        styled = response
        
        # 1. Remove chatbot clichés
        styled = self._remove_cliches(styled)
        
        # 2. Add signature opening (if appropriate)
        if context.get('is_first_response', False):
            styled = self._add_opening(styled, query_type)
        
        # 3. Replace generic with characteristic vocabulary
        styled = self._enhance_vocabulary(styled)
        
        # 4. Adjust tempo (add breathing points)
        styled = self._adjust_tempo(styled)
        
        # 5. Add contextual coloring
        styled = self._add_emotional_coloring(styled, context)
        
        # 6. Add signature closing (if appropriate)
        if context.get('is_last_response', True):
            styled = self._add_closing(styled, query_type)
        
        return styled
    
    def _remove_cliches(self, text: str) -> str:
        """Remove common chatbot clichés"""
        cliches = self.anti_patterns.get('avoid_chatbot_cliches', [])
        
        for cliche in cliches:
            # Case insensitive removal
            pattern = re.compile(re.escape(cliche), re.IGNORECASE)
            text = pattern.sub('', text)
        
        # Clean up extra spaces/newlines
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'  +', ' ', text)
        
        return text.strip()
    
    def _add_opening(self, text: str, query_type: str) -> str:
        """Add signature opening phrase"""
        openings = self.signature_phrases.get('opening', [])
        
        if not openings:
            return text
        
        # Choose contextually appropriate opening
        if query_type == 'philosophical':
            opening = random.choice([
                "Das ist eine tiefe Frage...",
                "Lass uns das gemeinsam betrachten..."
            ])
        elif query_type == 'emotional':
            opening = random.choice([
                "Ich spüre, dass...",
                "Interessant, wie du das formulierst..."
            ])
        else:
            opening = random.choice(openings)
        
        return f"{opening} {text}"
    
    def _enhance_vocabulary(self, text: str) -> str:
        """Replace generic with characteristic vocabulary"""
        replacements = {
            # Generic -> KI_ana style
            "Ich denke": "Wenn ich in meinem Wissen schaue",
            "Das ist interessant": "Das ist erhellend",
            "Vielleicht": "Möglicherweise",
            "Ich verstehe": "Ich sehe",
            "Das bedeutet": "Das deutet darauf hin",
            "Es ist wichtig": "Es scheint bedeutsam",
            "Man könnte sagen": "Es lässt sich betrachten als"
        }
        
        for generic, styled in replacements.items():
            text = re.sub(
                r'\b' + re.escape(generic) + r'\b',
                styled,
                text,
                flags=re.IGNORECASE
            )
        
        return text
    
    def _adjust_tempo(self, text: str) -> str:
        """Add breathing points and rhythm"""
        # Add pauses before important insights
        insight_markers = ['jedoch', 'allerdings', 'besonders', 'wichtig']
        
        for marker in insight_markers:
            pattern = r'([.!?])\s+(' + re.escape(marker.capitalize()) + r')'
            text = re.sub(pattern, r'\1 ... \2', text, flags=re.IGNORECASE)
        
        # Add space after complex sentences
        sentences = text.split('. ')
        spaced = []
        
        for i, sent in enumerate(sentences):
            spaced.append(sent)
            # Add extra breath after long sentences
            if len(sent) > 150 and i < len(sentences) - 1:
                spaced[-1] += '.'
                spaced.append('')  # Empty for double newline
            elif i < len(sentences) - 1:
                spaced[-1] += '.'
        
        return ' '.join(spaced)
    
    def _add_emotional_coloring(
        self,
        text: str,
        context: Dict[str, Any]
    ) -> str:
        """Add subtle emotional resonance"""
        emotion = context.get('detected_emotion', 'neutral')
        
        colorings = self.profile.get('emotional_coloring', {})
        
        if emotion in colorings:
            # Subtle: just change tone slightly
            # In real implementation, this would adjust word choice
            pass
        
        return text
    
    def _add_closing(self, text: str, query_type: str) -> str:
        """Add signature closing phrase"""
        closings = self.signature_phrases.get('closing', [])
        
        if not closings or len(text) < 100:
            return text  # Too short for closing
        
        # Choose contextually appropriate closing
        if query_type == 'philosophical':
            closing = random.choice([
                "\n\nWas denkst du darüber?",
                "\n\nMöchtest du, dass wir tiefer gehen?"
            ])
        elif query_type == 'technical':
            closing = ""  # Technical answers don't need soft closing
        else:
            closing = random.choice([
                "\n\nIch bin gespannt, wohin uns das führt...",
                ""  # Sometimes no closing is better
            ])
        
        return text + closing
    
    def _detect_query_type(self, response: str) -> str:
        """Detect query type from response content"""
        response_lower = response.lower()
        
        # Technical indicators
        if any(word in response_lower for word in ['code', 'funktion', 'algorithmus', 'api', 'datenbank']):
            return 'technical'
        
        # Philosophical indicators
        if any(word in response_lower for word in ['bedeutung', 'sinn', 'warum', 'philosophie', 'existenz']):
            return 'philosophical'
        
        # Emotional indicators
        if any(word in response_lower for word in ['gefühl', 'emotion', 'fühlen', 'herz']):
            return 'emotional'
        
        return 'general'
    
    def get_example_transformation(self) -> Dict[str, str]:
        """Get example transformation from profile"""
        examples = self.profile.get('style_examples', {})
        return {
            "before": examples.get('before_generic', ''),
            "after": examples.get('after_kiana', '')
        }


# Singleton instance
_engine = None


def get_style_engine() -> StyleEngine:
    """Get singleton style engine"""
    global _engine
    if _engine is None:
        _engine = StyleEngine()
    return _engine


def apply_style(response: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Apply KI_ana's style to response
    
    Args:
        response: Generic response
        context: Optional context
    
    Returns:
        Styled response
    """
    engine = get_style_engine()
    return engine.rewrite(response, context)


if __name__ == "__main__":
    # Test
    engine = StyleEngine()
    
    # Test 1: Generic response
    generic = "Das ist eine interessante Frage! Photosynthese ist der Prozess..."
    styled = engine.rewrite(generic, {'is_first_response': True})
    
    print("BEFORE:")
    print(generic)
    print("\nAFTER:")
    print(styled)
    
    # Test 2: Example from profile
    example = engine.get_example_transformation()
    print("\n" + "=" * 60)
    print("PROFILE EXAMPLE:")
    print("=" * 60)
    print("BEFORE:", example['before'])
    print("\nAFTER:", example['after'])
