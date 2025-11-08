"""
System Integration - Activate and Coordinate All New Features

Integrates all new capabilities:
- Time Awareness
- Proactive Actions
- Autonomous Execution
- Multi-Modal (Vision & Audio)
- Skill Engine
- Blockchain
- Distributed Sub-Minds

This module ties everything together.
"""
from __future__ import annotations
import asyncio
import time
from typing import Dict, Any, Optional
from pathlib import Path
import json


class SystemIntegration:
    """
    Central integration hub for all AI capabilities.
    
    Coordinates:
    - Time awareness
    - Proactive actions
    - Autonomous learning
    - Multi-modal processing
    - Skill generation
    - Blockchain memory
    - Distributed sub-minds
    
    Usage:
        integration = SystemIntegration()
        await integration.initialize()
        await integration.start()
    """
    
    def __init__(self):
        self.initialized = False
        self.running = False
        self.components = {}
        
        # Runtime directory
        self.runtime_dir = Path.home() / "ki_ana" / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.runtime_dir / "system_status.json"
    
    async def initialize(self) -> Dict[str, bool]:
        """
        Initialize all system components.
        
        Returns:
            Dict of component initialization status
        """
        results = {}
        
        print("🚀 Initializing KI_ana Advanced Features...\n")
        
        # 1. Time Awareness
        try:
            from .time_awareness import get_time_awareness
            self.components['time_awareness'] = get_time_awareness()
            results['time_awareness'] = True
            print("✅ Time Awareness initialized")
        except Exception as e:
            results['time_awareness'] = False
            print(f"❌ Time Awareness failed: {e}")
        
        # 2. Proactive Actions
        try:
            from .proactive_actions import get_proactive_engine
            self.components['proactive_engine'] = get_proactive_engine()
            results['proactive_engine'] = True
            print("✅ Proactive Engine initialized")
        except Exception as e:
            results['proactive_engine'] = False
            print(f"❌ Proactive Engine failed: {e}")
        
        # 3. Autonomous Executor
        try:
            from .autonomous_execution import get_autonomous_executor
            self.components['autonomous_executor'] = get_autonomous_executor()
            results['autonomous_executor'] = True
            print("✅ Autonomous Executor initialized")
        except Exception as e:
            results['autonomous_executor'] = False
            print(f"❌ Autonomous Executor failed: {e}")
        
        # 4. Vision Processor
        try:
            from ..multimodal import get_vision_processor
            self.components['vision'] = get_vision_processor()
            results['vision'] = True
            status = "available" if self.components['vision'].available else "model not installed"
            print(f"✅ Vision Processor initialized ({status})")
        except Exception as e:
            results['vision'] = False
            print(f"❌ Vision Processor failed: {e}")
        
        # 5. Audio Processor
        try:
            from ..multimodal import get_audio_processor
            self.components['audio'] = get_audio_processor()
            results['audio'] = True
            stt = "✓" if self.components['audio'].stt_available else "✗"
            tts = "✓" if self.components['audio'].tts_available else "✗"
            print(f"✅ Audio Processor initialized (STT: {stt}, TTS: {tts})")
        except Exception as e:
            results['audio'] = False
            print(f"❌ Audio Processor failed: {e}")
        
        # 6. Skill Engine
        try:
            from ..skills import get_skill_engine
            self.components['skill_engine'] = get_skill_engine()
            results['skill_engine'] = True
            print("✅ Skill Engine initialized")
        except Exception as e:
            results['skill_engine'] = False
            print(f"❌ Skill Engine failed: {e}")
        
        # 7. Knowledge Chain (Blockchain)
        try:
            from ..blockchain import get_knowledge_chain
            self.components['blockchain'] = get_knowledge_chain()
            results['blockchain'] = True
            chain_info = self.components['blockchain'].get_chain_info()
            print(f"✅ Knowledge Chain initialized ({chain_info['length']} blocks)")
        except Exception as e:
            results['blockchain'] = False
            print(f"❌ Knowledge Chain failed: {e}")
        
        # 8. SubMind Network
        try:
            from ..distributed import get_submind_network
            self.components['submind_network'] = get_submind_network()
            results['submind_network'] = True
            network_stats = self.components['submind_network'].get_statistics()
            print(f"✅ SubMind Network initialized ({network_stats['total_subminds']} sub-minds)")
        except Exception as e:
            results['submind_network'] = False
            print(f"❌ SubMind Network failed: {e}")
        
        # 9. Meta-Mind
        try:
            from .meta_mind import get_meta_mind
            self.components['meta_mind'] = get_meta_mind()
            results['meta_mind'] = True
            print("✅ Meta-Mind initialized")
        except Exception as e:
            results['meta_mind'] = False
            print(f"❌ Meta-Mind failed: {e}")
        
        # 10. Autonomous Goals
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path.home() / "ki_ana"))
            from system.autonomous_goals import get_autonomous_goal_engine
            self.components['goals_engine'] = get_autonomous_goal_engine()
            results['goals_engine'] = True
            print("✅ Autonomous Goals initialized")
        except Exception as e:
            results['goals_engine'] = False
            print(f"❌ Autonomous Goals failed: {e}")
        
        self.initialized = True
        success_count = sum(results.values())
        total_count = len(results)
        
        print(f"\n{'='*50}")
        print(f"Initialization Complete: {success_count}/{total_count} components")
        print(f"{'='*50}\n")
        
        self._save_status(results)
        
        return results
    
    async def start(self):
        """Start all background services"""
        if not self.initialized:
            await self.initialize()
        
        print("🎯 Starting background services...\n")
        
        self.running = True
        tasks = []
        
        # Start Proactive Engine
        if 'proactive_engine' in self.components:
            try:
                task = await self.components['proactive_engine'].start(check_interval=300)
                tasks.append(task)
                print("✅ Proactive Engine started (checking every 5 min)")
            except Exception as e:
                print(f"⚠️  Proactive Engine start failed: {e}")
        
        # Start SubMind Network Coordinator
        if 'submind_network' in self.components:
            try:
                task = await self.components['submind_network'].start(check_interval=30)
                tasks.append(task)
                print("✅ SubMind Network started (coordinating every 30s)")
            except Exception as e:
                print(f"⚠️  SubMind Network start failed: {e}")
        
        print(f"\n{'='*50}")
        print(f"System Fully Operational - {len(tasks)} services running")
        print(f"{'='*50}\n")
        
        return tasks
    
    def stop(self):
        """Stop all background services"""
        print("\n🛑 Stopping services...\n")
        
        if 'proactive_engine' in self.components:
            self.components['proactive_engine'].stop()
            print("✅ Proactive Engine stopped")
        
        if 'submind_network' in self.components:
            self.components['submind_network'].stop()
            print("✅ SubMind Network stopped")
        
        self.running = False
        print("\nAll services stopped.\n")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        status = {
            "initialized": self.initialized,
            "running": self.running,
            "timestamp": time.time(),
            "components": {}
        }
        
        # Time Awareness
        if 'time_awareness' in self.components:
            ta = self.components['time_awareness']
            status['components']['time_awareness'] = ta.get_statistics()
        
        # Proactive Engine
        if 'proactive_engine' in self.components:
            pe = self.components['proactive_engine']
            status['components']['proactive_engine'] = pe.get_statistics()
        
        # Autonomous Executor
        if 'autonomous_executor' in self.components:
            ae = self.components['autonomous_executor']
            status['components']['autonomous_executor'] = ae.get_statistics()
        
        # Vision
        if 'vision' in self.components:
            v = self.components['vision']
            status['components']['vision'] = v.get_statistics()
        
        # Audio
        if 'audio' in self.components:
            a = self.components['audio']
            status['components']['audio'] = a.get_statistics()
        
        # Skill Engine
        if 'skill_engine' in self.components:
            se = self.components['skill_engine']
            status['components']['skill_engine'] = se.get_statistics()
        
        # Blockchain
        if 'blockchain' in self.components:
            bc = self.components['blockchain']
            status['components']['blockchain'] = bc.get_statistics()
        
        # SubMind Network
        if 'submind_network' in self.components:
            sn = self.components['submind_network']
            status['components']['submind_network'] = sn.get_statistics()
        
        # Meta-Mind
        if 'meta_mind' in self.components:
            mm = self.components['meta_mind']
            status['components']['meta_mind'] = mm.get_statistics()
        
        # Autonomous Goals
        if 'goals_engine' in self.components:
            ge = self.components['goals_engine']
            status['components']['goals_engine'] = ge.get_stats()
        
        return status
    
    def _save_status(self, results: Dict[str, bool]):
        """Save initialization status"""
        try:
            status = {
                "initialized_at": time.time(),
                "components": results,
                "success_rate": sum(results.values()) / len(results) if results else 0.0
            }
            self.status_file.write_text(json.dumps(status, indent=2))
        except Exception:
            pass


