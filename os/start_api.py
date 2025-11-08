#!/usr/bin/env python3
"""
KI-ana OS REST API Server Starter
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.api.rest_api import APIServer
from loguru import logger

def main():
    logger.info("🚀 Starting KI-ana OS API Server...")
    
    server = APIServer(host="0.0.0.0", port=8090)
    server.run()

if __name__ == "__main__":
    main()
