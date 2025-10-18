"""
Popcorn Auto-Update System
Handles checking for updates, downloading new versions, and orchestrating the update process
"""

import os
import subprocess
import shutil
import requests
import json
import logging
from datetime import datetime
from pathlib import Path
import importlib.util
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UpdateManager:
    def __init__(self, github_repo='netpersona/Popcorn', backup_dir='backups'):
        self.github_repo = github_repo
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
    
    def is_running_in_docker(self):
        """Detect if running inside a Docker container"""
        try:
            # Check for .dockerenv file (most reliable method)
            if Path('/.dockerenv').exists():
                return True
            
            # Check cgroup for docker indicators
            if Path('/proc/self/cgroup').exists():
                with open('/proc/self/cgroup', 'r') as f:
                    if 'docker' in f.read() or 'containerd' in f.read():
                        return True
            
            # Check for common Docker environment variables
            docker_env_vars = ['DOCKER_CONTAINER', 'container', 'KUBERNETES_SERVICE_HOST']
            if any(os.getenv(var) for var in docker_env_vars):
                return True
            
            return False
        except Exception as e:
            logger.debug(f"Docker detection check failed: {e}")
            return False
        
    def get_current_commit(self):
        """Get the current git commit hash"""
        try:
            commit = subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'],
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            return commit[:7]
        except Exception as e:
            logger.warning(f"Could not get git commit: {e}")
            return 'unknown'
    
    def get_latest_release(self):
        """Check GitHub for the latest release"""
        try:
            url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return {
                'tag_name': data['tag_name'],
                'version': data['tag_name'].lstrip('v'),
                'name': data.get('name', data['tag_name']),
                'body': data.get('body', ''),
                'published_at': data['published_at'],
                'commit_sha': data['target_commitish']
            }
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            return None
    
    def check_for_updates(self):
        """Compare local version with latest GitHub release"""
        current = self.get_current_commit()
        latest_release = self.get_latest_release()
        is_docker = self.is_running_in_docker()
        
        if not latest_release:
            return {
                'available': False, 
                'error': 'Could not reach GitHub',
                'is_docker': is_docker
            }
        
        latest_commit = latest_release['commit_sha']
        if isinstance(latest_commit, str):
            latest_commit = latest_commit[:7]
        
        return {
            'available': current != latest_commit and current != 'unknown',
            'current_version': current,
            'latest_version': latest_release['tag_name'],
            'latest_version_name': latest_release['name'],
            'release_notes': latest_release['body'],
            'published_at': latest_release['published_at'],
            'is_docker': is_docker
        }
    
    def backup_database(self):
        """Create a backup of the database before updating"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f"popcorn_{timestamp}.db"
        
        try:
            if Path('popcorn.db').exists():
                shutil.copy2('popcorn.db', backup_path)
                logger.info(f"Database backed up to {backup_path}")
                return str(backup_path)
            return None
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            raise
    
    def restore_database(self, backup_path):
        """Restore database from backup"""
        try:
            if Path(backup_path).exists():
                shutil.copy2(backup_path, 'popcorn.db')
                logger.info(f"Database restored from {backup_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False
    
    def git_pull(self):
        """Pull latest changes from git repository"""
        try:
            subprocess.check_output(['git', 'pull', 'origin', 'main'], 
                                  stderr=subprocess.PIPE, text=True)
            logger.info("Successfully pulled latest code from GitHub")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Git pull failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Git pull error: {e}")
            return False
    
    def install_dependencies(self):
        """Install/update Python dependencies"""
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 
                                 'requirements.txt', '--quiet'])
            logger.info("Dependencies installed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to install dependencies: {e}")
            return False
    
    def discover_migrations(self):
        """Find all migration scripts in migrations/ folder"""
        migrations_dir = Path('migrations')
        if not migrations_dir.exists():
            return []
        
        migration_files = []
        for file in migrations_dir.glob('*.py'):
            if file.name != '__init__.py':
                migration_files.append(file)
        
        return sorted(migration_files)
    
    def bootstrap_migration_history(self):
        """Initialize migration_history table if it doesn't exist and record existing migrations"""
        import sqlite3
        from datetime import datetime
        
        try:
            conn = sqlite3.connect('popcorn.db')
            cursor = conn.cursor()
            
            # Check if migration_history table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='migration_history'")
            if cursor.fetchone():
                conn.close()
                return  # Table already exists
            
            logger.info("Bootstrapping migration_history table...")
            
            # Create the table
            cursor.execute("""
                CREATE TABLE migration_history (
                    id INTEGER PRIMARY KEY,
                    migration_name TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMP NOT NULL
                )
            """)
            
            # Record all existing migrations as already applied
            # This prevents re-running migrations that were applied before tracking existed
            existing_migrations = [
                'add_plex_settings.py',
                'add_poster_url.py',
                'add_playback_settings.py',
                'add_user_theme.py',
                'add_app_version.py',
                'add_migration_history.py',
                'add_custom_themes.py'
            ]
            
            for migration in existing_migrations:
                cursor.execute("""
                    INSERT INTO migration_history (migration_name, applied_at)
                    VALUES (?, ?)
                """, (migration, datetime.utcnow()))
                logger.info(f"  Pre-recorded: {migration}")
            
            conn.commit()
            conn.close()
            logger.info("✓ Migration history bootstrapped")
            
        except Exception as e:
            logger.error(f"Failed to bootstrap migration history: {e}")
            raise
    
    def get_applied_migrations(self):
        """Get list of already-applied migrations from database"""
        try:
            # Ensure migration_history table exists first
            self.bootstrap_migration_history()
            
            from models import MigrationHistory, get_session
            session = get_session()
            applied = session.query(MigrationHistory).all()
            return {m.migration_name for m in applied}
        except Exception as e:
            logger.warning(f"Could not get migration history: {e}")
            return set()
    
    def record_migration(self, migration_name):
        """Record a migration as applied"""
        try:
            from models import MigrationHistory, get_session
            from datetime import datetime
            session = get_session()
            
            history = MigrationHistory(
                migration_name=migration_name,
                applied_at=datetime.utcnow()
            )
            session.add(history)
            session.commit()
            logger.info(f"Recorded migration: {migration_name}")
        except Exception as e:
            logger.warning(f"Could not record migration {migration_name}: {e}")
    
    def run_migration(self, migration_file):
        """Execute a single migration script"""
        try:
            spec = importlib.util.spec_from_file_location(
                f"migration.{migration_file.stem}", 
                migration_file
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, 'migrate'):
                logger.info(f"Running migration: {migration_file.name}")
                module.migrate()
                self.record_migration(migration_file.name)
                return True
            else:
                logger.warning(f"Migration {migration_file.name} has no migrate() function")
                return False
        except Exception as e:
            logger.error(f"Migration {migration_file.name} failed: {e}")
            raise
    
    def run_all_migrations(self):
        """Execute only new migrations that haven't been applied yet"""
        all_migrations = self.discover_migrations()
        applied_migrations = self.get_applied_migrations()
        
        logger.info(f"Found {len(all_migrations)} total migration(s)")
        logger.info(f"Already applied: {len(applied_migrations)} migration(s)")
        
        new_migrations = [m for m in all_migrations if m.name not in applied_migrations]
        
        if not new_migrations:
            logger.info("No new migrations to apply")
            return True
        
        logger.info(f"Applying {len(new_migrations)} new migration(s)")
        
        for migration in new_migrations:
            try:
                self.run_migration(migration)
            except Exception as e:
                logger.error(f"Migration failed, stopping: {e}")
                raise
        
        logger.info("All new migrations completed successfully")
        return True
    
    def perform_update(self, progress_callback=None):
        """
        Perform the full update process
        progress_callback: function to call with progress updates (optional)
        """
        def report(step, message, progress):
            logger.info(f"[{progress}%] {step}: {message}")
            if progress_callback:
                progress_callback(step, message, progress)
        
        backup_path = None
        try:
            report('Preparing', 'Creating database backup', 10)
            backup_path = self.backup_database()
            
            report('Downloading', 'Pulling latest code from GitHub', 25)
            if not self.git_pull():
                raise Exception("Failed to download updates")
            
            report('Installing', 'Updating dependencies', 50)
            if not self.install_dependencies():
                raise Exception("Failed to install dependencies")
            
            report('Migrating', 'Running database migrations', 70)
            self.run_all_migrations()
            
            report('Finalizing', 'Update complete', 90)
            
            from models import AppVersion, get_session
            session = get_session()
            version_record = session.query(AppVersion).first()
            if version_record:
                version_record.current_commit = self.get_current_commit()
                version_record.last_update_date = datetime.utcnow()
                version_record.update_available = False
                session.commit()
            
            report('Complete', 'Update successful! Restart required', 100)
            return {'success': True, 'backup_path': backup_path}
            
        except Exception as e:
            logger.error(f"Update failed: {e}")
            report('Error', str(e), 0)
            
            if backup_path:
                logger.info("Attempting to restore from backup...")
                self.restore_database(backup_path)
            
            return {'success': False, 'error': str(e), 'backup_path': backup_path}
