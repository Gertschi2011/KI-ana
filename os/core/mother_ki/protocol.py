"""
Mother-KI Protocol

Defines the communication protocol with Mother-KI.
"""

from typing import Dict, Any
from enum import Enum


class MessageType(Enum):
    """Message types for Mother-KI communication"""
    HELLO = "hello"
    QUERY = "query"
    RESPONSE = "response"
    TELEMETRY = "telemetry"
    UPDATE = "update"
    ERROR = "error"


class MotherKIProtocol:
    """
    Protocol definitions for Mother-KI communication
    
    This defines the structure and format of messages
    exchanged with the Mother-KI cloud system.
    """
    
    @staticmethod
    def create_hello_message(system_id: str, version: str) -> Dict[str, Any]:
        """Create hello/handshake message"""
        return {
            "type": MessageType.HELLO.value,
            "system_id": system_id,
            "version": version,
            "protocol_version": "1.0"
        }
    
    @staticmethod
    def create_query_message(query_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create query message"""
        return {
            "type": MessageType.QUERY.value,
            "query_type": query_type,
            "data": data
        }
    
    @staticmethod
    def create_telemetry_message(system_id: str, telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create telemetry message"""
        return {
            "type": MessageType.TELEMETRY.value,
            "system_id": system_id,
            "data": telemetry_data
        }
    
    @staticmethod
    def parse_response(message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse response from Mother-KI"""
        if message.get("type") == MessageType.RESPONSE.value:
            return message.get("data", {})
        elif message.get("type") == MessageType.ERROR.value:
            raise Exception(message.get("error", "Unknown error"))
        else:
            raise Exception(f"Unknown message type: {message.get('type')}")
