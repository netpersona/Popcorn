from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Date, UniqueConstraint, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()

class Movie(Base):
    __tablename__ = 'movies'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    genre = Column(String, nullable=False)
    duration = Column(Integer, nullable=False)
    plex_id = Column(String, nullable=False)
    year = Column(Integer)
    rating = Column(String)
    summary = Column(String)
    poster_url = Column(String)
    art_url = Column(String)
    audience_rating = Column(Float)
    content_rating = Column(String)
    cast = Column(String)
    library_name = Column(String)

    schedules = relationship('Schedule', back_populates='movie', cascade='all, delete-orphan')
    overrides = relationship('MovieOverride', cascade='all, delete-orphan')
    favorites = relationship('MovieFavorite', cascade='all, delete-orphan')
    watch_history = relationship('WatchHistory')

    __table_args__ = (UniqueConstraint('plex_id', 'genre', name='_plex_genre_uc'),)
    
    def __repr__(self):
        return f"<Movie(title='{self.title}', genre='{self.genre}')>"

class Schedule(Base):
    __tablename__ = 'schedules'
    
    id = Column(Integer, primary_key=True)
    channel = Column(String, nullable=False)
    movie_id = Column(Integer, ForeignKey('movies.id'), nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    day = Column(Integer, nullable=False)
    
    movie = relationship('Movie', back_populates='schedules')
    
    def __repr__(self):
        return f"<Schedule(channel='{self.channel}', start='{self.start_time}')>"

class HolidayChannel(Base):
    __tablename__ = 'holiday_channels'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    start_month = Column(Integer, nullable=False)
    end_month = Column(Integer, nullable=False)
    genre_filter = Column(String)
    keywords = Column(String)
    rating_filter = Column(String)
    filter_mode = Column(String, default='AND')
    tmdb_collection_ids = Column(String)
    tmdb_keywords = Column(String)
    min_rating = Column(Float)
    min_popularity = Column(Float)
    
    def __repr__(self):
        return f"<HolidayChannel(name='{self.name}')>"

class MovieOverride(Base):
    __tablename__ = 'movie_overrides'
    
    id = Column(Integer, primary_key=True)
    channel_name = Column(String, nullable=False)
    movie_id = Column(Integer, ForeignKey('movies.id'), nullable=False)
    override_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    movie = relationship('Movie')
    
    __table_args__ = (UniqueConstraint('channel_name', 'movie_id', name='_channel_movie_uc'),)
    
    def __repr__(self):
        return f"<MovieOverride(channel='{self.channel_name}', type='{self.override_type}')>"

class Settings(Base):
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True)
    shuffle_frequency = Column(String, default='weekly')
    last_shuffle_date = Column(Date)
    plex_url = Column(String)
    plex_token = Column(String)
    plex_client = Column(String)
    enable_channel_numbers = Column(Boolean, default=True)
    current_glow_brightness = Column(Integer, default=100)
    tmdb_api_key = Column(String)
    selected_movie_libraries = Column(Text)
    plex_machine_identifier = Column(String)
    
    def __repr__(self):
        return f"<Settings(frequency='{self.shuffle_frequency}')>"

