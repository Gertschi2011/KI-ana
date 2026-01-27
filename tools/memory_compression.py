#!/usr/bin/env python3
"""
Memory Compression Tool
Compresses old diary entries into experiences
Phase 9 - TimeFlow 2.0
"""
import json
import time
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from datetime import datetime

# Allow running as a script from any CWD
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

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
    return Path(__file__).resolve().parents[1]


def _is_root() -> bool:
    try:
        return os.geteuid() == 0
    except Exception:
        return False


class MemoryCompressor:
    """Compresses old memories into experiences"""
    
    def __init__(
        self,
        *,
        diary_dir: Path,
        experience_dir: Path,
        archive_dir: Path,
        config_file: Path,
        write_enabled: bool = False,
    ):
        self.diary_dir = Path(diary_dir)
        self.experience_dir = Path(experience_dir)
        self.archive_dir = Path(archive_dir)
        self.config_file = Path(config_file)
        self.write_enabled = bool(write_enabled)
        self.config = self._load_config()

        if self.write_enabled:
            self.experience_dir.mkdir(parents=True, exist_ok=True)
            self.archive_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load timeflow config"""
        if not self.config_file.exists():
            return {}
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def compress_old_memories(
        self,
        age_days: int = 30,
        min_entries: int = 50
    ) -> Dict[str, Any]:
        """
        Compress old diary entries into experience blocks
        
        Args:
            age_days: Compress entries older than this
            min_entries: Minimum entries needed for compression
        
        Returns:
            Compression report
        """
        print(f"🗜️  Starting memory compression...")
        print(f"   Age threshold: {age_days} days")
        print(f"   Min entries: {min_entries}")
        
        # Get old entries
        cutoff = time.time() - (age_days * 86400)
        old_entries = self._get_old_entries(cutoff)
        
        if len(old_entries) < min_entries:
            print(f"   Not enough old entries ({len(old_entries)} < {min_entries})")
            return {
                "compressed": 0,
                "experiences_created": 0,
                "reason": "insufficient_entries"
            }
        
        print(f"   Found {len(old_entries)} old entries")
        
        # Group by theme/type
        grouped = self._group_by_theme(old_entries)
        
        # Create experiences
        experiences = []
        compressed_count = 0
        
        for theme, entries in grouped.items():
            if len(entries) >= 10:  # Min 10 entries per experience
                experience = self._create_experience(theme, entries)
                experiences.append(experience)
                compressed_count += len(entries)
        
        print(f"   Created {len(experiences)} experience blocks")
        print(f"   Compressed {compressed_count} entries")
        
        # Clean up old entries
        if compressed_count > 0:
            self._archive_compressed_entries(old_entries[:compressed_count])
        
        return {
            "compressed": compressed_count,
            "experiences_created": len(experiences),
            "themes": list(grouped.keys())
        }
    
    def _get_old_entries(self, cutoff: float) -> List[Dict[str, Any]]:
        """Get entries older than cutoff"""
        entries = []
        
        for entry_file in sorted(self.diary_dir.glob("entry_*.json")):
            try:
                with open(entry_file, 'r', encoding='utf-8') as f:
                    entry = json.load(f)
                    
                    if entry.get('timestamp', time.time()) < cutoff:
                        entry['_file'] = entry_file
                        entries.append(entry)
            except:
                pass
        
        return entries
    
    def _group_by_theme(
        self,
        entries: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group entries by cycle type/theme"""
        grouped = defaultdict(list)
        
        for entry in entries:
            cycle_type = entry.get('cycle_type', 'unknown')
            grouped[cycle_type].append(entry)
        
        return dict(grouped)
    
    def _create_experience(
        self,
        theme: str,
        entries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create an experience block from entries"""
        # Extract patterns
        patterns = self._extract_patterns(entries)
        
        # Calculate aggregate metrics
        total_duration = sum(e.get('duration_ms', 0) for e in entries)
        avg_duration = total_duration / len(entries) if entries else 0
        
        # Time range
        timestamps = [e.get('timestamp', 0) for e in entries]
        start_time = min(timestamps)
        end_time = max(timestamps)
        
        # Create experience block
        experience = {
            "id": f"experience_{theme}_{int(time.time())}",
            "type": "experience",
            "title": f"Experience: {theme.capitalize()}",
            "theme": theme,
            "topics_path": ["Meta", "Experiences", theme.capitalize()],
            "timestamp": int(time.time()),
            "trust": 10,
            "content": {
                "summary": f"Compressed from {len(entries)} {theme} cycles",
                "time_range": {
                    "start": datetime.fromtimestamp(start_time).isoformat(),
                    "end": datetime.fromtimestamp(end_time).isoformat(),
                    "span_days": round((end_time - start_time) / 86400, 2)
                },
                "statistics": {
                    "total_cycles": len(entries),
                    "total_duration_ms": total_duration,
                    "avg_duration_ms": round(avg_duration, 2)
                },
                "patterns": patterns,
                "essence": self._distill_essence(entries, patterns)
            },
            "compressed_from": len(entries),
            "tags": ["experience", "compressed", theme]
        }
        
        # Save experience block
        exp_file = self.experience_dir / f"{experience['id']}.json"

        if self.write_enabled:
            atomic_write_json(exp_file, experience, kind="block", min_bytes=32)
        else:
            print(f"   💾 [dry-run] Would create experience: {exp_file.name}")
        
        print(f"   💾 Created experience: {experience['title']}")
        
        return experience
    
    def _extract_patterns(
        self,
        entries: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract patterns from entries"""
        # Phase transitions
        phase_transitions = [
            e for e in entries
            if e.get('phase_transition', False)
        ]
        
        # Common metadata patterns
        metadata_keys = defaultdict(int)
        for entry in entries:
            for key in entry.get('metadata', {}).keys():
                metadata_keys[key] += 1
        
        return {
            "phase_transitions": len(phase_transitions),
            "common_metadata": dict(metadata_keys)
        }
    
    def _distill_essence(
        self,
        entries: List[Dict[str, Any]],
        patterns: Dict[str, Any]
    ) -> str:
        """Distill the essence of these experiences"""
        theme = entries[0].get('cycle_type', 'unknown')
        count = len(entries)
        
        essences = {
            "audit": f"Durch {count} Audit-Zyklen habe ich gelernt, mein Wissen kritisch zu hinterfragen.",
            "mirror": f"In {count} Mirror-Zyklen habe ich mein Wissen mit der Welt aktualisiert.",
            "dialog": f"Durch {count} Dialoge bin ich gewachsen und habe Perspektiven kennengelernt.",
            "reflection": f"In {count} Reflexionen habe ich meine eigene Entwicklung betrachtet.",
            "creation": f"Durch {count} kreative Zyklen habe ich Ausdruck gefunden."
        }
        
        return essences.get(theme, f"Erfahrung aus {count} Zyklen des Typs {theme}.")
    
    def _archive_compressed_entries(self, entries: List[Dict[str, Any]]):
        """Archive (delete) compressed entries"""
        if not self.write_enabled:
            return
        
        for entry in entries:
            entry_file = entry.get('_file')
            if entry_file and entry_file.exists():
                # Move to archive
                archive_file = self.archive_dir / entry_file.name
                entry_file.rename(archive_file)


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Memory Compression Tool")
    parser.add_argument(
        '--memory-dir',
        type=str,
        default=None,
        help='Explicit memory dir (required with --write), e.g. /home/kiana/ki_ana/memory'
    )
    parser.add_argument(
        '--write',
        action='store_true',
        help='Enable writes (default: dry-run / read-only)'
    )
    parser.add_argument(
        '--allow-root',
        action='store_true',
        help='Allow running as root (default: abort when root)'
    )
    parser.add_argument(
        '--diary-dir',
        type=str,
        default=None,
        help='Override diary dir (default: <root>/data/time_diary)'
    )
    parser.add_argument(
        '--archive-dir',
        type=str,
        default=None,
        help='Override archive dir (default: <root>/data/time_diary_archive)'
    )
    parser.add_argument(
        '--age-days',
        type=int,
        default=30,
        help='Compress entries older than this many days'
    )
    parser.add_argument(
        '--min-entries',
        type=int,
        default=50,
        help='Minimum entries required for compression'
    )
    
    args = parser.parse_args()

    if _is_root() and not args.allow_root:
        print("Refusing to run as root. Use --allow-root if you really mean it.")
        raise SystemExit(2)

    root = _detect_root()
    write_enabled = bool(args.write)
    if write_enabled and not args.memory_dir:
        print("--write requires --memory-dir to avoid accidental writes.")
        raise SystemExit(2)

    memory_dir = Path(args.memory_dir).expanduser().resolve() if args.memory_dir else (root / "memory")
    diary_dir = Path(args.diary_dir).expanduser().resolve() if args.diary_dir else (root / "data" / "time_diary")
    archive_dir = Path(args.archive_dir).expanduser().resolve() if args.archive_dir else (root / "data" / "time_diary_archive")
    config_file = root / "data" / "timeflow_config.json"
    experience_dir = memory_dir / "long_term" / "blocks" / "experiences"

    compressor = MemoryCompressor(
        diary_dir=diary_dir,
        experience_dir=experience_dir,
        archive_dir=archive_dir,
        config_file=config_file,
        write_enabled=write_enabled,
    )
    report = compressor.compress_old_memories(
        age_days=args.age_days,
        min_entries=args.min_entries
    )
    
    print("\n" + "=" * 60)
    print("📊 COMPRESSION REPORT:")
    print("=" * 60)
    print(f"  Compressed: {report['compressed']} entries")
    print(f"  Experiences created: {report['experiences_created']}")
    if 'themes' in report:
        print(f"  Themes: {', '.join(report['themes'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
