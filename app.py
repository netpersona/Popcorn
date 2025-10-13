import os
import sys
import json
import queue
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, abort, send_file, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from models import init_db, get_session, Settings, User, Movie
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
    
    logger.info("Running database migrations...")
    conn = sqlite3.connect('popcorn.db')
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
        ('art_url', 'VARCHAR')
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
    movie_data = plex_api.fetch_movies()
    
    from models import Movie
    session = get_session()
    
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
                    cast=data.get('cast')
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
    
    # Get configured Plex URL from settings
    settings = db_session.query(Settings).first()
    if not settings or not settings.plex_url:
        return jsonify({
            'success': False,
            'status': 'error',
            'message': 'Plex server not configured. Contact administrator.'
        })
    
    # Verify user has library access
    from plex_api import PlexAPI
    has_access, error_msg = PlexAPI.verify_library_access(settings.plex_url, auth_token)
    
    if not has_access:
        return jsonify({
            'success': False,
            'status': 'no_library_access',
            'message': f'You do not have access to this Plex server. {error_msg or ""}'
        })
    
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
    
    # Use user's playback preferences
    playback_mode = current_user.playback_mode if current_user.playback_mode else 'web_player'
    client_id = current_user.plex_client if current_user.plex_client else None
    
    offset_ms = request.json.get('offset_ms', 0) if request.is_json else 0
    
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
    
    session = get_session()
    settings_obj = session.query(Settings).first()
    
    if not settings_obj:
        settings_obj = Settings(shuffle_frequency='weekly')
        session.add(settings_obj)
        session.commit()
    
    if request.method == 'POST':
        if 'plex_url' in request.form:
            global plex_api
            
            settings_obj.plex_url = request.form.get('plex_url', '').strip() or None
            settings_obj.plex_token = request.form.get('plex_token', '').strip() or None
            # plex_client is now per-user setting, not admin setting
            session.commit()
            
            try:
                plex_api = PlexAPI(db_settings=settings_obj)
                logger.info("Plex API reconnected with new settings")
                
                sync_movies()
                scheduler.generate_all_schedules(force=True)
                
                movie_count = session.query(Movie).count()
                flash(f'Plex connected successfully! Synced {movie_count} movies and generated schedules.', 'success')
                return redirect(url_for('settings', plex_saved=1))
            except Exception as e:
                logger.error(f"Failed to connect to Plex with new settings: {e}")
                plex_api = None
                flash(f'Settings saved, but connection failed: {str(e)}', 'error')
                return redirect(url_for('settings', plex_error=1))
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
            
            session.commit()
            
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
    
    return render_template('settings.html', settings=settings_obj, reshuffled=reshuffled, plex_saved=plex_saved, theme_colors=theme_colors)

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
        return jsonify({
            'success': False,
            'message': f'Connection failed: {str(e)}'
        })

@app.route('/api/clients')
@login_required
def get_clients():
    if not plex_api:
        return jsonify({'success': False, 'clients': []})
    
    clients = plex_api.get_available_clients()
    return jsonify({'success': True, 'clients': clients})

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
            current_version='1.0.0',
            current_commit=UpdateManager().get_current_commit()
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
        return jsonify({'success': False, 'message': f'Failed to read file: {str(e)}'}), 400
    
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

if __name__ == '__main__':
    initialize_app()
    app.run(host='0.0.0.0', port=5000, debug=False)
