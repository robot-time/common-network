from dataclasses import dataclass

import numpy as np

from app.config import settings


@dataclass
class ScoredNode:
    node: dict
    score: float
    sim: float
    cost_term: float
    lat_term: float
    region_term: float


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def score_nodes(
    nodes: list[dict],
    request_embed: list[float],
    region_hint: str | None = None,
) -> list[ScoredNode]:
    """Score every candidate node against a request embedding.

    Returns nodes sorted best-first. Kept as plain arithmetic (no learned
    weights) so a human can read `sim`/`cost_term`/`lat_term` off a ScoredNode
    and see exactly why a node won — see Master Build Prompt "Routing
    algorithm" for the rationale.
    """
    if not nodes:
        return []

    max_cost = max((float(n["cost_per_1k"]) for n in nodes), default=0.0)
    max_lat = max((float(n["avg_latency_ms"]) for n in nodes), default=0.0)

    scored: list[ScoredNode] = []
    for n in nodes:
        sim = _cosine(request_embed, n["capability_embed"])

        norm_cost = (float(n["cost_per_1k"]) / max_cost) if max_cost > 0 else 0.0
        cost_term = settings.w_cost * (1 - norm_cost)

        norm_lat = (float(n["avg_latency_ms"]) / max_lat) if max_lat > 0 else 0.0
        lat_term = settings.w_lat * (1 - norm_lat)

        region_term = 0.0
        if region_hint and n.get("region") == region_hint:
            region_term = settings.region_bonus

        score = settings.w_sim * sim + cost_term + lat_term + region_term
        scored.append(ScoredNode(
            node=n, score=score, sim=sim, cost_term=cost_term,
            lat_term=lat_term, region_term=region_term,
        ))

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
