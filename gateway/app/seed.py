import os
from pathlib import Path

import yaml

from app import db, embedder
from app.config import settings


async def seed_from_file() -> None:
    path = Path(settings.seed_file)
    if not path.exists():
        return

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    for node in data.get("nodes", []):
        vec = embedder.embed(node["capability_text"])
        async with db.pool().acquire() as conn:
            await conn.execute(
                """
                insert into nodes
                    (name, operator, endpoint_url, model_name, api_key_ref,
                     capability_text, capability_embed, region, cost_per_1k)
                values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                on conflict (name) do nothing
                """,
                node["name"], node.get("operator"), node["endpoint_url"], node["model_name"],
                node.get("api_key_ref"), node["capability_text"], vec,
                node.get("region"), node.get("cost_per_1k", 0),
            )
