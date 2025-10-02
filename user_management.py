from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import get_session, User, Invitation
from datetime import datetime, timedelta
import secrets
import string
from functools import wraps

user_mgmt_bp = Blueprint('user_mgmt', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Only administrators can access this page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def generate_invite_code():
    """Generate a secure random invite code"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))

@user_mgmt_bp.route('/users')
@login_required
@admin_required
def list_users():
    """Display list of all users"""
    import json
    
    with open('themes.json', 'r') as f:
        themes = json.load(f)
    
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes['plex'])['colors']
    
    db = get_session()
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        return render_template('users.html', users=users, theme_colors=theme_colors)
    finally:
        db.close()

@user_mgmt_bp.route('/users/create-invite', methods=['POST'])
@login_required
@admin_required
def create_invite():
    """Create a new invitation"""
    db = get_session()
    try:
        email = request.form.get('email', '').strip()
        expires_days = int(request.form.get('expires_days', 7))
        
        code = generate_invite_code()
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        invitation = Invitation(
            code=code,
            email=email if email else None,
            created_by=current_user.id,
            expires_at=expires_at
        )
        
        db.add(invitation)
        db.commit()
        
        invite_url = request.host_url + 'register?invite=' + code
        
        flash(f'Invitation created successfully! Invite link: {invite_url}', 'success')
        return redirect(url_for('user_mgmt.list_users'))
    except Exception as e:
        db.rollback()
        flash(f'Error creating invitation: {str(e)}', 'error')
        return redirect(url_for('user_mgmt.list_users'))
    finally:
        db.close()

@user_mgmt_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Edit user permissions"""
    import json
    
    with open('themes.json', 'r') as f:
        themes = json.load(f)
    
    user_theme = current_user.theme if current_user.theme else 'plex'
    theme_colors = themes.get(user_theme, themes['plex'])['colors']
    
    db = get_session()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('user_mgmt.list_users'))
        
        if request.method == 'POST':
            if user.id == current_user.id:
                flash('You cannot modify your own permissions.', 'error')
                return redirect(url_for('user_mgmt.list_users'))
            
            user.is_admin = request.form.get('is_admin') == 'on'
            user.is_active = request.form.get('is_active') == 'on'
            user.updated_at = datetime.utcnow()
            
            db.commit()
            flash(f'User {user.username} updated successfully.', 'success')
            return redirect(url_for('user_mgmt.list_users'))
        
        return render_template('edit_user.html', user=user, theme_colors=theme_colors)
    finally:
        db.close()

@user_mgmt_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Delete a user"""
    db = get_session()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('user_mgmt.list_users'))
        
        if user.id == current_user.id:
            flash('You cannot delete your own account.', 'error')
            return redirect(url_for('user_mgmt.list_users'))
        
        username = user.username
        db.delete(user)
        db.commit()
        flash(f'User {username} deleted successfully.', 'success')
        return redirect(url_for('user_mgmt.list_users'))
    except Exception as e:
        db.rollback()
        flash(f'Error deleting user: {str(e)}', 'error')
        return redirect(url_for('user_mgmt.list_users'))
    finally:
        db.close()

@user_mgmt_bp.route('/users/invitations')
@login_required
@admin_required
def list_invitations():
    """Display list of all invitations"""
    db = get_session()
    try:
        invitations = db.query(Invitation).order_by(Invitation.created_at.desc()).all()
        return render_template('invitations.html', invitations=invitations)
    finally:
        db.close()

@user_mgmt_bp.route('/users/invitations/<int:invite_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_invitation(invite_id):
    """Delete an invitation"""
    db = get_session()
    try:
        invitation = db.query(Invitation).filter_by(id=invite_id).first()
        if not invitation:
            flash('Invitation not found.', 'error')
            return redirect(url_for('user_mgmt.list_invitations'))
        
        db.delete(invitation)
        db.commit()
        flash('Invitation deleted successfully.', 'success')
        return redirect(url_for('user_mgmt.list_invitations'))
    except Exception as e:
        db.rollback()
        flash(f'Error deleting invitation: {str(e)}', 'error')
        return redirect(url_for('user_mgmt.list_invitations'))
    finally:
        db.close()

def validate_invite_code(code):
    """Validate an invitation code"""
    db = get_session()
    try:
        invitation = db.query(Invitation).filter_by(code=code).first()
        
        if not invitation:
            return False, "Invalid invitation code."
        
        if invitation.used_by:
            return False, "This invitation has already been used."
        
        if not invitation.is_active:
            return False, "This invitation is no longer active."
        
        if invitation.expires_at and invitation.expires_at < datetime.utcnow():
            return False, "This invitation has expired."
        
        return True, invitation
    finally:
        db.close()

def mark_invite_used(code, user_id):
    """Mark an invitation as used"""
    db = get_session()
    try:
        invitation = db.query(Invitation).filter_by(code=code).first()
        if invitation:
            invitation.used_by = user_id
            invitation.used_at = datetime.utcnow()
            invitation.is_active = False
            db.commit()
            return True
        return False
    except:
        db.rollback()
        return False
    finally:
        db.close()
