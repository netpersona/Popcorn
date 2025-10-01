import os
from flask import Flask, render_template, jsonify, request, redirect, url_for
from dotenv import load_dotenv
from models import init_db, get_session, Settings
from plex_api import PlexAPI
from scheduler import ScheduleGenerator
import logging
from datetime import datetime

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

app = Flask(__name__)
app.secret_key = os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production')

db_session = None
plex_api = None
scheduler = None

def initialize_app():
    global db_session, plex_api, scheduler
    
    logger.info("Initializing Popcorn app...")
    
    db_session = init_db()
    logger.info("Database initialized")
    
    try:
        plex_api = PlexAPI()
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
                    summary=data['summary']
                )
                session.add(movie)
                new_count += 1
    
    session.commit()
    logger.info(f"Added {new_count} new movie entries to database")

@app.route('/')
def index():
    return redirect(url_for('guide'))

@app.route('/guide')
def guide():
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
    
    return render_template('guide.html', 
                         channels=guide_data, 
                         current_minutes=current_minutes)

@app.route('/channels')
def channels_list():
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
    
    return render_template('index.html', channels=channel_info)

@app.route('/channel/<channel_name>')
def channel(channel_name):
    if not scheduler:
        return render_template('error.html', message="Application not initialized")
    
    current = scheduler.get_current_playing(channel_name)
    schedule = scheduler.get_channel_schedule(channel_name)
    
    return render_template('channel.html', 
                         channel_name=channel_name,
                         current=current,
                         schedule=schedule)

@app.route('/play/<int:movie_id>')
def play(movie_id):
    if not plex_api:
        return jsonify({'success': False, 'message': 'Plex API not available'})
    
    from models import Movie
    session = get_session()
    movie = session.query(Movie).filter_by(id=movie_id).first()
    
    if not movie:
        return jsonify({'success': False, 'message': 'Movie not found'})
    
    success, message = plex_api.play_movie(movie.plex_id)
    return jsonify({'success': success, 'message': message})

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    session = get_session()
    settings_obj = session.query(Settings).first()
    
    if not settings_obj:
        settings_obj = Settings(shuffle_frequency='weekly')
        session.add(settings_obj)
        session.commit()
    
    if request.method == 'POST':
        frequency = request.form.get('shuffle_frequency')
        if frequency in ['daily', 'weekly', 'monthly']:
            settings_obj.shuffle_frequency = frequency
            session.commit()
            
            if request.form.get('reshuffle_now'):
                scheduler.generate_all_schedules(force=True)
                return redirect(url_for('settings', reshuffled=1))
        
        return redirect(url_for('settings'))
    
    reshuffled = request.args.get('reshuffled')
    return render_template('settings.html', settings=settings_obj, reshuffled=reshuffled)

@app.route('/api/clients')
def get_clients():
    if not plex_api:
        return jsonify({'success': False, 'clients': []})
    
    clients = plex_api.get_available_clients()
    return jsonify({'success': True, 'clients': clients})

@app.route('/api/deeplink/<int:movie_id>')
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

@app.route('/sync')
def sync():
    sync_movies()
    scheduler.generate_all_schedules(force=True)
    return redirect(url_for('index'))

if __name__ == '__main__':
    initialize_app()
    app.run(host='0.0.0.0', port=5000, debug=False)
