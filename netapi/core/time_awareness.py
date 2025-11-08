"""
Time Awareness - Semantic Time Understanding for KI_ana

Gives the AI a human-like understanding of time:
- "gestern", "letzte Woche", "vor 2 Stunden"
- Relative time calculations
- Context-aware time references
- Proactive time-based actions
"""
from __future__ import annotations
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class TimeContext(Enum):
    """Time context categories"""
    IMMEDIATE = "immediate"      # Jetzt, gerade
    RECENT = "recent"            # Vor kurzem (< 1h)
    TODAY = "today"              # Heute
    YESTERDAY = "yesterday"      # Gestern
    THIS_WEEK = "this_week"      # Diese Woche
    LAST_WEEK = "last_week"      # Letzte Woche
    THIS_MONTH = "this_month"    # Diesen Monat
    LAST_MONTH = "last_month"    # Letzten Monat
    THIS_YEAR = "this_year"      # Dieses Jahr
    LONG_AGO = "long_ago"        # Lange her (> 1 Jahr)


@dataclass
class TimeEvent:
    """Represents a time-aware event"""
    timestamp: float
    event_type: str
    description: str
    context: TimeContext
    
    def age_seconds(self) -> float:
        """Get age in seconds"""
        return time.time() - self.timestamp
    
    def age_human(self) -> str:
        """Get human-readable age"""
        return format_relative_time(self.timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "description": self.description,
            "context": self.context.value,
            "age_seconds": self.age_seconds(),
            "age_human": self.age_human()
        }


