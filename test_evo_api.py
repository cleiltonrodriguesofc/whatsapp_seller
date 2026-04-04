import requests
import json
import traceback

base_url = "https://evolutionapiwhatsappsellerpro.onrender.com"
apikey = "94c2b7f8e8a31e84d4b295dcbb29cf6364024b893cfb16982eb412f71050ae9f"
inst_name = "cleilton tim teste"
headers = {"apikey": apikey}

try:
    resp = requests.get(f"{base_url}/chat/fetchAllChats/{inst_name}", headers=headers)
    chats = resp.json()
    
    if isinstance(chats, dict) and "records" in chats:
        chats = chats.get("records", [])
    elif isinstance(chats, dict) and "data" in chats:
        chats = chats.get("data", [])
    elif isinstance(chats, dict):
        chats = list(chats.values())
        
    print(f"Found {len(chats)} chats.")
    
    with open("c:/Users/cleil/Documents/PROJETOS/whatsapp_sales_agent/evo_debug.txt", "w", encoding="utf-8") as f:
        f.write("=== CHATS ===\n")
        f.write(json.dumps(chats[:3], indent=2))
        
        if chats:
            c = chats[0]
            jid = c.get("remoteJid") or c.get("jid") or c.get("id") or ""
            f.write(f"\n\n=== MESSAGES FOR {jid} ===\n")
            
            msg_resp = requests.get(f"{base_url}/chat/fetchMessages/{inst_name}?remoteJid={jid}", headers=headers)
            f.write(f"RESP status: {msg_resp.status_code}\n")
            try:
                f.write(json.dumps(msg_resp.json()[:2] if isinstance(msg_resp.json(), list) else msg_resp.json(), indent=2))
            except:
                f.write(msg_resp.text)
                
            f.write("\n\n=== CONTACTS ===\n")
            contact_resp = requests.get(f"{base_url}/chat/fetchProfilePictureUrl/{inst_name}?number={jid}", headers=headers)
            f.write(contact_resp.text)
                
    print("Done writing to evo_debug.txt")
except Exception as e:
    print("Error:", e)
    traceback.print_exc()
