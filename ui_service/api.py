from fastapi import APIRouter, HTTPException, Response

from utils.settings import logger
from core import redis_client
from services import (generate_etag, fetch_agents)

router = APIRouter()

# Agents ----------------------------------------------------
@router.get("/api/agents")
async def get_capture_agent_details(response: Response):
    try:
        agents = await fetch_agents()

        payload = [c.model_dump() for c in agents]

        etag = generate_etag(payload)
        response.headers["ETag"] = f'"{etag}"'
        response.headers["Cache-Control"] = "no-cache, must-revalidate"

        last_check = await redis_client.get("ca:last_refresh") or "never"
        return {
            "status": "success",
            "agents": payload,
            "total": len(payload),
            "last_refresh": last_check,
            "version": etag
        }

    except Exception as e:
        logger.exception("Failed to get capture agents")
        raise HTTPException(status_code=500, detail=str(e))
