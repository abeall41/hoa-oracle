"""
CLI query tester — invokes the orchestrator directly against a running DB.

Usage:
  python scripts/test_query.py --query "Can I park a commercial vehicle in my driveway?" \
      --community-id 3 --source homeowner
"""
import argparse
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def run_query(query: str, community_id: int, source: str) -> None:
    from app.orchestrator.router import route_query

    print(f"\nQuery ({source}): {query}")
    print(f"Community ID: {community_id}")
    print("-" * 60)

    result = await route_query(
        query=query,
        query_source=source,
        community_tier_id=community_id,
        session_id="cli-test",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test a query through the HOA Oracle orchestrator")
    parser.add_argument("--query", required=True, help="Natural language query")
    parser.add_argument("--community-id", type=int, required=True, help="knowledge_tiers.id for the community")
    parser.add_argument("--source", choices=["board", "homeowner"], default="homeowner")
    args = parser.parse_args()
    asyncio.run(run_query(args.query, args.community_id, args.source))
