import os

import psycopg

DATABASE_URL = os.getenv("DATABASE_INTERNAL_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not provided")


async def init_db():
    conn = await psycopg.AsyncConnection.connect(DATABASE_URL)
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                create table if not exists subscribers (
                    user_id bigint primary key,
                    active boolean not null default true,
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            await conn.commit()
    finally:
        await conn.close()


async def add_or_activate_user(user_id: int):
    conn = await psycopg.AsyncConnection.connect(DATABASE_URL)
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                insert into subscribers (user_id, active)
                values (%s, true)
                on conflict (user_id)
                do update set active=true, updated_at=now()
                """,
                (user_id,),
            )
            await conn.commit()
    finally:
        await conn.close()


async def deactivate_user(user_id: int):
    conn = await psycopg.AsyncConnection.connect(DATABASE_URL)
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "update subscribers set active=false, updated_at=now() where user_id=%s",
                (user_id,),
            )
            await conn.commit()
    finally:
        await conn.close()


async def fetch_active_users() -> set[int]:
    conn = await psycopg.AsyncConnection.connect(DATABASE_URL)
    try:
        async with conn.cursor() as cur:
            await cur.execute("select user_id from subscribers where active=true")
            rows = await cur.fetchall()
            return {int(r[0]) for r in rows}
    finally:
        await conn.close()