class Invitation(Base):
    __tablename__ = 'invitations'
    
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    email = Column(String)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    used_by = Column(Integer, ForeignKey('users.id'))
    used_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<Invitation(code='{self.code}', email='{self.email}')>"

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True)
    password_hash = Column(String)
    plex_id = Column(String, unique=True)
    plex_token = Column(String)
    plex_username = Column(String)
    display_name = Column(String)
    avatar_url = Column(String)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    invited_by = Column(Integer, ForeignKey('users.id'))
    theme = Column(String, default='plex')
    enable_crt_mode = Column(Boolean, default=False)
    enable_film_grain = Column(Boolean, default=False)
    playback_mode = Column(String, default='web_player')
    enable_time_offset = Column(Boolean, default=True)
    visible_channels = Column(String)
    plex_client = Column(String)
    current_glow_brightness = Column(Integer, default=100)
    using_default_password = Column(Boolean, default=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"

class AppVersion(Base):
    __tablename__ = 'app_version'
    
    id = Column(Integer, primary_key=True)
    current_version = Column(String, nullable=False)
    current_commit = Column(String)
    last_check_date = Column(DateTime)
    last_update_date = Column(DateTime)
    github_repo = Column(String, default='netpersona/Popcorn')
    update_available = Column(Boolean, default=False)
    latest_version = Column(String)
    
    def __repr__(self):
        return f"<AppVersion(version='{self.current_version}', commit='{self.current_commit}')>"

class MigrationHistory(Base):
    __tablename__ = 'migration_history'
    
    id = Column(Integer, primary_key=True)
    migration_name = Column(String, unique=True, nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<MigrationHistory(migration='{self.migration_name}')>"

class CustomTheme(Base):
    __tablename__ = 'custom_themes'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    description = Column(String)
    theme_json = Column(Text, nullable=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (UniqueConstraint('user_id', 'slug', name='_user_slug_uc'),)
    
    def __repr__(self):
        return f"<CustomTheme(name='{self.name}', user_id={self.user_id})>"

class WatchHistory(Base):
    __tablename__ = 'watch_history'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    movie_id = Column(Integer, ForeignKey('movies.id', ondelete='SET NULL'))
    plex_id = Column(String, nullable=False)
    movie_title = Column(String, nullable=False)
    movie_genre = Column(String)
    watched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    duration_watched = Column(Integer)
    playback_position = Column(Integer, default=0)

    user = relationship('User')
    movie = relationship('Movie')
    
    def __repr__(self):
        return f"<WatchHistory(user_id={self.user_id}, movie='{self.movie_title}', watched_at='{self.watched_at}')>"

class ChannelFavorite(Base):
    __tablename__ = 'channel_favorites'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    channel_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship('User')
    
    __table_args__ = (UniqueConstraint('user_id', 'channel_name', name='_user_channel_uc'),)
    
    def __repr__(self):
        return f"<ChannelFavorite(user_id={self.user_id}, channel='{self.channel_name}')>"

class MovieFavorite(Base):
    __tablename__ = 'movie_favorites'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    movie_id = Column(Integer, ForeignKey('movies.id'), nullable=False)
    plex_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship('User')
    movie = relationship('Movie')
    
    __table_args__ = (UniqueConstraint('user_id', 'movie_id', name='_user_movie_uc'),)
    
    def __repr__(self):
        return f"<MovieFavorite(user_id={self.user_id}, movie_id={self.movie_id})>"

class UserDevice(Base):
    __tablename__ = 'user_devices'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    device_name = Column(String, nullable=False)
    machine_identifier = Column(String, nullable=False)
    platform = Column(String)
    product = Column(String)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship('User')
    
    __table_args__ = (UniqueConstraint('user_id', 'machine_identifier', name='_user_device_uc'),)
    
    def __repr__(self):
        return f"<UserDevice(user_id={self.user_id}, device_name='{self.device_name}', platform='{self.platform}')>"

def is_volume_properly_mounted():
    """
    Check if /data is properly mounted to a host directory (not an anonymous volume).
    Returns tuple: (is_mounted, warning_message)
    """
    import os
    import subprocess
    
    data_dir = os.getenv('DATA_DIR', '.')
    
    # If not using /data, assume local development - no warning needed
    if data_dir != '/data':
        return (True, None)
    
    # Check if we're in Docker
    if not os.path.exists('/.dockerenv'):
        return (True, None)
    
    try:
        # Check if /data has a real mount or is just an overlay/anonymous volume
        result = subprocess.run(['mountpoint', '-q', '/data'], capture_output=True)
        if result.returncode == 0:
            # /data is a proper mount point
            return (True, None)
        else:
            # /data is not mounted - using anonymous volume or overlay
            return (False, "WARNING: /data is not mapped to a host directory. Database will be lost on container updates!")
    except Exception:
        # If mountpoint command fails, assume it's okay
        return (True, None)

def get_db_path():
    """Get the database path from environment or use default"""
    import os
    data_dir = os.getenv('DATA_DIR', '.')
    return os.path.join(data_dir, 'popcorn.db')

def init_db(db_path=None):
    if db_path is None:
        db_path = get_db_path()
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def get_session(db_path=None):
    if db_path is None:
        db_path = get_db_path()
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    return Session()
