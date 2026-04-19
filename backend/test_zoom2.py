import base64
from app.core.config import settings

def test():
    raw = f"{settings.zoom_client_id}:{settings.zoom_client_secret}"
    encoded = base64.b64encode(raw.encode()).decode()
    
    print("--- DEBUG INFO ---")
    print(f"ACCOUNT_ID: '{settings.zoom_account_id}'")
    print(f"CLIENT_ID: '{settings.zoom_client_id}'")
    print(f"CLIENT_SECRET: '{settings.zoom_client_secret}'")
    print(f"ENCODED_AUTH: '{encoded}'")

if __name__ == "__main__":
    test()
