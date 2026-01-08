"""
Simplified, Clean Response Pipeline for KI_ana

Replaces the complex, multi-layered response generation with a clear, maintainable flow:

1. Input Processing (question normalization, context extraction)
2. Tool Execution (if needed: memory, web, calc)
3. LLM Response Generation (using context from tools)
4. Self-Reflection (quality check BEFORE output)
5. Retry on Low Quality (with improved prompts)
6. Final Output (clean, direct answer)

This pipeline implements the first step towards autonomous, self-reflecting AI.

Key Principles:
- Transparency: Every step is traceable
- Quality: Self-reflection ensures good outputs
- Learning: Each interaction is logged for improvement
- Simplicity: No hidden formatters or templates
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from .reflector import ResponseReflector, EvaluationResult, get_reflector

try:
    from ..learning.hub import LearningHub, get_learning_hub
except ImportError:
    LearningHub = None  # type: ignore
    get_learning_hub = None  # type: ignore


@dataclass
class PipelineContext:
    """Accumulated context during pipeline execution"""
    question: str
    tools_used: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)
    memory_ids: List[str] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    flags: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tools_used": self.tools_used,
            "sources": self.sources,
            "memory_ids": self.memory_ids,
            "trace": self.trace,
            "metadata": self.metadata,
        }


@dataclass
class PipelineResponse:
    """Final response from pipeline"""
    ok: bool
    reply: str
    evaluation: Optional[EvaluationResult] = None
    context: Optional[PipelineContext] = None
    retry_count: int = 0
    total_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "ok": self.ok,
            "reply": self.reply,
            "retry_count": self.retry_count,
            "total_time_ms": self.total_time_ms,
        }
        if self.evaluation:
            result["quality_score"] = self.evaluation.overall_score
            result["confidence"] = self.evaluation.confidence
        if self.context:
            result.update(self.context.to_dict())
        return result


class ResponsePipeline:
    """
    Clean, maintainable response generation pipeline.
    
    Usage:
        pipeline = ResponsePipeline(llm_backend, reflector, tools)
        response = pipeline.generate("Was ist 2+2?")
        print(response.reply)  # "4"
        print(response.evaluation.overall_score)  # 0.95
    """
    
    def __init__(
        self,
        llm_backend,
        reflector: Optional[ResponseReflector] = None,
        tools: Optional[Dict[str, Any]] = None,
        max_retries: int = 2,
        enable_reflection: bool = True,
        quality_threshold: float = 0.7
    ):
        """
        Args:
            llm_backend: LLM instance for generation (e.g., llm_local)
            reflector: ResponseReflector instance (created if None)
            tools: Dict of available tools {name: callable}
            max_retries: Max attempts to generate good response
            enable_reflection: If False, skip quality checks (faster but risky)
            quality_threshold: Minimum quality score to accept
        """
        self.llm = llm_backend
        self.reflector = reflector or get_reflector(llm_backend, quality_threshold)
        self.tools = tools or {}
        self.max_retries = max_retries
        self.enable_reflection = enable_reflection
        self.quality_threshold = quality_threshold
        
        # Learning Hub for continuous improvement
        self.learning_hub = get_learning_hub() if get_learning_hub else None
        
    def generate(
        self,
        question: str,
        user_context: Optional[Dict[str, Any]] = None,
        persona: str = "helpful",
        lang: str = "de"
    ) -> PipelineResponse:
        """
        Generate response through clean pipeline.
        
        Args:
            question: User's question
            user_context: Additional context (user preferences, conversation history, etc.)
            persona: Response style ("helpful", "concise", "detailed", etc.)
            lang: Language code
            
        Returns:
            PipelineResponse with answer and metadata
        """
        start_time = time.time()
        context = PipelineContext(question=question)
        
        # === Step 1: Input Processing ===
        processed_question = self._preprocess_question(question, user_context)
        context.trace.append({"step": "preprocess", "input": question, "output": processed_question})
        
        # === Step 2: Determine if tools are needed ===
        needs_tools, tool_plan = self._analyze_question(processed_question)
        context.trace.append({"step": "analysis", "needs_tools": needs_tools, "plan": tool_plan})
        
        # === Step 3: Execute tools if needed ===
        tool_results = {}
        if needs_tools and tool_plan:
            tool_results = self._execute_tools(tool_plan, context)
            context.trace.append({"step": "tools", "results_summary": {k: str(v)[:100] for k, v in tool_results.items()}})
        
        # === Step 4: Generate LLM response ===
        attempts = 0
        best_response = None
        best_evaluation = None
        
        while attempts <= self.max_retries:
            # Build context-aware prompt
            llm_prompt = self._build_prompt(
                question=processed_question,
                tool_results=tool_results,
                persona=persona,
                lang=lang,
                retry_hints=best_evaluation.suggestions if best_evaluation else None
            )
            
            # Generate response
            response = self._generate_llm_response(llm_prompt, lang)
            
            if not response:
                attempts += 1
                continue
            
            # === Step 5: Self-Reflection (if enabled) ===
            if self.enable_reflection:
                evaluation = self.reflector.evaluate(
                    question=processed_question,
                    answer=response,
                    context=context.to_dict()
                )
                
                context.trace.append({
                    "step": "reflection",
                    "attempt": attempts + 1,
                    "score": evaluation.overall_score,
                    "needs_retry": evaluation.needs_retry
                })
                
                # Check if quality acceptable
                if evaluation.overall_score >= self.quality_threshold:
                    # Success!
                    end_time = time.time()
                    # Learn from this interaction (success path)
                    if self.learning_hub and response:
                        try:
                            self.learning_hub.record_interaction(
                                question=processed_question,
                                answer=response,
                                quality_score=evaluation.overall_score,
                                tools_used=[t["tool"] for t in context.tools_used],
                                retry_count=attempts,
                            )
                        except Exception as e:
                            print(f"Learning Hub error: {e}")
                    return PipelineResponse(
                        ok=True,
                        reply=response,
                        evaluation=evaluation,
                        context=context,
                        retry_count=attempts,
                        total_time_ms=int((end_time - start_time) * 1000)
                    )
                
                # Quality too low - track best attempt and retry
                if best_evaluation is None or evaluation.overall_score > best_evaluation.overall_score:
                    best_response = response
                    best_evaluation = evaluation
                
                attempts += 1
                
                if attempts > self.max_retries:
                    # Max retries reached - return best attempt
                    context.trace.append({"step": "max_retries", "returning": "best_attempt"})
                    break
            else:
                # Reflection disabled - return immediately
                end_time = time.time()
                # Learn from this interaction (no-reflection path)
                if self.learning_hub and response:
                    try:
                        self.learning_hub.record_interaction(
                            question=processed_question,
                            answer=response,
                            quality_score=0.7,
                            tools_used=[t["tool"] for t in context.tools_used],
                            retry_count=0,
                        )
                    except Exception as e:
                        print(f"Learning Hub error: {e}")
                return PipelineResponse(
                    ok=True,
                    reply=response,
                    evaluation=None,
                    context=context,
                    retry_count=0,
                    total_time_ms=int((end_time - start_time) * 1000)
                )
        
        # Return best attempt (if any retries happened)
        end_time = time.time()
        
        final_response = PipelineResponse(
            ok=True,
            reply=best_response or "Entschuldigung, ich konnte keine zufriedenstellende Antwort generieren.",
            evaluation=best_evaluation,
            context=context,
            retry_count=attempts,
            total_time_ms=int((end_time - start_time) * 1000)
        )
        
        # Learn from this interaction
        if self.learning_hub and final_response.reply:
            try:
                self.learning_hub.record_interaction(
                    question=processed_question,
                    answer=final_response.reply,
                    quality_score=best_evaluation.overall_score if best_evaluation else 0.5,
                    tools_used=[t["tool"] for t in context.tools_used],
                    retry_count=attempts
                )
            except Exception as e:
                # Don't fail on learning errors
                print(f"Learning Hub error: {e}")
        
        return final_response
    
    def _preprocess_question(self, question: str, user_context: Optional[Dict[str, Any]]) -> str:
        """
        Normalize and enhance question.
        
        Could add:
        - Spell checking
        - Language detection
        - Context expansion from conversation history
        """
        # For now, just strip and basic normalization
        processed = question.strip()
        
        # TODO: Add more sophisticated preprocessing
        # - Resolve pronouns from context
        # - Expand abbreviations
        # - Detect question type
        
        return processed
    
    def _analyze_question(self, question: str) -> Tuple[bool, Optional[List[str]]]:
        """
        Determine if tools are needed and which ones.
        
        Returns:
            (needs_tools, tool_plan)
        
        Future: Use LLM to generate optimal tool plan
        Current: Simple heuristics
        """
        q_lower = question.lower()
        tool_plan = []
        
        # Math/Calc detection
        import re
        if re.search(r'\d+\s*[\+\-\*/]\s*\d+', question):
            tool_plan.append("calc")
        
        # Memory search for knowledge questions
        knowledge_patterns = ["was ist", "wer ist", "wie", "warum", "erkläre", "beschreibe"]
        if any(p in q_lower for p in knowledge_patterns):
            tool_plan.append("memory")
        
        # Web search for current/unknown information
        current_patterns = ["aktuell", "heute", "neueste", "letzte", "jetzt"]
        if any(p in q_lower for p in current_patterns):
            tool_plan.append("web")
        
        needs_tools = len(tool_plan) > 0
        return needs_tools, tool_plan if needs_tools else None
    
    def _execute_tools(self, tool_plan: List[str], context: PipelineContext) -> Dict[str, Any]:
        """
        Execute planned tools and collect results.
        
        Args:
            tool_plan: List of tool names to execute
            context: Pipeline context (updated with tool results)
            
        Returns:
            Dict of tool results {tool_name: result}
        """
        results = {}
        
        for tool_name in tool_plan:
            tool_func = self.tools.get(tool_name)
            if not tool_func:
                context.trace.append({"step": "tool_error", "tool": tool_name, "error": "not_found"})
                continue
            
            tool_start = time.time()
            try:
                result = tool_func(context.question)
                tool_time = int((time.time() - tool_start) * 1000)
                results[tool_name] = result
                
                # Track tool usage
                context.tools_used.append({
                    "tool": tool_name,
                    "ok": True,
                    "result_summary": str(result)[:200] if result else None
                })
                
                # Learn from successful tool use
                if self.learning_hub:
                    self.learning_hub.record_tool_use(
                        tool_name=tool_name,
                        success=True,
                        response_time_ms=tool_time
                    )
                
                # Extract sources if tool provides them
                if isinstance(result, dict):
                    if "sources" in result:
                        context.sources.extend(result["sources"])
                    if "memory_ids" in result:
                        context.memory_ids.extend(result["memory_ids"])
                
            except Exception as e:
                tool_time = int((time.time() - tool_start) * 1000)
                
                context.tools_used.append({
                    "tool": tool_name,
                    "ok": False,
                    "error": str(e)
                })
                context.trace.append({"step": "tool_error", "tool": tool_name, "error": str(e)})
                
                # Learn from failed tool use
                if self.learning_hub:
                    self.learning_hub.record_tool_use(
                        tool_name=tool_name,
                        success=False,
                        response_time_ms=tool_time
                    )
        
        return results
    
    def _build_prompt(
        self,
        question: str,
        tool_results: Dict[str, Any],
        persona: str,
        lang: str,
        retry_hints: Optional[List[str]] = None
    ) -> Tuple[str, str]:
        """
        Build system and user prompts for LLM.
        
        Returns:
            (system_prompt, user_prompt)
        """
        # System prompt with persona
        persona_instructions = {
            "helpful": "Du bist ein hilfreicher Assistent. Antworte präzise und freundlich.",
            "concise": "Du bist ein prägnanter Assistent. Antworte kurz und direkt.",
            "detailed": "Du bist ein ausführlicher Assistent. Gib umfassende Antworten mit Beispielen.",
            "technical": "Du bist ein technischer Experte. Nutze Fachterminologie wenn angebracht.",
        }
        system_prompt = persona_instructions.get(persona, persona_instructions["helpful"])
        
        # Add tool context if available
        if tool_results:
            context_parts = []
            
            if "memory" in tool_results:
                mem = tool_results["memory"]
                if isinstance(mem, dict) and mem.get("hits"):
                    context_parts.append("Relevantes Wissen:")
                    for hit in mem["hits"][:3]:
                        context_parts.append(f"- {hit.get('title', '?')}: {hit.get('content', '')[:200]}")
            
            if "web" in tool_results:
                web = tool_results["web"]
                if isinstance(web, dict) and web.get("answer"):
                    context_parts.append(f"Web-Recherche: {web['answer'][:300]}")
            
            if "calc" in tool_results:
                context_parts.append(f"Berechnung: {tool_results['calc']}")
            
            if context_parts:
                system_prompt += "\n\nVerfügbarer Kontext:\n" + "\n".join(context_parts)
        
        # Add retry hints if this is a retry
        if retry_hints:
            system_prompt += "\n\nVerbesserungshinweise:\n" + "\n".join(f"- {h}" for h in retry_hints)
            system_prompt += "\n\nAdressiere diese Punkte in deiner Antwort."
        
        # User prompt is the question
        user_prompt = question
        
        return system_prompt, user_prompt
    
    def _generate_llm_response(self, prompts: Tuple[str, str], lang: str) -> Optional[str]:
        """
        Generate response using LLM.
        
        Args:
            prompts: (system_prompt, user_prompt)
            lang: Language code
            
        Returns:
            Generated text or None on failure
        """
        system_prompt, user_prompt = prompts
        
        if not self.llm or not hasattr(self.llm, 'available') or not self.llm.available():
            return None
        
        try:
            response = self.llm.chat_once(
                user=user_prompt,
                system=system_prompt
            )
            return response.strip() if response else None
        except Exception as e:
            print(f"LLM generation failed: {e}")
            return None


# === Integration Helpers ===

def create_default_pipeline(llm_backend, tools: Optional[Dict] = None) -> ResponsePipeline:
    """
    Create pipeline with default configuration.
    
    Args:
        llm_backend: LLM instance
        tools: Optional dict of tools
        
    Returns:
        Configured ResponsePipeline
    """
    return ResponsePipeline(
        llm_backend=llm_backend,
        reflector=None,  # Will create default
        tools=tools or {},
        max_retries=2,
        enable_reflection=True,
        quality_threshold=0.7
    )


if __name__ == "__main__":
    # Self-test (requires llm_local)
    print("=== Response Pipeline Self-Test ===\n")
    
    try:
        from netapi.core import llm_local
        
        # Simple tools for testing
        def mock_calc(question: str) -> str:
            import re
            match = re.search(r'(\d+)\s*\+\s*(\d+)', question)
            if match:
                a, b = int(match.group(1)), int(match.group(2))
                return f"{a} + {b} = {a+b}"
            return None
        
        tools = {"calc": mock_calc}
        
        pipeline = create_default_pipeline(llm_local, tools)
        
        # Test 1: Simple math
        print("Test 1: Math question")
        response = pipeline.generate("Was ist 5+3?")
        print(f"Reply: {response.reply}")
        print(f"Quality: {response.evaluation.overall_score if response.evaluation else 'N/A':.2f}")
        print(f"Retries: {response.retry_count}")
        print(f"Time: {response.total_time_ms}ms\n")
        
        # Test 2: General knowledge
        print("Test 2: General question")
        response2 = pipeline.generate("Was ist Python?")
        print(f"Reply: {response2.reply[:200]}...")
        print(f"Quality: {response2.evaluation.overall_score if response2.evaluation else 'N/A':.2f}\n")
        
        print("=== Tests Complete ===")
        
    except Exception as e:
        print(f"Test failed: {e}")
        print("Note: Tests require llm_local to be available")
