
import sqlite3

VERSION_ID = 'b85c21bf1ba9'

try:
    conn = sqlite3.connect('cephly_dev.db')
    cursor = conn.cursor()
    
    # 1. Add 'platform' column
    try:
        cursor.execute("ALTER TABLE merchants ADD COLUMN platform VARCHAR(50) NOT NULL DEFAULT 'shopify'")
        print("Added 'platform' column.")
    except Exception as e:
        print(f"Error adding 'platform': {e}")

    # 2. Add 'platform_context' column
    try:
        cursor.execute("ALTER TABLE merchants ADD COLUMN platform_context JSON")
        print("Added 'platform_context' column.")
    except Exception as e:
        print(f"Error adding 'platform_context': {e}")
        
    # 3. Update Alembic Version
    # First check current version
    cursor.execute("SELECT version_num FROM alembic_version")
    current_ver = cursor.fetchone()
    print(f"Current version: {current_ver}")
    
    if current_ver:
        cursor.execute("UPDATE alembic_version SET version_num = ?", (VERSION_ID,))
    else:
        cursor.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (VERSION_ID,))
        
    conn.commit()
    print(f"Updated alembic_version to {VERSION_ID}")

except Exception as e:
    print(f"Migration script failed: {e}")
finally:
    if 'conn' in locals():
        conn.close()
