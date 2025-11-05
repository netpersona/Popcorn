import os
import sys
import json
import queue
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, abort, send_file, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from models import init_db, get_session, Settings, User, Movie, HolidayChannel, MovieOverride
from plex_api import PlexAPI
from scheduler import ScheduleGenerator
from auth import PlexOAuth, create_or_update_plex_user
from user_management import user_mgmt_bp, validate_invite_code, mark_invite_used
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
import requests
from io import BytesIO
from collections import OrderedDict

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bounded LRU cache for images (max 300 posters ~150MB)
class BoundedImageCache:
    def __init__(self, max_size=300):
        self.cache = OrderedDict()
        self.max_size = max_size
    
    def get(self, key):
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    
    def set(self, key, value):
        if key in self.cache:
            # Update existing and move to end
            self.cache.move_to_end(key)
        self.cache[key] = value
        
        # Evict oldest if over limit
        if len(self.cache) > self.max_size:
            oldest = next(iter(self.cache))
            logger.info(f"Evicting oldest cached poster: {oldest}")
            del self.cache[oldest]
    
    def __contains__(self, key):
        return key in self.cache

image_cache = BoundedImageCache(max_size=300)

def time_to_minutes(time_str):
    """Convert HH:MM time string to minutes from midnight"""
    try:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    except:
        return 0

def get_current_minutes():
    """Get current time in minutes from midnight"""
    now = datetime.now()
    return now.hour * 60 + now.minute

def is_safe_url(target):
    """Validate redirect URL is safe (relative to current host)"""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

app = Flask(__name__, template_folder='pages')

session_secret = os.getenv('SESSION_SECRET')
if not session_secret or session_secret == 'dev-secret-key-change-in-production':
    if os.getenv('FLASK_ENV') == 'production':
        logger.error("CRITICAL: SESSION_SECRET not set in production! Application will not start.")
        sys.exit(1)
    else:
        logger.warning("WARNING: Using default SESSION_SECRET. Set SESSION_SECRET environment variable for production!")
        session_secret = 'dev-secret-key-change-in-production'

app.secret_key = session_secret
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['REMEMBER_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=365)
app.config['WTF_CSRF_TIME_LIMIT'] = None

csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

app.register_blueprint(user_mgmt_bp)

@login_manager.user_loader
def load_user(user_id):
    db_session = get_session()
    return db_session.query(User).filter_by(id=int(user_id)).first()

db_session = None
plex_api = None
scheduler = None

def run_migrations():
    """Run database migrations for new columns and tables"""
    import sqlite3
    from models import get_db_path
    
    logger.info("Running database migrations...")
    db_path = get_db_path()
    logger.info(f"Using database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Add channel numbers to settings table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE settings ADD COLUMN enable_channel_numbers BOOLEAN DEFAULT 1")
        logger.info("Added column: enable_channel_numbers to settings")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower() or "no such table" in str(e).lower():
            pass
        else:
            logger.warning(f"Error adding enable_channel_numbers: {e}")
    
    # Add brightness control to settings table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE settings ADD COLUMN current_glow_brightness INTEGER DEFAULT 100")
        logger.info("Added column: current_glow_brightness to settings")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower() or "no such table" in str(e).lower():
            pass
        else:
            logger.warning(f"Error adding current_glow_brightness: {e}")
    
    # Add TMDB API key to settings table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE settings ADD COLUMN tmdb_api_key VARCHAR")
        logger.info("Added column: tmdb_api_key to settings")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower() or "no such table" in str(e).lower():
            pass
        else:
            logger.warning(f"Error adding tmdb_api_key: {e}")
    
    # Add selected movie libraries to settings table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE settings ADD COLUMN selected_movie_libraries TEXT")
        logger.info("Added column: selected_movie_libraries to settings")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower() or "no such table" in str(e).lower():
            pass
        else:
            logger.warning(f"Error adding selected_movie_libraries: {e}")
    
    # Add Plex machine identifier to settings table if it doesn't exist
    try:
        cursor.execute("ALTER TABLE settings ADD COLUMN plex_machine_identifier VARCHAR")
        logger.info("Added column: plex_machine_identifier to settings")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower() or "no such table" in str(e).lower():
            pass
        else:
            logger.warning(f"Error adding plex_machine_identifier: {e}")
    
    # Add user preference columns to users table if they don't exist
    user_columns = [
        ('enable_crt_mode', 'BOOLEAN DEFAULT 0'),
        ('enable_film_grain', 'BOOLEAN DEFAULT 0'),
        ('playback_mode', 'VARCHAR DEFAULT "web_player"'),
        ('enable_time_offset', 'BOOLEAN DEFAULT 1'),
        ('visible_channels', 'TEXT'),
        ('plex_client', 'VARCHAR'),
        ('current_glow_brightness', 'INTEGER DEFAULT 100'),
        ('using_default_password', 'BOOLEAN DEFAULT 0')
    ]
    
    for column_name, column_def in user_columns:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
            logger.info(f"Added user column: {column_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower() or "no such table" in str(e).lower():
                pass
            else:
                logger.warning(f"Error adding user {column_name}: {e}")
    
    # Add movie metadata columns
    movie_columns = [
        ('audience_rating', 'REAL'),
        ('content_rating', 'VARCHAR'),
        ('cast', 'VARCHAR'),
        ('art_url', 'VARCHAR'),
        ('library_name', 'VARCHAR')
    ]
    
    for column_name, column_def in movie_columns:
        try:
            cursor.execute(f"ALTER TABLE movies ADD COLUMN {column_name} {column_def}")
            logger.info(f"Added movie column: {column_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower() or "no such table" in str(e).lower():
                pass
            else:
                logger.warning(f"Error adding movie {column_name}: {e}")
    
    # Create watch_history table if not exists
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS watch_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        movie_id INTEGER,
        plex_id VARCHAR NOT NULL,
        movie_title VARCHAR NOT NULL,
        movie_genre VARCHAR,
        watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
        duration_watched INTEGER,
        playback_position INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (movie_id) REFERENCES movies(id)
    )
    ''')
    
    # Add playback_position to existing watch_history table
    try:
        cursor.execute("ALTER TABLE watch_history ADD COLUMN playback_position INTEGER DEFAULT 0")
        logger.info("Added column: playback_position to watch_history")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower() or "no such table" in str(e).lower():
            pass
        else:
            logger.warning(f"Error adding playback_position: {e}")
    
    # Create channel_favorites table if not exists
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS channel_favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        channel_name VARCHAR NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, channel_name)
    )
    ''')
    
    # Create movie_favorites table if not exists
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS movie_favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        movie_id INTEGER NOT NULL,
        plex_id VARCHAR NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (movie_id) REFERENCES movies(id),
        UNIQUE(user_id, movie_id)
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database migrations complete")

def create_default_accounts():
    """Create default demo accounts for first-time users"""
    db_session = get_session()
    
    # Create admin account if it doesn't exist
    admin_user = db_session.query(User).filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            email='admin@popcorn.local',
            is_admin=True,
            using_default_password=True
        )
        admin_user.set_password('admin')
        db_session.add(admin_user)
        logger.info("Created default admin account (username: admin, password: admin)")
    
    # Create demo account if it doesn't exist
    demo_user = db_session.query(User).filter_by(username='demo').first()
    if not demo_user:
        demo_user = User(
            username='demo',
            email='demo@popcorn.local',
            is_admin=False,
            using_default_password=True
        )
        demo_user.set_password('demo')
        db_session.add(demo_user)
        logger.info("Created default demo account (username: demo, password: demo)")
    
    db_session.commit()

def initialize_app():
    global db_session, plex_api, scheduler
    
    logger.info("Initializing Popcorn app...")
    
    # Check if data volume is properly mounted
    from models import is_volume_properly_mounted
    is_mounted, warning_msg = is_volume_properly_mounted()
    app.config['VOLUME_MOUNTED'] = is_mounted
    app.config['VOLUME_WARNING'] = warning_msg
    
    if not is_mounted and warning_msg:
        logger.error("=" * 80)
        logger.error(warning_msg)
        logger.error("Add volume mapping when running container:")
        logger.error("  docker run -v /path/on/host:/data ...")
        logger.error("=" * 80)
    
    # Run migrations before initializing database
    run_migrations()
    
    db_session = init_db()
    logger.info("Database initialized")
    
    # Create default accounts for demo/evaluation purposes
    create_default_accounts()
    
    try:
        settings_obj = db_session.query(Settings).first()
        plex_api = PlexAPI(db_settings=settings_obj)
        logger.info("Plex API connected")
    except Exception as e:
        logger.warning(f"Plex API not available: {e}")
        plex_api = None
    
    scheduler = ScheduleGenerator()
    logger.info("Scheduler initialized")
    
    sync_movies()
    scheduler.generate_all_schedules(force=True)

