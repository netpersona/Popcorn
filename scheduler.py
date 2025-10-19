from datetime import datetime, timedelta, date
import random
import logging
from models import Movie, Schedule, HolidayChannel, Settings, get_session

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
    
    def initialize_holiday_channels(self):
        self.migrate_holiday_channels_schema()
        
        existing = self.session.query(HolidayChannel).count()
        if existing > 0:
            return
        
        holiday_channels = [
            {
                'name': 'Cozy Halloween',
                'start_month': 9,
                'end_month': 11,
                'genre_filter': 'animation,family,fantasy',
                'keywords': 'halloween,hocus,casper,ghostbusters,monster,addams,beetlejuice,nightmare before christmas,corpse bride,frankenweenie,coraline,paranorman,witch,ghost,spooky,goosebumps',
                'rating_filter': 'G,PG,PG-13'
            },
            {
                'name': 'Scary Halloween',
                'start_month': 9,
                'end_month': 11,
                'genre_filter': 'horror,thriller',
                'keywords': 'halloween,scream,nightmare,friday the 13th,evil dead,saw,conjuring,insidious,paranormal,exorcist,ring,grudge,terror,slasher',
                'rating_filter': 'PG-13,R,NR,Not Rated,Unrated'
            },
            {
                'name': 'Christmas',
                'start_month': 11,
                'end_month': 1,
                'genre_filter': 'holiday',
                'keywords': 'christmas,xmas,santa,elf,grinch,miracle,wonderful life,home alone,polar express,jingle,carol,noel,claus,reindeer,snowman,nutcracker,scrooge',
                'rating_filter': None
            }
        ]
        
        for channel_data in holiday_channels:
            channel = HolidayChannel(**channel_data)
            self.session.add(channel)
        
        self.session.commit()
        logger.info("Initialized holiday channels with genre-based filtering")
    
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
        movies = self.session.query(Movie).all()
        matching_movies = []
        
        genre_filters = []
        if channel.genre_filter:
            genre_filters = [g.strip().lower() for g in channel.genre_filter.split(',')]
        
        keywords = []
        if channel.keywords:
            keywords = [k.strip().lower() for k in channel.keywords.split(',')]
        
        for movie in movies:
            matched = False
            genre_match = False
            keyword_match = False
            
            movie_genre_lower = movie.genre.lower()
            title_lower = movie.title.lower()
            summary_lower = movie.summary.lower() if movie.summary else ''
            
            if genre_filters:
                if any(genre_filter in movie_genre_lower for genre_filter in genre_filters):
                    genre_match = True
            
            if keywords:
                title_match = any(keyword in title_lower for keyword in keywords)
                summary_match = any(keyword in summary_lower for keyword in keywords)
                
                if title_match or summary_match:
                    keyword_match = True
            
            if channel.name == 'Cozy Halloween':
                matched = genre_match and keyword_match
            elif channel.name == 'Scary Halloween':
                horror_match = 'horror' in movie_genre_lower
                thriller_with_keyword = 'thriller' in movie_genre_lower and keyword_match
                matched = horror_match or thriller_with_keyword
            else:
                matched = genre_match or keyword_match
            
            if matched:
                if channel.rating_filter:
                    allowed_ratings = [r.strip().upper() for r in channel.rating_filter.split(',')]
                    movie_rating_upper = movie.rating.upper() if movie.rating else ''
                    if movie_rating_upper in allowed_ratings or not movie.rating:
                        matching_movies.append(movie)
                else:
                    matching_movies.append(movie)
        
        logger.info(f"Found {len(matching_movies)} movies for holiday channel '{channel.name}'")
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
        
        logger.info("Generating fresh schedules for all channels")
        
        self.session.query(Schedule).delete()
        
        genre_movies = {}
        movies = self.session.query(Movie).all()
        
        for movie in movies:
            if movie.genre not in genre_movies:
                genre_movies[movie.genre] = []
            genre_movies[movie.genre].append(movie)
        
        for genre, genre_movie_list in genre_movies.items():
            self.generate_channel_schedule(genre, genre_movie_list)
        
        active_holidays = self.get_active_holiday_channels()
        for holiday_channel in active_holidays:
            holiday_movies = self.get_movies_for_holiday_channel(holiday_channel)
            if holiday_movies:
                self.generate_channel_schedule(holiday_channel.name, holiday_movies)
        
        settings.last_shuffle_date = date.today()
        self.session.commit()
        
        logger.info("All schedules generated successfully")
    
    def get_current_playing(self, channel):
        now = datetime.now()
        current_time = f"{now.hour:02d}:{now.minute:02d}"
        
        schedules = self.session.query(Schedule).filter_by(
            channel=channel, 
            day=0
        ).order_by(Schedule.start_time).all()
        
        for schedule in schedules:
            if schedule.start_time <= current_time < schedule.end_time:
                return schedule
        
        return schedules[0] if schedules else None
    
    def get_channel_schedule(self, channel):
        return self.session.query(Schedule).filter_by(
            channel=channel,
            day=0
        ).order_by(Schedule.start_time).all()
    
    def get_all_channels(self):
        genre_channels = self.session.query(Movie.genre).distinct().all()
        channels = [genre[0] for genre in genre_channels]
        
        active_holidays = self.get_active_holiday_channels()
        for holiday in active_holidays:
            channels.append(holiday.name)
        
        return sorted(channels)
