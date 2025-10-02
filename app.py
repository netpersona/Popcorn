import os
import sys
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from models import init_db, get_session, Settings, User
from plex_api import PlexAPI
from scheduler import ScheduleGenerator
from auth import PlexOAuth, create_or_update_plex_user
from user_management import user_mgmt_bp, validate_invite_code, mark_invite_used
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

app = Flask(__name__)

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

def initialize_app():
    global db_session, plex_api, scheduler
    
    logger.info("Initializing Popcorn app...")
    
    db_session = init_db()
    logger.info("Database initialized")
    
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
                    summary=data['summary'],
                    poster_url=data.get('poster_url')
                )
                session.add(movie)
                new_count += 1
            else:
                existing_movie = session.query(Movie).filter_by(plex_id=data['plex_id'], genre=genre).first()
                if existing_movie and existing_movie.poster_url != data.get('poster_url'):
                    existing_movie.poster_url = data.get('poster_url')
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
    return redirect(auth_data['auth_url'])

@app.route('/auth/plex/callback')
@csrf.exempt
def plex_callback():
    pin_id = session.get('plex_pin_id')
    
    if not pin_id:
        flash('Invalid authentication request', 'error')
        return redirect(url_for('login'))
    
    plex_oauth = PlexOAuth()
    auth_token = plex_oauth.check_pin(pin_id)
    
    if not auth_token:
        flash('Plex authentication failed or pending', 'error')
        return redirect(url_for('login'))
    
    user_info = plex_oauth.get_user_info(auth_token)
    
    if not user_info:
        flash('Failed to get Plex user information', 'error')
        return redirect(url_for('login'))
    
    db_session = get_session()
    user = create_or_update_plex_user(user_info, auth_token, db_session)
    
    if user:
        login_user(user, remember=True)
        session.pop('plex_pin_id', None)
        flash(f'Welcome, {user.display_name}!', 'success')
        return redirect(url_for('guide'))
    
    flash('Failed to create user account', 'error')
    return redirect(url_for('login'))

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
    import json
    
    with open('themes.json', 'r') as f:
        themes = json.load(f)
    
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
    theme_colors = themes.get(user_theme, themes['plex'])['colors']
    
    return render_template('profile.html', themes=themes, theme_colors=theme_colors)

@app.route('/')
@login_required
def index():
    return redirect(url_for('guide'))

@app.route('/guide')
@login_required
def guide():
    import json
    
    if not scheduler:
        return render_template('error.html', message="Application not initialized")
    
    channels = scheduler.get_all_channels()
    
    guide_data = []
    for channel in channels:
        schedule = scheduler.get_channel_schedule(channel)
        programs = []
        
        for item in schedule:
            start_min = time_to_minutes(item.start_time)
            end_min = time_to_minutes(item.end_time)
            duration_min = end_min - start_min if end_min > start_min else (1440 - start_min + end_min)
            
            programs.append({
                'movie': item.movie,
                'start_time': item.start_time,
                'end_time': item.end_time,
                'start_minute': start_min,
                'duration_minutes': duration_min
            })
        
        guide_data.append({
            'name': channel,
            'programs': programs
        })
    
    current_minutes = get_current_minutes()
    
    session = get_session()
    settings_obj = session.query(Settings).first()
    enable_time_offset = settings_obj.enable_time_offset if settings_obj else True
    
    with open('themes.json', 'r') as f:
        themes = json.load(f)
    
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes['plex'])['colors']
    
    return render_template('guide.html', 
                         channels=guide_data, 
                         current_minutes=current_minutes,
                         enable_time_offset=enable_time_offset,
                         theme_colors=theme_colors)

@app.route('/channels')
@login_required
def channels_list():
    import json
    
    if not scheduler:
        return render_template('error.html', message="Application not initialized")
    
    channels = scheduler.get_all_channels()
    
    channel_info = []
    for channel in channels:
        current = scheduler.get_current_playing(channel)
        channel_info.append({
            'name': channel,
            'current': current.movie if current else None
        })
    
    with open('themes.json', 'r') as f:
        themes = json.load(f)
    
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes['plex'])['colors']
    
    return render_template('index.html', channels=channel_info, theme_colors=theme_colors)

