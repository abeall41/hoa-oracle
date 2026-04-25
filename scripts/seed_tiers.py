"""
Seed the three required knowledge tiers: Maryland (state), Montgomery County (county),
and Crest of Wickford HOA (community).

Usage: python scripts/seed_tiers.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.tier import KnowledgeTier

TIERS = [
    {"tier": "state",     "name": "Maryland",               "slug": "maryland",           "parent_slug": None},
    {"tier": "county",    "name": "Montgomery County",       "slug": "montgomery-county",  "parent_slug": "maryland"},
    {"tier": "community", "name": "Crest of Wickford HOA",   "slug": "wickford",           "parent_slug": "montgomery-county"},
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        slug_to_id: dict[str, int] = {}

        for tier_data in TIERS:
            existing = await db.execute(
                select(KnowledgeTier).where(KnowledgeTier.slug == tier_data["slug"])
            )
            row = existing.scalar_one_or_none()

            if row:
                print(f"  [skip] {tier_data['name']} already exists (id={row.id})")
                slug_to_id[tier_data["slug"]] = row.id
                continue

            parent_id = slug_to_id.get(tier_data["parent_slug"]) if tier_data["parent_slug"] else None
            tier = KnowledgeTier(
                tier=tier_data["tier"],
                name=tier_data["name"],
                slug=tier_data["slug"],
                parent_id=parent_id,
            )
            db.add(tier)
            await db.flush()
            slug_to_id[tier_data["slug"]] = tier.id
            print(f"  [created] {tier_data['name']} (id={tier.id})")

        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
