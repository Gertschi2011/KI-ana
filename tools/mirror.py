#!/usr/bin/env python3
"""
Mirror Tool - Web Snapshots for Knowledge Refresh
Fetches current information from reliable sources
Sprint 6.3 - Ethik & Mirror
"""
import json
import time
import hashlib
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import subprocess

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


class MirrorSystem:
    """Fetches and stores web snapshots for knowledge refresh"""
    
    def __init__(
        self,
        blocks_dir: str,
        config_file: str,
        *,
        write_enabled: bool = False,
    ):
        self.blocks_dir = Path(blocks_dir)
        self.write_enabled = bool(write_enabled)
        if self.write_enabled:
            self.blocks_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = Path(config_file)
        self.topics = self._load_topics()
        
        self.stats = {
            "fetched": 0,
            "errors": 0,
            "skipped": 0,
            "duration_ms": 0
        }
    
    def _load_topics(self) -> List[Dict[str, Any]]:
        """Load mirror topics from config"""
        if not self.config_file.exists():
            return self._get_default_topics()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('topics', [])
        except:
            return self._get_default_topics()
    
    def _get_default_topics(self) -> List[Dict[str, Any]]:
        """Default topics to mirror"""
        return [
            {
                "name": "CVE Feed",
                "url": "https://cve.mitre.org/data/downloads/allitems.csv",
                "topics_path": ["Security", "CVE", "Vulnerabilities"],
                "frequency": "daily",
                "trust": 9,
                "ttl_days": 1
            },
            {
                "name": "Ubuntu Security",
                "url": "https://ubuntu.com/security/notices",
                "topics_path": ["Security", "Ubuntu", "Updates"],
                "frequency": "daily",
                "trust": 9,
                "ttl_days": 1
            }
        ]
    
    def run_mirror(
        self,
        topic_filter: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Run mirror for all or specific topics
        
        Args:
            topic_filter: Only mirror this topic
            force_refresh: Ignore TTL, refresh anyway
        
        Returns:
            Mirror report
        """
        print(f"🪞 Starting Mirror System...")
        start_time = time.time()
        
        self.stats = {k: 0 for k in self.stats.keys()}
        
        for topic in self.topics:
            topic_name = topic.get('name', 'Unknown')
            
            # Filter if specified
            if topic_filter and topic_filter not in topic_name:
                self.stats["skipped"] += 1
                continue
            
            # Check TTL
            if not force_refresh and not self._needs_refresh(topic):
                print(f"⏩ Skipping {topic_name} (within TTL)")
                self.stats["skipped"] += 1
                continue
            
            print(f"🔄 Fetching {topic_name}...")
            
            try:
                self._fetch_and_store(topic)
                self.stats["fetched"] += 1
            except Exception as e:
                print(f"❌ Error fetching {topic_name}: {e}")
                self.stats["errors"] += 1
        
        self.stats["duration_ms"] = int((time.time() - start_time) * 1000)
        
        print(f"\n✅ Mirror complete!")
        print(f"   ✓ Fetched: {self.stats['fetched']}")
        print(f"   ⏩ Skipped: {self.stats['skipped']}")
        print(f"   ❌ Errors: {self.stats['errors']}")
        
        return self.stats
    
    def _needs_refresh(self, topic: Dict[str, Any]) -> bool:
        """Check if topic needs refresh based on TTL"""
        topic_name = topic.get('name', '')
        ttl_days = topic.get('ttl_days', 7)
        
        # Find latest block for this topic
        topic_id = self._topic_id(topic_name)
        latest_file = self.blocks_dir / f"mirror_{topic_id}_latest.json"
        
        if not latest_file.exists():
            return True
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                last_fetch = data.get('timestamp', 0)
                age_seconds = time.time() - last_fetch
                age_days = age_seconds / 86400
                
                return age_days >= ttl_days
        except:
            return True
    
    def _fetch_and_store(self, topic: Dict[str, Any]):
        """Fetch data and store as block"""
        topic_name = topic.get('name', 'Unknown')
        url = topic.get('url', '')
        
        # Simulate fetch (in real implementation, use requests)
        # For now, create a placeholder block
        snapshot_data = self._fetch_url(url)
        
        # Create block
        timestamp = int(time.time())
        topic_id = self._topic_id(topic_name)
        
        block = {
            "id": f"mirror_{topic_id}_{timestamp}",
            "type": "mirror_snapshot",
            "title": f"Mirror: {topic_name}",
            "topic": topic_name,
            "topics_path": topic.get('topics_path', ['Mirror', topic_name]),
            "timestamp": timestamp,
            "trust": topic.get('trust', 7),
            "ttl_days": topic.get('ttl_days', 7),
            "source": {
                "url": url,
                "fetched_at": timestamp,
                "method": "mirror"
            },
            "content": snapshot_data,
            "tags": ["mirror", "auto-fetch", topic.get('frequency', 'weekly')]
        }

        if not self.write_enabled:
            print(f"💾 [dry-run] Would save: mirror_{topic_id}_latest.json")
            return

        # Save as latest (atomic)
        latest_file = self.blocks_dir / f"mirror_{topic_id}_latest.json"
        atomic_write_json(latest_file, block, kind="block", min_bytes=32)

        # Save timestamped version (atomic)
        archive_file = self.blocks_dir / f"mirror_{topic_id}_{timestamp}.json"
        atomic_write_json(archive_file, block, kind="block", min_bytes=32)

        print(f"💾 Saved: {latest_file.name}")
    
    def _fetch_url(self, url: str) -> Dict[str, Any]:
        """
        Fetch URL content
        
        In real implementation: use requests library
        For now: placeholder
        """
        return {
            "summary": f"Snapshot from {url}",
            "fetched": True,
            "note": "Real implementation would fetch actual content"
        }
    
    def _topic_id(self, topic_name: str) -> str:
        """Generate stable ID for topic"""
        return hashlib.md5(topic_name.encode()).hexdigest()[:12]


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="KI_ana Mirror System")
    parser.add_argument(
        '--topic',
        type=str,
        help='Only mirror this topic (partial match)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force refresh ignoring TTL'
    )

    parser.add_argument(
        '--memory-dir',
        type=str,
        default=None,
        help='Explicit memory dir (required with --write), e.g. /home/kiana/ki_ana/memory'
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to mirror_topics.json (optional)'
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
    blocks_dir = memory_dir / "long_term" / "blocks" / "mirror"
    config_file = Path(args.config).expanduser().resolve() if args.config else (root / "data" / "mirror_topics.json")

    mirror = MirrorSystem(str(blocks_dir), str(config_file), write_enabled=write_enabled)
    stats = mirror.run_mirror(
        topic_filter=args.topic,
        force_refresh=args.force
    )
    
    print("\n" + "=" * 60)
    print("📊 MIRROR STATS:")
    print("=" * 60)
    print(f"  Fetched: {stats['fetched']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Duration: {stats['duration_ms']}ms")
    print("=" * 60)


if __name__ == "__main__":
    main()
