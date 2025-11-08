#!/usr/bin/env python3
"""
TimeFlow Scheduler
Automates periodic tasks: audits, mirrors, reflections
Sprint 6.3 - Ethik & Mirror
"""
import subprocess
import time
from pathlib import Path
from datetime import datetime
import json


class TimeFlowScheduler:
    """Manages scheduled tasks for KI_ana"""
    
    def __init__(self):
        self.base_dir = Path("/home/kiana/ki_ana")
        self.tools_dir = self.base_dir / "tools"
        self.log_file = self.base_dir / "data" / "scheduler.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, message: str):
        """Log message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        print(log_entry.strip())
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    
    def run_knowledge_audit(self) -> bool:
        """Run daily knowledge audit"""
        self.log("🔍 Running knowledge audit...")
        
        try:
            result = subprocess.run(
                ["python3", str(self.tools_dir / "knowledge_audit.py")],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                self.log("✅ Knowledge audit complete")
                return True
            else:
                self.log(f"❌ Audit failed: {result.stderr[:200]}")
                return False
        
        except subprocess.TimeoutExpired:
            self.log("⏰ Audit timed out after 5 minutes")
            return False
        except Exception as e:
            self.log(f"❌ Audit error: {str(e)}")
            return False
    
    def run_mirror(self, topic: str = None) -> bool:
        """Run mirror for topics"""
        self.log(f"🪞 Running mirror{f' for {topic}' if topic else ''}...")
        
        try:
            cmd = ["python3", str(self.tools_dir / "mirror.py")]
            if topic:
                cmd.extend(["--topic", topic])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes
            )
            
            if result.returncode == 0:
                self.log("✅ Mirror complete")
                return True
            else:
                self.log(f"❌ Mirror failed: {result.stderr[:200]}")
                return False
        
        except subprocess.TimeoutExpired:
            self.log("⏰ Mirror timed out")
            return False
        except Exception as e:
            self.log(f"❌ Mirror error: {str(e)}")
            return False
    
    def run_self_reflection(self) -> bool:
        """Create monthly self-reflection block"""
        self.log("🧠 Creating self-reflection block...")
        
        try:
            # Load recent audits
            audit_dir = self.base_dir / "data" / "audit"
            latest_audit = audit_dir / "latest_audit.json"
            
            reflection = {
                "id": f"reflection_{int(time.time())}",
                "type": "self_reflection",
                "title": f"Monthly Reflection {datetime.now().strftime('%Y-%m')}",
                "topic": "Self-Awareness",
                "topics_path": ["Meta", "Self-Reflection"],
                "timestamp": int(time.time()),
                "trust": 10,
                "content": {
                    "period": datetime.now().strftime("%Y-%m"),
                    "summary": "Monthly self-reflection on knowledge quality and learning",
                    "audit_summary": None,
                    "growth_areas": [
                        "Continue improving knowledge freshness",
                        "Resolve identified conflicts",
                        "Expand verified knowledge base"
                    ]
                },
                "tags": ["reflection", "meta", "monthly"]
            }
            
            # Add audit summary if available
            if latest_audit.exists():
                with open(latest_audit, 'r', encoding='utf-8') as f:
                    audit = json.load(f)
                    reflection["content"]["audit_summary"] = audit.get("stats", {})
            
            # Save reflection block
            reflection_dir = self.base_dir / "memory" / "long_term" / "blocks" / "reflections"
            reflection_dir.mkdir(parents=True, exist_ok=True)
            
            reflection_file = reflection_dir / f"reflection_{reflection['id']}.json"
            with open(reflection_file, 'w', encoding='utf-8') as f:
                json.dump(reflection, f, ensure_ascii=False, indent=2)
            
            self.log(f"✅ Reflection saved: {reflection_file.name}")
            return True
        
        except Exception as e:
            self.log(f"❌ Reflection error: {str(e)}")
            return False
    
    def run_daily_tasks(self):
        """Run daily scheduled tasks"""
        self.log("=" * 60)
        self.log("🌅 Daily tasks starting")
        
        # Knowledge audit
        self.run_knowledge_audit()
        
        self.log("🌅 Daily tasks complete")
        self.log("=" * 60)
    
    def run_weekly_tasks(self):
        """Run weekly scheduled tasks"""
        self.log("=" * 60)
        self.log("📅 Weekly tasks starting")
        
        # Mirror important topics
        topics = ["CVE", "Security", "Ubuntu"]
        for topic in topics:
            self.run_mirror(topic)
            time.sleep(5)  # Rate limiting
        
        self.log("📅 Weekly tasks complete")
        self.log("=" * 60)
    
    def run_monthly_tasks(self):
        """Run monthly scheduled tasks"""
        self.log("=" * 60)
        self.log("📆 Monthly tasks starting")
        
        # Self-reflection
        self.run_self_reflection()
        
        # Full mirror refresh
        self.run_mirror()
        
        self.log("📆 Monthly tasks complete")
        self.log("=" * 60)


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="KI_ana TimeFlow Scheduler")
    parser.add_argument(
        'task',
        choices=['daily', 'weekly', 'monthly', 'audit', 'mirror', 'reflect'],
        help='Task to run'
    )
    parser.add_argument(
        '--topic',
        type=str,
        help='Topic for mirror (optional)'
    )
    
    args = parser.parse_args()
    
    scheduler = TimeFlowScheduler()
    
    if args.task == 'daily':
        scheduler.run_daily_tasks()
    elif args.task == 'weekly':
        scheduler.run_weekly_tasks()
    elif args.task == 'monthly':
        scheduler.run_monthly_tasks()
    elif args.task == 'audit':
        scheduler.run_knowledge_audit()
    elif args.task == 'mirror':
        scheduler.run_mirror(args.topic)
    elif args.task == 'reflect':
        scheduler.run_self_reflection()


if __name__ == "__main__":
    main()
