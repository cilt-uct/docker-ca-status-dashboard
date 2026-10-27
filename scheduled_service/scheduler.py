import asyncio
import os
import time
import redis.asyncio as redis

from dateutil.parser import parse as parse_dt
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler

from utils.settings import FetchSettings, logger

from opencast.opencast import CaptureAgent

settings = FetchSettings()
settings.TITLE = "Fetch Capture Agent Status Service"

# Utility Functions
# -----------------------------------------------
def str_to_dt_or_none(s: str):
    if not s:
        return None
    try:
        return parse_dt(s)
    except Exception:
        # if parsing of datetime fails, return None
        return None

def get_redis(settings):
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD, #This line references a path for secret loading, but does not embed a secret.
        decode_responses=True
    )

def normalize_agent_status(status: str) -> str:
    if not status:
        return "unknown"
    return status.split(".")[-1].lower()

def format_datetime_for_redis(dt_value):
    """Convert datetime to string format suitable for Redis storage"""
    if dt_value is None:
        return None

    if isinstance(dt_value, datetime):
        # Make it timezone-aware if it isn't already
        if dt_value.tzinfo is None:
            # Use the system's local timezone
            dt_value = dt_value.astimezone()

        return dt_value.isoformat(timespec='seconds')

    if isinstance(dt_value, str):
        # Handle UTC format with Z
        if dt_value.endswith('Z'):
            try:
                utc_time = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
                local_time = utc_time.astimezone()
                return local_time.isoformat(timespec='seconds')
            except ValueError:
                pass
        return dt_value

    return str(dt_value)

# Opencast
# -----------------------------------------------
async def update_capture_agent_details(settings):
    """
    Load Opencast Capture Agents into Redis
    """
    rc = get_redis(settings)
    await rc.set("ca:last_refresh", datetime.now().astimezone().isoformat(timespec='seconds'))

    ca_names = settings.OC.get_ca_names().json()
    await rc.hset("ca:display", mapping=ca_names)

    response = settings.OC.get_capture_agent_capabilities().json()
    if "agents" not in response:
        logger.error("No Capture Agents in response")
        return

    await rc.delete("ca:index")
    updated_count = 0
    for data in response['agents']['agent']:
        ca = CaptureAgent(data)
        if ca.name not in ca_names:
            continue

        # ca:index -> set of capture agent names
        await rc.sadd("ca:index", ca.name)

        # ca:{name} -> hash of capture agent details
        await rc.hset(f"ca:{ca.name}", mapping=ca.get_dict(display=ca_names[ca.name]))
        updated_count += 1

    logger.info(f"Updated details for {updated_count} CA's")


async def update_capture_agent_state(settings):
    """
    Get the capture agents current state and update that details
    """
    rc = get_redis(settings)
    await rc.set("ca:last_refresh", datetime.now().astimezone().isoformat(timespec='seconds'))

    ca_names = settings.OC.get_ca_names().json()
    await rc.hset("ca:display", mapping=ca_names)

    response = settings.OC.get_capture_agent_status().json()
    if "results" not in response:
        logger.error("No Capture Agents in response")
        return

    await rc.delete("ca:index")
    updated_count = 0
    async with rc.pipeline() as pipe:
        for ca in response['results']:
            if ca['Name'] not in ca_names:
                continue

            update_value = ca.get('Update')
            if update_value is None:
                update_value = datetime.now().astimezone()

            pipe.sadd("ca:index", ca['Name'])
            pipe.hset(f"ca:{ca['Name']}", mapping={
                "display": ca_names[ca['Name']],
                "state": normalize_agent_status(ca['Status']),
                "last_updated": format_datetime_for_redis(update_value)
            })
            updated_count += 1
        await pipe.execute()

    logger.info(f"Updated states for {updated_count} CA's")

# -----------------------------------------------
# Cleanup
# -----------------------------------------------

async def clear_redis_on_startup(settings):
    rc = get_redis(settings)

    # Clear the current database only
    await rc.flushdb()

    logger.info("Redis cleared on startup")

# Scheduler entry
# --------------------------
def update_capture_agent_details_sync():
    asyncio.run(update_capture_agent_details(settings))

def update_capture_agent_state_sync():
    asyncio.run(update_capture_agent_state(settings))

async def startup():
    if settings.REDIS_CLEAN_START:
        await clear_redis_on_startup(settings) # start fresh

    await update_capture_agent_details(settings)
    await update_capture_agent_state(settings)

    logger.info("Startup load complete: capture agents synced to Redis.")

if __name__ == "__main__":
    asyncio.run(startup())

    scheduler = BackgroundScheduler()

    # Opencast - Get Capture Agent Status
    scheduler.add_job(update_capture_agent_details_sync, 'interval', hours=1, next_run_time=datetime.now() + timedelta(seconds=30))
    scheduler.add_job(update_capture_agent_state_sync, 'interval', minutes=5, next_run_time=datetime.now() + timedelta(seconds=40))

    scheduler.start()

    rc = get_redis(settings)
    start_time = datetime.now().astimezone().isoformat(timespec='seconds')
    asyncio.run(rc.set('scheduler_service_start', start_time))
    logger.info(f"Scheduler started at {start_time}")

    try:
        while True:
            time.sleep(1)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        asyncio.run(rc.close())
