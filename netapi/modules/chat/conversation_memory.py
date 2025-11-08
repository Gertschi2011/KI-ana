"""
Conversation Memory Module
Converts conversations into Memory Blocks with Blockchain signatures
"""
from typing import List, Dict, Any, Optional, Tuple
import time
import re
from datetime import datetime

def extract_conversation_topics(messages: List[Dict[str, Any]]) -> List[str]:
    """Extract main topics from conversation messages"""
    topics = []
    
    # Combine all user messages
    user_texts = [m.get("text", "") for m in messages if m.get("role") == "user"]
    combined = " ".join(user_texts)
    
    # Simple keyword extraction (can be enhanced with NLP)
    keywords = []
    
    # Common topic indicators
    topic_patterns = [
        r"über\s+(\w+)",  # "über Musik"
        r"zum\s+Thema\s+(\w+)",  # "zum Thema Sport"
        r"(\w+)\s+interessiert",  # "Filme interessiert"
        r"sprechen\s+über\s+(\w+)",  # "sprechen über Hobbys"
    ]
    
    for pattern in topic_patterns:
        matches = re.findall(pattern, combined, re.IGNORECASE)
        keywords.extend(matches)
    
    # Extract nouns (simple heuristic: capitalized words that aren't sentence starts)
    words = combined.split()
    for i, word in enumerate(words):
        if i > 0 and word[0].isupper() and len(word) > 3:
            keywords.append(word.lower())
    
    # Deduplicate and filter
    seen = set()
    for kw in keywords:
        kw_clean = kw.strip().lower()
        if kw_clean and kw_clean not in seen and len(kw_clean) > 2:
            topics.append(kw_clean)
            seen.add(kw_clean)
            if len(topics) >= 5:  # Max 5 topics
                break
    
    # Fallback: generic topic
    if not topics:
        topics = ["gespräch"]
    
    return topics


def generate_conversation_summary(
    messages: List[Dict[str, Any]], 
    max_length: int = 500
) -> str:
    """Generate a concise summary of the conversation"""
    
    if not messages:
        return "Leere Unterhaltung"
    
    # Count message types
    user_msgs = [m for m in messages if m.get("role") == "user"]
    ai_msgs = [m for m in messages if m.get("role") in ("ai", "assistant")]
    
    # Extract key points from user messages
    user_points = []
    for msg in user_msgs[:10]:  # First 10 user messages
        text = msg.get("text", "").strip()
        if text and len(text) > 20:
            # Take first sentence or first 100 chars
            first_sentence = text.split(".")[0].strip()
            if len(first_sentence) > 100:
                first_sentence = first_sentence[:97] + "..."
            user_points.append(first_sentence)
    
    # Build summary
    summary_parts = []
    
    # Opening
    if len(messages) == 1:
        summary_parts.append("Kurze Frage:")
    elif len(messages) < 5:
        summary_parts.append("Kurzer Austausch:")
    else:
        summary_parts.append(f"Gespräch mit {len(user_msgs)} Nachrichten:")
    
    # Add user points
    for i, point in enumerate(user_points[:3], 1):
        summary_parts.append(f"{i}. {point}")
    
    # Add topics
    topics = extract_conversation_topics(messages)
    if topics:
        summary_parts.append(f"\nThemen: {', '.join(topics[:3])}")
    
    summary = "\n".join(summary_parts)
    
    # Truncate if needed
    if len(summary) > max_length:
        summary = summary[:max_length-3] + "..."
    
    return summary


def create_conversation_title(messages: List[Dict[str, Any]]) -> str:
    """Create a concise title for the conversation"""
    
    if not messages:
        return "Leere Unterhaltung"
    
    # Get first user message
    first_user = next((m for m in messages if m.get("role") == "user"), None)
    
    if not first_user:
        return "Unterhaltung"
    
    text = first_user.get("text", "").strip()
    
    # Extract topic
    topics = extract_conversation_topics([first_user])
    
    if topics:
        # Use topic as title
        topic = topics[0].capitalize()
        if len(messages) > 5:
            return f"Gespräch über {topic}"
        else:
            return f"Frage zu {topic}"
    
    # Fallback: use first words
    words = text.split()[:10]
    title = " ".join(words)
    
    if len(title) > 60:
        title = title[:57] + "..."
    
    return title


async def save_conversation_to_memory(
    conv_id: int,
    user_id: int,
    messages: List[Dict[str, Any]],
    conversation_title: Optional[str] = None
) -> Optional[str]:
    """
    Save a conversation as a Memory Block
    Also updates user profile
    
    Returns: block_id if successful, None otherwise
    """
    try:
        from ... import memory_store as _mem
        from .router import upsert_addressbook
        
        # Update user profile from this conversation
        try:
            from .user_profile import update_user_profile_from_conversation
            update_user_profile_from_conversation(user_id, messages)
        except Exception:
            pass
        
        # Generate summary
        summary = generate_conversation_summary(messages)
        
        # Generate title
        if not conversation_title or conversation_title == "Neue Unterhaltung":
            title = create_conversation_title(messages)
        else:
            title = conversation_title
        
        # Extract topics
        topics = extract_conversation_topics(messages)
        
        # Create tags
        tags = ["conversation", "dialog", "memory"] + topics[:3]
        
        # Get user info for metadata
        user_email = "unknown"
        try:
            # messages might have user context
            # For now, use generic
            user_email = f"user_{user_id}"
        except:
            pass
        
        # Build metadata
        meta = {
            "conversation_id": conv_id,
            "user_id": user_id,
            "message_count": len(messages),
            "user_message_count": len([m for m in messages if m.get("role") == "user"]),
            "ai_message_count": len([m for m in messages if m.get("role") in ("ai", "assistant")]),
            "started_at": messages[0].get("created_at") if messages else int(time.time()),
            "ended_at": messages[-1].get("created_at") if messages else int(time.time()),
            "source": "conversation_auto_save",
            "participant": user_email
        }
        
        # Create memory block
        block_id = _mem.add_block(
            title=title,
            content=summary,
            tags=tags,
            url=None,
            meta=meta
        )
        
        # Index in addressbook
        if topics and block_id:
            try:
                upsert_addressbook(
                    topic=topics[0],
                    block_file=f"{block_id}.json",
                    url=""
                )
            except Exception:
                pass  # Not critical
        
        return block_id
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to save conversation to memory: {e}")
        return None


def should_save_conversation(
    message_count: int,
    time_since_last_message: int,
    last_save_at: Optional[int] = None
) -> bool:
    """
    Determine if a conversation should be saved to memory
    
    Criteria:
    - At least 3 messages
    - AND one of:
      - More than 10 messages
      - More than 5 minutes since last message (conversation ended)
      - More than 20 messages since last save
    """
    
    # Minimum threshold
    if message_count < 3:
        return False
    
    # Save long conversations
    if message_count >= 10:
        # Don't save too frequently
        if last_save_at and (int(time.time()) - last_save_at) < 60:
            return False
        return True
    
    # Save after conversation ends (5 min inactivity)
    if time_since_last_message > 300:  # 5 minutes
        return True
    
    # Save every 20 messages
    if last_save_at:
        messages_since_save = message_count  # Simplified
        if messages_since_save >= 20:
            return True
    
    return False
