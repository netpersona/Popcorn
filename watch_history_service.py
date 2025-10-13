from models import WatchHistory, Movie, get_session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from collections import Counter

class WatchHistoryService:
    @staticmethod
    def get_user_stats(user_id):
        session = get_session()
        
        total_movies = session.query(func.count(WatchHistory.id)).filter(
            WatchHistory.user_id == user_id
        ).scalar() or 0
        
        unique_movies = session.query(func.count(func.distinct(WatchHistory.plex_id))).filter(
            WatchHistory.user_id == user_id
        ).scalar() or 0
        
        total_minutes = session.query(func.sum(WatchHistory.duration_watched)).filter(
            WatchHistory.user_id == user_id
        ).scalar() or 0
        
        total_hours = round(total_minutes / 60, 1) if total_minutes else 0
        
        genre_counts = session.query(
            WatchHistory.movie_genre, 
            func.count(WatchHistory.id)
        ).filter(
            WatchHistory.user_id == user_id,
            WatchHistory.movie_genre.isnot(None)
        ).group_by(WatchHistory.movie_genre).all()
        
        favorite_genres = sorted(genre_counts, key=lambda x: x[1], reverse=True)[:3]
        
        recent_watches = session.query(WatchHistory).filter(
            WatchHistory.user_id == user_id
        ).order_by(desc(WatchHistory.watched_at)).limit(10).all()
        
        most_watched_query = session.query(
            WatchHistory.movie_title,
            WatchHistory.plex_id,
            func.count(WatchHistory.id).label('watch_count')
        ).filter(
            WatchHistory.user_id == user_id
        ).group_by(
            WatchHistory.movie_title,
            WatchHistory.plex_id
        ).order_by(desc('watch_count')).limit(5).all()
        
        most_watched = [
            {'title': title, 'plex_id': plex_id, 'count': count}
            for title, plex_id, count in most_watched_query
        ]
        
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_count = session.query(func.count(WatchHistory.id)).filter(
            WatchHistory.user_id == user_id,
            WatchHistory.watched_at >= thirty_days_ago
        ).scalar() or 0
        
        weekly_data = []
        for i in range(4):
            week_start = datetime.utcnow() - timedelta(days=(i+1)*7)
            week_end = datetime.utcnow() - timedelta(days=i*7)
            week_count = session.query(func.count(WatchHistory.id)).filter(
                WatchHistory.user_id == user_id,
                WatchHistory.watched_at >= week_start,
                WatchHistory.watched_at < week_end
            ).scalar() or 0
            weekly_data.insert(0, {'week': f"{i+1} weeks ago", 'count': week_count})
        
        return {
            'total_movies_watched': total_movies,
            'unique_movies_watched': unique_movies,
            'total_hours': total_hours,
            'favorite_genres': [{'genre': genre, 'count': count} for genre, count in favorite_genres],
            'recent_watches': recent_watches,
            'most_watched': most_watched,
            'recent_30_days': recent_count,
            'weekly_trend': weekly_data
        }
    
    @staticmethod
    def has_watched(user_id, plex_id):
        session = get_session()
        return session.query(WatchHistory).filter(
            WatchHistory.user_id == user_id,
            WatchHistory.plex_id == plex_id
        ).first() is not None
    
    @staticmethod
    def get_watch_count(user_id, plex_id):
        session = get_session()
        return session.query(func.count(WatchHistory.id)).filter(
            WatchHistory.user_id == user_id,
            WatchHistory.plex_id == plex_id
        ).scalar() or 0
    
    @staticmethod
    def get_progress(user_id, plex_id):
        session = get_session()
        latest_watch = session.query(WatchHistory).filter(
            WatchHistory.user_id == user_id,
            WatchHistory.plex_id == plex_id
        ).order_by(desc(WatchHistory.watched_at)).first()
        
        if latest_watch and latest_watch.playback_position is not None and latest_watch.playback_position > 0:
            return latest_watch.playback_position
        return 0
    
    @staticmethod
    def get_continue_watching(user_id, limit=10):
        session = get_session()
        
        # Get movies with watch history and progress
        recent_watches = session.query(
            WatchHistory.plex_id,
            WatchHistory.movie_title,
            func.max(WatchHistory.watched_at).label('last_watched'),
            func.max(WatchHistory.playback_position).label('position')
        ).filter(
            WatchHistory.user_id == user_id,
            WatchHistory.playback_position > 0
        ).group_by(
            WatchHistory.plex_id,
            WatchHistory.movie_title
        ).order_by(desc('last_watched')).limit(limit).all()
        
        # Get full movie details
        continue_watching = []
        for plex_id, title, last_watched, position in recent_watches:
            movie = session.query(Movie).filter(Movie.plex_id == plex_id).first()
            if movie and position < (movie.duration * 60 * 1000):  # Only if not fully watched
                progress_percent = (position / (movie.duration * 60 * 1000)) * 100
                continue_watching.append({
                    'movie': movie,
                    'position_ms': position,
                    'progress_percent': min(progress_percent, 100),
                    'last_watched': last_watched
                })
        
        return continue_watching
