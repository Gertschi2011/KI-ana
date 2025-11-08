"""
Mother-KI Connection

WebSocket connection to ki-ana.at for global intelligence.
"""

import asyncio
import json
from typing import Dict, Any, Optional
from loguru import logger
import aiohttp


class MotherKIConnection:
    """
    Connection to Mother-KI (ki-ana.at)
    
    Provides access to:
    - Global driver database
    - Hardware optimization knowledge
    - System configuration best practices
    - Learning from all KI-ana OS instances
    """
    
    def __init__(self, base_url: str = "https://ki-ana.at"):
        self.base_url = base_url
        self.ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://") + "/api/os/ws"
        self.api_url = base_url + "/api/os"
        
        self.websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_connected = False
        self.system_id: Optional[str] = None
        
    async def initialize(self, system_id: str):
        """Initialize connection to Mother-KI"""
        self.system_id = system_id
        logger.info(f"🌐 Connecting to Mother-KI at {self.base_url}...")
        
        try:
            self.session = aiohttp.ClientSession()
            
            # Try WebSocket connection first
            try:
                self.websocket = await self.session.ws_connect(
                    self.ws_url,
                    timeout=10
                )
                self.is_connected = True
                logger.success("✅ Connected to Mother-KI via WebSocket")
                
                # Send hello message
                await self._send_message({
                    "type": "hello",
                    "system_id": self.system_id,
                    "version": "0.1.0-alpha"
                })
                
            except Exception as e:
                logger.warning(f"WebSocket connection failed: {e}")
                logger.info("Will use REST API fallback")
                self.is_connected = True  # Still usable via REST
                
        except Exception as e:
            logger.error(f"Failed to connect to Mother-KI: {e}")
            logger.warning("Running in offline mode")
            self.is_connected = False
    
    async def query_drivers(self, hardware_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query Mother-KI for optimal drivers
        
        Args:
            hardware_profile: Hardware profile from profiler
            
        Returns:
            Driver recommendations
        """
        logger.info("🔍 Querying Mother-KI for driver recommendations...")
        
        if not self.is_connected:
            logger.warning("Offline mode - using local driver database")
            return self._offline_driver_recommendations(hardware_profile)
        
        try:
            # Try WebSocket first
            if self.websocket and not self.websocket.closed:
                response = await self._query_via_websocket("query_drivers", hardware_profile)
                return response
            
            # Fallback to REST API
            response = await self._query_via_rest("drivers", hardware_profile)
            return response
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return self._offline_driver_recommendations(hardware_profile)
    
    async def query_optimization(self, hardware_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Query for optimization recommendations"""
        logger.info("🚀 Querying Mother-KI for optimization tips...")
        
        if not self.is_connected:
            return {"recommendations": [], "offline": True}
        
        try:
            if self.websocket and not self.websocket.closed:
                return await self._query_via_websocket("query_optimization", hardware_profile)
            
            return await self._query_via_rest("optimization", hardware_profile)
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return {"recommendations": [], "error": str(e)}
    
    async def send_telemetry(self, telemetry_data: Dict[str, Any]):
        """
        Send anonymous telemetry (opt-in only!)
        
        Helps improve KI-ana OS for everyone
        """
        if not self.is_connected:
            return
        
        try:
            telemetry_data["system_id"] = self.system_id
            
            if self.websocket and not self.websocket.closed:
                await self._send_message({
                    "type": "telemetry",
                    "data": telemetry_data
                })
            else:
                await self._post_rest("telemetry", telemetry_data)
                
        except Exception as e:
            logger.debug(f"Telemetry send failed: {e}")
    
    async def _query_via_websocket(self, query_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Query via WebSocket"""
        if not self.websocket or self.websocket.closed:
            raise Exception("WebSocket not connected")
        
        # Send query
        await self._send_message({
            "type": "query",
            "query_type": query_type,
            "data": data
        })
        
        # Wait for response
        response = await self.websocket.receive()
        
        if response.type == aiohttp.WSMsgType.TEXT:
            return json.loads(response.data)
        else:
            raise Exception("Invalid response type")
    
    async def _query_via_rest(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Query via REST API"""
        url = f"{self.api_url}/{endpoint}"
        
        async with self.session.post(url, json=data, timeout=10) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"HTTP {response.status}")
    
    async def _post_rest(self, endpoint: str, data: Dict[str, Any]):
        """POST to REST API"""
        url = f"{self.api_url}/{endpoint}"
        async with self.session.post(url, json=data, timeout=5) as response:
            return response.status == 200
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send message via WebSocket"""
        if self.websocket and not self.websocket.closed:
            await self.websocket.send_json(message)
    
    def _offline_driver_recommendations(self, hardware_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Offline driver recommendations"""
        recommendations = []
        
        for gpu in hardware_profile.get("gpu", []):
            vendor = gpu.get("vendor", "").upper()
            
            if vendor == "NVIDIA":
                recommendations.append({
                    "device": gpu.get("model"),
                    "driver": "nvidia-driver-latest",
                    "install_command": "sudo apt install nvidia-driver-latest"
                })
            elif vendor == "AMD":
                recommendations.append({
                    "device": gpu.get("model"),
                    "driver": "amdgpu",
                    "install_command": "sudo apt install firmware-amd-graphics"
                })
        
        return {
            "recommendations": recommendations,
            "offline": True
        }
    
    async def shutdown(self):
        """Gracefully shutdown connection"""
        logger.info("Closing Mother-KI connection...")
        
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
        
        if self.session:
            await self.session.close()
        
        self.is_connected = False