def sync_movies():
    if not plex_api:
        logger.warning("Plex API not available, skipping movie sync")
        return
    
    logger.info("Syncing movies from Plex...")
    
    # Get selected libraries from settings
    from models import Movie
    session = get_session()
    settings = session.query(Settings).first()
    
    selected_libraries = None
    auto_selected = False
    if settings and settings.selected_movie_libraries:
        # Parse comma-separated library names
        selected_libraries = [lib.strip() for lib in settings.selected_movie_libraries.split(',') if lib.strip()]
        logger.info(f"Syncing from selected libraries: {selected_libraries}")
    else:
        logger.info("No library filter set, syncing from all movie libraries")
        auto_selected = True
    
    # Fetch movies with library filter
    movie_data = plex_api.fetch_movies(selected_libraries=selected_libraries)
    
    # Auto-save library selection on first sync
    if auto_selected and settings:
        try:
            available_libraries = plex_api.get_movie_libraries()
            if available_libraries:
                settings.selected_movie_libraries = ','.join(available_libraries)
                session.commit()
                logger.info(f"Auto-selected all {len(available_libraries)} movie libraries on first sync: {available_libraries}")
        except Exception as e:
            logger.error(f"Error auto-selecting libraries: {e}")
    
    existing_combinations = {(m.plex_id, m.genre) for m in session.query(Movie).all()}
    
    new_count = 0
    update_count = 0
    for data in movie_data:
        if data['duration'] <= 0:
            logger.warning(f"Skipping movie '{data['title']}' with invalid duration: {data['duration']}")
            continue
            
        for genre in data['genres']:
            if (data['plex_id'], genre) not in existing_combinations:
                movie = Movie(
                    title=data['title'],
                    genre=genre,
                    duration=max(data['duration'], 1),
                    plex_id=data['plex_id'],
                    year=data['year'],
                    rating=data['rating'],
                    content_rating=data.get('content_rating'),
                    audience_rating=data.get('audience_rating'),
                    summary=data['summary'],
                    poster_url=data.get('poster_url'),
                    art_url=data.get('art_url'),
                    cast=data.get('cast'),
                    library_name=data.get('library_name')
                )
                session.add(movie)
                new_count += 1
            else:
                existing_movie = session.query(Movie).filter_by(plex_id=data['plex_id'], genre=genre).first()
                if existing_movie:
                    changed = False
                    if existing_movie.poster_url != data.get('poster_url'):
                        existing_movie.poster_url = data.get('poster_url')
                        changed = True
                    if existing_movie.audience_rating != data.get('audience_rating'):
                        existing_movie.audience_rating = data.get('audience_rating')
                        changed = True
                    if existing_movie.content_rating != data.get('content_rating'):
                        existing_movie.content_rating = data.get('content_rating')
                        changed = True
                    if existing_movie.cast != data.get('cast'):
                        existing_movie.cast = data.get('cast')
                        changed = True
                    if existing_movie.art_url != data.get('art_url'):
                        existing_movie.art_url = data.get('art_url')
                        changed = True
                    if existing_movie.library_name != data.get('library_name'):
                        existing_movie.library_name = data.get('library_name')
                        changed = True
                    if changed:
                        update_count += 1
    
    session.commit()
    logger.info(f"Added {new_count} new movie entries to database")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('guide'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        db_session = get_session()
        user = db_session.query(User).filter_by(username=username).first()
        
        if user and user.check_password(password):
            user.last_login = datetime.utcnow()
            db_session.commit()
            login_user(user, remember=True)
            
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('guide'))
        
        flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('guide'))
    
    invite_code = request.args.get('invite', '')
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        setup_token = request.form.get('setup_token', '')
        invite_code = request.form.get('invite_code', '')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('login.html', show_register=True, invite_code=invite_code)
        
        db_session = get_session()
        
        is_first_user = db_session.query(User).count() == 0
        invited_by_user_id = None
        
        if is_first_user:
            required_token = os.getenv('ADMIN_SETUP_TOKEN')
            if not required_token:
                flash('Admin setup is not configured. Please contact the administrator.', 'error')
                return render_template('login.html', show_register=True)
            
            if setup_token != required_token:
                flash('Invalid setup token. The first user registration requires the admin setup token.', 'error')
                return render_template('login.html', show_register=True)
        else:
            if not invite_code:
                flash('An invitation code is required to register.', 'error')
                return render_template('login.html', show_register=True)
            
            is_valid, result = validate_invite_code(invite_code)
            if not is_valid:
                flash(result, 'error')
                return render_template('login.html', show_register=True, invite_code=invite_code)
            
            invitation = result
            invited_by_user_id = invitation.created_by
        
        if db_session.query(User).filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('login.html', show_register=True, invite_code=invite_code)
        
        if email and db_session.query(User).filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('login.html', show_register=True, invite_code=invite_code)
        
        user = User(
            username=username,
            email=email,
            is_admin=is_first_user,
            invited_by=invited_by_user_id
        )
        user.set_password(password)
        
        db_session.add(user)
        db_session.commit()
        
        if invite_code and not is_first_user:
            mark_invite_used(invite_code, user.id)
        
        login_user(user, remember=True)
        flash('Account created successfully!', 'success')
        return redirect(url_for('guide'))
    
    db_session = get_session()
    is_first_user = db_session.query(User).count() == 0
    return render_template('login.html', show_register=True, is_first_user=is_first_user, invite_code=invite_code)

@app.route('/auth/plex')
def plex_auth():
    db_session = get_session()
    is_first_user = db_session.query(User).count() == 0
    
    if is_first_user:
        required_token = os.getenv('ADMIN_SETUP_TOKEN')
        if not required_token:
            flash('Admin setup is not configured. Please register a local account first.', 'error')
            return redirect(url_for('login'))
        
        flash('The first admin account must be created using local registration with the setup token.', 'info')
        return redirect(url_for('register'))
    
    plex_oauth = PlexOAuth()
    redirect_uri = url_for('plex_callback', _external=True)
    
    auth_data = plex_oauth.get_auth_url(redirect_uri)
    
    if not auth_data:
        flash('Failed to connect to Plex', 'error')
        return redirect(url_for('login'))
    
    session['plex_pin_id'] = auth_data['pin_id']
    return jsonify({
        'success': True,
        'auth_url': auth_data['auth_url'],
        'pin_id': auth_data['pin_id']
    })

