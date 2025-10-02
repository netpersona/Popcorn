"""
Migration: Add theme to Users table
Date: 2025-10-02
"""

import sqlite3
import os

def migrate():
    db_path = 'popcorn.db'
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist. Skipping migration.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'theme' not in columns:
            print("Adding theme column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'plex'")
            print("✓ theme column added")
        else:
            print("theme column already exists")
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
