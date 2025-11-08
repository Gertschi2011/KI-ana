"""
User Profile System
Builds and maintains user profiles based on conversations
"""
import json, time
from typing import Dict, Any, List, Optional
from pathlib import Path
from ... import memory_store as _mem

PROFILE_DIR = Path(__file__).resolve().parent.parent.parent / "memory" / "user_profiles"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Load user profile from storage
    """
    try:
        profile_file = PROFILE_DIR / f"user_{user_id}.json"
        if profile_file.exists():
            return json.loads(profile_file.read_text())
        return None
    except Exception:
        return None

def save_user_profile(user_id: int, profile: Dict[str, Any]) -> bool:
    """
    Save user profile to storage
    """
    try:
        profile_file = PROFILE_DIR / f"user_{user_id}.json"
        profile['last_updated'] = int(time.time())
        profile_file.write_text(json.dumps(profile, ensure_ascii=False, indent=2))
        return True
    except Exception:
        return False

def update_user_profile_from_conversation(
    user_id: int,
    messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Extract and update user profile information from conversation
    """
    profile = get_user_profile(user_id) or {
        'user_id': user_id,
        'created_at': int(time.time()),
        'interests': [],
        'frequent_topics': {},
        'conversation_style': 'normal',
        'preferred_language': 'de',
        'learning_style': 'visual',
        'total_conversations': 0,
        'total_messages': 0
    }
    
    # Count messages
    profile['total_messages'] += len(messages)
    profile['total_conversations'] += 1
    
    # Extract interests and topics from user messages
    user_messages = [m for m in messages if m.get('role') == 'user']
    
    for msg in user_messages:
        text = msg.get('text', '').lower()
        
        # Detect interests
        interest_keywords = {
            'programmieren': 'Programmierung',
            'code': 'Programmierung',
            'kochen': 'Kochen',
            'rezept': 'Kochen',
            'sport': 'Sport',
            'fitness': 'Fitness',
            'musik': 'Musik',
            'kunst': 'Kunst',
            'reisen': 'Reisen',
            'urlaub': 'Reisen',
            'game': 'Gaming',
            'spielen': 'Gaming',
            'fotografie': 'Fotografie',
            'foto': 'Fotografie',
            'garten': 'Gartenarbeit',
            'pflanzen': 'Gartenarbeit',
            'film': 'Filme',
            'serie': 'Serien',
            'buch': 'Lesen',
            'lesen': 'Lesen'
        }
        
        for keyword, interest in interest_keywords.items():
            if keyword in text:
                if interest not in profile['interests']:
                    profile['interests'].append(interest)
        
        # Track frequent topics (simple word frequency)
        words = text.split()
        for word in words:
            if len(word) > 4:  # Only meaningful words
                profile['frequent_topics'][word] = profile['frequent_topics'].get(word, 0) + 1
    
    # Keep only top 20 frequent topics
    if len(profile['frequent_topics']) > 20:
        sorted_topics = sorted(profile['frequent_topics'].items(), key=lambda x: x[1], reverse=True)
        profile['frequent_topics'] = dict(sorted_topics[:20])
    
    # Keep only top 10 interests
    profile['interests'] = list(set(profile['interests']))[:10]
    
    # Save profile
    save_user_profile(user_id, profile)
    
    return profile

def format_user_profile_context(profile: Dict[str, Any]) -> str:
    """
    Format user profile for context injection
    Uses child-like language
    """
    if not profile:
        return ""
    
    parts = []
    
    # Interests
    interests = profile.get('interests', [])
    if interests:
        parts.append(f"**Was ich über dich weiß:** Du interessierst dich für {', '.join(interests[:5])}")
    
    # Conversation count
    conv_count = profile.get('total_conversations', 0)
    if conv_count > 0:
        if conv_count == 1:
            parts.append("Dies ist unser erstes Gespräch! 🌱")
        elif conv_count < 5:
            parts.append(f"Wir haben schon {conv_count} Gespräche geführt 💬")
        elif conv_count < 20:
            parts.append(f"Wir kennen uns schon gut - {conv_count} Gespräche! 🤗")
        else:
            parts.append(f"Wir sind richtig gute Freunde - {conv_count} Gespräche! 💝")
    
    if parts:
        return "\n" + "\n".join(parts) + "\n"
    return ""

def get_conversation_statistics(user_id: int) -> Dict[str, Any]:
    """
    Get statistics about user's conversations
    """
    profile = get_user_profile(user_id)
    if not profile:
        return {
            'total_conversations': 0,
            'total_messages': 0,
            'interests': [],
            'top_topics': []
        }
    
    # Get top topics
    topics = profile.get('frequent_topics', {})
    top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        'total_conversations': profile.get('total_conversations', 0),
        'total_messages': profile.get('total_messages', 0),
        'interests': profile.get('interests', []),
        'top_topics': [t[0] for t in top_topics]
    }