@app.route('/auth/plex/check/<pin_id>')
@csrf.exempt
def check_plex_pin(pin_id):
    plex_oauth = PlexOAuth()
    auth_token = plex_oauth.check_pin(pin_id)
    
    if not auth_token:
        return jsonify({'success': False, 'status': 'pending'})
    
    user_info = plex_oauth.get_user_info(auth_token)
    
    if not user_info:
        return jsonify({'success': False, 'status': 'error', 'message': 'Failed to get user information'})
    
    db_session = get_session()
    
    # Get configured Plex server machine identifier from settings
    settings = db_session.query(Settings).first()
    if not settings or not settings.plex_machine_identifier:
        return jsonify({
            'success': False,
            'status': 'error',
            'message': 'Plex server not configured. Contact administrator.'
        })
    
    # Verify user has access using machine identifier matching
    # This works for both internal and external users
    user_servers = plex_oauth.get_user_servers(auth_token)
    admin_machine_id = settings.plex_machine_identifier
    
    user_server_ids = [server['machineIdentifier'] for server in user_servers]
    has_access = admin_machine_id in user_server_ids
    
    if not has_access:
        logger.warning(f"User {user_info['username']} does not have access to server {admin_machine_id}")
        logger.info(f"User has access to servers: {user_server_ids}")
        return jsonify({
            'success': False,
            'status': 'no_library_access',
            'message': 'You do not have access to this Plex server. Please ask the administrator to share the server with your Plex account.'
        })
    
    logger.info(f"User {user_info['username']} verified with access to server {admin_machine_id}")
    
    # Smart merge logic: plex_id → email → create new
    user = None
    
    # 1. Check if plex_id already exists (existing Plex user)
    user = db_session.query(User).filter_by(plex_id=user_info['plex_id']).first()
    
    if user:
        # Update existing Plex-linked account
        user.plex_token = auth_token
        user.plex_username = user_info.get('username')
        user.display_name = user_info.get('display_name')
        user.avatar_url = user_info.get('avatar_url')
        if user_info.get('email'):
            user.email = user_info['email']
        user.updated_at = datetime.utcnow()
        user.last_login = datetime.utcnow()
        db_session.commit()
        logger.info(f"Updated existing Plex user: {user.username}")
    
    # 2. Check if email matches existing local account (merge scenario)
    elif user_info.get('email'):
        user = db_session.query(User).filter_by(email=user_info['email']).first()
        
        if user:
            # Link Plex to existing local account
            user.plex_id = user_info['plex_id']
            user.plex_token = auth_token
            user.plex_username = user_info.get('username')
            user.display_name = user_info.get('display_name')
            user.avatar_url = user_info.get('avatar_url')
            user.updated_at = datetime.utcnow()
            user.last_login = datetime.utcnow()
            db_session.commit()
            logger.info(f"Linked Plex account to existing user by email: {user.username}")
    
    # 3. Create new account (new Plex user with library access)
    if not user:
        username = user_info.get('username') or user_info.get('email', '').split('@')[0] or f"plex_user_{user_info['plex_id']}"
        
        # Ensure unique username
        base_username = username
        counter = 1
        while db_session.query(User).filter_by(username=username).first():
            username = f"{base_username}_{counter}"
            counter += 1
        
        user = User(
            username=username,
            email=user_info.get('email'),
            plex_id=user_info['plex_id'],
            plex_token=auth_token,
            plex_username=user_info.get('username'),
            display_name=user_info.get('display_name') or username,
            avatar_url=user_info.get('avatar_url'),
            is_admin=False,
            is_active=True,
            last_login=datetime.utcnow()
        )
        db_session.add(user)
        db_session.commit()
        logger.info(f"Created new Plex user with library access: {user.username}")
    
    login_user(user, remember=True)
    session.pop('plex_pin_id', None)
    return jsonify({'success': True, 'status': 'authorized', 'user': user.display_name})

@app.route('/auth/plex/callback')
@csrf.exempt
def plex_callback():
    return render_template('plex_callback.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    session.pop('_flashes', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    from theme_service import ThemeService
    from watch_history_service import WatchHistoryService
    from channel_numbers import CHANNEL_NUMBERS
    import json
    
    themes = ThemeService.get_all_themes_for_user(current_user.id)
    
    if request.method == 'POST':
        theme = request.form.get('theme')
        if theme and theme in themes:
            db_session = get_session()
            user = db_session.query(User).get(current_user.id)
            user.theme = theme
            db_session.commit()
            flash(f'Theme changed to {themes[theme]["name"]}!', 'success')
            return redirect(url_for('profile'))
    
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes.get('plex', {})).get('colors', {})
    
    watch_stats = WatchHistoryService.get_user_stats(current_user.id)
    
    # Get all available channels
    all_channels = sorted(list(CHANNEL_NUMBERS.keys()))
    
    # Get user's visible channels (default to all if not set)
    visible_channels = []
    if current_user.visible_channels:
        try:
            visible_channels = json.loads(current_user.visible_channels)
        except:
            visible_channels = all_channels
    else:
        visible_channels = all_channels
    
    # Get admin max brightness setting
    db_session_local = get_session()
    settings_obj = db_session_local.query(Settings).first()
    admin_max_brightness = settings_obj.current_glow_brightness if settings_obj and settings_obj.current_glow_brightness else 100
    
    return render_template('profile.html', 
                         themes=themes, 
                         theme_colors=theme_colors,
                         watch_stats=watch_stats,
                         all_channels=all_channels,
                         visible_channels=visible_channels,
                         admin_max_brightness=admin_max_brightness)

@app.route('/profile/preferences', methods=['POST'])
@login_required
def update_preferences():
    db_session = get_session()
    user = db_session.query(User).get(current_user.id)
    settings_obj = db_session.query(Settings).first()
    
    user.enable_crt_mode = 'enable_crt_mode' in request.form
    user.enable_film_grain = 'enable_film_grain' in request.form
    user.enable_time_offset = 'enable_time_offset' in request.form
    user.playback_mode = request.form.get('playback_mode', 'web_player')
    user.plex_client = request.form.get('plex_client', '').strip() or None
    
    # Handle user brightness with validation against admin max
    brightness = request.form.get('current_glow_brightness')
    if brightness is not None:
        try:
            brightness_val = int(brightness)
            # Get admin max brightness
            admin_max = settings_obj.current_glow_brightness if settings_obj and settings_obj.current_glow_brightness else 100
            # Constrain user brightness to admin max
            if 0 <= brightness_val <= admin_max:
                user.current_glow_brightness = brightness_val
            else:
                user.current_glow_brightness = min(brightness_val, admin_max)
        except ValueError:
            pass
    
    db_session.commit()
    flash('Viewing preferences saved successfully!', 'success')
    return redirect(url_for('profile'))

@app.route('/profile/channels', methods=['POST'])
@login_required
def update_channel_visibility():
    import json
    from channel_numbers import CHANNEL_NUMBERS
    
    db_session = get_session()
    user = db_session.query(User).get(current_user.id)
    
    # Get all channels that were checked
    visible_channels = request.form.getlist('visible_channels')
    
    # If no channels selected, show all channels (default)
    if not visible_channels:
        visible_channels = list(CHANNEL_NUMBERS.keys())
    
    # Save as JSON
    user.visible_channels = json.dumps(visible_channels)
    db_session.commit()
    
    flash(f'Channel preferences saved! {len(visible_channels)} channels visible.', 'success')
    return redirect(url_for('profile'))

@app.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        flash('All password fields are required.', 'error')
        return redirect(url_for('profile'))
    
    db_session = get_session()
    user = db_session.query(User).get(current_user.id)
    
    if not user.check_password(current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('profile'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('profile'))
    
    if len(new_password) < 4:
        flash('New password must be at least 4 characters long.', 'error')
        return redirect(url_for('profile'))
    
    user.set_password(new_password)
    user.using_default_password = False
    db_session.commit()
    
    flash('Password changed successfully! Security warning removed.', 'success')
    return redirect(url_for('profile'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('guide'))

@app.route('/guide')
@login_required
def guide():
    from theme_service import ThemeService
    from channel_numbers import get_channel_number
    from watch_history_service import WatchHistoryService
    from models import MovieFavorite
    import json
    
    # Genre to icon mapping (using only free Font Awesome 6.x solid icons)
    GENRE_ICONS = {
        'Action': 'fa-fire',
        'Adventure': 'fa-compass',
        'Animation': 'fa-palette',
        'Anime': 'fa-dragon',
        'Biography': 'fa-book',
        'Comedy': 'fa-face-smile',
        'Crime': 'fa-user-secret',
        'Documentary': 'fa-camera',
        'Drama': 'fa-film',
        'Family': 'fa-house',
        'Fantasy': 'fa-hat-wizard',
        'History': 'fa-landmark',
        'Horror': 'fa-ghost',
        'Indie': 'fa-lightbulb',
        'Music': 'fa-music',
        'Musical': 'fa-guitar',
        'Mystery': 'fa-magnifying-glass',
        'Reality': 'fa-tv',
        'Romance': 'fa-heart',
        'Science Fiction': 'fa-rocket',
        'Short': 'fa-clock',
        'Sport': 'fa-trophy',
        'Thriller': 'fa-bolt',
        'TV Movie': 'fa-video',
        'War': 'fa-shield',
        'Western': 'fa-star',
        'Unknown': 'fa-circle-question',
        'Cozy Halloween': 'fa-gift',
        'Scary Halloween': 'fa-skull'
    }
    
    themes = ThemeService.get_all_themes_for_user(current_user.id)
    
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes.get('plex', {})).get('colors', {})
    
    # Get user's favorited movie IDs
    session = get_session()
    user_favorites = session.query(MovieFavorite.movie_id).filter_by(user_id=current_user.id).all()
    favorited_ids = {fav[0] for fav in user_favorites}
    
    if not scheduler:
        return render_template('error.html', message="Application not initialized", theme_colors=theme_colors)
    
    channels = scheduler.get_all_channels()
    
    # Filter channels based on user preferences
    visible_channels = None
    if current_user.visible_channels:
        try:
            visible_channels = json.loads(current_user.visible_channels)
        except:
            visible_channels = None
    
    # If user has channel preferences, filter the channels
    if visible_channels:
        channels = [ch for ch in channels if ch in visible_channels]
    
    guide_data = []
    for channel in channels:
        schedule = scheduler.get_channel_schedule(channel)
        programs = []
        
        for item in schedule:
            start_min = time_to_minutes(item.start_time)
            end_min = time_to_minutes(item.end_time)
            duration_min = end_min - start_min if end_min > start_min else (1440 - start_min + end_min)
            
            has_watched = WatchHistoryService.has_watched(current_user.id, item.movie.plex_id)
            progress_ms = WatchHistoryService.get_progress(current_user.id, item.movie.plex_id)
            
            # Calculate progress percentage
            progress_percent = 0
            if progress_ms > 0 and item.movie.duration > 0:
                movie_duration_ms = item.movie.duration * 60 * 1000
                progress_percent = min((progress_ms / movie_duration_ms) * 100, 100)
            
            is_favorited = item.movie.id in favorited_ids
            
            programs.append({
                'movie': item.movie,
                'start_time': item.start_time,
                'end_time': item.end_time,
                'start_minute': start_min,
                'duration_minutes': duration_min,
                'watched': has_watched,
                'progress_percent': progress_percent,
                'progress_ms': progress_ms,
                'is_favorited': is_favorited
            })
        
        guide_data.append({
            'name': channel,
            'number': get_channel_number(channel),
            'icon': GENRE_ICONS.get(channel, 'fa-film'),
            'programs': programs
        })
    
    current_minutes = get_current_minutes()
    
    # Calculate glow opacity based on user's brightness setting
    user_brightness = current_user.current_glow_brightness if current_user.current_glow_brightness is not None else 100
    glow_opacity = user_brightness / 100.0
    
    return render_template('guide.html', 
                         channels=guide_data, 
                         current_minutes=current_minutes,
                         theme_colors=theme_colors,
                         glow_opacity=glow_opacity)

@app.route('/channels')
@login_required
def channels_list():
    from theme_service import ThemeService
    
    themes = ThemeService.get_all_themes_for_user(current_user.id)
    
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes.get('plex', {})).get('colors', {})
    
    if not scheduler:
        return render_template('error.html', message="Application not initialized", theme_colors=theme_colors)
    
    channels = scheduler.get_all_channels()
    
    channel_info = []
    for channel in channels:
        current = scheduler.get_current_playing(channel)
        channel_info.append({
            'name': channel,
            'current': current.movie if current else None
        })
    
    return render_template('index.html', channels=channel_info, theme_colors=theme_colors)

