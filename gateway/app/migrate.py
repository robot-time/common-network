"""Apply migrations/*.sql in order. Idempotent — safe to re-run.

Usage: python -m app.migrate
"""
import asyncio
from pathlib import Path

import asyncpg

from app.config import settings

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


async def main() -> None:
    conn = await asyncpg.connect(dsn=settings.database_url)
    try:
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            print(f"applying {path.name}")
            await conn.execute(path.read_text())
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
