"""
Migration: Add app_version table for update tracking
Date: 2025-10-02
"""

import sqlite3
import os
import subprocess
from datetime import datetime

def get_git_commit():
    """Get current git commit hash"""
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], 
                                        stderr=subprocess.DEVNULL).decode('utf-8').strip()
        return commit[:7]
    except:
        return 'unknown'

def migrate():
    db_path = 'popcorn.db'
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist. Skipping migration.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_version'")
        if cursor.fetchone():
            print("app_version table already exists")
            return
        
        print("Creating app_version table...")
        cursor.execute("""
            CREATE TABLE app_version (
                id INTEGER PRIMARY KEY,
                current_version TEXT NOT NULL,
                current_commit TEXT,
                last_check_date TIMESTAMP,
                last_update_date TIMESTAMP,
                github_repo TEXT DEFAULT 'netpersona/Popcorn',
                update_available INTEGER DEFAULT 0,
                latest_version TEXT
            )
        """)
        
        current_commit = get_git_commit()
        print(f"Initializing version tracking (commit: {current_commit})...")
        cursor.execute("""
            INSERT INTO app_version (current_version, current_commit, last_update_date, github_repo)
            VALUES (?, ?, ?, ?)
        """, ('1.0.0', current_commit, datetime.utcnow(), 'netpersona/Popcorn'))
        
        conn.commit()
        print("✓ app_version table created and initialized")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
