from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Date, UniqueConstraint, Boolean
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
    
    schedules = relationship('Schedule', back_populates='movie')
    
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
    
    def __repr__(self):
        return f"<HolidayChannel(name='{self.name}')>"

class Settings(Base):
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True)
    shuffle_frequency = Column(String, default='weekly')
    last_shuffle_date = Column(Date)
    
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

def init_db(db_path='popcorn.db'):
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def get_session(db_path='popcorn.db'):
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    return Session()
