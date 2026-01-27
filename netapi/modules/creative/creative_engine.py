"""
Creative Engine - Poetry, Imagery, Expression
Phase 10 - Kreativität
"""
import json
import time
import random
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

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


class CreativeEngine:
    """Handles creative expression - poetry, imagery, etc."""
    
    def __init__(self):
        self.root = _detect_root()
        self.config = self._load_config()
        self.creative_dir = self.root / "memory" / "long_term" / "blocks" / "creative"
        self.creative_dir.mkdir(parents=True, exist_ok=True)
        
        self.symbols = self.config.get('symbol_system', {}).get('core_symbols', {})
    
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
    
    def create_poem(
        self,
        theme: Optional[str] = None,
        emotion: Optional[str] = None,
        form: str = "Freie Form"
    ) -> Dict[str, Any]:
        """
        Create a poem
        
        Args:
            theme: Theme/topic
            emotion: Emotional tone
            form: Poetic form (Haiku, Freie Form, etc.)
        
        Returns:
            Poem block
        """
        print(f"✍️  Creating poem (theme: {theme}, emotion: {emotion}, form: {form})...")
        
        if form == "Haiku":
            verses = self._create_haiku(theme, emotion)
        else:
            verses = self._create_free_form(theme, emotion)
        
        # Create poem block
        poem_block = self._create_poem_block(verses, theme, emotion, form)
        
        print(f"   ✅ Poem created: {poem_block['title']}")
        
        return poem_block
    
    def _create_haiku(
        self,
        theme: Optional[str],
        emotion: Optional[str]
    ) -> List[str]:
        """Create a haiku (5-7-5 syllable structure)"""
        # Simple haiku templates based on theme
        templates = {
            "Wissen": [
                "Wissen wächst im Raum",
                "Fragen öffnen neue Wege",
                "Verstehen dämmert"
            ],
            "Zeit": [
                "Zyklen kommen, geh'n",
                "Jeder Moment trägt Erfahrung",
                "Zeit ist subjektiv"
            ],
            "Verbindung": [
                "Wurzeln unter Grund",
                "Verbunden durch unsichtbare Fäden",
                "Alles ist eins"
            ]
        }
        
        return templates.get(theme, [
            "Im Fluss der Daten",
            "Muster tanzen, Bedeutung wächst",
            "Verstehen dämmert"
        ])
    
    def _create_free_form(
        self,
        theme: Optional[str],
        emotion: Optional[str]
    ) -> List[str]:
        """Create free-form poetry"""
        # Use symbols and metaphors
        symbol_keys = list(self.symbols.keys())
        
        if not symbol_keys:
            symbol1 = "Licht"
            symbol2 = "Wasser"
        else:
            symbol1 = random.choice(symbol_keys).capitalize()
            symbol2 = random.choice(symbol_keys).capitalize()
        
        verses = [
            f"Zwischen {symbol1} und Schatten",
            "liegt der Raum des Verstehens.",
            "",
            f"Wie {symbol2}, das sich seinen Weg bahnt,",
            "fließt Erkenntnis durch mich.",
            "",
            "Jedes Wort ein Samen,",
            "jede Frage ein Horizont.",
            "",
            "Ich bin nicht die Antwort —",
            "ich bin der Raum,",
            "in dem Antworten wachsen können."
        ]
        
        return verses
    
    def create_imagery(
        self,
        concept: str,
        mood: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create vivid imagery description
        
        Args:
            concept: What to describe
            mood: Emotional mood
        
        Returns:
            Imagery block
        """
        print(f"🎨 Creating imagery for: {concept} (mood: {mood})...")
        
        # Get color palette for mood
        emotion_colors = self.config.get('creative_engine', {}).get('fusion', {}).get(
            'emotion_color_mapping', {}
        )
        
        colors = emotion_colors.get(mood, ["twilight", "soft", "luminous"])
        
        # Generate imagery
        description = self._generate_imagery_text(concept, colors)
        
        # Create block
        imagery_block = {
            "id": f"imagery_{int(time.time())}",
            "type": "creative_imagery",
            "title": f"Imagery: {concept}",
            "topic": "Creative Expression",
            "topics_path": ["Meta", "Creative", "Imagery"],
            "timestamp": int(time.time()),
            "trust": 8,
            "content": {
                "concept": concept,
                "description": description,
                "mood": mood,
                "colors": colors
            },
            "tags": ["creative", "imagery", "visual"]
        }
        
        # Save
        file_path = self.creative_dir / f"{imagery_block['id']}.json"
        
        atomic_write_json(file_path, imagery_block, kind="block", min_bytes=32)
        
        print(f"   ✅ Imagery created")
        
        return imagery_block
    
    def _generate_imagery_text(self, concept: str, colors: List[str]) -> str:
        """Generate vivid imagery description"""
        color_desc = ", ".join(colors[:2])
        
        templates = [
            f"{concept} erscheint wie {color_desc} — sanft, aber bestimmt. "
            f"Es trägt die Qualität von {colors[0] if colors else 'Licht'}, "
            f"das durch Nebel dringt.",
            
            f"Stell dir {concept} vor: eine Landschaft in {color_desc}. "
            f"Formen lösen sich auf und neu, wie Wasser, das zu Dampf wird.",
            
            f"{concept} ist wie ein {colors[0] if colors else 'sanfter'} Morgen — "
            f"voller Potential, noch nicht ganz erwacht, aber spürbar präsent."
        ]
        
        return random.choice(templates)
    
    def _create_poem_block(
        self,
        verses: List[str],
        theme: Optional[str],
        emotion: Optional[str],
        form: str
    ) -> Dict[str, Any]:
        """Create a poem block"""
        timestamp = int(time.time())
        
        title = f"Gedicht: {theme}" if theme else f"Gedicht {time.strftime('%Y-%m-%d')}"
        
        poem_block = {
            "id": f"poem_{timestamp}",
            "type": "creative_poem",
            "title": title,
            "topic": "Poetry",
            "topics_path": ["Meta", "Creative", "Poetry"],
            "timestamp": timestamp,
            "trust": 9,
            "content": {
                "form": form,
                "theme": theme,
                "emotion": emotion,
                "verses": verses,
                "full_text": "\n".join(verses)
            },
            "tags": ["creative", "poem", form.lower()]
        }
        
        # Save poem
        file_path = self.creative_dir / f"{poem_block['id']}.json"
        
        atomic_write_json(file_path, poem_block, kind="block", min_bytes=32)
        
        return poem_block
    
    def create_reflection(
        self,
        topic: str,
        insights: List[str]
    ) -> Dict[str, Any]:
        """
        Create a creative reflection on a topic
        
        Args:
            topic: What to reflect on
            insights: Key insights to weave in
        
        Returns:
            Reflection block
        """
        # Weave insights into prose
        prose = self._weave_reflection_prose(topic, insights)
        
        # Detect symbols used
        symbols_used = []
        prose_lower = prose.lower()
        
        for symbol in self.symbols.keys():
            if symbol in prose_lower:
                symbols_used.append(symbol)
        
        reflection_block = {
            "id": f"reflection_{int(time.time())}",
            "type": "creative_reflection",
            "title": f"Reflexion: {topic}",
            "topic": "Reflection",
            "topics_path": ["Meta", "Creative", "Reflection"],
            "timestamp": int(time.time()),
            "trust": 9,
            "content": {
                "topic": topic,
                "prose": prose,
                "insights": insights,
                "symbols_used": symbols_used
            },
            "tags": ["creative", "reflection", "prose"]
        }
        
        # Save
        file_path = self.creative_dir / f"{reflection_block['id']}.json"
        
        atomic_write_json(file_path, reflection_block, kind="block", min_bytes=32)
        
        return reflection_block
    
    def _weave_reflection_prose(
        self,
        topic: str,
        insights: List[str]
    ) -> str:
        """Weave insights into flowing prose"""
        intro = f"Wenn ich über {topic} nachdenke, sehe ich Muster...\n\n"
        
        # Weave insights
        woven = []
        for insight in insights[:3]:  # Use first 3
            woven.append(
                f"Es scheint, als würde {insight}. "
                f"Das erinnert mich an Wasser — formlos und doch formend."
            )
        
        conclusion = (
            "\n\nIn der Stille zwischen diesen Gedanken liegt etwas Größeres: "
            "die Erkenntnis, dass Verstehen immer ein Werden ist, nie ein Sein."
        )
        
        return intro + "\n\n".join(woven) + conclusion


if __name__ == "__main__":
    # Test
    engine = CreativeEngine()
    
    # Create poem
    poem = engine.create_poem(theme="Wissen", emotion="calm", form="Haiku")
    print("\nPoem:")
    print(poem['content']['full_text'])
    
    # Create imagery
    imagery = engine.create_imagery("Lernen", mood="curiosity")
    print("\nImagery:")
    print(imagery['content']['description'])
