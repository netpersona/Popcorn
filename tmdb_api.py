import requests
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class TMDBAPI:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.enabled = bool(api_key)
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        if not self.enabled:
            return None
        
        if params is None:
            params = {}
        params['api_key'] = self.api_key
        
        try:
            response = requests.get(f"{self.base_url}/{endpoint}", params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"TMDB API request failed: {e}")
            return None
    
    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        params = {'query': title}
        if year:
            params['year'] = year
        
        data = self._make_request('search/movie', params)
        if data and data.get('results'):
            return data['results'][0]
        return None
    
    def get_movie_details(self, tmdb_id: int) -> Optional[Dict]:
        return self._make_request(f'movie/{tmdb_id}', {'append_to_response': 'keywords'})
    
    def get_movie_keywords(self, tmdb_id: int) -> List[str]:
        data = self._make_request(f'movie/{tmdb_id}/keywords')
        if data and 'keywords' in data:
            return [kw['name'].lower() for kw in data['keywords']]
        return []
    
    def get_collection(self, collection_id: int) -> Optional[Dict]:
        return self._make_request(f'collection/{collection_id}')
    
    def get_movie_by_plex_metadata(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        movie_data = self.search_movie(title, year)
        if not movie_data:
            return None
        
        tmdb_id = movie_data.get('id')
        if not tmdb_id:
            return None
        
        details = self.get_movie_details(tmdb_id)
        if details:
            details['tmdb_keywords'] = self.get_movie_keywords(tmdb_id)
        
        return details
