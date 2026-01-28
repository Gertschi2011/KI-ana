"""
Memory Integration for Chat
Bridges conversation memory with chat responses
"""
import json, time, re
from typing import List, Dict, Any, Optional
from pathlib import Path
from ... import memory_store as _mem
from .conversation_memory import save_conversation_to_memory, should_save_conversation

# Import user profile functions
try:
    from .user_profile import (
        get_user_profile,
        format_user_profile_context,
        update_user_profile_from_conversation
    )
except ImportError:
    # Fallback if module not found
    def get_user_profile(user_id: int):
        return None
    def format_user_profile_context(profile):
        return ""
    def update_user_profile_from_conversation(user_id, messages):
        return {}

def search_conversation_memory(query: str, user_id: int, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Search for relevant conversation memories
    Returns list of memory blocks with conversation context
    """
    try:
        # Search in memory store for conversation blocks
        results = _mem.search_blocks(query, top_k=limit)
        
        # Filter for conversation blocks
        conversation_blocks = []
        for block_id, score in results:
            try:
                block = _mem.get_block(block_id)
                if block and 'conversation' in block.get('tags', []):
                    conversation_blocks.append({
                        'id': block_id,
                        'title': block.get('title', ''),
                        'content': block.get('content', ''),
                        'score': score,
                        'meta': block.get('meta', {}),
                        'tags': block.get('tags', []),
                        'ts': block.get('ts', 0)
                    })
            except Exception:
                continue
        
        # Sort by score and limit
        conversation_blocks.sort(key=lambda x: x['score'], reverse=True)
        return conversation_blocks[:limit]
        
    except Exception:
        return []

def format_conversation_context(memories: List[Dict[str, Any]]) -> str:
    """
    Format conversation memories for context injection
    Returns compact, readable context string with active recall
    """
    if not memories:
        return ""
    
    context_parts = []
    for i, mem in enumerate(memories, 1):
        try:
            title = mem.get('title', 'Gespräch')
            content = mem.get('content', '')
            meta = mem.get('meta', {})
            conv_id = meta.get('conversation_id', '?')
            msg_count = meta.get('message_count', 0)
            
            # Extract key topics from content
            topics = []
            if 'Themen:' in content:
                topics_part = content.split('Themen:')[-1].strip()
                topics = [t.strip() for t in topics_part.split(',') if t.strip()][:3]
            
            # Format with active recall language
            mem_ref = f"📝 Ich erinnere mich an unser Gespräch über '{title}'"
            if topics:
                mem_ref += f" - wir sprachen über: {', '.join(topics)}"
            
            context_parts.append(mem_ref)
            
        except Exception:
            continue
    
    if context_parts:
        # Use more personal, child-like language
        intro = "**Was ich mich erinnere:**\n"
        return "\n\n" + intro + "\n".join(context_parts)
    return ""

def extract_memory_keywords(message: str) -> List[str]:
    """
    Extract keywords that might indicate memory retrieval intent
    """
    memory_keywords = [
        'erinnerst', 'gesprochen', 'früher', 'zuletzt', 'vorhin', 'damals',
        'schonmal', 'wieder', 'weiter', 'genau', 'korrekt', 'stimmt',
        'gesagt', 'gemeint', 'besprochen', 'thematisiert'
    ]
    
    msg_lower = message.lower()
    found_keywords = [kw for kw in memory_keywords if kw in msg_lower]
    return found_keywords

def should_use_memory(message: str) -> bool:
    """
    Determine if message requires memory retrieval
    """
    # Check for memory keywords
    if extract_memory_keywords(message):
        return True
    
    # Check for questions about past conversations
    memory_patterns = [
        r'was.*haben.*wir.*gesprochen',
        r'wann.*haben.*wir.*über.*gesprochen',
        r'kannst.*du.*dich.*erinnern',
        r'wie.*war.*das.*nochmal',
        r'was.*haben.*wir.*gemacht'
    ]
    
    msg_lower = message.lower()
    for pattern in memory_patterns:
        if re.search(pattern, msg_lower):
            return True
    
    return False

def build_memory_context(message: str, user_id: int) -> str:
    """
    Build memory context for message
    Relevance-gated: loads memories only when the message indicates recall intent.
    """
    ctx, _ids = build_memory_context_with_ids(message, user_id)
    return ctx


def build_memory_context_with_ids(message: str, user_id: int) -> tuple[str, List[str]]:
    """Like build_memory_context(), but also returns the memory block ids used.

    This enables transparency (`memory_ids`) whenever memory context is injected.
    """
    # Only load memory context when the user is asking about prior context.
    # This avoids injecting unrelated memories into normal queries.
    try:
        if not should_use_memory(message or ""):
            return "", []
    except Exception:
        return "", []

    # Search relevant conversation memories
    memories = search_conversation_memory(message, user_id, limit=3)
    try:
        mem_ids = [str(m.get('id')) for m in (memories or []) if m.get('id')]
    except Exception:
        mem_ids = []

    # Format for context injection
    context = format_conversation_context(memories)

    # Add user profile context
    try:
        user_profile = get_user_profile(user_id)
        if user_profile:
            profile_context = format_user_profile_context(user_profile)
            if profile_context:
                context = profile_context + "\n" + context
    except Exception:
        pass

    # Add KI_ana's self-awareness context if needed
    if any(kw in (message or "").lower() for kw in ['wer bist du', 'was bist du', 'dein name', 'dein zweck']):
        try:
            from .ai_consciousness import get_identity
            identity = get_identity()
            self_context = f"\n\n**Wer ich bin:** Ich bin {identity['name']} v{identity['version']}, eine {identity['type']}. Mein Zweck ist {identity['purpose']}."
            context += self_context
        except Exception:
            pass

    return context, mem_ids

async def auto_save_conversation_if_needed(
    conv_id: int, 
    user_id: int, 
    db
) -> Optional[str]:
    """
    Auto-save conversation to memory if criteria met
    Also updates user profile
    """
    try:
        from sqlalchemy import select
        from ...db import Conversation, Message
        
        # Get conversation
        conv = db.execute(select(Conversation).where(Conversation.id == conv_id)).scalar_one_or_none()
        if not conv:
            return None
        
        # Get messages
        messages_rows = db.execute(
            select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
        ).scalars().all()
        
        messages = [{'role': m.role, 'text': m.text} for m in messages_rows]
        
        # Check if should save
        if not should_save_conversation(
            conv_id, 
            len(messages),
            conv.created_at,
            conv.updated_at,
            conv.last_save_at
        ):
            return None
        
        # Save to memory
        block_id = await save_conversation_to_memory(
            conv_id,
            user_id,
            messages,
            conv.title
        )
        
        if block_id:
            # Update last_save_at
            conv.last_save_at = int(time.time())
            db.commit()
        
        return block_id
        
    except Exception:
        return None

def compact_response(response: str, max_length: int = 150) -> str:
    """
    Format response to be compact and readable
    """
    if not response:
        return response
    
    # Remove repetitive phrases
    repetitive_patterns = [
        r'Darüber weiß ich noch nichts – ich schaue kurz im Web nach\.?\s*\(Falls du willst, kann ich danach mehr ins Detail gehen\.\)\s*Leider habe ich dazu aktuell keine verlässlichen Quellen gefunden\.\s*Möchtest du mehr\? Ich kann vertiefen oder auf bestimmte Bereiche eingehen.*',
        r'Wenn du möchtest, kann ich.*',
        r'Möchtest du mehr\?.*',
        r'Sag mir einfach, was dich interessiert\.?'
    ]
    
    cleaned = response
    for pattern in repetitive_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
    
    # Strip whitespace
    cleaned = cleaned.strip()
    
    # If empty after cleaning, provide helpful short response
    if not cleaned:
        return "Das weiß ich aktuell nicht. Möchtest du etwas anderes erfahren?"
    
    # Truncate if too long
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rsplit(' ', 1)[0] + "..."
    
    return cleaned

def should_save_current_conversation(conv_id: int, user_id: int, db) -> bool:
    """
    Check if current conversation should be saved to memory
    """
    try:
        from ..models import Message
        # Get message count
        msg_count = db.query(Message).filter(Message.conv_id == conv_id).count()
        
        # Get time since last message
        last_msg = db.query(Message).filter(Message.conv_id == conv_id).order_by(Message.created_at.desc()).first()
        time_since_last = int(time.time()) - (last_msg.created_at if last_msg else 0)
        
        return should_save_conversation(msg_count, time_since_last)
    except Exception:
        return False

async def auto_save_conversation_if_needed(conv_id: int, user_id: int, db) -> Optional[str]:
    """
    Auto-save conversation to memory if criteria met
    Returns block_id if saved, None otherwise
    """
    if not should_save_current_conversation(conv_id, user_id, db):
        return None
    
    try:
        from ..models import Message, Conversation
        # Get conversation messages
        messages = db.query(Message).filter(Message.conv_id == conv_id).order_by(Message.created_at.asc()).all()
        
        # Convert to dict format
        msg_dicts = []
        full_text = ""
        for msg in messages:
            msg_dicts.append({
                'id': msg.id,
                'role': msg.role,
                'text': msg.text,
                'created_at': msg.created_at
            })
            full_text += f"{msg.role}: {msg.text}\n"
        
        # Get conversation title
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        title = conv.title if conv else "Gespräch"
        
        # AI decision: should this be remembered?
        try:
            from .ai_consciousness import should_remember
            decision = should_remember(full_text, f"conversation_{conv_id}")
            
            if not decision["should_remember"]:
                return None  # AI decided not to remember
                
        except Exception:
            pass  # Fallback to original logic
        
        # Save to memory
        block_id = await save_conversation_to_memory(
            conv_id=conv_id,
            user_id=user_id,
            messages=msg_dicts,
            conversation_title=title
        )
        
        return block_id
        
    except Exception:
        return None
