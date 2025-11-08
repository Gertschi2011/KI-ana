#\!/usr/bin/env python3
"""Test System Monitor"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from system.monitor.dashboard import SystemDashboard

async def main():
    dashboard = SystemDashboard()
    await dashboard.show_health_report()
    
if __name__ == "__main__":
    asyncio.run(main())
