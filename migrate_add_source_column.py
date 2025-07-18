import sqlite3

db_path = "mental_health_agent/mood.db"
conn = sqlite3.connect(db_path)
try:
    conn.execute("ALTER TABLE moods ADD COLUMN source TEXT DEFAULT 'manual'")
    print("Migration successful: 'source' column added.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column 'source' already exists.")
    else:
        print("Migration failed:", e)
finally:
    conn.commit()
    conn.close()