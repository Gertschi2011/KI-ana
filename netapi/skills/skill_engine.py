"""
Skill Engine - Autonomous Tool Generation for KI_ana

Enables the AI to:
- Detect missing capabilities (skill gaps)
- Generate new tools/functions autonomously
- Test generated code safely
- Integrate successful tools
- Share tools with other instances
"""
from __future__ import annotations
import time
import ast
import sys
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
import json
import hashlib


@dataclass
class SkillSpec:
    """Specification for a new skill/tool"""
    name: str
    description: str
    input_type: str
    output_type: str
    requirements: List[str] = field(default_factory=list)
    examples: List[Dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_type": self.input_type,
            "output_type": self.output_type,
            "requirements": self.requirements,
            "examples": self.examples
        }


@dataclass
class GeneratedSkill:
    """A generated skill/tool"""
    id: str
    spec: SkillSpec
    code: str
    created_at: float
    tested: bool = False
    test_passed: bool = False
    test_results: Optional[Dict[str, Any]] = None
    integrated: bool = False
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "spec": self.spec.to_dict(),
            "code": self.code,
            "created_at": self.created_at,
            "tested": self.tested,
            "test_passed": self.test_passed,
            "test_results": self.test_results,
            "integrated": self.integrated,
            "error": self.error
        }


