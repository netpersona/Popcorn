import os
import sys
from sqlalchemy import create_engine, Column, String, text

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = 'popcorn.db'
engine = create_engine(f'sqlite:///{DB_PATH}')

def migrate():
    """Add Plex configuration columns to settings table"""
    with engine.connect() as conn:
        try:
            conn.execute(text("""
                ALTER TABLE settings ADD COLUMN plex_url VARCHAR;
            """))
            print("✓ Added plex_url column")
        except Exception as e:
            if 'duplicate column name' in str(e).lower() or 'already exists' in str(e).lower():
                print("- plex_url column already exists")
            else:
                raise
        
        try:
            conn.execute(text("""
                ALTER TABLE settings ADD COLUMN plex_token VARCHAR;
            """))
            print("✓ Added plex_token column")
        except Exception as e:
            if 'duplicate column name' in str(e).lower() or 'already exists' in str(e).lower():
                print("- plex_token column already exists")
            else:
                raise
        
        try:
            conn.execute(text("""
                ALTER TABLE settings ADD COLUMN plex_client VARCHAR;
            """))
            print("✓ Added plex_client column")
        except Exception as e:
            if 'duplicate column name' in str(e).lower() or 'already exists' in str(e).lower():
                print("- plex_client column already exists")
            else:
                raise
        
        conn.commit()
    
    print("\n✅ Migration complete: Plex settings columns added")

if __name__ == '__main__':
    migrate()
