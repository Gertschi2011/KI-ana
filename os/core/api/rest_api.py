"""
REST API Server

Provides REST API for KI-ana OS.
"""

from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
import uvicorn


class CommandRequest(BaseModel):
    command: str
    context: Dict[str, Any] = {}


class APIServer:
    """
    REST API Server for KI-ana OS
    
    Provides endpoints for:
    - Command execution
    - System status
    - Configuration
    - Remote control
    """
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.app = FastAPI(title="KI-ana OS API", version="0.1.0")
        
        self._setup_middleware()
        self._setup_routes()
    
    def _setup_middleware(self):
        """Setup middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self):
        """Setup API routes"""
        
        @self.app.get("/")
        async def root():
            return {
                "name": "KI-ana OS API",
                "version": "0.1.0",
                "status": "running"
            }
        
        @self.app.get("/status")
        async def get_status():
            """Get system status"""
            import psutil
            
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "status": "healthy"
            }
        
        @self.app.post("/command")
        async def execute_command(request: CommandRequest):
            """Execute a command"""
            try:
                # Get or create brain instance
                from core.ai_engine.enhanced_brain import EnhancedAIBrain
                
                # Use enhanced brain for API
                brain = EnhancedAIBrain()
                if not brain.is_ready:
                    await brain.initialize()
                
                logger.info(f"API command: {request.command}")
                result = await brain.process_command(request.command)
                
                return {
                    "success": result.get("success", False),
                    "command": request.command,
                    "response": result.get("response", "No response"),
                    "intent": result.get("intent"),
                    "result": result.get("result")
                }
            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "ok"}
    
    def run(self):
        """Run the API server"""
        logger.info(f"🚀 Starting API server on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")
