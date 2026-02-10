
import sqlite3
try:
    conn = sqlite3.connect('cephly_dev.db')
    cursor = conn.cursor()
    
    print("--- TABLES ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for t in tables:
        print(t[0])
        
    print("\n--- MERCHANTS COLUMNS ---")
    cursor.execute("PRAGMA table_info(merchants);")
    columns = cursor.fetchall()
    for col in columns:
        print(col)
        
except Exception as e:
    print(e)
finally:
    if 'conn' in locals():
        conn.close()
