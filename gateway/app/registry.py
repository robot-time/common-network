from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app import db, embedder
from app.config import settings
from app.models import NodeCreate, NodeOut

router = APIRouter()


def _require_secret(x_common_secret: str | None) -> None:
    if x_common_secret != settings.registry_secret:
        raise HTTPException(status_code=401, detail="invalid or missing X-Common-Secret")


def _row_to_node_out(row) -> NodeOut:
    return NodeOut(
        id=row["id"],
        name=row["name"],
        operator=row["operator"],
        endpoint_url=row["endpoint_url"],
        model_name=row["model_name"],
        region=row["region"],
        cost_per_1k=float(row["cost_per_1k"]),
        avg_latency_ms=row["avg_latency_ms"],
        healthy=row["healthy"],
        last_heartbeat=row["last_heartbeat"].isoformat() if row["last_heartbeat"] else None,
        capability_text=row["capability_text"],
    )


@router.post("/nodes", response_model=NodeOut)
async def register_node(node: NodeCreate, x_common_secret: str | None = Header(default=None)):
    _require_secret(x_common_secret)
    vec = embedder.embed(node.capability_text)
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into nodes
                (name, operator, endpoint_url, model_name, api_key_ref,
                 capability_text, capability_embed, region, cost_per_1k)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            on conflict (name) do update set
                operator = excluded.operator,
                endpoint_url = excluded.endpoint_url,
                model_name = excluded.model_name,
                api_key_ref = excluded.api_key_ref,
                capability_text = excluded.capability_text,
                capability_embed = excluded.capability_embed,
                region = excluded.region,
                cost_per_1k = excluded.cost_per_1k
            returning *
            """,
            node.name, node.operator, node.endpoint_url, node.model_name, node.api_key_ref,
            node.capability_text, vec, node.region, node.cost_per_1k,
        )
    return _row_to_node_out(row)


@router.get("/nodes", response_model=list[NodeOut])
async def list_nodes():
    async with db.pool().acquire() as conn:
        rows = await conn.fetch("select * from nodes order by created_at desc")
    return [_row_to_node_out(r) for r in rows]


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: UUID, x_common_secret: str | None = Header(default=None)):
    _require_secret(x_common_secret)
    async with db.pool().acquire() as conn:
        result = await conn.execute("delete from nodes where id = $1", node_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="node not found")
    return {"deleted": str(node_id)}
