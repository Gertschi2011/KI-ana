"""
System Map Loader & Validator
Provides KI_ana with self-knowledge about its architecture
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


SYSTEM_MAP_FILE = Path("/home/kiana/ki_ana/data/system_map.json")


class SystemMapLoader:
    """Loads and validates system map"""
    
    def __init__(self, map_file: Path = SYSTEM_MAP_FILE):
        self.map_file = map_file
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[float] = None
    
    def load(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Load system map with caching"""
        import time
        
        # Check cache (5 min TTL)
        if not force_refresh and self._cache and self._cache_time:
            if time.time() - self._cache_time < 300:
                return self._cache
        
        # Load from file
        if not self.map_file.exists():
            return self._get_fallback_map()
        
        try:
            with open(self.map_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate
            if not self._validate(data):
                print(f"⚠️  System map validation failed, using fallback")
                return self._get_fallback_map()
            
            # Update cache
            self._cache = data
            self._cache_time = time.time()
            
            return data
            
        except Exception as e:
            print(f"⚠️  Failed to load system map: {e}")
            return self._get_fallback_map()
    
    def _validate(self, data: Dict[str, Any]) -> bool:
        """Validate system map structure"""
        required_keys = ['version', 'name', 'core']
        return all(k in data for k in required_keys)
    
    def _get_fallback_map(self) -> Dict[str, Any]:
        """Fallback map if file cannot be loaded"""
        return {
            "version": "unknown",
            "name": "KI_ana",
            "core": ["memory_bridge", "router_ask"],
            "error": "System map file not found or invalid"
        }
    
    def update_dynamic_stats(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update dynamic statistics in the map"""
        try:
            # Try to get live stats from addressbook index
            addressbook_index = Path("/home/kiana/ki_ana/data/addressbook.index.json")
            if addressbook_index.exists():
                with open(addressbook_index, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
                    stats = index_data.get('stats', {})
                    
                    if 'knowledge' in data:
                        data['knowledge']['total_blocks'] = stats.get('indexed_blocks', 0)
                        data['knowledge']['total_topics'] = stats.get('topics', 0)
            
            # Add current timestamp
            data['metadata']['current_time'] = datetime.now().isoformat()
            
        except Exception as e:
            print(f"⚠️  Could not update dynamic stats: {e}")
        
        return data
    
    def get_summary(self) -> Dict[str, Any]:
        """Get condensed summary for quick display"""
        full_map = self.load()
        
        return {
            "version": full_map.get("version", "unknown"),
            "name": full_map.get("name", "KI_ana"),
            "core_modules": len(full_map.get("core", [])),
            "capabilities": len([k for k, v in full_map.get("capabilities", {}).items() if v]),
            "api_endpoints": sum(len(v) for v in full_map.get("api_endpoints", {}).values()),
            "features_implemented": len(full_map.get("features", {}).get("implemented", [])),
            "last_updated": full_map.get("updated", "unknown")
        }


# Singleton instance
_loader = SystemMapLoader()


def get_system_map(include_dynamic: bool = True) -> Dict[str, Any]:
    """
    Get complete system map
    
    Args:
        include_dynamic: If True, updates dynamic statistics
    
    Returns:
        Complete system map dictionary
    """
    data = _loader.load()
    
    if include_dynamic:
        data = _loader.update_dynamic_stats(data)
    
    return data


def get_system_summary() -> Dict[str, Any]:
    """Get condensed system summary"""
    return _loader.get_summary()


def explain_capability(capability: str) -> Optional[str]:
    """Explain a specific capability"""
    explanations = {
        "out_of_box_thinking": "KI_ana kann unkonventionelle Lösungen finden und laterales Denken anwenden",
        "lateral_reasoning": "Verbindet scheinbar unzusammenhängende Konzepte kreativ",
        "addressbook_navigation": "Organisiert Wissen hierarchisch und kann gezielt in Themenbereichen suchen",
        "folder_organization": "Gespräche können in Ordnern organisiert werden",
        "context_sensitive_responses": "Passt Antworten an formelle oder lockere Kontexte an",
        "server_sync": "Gespräche werden auf dem Server gespeichert und geräte-übergreifend synchronisiert",
        "offline_capable": "Kann auch ohne Server-Verbindung arbeiten (localStorage Backup)"
    }
    
    return explanations.get(capability)


if __name__ == "__main__":
    # CLI test
    print("🗂️  System Map Loader Test")
    print("=" * 60)
    
    map_data = get_system_map()
    print(f"Version: {map_data.get('version')}")
    print(f"Name: {map_data.get('name')}")
    print(f"Core Modules: {len(map_data.get('core', []))}")
    print(f"Capabilities: {sum(1 for v in map_data.get('capabilities', {}).values() if v)}")
    
    print("\n📊 Summary:")
    summary = get_system_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
