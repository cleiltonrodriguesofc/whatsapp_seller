import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "rc.cleiltonrodrigues@gmail.com")

if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def set_admin():
    db = SessionLocal()
    try:
        # 1. Ensure column is_admin exists (redundant with app.py but safe)
        try:
            db.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;"))
            db.commit()
            print("Column 'is_admin' added to 'users' table.")
        except Exception:
            # Column likely already exists
            db.rollback()

        # 2. Set the admin
        result = db.execute(
            text("UPDATE users SET is_admin = TRUE WHERE email = :email"),
            {"email": ADMIN_EMAIL}
        )
        db.commit()

        if result.rowcount > 0:
            print(f"Successfully set {ADMIN_EMAIL} as administrator.")
        else:
            print(f"Warning: No user found with email {ADMIN_EMAIL}. "
                  "Admin status will be set automatically upon registration.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    set_admin()
