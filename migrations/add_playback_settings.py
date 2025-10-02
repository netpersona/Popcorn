"""
Migration: Add playback_mode and enable_time_offset to Settings table
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
        cursor.execute("PRAGMA table_info(settings)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'playback_mode' not in columns:
            print("Adding playback_mode column to settings table...")
            cursor.execute("ALTER TABLE settings ADD COLUMN playback_mode TEXT DEFAULT 'web_player'")
            print("✓ playback_mode column added")
        else:
            print("playback_mode column already exists")
        
        if 'enable_time_offset' not in columns:
            print("Adding enable_time_offset column to settings table...")
            cursor.execute("ALTER TABLE settings ADD COLUMN enable_time_offset INTEGER DEFAULT 1")
            print("✓ enable_time_offset column added")
        else:
            print("enable_time_offset column already exists")
        
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
