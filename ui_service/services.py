import hashlib
import json

from core import redis_client
from models import CaptureAgent

def generate_etag(data: dict) -> str:
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12]

async def fetch_agents():
    """Get all capture agent details from Redis as a list of dicts."""
    agent_names = await redis_client.smembers("ca:index")
    agents = []

    for name in agent_names:
        agent_hash = await redis_client.hgetall(f"ca:{name}")
        if not agent_hash:
            continue

        agents.append(CaptureAgent(
                name=name,
                display=agent_hash.get("display", ""),
                state=agent_hash.get("state", ""),
                time_since_last_update=int(agent_hash.get("time_since_last_update", 0)),
                last_updated=agent_hash.get("last_updated")
            ))

    return agents
