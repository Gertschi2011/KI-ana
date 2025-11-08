"""
Tests for System Map Module
Sprint 6.1 - Self-Awareness
"""
import pytest
import json
from pathlib import Path


class TestSystemMap:
    """Test system map functionality"""
    
    def test_system_map_file_exists(self):
        """System map file should exist"""
        map_file = Path("/home/kiana/ki_ana/data/system_map.json")
        assert map_file.exists(), "system_map.json should exist"
    
    def test_system_map_valid_json(self):
        """System map should be valid JSON"""
        map_file = Path("/home/kiana/ki_ana/data/system_map.json")
        
        with open(map_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert isinstance(data, dict), "System map should be a dictionary"
    
    def test_system_map_required_fields(self):
        """System map should have required fields"""
        map_file = Path("/home/kiana/ki_ana/data/system_map.json")
        
        with open(map_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        required_fields = ['version', 'name', 'core', 'capabilities', 'features']
        
        for field in required_fields:
            assert field in data, f"System map should have '{field}' field"
    
    def test_system_map_version_format(self):
        """Version should be in semantic versioning format"""
        map_file = Path("/home/kiana/ki_ana/data/system_map.json")
        
        with open(map_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        version = data.get('version', '')
        assert len(version.split('.')) >= 2, "Version should be semantic (e.g., 6.0.0)"
    
    def test_core_modules_list(self):
        """Core modules should be a non-empty list"""
        map_file = Path("/home/kiana/ki_ana/data/system_map.json")
        
        with open(map_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        core = data.get('core', [])
        assert isinstance(core, list), "Core should be a list"
        assert len(core) > 0, "Core should have at least one module"
    
    def test_capabilities_structure(self):
        """Capabilities should be a dictionary of booleans"""
        map_file = Path("/home/kiana/ki_ana/data/system_map.json")
        
        with open(map_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        capabilities = data.get('capabilities', {})
        assert isinstance(capabilities, dict), "Capabilities should be a dictionary"
        
        # Check that at least some capabilities exist
        assert len(capabilities) > 0, "Should have at least one capability"
        
        # Check that values are booleans
        for key, value in capabilities.items():
            assert isinstance(value, bool), f"Capability '{key}' should be boolean"
    
    def test_features_has_implemented(self):
        """Features should have implemented list"""
        map_file = Path("/home/kiana/ki_ana/data/system_map.json")
        
        with open(map_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        features = data.get('features', {})
        assert 'implemented' in features, "Features should have 'implemented' list"
        assert isinstance(features['implemented'], list), "'implemented' should be a list"
    
    def test_metadata_exists(self):
        """Metadata should exist with deployment info"""
        map_file = Path("/home/kiana/ki_ana/data/system_map.json")
        
        with open(map_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert 'metadata' in data, "Should have metadata"
        metadata = data['metadata']
        
        expected_fields = ['deployment_date', 'last_major_update']
        for field in expected_fields:
            assert field in metadata, f"Metadata should have '{field}'"


class TestSystemMapLoader:
    """Test system map loader functionality"""
    
    def test_loader_import(self):
        """Should be able to import system_map module"""
        try:
            from netapi.modules.self.system_map import get_system_map
            assert callable(get_system_map)
        except ImportError as e:
            pytest.fail(f"Failed to import system_map: {e}")
    
    def test_get_system_map_returns_dict(self):
        """get_system_map should return a dictionary"""
        from netapi.modules.self.system_map import get_system_map
        
        result = get_system_map(include_dynamic=False)
        assert isinstance(result, dict), "get_system_map should return a dict"
    
    def test_get_system_summary(self):
        """get_system_summary should return condensed info"""
        from netapi.modules.self.system_map import get_system_summary
        
        summary = get_system_summary()
        assert isinstance(summary, dict), "Summary should be a dict"
        assert 'version' in summary, "Summary should have version"
        assert 'name' in summary, "Summary should have name"
    
    def test_explain_capability(self):
        """Should explain known capabilities"""
        from netapi.modules.self.system_map import explain_capability
        
        # Test known capability
        explanation = explain_capability("out_of_box_thinking")
        assert explanation is not None, "Should explain known capability"
        assert isinstance(explanation, str), "Explanation should be a string"
        
        # Test unknown capability
        unknown = explain_capability("nonexistent_capability")
        assert unknown is None, "Unknown capability should return None"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
