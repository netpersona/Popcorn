import requests
import secrets
import logging
from datetime import datetime
from models import User, get_session

logger = logging.getLogger(__name__)

class PlexOAuth:
    def __init__(self, client_id='popcorn-tv-scheduler'):
        self.client_id = client_id
        self.redirect_uri = None
        self.plex_auth_url = 'https://plex.tv/api/v2/pins'
        self.plex_user_url = 'https://plex.tv/users/account.json'
    
    def get_auth_url(self, redirect_uri):
        self.redirect_uri = redirect_uri
        
        headers = {
            'Accept': 'application/json',
            'X-Plex-Product': 'Popcorn',
            'X-Plex-Client-Identifier': self.client_id
        }
        
        data = {
            'strong': 'true'
        }
        
        try:
            response = requests.post(self.plex_auth_url, headers=headers, json=data)
            response.raise_for_status()
            pin_data = response.json()
            
            pin_id = pin_data['id']
            code = pin_data['code']
            
            auth_url = f"https://app.plex.tv/auth#?clientID={self.client_id}&code={code}&context%5Bdevice%5D%5Bproduct%5D=Popcorn"
            
            return {
                'auth_url': auth_url,
                'pin_id': pin_id,
                'code': code
            }
        except Exception as e:
            logger.error(f"Failed to get Plex auth URL: {e}")
            return None
    
    def check_pin(self, pin_id):
        headers = {
            'Accept': 'application/json',
            'X-Plex-Client-Identifier': self.client_id
        }
        
        try:
            response = requests.get(f"{self.plex_auth_url}/{pin_id}", headers=headers)
            response.raise_for_status()
            pin_data = response.json()
            
            if pin_data.get('authToken'):
                return pin_data['authToken']
            return None
        except Exception as e:
            logger.error(f"Failed to check Plex pin: {e}")
            return None
    
    def get_user_info(self, auth_token):
        headers = {
            'Accept': 'application/json',
            'X-Plex-Token': auth_token
        }
        
        try:
            response = requests.get(self.plex_user_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            user_data = data.get('user', {})
            return {
                'plex_id': str(user_data.get('id')),
                'username': user_data.get('username'),
                'email': user_data.get('email'),
                'display_name': user_data.get('title') or user_data.get('username'),
                'avatar_url': user_data.get('thumb')
            }
        except Exception as e:
            logger.error(f"Failed to get Plex user info: {e}")
            return None

def create_or_update_plex_user(user_info, auth_token, db_session):
    try:
        user = db_session.query(User).filter_by(plex_id=user_info['plex_id']).first()
        
        if user:
            user.plex_token = auth_token
            user.plex_username = user_info['username']
            user.display_name = user_info['display_name']
            user.avatar_url = user_info['avatar_url']
            user.last_login = datetime.utcnow()
        else:
            username = user_info['username']
            email = user_info.get('email')
            
            existing_username = db_session.query(User).filter_by(username=username).first()
            if existing_username:
                username = f"{username}_{user_info['plex_id'][:8]}"
            
            is_first_user = db_session.query(User).count() == 0
            
            user = User(
                username=username,
                email=email,
                plex_id=user_info['plex_id'],
                plex_token=auth_token,
                plex_username=user_info['username'],
                display_name=user_info['display_name'],
                avatar_url=user_info['avatar_url'],
                is_admin=is_first_user,
                last_login=datetime.utcnow()
            )
            db_session.add(user)
        
        db_session.commit()
        return user
    except Exception as e:
        logger.error(f"Failed to create/update Plex user: {e}")
        db_session.rollback()
        return None