@app.route('/channel/<channel_name>')
@login_required
def channel(channel_name):
    from theme_service import ThemeService
    
    themes = ThemeService.get_all_themes_for_user(current_user.id)
    
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes.get('plex', {})).get('colors', {})
    
    if not scheduler:
        return render_template('error.html', message="Application not initialized", theme_colors=theme_colors)
    
    current = scheduler.get_current_playing(channel_name)
    schedule = scheduler.get_channel_schedule(channel_name)
    
    return render_template('channel.html', 
                         channel_name=channel_name,
                         current=current,
                         schedule=schedule,
                         theme_colors=theme_colors)

@app.route('/play/<int:movie_id>', methods=['POST'])
@login_required
def play(movie_id):
    if not plex_api:
        return jsonify({'success': False, 'message': 'Plex API not available'})
    
    from models import Movie, WatchHistory
    session = get_session()
    movie = session.query(Movie).filter_by(id=movie_id).first()
    
    if not movie:
        return jsonify({'success': False, 'message': 'Movie not found'})
    
    # Check if device_id was passed in request (from device selector dropdown)
    device_id = request.json.get('device_id') if request.is_json else None
    offset_ms = request.json.get('offset_ms', 0) if request.is_json else 0
    
    # Determine playback mode and client
    if device_id and device_id != 'web_player':
        # User selected a specific device from dropdown
        playback_mode = 'client_playback'
        client_id = device_id  # device_id is the machine_identifier
    else:
        # Fall back to user's saved preferences or web player
        playback_mode = current_user.playback_mode if current_user.playback_mode else 'web_player'
        client_id = current_user.plex_client if current_user.plex_client else None
    
    success, result, offset_min = plex_api.play_movie(movie.plex_id, offset_ms=offset_ms, playback_mode=playback_mode, client_id=client_id)
    
    if success:
        watch_entry = WatchHistory(
            user_id=current_user.id,
            movie_id=movie.id,
            plex_id=movie.plex_id,
            movie_title=movie.title,
            movie_genre=movie.genre,
            duration_watched=movie.duration,
            playback_position=offset_ms
        )
        session.add(watch_entry)
        session.commit()
        logger.info(f"Logged watch history for user {current_user.id}: {movie.title} at position {offset_ms}ms")
    
    if success and playback_mode == 'web_player':
        message = f"Opening movie in browser" + (f" (starting at {offset_min} min)" if offset_min > 0 else "")
        logger.info(f"Returning web_url to client: {result}")
        return jsonify({'success': True, 'message': message, 'web_url': result, 'offset_min': offset_min})
    else:
        return jsonify({'success': success, 'message': result, 'offset_min': offset_min if success else 0})

