"""
Helper utilities for generating TODO plans for the Norns deep agent.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional, Union

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.core.config import get_settings


def _extract_text(content: Union[str, list, Any]) -> str:
    """Extract text from content that may be string or multi-modal list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Handle multi-modal content blocks
        texts = []
        for block in content:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif "text" in block:
                    texts.append(str(block["text"]))
        return " ".join(texts)
    return str(content) if content else ""


def _normalize_todos(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        todos = raw
    elif isinstance(raw, dict) and "todos" in raw:
        todos = raw["todos"]
    else:
        return []

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(todos, start=1):
        if isinstance(item, str):
            normalized.append(
                {
                    "id": str(idx),
                    "description": item.strip(),
                    "status": "pending",
                }
            )
            continue
        
        if isinstance(item, list):
            # Handle multi-modal content
            item_text = _extract_text(item)
            normalized.append(
                {
                    "id": str(idx),
                    "description": item_text.strip(),
                    "status": "pending",
                }
            )
            continue

        if isinstance(item, dict):
            desc = item.get("description") or item.get("task") or f"Task {idx}"
            # Handle multi-modal description
            if isinstance(desc, list):
                desc = _extract_text(desc)
            normalized.append(
                {
                    "id": str(item.get("id", idx)),
                    "description": str(desc).strip() if desc else f"Task {idx}",
                    "status": item.get("status", "pending"),
                    "owner": item.get("owner", "Norns"),
                }
            )
    return normalized


def generate_todo_plan(goal: Union[str, list, Any], context: Optional[str] = None) -> list[dict]:
    """
    Ask the model to decompose a user goal into TODO items.

    Returns a list of dictionaries with id/description/status fields.
    
    Args:
        goal: The goal text (can be string or multi-modal list)
        context: Optional additional context
    """
    # Handle multi-modal content
    goal_text = _extract_text(goal)
    context_text = _extract_text(context) if context else ""
    
    settings = get_settings()
    llm = ChatOpenAI(model=settings.NORNS_MODEL, temperature=0.2)
    prompt_context = (
        f"Context:\n{context_text.strip()}\n\n" if context_text and context_text.strip() else ""
    )
    messages = [
        SystemMessage(
            content=(
                "You are Skuld, the Norn who plans what shall be. Break goals into"
                " precise TODO items with owners, dependencies, and measurable outputs."
                " Respond with JSON: {\"todos\": [{\"id\": \"T1\", \"description\":"
                " \"...\", \"status\": \"pending\", \"owner\": \"role\"}, ...]}"
            )
        ),
        HumanMessage(content=f"{prompt_context}Goal:\n{goal_text.strip()}"),
    ]
    response = llm.invoke(messages)
    
    # Handle response content that might also be multi-modal
    response_text = _extract_text(response.content)
    try:
        payload = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        payload = {"todos": [response_text.strip()]}

    todos = _normalize_todos(payload)
    if not todos:
        todos = [
            {
                "id": "1",
                "description": goal_text.strip()[:120],
                "status": "pending",
                "owner": "Norns",
            }
        ]
    return todos


