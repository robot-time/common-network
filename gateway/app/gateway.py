import os
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app import db, embedder
from app.config import settings
from app.router import ScoredNode, score_nodes

router = APIRouter()


def _extract_routing_text(body: dict[str, Any]) -> str:
    messages = body.get("messages") or []
    user_turns = [m.get("content", "") for m in messages if m.get("role") == "user"]
    text = "\n".join(str(t) for t in user_turns if t)
    return text or str(body)


async def _fetch_healthy_nodes() -> list[dict]:
    async with db.pool().acquire() as conn:
        rows = await conn.fetch("select * from nodes where healthy = true")
    return [dict(r) for r in rows]


def _auth_headers(node: dict) -> dict:
    headers = {"Content-Type": "application/json"}
    api_key_ref = node.get("api_key_ref")
    if api_key_ref:
        key = os.environ.get(api_key_ref)
        if key:
            headers["Authorization"] = f"Bearer {key}"
    return headers


async def _record_decision(
    request_embed: list[float],
    chosen: ScoredNode | None,
    runner_up: ScoredNode | None,
    latency_ms: int,
    ok: bool,
) -> None:
    async with db.pool().acquire() as conn:
        await conn.execute(
            """
            insert into decisions
                (request_embed, chosen_node, score, runner_up, latency_ms, ok)
            values ($1, $2, $3, $4, $5, $6)
            """,
            request_embed,
            chosen.node["id"] if chosen else None,
            chosen.score if chosen else None,
            runner_up.node["id"] if runner_up else None,
            latency_ms,
            ok,
        )


async def _update_latency(node_id, latency_ms: int) -> None:
    # Simple rolling average (equal weight to history and this sample).
    async with db.pool().acquire() as conn:
        await conn.execute(
            """
            update nodes
            set avg_latency_ms = case
                when avg_latency_ms = 0 then $2
                else (avg_latency_ms + $2) / 2
            end
            where id = $1
            """,
            node_id, latency_ms,
        )


async def _forward(node: dict, body: dict[str, Any], stream: bool) -> httpx.Response:
    outgoing = dict(body)
    outgoing["model"] = node["model_name"]
    url = node["endpoint_url"].rstrip("/") + "/chat/completions"
    client = httpx.AsyncClient(timeout=settings.forward_timeout_seconds)
    req = client.build_request("POST", url, json=outgoing, headers=_auth_headers(node))
    resp = await client.send(req, stream=stream)
    resp.extensions["_client"] = client
    return resp


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    stream = bool(body.get("stream", False))

    nodes = await _fetch_healthy_nodes()
    if not nodes:
        raise HTTPException(status_code=503, detail="no healthy nodes available")

    routing_text = _extract_routing_text(body)
    request_embed = embedder.embed(routing_text)
    region_hint = request.headers.get("X-Common-Region")
    forced_node_name = request.headers.get("X-Common-Node")

    if forced_node_name:
        matches = [n for n in nodes if n["name"] == forced_node_name]
        if not matches:
            raise HTTPException(status_code=404, detail=f"node '{forced_node_name}' not found or not currently healthy")
        # No fallback candidate -- if you asked for this node specifically,
        # a failure should surface as a failure, not silently reroute.
        candidates = [ScoredNode(node=matches[0], score=1.0, sim=0.0, cost_term=0.0, lat_term=0.0, region_term=0.0)]
    else:
        scored = score_nodes(nodes, request_embed, region_hint)
        primary, backup = scored[0], (scored[1] if len(scored) > 1 else None)
        candidates = [primary] + ([backup] if backup else [])

    last_error: Exception | None = None

    for attempt, candidate in enumerate(candidates):
        start = time.monotonic()
        try:
            resp = await _forward(candidate.node, body, stream)
            latency_ms = int((time.monotonic() - start) * 1000)
            if resp.status_code >= 500:
                raise httpx.HTTPStatusError("upstream error", request=resp.request, response=resp)

            await _update_latency(candidate.node["id"], latency_ms)
            runner_up = next((c for i, c in enumerate(candidates) if i != attempt), None)
            await _record_decision(request_embed, candidate, runner_up, latency_ms, True)

            headers = {
                "X-Common-Node": candidate.node["name"],
                "X-Common-Score": "forced" if forced_node_name else f"{candidate.score:.4f}",
            }

            if stream:
                async def body_iter():
                    client = resp.extensions["_client"]
                    try:
                        async for chunk in resp.aiter_raw():
                            yield chunk
                    finally:
                        await resp.aclose()
                        await client.aclose()

                return StreamingResponse(
                    body_iter(),
                    status_code=resp.status_code,
                    media_type=resp.headers.get("content-type", "text/event-stream"),
                    headers=headers,
                )

            content = await resp.aread()
            await resp.aclose()
            await resp.extensions["_client"].aclose()
            return Response(
                content=content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "application/json"),
                headers=headers,
            )
        except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
            last_error = exc
            latency_ms = int((time.monotonic() - start) * 1000)
            if attempt == len(candidates) - 1:
                await _record_decision(request_embed, None, None, latency_ms, False)

    raise HTTPException(status_code=502, detail=f"all candidate nodes failed: {last_error}")


@router.get("/v1/models")
async def list_models():
    nodes = await _fetch_healthy_nodes()
    seen = {}
    for n in nodes:
        seen[n["model_name"]] = n
    data = [
        {"id": model_name, "object": "model", "owned_by": n.get("operator") or "common-network"}
        for model_name, n in seen.items()
    ]
    return JSONResponse({"object": "list", "data": data})
