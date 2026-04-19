import asyncio
import httpx
import base64
from app.core.config import settings

async def main():
    encoded = base64.b64encode(f"{settings.zoom_client_id}:{settings.zoom_client_secret}".encode()).decode()
    
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={settings.zoom_account_id}"
    
    print(f"URL: {url}")
    print(f"Auth: Basic {encoded}")
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )
        print("Status Code:", resp.status_code)
        print("Response Text:", resp.text)

if __name__ == "__main__":
    asyncio.run(main())
