"""Carga idempotente de seeds/academic_programs.json (ADR-06).

Uso: python -m seeds.load_academic_programs
"""
import asyncio
import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import get_settings
from app.core.db import create_engine
from app.modules.auth.models import AcademicProgram

SEED_FILE = Path(__file__).with_name("academic_programs.json")


def read_programs(path: Path = SEED_FILE) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [{"code": p["code"], "name": p["name"]} for p in data["programs"]]


async def load_programs(connection: AsyncConnection, programs: list[dict[str, str]]) -> int:
    stmt = insert(AcademicProgram).values(programs)
    stmt = stmt.on_conflict_do_update(index_elements=[AcademicProgram.code], set_={"name": stmt.excluded.name})
    await connection.execute(stmt)
    return len(programs)


async def main() -> None:
    engine = create_engine(get_settings().DATABASE_URL_DIRECT)
    async with engine.begin() as connection:
        count = await load_programs(connection, read_programs())
    await engine.dispose()
    print(f"academic_programs: {count} programas cargados/actualizados")


if __name__ == "__main__":
    asyncio.run(main())
