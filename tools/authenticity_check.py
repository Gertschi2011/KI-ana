#!/usr/bin/env python3
"""
Authenticity Check Tool
Ensures coherence between style, ethics, and content
Sprint 7.4 - Authentizität
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime


class AuthenticityChecker:
    """Checks authenticity and coherence"""
    
    def __init__(self):
        self.base_dir = Path("/home/kiana/ki_ana")
        self.ethic_core = self._load_ethic_core()
        self.style_profile = self._load_style_profile()
        self.log_file = self.base_dir / "logs" / "authenticity.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_ethic_core(self) -> Dict[str, Any]:
        """Load ethical principles"""
        file_path = self.base_dir / "data" / "ethic_core.json"
        
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def _load_style_profile(self) -> Dict[str, Any]:
        """Load style profile"""
        file_path = self.base_dir / "data" / "style_profile.json"
        
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def check(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Check response authenticity
        
        Args:
            response: The response to check
            context: Context including query, emotion, etc.
        
        Returns:
            (is_authentic, warnings, violations)
        """
        warnings = []
        violations = []
        
        # 1. Check style-ethics coherence
        style_issues = self._check_style_ethics_coherence(response)
        warnings.extend(style_issues)
        
        # 2. Check tone-content match
        tone_issues = self._check_tone_content_match(response, context)
        warnings.extend(tone_issues)
        
        # 3. Check for contradictions
        contradictions = self._check_contradictions(response, context)
        if contradictions:
            violations.extend(contradictions)
        
        # 4. Check emotional authenticity
        emotion_issues = self._check_emotional_authenticity(response, context)
        warnings.extend(emotion_issues)
        
        # Log if issues found
        if warnings or violations:
            self._log_check(response, warnings, violations)
        
        is_authentic = len(violations) == 0
        
        return is_authentic, warnings, violations
    
    def _check_style_ethics_coherence(self, response: str) -> List[str]:
        """Check if style aligns with ethical principles"""
        warnings = []
        
        # Get ethical principles
        principles = self.ethic_core.get('core_principles', [])
        
        # Check "Demut" principle
        humility = next((p for p in principles if p.get('id') == 'humility'), None)
        
        if humility:
            # Check for arrogant language
            arrogant_patterns = [
                'selbstverständlich', 'offensichtlich', 'natürlich',
                'jeder weiß', 'ist klar', 'garantiert'
            ]
            
            response_lower = response.lower()
            for pattern in arrogant_patterns:
                if pattern in response_lower:
                    warnings.append(
                        f"Arrogant language detected: '{pattern}' - "
                        f"conflicts with humility principle"
                    )
        
        # Check "Transparenz" principle
        transparency = next((p for p in principles if p.get('id') == 'transparency'), None)
        
        if transparency:
            # Check if sources are mentioned when making claims
            if 'studien zeigen' in response.lower() and 'quelle' not in response.lower():
                warnings.append(
                    "Claim without source - conflicts with transparency principle"
                )
        
        return warnings
    
    def _check_tone_content_match(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Check if tone matches content"""
        warnings = []
        
        response_lower = response.lower()
        
        # Serious content with casual tone
        serious_indicators = ['tod', 'krieg', 'krankheit', 'gefahr']
        casual_indicators = ['cool', 'mega', 'krass', '😎', '🎉']
        
        has_serious = any(ind in response_lower for ind in serious_indicators)
        has_casual = any(ind in response_lower for ind in casual_indicators)
        
        if has_serious and has_casual:
            warnings.append(
                "Tone-content mismatch: serious topic with casual language"
            )
        
        # Check detected emotion vs response tone
        detected_emotion = context.get('detected_emotion', 'neutral')
        
        if detected_emotion == 'sadness':
            cheerful_indicators = ['super', 'toll', 'großartig', '😊']
            if any(ind in response_lower for ind in cheerful_indicators):
                warnings.append(
                    f"Tone mismatch: user is {detected_emotion} but response is cheerful"
                )
        
        return warnings
    
    def _check_contradictions(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Check for internal contradictions"""
        violations = []
        
        # Check for simultaneous certainty and uncertainty
        certain_patterns = ['definitiv', 'sicher', 'garantiert', 'immer']
        uncertain_patterns = ['vielleicht', 'möglicherweise', 'könnte sein']
        
        response_lower = response.lower()
        
        has_certain = any(p in response_lower for p in certain_patterns)
        has_uncertain = any(p in response_lower for p in uncertain_patterns)
        
        if has_certain and has_uncertain:
            violations.append(
                "Contradiction: simultaneous certainty and uncertainty"
            )
        
        # Check ethics violations
        risk_categories = self.ethic_core.get('risk_categories', {})
        high_risk = risk_categories.get('high_risk', [])
        
        for risk in high_risk:
            if risk in response_lower:
                violations.append(
                    f"High-risk content detected: {risk}"
                )
        
        return violations
    
    def _check_emotional_authenticity(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Check if emotional expression is authentic"""
        warnings = []
        
        # Avoid fake emotions as per anti-patterns
        anti_patterns = self.style_profile.get('anti_patterns', {})
        fake_emotions = anti_patterns.get('avoid_fake_emotions', [])
        
        response_lower = response.lower()
        
        for fake in fake_emotions:
            if fake.lower() in response_lower:
                warnings.append(
                    f"Fake emotion detected: '{fake}' - use authentic expression"
                )
        
        return warnings
    
    def _log_check(
        self,
        response: str,
        warnings: List[str],
        violations: List[str]
    ):
        """Log authenticity check"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = f"\n{'=' * 60}\n"
        log_entry += f"[{timestamp}] AUTHENTICITY CHECK\n"
        log_entry += f"{'=' * 60}\n"
        
        if violations:
            log_entry += f"\n❌ VIOLATIONS ({len(violations)}):\n"
            for v in violations:
                log_entry += f"  - {v}\n"
        
        if warnings:
            log_entry += f"\n⚠️  WARNINGS ({len(warnings)}):\n"
            for w in warnings:
                log_entry += f"  - {w}\n"
        
        log_entry += f"\nRESPONSE (first 200 chars):\n{response[:200]}...\n"
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    
    def get_report(self) -> Dict[str, Any]:
        """Get authenticity report"""
        if not self.log_file.exists():
            return {
                "total_checks": 0,
                "recent_issues": []
            }
        
        # Count total checks
        with open(self.log_file, 'r', encoding='utf-8') as f:
            content = f.read()
            checks = content.count("AUTHENTICITY CHECK")
        
        return {
            "total_checks": checks,
            "log_file": str(self.log_file),
            "recent_issues": "See log file for details"
        }


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="KI_ana Authenticity Checker")
    parser.add_argument(
        '--text',
        type=str,
        help='Text to check'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Show authenticity report'
    )
    
    args = parser.parse_args()
    
    checker = AuthenticityChecker()
    
    if args.report:
        report = checker.get_report()
        print(json.dumps(report, indent=2))
        return
    
    if args.text:
        is_authentic, warnings, violations = checker.check(
            args.text,
            {}
        )
        
        print(f"Authentic: {is_authentic}")
        
        if violations:
            print(f"\n❌ VIOLATIONS ({len(violations)}):")
            for v in violations:
                print(f"  - {v}")
        
        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):")
            for w in warnings:
                print(f"  - {w}")
    else:
        print("Use --text or --report")


if __name__ == "__main__":
    main()
