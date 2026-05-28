import asyncio
from dotenv import load_dotenv; load_dotenv()
import httpx
from core.infrastructure.database.session import SessionLocal
from core.infrastructure.database.models import InstanceModel

db = SessionLocal()
# try pessoal first
inst = db.query(InstanceModel).filter(InstanceModel.name == 'pessoal_1_bc12').first()
if not inst:
    inst = db.query(InstanceModel).filter(InstanceModel.user_id == 1).first()
print(f'Using instance: {inst.name}')

async def debug():
    url = f'https://evolutionapiwhatsappsellerpro.onrender.com/chat/findChats/{inst.name}'
    headers = {'apikey': inst.apikey}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(url, json={}, headers=headers)
        data = r.json()
        if isinstance(data, list):
            print(f'Total chats: {len(data)}')
            with_name = [x for x in data if x.get('pushName')][:8]
            no_name = [x for x in data if not x.get('pushName')][:5]
            print('--- With pushName ---')
            for x in with_name:
                jid = x.get('remoteJid', '')[:35]
                name = x.get('pushName', '')
                print(f'  jid={jid}, push={name}')
            print('--- Without pushName ---')
            for x in no_name:
                jid = x.get('remoteJid', '')[:35]
                print(f'  jid={jid}')

asyncio.run(debug())
db.close()
