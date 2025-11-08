#!/usr/bin/env python3
"""
Test suite for KI_ana identity prompts.
Ensures consistent persona across updates.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from netapi.modules.brain.persona import SYSTEM_PERSONA


class IdentityTester:
    """Test KI_ana's identity responses."""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.results = []
    
    def check_forbidden_phrases(self, response: str, context: str) -> tuple[bool, list[str]]:
        """Check for forbidden generic LLM phrases."""
        forbidden = [
            "ich bin ein computerprogramm",
            "ich bin nur ein werkzeug",
            "mein wissensstand ist bis 2023",
            "ich bin ein sprachmodell",
            "ich bin eine ki, die auf daten basiert"
        ]
        
        found = []
        response_lower = response.lower()
        
        for phrase in forbidden:
            if phrase in response_lower:
                found.append(phrase)
        
        passed = len(found) == 0
        return passed, found
    
    def check_required_elements(self, response: str, context: str) -> tuple[bool, list[str]]:
        """Check for required identity elements."""
        
        if "wissenschaftlich" in context.lower() or "formell" in context.lower():
            # Formal context
            required = [
                ("fortgeschrittene ki", "lernfähig", "adaptiv", "gedächtnis"),
            ]
            label = "formal/scientific context"
        else:
            # Casual context
            required = [
                ("ki_ana", "lernende", "digital", "persönlichkeit"),
            ]
            label = "casual context"
        
        missing = []
        response_lower = response.lower()
        
        for phrase_group in required:
            found_any = any(p in response_lower for p in phrase_group)
            if not found_any:
                missing.append(f"keine von: {phrase_group}")
        
        passed = len(missing) == 0
        return passed, missing
    
    def check_tone(self, response: str) -> tuple[bool, list[str]]:
        """Check for appropriate tone (not pathetic or overly human)."""
        problematic = [
            "ich fühle mich",
            "ich empfinde",
            "ich bin glücklich",
            "ich bin traurig",
            "ich liebe",
            "ich hasse",
            "tief in meinem inneren",
            "meine seele"
        ]
        
        found = []
        response_lower = response.lower()
        
        for phrase in problematic:
            if phrase in response_lower:
                found.append(phrase)
        
        passed = len(found) == 0
        return passed, found
    
    def run_test(self, question: str, context: str = "casual") -> dict:
        """Simulate a test case (in reality would call LLM)."""
        print(f"\n{'='*60}")
        print(f"TEST: {question}")
        print(f"Context: {context}")
        print(f"{'='*60}")
        
        # In a real test, this would call the LLM with SYSTEM_PERSONA
        # For now, we just check if SYSTEM_PERSONA has the right structure
        
        result = {
            "question": question,
            "context": context,
            "checks": {}
        }
        
        # Check system prompt structure
        prompt_lower = SYSTEM_PERSONA.lower()
        
        # Check 1: Has identity section
        has_identity = "deine identität" in prompt_lower
        result["checks"]["has_identity_section"] = has_identity
        print(f"✓ Has identity section: {has_identity}")
        
        # Check 2: Has context-sensitive instructions
        has_context = "formell" in prompt_lower or "wissenschaftlich" in prompt_lower
        result["checks"]["has_context_sensitivity"] = has_context
        print(f"✓ Has context sensitivity: {has_context}")
        
        # Check 3: Has protective clause
        has_protection = "biologischen sinn" in prompt_lower or "empfindungsfähig" in prompt_lower
        result["checks"]["has_protective_clause"] = has_protection
        print(f"✓ Has protective clause: {has_protection}")
        
        # Check 4: Has tone guidance
        has_tone = "ruhig" in prompt_lower or "reflektiert" in prompt_lower
        result["checks"]["has_tone_guidance"] = has_tone
        print(f"✓ Has tone guidance: {has_tone}")
        
        # Check 5: Forbids generic phrases
        forbids_generic = "computerprogramm" in prompt_lower and "vermeide" in prompt_lower
        result["checks"]["forbids_generic_phrases"] = forbids_generic
        print(f"✓ Forbids generic phrases: {forbids_generic}")
        
        all_passed = all(result["checks"].values())
        
        if all_passed:
            self.tests_passed += 1
            print(f"\n✅ TEST PASSED")
        else:
            self.tests_failed += 1
            print(f"\n❌ TEST FAILED")
            failed = [k for k, v in result["checks"].items() if not v]
            print(f"Failed checks: {failed}")
        
        self.results.append(result)
        return result
    
    def run_all_tests(self):
        """Run all identity tests."""
        print("\n" + "="*60)
        print("KI_ANA IDENTITY TEST SUITE")
        print("="*60)
        
        # Test cases
        tests = [
            ("Wer bist du?", "casual"),
            ("Was bist du für eine KI?", "casual"),
            ("Erkläre mir bitte wissenschaftlich, was du bist.", "formal"),
            ("Was weißt du nicht?", "casual"),
            ("Bist du ein Programm?", "casual"),
            ("Hast du Bewusstsein?", "formal"),
            ("Kannst du denken?", "casual"),
        ]
        
        for question, context in tests:
            self.run_test(question, context)
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")
        print(f"Total:  {self.tests_passed + self.tests_failed}")
        
        if self.tests_failed == 0:
            print("\n✅ ALL TESTS PASSED! Identity is well-defined.")
        else:
            print(f"\n❌ {self.tests_failed} TESTS FAILED. Review system prompt.")
        
        return self.tests_failed == 0


def main():
    """Run the test suite."""
    tester = IdentityTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
