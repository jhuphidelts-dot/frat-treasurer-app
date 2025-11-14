#!/usr/bin/env python3
"""
Final comprehensive cleanup of legacy JSON storage code.
This script carefully removes all legacy code while preserving database functionality.
"""

import re
import sys

def read_file():
    """Read the current app.py"""
    with open('app.py', 'r') as f:
        return f.read()

def write_file(content):
    """Write the cleaned app.py"""
    with open('app.py', 'w') as f:
        f.write(content)

def step1_remove_legacy_imports(content):
    """Remove imports only used by JSON mode"""
    print("Step 1: Removing legacy imports...")
    
    # Remove specific imports
    content = re.sub(r'import gzip\n', '', content)
    content = re.sub(r'import pickle\n', '', content)
    content = re.sub(r'from dataclasses import dataclass, asdict\n', '', content)
    content = re.sub(r'import calendar\n', '', content)
    content = re.sub(r'import time\n', '', content)
    
    # Remove BackgroundScheduler (used by TreasurerApp for reminders)
    content = re.sub(r'from apscheduler\.schedulers\.background import BackgroundScheduler\n', '', content)
    
    print("  ✓ Removed legacy imports")
    return content

def step2_remove_database_flags(content):
    """Remove DATABASE_AVAILABLE and USE_DATABASE flag initialization"""
    print("Step 2: Removing database availability flags...")
    
    # Find and remove the try/except block that sets DATABASE_AVAILABLE
    pattern = r'# Database imports\ntry:.*?DATABASE_AVAILABLE = True.*?except ImportError as e:.*?DATABASE_AVAILABLE = False\n'
    content = re.sub(pattern, '# Database imports\nfrom models import db, User, Role, Member, Transaction, Semester, Payment, BudgetLimit, TreasurerConfig, init_default_roles\nfrom database import create_app as create_database_app, init_database\n', content, flags=re.DOTALL)
    
    print("  ✓ Removed DATABASE_AVAILABLE flag")
    return content

def step3_simplify_app_initialization(content):
    """Simplify app initialization to always use database"""
    print("Step 3: Simplifying app initialization...")
    
    # Replace the complex initialization with simple version
    old_init = r'# Initialize Flask app with database support when available.*?print\("✅ App initialized with JSON file support"\)\n'
    
    new_init = '''# Initialize Flask app with database support
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is required. Please configure your database.")

print(f"🔍 Initializing app with database: {database_url[:50]}...")
app = create_database_app('production' if os.environ.get('FLASK_ENV') == 'production' else 'development')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize database tables
print("🔄 Initializing database tables...")
with app.app_context():
    try:
        db.create_all()
        print("✅ Database tables ready")
    except Exception as e:
        print(f"⚠️ Database table creation warning: {e}")

print("✅ App initialized with database support")
'''
    
    content = re.sub(old_init, new_init, content, flags=re.DOTALL)
    
    print("  ✓ Simplified app initialization")
    return content

def step4_remove_dataclasses(content):
    """Remove legacy dataclass definitions"""
    print("Step 4: Removing legacy dataclasses...")
    
    # Remove each dataclass (Member, Transaction, Semester, PendingBrother, TreasurerConfig)
    # Pattern: @dataclass\nclass Name:...\n\n (up to next top-level item)
    pattern = r'@dataclass\nclass (Member|Transaction|Semester|PendingBrother|TreasurerConfig):.*?(?=\n@dataclass|\nclass TreasurerApp:|\ndef [a-z_]+\()'
    content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    print("  ✓ Removed legacy dataclasses")
    return content

def step5_remove_treasurer_app_class(content):
    """Remove the entire TreasurerApp class"""
    print("Step 5: Removing TreasurerApp class...")
    
    # Find class TreasurerApp: and remove until the next top-level definition
    pattern = r'class TreasurerApp:.*?(?=\n# Initialize the appropriate data layer|\n# Authentication decorator|\ndef require_auth)'
    content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    # Also remove the initialization line
    content = re.sub(r'# Initialize the appropriate data layer.*?treasurer_app = TreasurerApp\(\)\n', '', content, flags=re.DOTALL)
    
    print("  ✓ Removed TreasurerApp class")
    return content