@app.route('/api/favorite/<int:movie_id>', methods=['POST'])
@login_required
def toggle_favorite(movie_id):
    from models import Movie, MovieFavorite
    session = get_session()
    
    movie = session.query(Movie).filter_by(id=movie_id).first()
    if not movie:
        return jsonify({'success': False, 'message': 'Movie not found'}), 404
    
    existing_favorite = session.query(MovieFavorite).filter_by(
        user_id=current_user.id,
        movie_id=movie_id
    ).first()
    
    if existing_favorite:
        session.delete(existing_favorite)
        session.commit()
        return jsonify({'success': True, 'favorited': False, 'message': 'Removed from favorites'})
    else:
        favorite = MovieFavorite(
            user_id=current_user.id,
            movie_id=movie_id,
            plex_id=movie.plex_id
        )
        session.add(favorite)
        session.commit()
        return jsonify({'success': True, 'favorited': True, 'message': 'Added to favorites'})

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if not current_user.is_admin:
        flash('Only administrators can access settings', 'error')
        return redirect(url_for('guide'))
    
    db_session = get_session()
    settings_obj = db_session.query(Settings).first()
    
    if not settings_obj:
        settings_obj = Settings(shuffle_frequency='weekly')
        db_session.add(settings_obj)
        db_session.commit()
    
    if request.method == 'POST':
        if 'plex_url' in request.form:
            global plex_api
            
            settings_obj.plex_url = request.form.get('plex_url', '').strip() or None
            settings_obj.plex_token = request.form.get('plex_token', '').strip() or None
            # plex_client is now per-user setting, not admin setting
            db_session.commit()
            
            try:
                plex_api = PlexAPI(db_settings=settings_obj)
                logger.info("Plex API reconnected with new settings")
                
                # Capture and store the Plex server's machine identifier
                if plex_api.plex:
                    machine_id = plex_api.plex.machineIdentifier
                    settings_obj.plex_machine_identifier = machine_id
                    db_session.commit()
                    logger.info(f"Stored Plex machine identifier: {machine_id}")
                
                # Get available libraries
                available_libraries = plex_api.get_movie_libraries()
                if available_libraries:
                    # Only auto-select all libraries on first connect
                    if not settings_obj.selected_movie_libraries:
                        settings_obj.selected_movie_libraries = ','.join(available_libraries)
                        db_session.commit()
                        logger.info(f"Auto-selected all {len(available_libraries)} movie libraries on first connection: {available_libraries}")
                    else:
                        logger.info(f"Preserving existing library selection. Use library settings to modify selection.")
                else:
                    logger.warning("No movie libraries found on Plex server")
                
                sync_movies()
                scheduler.generate_all_schedules(force=True)
                
                movie_count = db_session.query(Movie).count()
                flash(f'Plex connected successfully! Synced {movie_count} movies and generated schedules.', 'success')
                return redirect(url_for('settings', plex_saved=1))
            except Exception as e:
                logger.error(f"Failed to connect to Plex with new settings: {e}")
                plex_api = None
                flash(f'Settings saved, but connection failed: {str(e)}', 'error')
                return redirect(url_for('settings', plex_error=1))
        elif 'tmdb_api_key' in request.form:
            tmdb_api_key = request.form.get('tmdb_api_key', '').strip() or None
            settings_obj.tmdb_api_key = tmdb_api_key
            db_session.commit()
            
            if tmdb_api_key:
                flash('TMDB API key saved successfully!', 'success')
            else:
                flash('TMDB API key removed.', 'success')
            return redirect(url_for('settings'))
        elif 'library_selection' in request.form:
            # Handle library selection changes
            if not plex_api:
                flash('Plex is not connected', 'error')
                return redirect(url_for('settings'))
            
            # Get all available libraries
            available_libraries = plex_api.get_movie_libraries()
            
            # Get selected libraries from form (checkboxes)
            selected_libraries = request.form.getlist('selected_libraries')
            
            # Validate at least one library is selected
            if not selected_libraries:
                flash('You must select at least one library', 'error')
                return redirect(url_for('settings'))
            
            # Validate all selected libraries exist
            invalid_libraries = [lib for lib in selected_libraries if lib not in available_libraries]
            if invalid_libraries:
                flash(f'Invalid libraries selected: {", ".join(invalid_libraries)}', 'error')
                return redirect(url_for('settings'))
            
            # Get previously selected libraries
            old_selected = []
            if settings_obj.selected_movie_libraries:
                old_selected = [lib.strip() for lib in settings_obj.selected_movie_libraries.split(',') if lib.strip()]
            
            # Update settings
            settings_obj.selected_movie_libraries = ','.join(selected_libraries)
            db_session.commit()
            logger.info(f"Library selection updated: {selected_libraries}")
            
            # Find deselected libraries
            deselected_libraries = [lib for lib in old_selected if lib not in selected_libraries]
            
            # Delete movies from deselected libraries
            if deselected_libraries:
                deleted_count = 0
                for library_name in deselected_libraries:
                    movies_to_delete = db_session.query(Movie).filter_by(library_name=library_name).all()
                    deleted_count += len(movies_to_delete)
                    for movie in movies_to_delete:
                        db_session.delete(movie)
                db_session.commit()
                logger.info(f"Deleted {deleted_count} movies from deselected libraries: {deselected_libraries}")
            
            # Re-sync movies from selected libraries
            sync_movies()
            
            # Regenerate schedules
            scheduler.generate_all_schedules(force=True)
            
            flash(f'Library selection updated! Syncing from {len(selected_libraries)} libraries.', 'success')
            return redirect(url_for('settings'))
        else:
            frequency = request.form.get('shuffle_frequency')
            brightness = request.form.get('current_glow_brightness')
            
            if frequency in ['daily', 'weekly', 'monthly']:
                settings_obj.shuffle_frequency = frequency
            
            if brightness is not None:
                try:
                    brightness_val = int(brightness)
                    if 0 <= brightness_val <= 100:
                        settings_obj.current_glow_brightness = brightness_val
                except ValueError:
                    pass
            
            db_session.commit()
            
            if request.form.get('reshuffle_now'):
                scheduler.generate_all_schedules(force=True)
                return redirect(url_for('settings', reshuffled=1))
            
            flash('Settings saved successfully!', 'success')
            return redirect(url_for('settings'))
    
    reshuffled = request.args.get('reshuffled')
    plex_saved = request.args.get('plex_saved')
    
    from theme_service import ThemeService
    themes = ThemeService.get_all_themes_for_user(current_user.id)
    
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes.get('plex', {})).get('colors', {})
    
    channels = db_session.query(HolidayChannel).order_by(HolidayChannel.name).all()
    
    # Get available and selected movie libraries
    available_libraries = []
    selected_libraries = []
    if plex_api:
        try:
            available_libraries = plex_api.get_movie_libraries()
            if settings_obj.selected_movie_libraries:
                selected_libraries = [lib.strip() for lib in settings_obj.selected_movie_libraries.split(',') if lib.strip()]
            logger.info(f"Available libraries: {available_libraries}, Selected: {selected_libraries}")
        except Exception as e:
            logger.error(f"Error fetching movie libraries: {e}")
    
    return render_template('settings.html', settings=settings_obj, reshuffled=reshuffled, plex_saved=plex_saved, theme_colors=theme_colors, holiday_channels=channels, available_libraries=available_libraries, selected_libraries=selected_libraries)

@app.route('/settings/test-plex', methods=['POST'])
@login_required
def test_plex_connection():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    plex_url = request.form.get('plex_url', '').strip()
    plex_token = request.form.get('plex_token', '').strip()
    
    if not plex_url or not plex_token:
        return jsonify({'success': False, 'message': 'Plex URL and Token are required'})
    
    try:
        from plex_api import PlexServer
        test_plex = PlexServer(plex_url, plex_token)
        server_name = test_plex.friendlyName
        return jsonify({
            'success': True,
            'message': f'Successfully connected to: {server_name}'
        })
    except Exception as e:
        logger.error(f"Error testing Plex connection: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Connection failed: An internal error occurred while testing the Plex connection.'
        })

@app.route('/admin/test-tmdb', methods=['POST'])
@login_required
def test_tmdb_connection():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    tmdb_api_key = request.form.get('tmdb_api_key', '').strip()
    
    if not tmdb_api_key:
        return jsonify({'success': False, 'message': 'TMDB API key is required'})
    
    try:
        from tmdb_api import TMDBAPI
        test_tmdb = TMDBAPI(api_key=tmdb_api_key)
        
        # Make a simple test request to validate the API key
        test_result = test_tmdb._make_request('configuration')
        
        if test_result:
            return jsonify({
                'success': True,
                'message': 'Successfully connected to TMDB API!'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid API key or connection failed'
            })
    except Exception as e:
        logger.error(f"Error testing TMDB connection: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Connection failed: {str(e)}'
        })

@app.route('/api/clients')
@login_required
def get_clients():
    logger.info(f"API /api/clients called by user {current_user.username}")
    
    if not plex_api:
        logger.warning("Plex API is None - cannot get clients")
        return jsonify({'success': False, 'clients': [], 'error': 'Plex API not initialized'})
    
    try:
        clients = plex_api.get_available_clients()
        logger.info(f"Found {len(clients)} Plex clients: {[c['name'] for c in clients]}")
        return jsonify({'success': True, 'clients': clients})
    except Exception as e:
        logger.error(f"Error getting clients: {e}", exc_info=True)
        return jsonify({'success': False, 'clients': [], 'error': 'An internal server error occurred.'})

@app.route('/api/devices', methods=['GET'])
@login_required
def get_user_devices():
    """Get all saved devices for current user"""
    from models import UserDevice
    session = get_session()
    
    devices = session.query(UserDevice).filter_by(user_id=current_user.id).order_by(UserDevice.is_default.desc(), UserDevice.device_name).all()
    
    device_list = [{
        'id': d.id,
        'device_name': d.device_name,
        'machine_identifier': d.machine_identifier,
        'platform': d.platform,
        'product': d.product,
        'is_default': d.is_default
    } for d in devices]
    
    return jsonify({'success': True, 'devices': device_list})

@app.route('/api/devices', methods=['POST'])
@login_required
def save_device():
    """Save a new device for current user"""
    from models import UserDevice
    session = get_session()
    
    data = request.get_json()
    device_name = data.get('device_name')
    machine_identifier = data.get('machine_identifier')
    platform = data.get('platform', '')
    product = data.get('product', '')
    set_as_default = data.get('is_default', False)
    
    if not device_name or not machine_identifier:
        return jsonify({'success': False, 'message': 'Device name and machine identifier required'}), 400
    
    # Check if device already exists for this user
    existing = session.query(UserDevice).filter_by(
        user_id=current_user.id,
        machine_identifier=machine_identifier
    ).first()
    
    if existing:
        return jsonify({'success': False, 'message': 'Device already saved'}), 400
    
    # If setting as default, unset other defaults
    if set_as_default:
        session.query(UserDevice).filter_by(user_id=current_user.id).update({'is_default': False})
    
    # Create new device
    new_device = UserDevice(
        user_id=current_user.id,
        device_name=device_name,
        machine_identifier=machine_identifier,
        platform=platform,
        product=product,
        is_default=set_as_default
    )
    
    session.add(new_device)
    session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Device saved successfully',
        'device': {
            'id': new_device.id,
            'device_name': new_device.device_name,
            'machine_identifier': new_device.machine_identifier,
            'platform': new_device.platform,
            'product': new_device.product,
            'is_default': new_device.is_default
        }
    })

