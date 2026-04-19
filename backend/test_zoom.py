import asyncio
import httpx
import base64
from app.core.config import settings

async def main():
    auth_str = f"{settings.zoom_client_id}:{settings.zoom_client_secret}"
    encoded = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Try POST with data
    print("Test 1: data dict")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://zoom.us/oauth/token", 
            headers=headers, 
            data={"grant_type": "account_credentials", "account_id": settings.zoom_account_id}
        )
        print(resp.status_code, resp.text)
        
    # Try POST with query string directly in URL, no data
    print("Test 2: query string")
    async with httpx.AsyncClient() as client:
        # Note: not sending content-type here
        resp = await client.post(
            f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={settings.zoom_account_id}", 
            headers={"Authorization": f"Basic {encoded}"}
        )
        print(resp.status_code, resp.text)

if __name__ == "__main__":
    asyncio.run(main())