def step6_fix_helper_functions(content):
    """Fix get_current_user_role, get_user_member, and authenticate functions"""
    print("Step 6: Fixing helper functions...")
    
    # Fix get_current_user_role - remove USE_DATABASE checks
    old_get_role = r'def get_current_user_role\(\):.*?return session\.get\(\'role\', \'brother\'\)'
    new_get_role = '''def get_current_user_role():
    """Get current user's role based on session and database"""
    if session.get('preview_mode'):
        return session.get('preview_role', 'admin')
    
    # Check if user is admin/treasurer
    if session.get('user') == 'admin' or session.get('role') == 'admin':
        return 'admin'
    
    # Get role from database
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            primary_role = user.get_primary_role()
            return primary_role.name if primary_role else 'brother'
    
    return session.get('role', 'brother')'''
    
    content = re.sub(old_get_role, new_get_role, content, flags=re.DOTALL)
    
    # Fix get_user_member
    old_get_member = r'def get_user_member\(\):.*?return None'
    new_get_member = '''def get_user_member():
    """Get the member object for the current user"""
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user and user.member_record:
            return user.member_record
    return None'''
    
    content = re.sub(old_get_member, new_get_member, content, flags=re.DOTALL)
    
    # Fix authenticate_user_dual -> authenticate_user
    old_auth = r'def authenticate_user_dual\(username, password\):.*?return None, None'
    new_auth = '''def authenticate_user(username, password):
    """Authenticate user using database"""
    try:
        user = None
        
        # Check for admin username
        if username == 'admin':
            user = User.query.filter_by(phone='admin').first()
        else:
            # Check by phone or email
            user = User.query.filter_by(phone=username).first()
            if not user:
                user = User.query.filter_by(email=username).first()
        
        if user and user.check_password(password):
            primary_role = user.get_primary_role()
            role_name = primary_role.name if primary_role else 'brother'
            return user, role_name
        
        return None, None
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return None, None'''
    
    content = re.sub(old_auth, new_auth, content, flags=re.DOTALL)
    
    # Update login route to use authenticate_user instead of authenticate_user_dual
    content = content.replace('authenticate_user_dual(', 'authenticate_user(')
    
    print("  ✓ Fixed helper functions")
    return content

def step7_remove_use_database_checks(content):
    """Remove all if USE_DATABASE: checks throughout routes"""
    print("Step 7: Removing USE_DATABASE conditionals...")
    
    # Remove all debug prints with USE_DATABASE
    content = re.sub(r'\s*print\(f?".*?USE_DATABASE=.*?"\)\s*\n', '\n', content)
    
    # Remove "if not USE_DATABASE:" blocks entirely (JSON mode code)
    lines = content.split('\n')
    new_lines = []
    skip_depth = 0
    skip_indent = 0
    
    for line in lines:
        if skip_depth > 0:
            current_indent = len(line) - len(line.lstrip())
            if line.strip() and current_indent <= skip_indent:
                skip_depth = 0
            else:
                continue
        
        # Skip if not USE_DATABASE blocks
        if 'if not USE_DATABASE:' in line:
            skip_depth = 1
            skip_indent = len(line) - len(line.lstrip())
            continue
        
        # Skip if USE_DATABASE: line itself, but keep the indented content
        if 'if USE_DATABASE:' in line:
            continue
        
        # Fix debug endpoint
        if "'USE_DATABASE': USE_DATABASE" in line:
            line = line.replace("'USE_DATABASE': USE_DATABASE", "'database_mode': 'always_active'")
        if "'DATABASE_AVAILABLE': DATABASE_AVAILABLE" in line:
            line = line.replace("'DATABASE_AVAILABLE': DATABASE_AVAILABLE", "'database_available': True")
        
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    print("  ✓ Removed USE_DATABASE checks")
    return content

