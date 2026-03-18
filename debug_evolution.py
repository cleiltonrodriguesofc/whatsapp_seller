import asyncio
import httpx
import os
import uuid
import sys

# Manually load .env since we don't know if python-dotenv is there
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

# Add current dir to sys.path
sys.path.append(os.getcwd())

from core.infrastructure.notifications.evolution_whatsapp import EvolutionWhatsAppService

async def debug_qr():
    # Force use environment variables manually in case the class doesn't pick them up
    api_url = os.environ.get("EVOLUTION_API_URL")
    api_key = os.environ.get("EVOLUTION_API_KEY")
    
    print(f"ENV URL: {api_url}")
    print(f"ENV KEY: {api_key[:10]}...")
    
    service = EvolutionWhatsAppService(instance="debug_" + str(uuid.uuid4())[:8])
    # Override if necessary
    if api_url: service.base_url = api_url
    if api_key: service.api_key = api_key
    
    print(f"Testing instance: {service.instance}")
    print(f"Base URL: {service.base_url}")
    
    headers = service._headers()
    url = f"{service.base_url}/instance/connect/{service.instance}?base64=true"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"1. Attempting connection...")
        try:
            res = await client.get(url, headers=headers)
            print(f"Status: {res.status_code}")
            print(f"Response: {res.text[:1000]}")
            
            if res.status_code == 404:
                print("2. Instance not found, creating...")
                create_url = f"{service.base_url}/instance/create"
                payload = {
                    "instanceName": service.instance,
                    "token": "debugtoken_" + str(uuid.uuid4())[:8],
                    "qrcode": True,
                    "integration": "WHATSAPP-BAILEYS",
                }
                res_create = await client.post(create_url, json=payload, headers=headers)
                print(f"Create Status: {res_create.status_code}")
                # Evolution API often returns the QR in the create response!
                print(f"Create Response: {res_create.text[:1000]}")
                
                # Retry connect
                print("3. Retrying connection...")
                res = await client.get(url, headers=headers)
                print(f"Retry Status: {res.status_code}")
                print(f"Retry Response: {res.text[:1000]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_qr())