@app.route('/api/devices/<int:device_id>/default', methods=['POST'])
@login_required
def set_default_device(device_id):
    """Set a device as default for current user"""
    from models import UserDevice
    session = get_session()
    
    # Get the device
    device = session.query(UserDevice).filter_by(id=device_id, user_id=current_user.id).first()
    
    if not device:
        return jsonify({'success': False, 'message': 'Device not found'}), 404
    
    # Unset all defaults
    session.query(UserDevice).filter_by(user_id=current_user.id).update({'is_default': False})
    
    # Set this device as default
    device.is_default = True
    session.commit()
    
    return jsonify({'success': True, 'message': 'Default device updated'})

@app.route('/api/devices/<int:device_id>', methods=['DELETE'])
@login_required
def delete_device(device_id):
    """Delete a saved device"""
    from models import UserDevice
    session = get_session()
    
    device = session.query(UserDevice).filter_by(id=device_id, user_id=current_user.id).first()
    
    if not device:
        return jsonify({'success': False, 'message': 'Device not found'}), 404
    
    session.delete(device)
    session.commit()
    
    return jsonify({'success': True, 'message': 'Device deleted'})

@app.route('/api/deeplink/<int:movie_id>')
@login_required
def api_deeplink(movie_id):
    if not plex_api:
        return jsonify({'success': False, 'message': 'Plex API not available'})
    
    from models import Movie
    session = get_session()
    movie = session.query(Movie).filter_by(id=movie_id).first()
    
    if not movie:
        return jsonify({'success': False, 'message': 'Movie not found'})
    
    deep_link = plex_api.get_movie_deep_link(movie.plex_id)
    if not deep_link:
        return jsonify({'success': False, 'message': 'Could not generate deep link'})
    
    return jsonify({
        'success': True,
        'plex_uri': deep_link['plex_uri'],
        'web_url': deep_link['web_url'],
        'movie_title': movie.title
    })

@app.route('/api/poster/<plex_id>')
@csrf.exempt
def get_poster(plex_id):
    """Proxy and cache Plex movie posters with LRU eviction"""
    
    # Check if image is already cached
    cached_image = image_cache.get(plex_id)
    if cached_image:
        logger.debug(f"Serving cached poster for plex_id: {plex_id}")
        response = make_response(cached_image['data'])
        response.headers['Content-Type'] = cached_image['content_type']
        response.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 days
        return response
    
    # Fetch from Plex
    db_session = get_session()
    settings = db_session.query(Settings).first()
    
    if not settings or not settings.plex_url or not settings.plex_token:
        logger.error("Plex settings not configured")
        abort(404)
    
    # Get movie art/poster URL from database (prefer landscape art)
    movie = db_session.query(Movie).filter_by(plex_id=plex_id).first()
    
    image_url = None
    if movie:
        # Prefer landscape art over portrait poster
        image_url = movie.art_url if movie.art_url else movie.poster_url
    
    if not image_url:
        logger.error(f"No art/poster URL found for plex_id: {plex_id}")
        abort(404)
    
    try:
        # Fetch image from Plex
        plex_response = requests.get(image_url, timeout=10)
        plex_response.raise_for_status()
        
        # Cache the image (with LRU eviction if needed)
        image_data = {
            'data': plex_response.content,
            'content_type': plex_response.headers.get('Content-Type', 'image/jpeg')
        }
        image_cache.set(plex_id, image_data)
        
        logger.info(f"Cached poster for plex_id: {plex_id} ({len(plex_response.content)} bytes, cache size: {len(image_cache.cache)})")
        
        # Return image with cache headers
        flask_response = make_response(plex_response.content)
        flask_response.headers['Content-Type'] = image_data['content_type']
        flask_response.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 days
        return flask_response
        
    except requests.RequestException as e:
        logger.error(f"Failed to fetch poster for plex_id {plex_id}: {e}")
        abort(404)

@app.route('/api/update/check')
@login_required
def check_for_updates():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    from updater import UpdateManager
    from models import AppVersion
    
    session = get_session()
    version_record = session.query(AppVersion).first()
    
    if not version_record:
        version_record = AppVersion(
            current_version=UpdateManager().get_current_version(),
            current_commit=UpdateManager().get_current_version()
        )
        session.add(version_record)
        session.commit()
    
    updater = UpdateManager(github_repo=version_record.github_repo)
    update_info = updater.check_for_updates()
    
    if update_info.get('available'):
        version_record.update_available = True
        version_record.latest_version = update_info['latest_version']
        version_record.last_check_date = datetime.utcnow()
    else:
        version_record.update_available = False
    
    session.commit()
    
    return jsonify({
        'success': True,
        'current_version': update_info.get('current_version', 'unknown'),
        'latest_version': update_info.get('latest_version', 'unknown'),
        'update_available': update_info.get('available', False),
        'commit_message': update_info.get('commit_message'),
        'commit_author': update_info.get('commit_author'),
        'commit_date': update_info.get('commit_date'),
        'error': update_info.get('error'),
        'is_docker': update_info.get('is_docker', False)
    })

@app.route('/api/update/stream')
@login_required
def update_stream():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    from updater import UpdateManager
    from models import AppVersion
    import queue
    import threading
    
    session = get_session()
    version_record = session.query(AppVersion).first()
    github_repo = version_record.github_repo if version_record else 'netpersona/Popcorn'
    
    message_queue = queue.Queue()
    updater = UpdateManager(github_repo=github_repo)
    
    def progress_callback(step, message, progress):
        message_queue.put({
            'step': step,
            'message': message,
            'progress': progress
        })
    
    def perform_update_async():
        try:
            result = updater.perform_update(progress_callback)
            message_queue.put({'done': True, 'result': result})
        except Exception as e:
            message_queue.put({'error': str(e)})
    
    update_thread = threading.Thread(target=perform_update_async)
    update_thread.daemon = True
    update_thread.start()
    
    def generate():
        while True:
            try:
                msg = message_queue.get(timeout=30)
                
                if 'done' in msg:
                    yield f"data: {json.dumps(msg)}\n\n"
                    break
                elif 'error' in msg:
                    yield f"data: {json.dumps(msg)}\n\n"
                    break
                else:
                    yield f"data: {json.dumps(msg)}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
    
    return app.response_class(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

@app.route('/api/update/apply', methods=['POST'])
@login_required
def apply_update():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    from updater import UpdateManager
    from models import AppVersion
    
    session = get_session()
    version_record = session.query(AppVersion).first()
    github_repo = version_record.github_repo if version_record else 'netpersona/Popcorn'
    
    updater = UpdateManager(github_repo=github_repo)
    result = updater.perform_update()
    
    return jsonify(result)

@app.route('/api/themes/upload', methods=['POST'])
@login_required
def upload_theme():
    if 'theme_file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    
    file = request.files['theme_file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    
    try:
        theme_json = file.read().decode('utf-8')
    except Exception as e:
        logging.exception("Failed to read uploaded theme file")
        return jsonify({'success': False, 'message': 'Failed to read file.'}), 400
    
    from theme_service import ThemeService
    is_public = request.form.get('is_public') == 'true' if current_user.is_admin else False
    
    success, error, theme = ThemeService.save_custom_theme(
        user_id=current_user.id,
        theme_json_str=theme_json,
        is_public=is_public
    )
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Theme uploaded successfully',
            'theme': {
                'id': theme.id,
                'name': theme.name,
                'slug': theme.slug
            }
        })
    else:
        return jsonify({'success': False, 'message': error}), 400

@app.route('/api/themes/custom')
@login_required
def get_custom_themes():
    from theme_service import ThemeService
    themes = ThemeService.get_user_custom_themes(current_user.id)
    return jsonify({'success': True, 'themes': themes})

@app.route('/api/themes/<int:theme_id>', methods=['DELETE'])
@login_required
def delete_theme(theme_id):
    from theme_service import ThemeService
    success, error = ThemeService.delete_custom_theme(current_user.id, theme_id)
    
    if success:
        return jsonify({'success': True, 'message': 'Theme deleted successfully'})
    else:
        return jsonify({'success': False, 'message': error}), 400

