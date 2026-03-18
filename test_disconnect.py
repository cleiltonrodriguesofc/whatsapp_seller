import asyncio
import httpx
import os

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

async def debug_disconnect():
    api_url = os.environ.get("EVOLUTION_API_URL")
    api_key = os.environ.get("EVOLUTION_API_KEY")
    headers = {"apikey": api_key}
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.get(f"{api_url}/instance/fetchInstances", headers=headers)
        if res.status_code == 200:
            instances = res.json()
            if instances:
                print(f"Instances: {[i.get('instance', {}).get('instanceName') for i in instances]}")
                inst_name = instances[-1].get('instance', {}).get('instanceName')
                print(f"Logging out {inst_name}")
                logout_res = await client.delete(f"{api_url}/instance/logout/{inst_name}", headers=headers)
                print(f"Logout status: {logout_res.status_code}")
                print(f"Logout Response: {logout_res.text}")
            else:
                print("No instances to logout")
        else:
            print("Failed to fetch instances")

if __name__ == "__main__":
    asyncio.run(debug_disconnect())
