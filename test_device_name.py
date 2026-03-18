import asyncio
import httpx
import os
import uuid
import json

def load_env_manual():
    env_path = 'c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/.env'
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    try:
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
                    except ValueError:
                        pass

load_env_manual()

async def debug_create():
    api_url = os.environ.get("EVOLUTION_API_URL")
    api_key = os.environ.get("EVOLUTION_API_KEY")
    instance_name = "test_custom_browser"
    
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json",
    }
    url = f"{api_url}/instance/create"
    # Attempting to set browser or clientName
    payload = {
        "instanceName": instance_name,
        "token": "debugtoken_" + str(uuid.uuid4())[:8],
        "qrcode": True,
        "integration": "WHATSAPP-BAILEYS",
        "browser": ["SalesAgent", "Chrome", "1.0.0"],
        "clientName": "SalesAgentInstance"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(url, json=payload, headers=headers)
        print(f"Create status: {res.status_code}")
        print(f"Create body: {res.text}")

if __name__ == "__main__":
    asyncio.run(debug_create())