@app.route('/deeplink/<int:movie_id>')
@login_required
def deeplink(movie_id):
    from theme_service import ThemeService
    
    themes = ThemeService.get_all_themes_for_user(current_user.id)
    
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes.get('plex', {})).get('colors', {})
    
    if not plex_api:
        return render_template('error.html', message="Plex API not available", theme_colors=theme_colors)
    
    from models import Movie
    session = get_session()
    movie = session.query(Movie).filter_by(id=movie_id).first()
    
    if not movie:
        return render_template('error.html', message="Movie not found", theme_colors=theme_colors)
    
    deep_link = plex_api.get_movie_deep_link(movie.plex_id)
    if not deep_link:
        return render_template('error.html', message="Could not generate deep link", theme_colors=theme_colors)
    
    return render_template('deeplink.html',
                         movie_title=movie.title,
                         plex_uri=deep_link['plex_uri'],
                         web_url=deep_link['web_url'],
                         theme_colors=theme_colors)

@app.route('/sync', methods=['POST'])
@login_required
def sync():
    if not current_user.is_admin:
        flash('Only administrators can sync the library', 'error')
        return redirect(url_for('guide'))
    
    sync_movies()
    scheduler.generate_all_schedules(force=True)
    flash('Library synced and schedules regenerated', 'success')
    return redirect(url_for('guide'))

@app.route('/admin/holiday-channels/create', methods=['GET', 'POST'])
@login_required
def create_holiday_channel():
    if not current_user.is_admin:
        flash('Only administrators can access this page', 'error')
        return redirect(url_for('guide'))
    
    from theme_service import ThemeService
    themes = ThemeService.get_all_themes_for_user(current_user.id)
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes.get('plex', {})).get('colors', {})
    
    if request.method == 'POST':
        db = get_session()
        try:
            name = request.form.get('name', '').strip()
            start_month = int(request.form.get('start_month', 1))
            end_month = int(request.form.get('end_month', 1))
            
            if not name:
                flash('Channel name is required', 'error')
                return redirect(url_for('create_holiday_channel'))
            
            if start_month < 1 or start_month > 12 or end_month < 1 or end_month > 12:
                flash('Months must be between 1 and 12', 'error')
                return redirect(url_for('create_holiday_channel'))
            
            existing = db.query(HolidayChannel).filter_by(name=name).first()
            if existing:
                flash('A channel with this name already exists', 'error')
                return redirect(url_for('create_holiday_channel'))
            
            genre_filter = request.form.get('genre_filter', '').strip() or None
            keywords = request.form.get('keywords', '').strip() or None
            filter_mode = request.form.get('filter_mode', 'OR')
            
            rating_filters = request.form.getlist('rating_filter')
            rating_filter = ','.join(rating_filters) if rating_filters else None
            
            tmdb_collection_ids = request.form.get('tmdb_collection_ids', '').strip() or None
            tmdb_keywords = request.form.get('tmdb_keywords', '').strip() or None
            min_rating = request.form.get('min_rating', '').strip()
            min_popularity = request.form.get('min_popularity', '').strip()
            
            channel = HolidayChannel(
                name=name,
                start_month=start_month,
                end_month=end_month,
                genre_filter=genre_filter,
                keywords=keywords,
                rating_filter=rating_filter,
                filter_mode=filter_mode,
                tmdb_collection_ids=tmdb_collection_ids,
                tmdb_keywords=tmdb_keywords,
                min_rating=float(min_rating) if min_rating else None,
                min_popularity=float(min_popularity) if min_popularity else None
            )
            
            db.add(channel)
            db.commit()
            
            scheduler.generate_all_schedules(force=True)
            
            flash(f'Holiday channel "{name}" created successfully', 'success')
            return redirect(url_for('settings') + '#holiday-channels')
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating holiday channel: {e}")
            flash(f'Error creating channel: {str(e)}', 'error')
            return redirect(url_for('create_holiday_channel'))
    
    db = get_session()
    settings_obj = db.query(Settings).first()
    has_tmdb = settings_obj and settings_obj.tmdb_api_key
    
    return render_template('edit_holiday_channel.html', 
                         channel=None,
                         has_tmdb=has_tmdb,
                         theme_colors=theme_colors)

@app.route('/admin/holiday-channels/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_holiday_channel(id):
    if not current_user.is_admin:
        flash('Only administrators can access this page', 'error')
        return redirect(url_for('guide'))
    
    from theme_service import ThemeService
    themes = ThemeService.get_all_themes_for_user(current_user.id)
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes.get('plex', {})).get('colors', {})
    
    db = get_session()
    channel = db.query(HolidayChannel).filter_by(id=id).first()
    
    if not channel:
        flash('Channel not found', 'error')
        return redirect(url_for('settings') + '#holiday-channels')
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            start_month = int(request.form.get('start_month', 1))
            end_month = int(request.form.get('end_month', 1))
            
            if not name:
                flash('Channel name is required', 'error')
                return redirect(url_for('edit_holiday_channel', id=id))
            
            if start_month < 1 or start_month > 12 or end_month < 1 or end_month > 12:
                flash('Months must be between 1 and 12', 'error')
                return redirect(url_for('edit_holiday_channel', id=id))
            
            existing = db.query(HolidayChannel).filter(
                HolidayChannel.name == name,
                HolidayChannel.id != id
            ).first()
            if existing:
                flash('A channel with this name already exists', 'error')
                return redirect(url_for('edit_holiday_channel', id=id))
            
            channel.name = name
            channel.start_month = start_month
            channel.end_month = end_month
            channel.genre_filter = request.form.get('genre_filter', '').strip() or None
            channel.keywords = request.form.get('keywords', '').strip() or None
            channel.filter_mode = request.form.get('filter_mode', 'OR')
            
            rating_filters = request.form.getlist('rating_filter')
            channel.rating_filter = ','.join(rating_filters) if rating_filters else None
            
            channel.tmdb_collection_ids = request.form.get('tmdb_collection_ids', '').strip() or None
            channel.tmdb_keywords = request.form.get('tmdb_keywords', '').strip() or None
            
            min_rating = request.form.get('min_rating', '').strip()
            min_popularity = request.form.get('min_popularity', '').strip()
            channel.min_rating = float(min_rating) if min_rating else None
            channel.min_popularity = float(min_popularity) if min_popularity else None
            
            db.commit()
            
            scheduler.generate_all_schedules(force=True)
            
            flash(f'Holiday channel "{name}" updated successfully', 'success')
            return redirect(url_for('settings') + '#holiday-channels')
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating holiday channel: {e}")
            flash(f'Error updating channel: {str(e)}', 'error')
            return redirect(url_for('edit_holiday_channel', id=id))
    
    settings_obj = db.query(Settings).first()
    has_tmdb = settings_obj and settings_obj.tmdb_api_key
    
    return render_template('edit_holiday_channel.html', 
                         channel=channel,
                         has_tmdb=has_tmdb,
                         theme_colors=theme_colors)

@app.route('/admin/holiday-channels/<int:id>/delete', methods=['POST'])
@login_required
def delete_holiday_channel(id):
    if not current_user.is_admin:
        flash('Only administrators can access this page', 'error')
        return redirect(url_for('guide'))
    
    db = get_session()
    channel = db.query(HolidayChannel).filter_by(id=id).first()
    
    if not channel:
        flash('Channel not found', 'error')
        return redirect(url_for('settings') + '#holiday-channels')
    
    try:
        name = channel.name
        db.delete(channel)
        db.commit()
        
        scheduler.generate_all_schedules(force=True)
        
        flash(f'Holiday channel "{name}" deleted successfully', 'success')
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting holiday channel: {e}")
        flash(f'Error deleting channel: {str(e)}', 'error')
    
    return redirect(url_for('settings') + '#holiday-channels')

@app.route('/admin/holiday-channels/<int:id>/test')
@login_required
def test_holiday_channel(id):
    if not current_user.is_admin:
        flash('Only administrators can access this page', 'error')
        return redirect(url_for('guide'))
    
    from theme_service import ThemeService
    themes = ThemeService.get_all_themes_for_user(current_user.id)
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes.get('plex', {})).get('colors', {})
    
    db = get_session()
    channel = db.query(HolidayChannel).filter_by(id=id).first()
    
    if not channel:
        flash('Channel not found', 'error')
        return redirect(url_for('settings') + '#holiday-channels')
    
    matching_movies = scheduler.get_movies_for_holiday_channel(channel)
    
    overrides = db.query(MovieOverride).filter_by(channel_name=channel.name).all()
    whitelist = [o for o in overrides if o.override_type == 'whitelist']
    blacklist = [o for o in overrides if o.override_type == 'blacklist']
    
    override_map = {}
    for override in overrides:
        override_map[override.movie_id] = override.override_type
    
    return render_template('test_holiday_channel.html',
                         channel=channel,
                         matching_movies=matching_movies,
                         whitelist=whitelist,
                         blacklist=blacklist,
                         override_map=override_map,
                         theme_colors=theme_colors)

