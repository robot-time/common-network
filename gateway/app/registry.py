import secrets
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException

from app import db, embedder
from app.models import NodeCreate, NodeOut, NodeRegisterOut

router = APIRouter()


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
        domain_tags=row["domain_tags"],
        catalogue_id=row["catalogue_id"],
    )


@router.post("/nodes", response_model=NodeRegisterOut)
async def register_node(node: NodeCreate):
    # Permissionless by design -- see README "Scope": anyone can contribute a
    # node, no shared password. The one credential issued here is scoped to
    # *this* node only (below), so joining is frictionless but a node can
    # still only be deregistered by whoever holds its own token.
    vec = embedder.embed(node.capability_text)
    new_token = secrets.token_urlsafe(24)
    async with db.pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into nodes
                (name, operator, endpoint_url, model_name, api_key_ref,
                 capability_text, capability_embed, region, cost_per_1k,
                 domain_tags, catalogue_id, node_token)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            on conflict (name) do update set
                operator = excluded.operator,
                endpoint_url = excluded.endpoint_url,
                model_name = excluded.model_name,
                api_key_ref = excluded.api_key_ref,
                capability_text = excluded.capability_text,
                capability_embed = excluded.capability_embed,
                region = excluded.region,
                cost_per_1k = excluded.cost_per_1k,
                domain_tags = excluded.domain_tags,
                catalogue_id = excluded.catalogue_id
            returning *
            """,
            node.name, node.operator, node.endpoint_url, node.model_name, node.api_key_ref,
            node.capability_text, vec, node.region, node.cost_per_1k,
            node.domain_tags, node.catalogue_id, new_token,
        )
    out = _row_to_node_out(row)
    # A re-registration (same name, e.g. after a tunnel restart) keeps the
    # row's original token rather than the fresh one generated above.
    return NodeRegisterOut(**out.model_dump(), node_token=row["node_token"])


@router.get("/nodes", response_model=list[NodeOut])
async def list_nodes():
    async with db.pool().acquire() as conn:
        rows = await conn.fetch("select * from nodes order by created_at desc")
    return [_row_to_node_out(r) for r in rows]


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: UUID, x_common_node_token: str | None = Header(default=None)):
    async with db.pool().acquire() as conn:
        result = await conn.execute(
            "delete from nodes where id = $1 and node_token = $2", node_id, x_common_node_token,
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="node not found, or X-Common-Node-Token doesn't match")
    return {"deleted": str(node_id)}
