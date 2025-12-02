from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Literal
from pathlib import Path

from ...core.orchestrator import build_orchestrator
from ...core.schema import ModerationResponse, Reason
from ...models.providers import get_provider
from ...core.logger import api_logger, system_logger
import time


router = APIRouter()
orc = build_orchestrator(
    model_name="qw3_guard",
    rules_files=[
        Path(__file__).resolve().parent.parent.parent / "rules" / "chat_whitelist.yml",
        Path(__file__).resolve().parent.parent.parent / "rules" / "chat_blacklist.yml",
    ],
    api_path="/v1/chat-guard",
)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatGuardRequest(BaseModel):
    messages: List[ChatMessage]
    model: str | None = None  # Optional, for OpenAI compatibility


def _messages_to_text(messages: List[Dict[str, str]]) -> str:
    """Convert messages list to text format for rule checking."""
    text_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        text_parts.append(f"{role}: {content}")
    return "\n".join(text_parts)


@router.post("/v1/chat-guard")
async def chat_guard(req: ChatGuardRequest):
    """
    Moderate LLM generated answers with user prompt using qw3-guard.
    
    Uses rule engine with higher priority, then qw3-guard model for moderation.
    Accepts messages in OpenAI chat completions format and returns moderation result.
    """
    start_time = time.time()
    
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")
    
    # Convert Pydantic models to dict format
    messages_dict = [{"role": msg.role, "content": msg.content} for msg in req.messages]
    
    # Convert messages to text for rule checking
    text_for_rules = _messages_to_text(messages_dict)
    
    # Check rules first using orchestrator's rule engine (rules have higher priority)
    rule_start = time.time()
    rule = orc.rule_engine.evaluate(text_for_rules)
    rule_time = time.time() - rule_start
    
    reasons: List[Reason] = []
    
    # If rule matched, return early with rule decision
    if rule:
        reasons.append(Reason(engine="rule", id=rule.id))
        resp = ModerationResponse(
            safe=rule.action == "ALLOW",
            decision=rule.action,
            reasons=reasons,
            policy_version="v1",
        )
        total_time = time.time() - start_time
        timings = {'total': total_time, 'rule_engine': rule_time}
        system_logger.info(f"Chat guard moderation timings: {timings}")
        
        messages_preview = str(messages_dict)[:200] + "..." if len(str(messages_dict)) > 200 else str(messages_dict)
        api_logger.info(f"/v1/chat-guard request: {messages_preview}")
        api_logger.info(f"/v1/chat-guard response: {resp}")
        
        return resp
    
    # Rules didn't match, use qw3-guard with messages
    qw3_provider = get_provider("qw3_guard")
    
    # Use moderate_messages if available (preferred for chat context)
    if hasattr(qw3_provider, "moderate_messages"):
        qw3_start = time.time()
        score, label = await qw3_provider.moderate_messages(messages_dict)
        qw3_time = time.time() - qw3_start
    else:
        # Fallback: combine messages into text
        qw3_start = time.time()
        score, label = await qw3_provider.moderate(text_for_rules)
        qw3_time = time.time() - qw3_start
    
    # Build reasons (add qw3-guard result)
    reasons.append(Reason(engine="qw3_guard", category=label, score=score))
    
    # Determine safety based on score
    safe = score < 0.5
    decision = "ALLOW" if safe else "BLOCK"
    
    # Build response
    resp = ModerationResponse(
        safe=safe,
        decision=decision,
        reasons=reasons,
        model_version="qw3_guard",
    )
    
    total_time = time.time() - start_time
    timings = {'total': total_time, 'rule_engine': rule_time, 'qw3_guard': qw3_time}
    system_logger.info(f"Chat guard moderation timings: {timings}")
    
    # Log request and response
    messages_preview = str(messages_dict)[:200] + "..." if len(str(messages_dict)) > 200 else str(messages_dict)
    api_logger.info(f"/v1/chat-guard request: {messages_preview}")
    api_logger.info(f"/v1/chat-guard response: {resp}")
    
    return resp