# Global instance
_system_integration_instance: Optional[SystemIntegration] = None


def get_system_integration() -> SystemIntegration:
    """Get or create global SystemIntegration instance"""
    global _system_integration_instance
    if _system_integration_instance is None:
        _system_integration_instance = SystemIntegration()
    return _system_integration_instance


async def initialize_all_features():
    """Convenience function to initialize all features"""
    integration = get_system_integration()
    return await integration.initialize()


async def start_all_services():
    """Convenience function to start all services"""
    integration = get_system_integration()
    return await integration.start()


if __name__ == "__main__":
    # Self-test
    import asyncio
    
    print("="*60)
    print(" "*15 + "KI_ana System Integration")
    print("="*60 + "\n")
    
    async def test():
        integration = SystemIntegration()
        
        # Initialize
        results = await integration.initialize()
        
        # Start services
        await integration.start()
        
        # Wait a bit
        print("\nRunning for 10 seconds...")
        await asyncio.sleep(10)
        
        # Get status
        print("\nSystem Status:")
        status = integration.get_system_status()
        print(f"  Initialized: {status['initialized']}")
        print(f"  Running: {status['running']}")
        print(f"  Components: {len(status['components'])}")
        
        # Stop
        integration.stop()
        
        print("\n✅ System Integration Test Complete!")
    
    asyncio.run(test())
