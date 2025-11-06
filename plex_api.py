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
    
    def get_movie_libraries(self):
        """
        Get list of all available movie library names.
        Returns a list of library names (strings).
        """
        try:
            library_names = []
            for section in self.plex.library.sections():
                if section.type == 'movie':
                    library_names.append(section.title)
                    logger.info(f"Found movie library: {section.title}")
            
            if not library_names:
                logger.warning("No movie libraries found in Plex")
            else:
                logger.info(f"Total movie libraries found: {len(library_names)}")
            
            return library_names
            
        except Exception as e:
            logger.error(f"Error fetching movie libraries: {e}")
            return []
    
    def fetch_movies(self, selected_libraries=None):
        """
        Fetch movies from Plex libraries.
        
        Args:
            selected_libraries (list, optional): List of library names to fetch from.
                                                If None or empty, fetches from ALL movie libraries.
        
        Returns:
            list: List of movie dictionaries with library_name field included.
        """
        try:
            # Get all movie sections
            movie_sections = []
            for section in self.plex.library.sections():
                if section.type == 'movie':
                    # If selected_libraries is specified, filter by those names
                    if selected_libraries and section.title not in selected_libraries:
                        logger.info(f"Skipping library '{section.title}' (not in selected libraries)")
                        continue
                    movie_sections.append(section)
            
            if not movie_sections:
                if selected_libraries:
                    logger.warning(f"No movie libraries found matching selected libraries: {selected_libraries}")
                else:
                    logger.error("No movie libraries found in Plex")
                return []
            
            # Fetch movies from all selected libraries
            movie_data = []
            for movies_section in movie_sections:
                logger.info(f"Fetching movies from library: {movies_section.title}")
                movies = movies_section.all()
                library_name = movies_section.title
                
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
                        'cast': cast_str,
                        'library_name': library_name
                    }
                    movie_data.append(movie_info)
            
            logger.info(f"Fetched {len(movie_data)} movies from {len(movie_sections)} libraries")
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

                # Use custom Plex URL if available, otherwise fall back to app.plex.tv
                if self.base_url and not self.base_url.startswith('http://127.0.0.1') and not self.base_url.startswith('http://localhost'):
                    # Custom domain - use /web/index.html format
                    base_web_url = self.base_url.rstrip('/')
                    web_path = f"/web/index.html#!/server/{server_id}/details?key=%2Flibrary%2Fmetadata%2F{plex_id}"
                    web_url = f"{base_web_url}{web_path}"
                else:
                    # Default to app.plex.tv for local or unset URLs
                    web_url = f"https://app.plex.tv/desktop/#!/server/{server_id}/details?key=/library/metadata/{plex_id}&context=content.browse.metadata"

                if offset_ms > 0:
                    offset_min = offset_ms // 60000

                    try:
                        movie.updateTimeline(offset_ms, state='stopped', duration=int(movie.duration))
                        logger.info(f"Set resume position to {offset_min} min ({offset_ms}ms) for '{movie.title}'")
                    except Exception as e:
                        logger.warning(f"Failed to set resume position: {e}")

                    logger.info(f"Generated web player URL for '{movie.title}' with {offset_min} min offset")
                    logger.info(f"FULL URL: {web_url}")
                    return True, web_url, offset_min
                else:
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
        """
        Get list of available Plex clients using multiple discovery methods.
        
        This combines several approaches to find as many devices as possible:
        1. Active GDM clients (clients() - actively responding on network)
        2. Currently playing sessions (sessions() - currently streaming)
        3. MyPlex account resources (resources() - all registered devices)
        """
        try:
            logger.info(f"Discovering Plex clients using multiple methods...")
            client_map = {}  # Use dict to deduplicate by machine_identifier
            
            # Method 1: Active GDM clients (most reliable for controlling playback)
            try:
                clients = self.plex.clients()
                logger.info(f"Method 1 (GDM): Found {len(clients)} active client(s)")
                
                for c in clients:
                    platform = 'Unknown'
                    if hasattr(c, 'platform') and c.platform:
                        platform = c.platform
                    
                    client_map[c.machineIdentifier] = {
                        'name': c.title or 'Unknown Device',
                        'product': c.product or 'Unknown',
                        'identifier': c.machineIdentifier,
                        'platform': platform,
                        'source': 'Active (GDM)'
                    }
                    logger.info(f"  → Active: {c.title} ({c.product})")
            except Exception as e:
                logger.warning(f"Could not get GDM clients: {e}")
            
            # Method 2: Currently playing sessions
            try:
                sessions = self.plex.sessions()
                logger.info(f"Method 2 (Sessions): Found {len(sessions)} active session(s)")
                
                for session in sessions:
                    if hasattr(session, 'player') and session.player:
                        player = session.player
                        identifier = player.machineIdentifier if hasattr(player, 'machineIdentifier') else f"session_{player.title}"
                        
                        # Don't overwrite GDM clients (they're more reliable)
                        if identifier not in client_map:
                            platform = player.platform if hasattr(player, 'platform') and player.platform else 'Unknown'
                            
                            client_map[identifier] = {
                                'name': player.title or 'Unknown Player',
                                'product': player.product if hasattr(player, 'product') else 'Unknown',
                                'identifier': identifier,
                                'platform': platform,
                                'source': 'Playing Now'
                            }
                            logger.info(f"  → Playing: {player.title}")
            except Exception as e:
                logger.warning(f"Could not get active sessions: {e}")
            
            # Method 3: MyPlex account resources (all registered devices)
            try:
                from plexapi.myplex import MyPlexAccount
                if hasattr(self.plex, '_token'):
                    logger.info("Method 3 (MyPlex): Fetching account resources...")
                    account = MyPlexAccount(token=self.plex._token)
                    resources = account.resources()
                    
                    # Filter for client devices (not servers)
                    client_resources = [r for r in resources if r.provides == 'client' or r.provides == 'player']
                    logger.info(f"Method 3 (MyPlex): Found {len(client_resources)} registered client(s)")
                    
                    for resource in client_resources:
                        # Don't overwrite active clients
                        if resource.clientIdentifier not in client_map:
                            platform = resource.platform if hasattr(resource, 'platform') and resource.platform else 'Unknown'
                            
                            client_map[resource.clientIdentifier] = {
                                'name': resource.name or 'Unknown Device',
                                'product': resource.product if hasattr(resource, 'product') else 'Unknown',
                                'identifier': resource.clientIdentifier,
                                'platform': platform,
                                'source': 'Registered (may be offline)'
                            }
                            logger.info(f"  → Registered: {resource.name}")
            except Exception as e:
                logger.warning(f"Could not fetch MyPlex resources: {e}")
            
            # Convert to list and sort by source priority
            client_list = list(client_map.values())
            
            # Sort: Active first, then Playing, then Registered
            source_priority = {'Active (GDM)': 1, 'Playing Now': 2, 'Registered (may be offline)': 3}
            client_list.sort(key=lambda x: (source_priority.get(x['source'], 4), x['name']))
            
            logger.info(f"Total unique clients discovered: {len(client_list)}")
            
            if len(client_list) == 0:
                logger.warning("No clients found via any method. Troubleshooting tips:")
                logger.warning("  1. Ensure Plex app is open on at least one device")
                logger.warning("  2. Check that devices are on the same network")
                logger.warning("  3. Verify using local Plex URL (not app.plex.tv)")
                logger.warning("  4. Enable GDM in Plex Settings → Network")
                logger.warning("  5. Check firewall allows UDP port 32414")
            
            return client_list
        except Exception as e:
            logger.error(f"Error fetching clients from Plex API: {e}", exc_info=True)
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

            # Use custom Plex URL if available, otherwise fall back to app.plex.tv
            if self.base_url and not self.base_url.startswith('http://127.0.0.1') and not self.base_url.startswith('http://localhost'):
                # Custom domain - use /web/index.html format
                base_web_url = self.base_url.rstrip('/')
                web_url = f"{base_web_url}/web/index.html#!/server/{server_id}/details?key=%2Flibrary%2Fmetadata%2F{plex_id}"
            else:
                # Default to app.plex.tv for local or unset URLs
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
