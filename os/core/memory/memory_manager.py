"""
Memory Manager - Long-term conversation and preference storage

Features:
- Conversation history
- User preferences
- Learned patterns
- Context recall
- SQLite storage
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger


class MemoryManager:
    """Manages long-term memory storage"""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize memory manager
        
        Args:
            db_path: Path to SQLite database
        """
        if db_path is None:
            db_path = str(Path.home() / ".kiana" / "memory.db")
        
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
        logger.info(f"Memory manager initialized: {db_path}")
    
    def _init_database(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_input TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                context TEXT,
                metadata TEXT
            )
        """)
        
        # Preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT NOT NULL,
                pattern_data TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                last_seen TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
    
    async def store_conversation(
        self,
        user_input: str,
        ai_response: str,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Store a conversation exchange
        
        Args:
            user_input: User's message
            ai_response: AI's response
            context: Optional context data
            metadata: Optional metadata
            
        Returns:
            Conversation ID
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO conversations (timestamp, user_input, ai_response, context, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                user_input,
                ai_response,
                json.dumps(context) if context else None,
                json.dumps(metadata) if metadata else None
            ))
            
            conv_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.debug(f"Stored conversation: {conv_id}")
            return conv_id
            
        except Exception as e:
            logger.error(f"Failed to store conversation: {e}")
            return -1
    
    async def get_recent_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversations
        
        Args:
            limit: Number of conversations to retrieve
            
        Returns:
            List of conversation dicts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, timestamp, user_input, ai_response, context, metadata
                FROM conversations
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            conversations = []
            for row in rows:
                conversations.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "user_input": row[2],
                    "ai_response": row[3],
                    "context": json.loads(row[4]) if row[4] else None,
                    "metadata": json.loads(row[5]) if row[5] else None
                })
            
            return conversations
            
        except Exception as e:
            logger.error(f"Failed to get conversations: {e}")
            return []
    
    async def search_conversations(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search conversations by content
        
        Args:
            query: Search query
            limit: Max results
            
        Returns:
            List of matching conversations
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, timestamp, user_input, ai_response, context, metadata
                FROM conversations
                WHERE user_input LIKE ? OR ai_response LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                results.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "user_input": row[2],
                    "ai_response": row[3],
                    "context": json.loads(row[4]) if row[4] else None,
                    "metadata": json.loads(row[5]) if row[5] else None
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
            return []
    
    async def set_preference(self, key: str, value: Any) -> bool:
        """Set a user preference
        
        Args:
            key: Preference key
            value: Preference value
            
        Returns:
            Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO preferences (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, json.dumps(value), datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Set preference: {key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set preference: {e}")
            return False
    
    async def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference
        
        Args:
            key: Preference key
            default: Default value if not found
            
        Returns:
            Preference value or default
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT value FROM preferences WHERE key = ?
            """, (key,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return json.loads(row[0])
            else:
                return default
                
        except Exception as e:
            logger.error(f"Failed to get preference: {e}")
            return default
    
    async def get_all_preferences(self) -> Dict[str, Any]:
        """Get all preferences
        
        Returns:
            Dict of all preferences
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT key, value FROM preferences")
            rows = cursor.fetchall()
            conn.close()
            
            prefs = {}
            for row in rows:
                prefs[row[0]] = json.loads(row[1])
            
            return prefs
            
        except Exception as e:
            logger.error(f"Failed to get preferences: {e}")
            return {}
    
    async def learn_pattern(
        self,
        pattern_type: str,
        pattern_data: Dict[str, Any]
    ) -> bool:
        """Learn a usage pattern
        
        Args:
            pattern_type: Type of pattern (e.g., "command", "time", "context")
            pattern_data: Pattern data
            
        Returns:
            Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if pattern exists
            data_json = json.dumps(pattern_data)
            cursor.execute("""
                SELECT id, frequency FROM patterns
                WHERE pattern_type = ? AND pattern_data = ?
            """, (pattern_type, data_json))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update frequency
                cursor.execute("""
                    UPDATE patterns
                    SET frequency = frequency + 1, last_seen = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), existing[0]))
            else:
                # Insert new pattern
                cursor.execute("""
                    INSERT INTO patterns (pattern_type, pattern_data, last_seen)
                    VALUES (?, ?, ?)
                """, (pattern_type, data_json, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Learned pattern: {pattern_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to learn pattern: {e}")
            return False
    
    async def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_frequency: int = 1
    ) -> List[Dict[str, Any]]:
        """Get learned patterns
        
        Args:
            pattern_type: Filter by pattern type
            min_frequency: Minimum frequency
            
        Returns:
            List of patterns
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if pattern_type:
                cursor.execute("""
                    SELECT pattern_type, pattern_data, frequency, last_seen
                    FROM patterns
                    WHERE pattern_type = ? AND frequency >= ?
                    ORDER BY frequency DESC
                """, (pattern_type, min_frequency))
            else:
                cursor.execute("""
                    SELECT pattern_type, pattern_data, frequency, last_seen
                    FROM patterns
                    WHERE frequency >= ?
                    ORDER BY frequency DESC
                """, (min_frequency,))
            
            rows = cursor.fetchall()
            conn.close()
            
            patterns = []
            for row in rows:
                patterns.append({
                    "type": row[0],
                    "data": json.loads(row[1]),
                    "frequency": row[2],
                    "last_seen": row[3]
                })
            
            return patterns
            
        except Exception as e:
            logger.error(f"Failed to get patterns: {e}")
            return []
    
    async def get_context_for_query(self, query: str, max_items: int = 5) -> Dict[str, Any]:
        """Get relevant context for a query
        
        Args:
            query: User query
            max_items: Max context items
            
        Returns:
            Context dict with recent conversations and preferences
        """
        try:
            # Get recent relevant conversations
            conversations = await self.search_conversations(query, limit=max_items)
            
            # Get user preferences
            preferences = await self.get_all_preferences()
            
            # Get relevant patterns
            patterns = await self.get_patterns(min_frequency=2)
            
            context = {
                "recent_conversations": conversations[:3],
                "preferences": preferences,
                "patterns": patterns[:5],
                "query": query
            }
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to get context: {e}")
            return {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics
        
        Returns:
            Dict with memory stats
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Count conversations
            cursor.execute("SELECT COUNT(*) FROM conversations")
            conv_count = cursor.fetchone()[0]
            
            # Count preferences
            cursor.execute("SELECT COUNT(*) FROM preferences")
            pref_count = cursor.fetchone()[0]
            
            # Count patterns
            cursor.execute("SELECT COUNT(*) FROM patterns")
            pattern_count = cursor.fetchone()[0]
            
            # Get oldest conversation
            cursor.execute("SELECT MIN(timestamp) FROM conversations")
            oldest = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "conversations": conv_count,
                "preferences": pref_count,
                "patterns": pattern_count,
                "oldest_conversation": oldest,
                "database_size": Path(self.db_path).stat().st_size
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}


# Singleton instance
_memory_manager: Optional[MemoryManager] = None


async def get_memory_manager() -> MemoryManager:
    """Get or create memory manager singleton
    
    Returns:
        MemoryManager instance
    """
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
