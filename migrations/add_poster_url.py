import sqlite3
import sys

def migrate():
    db_path = 'popcorn.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT poster_url FROM movies LIMIT 1")
        print("poster_url column already exists")
    except sqlite3.OperationalError:
        print("Adding poster_url column to movies table...")
        cursor.execute("ALTER TABLE movies ADD COLUMN poster_url TEXT")
        conn.commit()
        print("Successfully added poster_url column")
    
    conn.close()

if __name__ == '__main__':
    migrate()
