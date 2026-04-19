import asyncio
import uuid
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.tools.google_calendar import get_calendar_events
from app.services.token_service import get_valid_token
from app.core.database import SessionLocal
import json

async def main():
    user_id = "db3ed829-d6f4-479b-9345-1e19e598c49e"
    async with SessionLocal() as db:
        token = await get_valid_token(db, uuid.UUID(user_id), "google")
        if not token:
            print("No token found")
            return
        
        # List events for today (2026-04-17)
        res = await get_calendar_events(
            access_token=token,
            time_min="2026-04-17T00:00:00Z",
            time_max="2026-04-17T23:59:59Z"
        )
        print("--- EVENTS TODAY ---")
        print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