class TimeAwareness:
    """
    Time awareness system for KI_ana.
    
    Provides semantic understanding of time and temporal context.
    
    Usage:
        ta = TimeAwareness()
        
        # Parse natural language time
        ts = ta.parse_time("vor 2 Stunden")
        
        # Get context for timestamp
        context = ta.get_time_context(some_timestamp)
        
        # Format relative time
        text = ta.format_relative(some_timestamp)
    """
    
    def __init__(self):
        self._events: List[TimeEvent] = []
        self._timezone_offset = 0  # UTC offset in hours
    
    def parse_time_expression(self, text: str) -> Optional[float]:
        """
        Parse natural language time expressions to timestamps.
        
        Args:
            text: Natural language like "vor 2 Stunden", "gestern", "letzte Woche"
            
        Returns:
            Unix timestamp or None
        """
        text_lower = text.lower().strip()
        now = time.time()
        
        # Immediate
        if any(word in text_lower for word in ["jetzt", "gerade", "sofort", "now"]):
            return now
        
        # Relative time with numbers
        import re
        
        # "vor X Stunden/Minuten/Tagen"
        match = re.search(r'vor\s+(\d+)\s+(sekunde|minute|stunde|tag|woche|monat|jahr)', text_lower)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            
            seconds_map = {
                "sekunde": 1,
                "minute": 60,
                "stunde": 3600,
                "tag": 86400,
                "woche": 604800,
                "monat": 2592000,  # ~30 days
                "jahr": 31536000   # ~365 days
            }
            
            if unit in seconds_map:
                return now - (amount * seconds_map[unit])
        
        # "in X Stunden/Minuten/Tagen" (future)
        match = re.search(r'in\s+(\d+)\s+(sekunde|minute|stunde|tag|woche|monat)', text_lower)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            
            seconds_map = {
                "sekunde": 1,
                "minute": 60,
                "stunde": 3600,
                "tag": 86400,
                "woche": 604800,
                "monat": 2592000
            }
            
            if unit in seconds_map:
                return now + (amount * seconds_map[unit])
        
        # Named time references
        dt_now = datetime.fromtimestamp(now)
        
        if "heute" in text_lower or "today" in text_lower:
            # Start of today
            return datetime(dt_now.year, dt_now.month, dt_now.day).timestamp()
        
        if "gestern" in text_lower or "yesterday" in text_lower:
            yesterday = dt_now - timedelta(days=1)
            return datetime(yesterday.year, yesterday.month, yesterday.day).timestamp()
        
        if "letzte woche" in text_lower or "last week" in text_lower:
            return now - (7 * 86400)
        
        if "letzten monat" in text_lower or "last month" in text_lower:
            return now - (30 * 86400)
        
        if "letztes jahr" in text_lower or "last year" in text_lower:
            return now - (365 * 86400)
        
        return None
    
    def get_time_context(self, timestamp: float) -> TimeContext:
        """
        Determine the time context for a timestamp.
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            TimeContext enum
        """
        now = time.time()
        age = now - timestamp
        
        if age < 60:  # < 1 minute
            return TimeContext.IMMEDIATE
        elif age < 3600:  # < 1 hour
            return TimeContext.RECENT
        elif age < 86400:  # < 1 day
            # Check if same day
            dt_now = datetime.fromtimestamp(now)
            dt_ts = datetime.fromtimestamp(timestamp)
            if dt_now.date() == dt_ts.date():
                return TimeContext.TODAY
            else:
                return TimeContext.YESTERDAY
        elif age < 172800:  # < 2 days
            return TimeContext.YESTERDAY
        elif age < 604800:  # < 1 week
            return TimeContext.THIS_WEEK
        elif age < 1209600:  # < 2 weeks
            return TimeContext.LAST_WEEK
        elif age < 2592000:  # < 30 days
            # Check if same month
            dt_now = datetime.fromtimestamp(now)
            dt_ts = datetime.fromtimestamp(timestamp)
            if dt_now.year == dt_ts.year and dt_now.month == dt_ts.month:
                return TimeContext.THIS_MONTH
            else:
                return TimeContext.LAST_MONTH
        elif age < 31536000:  # < 365 days
            # Check if same year
            dt_now = datetime.fromtimestamp(now)
            dt_ts = datetime.fromtimestamp(timestamp)
            if dt_now.year == dt_ts.year:
                return TimeContext.THIS_YEAR
            else:
                return TimeContext.LONG_AGO
        else:
            return TimeContext.LONG_AGO
    
    def format_relative_time(self, timestamp: float) -> str:
        """
        Format timestamp as human-readable relative time.
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            Human-readable string like "vor 2 Stunden"
        """
        return format_relative_time(timestamp)
    
    def track_event(self, event_type: str, description: str, timestamp: Optional[float] = None) -> TimeEvent:
        """
        Track a time-aware event.
        
        Args:
            event_type: Type of event (e.g., "conversation", "memory_save")
            description: Event description
            timestamp: Optional timestamp (default: now)
            
        Returns:
            TimeEvent object
        """
        ts = timestamp or time.time()
        context = self.get_time_context(ts)
        
        event = TimeEvent(
            timestamp=ts,
            event_type=event_type,
            description=description,
            context=context
        )
        
        self._events.append(event)
        
        # Keep only last 1000 events
        if len(self._events) > 1000:
            self._events = self._events[-1000:]
        
        return event
    
    def get_events_in_context(self, context: TimeContext) -> List[TimeEvent]:
        """Get all events in a specific time context"""
        return [e for e in self._events if e.context == context]
    
    def get_recent_events(self, limit: int = 10) -> List[TimeEvent]:
        """Get most recent events"""
        return sorted(self._events, key=lambda e: e.timestamp, reverse=True)[:limit]
    
    def time_since_last_event(self, event_type: str) -> Optional[float]:
        """
        Get seconds since last event of specific type.
        
        Returns:
            Seconds or None if no such event exists
        """
        matching = [e for e in self._events if e.event_type == event_type]
        if not matching:
            return None
        
        last = max(matching, key=lambda e: e.timestamp)
        return time.time() - last.timestamp
    
    def should_trigger_action(self, event_type: str, interval_seconds: float) -> bool:
        """
        Check if enough time has passed since last event to trigger action.
        
        Args:
            event_type: Type of event to check
            interval_seconds: Required interval in seconds
            
        Returns:
            True if action should be triggered
        """
        since_last = self.time_since_last_event(event_type)
        if since_last is None:
            return True  # Never happened, so yes
        return since_last >= interval_seconds
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get time awareness statistics"""
        return {
            "total_events": len(self._events),
            "by_context": {
                ctx.value: len(self.get_events_in_context(ctx))
                for ctx in TimeContext
            },
            "recent_events": [e.to_dict() for e in self.get_recent_events(5)]
        }


def format_relative_time(timestamp: float) -> str:
    """
    Format timestamp as human-readable relative time.
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        German text like "vor 2 Stunden", "gestern", "gerade eben"
    """
    now = time.time()
    diff = now - timestamp
    
    # Future (should be rare)
    if diff < 0:
        diff = abs(diff)
        if diff < 60:
            return "in wenigen Sekunden"
        elif diff < 3600:
            mins = int(diff / 60)
            return f"in {mins} Minute{'n' if mins != 1 else ''}"
        elif diff < 86400:
            hours = int(diff / 3600)
            return f"in {hours} Stunde{'n' if hours != 1 else ''}"
        else:
            days = int(diff / 86400)
            return f"in {days} Tag{'en' if days != 1 else ''}"
    
    # Past
    if diff < 10:
        return "gerade eben"
    elif diff < 60:
        secs = int(diff)
        return f"vor {secs} Sekunde{'n' if secs != 1 else ''}"
    elif diff < 3600:
        mins = int(diff / 60)
        return f"vor {mins} Minute{'n' if mins != 1 else ''}"
    elif diff < 86400:
        hours = int(diff / 3600)
        return f"vor {hours} Stunde{'n' if hours != 1 else ''}"
    elif diff < 172800:  # < 2 days
        return "gestern"
    elif diff < 604800:  # < 1 week
        days = int(diff / 86400)
        return f"vor {days} Tage{'n' if days != 1 else ''}"
    elif diff < 2592000:  # < 30 days
        weeks = int(diff / 604800)
        return f"vor {weeks} Woche{'n' if weeks != 1 else ''}"
    elif diff < 31536000:  # < 1 year
        months = int(diff / 2592000)
        return f"vor {months} Monat{'en' if months != 1 else ''}"
    else:
        years = int(diff / 31536000)
        return f"vor {years} Jahr{'en' if years != 1 else ''}"


def parse_duration(text: str) -> Optional[int]:
    """
    Parse duration expression to seconds.
    
    Args:
        text: Like "2 Stunden", "30 Minuten", "1 Tag"
        
    Returns:
        Duration in seconds or None
    """
    import re
    text_lower = text.lower().strip()
    
    match = re.search(r'(\d+)\s*(sekunde|minute|stunde|tag|woche|monat)', text_lower)
    if not match:
        return None
    
    amount = int(match.group(1))
    unit = match.group(2)
    
    seconds_map = {
        "sekunde": 1,
        "minute": 60,
        "stunde": 3600,
        "tag": 86400,
        "woche": 604800,
        "monat": 2592000
    }
    
    return amount * seconds_map.get(unit, 0)


# Global instance
_time_awareness_instance: Optional[TimeAwareness] = None


def get_time_awareness() -> TimeAwareness:
    """Get or create global TimeAwareness instance"""
    global _time_awareness_instance
    if _time_awareness_instance is None:
        _time_awareness_instance = TimeAwareness()
    return _time_awareness_instance


if __name__ == "__main__":
    # Self-test
    print("=== Time Awareness Self-Test ===\n")
    
    ta = TimeAwareness()
    
    # Test 1: Parse expressions
    print("1. Parsing Time Expressions:")
    expressions = [
        "vor 2 Stunden",
        "gestern",
        "letzte Woche",
        "in 30 Minuten"
    ]
    for expr in expressions:
        ts = ta.parse_time_expression(expr)
        if ts:
            print(f"  '{expr}' → {ta.format_relative_time(ts)}")
    
    # Test 2: Context detection
    print("\n2. Time Context Detection:")
    test_times = [
        (time.time() - 30, "30 seconds ago"),
        (time.time() - 3600, "1 hour ago"),
        (time.time() - 86400, "1 day ago"),
        (time.time() - 604800, "1 week ago")
    ]
    for ts, label in test_times:
        ctx = ta.get_time_context(ts)
        print(f"  {label}: {ctx.value}")
    
    # Test 3: Event tracking
    print("\n3. Event Tracking:")
    ta.track_event("test", "First test event")
    time.sleep(0.1)
    ta.track_event("test", "Second test event")
    
    events = ta.get_recent_events(2)
    for e in events:
        print(f"  {e.event_type}: {e.age_human()}")
    
    # Test 4: Trigger check
    print("\n4. Action Trigger:")
    should = ta.should_trigger_action("test", 1.0)
    print(f"  Should trigger (1s interval): {should}")
    
    print("\n✅ Time Awareness functional!")
