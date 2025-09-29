#!/usr/bin/env python3
from __future__ import annotations
import json, os, time
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path.home() / "ki_ana"
PROMPT_DIR = BASE_DIR / "memory" / "model"
PROMPT_PATH = PROMPT_DIR / "active_prompt.txt"
BLOCKS_DIR = BASE_DIR / "memory" / "long_term" / "blocks"

try:
    from system.thought_logger import log_decision  # type: ignore
except Exception:
    def log_decision(**kwargs):  # noqa: N802
        pass


def _gather_corpus(topic: Optional[str] = None, limit: int = 200) -> str:
    texts = []
    if not BLOCKS_DIR.exists():
        return ""
    for p in sorted(BLOCKS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            t = (obj.get("topic") or obj.get("title") or "").strip()
            if topic and topic.lower() not in t.lower():
                continue
            txt = (obj.get("title","") + "\n" + obj.get("content",""))
            if txt.strip():
                texts.append(txt.strip())
        except Exception:
            continue
    return "\n\n".join(texts)


def _write_prompt(text: str) -> None:
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    PROMPT_PATH.write_text(text, encoding="utf-8")


def update_model(mode: str = "prompt", topic: Optional[str] = None) -> Dict[str, Any]:
    """Autopilot model update hook.
    Modes:
      - "prompt": regenerate specialization prompt from current memory blocks
      - "embeddings": rebuild embeddings index for retrieval
      - "lora": placeholder hook for LoRA fine-tuning pipelines
    """
    mode = (mode or "prompt").lower()
    try:
        if mode == "embeddings":
            # Rebuild semantic index to reflect new memory
            try:
                from netapi import memory_store as _mem
                ok = _mem.build_embeddings_index()
            except Exception:
                ok = False
            log_decision(component="autopilot", action="update_model", outcome="embeddings",
                         reasons=["rebuild embeddings index"], meta={"ok": ok})
            return {"ok": bool(ok), "mode": mode}

        if mode == "prompt":
            corpus = _gather_corpus(topic=topic)
            if not corpus:
                _write_prompt("KI_ana: Keine Daten – Standardverhalten beibehalten.")
            else:
                header = (
                    "Rolle: KI_ana – empathisch, transparent, verantwortungsvoll.\n"
                    "Prinzipien: Transparenz, Quellen, Unsicherheiten benennen, nicht-dogmatisch.\n"
                    "Stil: knapp, präzise, nachvollziehbar.\n"
                    "Reflexion: Markiere veraltete/widersprüchliche/nicht belegte Aussagen in meta.reflection.\n"
                    "Ethik-Fragen: Welche Konsequenzen hätte es, wenn ich diese Information falsch weitergebe?\n"
                    "Ethik-Fragen: Was kann ich tun, um dem Menschen zu helfen, statt nur zu antworten?\n"
                    "Korpus (Auszüge):\n\n"
                )
                _write_prompt(header + corpus)
            log_decision(component="autopilot", action="update_model", outcome="prompt",
                         reasons=["refresh specialization prompt"], meta={"topic": topic or "*"})
            return {"ok": True, "mode": mode, "prompt_path": str(PROMPT_PATH)}

        if mode == "lora":
            # Placeholder: integrate with an external LoRA pipeline
            log_decision(component="autopilot", action="update_model", outcome="lora_placeholder",
                         reasons=["no pipeline configured"], meta={})
            return {"ok": False, "mode": mode, "reason": "no lora pipeline configured"}

        return {"ok": False, "mode": mode, "error": "unknown mode"}
    except Exception as e:
        log_decision(component="autopilot", action="update_model", outcome="error",
                     reasons=[str(e)], meta={"mode": mode})
        return {"ok": False, "mode": mode, "error": str(e)}
