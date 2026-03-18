
import httpx
import asyncio
import uuid
import sys

BASE_URL = "http://localhost:8000"

async def test_all():
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    password = "Password123!"
    business = "Test Biz"

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        print(f"--- TESTING SYSTEM ---")
        
        # 1. Register
        print("1. Registering...")
        reg_data = {
            "email": email,
            "password": password,
            "business_name": business
        }
        res = await client.post(f"{BASE_URL}/register", data=reg_data)
        assert res.status_code == 200
        assert "Dashboard" in res.text or "Welcome" in res.text
        print("   SUCCESS")

        # 2. Login (Should already be logged in from register, but let's re-login to be sure)
        print("2. Logging in...")
        login_data = {"username": email, "password": password}
        res = await client.post(f"{BASE_URL}/login", data=login_data)
        assert res.status_code == 200
        print("   SUCCESS")

        # 3. Product CRUD
        print("3. Product CRUD...")
        # Create
        prod_data = {
            "name": "Test Item",
            "price": "100.0",
            "description": "Desc",
            "affiliate_link": "http://link.com",
            "category": "Cat"
        }
        res = await client.post(f"{BASE_URL}/products/new", data=prod_data)
        assert res.status_code == 200
        assert "Test Item" in res.text
        
        # Find Product ID
        import re
        match = re.search(r'edit/(\d+)', res.text)
        if not match:
            print("   FAILED to find product ID in HTML")
            return
        prod_id = match.group(1)
        print(f"   Created Product ID: {prod_id}")
        
        # Edit
        edit_data = prod_data.copy()
        edit_data["name"] = "Updated Item"
        res = await client.post(f"{BASE_URL}/products/edit/{prod_id}", data=edit_data)
        assert res.status_code == 200
        assert "Updated Item" in res.text
        print("   Edit SUCCESS")
        
        # 4. WhatsApp Instance
        print("4. Instance Creation...")
        inst_name = f"inst_{uuid.uuid4().hex[:6]}"
        inst_data = {"name": inst_name}
        res = await client.post(f"{BASE_URL}/whatsapp/instance/new", data=inst_data)
        assert res.status_code == 200
        # Check if instance is in Connect page
        res = await client.get(f"{BASE_URL}/whatsapp/connect")
        assert inst_name in res.text
        print(f"   Created Instance: {inst_name}")
        
        # Find Instance ID for campaign (needed if we use ID)
        match_inst = re.search(r'qrcode/(\d+)', res.text)
        if not match_inst:
             # Try other patterns or list_all if possible
             match_inst = re.search(r'disconnect/(\d+)', res.text)
        
        inst_id = match_inst.group(1) if match_inst else "1" # Fallback
        print(f"   Instance ID: {inst_id}")

        # 5. Campaign CRUD
        print("5. Campaign CRUD...")
        camp_data = {
            "title": "My Campaign",
            "product_id": prod_id,
            "instance_id": inst_id,
            "groups": ["123@g.us"],
            "custom_message": "Hello!",
            "scheduled_at": ""
        }
        res = await client.post(f"{BASE_URL}/campaigns/new", data=camp_data)
        assert res.status_code == 200
        assert "My Campaign" in res.text
        
        # Find Campaign ID
        match_camp = re.search(r'campaigns/edit/(\d+)', res.text)
        if not match_camp:
            print("   FAILED to find campaign ID in HTML")
            return
        camp_id = match_camp.group(1)
        print(f"   Created Campaign ID: {camp_id}")
        
        # Edit Campaign
        edit_camp = camp_data.copy()
        edit_camp["title"] = "Updated Campaign"
        res = await client.post(f"{BASE_URL}/campaigns/edit/{camp_id}", data=edit_camp)
        assert res.status_code == 200
        assert "Updated Campaign" in res.text
        print("   Edit Campaign SUCCESS")
        
        # Delete Campaign
        print("6. Deleting Campaign...")
        res = await client.post(f"{BASE_URL}/campaigns/delete/{camp_id}")
        assert res.status_code == 200
        assert "Updated Campaign" not in res.text
        print("   Delete Campaign SUCCESS")

        # Delete Product
        print("7. Deleting Product...")
        res = await client.post(f"{BASE_URL}/products/delete/{prod_id}")
        assert res.status_code == 200
        assert "Updated Item" not in res.text
        print("   Delete Product SUCCESS")

        print("\n--- ALL TESTS PASSED! ---")

if __name__ == "__main__":
    try:
        asyncio.run(test_all())
    except Exception as e:
        print(f"\n--- TEST FAILED ---")
        print(e)
        sys.exit(1)
