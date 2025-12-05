from datetime import datetime, timedelta, date
import random
import logging
import re
from models import Movie, Schedule, HolidayChannel, Settings, MovieOverride, get_session
from tmdb_api import TMDBAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScheduleGenerator:
    def __init__(self, db_path=None):
        from models import get_db_path
        if db_path is None:
            db_path = get_db_path()
        self.session = get_session(db_path)
        self.initialize_holiday_channels()
    
    def migrate_holiday_channels_schema(self):
        from sqlalchemy import inspect, text
        inspector = inspect(self.session.bind)
        columns = [col['name'] for col in inspector.get_columns('holiday_channels')]
        
        if 'genre_filter' not in columns:
            logger.info("Migrating holiday_channels table: adding genre_filter column")
            self.session.execute(text('ALTER TABLE holiday_channels ADD COLUMN genre_filter TEXT'))
            self.session.commit()
        
        if 'filter_mode' not in columns:
            logger.info("Migrating holiday_channels table: adding filter_mode column")
            self.session.execute(text('ALTER TABLE holiday_channels ADD COLUMN filter_mode TEXT DEFAULT "AND"'))
            self.session.execute(text('UPDATE holiday_channels SET filter_mode = "AND" WHERE filter_mode IS NULL'))
            self.session.commit()
        
        if 'tmdb_collection_ids' not in columns:
            logger.info("Migrating holiday_channels table: adding tmdb_collection_ids column")
            self.session.execute(text('ALTER TABLE holiday_channels ADD COLUMN tmdb_collection_ids TEXT'))
            self.session.commit()
        
        if 'tmdb_keywords' not in columns:
            logger.info("Migrating holiday_channels table: adding tmdb_keywords column")
            self.session.execute(text('ALTER TABLE holiday_channels ADD COLUMN tmdb_keywords TEXT'))
            self.session.commit()
        
        if 'min_rating' not in columns:
            logger.info("Migrating holiday_channels table: adding min_rating column")
            self.session.execute(text('ALTER TABLE holiday_channels ADD COLUMN min_rating REAL'))
            self.session.commit()
        
        if 'min_popularity' not in columns:
            logger.info("Migrating holiday_channels table: adding min_popularity column")
            self.session.execute(text('ALTER TABLE holiday_channels ADD COLUMN min_popularity REAL'))
            self.session.commit()
    
    def upgrade_holiday_channel_defaults(self):
        """
        Upgrade existing holiday channels with improved keywords and AND filter mode.
        This is called for existing installations to ensure they get the latest improvements.
        """
        from sqlalchemy import text
        
        # Define the improved channel configurations
        channel_upgrades = {
            'Cozy Halloween': {
                'keywords': 'halloween,hocus pocus,casper,ghostbusters,addams family,beetlejuice,nightmare before christmas,corpse bride,frankenweenie,coraline,paranorman,goosebumps',
                'filter_mode': 'AND',
                'tmdb_keywords': '3335',
                'min_rating': 6.0
            },
            'Scary Halloween': {
                'keywords': 'halloween,scream,nightmare on elm street,friday the 13th,evil dead,saw,conjuring,insidious,paranormal activity,exorcist,the ring,the grudge,slasher',
                'filter_mode': 'AND',
                'tmdb_collection_ids': '91361,9735,8581',
                'tmdb_keywords': '3335',
                'min_rating': 5.5
            },
            'Christmas': {
                'keywords': 'christmas,xmas,santa claus,grinch,miracle on 34th street,wonderful life,home alone,polar express,jingle all the way,carol,noel,nutcracker,scrooge',
                'genre_filter': 'comedy,family,drama,animation,fantasy,romance',
                'filter_mode': 'AND',
                'tmdb_collection_ids': '9888,53159',
                'tmdb_keywords': '207317,260365,189966',
                'min_rating': 6.0
            }
        }
        
        # Update each existing channel
        for channel_name, upgrades in channel_upgrades.items():
            existing_channel = self.session.query(HolidayChannel).filter_by(name=channel_name).first()
            if existing_channel:
                existing_channel.keywords = upgrades['keywords']
                existing_channel.filter_mode = upgrades['filter_mode']
                if 'genre_filter' in upgrades:
                    existing_channel.genre_filter = upgrades['genre_filter']
                if 'tmdb_collection_ids' in upgrades and not existing_channel.tmdb_collection_ids:
                    existing_channel.tmdb_collection_ids = upgrades['tmdb_collection_ids']
                if 'tmdb_keywords' in upgrades and not existing_channel.tmdb_keywords:
                    existing_channel.tmdb_keywords = upgrades['tmdb_keywords']
                if 'min_rating' in upgrades and not existing_channel.min_rating:
                    existing_channel.min_rating = upgrades['min_rating']
                logger.info(f"Upgraded holiday channel '{channel_name}' with improved filters and TMDB defaults")
        
        self.session.commit()
    
    def initialize_holiday_channels(self):
        self.migrate_holiday_channels_schema()
        
        existing = self.session.query(HolidayChannel).count()
        if existing > 0:
            self.upgrade_holiday_channel_defaults()
            return
        
        holiday_channels = [
            {
                'name': 'Cozy Halloween',
                'start_month': 9,
                'end_month': 11,
                'genre_filter': 'animation,family,fantasy',
                'keywords': 'halloween,hocus pocus,casper,ghostbusters,addams family,beetlejuice,nightmare before christmas,corpse bride,frankenweenie,coraline,paranorman,goosebumps',
                'rating_filter': 'G,PG,PG-13',
                'filter_mode': 'AND',
                'tmdb_keywords': '3335',
                'min_rating': 6.0
            },
            {
                'name': 'Scary Halloween',
                'start_month': 9,
                'end_month': 11,
                'genre_filter': 'horror,thriller',
                'keywords': 'halloween,scream,nightmare on elm street,friday the 13th,evil dead,saw,conjuring,insidious,paranormal activity,exorcist,the ring,the grudge,slasher',
                'rating_filter': 'PG-13,R,NR,Not Rated,Unrated',
                'filter_mode': 'AND',
                'tmdb_collection_ids': '91361,9735,8581',
                'tmdb_keywords': '3335',
                'min_rating': 5.5
            },
            {
                'name': 'Christmas',
                'start_month': 11,
                'end_month': 1,
                'genre_filter': 'comedy,family,drama,animation,fantasy,romance',
                'keywords': 'christmas,xmas,santa claus,grinch,miracle on 34th street,wonderful life,home alone,polar express,jingle all the way,carol,noel,nutcracker,scrooge',
                'rating_filter': None,
                'filter_mode': 'AND',
                'tmdb_collection_ids': '9888,53159',
                'tmdb_keywords': '207317,260365,189966',
                'min_rating': 6.0
            }
        ]
        
        for channel_data in holiday_channels:
            channel = HolidayChannel(**channel_data)
            self.session.add(channel)
        
        self.session.commit()
        logger.info("Initialized holiday channels with improved filtering")
    
    def get_active_holiday_channels(self):
        current_month = datetime.now().month
        holiday_channels = self.session.query(HolidayChannel).all()
        active = []
        
        for channel in holiday_channels:
            if channel.start_month <= channel.end_month:
                if channel.start_month <= current_month <= channel.end_month:
                    active.append(channel)
            else:
                if current_month >= channel.start_month or current_month <= channel.end_month:
                    active.append(channel)
        
        return active
    
    def get_movies_for_holiday_channel(self, channel):
        """
        Filter movies for a holiday channel with improved logic.
        
        Priority:
        1. Check MovieOverride table (blacklist excludes, whitelist includes immediately)
        2. Use word boundary regex for keyword matching
        3. Support filter_mode: 'AND' or 'OR'
        4. Integrate TMDB if api_key exists
        5. Return movies with detailed match reasons
        """
        movies = self.session.query(Movie).all()
        matching_movies = []
        
        # Get all overrides for this channel
        overrides = self.session.query(MovieOverride).filter_by(channel_name=channel.name).all()
        blacklist_ids = {o.movie_id for o in overrides if o.override_type == 'blacklist'}
        whitelist_ids = {o.movie_id for o in overrides if o.override_type == 'whitelist'}
        
        # Get TMDB API if available
        settings = self.session.query(Settings).first()
        tmdb = None
        if settings and settings.tmdb_api_key:
            tmdb = TMDBAPI(settings.tmdb_api_key)
        
        # Parse channel filters
        genre_filters = []
        if channel.genre_filter:
            genre_filters = [g.strip().lower() for g in channel.genre_filter.split(',')]
        
        keywords = []
        if channel.keywords:
            keywords = [k.strip().lower() for k in channel.keywords.split(',')]
        
        # Parse TMDB filters
        tmdb_collection_ids = []
        if channel.tmdb_collection_ids:
            tmdb_collection_ids = [int(id.strip()) for id in channel.tmdb_collection_ids.split(',') if id.strip().isdigit()]
        
        tmdb_keywords = []
        if channel.tmdb_keywords:
            tmdb_keywords = [k.strip().lower() for k in channel.tmdb_keywords.split(',')]
        
        filter_mode = channel.filter_mode if channel.filter_mode else 'OR'
        
        for movie in movies:
            # Check blacklist first - skip if blacklisted
            if movie.id in blacklist_ids:
                logger.debug(f"Movie '{movie.title}' blacklisted for channel '{channel.name}'")
                continue
            
            # Check whitelist - include immediately if whitelisted
            if movie.id in whitelist_ids:
                logger.debug(f"Movie '{movie.title}' whitelisted for channel '{channel.name}'")
                matching_movies.append(movie)
                continue
            
            # Prepare text for matching
            movie_genre_lower = movie.genre.lower()
            title_lower = movie.title.lower()
            summary_lower = movie.summary.lower() if movie.summary else ''
            
            # Genre matching
            genre_match = False
            if genre_filters:
                genre_match = any(genre_filter in movie_genre_lower for genre_filter in genre_filters)
            
            # Keyword matching with word boundaries
            keyword_match = False
            matched_keywords = []
            if keywords:
                for keyword in keywords:
                    # Use word boundary regex to avoid partial matches
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    if re.search(pattern, title_lower, re.IGNORECASE) or re.search(pattern, summary_lower, re.IGNORECASE):
                        keyword_match = True
                        matched_keywords.append(keyword)
                        break
            
            # TMDB integration (optional)
            tmdb_match = False
            if tmdb and movie.year:
                try:
                    tmdb_data = tmdb.get_movie_by_plex_metadata(movie.title, movie.year)
                    if tmdb_data:
                        # Check TMDB collections
                        if tmdb_collection_ids and tmdb_data.get('belongs_to_collection'):
                            collection_id = tmdb_data['belongs_to_collection'].get('id')
                            if collection_id in tmdb_collection_ids:
                                tmdb_match = True
                        
                        # Check TMDB keywords
                        if tmdb_keywords and tmdb_data.get('tmdb_keywords'):
                            if any(kw in tmdb_data['tmdb_keywords'] for kw in tmdb_keywords):
                                tmdb_match = True
                        
                        # Check min_rating
                        if channel.min_rating and tmdb_data.get('vote_average'):
                            if tmdb_data['vote_average'] < channel.min_rating:
                                continue
                        
                        # Check min_popularity
                        if channel.min_popularity and tmdb_data.get('popularity'):
                            if tmdb_data['popularity'] < channel.min_popularity:
                                continue
                except Exception as e:
                    logger.debug(f"TMDB lookup failed for '{movie.title}': {e}")
            
            # Apply filter mode logic
            matched = False
            if filter_mode == 'AND':
                # Both genre AND keyword must match
                matched = genre_match and keyword_match
            else:
                # Either genre OR keyword can match
                matched = genre_match or keyword_match
            
            # Include TMDB match in OR logic
            if tmdb_match:
                matched = True
            
            # Apply rating filter if matched
            if matched:
                if channel.rating_filter:
                    allowed_ratings = [r.strip().upper() for r in channel.rating_filter.split(',')]
                    movie_rating_upper = movie.rating.upper() if movie.rating else ''
                    if movie_rating_upper in allowed_ratings or not movie.rating:
                        matching_movies.append(movie)
                        logger.debug(f"Movie '{movie.title}' matched for '{channel.name}' - Genre: {genre_match}, Keyword: {keyword_match}, TMDB: {tmdb_match}")
                else:
                    matching_movies.append(movie)
                    logger.debug(f"Movie '{movie.title}' matched for '{channel.name}' - Genre: {genre_match}, Keyword: {keyword_match}, TMDB: {tmdb_match}")
        
        logger.info(f"Found {len(matching_movies)} movies for holiday channel '{channel.name}' (filter_mode: {filter_mode})")
        return matching_movies
    
    def generate_channel_schedule(self, channel_name, movies, day=0):
        if not movies:
            logger.warning(f"No movies available for channel: {channel_name}")
            return
        
        valid_movies = [m for m in movies if m.duration > 0]
        if not valid_movies:
            logger.warning(f"No valid movies (duration > 0) for channel: {channel_name}")
            return
        
        self.session.query(Schedule).filter_by(channel=channel_name, day=day).delete()
        
        random.shuffle(valid_movies)
        
        current_time = 0
        movie_index = 0
        
        while current_time < 1440:
            movie = valid_movies[movie_index % len(valid_movies)]
            
            if movie.duration <= 0:
                logger.error(f"Movie {movie.title} has invalid duration {movie.duration}, skipping")
                movie_index += 1
                continue
            
            start_minutes = current_time
            end_minutes = current_time + movie.duration
            
            if end_minutes > 1440:
                end_minutes = 1440
            
            start_time = f"{start_minutes // 60:02d}:{start_minutes % 60:02d}"
            end_time = f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"
            
            schedule_entry = Schedule(
                channel=channel_name,
                movie_id=movie.id,
                start_time=start_time,
                end_time=end_time,
                day=day
            )
            self.session.add(schedule_entry)
            
            current_time = end_minutes
            movie_index += 1
        
        self.session.commit()
        logger.info(f"Generated schedule for channel: {channel_name} (day {day})")
    
    def generate_all_schedules(self, force=False):
        try:
            settings = self.session.query(Settings).first()
            is_first_run = False
            
            if not settings:
                settings = Settings(shuffle_frequency='weekly', last_shuffle_date=None)
                self.session.add(settings)
                self.session.commit()
                is_first_run = True
            
            if not force and not is_first_run and settings.last_shuffle_date:
                days_since_shuffle = (date.today() - settings.last_shuffle_date).days
                
                if settings.shuffle_frequency == 'daily' and days_since_shuffle < 1:
                    logger.info("Schedules already generated today")
                    return
                elif settings.shuffle_frequency == 'weekly' and days_since_shuffle < 7:
                    logger.info("Schedules generated within the past week")
                    return
                elif settings.shuffle_frequency == 'monthly' and days_since_shuffle < 30:
                    logger.info("Schedules generated within the past month")
                    return
            
            logger.info("Generating fresh schedules for all channels and all 7 days")
            
            self.session.query(Schedule).delete()
            self.session.commit()
            
            genre_movies = {}
            movies = self.session.query(Movie).all()
            
            for movie in movies:
                if movie.genre not in genre_movies:
                    genre_movies[movie.genre] = []
                genre_movies[movie.genre].append(movie)
            
            channels_generated = 0
            errors_encountered = 0
            
            for day in range(7):
                try:
                    for genre, genre_movie_list in genre_movies.items():
                        try:
                            self.generate_channel_schedule(genre, genre_movie_list, day=day)
                            channels_generated += 1
                        except Exception as e:
                            logger.error(f"Failed to generate schedule for {genre} on day {day}: {e}", exc_info=True)
                            errors_encountered += 1
                            continue
                    
                    try:
                        active_holidays = self.get_active_holiday_channels()
                        for holiday_channel in active_holidays:
                            try:
                                holiday_movies = self.get_movies_for_holiday_channel(holiday_channel)
                                if holiday_movies:
                                    self.generate_channel_schedule(holiday_channel.name, holiday_movies, day=day)
                                    channels_generated += 1
                            except Exception as e:
                                logger.error(f"Failed to generate holiday schedule for {holiday_channel.name} on day {day}: {e}", exc_info=True)
                                errors_encountered += 1
                                continue
                    except Exception as e:
                        logger.error(f"Failed to process holiday channels for day {day}: {e}", exc_info=True)
                        errors_encountered += 1
                
                except Exception as e:
                    logger.error(f"Failed to generate schedules for day {day}: {e}", exc_info=True)
                    errors_encountered += 1
                    continue
            
            settings.last_shuffle_date = date.today()
            self.session.commit()
            
            if errors_encountered > 0:
                logger.warning(f"Schedule generation completed with {errors_encountered} errors. Generated {channels_generated} channel schedules across 7 days.")
            else:
                logger.info(f"All schedules generated successfully: {channels_generated} channel schedules across 7 days")
                
        except Exception as e:
            logger.error(f"Critical error during schedule generation: {e}", exc_info=True)
            try:
                self.session.rollback()
            except Exception:
                pass
            raise
    
    def get_current_playing(self, channel):
        now = datetime.now()
        current_time = f"{now.hour:02d}:{now.minute:02d}"
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        
        schedules = self.session.query(Schedule).filter_by(
            channel=channel, 
            day=current_day
        ).order_by(Schedule.start_time).all()
        
        for schedule in schedules:
            if schedule.start_time <= current_time < schedule.end_time:
                return schedule
        
        return schedules[0] if schedules else None
    
    def get_channel_schedule(self, channel, day=None):
        if day is None:
            day = datetime.now().weekday()  # Use current day if not specified
        return self.session.query(Schedule).filter_by(
            channel=channel,
            day=day
        ).order_by(Schedule.start_time).all()
    
    def get_all_channels(self):
        genre_channels = self.session.query(Movie.genre).distinct().all()
        channels = [genre[0] for genre in genre_channels]
        
        active_holidays = self.get_active_holiday_channels()
        for holiday in active_holidays:
            channels.append(holiday.name)
        
        return sorted(channels)
