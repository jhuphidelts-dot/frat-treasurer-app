"""
Authentication and User Management System
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import re
from datetime import datetime
from models import db, User, Role, Member
from functools import wraps

# Create authentication blueprint
auth_bp = Blueprint('auth', __name__)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))

def init_auth(app):
    """Initialize authentication system with Flask app"""
    login_manager.init_app(app)
    app.register_blueprint(auth_bp)

# Phone number validation
def validate_phone(phone):
    """Validate and format phone number"""
    # Remove all non-digits
    digits = re.sub(r'[^\d]', '', phone)
    
    # Check if it's a valid US phone number
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}"
    else:
        return None

def role_required(*allowed_roles):
    """Decorator to require specific roles for route access"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # Check if user has any of the required roles
            user_roles = [role.name for role in current_user.roles]
            
            if not any(role in user_roles for role in allowed_roles):
                flash('You do not have permission to access this page.', 'error')
                return redirect(url_for('main.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def has_permission(permission_name):
    """Check if current user has a specific permission"""
    if not current_user.is_authenticated:
        return False
    
    for role in current_user.roles:
        permissions = role.get_permissions()
        if permissions.get(permission_name, False):
            return True
    
    return False

# Authentication Routes
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        
        if not phone or not password:
            flash('Please enter both phone number and password.', 'error')
            return render_template('auth/login.html')
        
        # Format phone number
        formatted_phone = validate_phone(phone)
        if not formatted_phone:
            flash('Please enter a valid phone number.', 'error')
            return render_template('auth/login.html')
        
        # Find user by phone
        user = User.query.filter_by(phone=formatted_phone).first()
        
        if not user:
            flash('No account found with that phone number.', 'error')
            return render_template('auth/login.html')
        
        if user.status != 'active':
            if user.status == 'pending':
                flash('Your account is pending approval. Please contact the treasurer.', 'warning')
            else:
                flash('Your account has been suspended. Please contact the treasurer.', 'error')
            return render_template('auth/login.html')
        
        if not user.check_password(password):
            flash('Incorrect password.', 'error')
            return render_template('auth/login.html')
        
        # Log user in
        login_user(user, remember=True)
        flash(f'Welcome, {user.first_name}!', 'success')
        
        # Redirect to next page or dashboard
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        
        return redirect(url_for('main.dashboard'))
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        # Get form data
        phone = request.form.get('phone', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        errors = []
        
        if not all([phone, first_name, last_name, password, confirm_password]):
            errors.append('All fields except email are required.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        
        # Validate phone number
        formatted_phone = validate_phone(phone)
        if not formatted_phone:
            errors.append('Please enter a valid phone number (10 digits).')
        
        # Check if user already exists
        if formatted_phone:
            existing_user = User.query.filter_by(phone=formatted_phone).first()
            if existing_user:
                errors.append('An account with this phone number already exists.')
        
        # Validate email if provided
        if email and not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            errors.append('Please enter a valid email address.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html')
        
        try:
            # Create new user
            user = User(
                phone=formatted_phone,
                first_name=first_name,
                last_name=last_name,
                email=email if email else None,
                status='pending'  # Requires treasurer approval
            )
            user.set_password(password)
            
            # Add default 'brother' role
            brother_role = Role.query.filter_by(name='brother').first()
            if brother_role:
                user.roles.append(brother_role)
            
            db.session.add(user)
            db.session.commit()
            
            flash('Registration successful! Your account is pending approval by the treasurer. You will be notified when your account is activated.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            print(f"Registration error: {e}")
            return render_template('auth/register.html')
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Log out current user"""
    user_name = current_user.first_name
    logout_user()
    flash(f'Goodbye, {user_name}!', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile management"""
    if request.method == 'POST':
        # Update profile information
        current_user.first_name = request.form.get('first_name', current_user.first_name).strip()
        current_user.last_name = request.form.get('last_name', current_user.last_name).strip()
        
        email = request.form.get('email', '').strip()
        if email and email != current_user.email:
            if re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                current_user.email = email
            else:
                flash('Invalid email address.', 'error')
                return render_template('auth/profile.html')
        
        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error updating profile.', 'error')
    
    return render_template('auth/profile.html')

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return render_template('auth/change_password.html')
        
        if len(new_password) < 8:
            flash('New password must be at least 8 characters long.', 'error')
            return render_template('auth/change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('auth/change_password.html')
        
        try:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('auth.profile'))
        except Exception as e:
            db.session.rollback()
            flash('Error changing password.', 'error')
    
    return render_template('auth/change_password.html')

# Admin Routes (Treasurer only)
@auth_bp.route('/admin/users')
@role_required('treasurer')
def admin_users():
    """Admin page to manage users"""
    pending_users = User.query.filter_by(status='pending').all()
    active_users = User.query.filter_by(status='active').all()
    
    return render_template('auth/admin_users.html', 
                         pending_users=pending_users, 
                         active_users=active_users)

@auth_bp.route('/admin/approve-user/<int:user_id>', methods=['POST'])
@role_required('treasurer')
def approve_user(user_id):
    """Approve a pending user"""
    user = User.query.get_or_404(user_id)
    
    if user.status != 'pending':
        flash('User is not pending approval.', 'error')
        return redirect(url_for('auth.admin_users'))
    
    try:
        user.status = 'active'
        user.approved_by = current_user.id
        user.approved_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'User {user.full_name} has been approved!', 'success')
        
        # TODO: Send approval notification email/SMS
        
    except Exception as e:
        db.session.rollback()
        flash('Error approving user.', 'error')
    
    return redirect(url_for('auth.admin_users'))

@auth_bp.route('/admin/link-member/<int:user_id>', methods=['POST'])
@role_required('treasurer')
def link_member(user_id):
    """Link user account to existing member record"""
    user = User.query.get_or_404(user_id)
    member_id = request.form.get('member_id')
    
    if not member_id:
        flash('Please select a member to link.', 'error')
        return redirect(url_for('auth.admin_users'))
    
    try:
        member = Member.query.get(member_id)
        if not member:
            flash('Member not found.', 'error')
            return redirect(url_for('auth.admin_users'))
        
        # Check if member is already linked
        if member.user_id:
            flash('This member is already linked to another account.', 'error')
            return redirect(url_for('auth.admin_users'))
        
        # Link the accounts
        member.user_id = user.id
        user.status = 'active'  # Approve the user when linking
        user.approved_by = current_user.id
        user.approved_at = datetime.utcnow()
        
        db.session.commit()
        flash(f'User {user.full_name} has been linked to member {member.name}!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error linking user to member.', 'error')
    
    return redirect(url_for('auth.admin_users'))

@auth_bp.route('/admin/suspend-user/<int:user_id>', methods=['POST'])
@role_required('treasurer')
def suspend_user(user_id):
    """Suspend a user account"""
    user = User.query.get_or_404(user_id)
    
    # Prevent suspending treasurer accounts
    if user.has_role('treasurer'):
        flash('Cannot suspend treasurer accounts.', 'error')
        return redirect(url_for('auth.admin_users'))
    
    try:
        user.status = 'suspended'
        db.session.commit()
        flash(f'User {user.full_name} has been suspended.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash('Error suspending user.', 'error')
    
    return redirect(url_for('auth.admin_users'))

@auth_bp.route('/admin/user-roles/<int:user_id>', methods=['GET', 'POST'])
@role_required('treasurer')
def manage_user_roles(user_id):
    """Manage user roles"""
    user = User.query.get_or_404(user_id)
    all_roles = Role.query.all()
    
    if request.method == 'POST':
        # Get selected roles from form
        selected_role_ids = request.form.getlist('roles')
        
        try:
            # Clear existing roles (except treasurer role for protection)
            if not user.has_role('treasurer'):
                user.roles.clear()
            else:
                # Keep treasurer role, remove others
                user.roles = [role for role in user.roles if role.name == 'treasurer']
            
            # Add selected roles
            for role_id in selected_role_ids:
                role = Role.query.get(role_id)
                if role and role not in user.roles:
                    user.roles.append(role)
            
            db.session.commit()
            flash(f'Roles updated for {user.full_name}!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash('Error updating roles.', 'error')
        
        return redirect(url_for('auth.admin_users'))
    
    return render_template('auth/manage_roles.html', user=user, all_roles=all_roles)

# API Routes
@auth_bp.route('/api/check-phone', methods=['POST'])
def check_phone():
    """API endpoint to check if phone number is available"""
    phone = request.json.get('phone', '').strip()
    formatted_phone = validate_phone(phone)
    
    if not formatted_phone:
        return jsonify({'available': False, 'message': 'Invalid phone number format'})
    
    existing_user = User.query.filter_by(phone=formatted_phone).first()
    
    return jsonify({
        'available': existing_user is None,
        'formatted': formatted_phone,
        'message': 'Phone number is available' if existing_user is None else 'Phone number already registered'
    })

@auth_bp.route('/api/unlinked-members')
@role_required('treasurer')
def get_unlinked_members():
    """API endpoint to get members not linked to any user account"""
    unlinked_members = Member.query.filter_by(user_id=None).all()
    
    return jsonify([{
        'id': member.id,
        'name': member.name,
        'contact': member.contact,
        'dues_amount': member.dues_amount
    } for member in unlinked_members])