import asyncio
import httpx
from app.core.config import settings

async def main():
    url = f"https://zoom.us/oauth/token"
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            auth=(settings.zoom_client_id, settings.zoom_client_secret),
            data={
                "grant_type": "account_credentials",
                "account_id": settings.zoom_account_id,
            }
        )
        print("Status Code:", resp.status_code)
        print("Response Text:", resp.text)

if __name__ == "__main__":
    asyncio.run(main())
