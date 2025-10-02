"""
Migration: Add migration_history table for tracking applied migrations
Date: 2025-10-02
"""

import sqlite3
import os
from datetime import datetime

def migrate():
    db_path = 'popcorn.db'
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist. Skipping migration.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if migration_history table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='migration_history'")
        if cursor.fetchone():
            print("migration_history table already exists")
            return
        
        print("Creating migration_history table...")
        cursor.execute("""
            CREATE TABLE migration_history (
                id INTEGER PRIMARY KEY,
                migration_name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP NOT NULL
            )
        """)
        
        # Record all existing migrations as already applied
        existing_migrations = [
            'add_plex_settings.py',
            'add_poster_url.py',
            'add_playback_settings.py',
            'add_user_theme.py',
            'add_app_version.py',
            'add_migration_history.py'  # This migration itself
        ]
        
        print("Recording existing migrations as applied...")
        for migration in existing_migrations:
            cursor.execute("""
                INSERT INTO migration_history (migration_name, applied_at)
                VALUES (?, ?)
            """, (migration, datetime.utcnow()))
            print(f"  - Recorded: {migration}")
        
        conn.commit()
        print("✓ migration_history table created and initialized")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
