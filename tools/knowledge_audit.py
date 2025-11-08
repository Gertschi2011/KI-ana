#!/usr/bin/env python3
"""
Knowledge Audit Tool
Checks quality and actuality of KI_ana's knowledge blocks
Sprint 6.2 - Metakognition
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict


class KnowledgeAuditor:
    """Audits knowledge blocks for quality and freshness"""
    
    def __init__(
        self,
        blocks_dir: str = "/home/kiana/ki_ana/memory/long_term/blocks",
        report_dir: str = "/home/kiana/ki_ana/data/audit"
    ):
        self.blocks_dir = Path(blocks_dir)
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
        # Audit results
        self.stale_blocks: List[Dict[str, Any]] = []
        self.conflict_blocks: List[Dict[str, Any]] = []
        self.verified_blocks: List[Dict[str, Any]] = []
        self.unverified_blocks: List[Dict[str, Any]] = []
        
        self.stats = {
            "total_scanned": 0,
            "total_stale": 0,
            "total_conflicts": 0,
            "total_verified": 0,
            "total_unverified": 0,
            "scan_duration_ms": 0,
            "timestamp": 0
        }
    
    def run_audit(
        self,
        max_age_days: int = 180,
        min_trust: float = 5.0
    ) -> Dict[str, Any]:
        """
        Run complete knowledge audit
        
        Args:
            max_age_days: Blocks older than this are marked as stale
            min_trust: Minimum trust rating for verified blocks
        
        Returns:
            Audit report dictionary
        """
        print(f"🔍 Starting Knowledge Audit...")
        print(f"📂 Blocks directory: {self.blocks_dir}")
        
        start_time = time.time()
        
        # Reset counters
        self._reset()
        
        # Get cutoff timestamp
        cutoff = time.time() - (max_age_days * 86400)
        
        # Scan all block files
        block_files = list(self.blocks_dir.rglob("*.json"))
        block_files.extend(self.blocks_dir.rglob("*.jsonl"))
        
        print(f"📦 Found {len(block_files)} block files")
        
        for block_file in block_files:
            try:
                self._audit_file(block_file, cutoff, min_trust)
            except Exception as e:
                print(f"⚠️  Error auditing {block_file.name}: {e}")
        
        # Calculate stats
        self.stats["scan_duration_ms"] = int((time.time() - start_time) * 1000)
        self.stats["timestamp"] = int(time.time())
        
        # Generate report
        report = self._generate_report()
        
        # Save report
        self._save_report(report)
        
        # Create audit block
        self._create_audit_block(report)
        
        print(f"\n✅ Audit complete!")
        print(f"   📊 Total scanned: {self.stats['total_scanned']}")
        print(f"   🕐 Stale: {self.stats['total_stale']}")
        print(f"   ⚔️  Conflicts: {self.stats['total_conflicts']}")
        print(f"   ✓ Verified: {self.stats['total_verified']}")
        print(f"   ⏱️  Duration: {self.stats['scan_duration_ms']}ms")
        
        return report
    
    def _reset(self):
        """Reset audit results"""
        self.stale_blocks = []
        self.conflict_blocks = []
        self.verified_blocks = []
        self.unverified_blocks = []
        
        self.stats = {k: 0 for k in self.stats.keys()}
    
    def _audit_file(self, file_path: Path, cutoff: float, min_trust: float):
        """Audit a single file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # Handle JSONL
        if file_path.suffix == '.jsonl':
            for line in content.split('\n'):
                if line.strip():
                    try:
                        block = json.loads(line)
                        self._audit_block(block, file_path, cutoff, min_trust)
                    except:
                        pass
        else:
            # Regular JSON
            try:
                block = json.loads(content)
                self._audit_block(block, file_path, cutoff, min_trust)
            except:
                pass
    
    def _audit_block(
        self,
        block: Dict[str, Any],
        file_path: Path,
        cutoff: float,
        min_trust: float
    ):
        """Audit a single block"""
        self.stats["total_scanned"] += 1
        
        block_id = block.get('id', file_path.stem)
        
        # Get timestamp
        ts = self._get_timestamp(block)
        
        # Get trust/rating
        trust = block.get('trust', block.get('rating', 5))
        
        # Check for conflicts
        has_conflict = bool(
            block.get('conflict_with') or
            block.get('conflicts') or
            block.get('disputed')
        )
        
        # Build audit entry
        entry = {
            "id": block_id,
            "title": block.get('title', 'Untitled'),
            "topic": block.get('topic', 'Unknown'),
            "topics_path": block.get('topics_path', []),
            "timestamp": ts,
            "trust": trust,
            "age_days": int((time.time() - ts) / 86400) if ts else None,
            "file": str(file_path.relative_to(self.blocks_dir))
        }
        
        # Categorize
        if has_conflict:
            self.conflict_blocks.append({**entry, "reason": "Has conflict marker"})
            self.stats["total_conflicts"] += 1
        
        if ts and ts < cutoff:
            self.stale_blocks.append({**entry, "reason": "Older than threshold"})
            self.stats["total_stale"] += 1
        
        if trust >= min_trust:
            self.verified_blocks.append(entry)
            self.stats["total_verified"] += 1
        else:
            self.unverified_blocks.append({**entry, "reason": f"Trust {trust} < {min_trust}"})
            self.stats["total_unverified"] += 1
    
    def _get_timestamp(self, block: Dict[str, Any]) -> float:
        """Extract timestamp from block"""
        # Try various timestamp fields
        for field in ['ts_epoch', 'timestamp', 'created_at', 'ts']:
            if field in block:
                ts = block[field]
                # Handle both unix timestamp and datetime strings
                if isinstance(ts, (int, float)):
                    return float(ts)
                elif isinstance(ts, str):
                    try:
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        return dt.timestamp()
                    except:
                        pass
        
        return 0
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate audit report"""
        return {
            "audit_version": "1.0",
            "timestamp": self.stats["timestamp"],
            "stats": self.stats,
            "stale": {
                "count": len(self.stale_blocks),
                "blocks": self.stale_blocks[:100]  # Limit to 100
            },
            "conflicts": {
                "count": len(self.conflict_blocks),
                "blocks": self.conflict_blocks[:100]
            },
            "verified": {
                "count": len(self.verified_blocks),
                "sample": self.verified_blocks[:10]
            },
            "unverified": {
                "count": len(self.unverified_blocks),
                "sample": self.unverified_blocks[:10]
            },
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate actionable recommendations"""
        recs = []
        
        if self.stats["total_stale"] > 0:
            recs.append(
                f"🕐 {self.stats['total_stale']} stale blocks found. "
                f"Consider updating or archiving."
            )
        
        if self.stats["total_conflicts"] > 0:
            recs.append(
                f"⚔️  {self.stats['total_conflicts']} conflict markers found. "
                f"Review and resolve contradictions."
            )
        
        if self.stats["total_unverified"] > 50:
            recs.append(
                f"⚠️  {self.stats['total_unverified']} unverified blocks. "
                f"Review and increase trust ratings for validated content."
            )
        
        stale_ratio = self.stats["total_stale"] / max(self.stats["total_scanned"], 1)
        if stale_ratio > 0.3:
            recs.append(
                f"📊 {int(stale_ratio * 100)}% of knowledge is stale. "
                f"Trigger mirror.py to fetch fresh data."
            )
        
        if not recs:
            recs.append("✅ Knowledge base is in good health!")
        
        return recs
    
    def _save_report(self, report: Dict[str, Any]):
        """Save report to file"""
        report_file = self.report_dir / "latest_audit.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Report saved: {report_file}")
        
        # Also save timestamped version
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_file = self.report_dir / f"audit_{timestamp}.json"
        
        with open(archive_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    
    def _create_audit_block(self, report: Dict[str, Any]):
        """Create a memory block for this audit"""
        audit_block = {
            "id": f"audit_{report['timestamp']}",
            "type": "self_audit",
            "title": f"Knowledge Audit {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "topic": "Self-Reflection",
            "topics_path": ["Meta", "Self-Audit"],
            "timestamp": report['timestamp'],
            "trust": 10,
            "content": {
                "summary": f"Scanned {report['stats']['total_scanned']} blocks. "
                          f"Found {report['stats']['total_stale']} stale, "
                          f"{report['stats']['total_conflicts']} conflicts.",
                "stats": report['stats'],
                "recommendations": report['recommendations']
            },
            "tags": ["audit", "self-reflection", "quality-check"]
        }
        
        # Save as block
        audit_blocks_dir = Path("/home/kiana/ki_ana/memory/long_term/blocks/audits")
        audit_blocks_dir.mkdir(parents=True, exist_ok=True)
        
        block_file = audit_blocks_dir / f"audit_{report['timestamp']}.json"
        
        with open(block_file, 'w', encoding='utf-8') as f:
            json.dump(audit_block, f, ensure_ascii=False, indent=2)
        
        print(f"📝 Audit block created: {block_file.name}")


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="KI_ana Knowledge Audit")
    parser.add_argument(
        '--max-age-days',
        type=int,
        default=180,
        help='Maximum age in days before marking as stale'
    )
    parser.add_argument(
        '--min-trust',
        type=float,
        default=5.0,
        help='Minimum trust rating for verified blocks'
    )
    parser.add_argument(
        '--blocks-dir',
        type=str,
        default="/home/kiana/ki_ana/memory/long_term/blocks",
        help='Blocks directory path'
    )
    
    args = parser.parse_args()
    
    auditor = KnowledgeAuditor(blocks_dir=args.blocks_dir)
    report = auditor.run_audit(
        max_age_days=args.max_age_days,
        min_trust=args.min_trust
    )
    
    print("\n" + "=" * 60)
    print("📊 RECOMMENDATIONS:")
    print("=" * 60)
    for rec in report['recommendations']:
        print(f"  {rec}")
    print("=" * 60)


if __name__ == "__main__":
    main()
