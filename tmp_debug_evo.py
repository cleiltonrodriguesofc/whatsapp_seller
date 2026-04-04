import json
import requests

base_url = "https://evolutionapiwhatsappsellerpro.onrender.com"
apikey = "94c2b7f8e8a31e84d4b295dcbb29cf6364024b893cfb16982eb412f71050ae9f"

def main():
    headers = {"apikey": apikey}
    inst_name = "cleilton tim teste"
    
    print(f"Using instance: {inst_name}")
    
    # 1. Fetch Chats
    try:
        resp = requests.post(f"{base_url}/chat/findChats/{inst_name}", json={}, headers=headers)
        chats = resp.json()
        if isinstance(chats, dict) and "records" in chats:
            chats = chats.get("records", [])
        elif isinstance(chats, dict) and "data" in chats:
            chats = chats.get("data", [])
            
        print(f"Found {len(chats)} chats")
        if chats and isinstance(chats, list):
            with open("debug.txt", "w", encoding="utf-8") as f:
                f.write("First chat raw JSON:\n")
                f.write(json.dumps(chats[0], indent=2))
                f.write("\n\n")
                jid = chats[0].get("id") or chats[0].get("remoteJid") or chats[0].get("jid")
                f.write(f"Target JID: {jid}\n")
                
                msg_payload = {"where": {"remoteJid": jid}, "limit": 3}
                msg_resp = requests.post(f"{base_url}/chat/findMessages/{inst_name}", json=msg_payload, headers=headers)
                f.write("Messages raw JSON:\n")
                f.write(json.dumps(msg_resp.json()[:1] if isinstance(msg_resp.json(), list) else msg_resp.json(), indent=2))
            print("Wrote to debug.txt")
            
    except Exception as e:
        print(f"Error checking chats: {e}")

if __name__ == "__main__":
    main()
