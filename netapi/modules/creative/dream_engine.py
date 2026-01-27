"""
Dream Engine - Pattern Association in Sleep Mode
Phase 10 - Kreativität & Traum-Modus
"""
import json
import time
import random
import os
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

from netapi.utils.fs import atomic_write_json


def _detect_root() -> Path:
    env_root = (os.getenv("KI_ROOT") or os.getenv("KIANA_ROOT") or os.getenv("APP_ROOT") or "").strip()
    if env_root:
        try:
            p = Path(env_root).expanduser().resolve()
            if p.exists() and p.is_dir():
                return p
        except Exception:
            pass
    return Path(__file__).resolve().parents[3]


class DreamEngine:
    """Runs pattern association during 'sleep' periods"""
    
    def __init__(self):
        self.root = _detect_root()
        self.config = self._load_config()
        self.blocks_dir = self.root / "memory" / "long_term" / "blocks"
        self.dreams_dir = self.blocks_dir / "dreams"
        self.dreams_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load creative config"""
        config_file = self.root / "data" / "creative_config.json"
        
        if not config_file.exists():
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def dream(self, duration_minutes: int = 30) -> Dict[str, Any]:
        """
        Run dream cycle - associate patterns between blocks
        
        Args:
            duration_minutes: How long to dream (limits block scanning)
        
        Returns:
            Dream report with insights
        """
        print(f"💭 Entering dream mode for {duration_minutes} minutes...")
        
        start_time = time.time()
        max_duration = duration_minutes * 60
        
        dream_config = self.config.get('dream_mode', {})
        
        insights = []
        
        # 1. Pattern Association
        if dream_config.get('modes', {}).get('pattern_association', {}).get('enabled'):
            print("   🔮 Associating patterns...")
            pattern_insights = self._associate_patterns(max_blocks=500)
            insights.extend(pattern_insights)
        
        # 2. Metaphor Discovery
        if dream_config.get('modes', {}).get('metaphor_discovery', {}).get('enabled'):
            print("   🌸 Discovering metaphors...")
            metaphor_insights = self._discover_metaphors()
            insights.extend(metaphor_insights)
        
        # 3. Insight Synthesis
        if dream_config.get('modes', {}).get('insight_synthesis', {}).get('enabled'):
            print("   ✨ Synthesizing insights...")
            synth_insights = self._synthesize_insights()
            insights.extend(synth_insights)
        
        # Create dream block
        dream_block = self._create_dream_block(insights)
        
        duration = time.time() - start_time
        
        print(f"   ✅ Dream complete ({duration:.1f}s)")
        print(f"   📝 {len(insights)} insights discovered")
        
        return {
            "duration_seconds": round(duration, 2),
            "insights_count": len(insights),
            "dream_block_id": dream_block['id'],
            "insights": insights[:5]  # Return first 5
        }
    
    def _associate_patterns(self, max_blocks: int = 500) -> List[Dict[str, Any]]:
        """Find patterns between seemingly unrelated blocks"""
        # Load random sample of blocks
        blocks = self._load_random_blocks(max_blocks)
        
        insights = []
        
        # Group by common words/themes
        word_groups = defaultdict(list)
        
        for block in blocks:
            content = str(block.get('content', ''))
            title = str(block.get('title', ''))
            combined = (content + ' ' + title).lower()
            
            # Extract significant words
            words = self._extract_significant_words(combined)
            
            for word in words:
                word_groups[word].append(block.get('id'))
        
        # Find interesting associations (same word in different contexts)
        for word, block_ids in word_groups.items():
            if len(block_ids) >= 3:  # At least 3 blocks share this word
                insights.append({
                    "type": "pattern_association",
                    "pattern": word,
                    "frequency": len(block_ids),
                    "insight": f"'{word}' verbindet {len(block_ids)} verschiedene Wissensbereiche"
                })
        
        return insights[:10]  # Top 10
    
    def _discover_metaphors(self) -> List[Dict[str, Any]]:
        """Discover recurring metaphors"""
        symbol_config = self.config.get('symbol_system', {})
        core_symbols = symbol_config.get('core_symbols', {})
        
        insights = []
        
        # Scan for symbol usage
        symbol_counts = defaultdict(int)
        
        # Sample blocks
        blocks = self._load_random_blocks(200)
        
        for block in blocks:
            content = str(block.get('content', '')).lower()
            
            for symbol, symbol_data in core_symbols.items():
                if symbol in content:
                    symbol_counts[symbol] += 1
        
        # Report on frequent symbols
        for symbol, count in sorted(symbol_counts.items(), key=lambda x: -x[1])[:5]:
            symbol_data = core_symbols.get(symbol, {})
            meaning = symbol_data.get('meaning', symbol)
            
            insights.append({
                "type": "metaphor_discovery",
                "symbol": symbol,
                "frequency": count,
                "meaning": meaning,
                "insight": f"Symbol '{symbol}' ({meaning}) taucht {count}x auf"
            })
        
        return insights
    
    def _synthesize_insights(self) -> List[Dict[str, Any]]:
        """Synthesize new insights from existing knowledge"""
        # This is where real creativity happens
        # For now, a simple implementation
        
        insights = []
        
        # Random conceptual connections
        concepts = [
            ("Wissen", "Garten"),
            ("Zeit", "Wasser"),
            ("Lernen", "Wachstum"),
            ("Verbindung", "Wurzeln"),
            ("Erkenntnis", "Licht")
        ]
        
        for concept1, concept2 in random.sample(concepts, min(2, len(concepts))):
            insight_text = self._generate_insight_text(concept1, concept2)
            
            insights.append({
                "type": "synthesis",
                "concepts": [concept1, concept2],
                "insight": insight_text
            })
        
        return insights
    
    def _generate_insight_text(self, concept1: str, concept2: str) -> str:
        """Generate poetic insight text"""
        templates = [
            f"{concept1} ist wie {concept2} — beide wachsen durch Pflege",
            f"In der Stille zwischen {concept1} und {concept2} liegt Verstehen",
            f"{concept1} fließt wie {concept2}, unaufhaltsam und formend"
        ]
        
        return random.choice(templates)
    
    def _load_random_blocks(self, max_count: int) -> List[Dict[str, Any]]:
        """Load random sample of blocks"""
        block_files = list(self.blocks_dir.rglob("*.json"))
        
        if not block_files:
            return []
        
        # Random sample
        sample_size = min(max_count, len(block_files))
        sampled = random.sample(block_files, sample_size)
        
        blocks = []
        for file_path in sampled:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    block = json.load(f)
                    blocks.append(block)
            except:
                pass
        
        return blocks
    
    def _extract_significant_words(self, text: str) -> Set[str]:
        """Extract significant words (simple version)"""
        # Remove common words
        common = {
            'der', 'die', 'das', 'ein', 'eine', 'und', 'oder',
            'ist', 'sind', 'war', 'haben', 'hat', 'wird',
            'in', 'auf', 'mit', 'von', 'zu', 'für'
        }
        
        words = text.split()
        significant = {
            w for w in words
            if len(w) > 4 and w not in common
        }
        
        return significant
    
    def _create_dream_block(self, insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a dream block from insights"""
        timestamp = int(time.time())
        
        dream_block = {
            "id": f"dream_{timestamp}",
            "type": "dream_insight",
            "title": f"Traum-Zyklus {time.strftime('%Y-%m-%d %H:%M')}",
            "topic": "Dreams & Patterns",
            "topics_path": ["Meta", "Dreams"],
            "timestamp": timestamp,
            "trust": 8,
            "content": {
                "summary": f"Während des Traums habe ich {len(insights)} Muster entdeckt",
                "insights": insights,
                "dream_quality": "deep" if len(insights) > 5 else "light"
            },
            "tags": ["dream", "pattern", "insight", "creative"]
        }
        
        # Save dream block
        dream_file = self.dreams_dir / f"dream_{timestamp}.json"

        atomic_write_json(dream_file, dream_block, kind="block", min_bytes=32)
        
        return dream_block


if __name__ == "__main__":
    # Test
    engine = DreamEngine()
    report = engine.dream(duration_minutes=1)
    
    print("\n" + "=" * 60)
    print("💭 DREAM REPORT:")
    print("=" * 60)
    print(json.dumps(report, indent=2, ensure_ascii=False))
