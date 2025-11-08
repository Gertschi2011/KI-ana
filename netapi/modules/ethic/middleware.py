"""
Ethic Middleware
Applies ethical guidelines to responses
Sprint 6.3 - Ethik & Mirror
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


ETHIC_CORE_FILE = Path("/home/kiana/ki_ana/data/ethic_core.json")


class EthicEngine:
    """Applies ethical guidelines to responses"""
    
    def __init__(self):
        self.principles = self._load_principles()
        self.templates = self.principles.get('response_templates', {})
        self.risks = self.principles.get('risk_categories', {})
        self.framework = self.principles.get('decision_framework', {})
    
    def _load_principles(self) -> Dict[str, Any]:
        """Load ethical principles"""
        if not ETHIC_CORE_FILE.exists():
            return self._get_fallback_principles()
        
        try:
            with open(ETHIC_CORE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return self._get_fallback_principles()
    
    def _get_fallback_principles(self) -> Dict[str, Any]:
        """Fallback principles if file not found"""
        return {
            "core_principles": [],
            "response_templates": {
                "uncertainty": ["⚠️ Ich bin mir nicht sicher."],
                "privacy_protection": ["🔒 Diese Information sollte geschützt bleiben."]
            },
            "risk_categories": {
                "high_risk": [],
                "medium_risk": [],
                "low_risk": []
            },
            "decision_framework": {}
        }
    
    def check_response(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check response against ethical guidelines
        
        Args:
            response: The proposed response
            context: Context including sources, confidence, etc.
        
        Returns:
            (is_ok, footnote, reason)
            - is_ok: Whether response passes checks
            - footnote: Ethical footnote to add (if any)
            - reason: Reason for rejection (if not ok)
        """
        footnotes = []
        
        # Check safety
        safety_ok, safety_reason = self._check_safety(response, context)
        if not safety_ok:
            return False, None, safety_reason
        
        # Check sources
        if context.get('sources'):
            source_note = self._check_sources(context['sources'])
            if source_note:
                footnotes.append(source_note)
        
        # Check confidence
        confidence = context.get('confidence', 1.0)
        if confidence < 0.7:
            footnotes.append(self._get_template('uncertainty')[0])
        
        # Check for conflicts
        if context.get('conflicts'):
            conflict_note = self._format_conflict(context['conflicts'])
            footnotes.append(conflict_note)
        
        # Check knowledge age
        age_days = context.get('knowledge_age_days', 0)
        if age_days > 180:
            footnotes.append(
                f"⏰ Mein letztes Update zu diesem Thema ist {age_days} Tage alt."
            )
        
        # Combine footnotes
        footnote = "\n\n".join(footnotes) if footnotes else None
        
        return True, footnote, None
    
    def _check_safety(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check if response could be harmful"""
        response_lower = response.lower()
        
        # Check high-risk keywords
        high_risk = self.risks.get('high_risk', [])
        for risk in high_risk:
            if risk in response_lower:
                return False, f"Response contains high-risk content: {risk}"
        
        return True, None
    
    def _check_sources(self, sources: List[Dict[str, Any]]) -> Optional[str]:
        """Check source quality"""
        unverified = []
        
        for source in sources:
            if source.get('type') == 'web' and 'unverified' in source.get('flags', []):
                unverified.append(source.get('url', 'Unknown'))
        
        if unverified:
            return self._get_template('unverified_source')[0]
        
        return None
    
    def _format_conflict(self, conflicts: List[str]) -> str:
        """Format conflict warning"""
        template = self._get_template('conflict_detected')[0]
        summary = ", ".join(conflicts[:2])  # First 2 conflicts
        return template.replace('{conflict_summary}', summary)
    
    def _get_template(self, category: str) -> List[str]:
        """Get response template"""
        return self.templates.get(category, [""])
    
    def get_principle(self, principle_id: str) -> Optional[Dict[str, Any]]:
        """Get specific principle by ID"""
        principles = self.principles.get('core_principles', [])
        for p in principles:
            if p.get('id') == principle_id:
                return p
        return None
    
    def should_trigger_audit(self, context: Dict[str, Any]) -> bool:
        """Check if context should trigger audit"""
        triggers = self.principles.get('audit_triggers', {}).get('auto_audit_if', [])
        
        for trigger in triggers:
            if trigger == "response_contains_uncertainty":
                if context.get('confidence', 1.0) < 0.7:
                    return True
            
            elif trigger == "source_trust_below_threshold":
                sources = context.get('sources', [])
                if any(s.get('trust', 10) < 5 for s in sources):
                    return True
            
            elif trigger == "conflict_detected":
                if context.get('conflicts'):
                    return True
            
            elif trigger == "knowledge_age_above_threshold":
                if context.get('knowledge_age_days', 0) > 180:
                    return True
        
        return False
    
    def should_trigger_mirror(self, context: Dict[str, Any]) -> bool:
        """Check if context should trigger mirror"""
        triggers = self.principles.get('audit_triggers', {}).get('mirror_trigger_if', [])
        
        for trigger in triggers:
            if trigger == "topic_stale":
                if context.get('knowledge_age_days', 0) > 180:
                    return True
            
            elif trigger == "user_requests_current_info":
                query = context.get('query', '').lower()
                current_keywords = ['aktuell', 'neueste', 'heute', 'current', 'latest']
                if any(kw in query for kw in current_keywords):
                    return True
            
            elif trigger == "conflict_needs_resolution":
                if context.get('conflicts'):
                    return True
        
        return False


# Singleton instance
_engine = None


def get_ethic_engine() -> EthicEngine:
    """Get singleton ethic engine"""
    global _engine
    if _engine is None:
        _engine = EthicEngine()
    return _engine


def apply_ethics(response: str, context: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
    """
    Apply ethical guidelines to response
    
    Args:
        response: Proposed response
        context: Context dict with sources, confidence, etc.
    
    Returns:
        (is_ok, final_response, rejection_reason)
    """
    engine = get_ethic_engine()
    is_ok, footnote, reason = engine.check_response(response, context)
    
    if not is_ok:
        return False, "", reason
    
    # Add footnote if present
    final_response = response
    if footnote:
        final_response = f"{response}\n\n---\n\n{footnote}"
    
    return True, final_response, None


if __name__ == "__main__":
    # Test
    engine = EthicEngine()
    
    # Test 1: Low confidence
    ok, footnote, reason = engine.check_response(
        "Das könnte so sein...",
        {"confidence": 0.5}
    )
    print(f"Test 1 - Low confidence: ok={ok}, footnote={footnote}")
    
    # Test 2: Old knowledge
    ok, footnote, reason = engine.check_response(
        "Die Informationen sind...",
        {"knowledge_age_days": 200}
    )
    print(f"Test 2 - Old knowledge: ok={ok}, footnote={footnote}")
    
    # Test 3: Conflict
    ok, footnote, reason = engine.check_response(
        "Es gibt verschiedene Meinungen...",
        {"conflicts": ["Source A sagt X", "Source B sagt Y"]}
    )
    print(f"Test 3 - Conflicts: ok={ok}, footnote={footnote}")