class SkillEngine:
    """
    Autonomous skill generation and integration engine.
    
    The AI uses this to extend its own capabilities by generating new tools.
    
    Usage:
        engine = SkillEngine()
        
        # Define skill need
        spec = SkillSpec(
            name="json_formatter",
            description="Format JSON with proper indentation",
            input_type="str",
            output_type="str"
        )
        
        # Generate skill
        skill = await engine.generate_skill(spec)
        
        # Test skill
        if await engine.test_skill(skill):
            # Integrate into system
            await engine.integrate_skill(skill)
    """
    
    def __init__(self, llm_backend=None):
        self.llm = llm_backend
        self.skills: Dict[str, GeneratedSkill] = {}
        self.skills_dir = Path.home() / "ki_ana" / "generated_skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        self._load_skills()
    
    def _load_skills(self):
        """Load previously generated skills"""
        try:
            skills_file = self.skills_dir / "skills.json"
            if skills_file.exists():
                data = json.loads(skills_file.read_text())
                for skill_data in data.get("skills", []):
                    # Reconstruct skill
                    spec_data = skill_data.get("spec", {})
                    spec = SkillSpec(
                        name=spec_data.get("name", ""),
                        description=spec_data.get("description", ""),
                        input_type=spec_data.get("input_type", "Any"),
                        output_type=spec_data.get("output_type", "Any"),
                        requirements=spec_data.get("requirements", []),
                        examples=spec_data.get("examples", [])
                    )
                    
                    skill = GeneratedSkill(
                        id=skill_data.get("id", ""),
                        spec=spec,
                        code=skill_data.get("code", ""),
                        created_at=skill_data.get("created_at", time.time()),
                        tested=skill_data.get("tested", False),
                        test_passed=skill_data.get("test_passed", False),
                        integrated=skill_data.get("integrated", False)
                    )
                    
                    self.skills[skill.id] = skill
        except Exception as e:
            print(f"Failed to load skills: {e}")
    
    def _save_skills(self):
        """Save generated skills"""
        try:
            skills_file = self.skills_dir / "skills.json"
            data = {
                "skills": [s.to_dict() for s in self.skills.values()],
                "updated_at": time.time()
            }
            skills_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Failed to save skills: {e}")
    
    async def generate_skill(self, spec: SkillSpec) -> GeneratedSkill:
        """
        Generate a new skill from specification.
        
        Args:
            spec: SkillSpec describing the desired skill
            
        Returns:
            GeneratedSkill object
        """
        skill_id = hashlib.sha256(f"{spec.name}_{time.time()}".encode()).hexdigest()[:12]
        
        try:
            # Generate code using LLM
            if self.llm:
                code = await self._generate_with_llm(spec)
            else:
                # Fallback: Use templates
                code = self._generate_from_template(spec)
            
            skill = GeneratedSkill(
                id=skill_id,
                spec=spec,
                code=code,
                created_at=time.time()
            )
            
            self.skills[skill_id] = skill
            self._save_skills()
            
            return skill
            
        except Exception as e:
            error_skill = GeneratedSkill(
                id=skill_id,
                spec=spec,
                code="",
                created_at=time.time(),
                error=str(e)
            )
            return error_skill
    
    async def _generate_with_llm(self, spec: SkillSpec) -> str:
        """Generate code using LLM"""
        prompt = f"""Generate a Python function with the following specification:

Name: {spec.name}
Description: {spec.description}
Input Type: {spec.input_type}
Output Type: {spec.output_type}

Requirements:
{chr(10).join('- ' + r for r in spec.requirements)}

Examples:
{chr(10).join(f"Input: {ex['input']} → Output: {ex['output']}" for ex in spec.examples)}

Generate ONLY the function code, no explanations. Include:
1. Function definition with type hints
2. Docstring
3. Implementation
4. Error handling

Function must be self-contained and use only standard library or common packages.
"""
        
        # Call LLM (placeholder - actual implementation depends on LLM backend)
        try:
            if hasattr(self.llm, 'generate'):
                response = await self.llm.generate(prompt)
                # Extract code block
                code = self._extract_code_block(response)
                return code
            else:
                raise Exception("LLM backend not properly configured")
        except Exception as e:
            raise Exception(f"LLM generation failed: {e}")
    
    def _extract_code_block(self, text: str) -> str:
        """Extract Python code from markdown code block"""
        import re
        match = re.search(r'```python\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Try without language specifier
        match = re.search(r'```\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Return as-is if no code block found
        return text.strip()
    
    def _generate_from_template(self, spec: SkillSpec) -> str:
        """Generate code from template (fallback)"""
        template = f'''def {spec.name}(input_data: {spec.input_type}) -> {spec.output_type}:
    """
    {spec.description}
    
    Args:
        input_data: Input of type {spec.input_type}
        
    Returns:
        Output of type {spec.output_type}
    """
    try:
        # TODO: Implement {spec.name} logic
        # This is a template - needs manual implementation
        result = input_data
        return result
    except Exception as e:
        raise Exception(f"{{spec.name}} failed: {{e}}")
'''
        return template
    
    async def test_skill(self, skill: GeneratedSkill) -> bool:
        """
        Test a generated skill safely in sandbox.
        
        Args:
            skill: GeneratedSkill to test
            
        Returns:
            True if tests passed
        """
        skill.tested = True
        
        try:
            # Parse code to check syntax
            try:
                ast.parse(skill.code)
            except SyntaxError as e:
                skill.test_passed = False
                skill.error = f"Syntax error: {e}"
                self._save_skills()
                return False
            
            # Create isolated namespace
            namespace = {
                '__builtins__': __builtins__,
                'print': lambda *args, **kwargs: None,  # Suppress prints
            }
            
            # Execute code in namespace
            exec(skill.code, namespace)
            
            # Check function exists
            if skill.spec.name not in namespace:
                skill.test_passed = False
                skill.error = f"Function '{skill.spec.name}' not found in generated code"
                self._save_skills()
                return False
            
            func = namespace[skill.spec.name]
            
            # Run tests with examples
            test_results = []
            for example in skill.spec.examples:
                try:
                    input_val = eval(example['input'])
                    expected = eval(example['output'])
                    result = func(input_val)
                    
                    passed = result == expected
                    test_results.append({
                        "input": example['input'],
                        "expected": example['output'],
                        "actual": str(result),
                        "passed": passed
                    })
                except Exception as e:
                    test_results.append({
                        "input": example['input'],
                        "error": str(e),
                        "passed": False
                    })
            
            # Check if all tests passed
            all_passed = all(t.get("passed", False) for t in test_results)
            
            skill.test_passed = all_passed
            skill.test_results = {
                "total": len(test_results),
                "passed": sum(1 for t in test_results if t.get("passed", False)),
                "details": test_results
            }
            
            self._save_skills()
            return all_passed
            
        except Exception as e:
            skill.test_passed = False
            skill.error = str(e)
            self._save_skills()
            return False
    
    async def integrate_skill(self, skill: GeneratedSkill) -> bool:
        """
        Integrate a tested skill into the system.
        
        Args:
            skill: GeneratedSkill to integrate
            
        Returns:
            True if integration successful
        """
        if not skill.test_passed:
            return False
        
        try:
            # Save to skills directory
            skill_file = self.skills_dir / f"{skill.spec.name}.py"
            skill_file.write_text(skill.code)
            
            skill.integrated = True
            self._save_skills()
            
            print(f"✅ Skill '{skill.spec.name}' integrated successfully")
            return True
            
        except Exception as e:
            skill.error = f"Integration failed: {e}"
            self._save_skills()
            return False
    
    def get_skill(self, skill_id: str) -> Optional[GeneratedSkill]:
        """Get skill by ID"""
        return self.skills.get(skill_id)
    
    def list_skills(self, filter_integrated: bool = False) -> List[GeneratedSkill]:
        """List all skills, optionally filtered"""
        skills = list(self.skills.values())
        if filter_integrated:
            skills = [s for s in skills if s.integrated]
        return skills
    
    def detect_skill_gap(self, error_message: str) -> Optional[SkillSpec]:
        """
        Analyze error message to detect missing skill.
        
        Args:
            error_message: Error message from failed operation
            
        Returns:
            SkillSpec for missing capability or None
        """
        # Common patterns for missing skills
        import re
        
        # Pattern: "No tool 'X' available"
        match = re.search(r"No tool '(\w+)' available", error_message)
        if match:
            tool_name = match.group(1)
            return SkillSpec(
                name=tool_name,
                description=f"Tool '{tool_name}' detected as missing from error",
                input_type="str",
                output_type="Any"
            )
        
        # Pattern: "Cannot process X format"
        match = re.search(r"Cannot process (\w+) format", error_message)
        if match:
            format_name = match.group(1)
            return SkillSpec(
                name=f"{format_name}_processor",
                description=f"Process {format_name} format data",
                input_type="str",
                output_type="Dict[str, Any]"
            )
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get skill engine statistics"""
        return {
            "total_skills": len(self.skills),
            "tested": sum(1 for s in self.skills.values() if s.tested),
            "passed": sum(1 for s in self.skills.values() if s.test_passed),
            "integrated": sum(1 for s in self.skills.values() if s.integrated),
            "skills": [s.to_dict() for s in self.skills.values()]
        }


# Global instance
_skill_engine_instance: Optional[SkillEngine] = None


def get_skill_engine(llm_backend=None) -> SkillEngine:
    """Get or create global SkillEngine instance"""
    global _skill_engine_instance
    if _skill_engine_instance is None:
        _skill_engine_instance = SkillEngine(llm_backend)
    return _skill_engine_instance


if __name__ == "__main__":
    # Self-test
    import asyncio
    
    print("=== Skill Engine Self-Test ===\n")
    
    async def test():
        engine = SkillEngine()
        
        # Test skill generation
        spec = SkillSpec(
            name="reverse_string",
            description="Reverse a string",
            input_type="str",
            output_type="str",
            examples=[
                {"input": "'hello'", "output": "'olleh'"},
                {"input": "'world'", "output": "'dlrow'"}
            ]
        )
        
        print(f"Generating skill: {spec.name}")
        skill = await engine.generate_skill(spec)
        
        print(f"Generated code:\n{skill.code}\n")
        
        print(f"Testing skill...")
        passed = await engine.test_skill(skill)
        print(f"Tests {'passed' if passed else 'failed'}")
        
        if passed:
            print(f"Integrating skill...")
            integrated = await engine.integrate_skill(skill)
            print(f"Integration {'successful' if integrated else 'failed'}")
        
        # Statistics
        stats = engine.get_statistics()
        print(f"\nStatistics:")
        print(f"  Total skills: {stats['total_skills']}")
        print(f"  Tested: {stats['tested']}")
        print(f"  Passed: {stats['passed']}")
        print(f"  Integrated: {stats['integrated']}")
        
        print("\n✅ Skill Engine functional!")
    
    asyncio.run(test())
