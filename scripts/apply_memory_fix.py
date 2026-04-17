import os
import requests
from dotenv import load_dotenv

def apply_memory_optimizations():
    load_dotenv()
    api_url = os.environ.get("EVOLUTION_API_URL")
    api_key = os.environ.get("EVOLUTION_API_KEY")

    if not api_url or not api_key:
        print("Error: EVOLUTION_API_URL or EVOLUTION_API_KEY is missing from .env")
        return

    headers = {
        "apikey": api_key,
        "Content-Type": "application/json"
    }

    print("Fetching all connected instances from Evolution API...")
    try:
        # GET all instances
        resp = requests.get(f"{api_url}/instance/fetchInstances", headers=headers)
        resp.raise_for_status()
        instances = resp.json()
    except Exception as e:
        print(f"Failed to fetch instances: {e}")
        if 'resp' in locals():
            print(f"Response: {resp.text}")
        return

    if not isinstance(instances, list):
        print(f"Unexpected response format from fetchInstances: {instances}")
        return

    print(f"Found {len(instances)} instances recorded globally.")
    
    settings_payload = {
        "rejectCall": True,
        "msgCall": "",
        "groupsIgnore": True,
        "alwaysOnline": False,
        "readMessages": False,
        "readStatus": False,
        "syncFullHistory": False
    }

    success_count = 0
    for inst in instances:
        instance_name = inst.get("name")
        if not instance_name:
            continue
            
        print(f"Applying memory isolation fixes to instance: {instance_name}...")
        try:
            res = requests.post(f"{api_url}/settings/set/{instance_name}", headers=headers, json=settings_payload)
            if res.status_code in [200, 201]:
                print(f" -> SUCCESS on {instance_name}!")
                success_count += 1
            else:
                print(f" -> FAILED on {instance_name}: {res.status_code} {res.text}")
        except Exception as e:
            print(f" -> EXCEPTION on {instance_name}: {e}")

    print(f"\nDone. Successfully patched {success_count} / {len(instances)} instances.")

if __name__ == "__main__":
    apply_memory_optimizations()
