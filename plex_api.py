import os
from plexapi.server import PlexServer
from plexapi.exceptions import BadRequest, NotFound
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlexAPI:
    def __init__(self, db_settings=None):
        if db_settings and db_settings.plex_url and db_settings.plex_token:
            self.base_url = db_settings.plex_url
            self.token = db_settings.plex_token
            self.client_name = db_settings.plex_client
        else:
            self.base_url = os.getenv('PLEX_URL')
            self.token = os.getenv('PLEX_TOKEN')
            self.client_name = os.getenv('PLEX_CLIENT')
        
        if not self.base_url or not self.token:
            raise ValueError("Plex URL and Token must be configured in Settings or environment variables")
        
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
                
                poster_url = None
                if hasattr(movie, 'thumb') and movie.thumb:
                    poster_url = f"{self.base_url}{movie.thumb}?X-Plex-Token={self.token}"
                
                movie_info = {
                    'title': movie.title,
                    'plex_id': str(movie.ratingKey),
                    'duration': int(movie.duration / 60000) if movie.duration else 0,
                    'genres': genres,
                    'year': movie.year if hasattr(movie, 'year') else None,
                    'rating': movie.contentRating if hasattr(movie, 'contentRating') else None,
                    'summary': movie.summary if hasattr(movie, 'summary') else '',
                    'poster_url': poster_url
                }
                movie_data.append(movie_info)
            
            logger.info(f"Fetched {len(movie_data)} movies from Plex")
            return movie_data
            
        except Exception as e:
            logger.error(f"Error fetching movies: {e}")
            return []
    
    def play_movie(self, plex_id, offset_ms=0, playback_mode='web_player'):
        try:
            movie = self.plex.fetchItem(int(plex_id))
            logger.info(f"Found movie: {movie.title}")
            
            if playback_mode == 'web_player':
                server_id = self.plex.machineIdentifier
                
                if offset_ms > 0:
                    offset_min = offset_ms // 60000
                    web_url = f"https://app.plex.tv/desktop/#!/server/{server_id}/details?key=%2Flibrary%2Fmetadata%2F{plex_id}&autoplay=1&automute=0&viewOffset={offset_ms}"
                    logger.info(f"Generated web player URL for '{movie.title}' with {offset_min} min offset (viewOffset={offset_ms}ms)")
                    return True, web_url, offset_min
                else:
                    web_url = f"https://app.plex.tv/desktop/#!/server/{server_id}/details?key=%2Flibrary%2Fmetadata%2F{plex_id}&autoplay=1&automute=0"
                    logger.info(f"Generated web player URL for '{movie.title}'")
                    return True, web_url, 0
            
            else:
                if not self.client_name:
                    logger.error("PLEX_CLIENT not set - cannot play movie")
                    return False, "Plex client not configured. Please set a default client in Settings.", 0
                
                try:
                    client = self.plex.client(self.client_name)
                    logger.info(f"Found Plex client: {client.title}")
                except NotFound:
                    try:
                        available_clients = [c.title for c in self.plex.clients()]
                        logger.error(f"Client '{self.client_name}' not found. Available: {available_clients}")
                        if available_clients:
                            return False, f"Client '{self.client_name}' not found. Available: {', '.join(available_clients)}. Update in Settings.", 0
                        else:
                            return False, "No Plex clients found. Make sure a Plex player is running and connected to your server.", 0
                    except Exception as e:
                        logger.error(f"Failed to list clients: {e}")
                        return False, f"Cannot connect to Plex server. Check your network and Plex settings.", 0
                
                try:
                    client.playMedia(movie)
                    logger.info(f"Sent playMedia command to {client.title}")
                except Exception as e:
                    logger.error(f"Failed to start playback: {e}")
                    return False, f"Playback failed: {str(e)}. Make sure your Plex client is responding.", 0
                
                if offset_ms > 0:
                    import time
                    time.sleep(1)
                    try:
                        client.seekTo(int(offset_ms))
                        logger.info(f"Sought to {offset_ms}ms ({offset_ms // 60000} min) in '{movie.title}'")
                    except Exception as e:
                        logger.warning(f"Failed to seek to {offset_ms}ms: {e}")
                        logger.info(f"Movie is playing from beginning instead")
                
                offset_min = offset_ms // 60000
                logger.info(f"Successfully playing '{movie.title}' on {client.title}")
                if offset_min > 0:
                    return True, f"Now playing: {movie.title} (starting at {offset_min} min)", offset_min
                else:
                    return True, f"Now playing: {movie.title}", 0
            
        except NotFound:
            logger.error(f"Movie with plex_id {plex_id} not found in Plex library")
            return False, "Movie not found in Plex library. Try syncing your library in Settings.", 0
        except Exception as e:
            logger.error(f"Unexpected error playing movie: {e}", exc_info=True)
            return False, f"Error: {str(e)}", 0
    
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
