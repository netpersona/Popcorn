import os
from plexapi.server import PlexServer
from plexapi.exceptions import BadRequest, NotFound
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlexAPI:
    def __init__(self):
        self.base_url = os.getenv('PLEX_URL')
        self.token = os.getenv('PLEX_TOKEN')
        self.client_name = os.getenv('PLEX_CLIENT')
        
        if not self.base_url or not self.token:
            raise ValueError("PLEX_URL and PLEX_TOKEN must be set in environment variables")
        
        try:
            self.plex = PlexServer(self.base_url, self.token)
            logger.info(f"Connected to Plex server: {self.plex.friendlyName}")
        except Exception as e:
            logger.error(f"Failed to connect to Plex: {e}")
            raise
    
    def fetch_movies(self):
        try:
            movies_section = None
            for section in self.plex.library.sections():
                if section.type == 'movie':
                    movies_section = section
                    break
            
            if not movies_section:
                logger.error("No movie library found in Plex")
                return []
            
            logger.info(f"Fetching movies from library: {movies_section.title}")
            movies = movies_section.all()
            
            movie_data = []
            for movie in movies:
                genres = [g.tag for g in movie.genres] if movie.genres else ['Unknown']
                
                movie_info = {
                    'title': movie.title,
                    'plex_id': str(movie.ratingKey),
                    'duration': int(movie.duration / 60000) if movie.duration else 0,
                    'genres': genres,
                    'year': movie.year if hasattr(movie, 'year') else None,
                    'rating': movie.contentRating if hasattr(movie, 'contentRating') else None,
                    'summary': movie.summary if hasattr(movie, 'summary') else ''
                }
                movie_data.append(movie_info)
            
            logger.info(f"Fetched {len(movie_data)} movies from Plex")
            return movie_data
            
        except Exception as e:
            logger.error(f"Error fetching movies: {e}")
            return []
    
    def play_movie(self, plex_id):
        try:
            if not self.client_name:
                logger.error("PLEX_CLIENT not set in environment variables")
                return False, "Plex client not configured"
            
            try:
                client = self.plex.client(self.client_name)
            except NotFound:
                available_clients = [c.title for c in self.plex.clients()]
                logger.error(f"Client '{self.client_name}' not found. Available: {available_clients}")
                return False, f"Client not found. Available clients: {', '.join(available_clients)}"
            
            movie = self.plex.fetchItem(int(plex_id))
            client.playMedia(movie)
            
            logger.info(f"Playing '{movie.title}' on {client.title}")
            return True, f"Now playing: {movie.title}"
            
        except NotFound:
            logger.error(f"Movie with plex_id {plex_id} not found")
            return False, "Movie not found in Plex library"
        except Exception as e:
            logger.error(f"Error playing movie: {e}")
            return False, str(e)
    
    def get_available_clients(self):
        try:
            clients = self.plex.clients()
            return [{'name': c.title, 'product': c.product} for c in clients]
        except Exception as e:
            logger.error(f"Error fetching clients: {e}")
            return []
    
    def get_server_info(self):
        try:
            return {
                'machine_identifier': self.plex.machineIdentifier,
                'friendly_name': self.plex.friendlyName,
                'version': self.plex.version
            }
        except Exception as e:
            logger.error(f"Error fetching server info: {e}")
            return None
    
    def get_movie_deep_link(self, plex_id):
        try:
            server_id = self.plex.machineIdentifier
            plex_uri = f"plex://library/metadata/{plex_id}"
            web_url = f"https://app.plex.tv/desktop#!/server/{server_id}/details?key=/library/metadata/{plex_id}"
            
            return {
                'plex_uri': plex_uri,
                'web_url': web_url,
                'rating_key': plex_id
            }
        except Exception as e:
            logger.error(f"Error generating deep link: {e}")
            return None
