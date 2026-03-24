import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Load .env
load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
bucket_name = "produtos"

print(f"URL: {url}")
print(f"Key: {key[:10]}...{key[-5:] if key else ''}")

if not url or not key:
    print("Missing credentials!")
    sys.exit(1)

try:
    supabase = create_client(url, key)
    
    # Try to list buckets to verify connection
    buckets = supabase.storage.list_buckets()
    print(f"Buckets: {buckets}")
    
    # Check if 'produtos' exists
    exists = any(b.name == bucket_name for b in buckets)
    if not exists:
        print(f"Bucket '{bucket_name}' not found. Creating it...")
        supabase.storage.create_bucket(bucket_name, options={"public": False})
        print("Bucket created.")
    else:
        print(f"Bucket '{bucket_name}' exists.")

    # Try a test upload
    test_content = b"hello supabase"
    res = supabase.storage.from_(bucket_name).upload(
        path="test_connection.txt",
        file=test_content,
        file_options={"content-type": "text/plain"}
    )
    print(f"Upload result: {res}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