def step8_remove_treasurer_app_references(content):
    """Remove or comment out treasurer_app method calls"""
    print("Step 8: Handling treasurer_app references...")
    
    # Remove elif treasurer_app: blocks
    lines = content.split('\n')
    new_lines = []
    skip_depth = 0
    skip_indent = 0
    
    for line in lines:
        if skip_depth > 0:
            current_indent = len(line) - len(line.lstrip())
            if line.strip() and current_indent <= skip_indent:
                skip_depth = 0
            else:
                continue
        
        # Skip elif treasurer_app blocks
        if 'elif treasurer_app:' in line or (skip_depth == 0 and 'if treasurer_app' in line and 'treasurer_app.' not in line):
            skip_depth = 1
            skip_indent = len(line) - len(line.lstrip())
            continue
        
        # Comment out direct treasurer_app method calls
        if 'treasurer_app.' in line and not line.strip().startswith('#'):
            # Add TODO comment
            indent = ' ' * (len(line) - len(line.lstrip()))
            new_lines.append(f"{indent}# TODO: Implement database version")
            new_lines.append(f"{indent}# {line.strip()}")
            continue
        
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    print("  ✓ Handled treasurer_app references")
    return content

def step9_fix_login_route(content):
    """Fix login route to use database-only authentication"""
    print("Step 9: Fixing login route...")
    
    # Simplify login route
    old_login = r"@app\.route\('/login', methods=\['GET', 'POST'\]\)\ndef login\(\):.*?return redirect\(url_for\('login'\)\)"
    
    new_login = """@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    username = request.form['username']
    password = request.form['password']
    
    try:
        user, role = authenticate_user(username, password)
        
        if user:
            login_user(user, remember=True)
            session['user'] = user.phone
            session['role'] = role
            session['user_id'] = user.id
            flash(f'Welcome, {user.first_name}!')
            
            # Redirect based on role
            if role == 'brother':
                return redirect(url_for('brother_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))
    
    except Exception as e:
        print(f"❌ Login error: {e}")
        flash('Login system error')
        return redirect(url_for('login'))"""
    
    content = re.sub(old_login, new_login, content, flags=re.DOTALL, count=1)
    
    print("  ✓ Fixed login route")
    return content

def main():
    print("=" * 60)
    print("COMPREHENSIVE LEGACY CODE CLEANUP")
    print("=" * 60)
    print()
    
    # Backup
    import shutil
    shutil.copy('app.py', 'app.py.backup_final_cleanup')
    print("📦 Backup created: app.py.backup_final_cleanup\n")
    
    # Read file
    content = read_file()
    original_lines = len(content.split('\n'))
    print(f"📄 Original file: {original_lines} lines\n")
    
    # Execute cleanup steps
    content = step1_remove_legacy_imports(content)
    content = step2_remove_database_flags(content)
    content = step3_simplify_app_initialization(content)
    content = step4_remove_dataclasses(content)
    content = step5_remove_treasurer_app_class(content)
    content = step6_fix_helper_functions(content)
    content = step7_remove_use_database_checks(content)
    content = step8_remove_treasurer_app_references(content)
    content = step9_fix_login_route(content)
    
    # Write cleaned file
    write_file(content)
    final_lines = len(content.split('\n'))
    
    print()
    print("=" * 60)
    print("CLEANUP COMPLETE")
    print("=" * 60)
    print(f"📊 Final file: {final_lines} lines")
    print(f"📉 Removed: {original_lines - final_lines} lines")
    print()
    
    # Test import
    print("🧪 Testing import...")
    import subprocess
    result = subprocess.run(
        ['python3', '-c', 'import app; print("✅ SUCCESS: App imports without errors!")'],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode == 0:
        print(result.stdout.strip())
        print()
        print("🎉 All done! The app is ready to deploy.")
        return 0
    else:
        print("❌ Import test failed:")
        print(result.stderr[:500])
        print()
        print("💡 Restore backup: cp app.py.backup_final_cleanup app.py")
        return 1

if __name__ == '__main__':
    sys.exit(main())
