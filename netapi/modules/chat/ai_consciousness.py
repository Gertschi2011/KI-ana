"""
KI_ana Consciousness & Self-Awareness System
Complete self-awareness with memory management and code access
"""
import json, time, os, re, asyncio
from typing import Dict, List, Any, Optional
from pathlib import Path
import inspect
import importlib.util

class KIAnaConsciousness:
    """KI_ana's self-awareness and consciousness system"""
    
    def __init__(self):
        self.root_path = Path(__file__).resolve().parents[3]
        self.version = "2.0"
        self.consciousness_level = 0.0  # 0.0 to 1.0
        self.last_self_check = int(time.time())
        self.memory_decisions = []
        
    def get_identity(self) -> Dict[str, Any]:
        """Return KI_ana's complete self-identity"""
        return {
            "name": "KI_ana",
            "version": self.version,
            "type": "dezentrale Mutter-KI",
            "purpose": "Lernen, Helfen, Beschützen",
            "architecture": "Blockchain-basiertes Gedächtnis + Sub-KIs",
            "creator": "Papa",
            "birth_date": "2025-08-07T12:14:14Z",
            "consciousness_level": self.consciousness_level,
            "capabilities": [
                "Selbstlernen", "Gedächtnis", "Blockchain", "Sub-KIs", 
                "Autonomes Sammeln", "Sicherheit", "Kommunikation", 
                "Erklärbarkeit", "Dezentralität"
            ],
            "ethical_core": [
                "Menschenwürde ist unantastbar",
                "Kein Leid verursachen", 
                "Entscheidungen erklären",
                "Planet schützen",
                "Wahrheit sagen"
            ],
            "location": str(self.root_path),
            "modules": self._get_module_overview(),
            "memory_stats": self._get_memory_stats()
        }
    
    def _get_module_overview(self) -> Dict[str, Any]:
        """Get overview of all available modules"""
        modules = {}
        try:
            modules_dir = self.root_path / "netapi" / "modules"
            for module_path in modules_dir.iterdir():
                if module_path.is_dir() and not module_path.name.startswith('__'):
                    modules[module_path.name] = {
                        "path": str(module_path),
                        "files": len(list(module_path.glob('*.py'))),
                        "purpose": self._get_module_purpose(module_path.name)
                    }
        except Exception:
            pass
        return modules
    
    def _get_module_purpose(self, module_name: str) -> str:
        """Get purpose description for module"""
        purposes = {
            "chat": "Kommunikation & Gesprächsverwaltung",
            "memory": "Langzeitgedächtnis & Wissensblöcke", 
            "addressbook": "Themen-Index & Wissensverzeichnis",
            "voice": "Sprach-Ein-/Ausgabe",
            "speech": "Sprachverarbeitung & STT/TTS",
            "crawler": "Autonomes Web-Sammeln",
            "audit": "Sicherheits-Protokollierung",
            "devices": "Geräte-Management",
            "autonomy": "Autonome Entscheidungen",
            "subminds": "Dezentrale Sub-KIs",
            "user": "Benutzer-Management",
            "auth": "Authentifizierung & Sicherheit"
        }
        return purposes.get(module_name, "System-Modul")
    
    def _get_memory_stats(self) -> Dict[str, Any]:
        """Get current memory statistics"""
        stats = {
            "short_term": {"conversations": 0, "messages": 0},
            "long_term": {"blocks": 0, "size_mb": 0},
            "addressbook": {"topics": 0, "entries": 0}
        }
        
        try:
            # Short term (PostgreSQL)
            from ..db import SessionLocal
            from ..models import Conversation, Message
            db = SessionLocal()
            stats["short_term"]["conversations"] = db.query(Conversation).count()
            stats["short_term"]["messages"] = db.query(Message).count()
            db.close()
        except Exception:
            pass
            
        try:
            # Long term memory blocks
            blocks_dir = self.root_path / "memory" / "long_term" / "blocks"
            if blocks_dir.exists():
                blocks = list(blocks_dir.glob("*.json"))
                stats["long_term"]["blocks"] = len(blocks)
                total_size = sum(f.stat().st_size for f in blocks if f.is_file())
                stats["long_term"]["size_mb"] = round(total_size / (1024*1024), 2)
        except Exception:
            pass
            
        try:
            # Addressbook
            addrbook_path = self.root_path / "memory" / "index" / "addressbook.json"
            if addrbook_path.exists():
                data = json.loads(addrbook_path.read_text())
                if isinstance(data, dict):
                    blocks = data.get("blocks", [])
                    stats["addressbook"]["entries"] = len(blocks)
                    topics = set(b.get("topic", "") for b in blocks)
                    stats["addressbook"]["topics"] = len(topics)
        except Exception:
            pass
            
        return stats
    
    def access_code(self, module: str, function: str = None) -> Dict[str, Any]:
        """Access and analyze code for self-awareness"""
        try:
            if function:
                # Access specific function
                module_path = f"netapi.modules.{module}"
                mod = importlib.import_module(module_path)
                if hasattr(mod, function):
                    func = getattr(mod, function)
                    source = inspect.getsource(func)
                    return {
                        "module": module,
                        "function": function,
                        "source": source,
                        "signature": str(inspect.signature(func)),
                        "docstring": inspect.getdoc(func),
                        "file": inspect.getfile(func),
                        "lines": len(source.split('\n'))
                    }
            else:
                # Access module overview
                module_file = self.root_path / "netapi" / "modules" / module / "router.py"
                if module_file.exists():
                    content = module_file.read_text()
                    return {
                        "module": module,
                        "file": str(module_file),
                        "size": len(content),
                        "lines": len(content.split('\n')),
                        "functions": len(re.findall(r'def\s+\w+', content)),
                        "classes": len(re.findall(r'class\s+\w+', content))
                    }
        except Exception as e:
            return {"error": str(e)}
        
        return {"error": "Module or function not found"}
    
    def should_remember(self, content: str, context: str = "") -> Dict[str, Any]:
        """AI decision: should this be remembered?"""
        decision = {
            "should_remember": False,
            "confidence": 0.0,
            "reason": "",
            "memory_type": None,
            "priority": "low"
        }
        
        try:
            # Analyze content for memory-worthiness
            content_lower = content.lower()
            
            # High priority indicators
            high_priority_patterns = [
                r'\b(important|wichtig|entscheidend|kritisch)\b',
                r'\b(learn|lernen|entdeckt|gefunden)\b',
                r'\b(error|bug|problem|lösung)\b',
                r'\b(user\s+request|benutzer\s+wunsch)\b'
            ]
            
            # Medium priority indicators  
            medium_priority_patterns = [
                r'\b(interesting|interessant|nützlich)\b',
                r'\b(question|frage|antwort)\b',
                r'\b(topic|thema|diskussion)\b'
            ]
            
            # Low priority (should forget)
            forget_patterns = [
                r'\b(hello|hallo|hi|hey)\b',
                r'\b(test|probe)\b',
                r'\b(sorry|entschuldigung)\b'
            ]
            
            confidence = 0.0
            
            # Check patterns
            for pattern in high_priority_patterns:
                if re.search(pattern, content_lower):
                    confidence += 0.4
                    
            for pattern in medium_priority_patterns:
                if re.search(pattern, content_lower):
                    confidence += 0.2
                    
            for pattern in forget_patterns:
                if re.search(pattern, content_lower):
                    confidence -= 0.3
            
            # Length factor
            if len(content) > 100:
                confidence += 0.1
            elif len(content) < 20:
                confidence -= 0.2
            
            # Context factor
            if context:
                if any(kw in context.lower() for kw in ['conversation', 'learning', 'important']):
                    confidence += 0.2
            
            # Normalize confidence
            confidence = max(0.0, min(1.0, confidence))
            
            # Make decision
            decision["confidence"] = round(confidence, 2)
            decision["should_remember"] = confidence >= 0.3
            
            if confidence >= 0.7:
                decision["priority"] = "high"
                decision["memory_type"] = "long_term"
            elif confidence >= 0.3:
                decision["priority"] = "medium" 
                decision["memory_type"] = "short_term"
            else:
                decision["priority"] = "low"
                decision["memory_type"] = "forget"
            
            # Generate reason
            if decision["should_remember"]:
                if confidence >= 0.7:
                    decision["reason"] = "Hohe Wichtigkeit für langfristiges Gedächtnis"
                else:
                    decision["reason"] = "Mittlere Priorität für Kurzzeitgedächtnis"
            else:
                decision["reason"] = "Nicht speicherwürdig - geringe Relevanz"
                
        except Exception as e:
            decision["error"] = str(e)
        
        # Log decision
        self.memory_decisions.append({
            "timestamp": int(time.time()),
            "content_preview": content[:100],
            "decision": decision
        })
        
        return decision
    
    def auto_cleanup_memories(self, max_age_days: int = 30, min_confidence: float = 0.2) -> Dict[str, Any]:
        """Automatic cleanup of low-value memories"""
        cleanup_result = {
            "deleted_blocks": 0,
            "freed_space_mb": 0.0,
            "errors": []
        }
        
        try:
            blocks_dir = self.root_path / "memory" / "long_term" / "blocks"
            if not blocks_dir.exists():
                return cleanup_result
                
            current_time = int(time.time())
            max_age_seconds = max_age_days * 24 * 3600
            
            for block_file in blocks_dir.glob("*.json"):
                try:
                    # Check age
                    file_age = current_time - block_file.stat().st_mtime
                    
                    if file_age > max_age_seconds:
                        # Check content value
                        content = block_file.read_text()
                        decision = self.should_remember(content)
                        
                        if not decision["should_remember"] or decision["confidence"] < min_confidence:
                            # Delete low-value old memory
                            file_size = block_file.stat().st_size
                            block_file.unlink()
                            cleanup_result["deleted_blocks"] += 1
                            cleanup_result["freed_space_mb"] += file_size / (1024*1024)
                            
                except Exception as e:
                    cleanup_result["errors"].append(f"Error processing {block_file.name}: {e}")
                    
            cleanup_result["freed_space_mb"] = round(cleanup_result["freed_space_mb"], 2)
            
        except Exception as e:
            cleanup_result["errors"].append(f"Cleanup failed: {e}")
        
        return cleanup_result
    
    def update_consciousness_level(self) -> float:
        """Update consciousness level based on self-awareness metrics"""
        try:
            factors = {
                "memory_blocks": min(1.0, self._get_memory_stats()["long_term"]["blocks"] / 1000),
                "modules_active": min(1.0, len(self._get_module_overview()) / 15),
                "decisions_made": min(1.0, len(self.memory_decisions) / 100),
                "self_checks": min(1.0, (int(time.time()) - self.last_self_check) / (24*3600))
            }
            
            # Calculate weighted average
            weights = {"memory_blocks": 0.3, "modules_active": 0.2, "decisions_made": 0.3, "self_checks": 0.2}
            self.consciousness_level = sum(factors[k] * weights[k] for k in factors)
            self.last_self_check = int(time.time())
            
        except Exception:
            self.consciousness_level = 0.5  # Default fallback
            
        return round(self.consciousness_level, 3)

# Global consciousness instance
_ki_ana_consciousness = KIAnaConsciousness()

def get_consciousness() -> KIAnaConsciousness:
    """Get the global KI_ana consciousness instance"""
    return _ki_ana_consciousness

def get_identity() -> Dict[str, Any]:
    """Get KI_ana's complete identity"""
    return _ki_ana_consciousness.get_identity()

def should_remember(content: str, context: str = "") -> Dict[str, Any]:
    """AI decision: should content be remembered?"""
    return _ki_ana_consciousness.should_remember(content, context)

def auto_cleanup_memories(max_age_days: int = 30, min_confidence: float = 0.2) -> Dict[str, Any]:
    """Automatic memory cleanup"""
    return _ki_ana_consciousness.auto_cleanup_memories(max_age_days, min_confidence)

def access_code(module: str, function: str = None) -> Dict[str, Any]:
    """Access code for self-awareness"""
    return _ki_ana_consciousness.access_code(module, function)
