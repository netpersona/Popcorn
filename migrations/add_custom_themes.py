"""
Migration: Create custom_themes table for user-uploaded themes
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
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='custom_themes'")
        if cursor.fetchone():
            print("custom_themes table already exists")
        else:
            print("Creating custom_themes table...")
            cursor.execute("""
                CREATE TABLE custom_themes (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    description TEXT,
                    theme_json TEXT NOT NULL,
                    is_public INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE (user_id, slug)
                )
            """)
            print("✓ custom_themes table created")
        
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
