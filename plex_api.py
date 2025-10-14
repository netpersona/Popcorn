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
        else:
            self.base_url = os.getenv('PLEX_URL')
            self.token = os.getenv('PLEX_TOKEN')
        
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
                
                # Get landscape art (banner/backdrop)
                art_url = None
                if hasattr(movie, 'art') and movie.art:
                    art_url = f"{self.base_url}{movie.art}?X-Plex-Token={self.token}"
                
                # Get audience rating (IMDb, Rotten Tomatoes, etc.)
                audience_rating = None
                if hasattr(movie, 'audienceRating') and movie.audienceRating:
                    audience_rating = float(movie.audienceRating)
                elif hasattr(movie, 'rating') and movie.rating:
                    audience_rating = float(movie.rating)
                
                # Get cast (top 5 actors)
                cast = []
                if hasattr(movie, 'roles') and movie.roles:
                    cast = [role.tag for role in movie.roles[:5]]
                cast_str = ', '.join(cast) if cast else None
                
                movie_info = {
                    'title': movie.title,
                    'plex_id': str(movie.ratingKey),
                    'duration': int(movie.duration / 60000) if movie.duration else 0,
                    'genres': genres,
                    'year': movie.year if hasattr(movie, 'year') else None,
                    'rating': movie.contentRating if hasattr(movie, 'contentRating') else None,
                    'content_rating': movie.contentRating if hasattr(movie, 'contentRating') else None,
                    'audience_rating': audience_rating,
                    'summary': movie.summary if hasattr(movie, 'summary') else '',
                    'poster_url': poster_url,
                    'art_url': art_url,
                    'cast': cast_str
                }
                movie_data.append(movie_info)
            
            logger.info(f"Fetched {len(movie_data)} movies from Plex")
            return movie_data
            
        except Exception as e:
            logger.error(f"Error fetching movies: {e}")
            return []
    
    def play_movie(self, plex_id, offset_ms=0, playback_mode='web_player', client_id=None):
        try:
            movie = self.plex.fetchItem(int(plex_id))
            logger.info(f"Found movie: {movie.title}")
            
            if playback_mode == 'web_player':
                server_id = self.plex.machineIdentifier
                
                if offset_ms > 0:
                    offset_min = offset_ms // 60000
                    
                    try:
                        movie.updateTimeline(offset_ms, state='stopped', duration=int(movie.duration))
                        logger.info(f"Set resume position to {offset_min} min ({offset_ms}ms) for '{movie.title}'")
                    except Exception as e:
                        logger.warning(f"Failed to set resume position: {e}")
                    
                    web_url = f"https://app.plex.tv/desktop/#!/server/{server_id}/details?key=/library/metadata/{plex_id}&context=content.browse.metadata"
                    logger.info(f"Generated web player URL for '{movie.title}' with {offset_min} min offset")
                    logger.info(f"FULL URL: {web_url}")
                    return True, web_url, offset_min
                else:
                    web_url = f"https://app.plex.tv/desktop/#!/server/{server_id}/details?key=/library/metadata/{plex_id}&context=content.browse.metadata"
                    logger.info(f"Generated web player URL for '{movie.title}'")
                    logger.info(f"FULL URL: {web_url}")
                    return True, web_url, 0
            
            else:
                # Only use user's client_id - no admin fallback
                if not client_id:
                    logger.error("Plex client not configured - user must set their client in Profile settings")
                    return False, "Plex client not configured. Please set your Plex Client ID in your Profile settings.", 0
                
                try:
                    client = self.plex.client(client_id)
                    logger.info(f"Found Plex client: {client.title}")
                except NotFound:
                    try:
                        available_clients = [c.title for c in self.plex.clients()]
                        logger.error(f"Client '{client_id}' not found. Available: {available_clients}")
                        if available_clients:
                            return False, f"Client '{client_id}' not found. Available: {', '.join(available_clients)}. Update your Plex Client ID in Profile settings.", 0
                        else:
                            return False, "No Plex clients found. Make sure a Plex player is running and connected to your server.", 0
                    except Exception as e:
                        logger.error(f"Failed to list clients: {e}")
                        return False, f"Cannot connect to Plex server. Check your network and Plex settings.", 0
                
                try:
                    client.playMedia(movie)
                    logger.info(f"Sent playMedia command to {client.title}")
                except Exception as e:
                    logger.error(f"Failed to start playback: {e}", exc_info=True)
                    return False, "Playback failed. Please check your Plex client and try again.", 0
                
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
    
    @staticmethod
    def verify_library_access(plex_url, user_token):
        """
        Verify if a user token has access to the Plex server's movie library.
        Returns (has_access: bool, error_message: str or None)
        """
        try:
            user_plex = PlexServer(plex_url, user_token)
            
            # Check if user can access any movie library
            for section in user_plex.library.sections():
                if section.type == 'movie':
                    logger.info(f"User has access to movie library: {section.title}")
                    return True, None
            
            logger.warning("User authenticated but has no movie library access")
            return False, "No movie library access found"
            
        except Exception as e:
            logger.error(f"Failed to verify library access: {e}")
            return False, f"Cannot access Plex server: {str(e)}"
