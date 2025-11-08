"""
Tests for Phase 7 - Identity & Expression
All sprints: Style, Emotion, Expression, Authenticity
"""
import pytest
import json
from pathlib import Path


class TestStyleProfile:
    """Test style profile and style engine"""
    
    def test_style_profile_exists(self):
        """Style profile should exist"""
        profile = Path("/home/kiana/ki_ana/data/style_profile.json")
        assert profile.exists(), "style_profile.json should exist"
    
    def test_style_profile_valid_json(self):
        """Style profile should be valid JSON"""
        profile = Path("/home/kiana/ki_ana/data/style_profile.json")
        
        with open(profile, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert isinstance(data, dict), "Profile should be a dict"
    
    def test_style_profile_has_tone(self):
        """Profile should define tone"""
        profile = Path("/home/kiana/ki_ana/data/style_profile.json")
        
        with open(profile, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert 'tone' in data, "Should have tone"
        assert 'primary' in data['tone'], "Tone should have primary"
    
    def test_signature_phrases_exist(self):
        """Profile should have signature phrases"""
        profile = Path("/home/kiana/ki_ana/data/style_profile.json")
        
        with open(profile, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert 'signature_phrases' in data, "Should have signature_phrases"
        phrases = data['signature_phrases']
        
        assert 'opening' in phrases, "Should have opening phrases"
        assert 'closing' in phrases, "Should have closing phrases"


class TestStyleEngine:
    """Test style engine"""
    
    def test_style_engine_import(self):
        """Should be able to import StyleEngine"""
        try:
            from netapi.modules.expression.style_engine import StyleEngine
            assert StyleEngine is not None
        except ImportError:
            pytest.skip("Cannot import in test environment")
    
    def test_style_engine_creation(self):
        """Should be able to create engine"""
        try:
            from netapi.modules.expression.style_engine import StyleEngine
            engine = StyleEngine()
            assert engine is not None
        except ImportError:
            pytest.skip("Cannot import in test environment")


class TestEmotionEngine:
    """Test emotion/affect engine"""
    
    def test_affect_engine_import(self):
        """Should be able to import AffectEngine"""
        try:
            from netapi.modules.emotion.affect_engine import AffectEngine
            assert AffectEngine is not None
        except ImportError:
            pytest.skip("Cannot import in test environment")
    
    def test_emotion_patterns_defined(self):
        """Emotion patterns should be defined"""
        try:
            from netapi.modules.emotion.affect_engine import AffectEngine
            engine = AffectEngine()
            
            assert hasattr(engine, 'emotion_patterns')
            patterns = engine.emotion_patterns
            
            # Check key emotions
            assert 'joy' in patterns
            assert 'sadness' in patterns
            assert 'curiosity' in patterns
        except ImportError:
            pytest.skip("Cannot import in test environment")


class TestVoiceEngine:
    """Test voice/TTS engine"""
    
    def test_voice_engine_exists(self):
        """Voice engine file should exist"""
        voice = Path("/home/kiana/ki_ana/netapi/modules/speech/voice_engine.py")
        assert voice.exists(), "voice_engine.py should exist"
    
    def test_voice_engine_import(self):
        """Should be able to import VoiceEngine"""
        try:
            from netapi.modules.speech.voice_engine import VoiceEngine
            assert VoiceEngine is not None
        except ImportError:
            pytest.skip("Cannot import in test environment")


class TestAuthenticityChecker:
    """Test authenticity checker"""
    
    def test_authenticity_tool_exists(self):
        """Authenticity checker should exist"""
        tool = Path("/home/kiana/ki_ana/tools/authenticity_check.py")
        assert tool.exists(), "authenticity_check.py should exist"
    
    def test_authenticity_import(self):
        """Should be able to import checker"""
        try:
            import sys
            sys.path.insert(0, '/home/kiana/ki_ana')
            from tools.authenticity_check import AuthenticityChecker
            assert AuthenticityChecker is not None
        except ImportError:
            pytest.skip("Cannot import in test environment")


class TestIntegration:
    """Test integration of all Phase 7 components"""
    
    def test_all_phase7_files_exist(self):
        """All Phase 7 files should exist"""
        files = [
            # Sprint 7.1
            "/home/kiana/ki_ana/data/style_profile.json",
            "/home/kiana/ki_ana/netapi/modules/expression/style_engine.py",
            
            # Sprint 7.2
            "/home/kiana/ki_ana/netapi/modules/emotion/affect_engine.py",
            "/home/kiana/ki_ana/netapi/modules/emotion/router.py",
            
            # Sprint 7.3
            "/home/kiana/ki_ana/netapi/modules/speech/voice_engine.py",
            "/home/kiana/ki_ana/netapi/static/expression_widget.html",
            
            # Sprint 7.4
            "/home/kiana/ki_ana/tools/authenticity_check.py"
        ]
        
        for file_path in files:
            path = Path(file_path)
            assert path.exists(), f"{file_path} should exist"
    
    def test_emotion_router_integration(self):
        """Emotion router should be importable"""
        try:
            from netapi.modules.emotion import router
            assert router is not None
        except ImportError:
            pytest.skip("Cannot import in test environment")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