@app.route('/channel/<channel_name>')
@login_required
def channel(channel_name):
    if not scheduler:
        return render_template('error.html', message="Application not initialized")
    
    current = scheduler.get_current_playing(channel_name)
    schedule = scheduler.get_channel_schedule(channel_name)
    
    return render_template('channel.html', 
                         channel_name=channel_name,
                         current=current,
                         schedule=schedule)

@app.route('/play/<int:movie_id>', methods=['POST'])
@login_required
def play(movie_id):
    if not plex_api:
        return jsonify({'success': False, 'message': 'Plex API not available'})
    
    from models import Movie, Settings
    session = get_session()
    movie = session.query(Movie).filter_by(id=movie_id).first()
    
    if not movie:
        return jsonify({'success': False, 'message': 'Movie not found'})
    
    settings_obj = session.query(Settings).first()
    playback_mode = settings_obj.playback_mode if settings_obj else 'web_player'
    
    offset_ms = request.json.get('offset_ms', 0) if request.is_json else 0
    
    success, result, offset_min = plex_api.play_movie(movie.plex_id, offset_ms=offset_ms, playback_mode=playback_mode)
    
    if success and playback_mode == 'web_player':
        message = f"Opening movie in browser" + (f" (starting at {offset_min} min)" if offset_min > 0 else "")
        return jsonify({'success': True, 'message': message, 'web_url': result, 'offset_min': offset_min})
    else:
        return jsonify({'success': success, 'message': result, 'offset_min': offset_min if success else 0})

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
            settings_obj.plex_client = request.form.get('plex_client', '').strip() or None
            session.commit()
            
            try:
                plex_api = PlexAPI(db_settings=settings_obj)
                logger.info("Plex API reconnected with new settings")
                
                sync_movies()
                
                movie_count = session.query(Movie).count()
                flash(f'Plex connected successfully! Synced {movie_count} movies.', 'success')
                return redirect(url_for('settings', plex_saved=1))
            except Exception as e:
                logger.error(f"Failed to connect to Plex with new settings: {e}")
                plex_api = None
                flash(f'Settings saved, but connection failed: {str(e)}', 'error')
                return redirect(url_for('settings', plex_error=1))
        elif 'playback_mode' in request.form:
            playback_mode = request.form.get('playback_mode')
            if playback_mode in ['web_player', 'client']:
                settings_obj.playback_mode = playback_mode
            
            settings_obj.enable_time_offset = 'enable_time_offset' in request.form
            session.commit()
            
            flash('Playback settings saved successfully!', 'success')
            return redirect(url_for('settings'))
        else:
            frequency = request.form.get('shuffle_frequency')
            if frequency in ['daily', 'weekly', 'monthly']:
                settings_obj.shuffle_frequency = frequency
                session.commit()
                
                if request.form.get('reshuffle_now'):
                    scheduler.generate_all_schedules(force=True)
                    return redirect(url_for('settings', reshuffled=1))
            
            return redirect(url_for('settings'))
    
    reshuffled = request.args.get('reshuffled')
    plex_saved = request.args.get('plex_saved')
    
    import json
    with open('themes.json', 'r') as f:
        themes = json.load(f)
    
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes['plex'])['colors']
    
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

@app.route('/deeplink/<int:movie_id>')
@login_required
def deeplink(movie_id):
    if not plex_api:
        return render_template('error.html', message="Plex API not available")
    
    from models import Movie
    session = get_session()
    movie = session.query(Movie).filter_by(id=movie_id).first()
    
    if not movie:
        return render_template('error.html', message="Movie not found")
    
    deep_link = plex_api.get_movie_deep_link(movie.plex_id)
    if not deep_link:
        return render_template('error.html', message="Could not generate deep link")
    
    return render_template('deeplink.html',
                         movie_title=movie.title,
                         plex_uri=deep_link['plex_uri'],
                         web_url=deep_link['web_url'])

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