@app.route('/admin/holiday-channels/<int:id>/overrides')
@login_required
def get_channel_overrides(id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db = get_session()
    channel = db.query(HolidayChannel).filter_by(id=id).first()
    
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404
    
    overrides = db.query(MovieOverride).filter_by(channel_name=channel.name).all()
    
    result = {
        'whitelist': [],
        'blacklist': []
    }
    
    for override in overrides:
        movie = override.movie
        override_data = {
            'id': override.id,
            'movie_id': movie.id,
            'title': movie.title,
            'year': movie.year,
            'genre': movie.genre
        }
        
        if override.override_type == 'whitelist':
            result['whitelist'].append(override_data)
        else:
            result['blacklist'].append(override_data)
    
    return jsonify(result)

@app.route('/admin/holiday-channels/<int:id>/override/add', methods=['POST'])
@login_required
def add_channel_override(id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db = get_session()
    channel = db.query(HolidayChannel).filter_by(id=id).first()
    
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404
    
    data = request.get_json()
    movie_id = data.get('movie_id')
    override_type = data.get('override_type')
    
    if not movie_id or not override_type:
        return jsonify({'error': 'Missing movie_id or override_type'}), 400
    
    if override_type not in ['whitelist', 'blacklist']:
        return jsonify({'error': 'Invalid override_type. Must be whitelist or blacklist'}), 400
    
    movie = db.query(Movie).filter_by(id=movie_id).first()
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404
    
    try:
        existing = db.query(MovieOverride).filter_by(
            channel_name=channel.name,
            movie_id=movie_id
        ).first()
        
        if existing:
            existing.override_type = override_type
            db.commit()
            logger.info(f"Updated override for movie '{movie.title}' in channel '{channel.name}' to {override_type}")
        else:
            override = MovieOverride(
                channel_name=channel.name,
                movie_id=movie_id,
                override_type=override_type
            )
            db.add(override)
            db.commit()
            logger.info(f"Added {override_type} override for movie '{movie.title}' in channel '{channel.name}'")
        
        scheduler.generate_all_schedules(force=True)
        
        return jsonify({
            'success': True,
            'message': f'Movie {override_type}ed successfully',
            'movie_title': movie.title,
            'override_type': override_type
        })
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding override: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/holiday-channels/<int:id>/override/<int:override_id>/delete', methods=['POST'])
@login_required
def delete_channel_override(id, override_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db = get_session()
    channel = db.query(HolidayChannel).filter_by(id=id).first()
    
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404
    
    override = db.query(MovieOverride).filter_by(
        id=override_id,
        channel_name=channel.name
    ).first()
    
    if not override:
        return jsonify({'error': 'Override not found'}), 404
    
    try:
        movie_title = override.movie.title
        db.delete(override)
        db.commit()
        
        scheduler.generate_all_schedules(force=True)
        
        logger.info(f"Removed override for movie '{movie_title}' from channel '{channel.name}'")
        
        return jsonify({
            'success': True,
            'message': f'Override removed for {movie_title}'
        })
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting override: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/holiday-channels/<int:id>/search-movies')
@login_required
def search_channel_movies(id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db = get_session()
    channel = db.query(HolidayChannel).filter_by(id=id).first()
    
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404
    
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'movies': []})
    
    matching_movies = scheduler.get_movies_for_holiday_channel(channel)
    matching_movie_ids = {movie.id for movie in matching_movies}
    
    query_lower = query.lower()
    movies = db.query(Movie).filter(
        Movie.title.ilike(f'%{query}%')
    ).limit(50).all()
    
    results = []
    for movie in movies:
        results.append({
            'id': movie.id,
            'title': movie.title,
            'year': movie.year,
            'rating': movie.rating,
            'genre': movie.genre,
            'matches_filter': movie.id in matching_movie_ids
        })
    
    return jsonify({'movies': results})

@app.route('/admin/holiday-channels/<int:id>/suggest-filters', methods=['POST'])
@login_required
def suggest_channel_filters(id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db = get_session()
    channel = db.query(HolidayChannel).filter_by(id=id).first()
    
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404
    
    data = request.get_json()
    movie_id = data.get('movie_id')
    
    if not movie_id:
        return jsonify({'error': 'Missing movie_id'}), 400
    
    movie = db.query(Movie).filter_by(id=movie_id).first()
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404
    
    suggestions = []
    
    existing_genres = set()
    if channel.genre_filter:
        existing_genres = {g.strip().lower() for g in channel.genre_filter.split(',') if g.strip()}
    
    existing_keywords = set()
    if channel.keywords:
        existing_keywords = {k.strip().lower() for k in channel.keywords.split(',') if k.strip()}
    
    movie_genres = [g.strip() for g in movie.genre.split(',') if g.strip()]
    for genre in movie_genres:
        genre_lower = genre.lower()
        if genre_lower not in existing_genres:
            suggestions.append({
                'type': 'genre',
                'value': genre,
                'label': f"Add '{genre}' to genre filter"
            })
    
    import re
    title_words = re.findall(r'\b[a-z]{4,}\b', movie.title.lower())
    common_words = {'with', 'from', 'that', 'this', 'have', 'been', 'were', 'when', 'what', 'where', 'which', 'their', 'there'}
    title_words = [w for w in title_words if w not in common_words and w not in existing_keywords]
    
    for word in title_words[:3]:
        suggestions.append({
            'type': 'keyword',
            'value': word,
            'label': f"Add '{word}' keyword from title"
        })
    
    if movie.summary:
        summary_words = re.findall(r'\b[a-z]{5,}\b', movie.summary.lower())
        summary_words = [w for w in summary_words if w not in common_words and w not in existing_keywords and w not in title_words]
        
        for word in summary_words[:2]:
            suggestions.append({
                'type': 'keyword',
                'value': word,
                'label': f"Add '{word}' keyword from summary"
            })
    
    suggestions = suggestions[:5]
    
    return jsonify({'suggestions': suggestions})

@app.route('/admin/holiday-channels/<int:id>/apply-suggestions', methods=['POST'])
@login_required
def apply_channel_suggestions(id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db = get_session()
    channel = db.query(HolidayChannel).filter_by(id=id).first()
    
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404
    
    data = request.get_json()
    suggestions = data.get('suggestions', [])
    
    if not suggestions:
        return jsonify({'error': 'No suggestions provided'}), 400
    
    try:
        existing_genres = set()
        if channel.genre_filter:
            existing_genres = {g.strip().lower() for g in channel.genre_filter.split(',') if g.strip()}
        
        existing_keywords = set()
        if channel.keywords:
            existing_keywords = {k.strip().lower() for k in channel.keywords.split(',') if k.strip()}
        
        new_genres = []
        new_keywords = []
        
        for suggestion in suggestions:
            suggestion_type = suggestion.get('type')
            value = suggestion.get('value', '').strip()
            
            if not value:
                continue
            
            if suggestion_type == 'genre':
                value_lower = value.lower()
                if value_lower not in existing_genres:
                    new_genres.append(value)
                    existing_genres.add(value_lower)
            elif suggestion_type == 'keyword':
                value_lower = value.lower()
                if value_lower not in existing_keywords:
                    new_keywords.append(value)
                    existing_keywords.add(value_lower)
        
        if new_genres:
            if channel.genre_filter:
                channel.genre_filter = channel.genre_filter + ',' + ','.join(new_genres)
            else:
                channel.genre_filter = ','.join(new_genres)
            logger.info(f"Added genres to channel '{channel.name}': {', '.join(new_genres)}")
        
        if new_keywords:
            if channel.keywords:
                channel.keywords = channel.keywords + ',' + ','.join(new_keywords)
            else:
                channel.keywords = ','.join(new_keywords)
            logger.info(f"Added keywords to channel '{channel.name}': {', '.join(new_keywords)}")
        
        db.commit()
        
        scheduler.generate_all_schedules(force=True)
        
        return jsonify({
            'success': True,
            'message': f'Applied {len(new_genres)} genre(s) and {len(new_keywords)} keyword(s) to channel filters',
            'genres_added': new_genres,
            'keywords_added': new_keywords
        })
    except Exception as e:
        db.rollback()
        logger.error(f"Error applying suggestions: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    initialize_app()
    app.run(host='0.0.0.0', port=5000, debug=False)
