"""
Theme Service - Handles theme loading, validation, and management
"""

import json
import re
from models import CustomTheme, get_session
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

REQUIRED_THEME_KEYS = ['name', 'description', 'colors']
REQUIRED_COLOR_KEYS = [
    'bg-primary', 'bg-secondary', 'bg-tertiary',
    'accent', 'accent-hover',
    'text-primary', 'text-secondary', 'text-muted',
    'border', 'shadow'
]

MAX_THEME_SIZE = 50 * 1024  # 50KB limit

class ThemeService:
    
    @staticmethod
    def load_default_themes():
        """Load default themes from themes.json"""
        try:
            with open('themes.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load default themes: {e}")
            return {}
    
    @staticmethod
    def get_all_themes_for_user(user_id):
        """
        Get all available themes for a user (default + custom + public)
        Returns dict with theme slug as key
        Custom themes are namespaced as "custom_{user_id}_{slug}"
        """
        themes = ThemeService.load_default_themes()
        
        session = get_session()
        try:
            custom_themes = session.query(CustomTheme).filter(
                (CustomTheme.user_id == user_id) | (CustomTheme.is_public == True)
            ).all()
            
            for theme in custom_themes:
                try:
                    theme_data = json.loads(theme.theme_json)
                    theme_data['_custom'] = True
                    theme_data['_theme_id'] = theme.id
                    theme_data['_owner_id'] = theme.user_id
                    custom_slug = f"custom_{theme.user_id}_{theme.slug}"
                    themes[custom_slug] = theme_data
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in custom theme {theme.id}")
                    continue
        finally:
            session.close()
        
        return themes
    
    @staticmethod
    def validate_theme_json(theme_data_str):
        """
        Validate theme JSON structure and content
        Returns (is_valid, error_message, parsed_data)
        """
        if len(theme_data_str) > MAX_THEME_SIZE:
            return False, f"Theme file too large (max {MAX_THEME_SIZE} bytes)", None
        
        try:
            data = json.loads(theme_data_str)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON when validating theme: {e}")
            return False, "Invalid theme file format.", None
        
        for key in REQUIRED_THEME_KEYS:
            if key not in data:
                return False, f"Missing required key: {key}", None
        
        colors = data.get('colors', {})
        for key in REQUIRED_COLOR_KEYS:
            if key not in colors:
                return False, f"Missing required color: {key}", None
        
        if not isinstance(data['name'], str) or not data['name'].strip():
            return False, "Theme name must be a non-empty string", None
        
        if not isinstance(data['description'], str):
            return False, "Theme description must be a string", None
        
        for color_key, color_value in colors.items():
            if not isinstance(color_value, str):
                return False, f"Color {color_key} must be a string", None
            if not (color_value.startswith('#') or color_value.startswith('rgba') or color_value.startswith('rgb')):
                return False, f"Color {color_key} has invalid format: {color_value}", None
        
        return True, None, data
    
    @staticmethod
    def slugify(text):
        """Convert text to safe slug"""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '_', text)
        return text[:50]
    
    @staticmethod
    def save_custom_theme(user_id, theme_json_str, is_public=False):
        """
        Save a custom theme for a user
        Returns (success, error_message, theme_object)
        """
        is_valid, error, theme_data = ThemeService.validate_theme_json(theme_json_str)
        if not is_valid:
            return False, error, None
        
        slug = ThemeService.slugify(theme_data['name'])
        
        session = get_session()
        try:
            existing = session.query(CustomTheme).filter_by(
                user_id=user_id,
                slug=slug
            ).first()
            
            if existing:
                existing.name = theme_data['name']
                existing.description = theme_data['description']
                existing.theme_json = theme_json_str
                existing.is_public = is_public
                existing.updated_at = datetime.utcnow()
                theme = existing
                logger.info(f"Updated custom theme: {slug} for user {user_id}")
            else:
                theme = CustomTheme(
                    user_id=user_id,
                    name=theme_data['name'],
                    slug=slug,
                    description=theme_data['description'],
                    theme_json=theme_json_str,
                    is_public=is_public
                )
                session.add(theme)
                logger.info(f"Created custom theme: {slug} for user {user_id}")
            
            session.commit()
            return True, None, theme
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save custom theme: {e}")
            return False, "Failed to save custom theme due to a server error.", None
        finally:
            session.close()
    
    @staticmethod
    def delete_custom_theme(user_id, theme_id):
        """
        Delete a custom theme (only if owned by user)
        Returns (success, error_message)
        """
        session = get_session()
        try:
            theme = session.query(CustomTheme).filter_by(
                id=theme_id,
                user_id=user_id
            ).first()
            
            if not theme:
                return False, "Theme not found or you don't have permission to delete it"
            
            session.delete(theme)
            session.commit()
            logger.info(f"Deleted custom theme {theme_id} for user {user_id}")
            return True, None
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete custom theme: {e}")
            return False, "An internal error occurred while deleting the theme."
        finally:
            session.close()
    
    @staticmethod
    def get_user_custom_themes(user_id):
        """Get all custom themes created by a specific user"""
        session = get_session()
        try:
            themes = session.query(CustomTheme).filter_by(user_id=user_id).all()
            return [
                {
                    'id': t.id,
                    'name': t.name,
                    'slug': t.slug,
                    'description': t.description,
                    'is_public': t.is_public,
                    'created_at': t.created_at.isoformat() if t.created_at else None
                }
                for t in themes
            ]
        finally:
            session.close()
