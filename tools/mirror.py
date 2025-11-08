#!/usr/bin/env python3
"""
Mirror Tool - Web Snapshots for Knowledge Refresh
Fetches current information from reliable sources
Sprint 6.3 - Ethik & Mirror
"""
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import subprocess


class MirrorSystem:
    """Fetches and stores web snapshots for knowledge refresh"""
    
    def __init__(
        self,
        blocks_dir: str = "/home/kiana/ki_ana/memory/long_term/blocks/mirror",
        config_file: str = "/home/kiana/ki_ana/data/mirror_topics.json"
    ):
        self.blocks_dir = Path(blocks_dir)
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
        
        # Save as latest
        latest_file = self.blocks_dir / f"mirror_{topic_id}_latest.json"
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(block, f, ensure_ascii=False, indent=2)
        
        # Save timestamped version
        archive_file = self.blocks_dir / f"mirror_{topic_id}_{timestamp}.json"
        with open(archive_file, 'w', encoding='utf-8') as f:
            json.dump(block, f, ensure_ascii=False, indent=2)
        
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
    
    args = parser.parse_args()
    
    mirror = MirrorSystem()
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
