from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# --- Registry ---

class NodeCreate(BaseModel):
    name: str
    operator: str | None = None
    endpoint_url: str
    model_name: str
    api_key_ref: str | None = None
    capability_text: str
    region: str | None = None
    cost_per_1k: float = 0
    domain_tags: list[str] | None = None
    catalogue_id: str | None = None


class NodeOut(BaseModel):
    id: UUID
    name: str
    operator: str | None
    endpoint_url: str
    model_name: str
    region: str | None
    cost_per_1k: float
    avg_latency_ms: int
    healthy: bool
    last_heartbeat: str | None
    capability_text: str
    domain_tags: list[str] | None = None
    catalogue_id: str | None = None


# --- Decisions ---

class DecisionOut(BaseModel):
    id: UUID
    chosen_node: UUID | None
    chosen_node_name: str | None
    score: float | None
    runner_up: UUID | None
    latency_ms: int | None
    ok: bool | None
    created_at: str
    matched_domain: str | None = None


# --- OpenAI-compatible passthrough ---
# Deliberately untyped/loose (dict passthrough) — v0.1 forwards whatever the
# client sends and returns whatever the node returns, unchanged except for
# our transparency headers. Do not model the full OpenAI schema here.

ChatCompletionRequest = dict[str, Any]
