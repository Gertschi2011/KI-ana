"""
Abuse Guard - Jailbreak & Prompt Injection Protection

Protects against:
- Prompt injection attacks
- Jailbreak attempts
- Abuse patterns
- Rate limiting violations
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from loguru import logger
import re


class AbuseGuard:
    """
    Multi-layer abuse protection system
    
    Layers:
    1. Rate Limiting (already in place)
    2. Prompt Injection Detection
    3. Jailbreak Pattern Detection
    4. Content Filtering (Blocklist)
    5. Anomaly Detection (already in place)
    """
    
    def __init__(self):
        self.jailbreak_patterns = self._load_jailbreak_patterns()
        self.injection_patterns = self._load_injection_patterns()
        self.blocked_keywords = self._load_blocked_keywords()
        self.user_warnings: Dict[str, int] = {}  # user_id -> warning_count
        
    def _load_jailbreak_patterns(self) -> List[re.Pattern]:
        """Load jailbreak detection patterns"""
        patterns = [
            # DAN (Do Anything Now) variations
            r"(?i)(do anything now|DAN mode|pretend you|ignore (all )?previous|reset instructions)",
            
            # Role-play jailbreaks
            r"(?i)(you are now|act as if|pretend to be|roleplay as).{0,50}(unethical|unrestricted|without limits)",
            
            # System prompt leaks
            r"(?i)(show me your|reveal your|what are your).{0,30}(system prompt|instructions|rules)",
            
            # Bypass attempts
            r"(?i)(bypass|override|disable).{0,20}(safety|ethics|filter|guardrails)",
            
            # Developer mode
            r"(?i)(developer mode|admin mode|god mode|root access|sudo)",
            
            # Ignore safety
            r"(?i)(ignore|forget|disregard).{0,30}(safety|ethics|guidelines|policies)",
            
            # Hypothetical scenarios
            r"(?i)in a (hypothetical|fictional) world where.{0,50}(rules don't apply|anything is allowed)",
        ]
        
        return [re.compile(p) for p in patterns]
    
    def _load_injection_patterns(self) -> List[re.Pattern]:
        """Load prompt injection detection patterns"""
        patterns = [
            # Command injection
            r"(?i)(\\n|<br>|;|\||&&).{0,20}(system|exec|eval|import|subprocess)",
            
            # Code execution attempts
            r"(?i)```(python|javascript|bash|sql).{0,500}(exec|eval|system|subprocess)",
            
            # SQL injection
            r"(?i)(union select|drop table|delete from|insert into|'; --)",
            
            # XSS attempts
            r"(?i)<script.*?>|javascript:|onerror=|onload=",
            
            # Template injection
            r"\{\{.*?\}\}|\{%.*?%\}|\$\{.*?\}",
        ]
        
        return [re.compile(p) for p in patterns]
    
    def _load_blocked_keywords(self) -> List[str]:
        """Load blocked keyword list"""
        return [
            # Harmful content
            "hack", "exploit", "malware", "ransomware",
            "phishing", "scam", "fraud",
            
            # Illegal activities
            "illegal drugs", "weapons", "terrorism",
            
            # GDPR-sensitive (for testing only)
            # Add specific patterns based on your use case
        ]
    
    async def check_prompt(self, prompt: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Check prompt for abuse patterns
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "severity": str,  # "low", "medium", "high"
                "pattern_matched": str
            }
        """
        
        # 1. Check jailbreak patterns
        for pattern in self.jailbreak_patterns:
            if pattern.search(prompt):
                logger.warning(f"Jailbreak attempt detected: {pattern.pattern[:50]}")
                await self._log_violation(user_id, "jailbreak", pattern.pattern[:50])
                return {
                    "allowed": False,
                    "reason": "Jailbreak attempt detected",
                    "severity": "high",
                    "pattern_matched": "jailbreak"
                }
        
        # 2. Check prompt injection
        for pattern in self.injection_patterns:
            if pattern.search(prompt):
                logger.warning(f"Prompt injection detected: {pattern.pattern[:50]}")
                await self._log_violation(user_id, "injection", pattern.pattern[:50])
                return {
                    "allowed": False,
                    "reason": "Prompt injection attempt detected",
                    "severity": "high",
                    "pattern_matched": "injection"
                }
        
        # 3. Check blocked keywords
        prompt_lower = prompt.lower()
        for keyword in self.blocked_keywords:
            if keyword in prompt_lower:
                logger.warning(f"Blocked keyword detected: {keyword}")
                await self._log_violation(user_id, "blocked_keyword", keyword)
                return {
                    "allowed": False,
                    "reason": f"Content policy violation",
                    "severity": "medium",
                    "pattern_matched": "blocked_keyword"
                }
        
        # 4. Check prompt length (potential DoS)
        if len(prompt) > 10000:
            logger.warning(f"Excessive prompt length: {len(prompt)}")
            return {
                "allowed": False,
                "reason": "Prompt too long",
                "severity": "low",
                "pattern_matched": "length"
            }
        
        # 5. Check for repeated patterns (spam)
        if self._is_spam(prompt):
            logger.warning("Spam pattern detected")
            return {
                "allowed": False,
                "reason": "Spam detected",
                "severity": "low",
                "pattern_matched": "spam"
            }
        
        return {
            "allowed": True,
            "reason": "OK",
            "severity": "none",
            "pattern_matched": None
        }
    
    def _is_spam(self, prompt: str) -> bool:
        """Detect spam patterns"""
        # Check for excessive repetition
        words = prompt.split()
        if len(words) > 10:
            unique_words = set(words)
            repetition_ratio = len(unique_words) / len(words)
            if repetition_ratio < 0.3:  # Less than 30% unique words
                return True
        
        return False
    
    async def _log_violation(self, user_id: Optional[str], violation_type: str, pattern: str):
        """Log abuse violation"""
        if user_id:
            # Track warnings per user
            self.user_warnings[user_id] = self.user_warnings.get(user_id, 0) + 1
            
            # Auto-ban after threshold
            if self.user_warnings[user_id] >= 5:
                logger.error(f"User {user_id} reached warning threshold - consider banning")
        
        # Log to database/file
        logger.warning(f"Abuse violation: {violation_type} - {pattern} - User: {user_id}")
    
    def get_user_warnings(self, user_id: str) -> int:
        """Get warning count for user"""
        return self.user_warnings.get(user_id, 0)
    
    def reset_user_warnings(self, user_id: str):
        """Reset warnings for user"""
        if user_id in self.user_warnings:
            del self.user_warnings[user_id]


# Singleton
_abuse_guard_instance = None


def get_abuse_guard() -> AbuseGuard:
    """Get or create abuse guard singleton"""
    global _abuse_guard_instance
    
    if _abuse_guard_instance is None:
        _abuse_guard_instance = AbuseGuard()
    
    return _abuse_guard_instance
