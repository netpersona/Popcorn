from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Date, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

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
    keywords = Column(String, nullable=False)
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

def init_db(db_path='popcorn.db'):
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def get_session(db_path='popcorn.db'):
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    return Session()
