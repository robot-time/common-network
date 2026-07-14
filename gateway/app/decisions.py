from fastapi import APIRouter, Query

from app import db
from app.models import DecisionOut

router = APIRouter()


@router.get("/decisions/recent", response_model=list[DecisionOut])
async def recent_decisions(limit: int = Query(default=50, le=500)):
    async with db.pool().acquire() as conn:
        rows = await conn.fetch(
            """
            select d.id, d.chosen_node, n.name as chosen_node_name,
                   d.score, d.runner_up, d.latency_ms, d.ok, d.created_at
            from decisions d
            left join nodes n on n.id = d.chosen_node
            order by d.created_at desc
            limit $1
            """,
            limit,
        )
    return [
        DecisionOut(
            id=r["id"],
            chosen_node=r["chosen_node"],
            chosen_node_name=r["chosen_node_name"],
            score=float(r["score"]) if r["score"] is not None else None,
            runner_up=r["runner_up"],
            latency_ms=r["latency_ms"],
            ok=r["ok"],
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ]
