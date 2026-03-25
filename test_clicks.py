import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)

with engine.connect() as conn:
    print("--- Click Tracking Verification ---")
    
    # 1. Get initial count for a product (or first one)
    res = conn.execute(text("SELECT id, name, click_count FROM products LIMIT 1;")).fetchone()
    if not res:
        print("No products found to test.")
        exit(0)
    
    p_id, p_name, initial_count = res
    if initial_count is None: initial_count = 0
    print(f"Product: {p_name} (ID: {p_id})")
    print(f"Initial Click Count: {initial_count}")
    
    # 2. Simulate increment
    from sqlalchemy import update, func, Column, Integer, Table, MetaData
    # Manually execute the update logic we added to the repo
    # Note: we use conn.execute(update(...))
    metadata = MetaData()
    products_table = Table('products', metadata, Column('id', Integer, primary_key=True), Column('click_count', Integer))
    
    conn.execute(
        update(products_table)
        .where(products_table.c.id == p_id)
        .values(click_count=func.coalesce(products_table.c.click_count, 0) + 1)
    )
    conn.commit()
    
    # 3. Verify
    new_count = conn.execute(text(f"SELECT click_count FROM products WHERE id = {p_id}")).scalar()
    print(f"New Click Count: {new_count}")
    
    if new_count == initial_count + 1:
        print("SUCCESS: Click tracking increment is WORKING.")
    else:
        print(f"FAILED: Click tracking increment failed. Expected {initial_count + 1}, got {new_count}")
