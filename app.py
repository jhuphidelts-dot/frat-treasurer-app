from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
import os
from apscheduler.schedulers.background import BackgroundScheduler
import json
import gzip
import pickle
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import uuid
from dotenv import load_dotenv
import hashlib
import re
import calendar
import time

# Import Flask blueprints
# from notifications import notifications_bp  # Commented out due to compatibility issues
from export_system import export_bp
from chair_management import chair_bp
from executive_views import exec_bp


# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")  # needed for flash()

# Register blueprints
# app.register_blueprint(notifications_bp)  # Commented out due to compatibility issues
app.register_blueprint(export_bp)
app.register_blueprint(chair_bp)
app.register_blueprint(exec_bp)

# SMS Gateway mappings for email-to-SMS (Updated and optimized)
SMS_GATEWAYS = {
    'verizon': '@vtext.com',
    'att': '@txt.att.net', 
    'tmobile': '@tmomail.net',
    'sprint': '@messaging.sprintpcs.com',  # Now T-Mobile
    'boost': '@smsmyboostmobile.com',
    'cricket': '@sms.cricketwireless.net',
    'uscellular': '@email.uscc.net',
    'virgin': '@vmobl.com',
    'metropcs': '@mymetropcs.com',
    # Additional gateways for better coverage
    'google_fi': '@msg.fi.google.com',
    'xfinity': '@vtext.com',
    'straighttalk': '@vtext.com'
}

# Primary gateways that work most reliably
PRIMARY_GATEWAYS = ['verizon', 'att', 'tmobile']

def send_email_to_sms(phone, message, config):
    """Send SMS via email-to-SMS gateway with improved error handling"""
    if not config.smtp_username or not config.smtp_password:
        print("SMS Error: SMTP credentials not configured")
        return False
    
    # Clean and validate phone number
    clean_phone = ''.join(filter(str.isdigit, phone))
    if len(clean_phone) == 11 and clean_phone.startswith('1'):
        clean_phone = clean_phone[1:]  # Remove leading 1
    elif len(clean_phone) != 10:
        print(f"SMS Error: Invalid phone number format: {phone}")
        return False
    
    # Limit message length for SMS compatibility
    if len(message) > 160:
        message = message[:157] + "..."
    
    # Try primary gateways first (most reliable)
    gateways_to_try = [(name, SMS_GATEWAYS[name]) for name in PRIMARY_GATEWAYS]
    
    success_count = 0
    last_error = None
    
    for carrier, gateway in gateways_to_try:
        try:
            sms_email = clean_phone + gateway
            print(f"Attempting SMS via {carrier} to {sms_email}")
            
            # Create email message
            msg = MIMEText(message)
            msg['Subject'] = ''  # Empty subject for SMS
            msg['From'] = config.smtp_username
            msg['To'] = sms_email
            
            # Send via SMTP with timeout settings
            server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)  # 10 second timeout
            server.set_debuglevel(0)  # Disable debug for production
            server.starttls()
            server.login(config.smtp_username, config.smtp_password)
            server.send_message(msg)
            server.quit()
            
            success_count += 1
            print(f"SMS sent successfully via {carrier}")
            
            # Don't try other gateways if one succeeds
            break
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"SMS Error ({carrier}): Authentication failed - check Gmail app password")
            last_error = f"Authentication failed: {str(e)}"
            break  # No point trying other gateways if auth fails
        except smtplib.SMTPException as e:
            print(f"SMS Error ({carrier}): SMTP error - {str(e)}")
            last_error = f"SMTP error: {str(e)}"
            continue  # Try next gateway
        except Exception as e:
            print(f"SMS Error ({carrier}): {str(e)}")
            last_error = f"General error: {str(e)}"
            continue  # Try next gateway
    
    if success_count == 0:
        print(f"SMS Failed: All gateways failed. Last error: {last_error}")
    
    return success_count > 0

def notify_treasurer(message, config, notification_type="Alert"):
    """Send notification to treasurer via SMS and email"""
    if not config.name:
        return False
    
    sent = False
    
    # Send email to treasurer
    if config.email and config.smtp_username and config.smtp_password:
        try:
            msg = MIMEText(f"Fraternity Treasurer {notification_type}:\n\n{message}")
            msg['Subject'] = f'Fraternity Treasurer {notification_type}'
            msg['From'] = config.smtp_username
            msg['To'] = config.email
            
            server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
            server.starttls()
            server.login(config.smtp_username, config.smtp_password)
            server.send_message(msg)
            server.quit()
            sent = True
        except Exception:
            pass
    
    # Send SMS to treasurer
    if config.phone:
        sms_message = f"Treasurer {notification_type}: {message[:100]}..." if len(message) > 100 else f"Treasurer {notification_type}: {message}"
        if send_email_to_sms(config.phone, sms_message, config):
            sent = True
    
    return sent

def notify_payment_plan_request(member_name, plan_details, config):
    """Notify treasurer about payment plan request"""
    message = f"{member_name} has submitted a payment plan request:\n{plan_details}\n\nPlease review and approve in the app."
    return notify_treasurer(message, config, "Payment Plan Request")

def notify_reimbursement_request(submitter_name, amount, category, description, config):
    """Notify treasurer about reimbursement request"""
    message = f"{submitter_name} has submitted a reimbursement request:\n\nAmount: ${amount:.2f}\nCategory: {category}\nDescription: {description}\n\nPlease review and approve in the app."
    return notify_treasurer(message, config, "Reimbursement Request")

def notify_spending_plan_request(submitter_name, category, amount, description, config):
    """Notify treasurer about spending plan request"""
    message = f"{submitter_name} has submitted a spending plan request:\n\nCategory: {category}\nAmount: ${amount:.2f}\nDescription: {description}\n\nPlease review and approve in the app."
    return notify_treasurer(message, config, "Spending Plan Request")

def send_brother_credentials_sms(full_name, phone, username, password, config):
    """Send login credentials to approved brother via SMS with enhanced logging"""
    print(f"\n🔐 Starting brother credentials SMS process...")
    print(f"   Full name: {full_name}")
    print(f"   Phone: {phone}")
    print(f"   Username: {username}")
    
    if not config.smtp_username or not config.smtp_password:
        print("❌ Brother SMS Error: SMTP credentials not configured")
        print(f"   SMTP Username: {config.smtp_username}")
        print(f"   SMTP Password configured: {bool(config.smtp_password)}")
        return False
    
    # Create concise SMS message (SMS has 160 char limit)
    first_name = full_name.split()[0] if full_name else "Brother"
    message = f"Fraternity Account Approved! Hi {first_name}, Login: {username} Pass: {password} Change password after first login."
    
    # Check message length
    if len(message) > 160:
        # Create shorter version
        message = f"Account approved! {first_name}, Login: {username} Pass: {password}"
        print(f"📏 Message shortened to {len(message)} chars: {message}")
    else:
        print(f"📏 Message length OK: {len(message)} chars")
    
    print(f"📱 Sending brother credentials to {first_name} at {phone}")
    
    # Send SMS via email-to-SMS gateway with enhanced error reporting
    success = send_email_to_sms(phone, message, config)
    
    if success:
        print(f"✅ Brother credentials SMS sent successfully to {phone}")
    else:
        print(f"❌ Brother credentials SMS failed to {phone}")
        print(f"🔧 Debug: Config status - SMTP User: {config.smtp_username}, Phone: {phone}")
    
    return success

# Role-based access control for member roles
MEMBER_ROLE_PERMISSIONS = {
    'admin': {
        # Full admin permissions (treasurer)
        'view_all_data': True,
        'edit_all_data': True,
        'manage_users': True,
        'send_reminders': True,
        'add_transactions': True,
        'edit_transactions': True,
        'add_members': True,
        'edit_members': True,
        'record_payments': True,
        'manage_budgets': True,
        'assign_roles': True,
    },
    'brother': {
        # Basic brother access
        'view_all_data': False,
        'view_own_data': True,
        'view_dues_info': True,
        'edit_all_data': False,
        'manage_users': False,
        'send_reminders': False,
        'add_transactions': False,
        'edit_transactions': False,
        'add_members': False,
        'edit_members': False,
        'record_payments': False,
        'manage_budgets': False,
        'assign_roles': False,
    },
    'president': {
        # President access - read all financial data
        'view_all_data': True,
        'view_own_data': True,
        'view_dues_info': True,
        'edit_all_data': False,
        'manage_users': False,
        'send_reminders': False,
        'add_transactions': False,
        'edit_transactions': False,
        'add_members': False,
        'edit_members': False,
        'record_payments': False,
        'manage_budgets': False,
        'assign_roles': False,
    },
    'vice_president': {
        # VP access - can only view own data and general info, NOT individual dues
        'view_all_data': False,
        'view_own_data': True,
        'view_dues_info': False,  # No individual dues access
        'view_general_budget': True,  # Can see general budget info
        'edit_all_data': False,
        'manage_users': False,
        'send_reminders': False,
        'add_transactions': False,
        'edit_transactions': False,
        'add_members': False,
        'edit_members': False,
        'record_payments': False,
        'manage_budgets': False,
        'assign_roles': False,
    },
    'social_chair': {
        # Social chair - view social budget and expenses only
        'view_all_data': False,
        'view_own_data': True,
        'view_dues_info': False,  # No individual dues access
        'view_social_budget': True,
        'edit_all_data': False,
        'manage_users': False,
        'send_reminders': False,
        'add_transactions': False,
        'edit_transactions': False,
        'add_members': False,
        'edit_members': False,
        'record_payments': False,
        'manage_budgets': False,
        'assign_roles': False,
    },
    'phi_ed_chair': {
        # Phi Ed chair access
        'view_all_data': False,
        'view_own_data': True,
        'view_dues_info': False,  # No individual dues access
        'view_phi_ed_budget': True,
        'edit_all_data': False,
        'manage_users': False,
        'send_reminders': False,
        'add_transactions': False,
        'edit_transactions': False,
        'add_members': False,
        'edit_members': False,
        'record_payments': False,
        'manage_budgets': False,
        'assign_roles': False,
    },
    'brotherhood_chair': {
        # Brotherhood chair access
        'view_all_data': False,
        'view_own_data': True,
        'view_dues_info': False,  # No individual dues access
        'view_brotherhood_budget': True,
        'edit_all_data': False,
        'manage_users': False,
        'send_reminders': False,
        'add_transactions': False,
        'edit_transactions': False,
        'add_members': False,
        'edit_members': False,
        'record_payments': False,
        'manage_budgets': False,
        'assign_roles': False,
    },
    'recruitment_chair': {
        # Recruitment chair access
        'view_all_data': False,
        'view_own_data': True,
        'view_dues_info': False,  # No individual dues access
        'view_recruitment_budget': True,
        'edit_all_data': False,
        'manage_users': False,
        'send_reminders': False,
        'add_transactions': False,
        'edit_transactions': False,
        'add_members': False,
        'edit_members': False,
        'record_payments': False,
        'manage_budgets': False,
        'assign_roles': False,
    },
    'treasurer': {
        # Treasurer access - same as admin but assigned as member role
        'view_all_data': True,
        'edit_all_data': True,
        'manage_users': True,
        'send_reminders': True,
        'add_transactions': True,
        'edit_transactions': True,
        'add_members': True,
        'edit_members': True,
        'record_payments': True,
        'manage_budgets': True,
        'assign_roles': True,
    }
}

# Legacy role permissions for backwards compatibility
ROLE_PERMISSIONS = {
    'admin': MEMBER_ROLE_PERMISSIONS['admin'],
    'brother': MEMBER_ROLE_PERMISSIONS['brother'],
    'president': MEMBER_ROLE_PERMISSIONS['president']
}

def get_current_user_role():
    """Get current user's role based on session and member data"""
    if session.get('preview_mode'):
        return session.get('preview_role', 'admin')
    
    # Check if user is admin/treasurer
    if session.get('user') == 'admin' or session.get('role') == 'admin':
        return 'admin'
    
    # For brother accounts, get role from linked member
    user_id = session.get('user')
    if user_id:
        member = treasurer_app.get_member_by_user_id(user_id)
        if member and hasattr(member, 'role'):
            return member.role
    
    # Fallback to session role or default
    return session.get('role', 'brother')

def has_permission(permission_name):
    """Check if current user has a specific permission"""
    role = get_current_user_role()
    
    # Check member role permissions first
    if role in MEMBER_ROLE_PERMISSIONS:
        return MEMBER_ROLE_PERMISSIONS[role].get(permission_name, False)
    
    # Fallback to legacy role permissions
    return ROLE_PERMISSIONS.get(role, {}).get(permission_name, False)

def get_user_member():
    """Get the member object for the current user"""
    user_id = session.get('user')
    if user_id:
        return treasurer_app.get_member_by_user_id(user_id)
    return None

def require_permission(permission_name):
    """Decorator to require specific permission for route access"""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not has_permission(permission_name):
                flash(f'You do not have permission to {permission_name.replace("_", " ")}. This action is restricted to treasurers only.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Configuration
BUDGET_CATEGORIES = [
    'Executive(GHQ, IFC, Flights)', 'Brotherhood', 'Social', 
    'Philanthropy', 'Recruitment', 'Phi ED', 'Housing', 'Bank Maintenance'
]

@dataclass
class Member:
    id: str
    name: str
    contact: str  # Can be phone or email
    dues_amount: float
    payment_plan: str  # 'monthly', 'semester', 'custom'
    custom_schedule: Optional[List[dict]] = None
    payments_made: List[dict] = None
    contact_type: str = 'phone'  # 'phone' or 'email'
    semester_id: str = 'current'  # Links to specific semester
    role: str = 'brother'  # 'brother', 'president', 'vice_president', 'social_chair', 'phi_ed_chair', 'recruitment_chair', 'brotherhood_chair'
    user_id: Optional[str] = None  # Link to user account if they have one
    
    def __post_init__(self):
        if self.payments_made is None:
            self.payments_made = []
        # Auto-detect contact type if not specified
        if self.contact_type == 'phone':
            if '@' in self.contact and '.' in self.contact:
                self.contact_type = 'email'

@dataclass
class Transaction:
    id: str
    date: str
    category: str
    description: str
    amount: float
    type: str  # 'income' or 'expense'
    semester_id: str = 'current'  # Links to specific semester

@dataclass
class Semester:
    id: str
    name: str  # e.g., "Fall 2024", "Spring 2025"
    year: int
    season: str  # 'Fall', 'Spring', 'Summer'
    start_date: str
    end_date: str
    is_current: bool = False
    archived: bool = False

@dataclass
class PendingBrother:
    id: str
    full_name: str
    phone: str
    email: str
    registration_date: str
    verification_token: str
    is_verified: bool = False
    member_id: Optional[str] = None  # Links to Member once verified
    user_id: Optional[str] = None  # Links to User account once approved

@dataclass
class TreasurerConfig:
    name: str = ""
    email: str = ""
    phone: str = ""  # Treasurer's phone for notifications
    smtp_username: str = ""
    smtp_password: str = ""

class TreasurerApp:
    def __init__(self):
        try:
            self.data_dir = os.path.join(os.path.dirname(__file__), 'data')
            self.members_file = os.path.join(self.data_dir, 'members.json')
            self.transactions_file = os.path.join(self.data_dir, 'transactions.json')
            self.budget_file = os.path.join(self.data_dir, 'budget.json')
            self.users_file = os.path.join(self.data_dir, 'users.json')
            self.semesters_file = os.path.join(self.data_dir, 'semesters.json')
            self.treasurer_config_file = os.path.join(self.data_dir, 'treasurer_config.json')
            self.pending_brothers_file = os.path.join(self.data_dir, 'pending_brothers.json')
            
            print(f"📁 Data directory: {self.data_dir}")
            
            # Create data directory if it doesn't exist
            os.makedirs(self.data_dir, exist_ok=True)
            print(f"✅ Data directory created/verified")
        
            # Load existing data or initialize empty
            print(f"📄 Loading data files...")
            self.members = self.load_data(self.members_file, {})
            print(f"✅ Members loaded: {len(self.members)} members")
            
            self.transactions = self.load_data(self.transactions_file, [])
            print(f"✅ Transactions loaded: {len(self.transactions)} transactions")
            
            self.budget_limits = self.load_data(self.budget_file, {category: 0.0 for category in BUDGET_CATEGORIES})
            print(f"✅ Budget limits loaded")
            
            self.users = self.load_data(self.users_file, {})
            print(f"✅ Users loaded: {len(self.users)} users")
            
            self.semesters = self.load_data(self.semesters_file, {})
            print(f"✅ Semesters loaded: {len(self.semesters)} semesters")
            
            self.treasurer_config = self.load_treasurer_config()
            print(f"✅ Treasurer config loaded")
            
            self.pending_brothers = self.load_data(self.pending_brothers_file, {})
            print(f"✅ Pending brothers loaded: {len(self.pending_brothers)} pending")
        
            # Create default admin user if no users exist
            if not self.users:
                print(f"👤 Creating default admin user...")
                self.create_user('admin', 'admin123', 'admin')
                print(f"✅ Default admin user created")
            
            # Initialize current semester if none exists
            if not self.semesters:
                print(f"📅 Creating default semester...")
                self.create_default_semester()
                print(f"✅ Default semester created")
            
            self.current_semester = self.get_current_semester()
            print(f"✅ Current semester set")
            
            # Initialize scheduler with error handling
            try:
                print(f"⏰ Starting background scheduler...")
                self.scheduler = BackgroundScheduler()
                self.scheduler.start()
                self.setup_reminders()
                print(f"✅ Background scheduler started")
            except Exception as e:
                print(f"⚠️ Scheduler failed to start: {e} (continuing without scheduler)")
                self.scheduler = None
            
            # Auto-optimize storage on startup (lightweight check)
            try:
                self._auto_optimize_if_needed()
                print(f"✅ Storage optimization check completed")
            except Exception as e:
                print(f"⚠️ Storage optimization failed: {e} (continuing)")
            
            print(f"🎉 TreasurerApp initialization completed successfully!")
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR during TreasurerApp initialization: {e}")
            import traceback
            traceback.print_exc()
            raise

    def load_data(self, file_path, default_data):
        # Check for compressed version first
        compressed_path = file_path + '.gz'
        
        if os.path.exists(compressed_path):
            with gzip.open(compressed_path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
        elif os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
        else:
            return default_data
        
        if data:
                # Convert loaded members back to Member objects if needed
                if 'members.json' in file_path and data:
                    loaded_members = {}
                    for member_id, member_data in data.items():
                        # Handle legacy 'phone' field by converting to 'contact'
                        contact = member_data.get('contact', member_data.get('phone', ''))
                        contact_type = member_data.get('contact_type', 'phone')
                        
                        loaded_members[member_id] = Member(
                            id=member_data['id'],
                            name=member_data['name'],
                            contact=contact,
                            dues_amount=member_data['dues_amount'],
                            payment_plan=member_data['payment_plan'],
                            custom_schedule=member_data.get('custom_schedule', []),
                            payments_made=member_data.get('payments_made', []),
                            contact_type=contact_type,
                            semester_id=member_data.get('semester_id', 'current'),
                            role=member_data.get('role', 'brother'),
                            user_id=member_data.get('user_id')
                        )
                    return loaded_members
                # Convert loaded transactions back to Transaction objects if needed
                elif 'transactions.json' in file_path and data:
                    loaded_transactions = []
                    for trans_data in data:
                        loaded_transactions.append(Transaction(
                            id=trans_data['id'],
                            date=trans_data['date'],
                            category=trans_data['category'],
                            description=trans_data['description'],
                            amount=trans_data['amount'],
                            type=trans_data['type']
                        ))
                    return loaded_transactions
                # Convert loaded semesters back to Semester objects if needed
                elif 'semesters.json' in file_path and data:
                    loaded_semesters = {}
                    for semester_id, semester_data in data.items():
                        loaded_semesters[semester_id] = Semester(
                            id=semester_data['id'],
                            name=semester_data['name'],
                            year=semester_data['year'],
                            season=semester_data['season'],
                            start_date=semester_data['start_date'],
                            end_date=semester_data.get('end_date', ''),
                            is_current=semester_data.get('is_current', False),
                            archived=semester_data.get('archived', False)
                        )
                    return loaded_semesters
                # Convert loaded pending brothers back to PendingBrother objects if needed
                elif 'pending_brothers.json' in file_path and data:
                    loaded_pending = {}
                    for pending_id, pending_data in data.items():
                        loaded_pending[pending_id] = PendingBrother(
                            id=pending_data['id'],
                            full_name=pending_data['full_name'],
                            phone=pending_data['phone'],
                            email=pending_data['email'],
                            registration_date=pending_data['registration_date'],
                            verification_token=pending_data['verification_token'],
                            is_verified=pending_data.get('is_verified', False),
                            member_id=pending_data.get('member_id'),
                            user_id=pending_data.get('user_id')
                        )
                    return loaded_pending
                return data
        return default_data
    
    def load_treasurer_config(self):
        """Load treasurer configuration from file or environment"""
        config = TreasurerConfig()
        
        # Try to load from file first
        if os.path.exists(self.treasurer_config_file):
            try:
                with open(self.treasurer_config_file, 'r') as f:
                    config_data = json.load(f)
                    config.name = config_data.get('name', '')
                    config.email = config_data.get('email', '')
                    config.phone = config_data.get('phone', '')
                    config.smtp_username = config_data.get('smtp_username', '')
                    config.smtp_password = config_data.get('smtp_password', '')
            except Exception as e:
                print(f"Error loading treasurer config: {e}")
        
        # Fallback to environment variables if not in file
        if not config.smtp_username:
            config.smtp_username = os.getenv('SMTP_USERNAME', '')
        if not config.smtp_password:
            config.smtp_password = os.getenv('SMTP_PASSWORD', '')
        
        return config
    
    def save_treasurer_config(self):
        """Save treasurer configuration to file"""
        config_data = asdict(self.treasurer_config)
        with open(self.treasurer_config_file, 'w') as f:
            json.dump(config_data, f, indent=4)
    
    def compress_data(self, data):
        """Compress data using gzip"""
        json_str = json.dumps(data, separators=(',', ':'))  # Compact JSON
        return gzip.compress(json_str.encode('utf-8'))
    
    def decompress_data(self, compressed_data):
        """Decompress gzipped data"""
        json_str = gzip.decompress(compressed_data).decode('utf-8')
        return json.loads(json_str)
    
    def should_compress_file(self, file_path):
        """Check if file should be compressed based on size"""
        if not os.path.exists(file_path):
            return False
        file_size = os.path.getsize(file_path)
        return file_size > 5 * 1024  # Compress files larger than 5KB
    
    def cleanup_old_files(self):
        """Remove unnecessary files to save space"""
        files_to_remove = [
            '.DS_Store',
            '__pycache__',
            '*.pyc',
            '*.pyo',
            'test_*.py'
        ]
        
        for root, dirs, files in os.walk(self.data_dir.replace('data', '')):
            # Remove __pycache__ directories
            if '__pycache__' in dirs:
                import shutil
                shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)
            
            # Remove specific files
            for file in files:
                if any(file.startswith(pattern.replace('*', '')) or file == pattern for pattern in files_to_remove):
                    try:
                        os.remove(os.path.join(root, file))
                        print(f"Removed: {file}")
                    except Exception:
                        pass
    
    def optimize_data_storage(self):
        """Aggressive data storage optimization for Render deployment"""
        print("\n💾 OPTIMIZING STORAGE FOR RENDER DEPLOYMENT")
        print("=" * 60)
        
        # Get initial storage usage
        initial_size = self._get_data_directory_size()
        print(f"📁 Initial data directory size: {initial_size / 1024:.1f} KB")
        
        # Recompress all data files with maximum compression
        data_files = [
            (self.members_file, "Members"),
            (self.transactions_file, "Transactions"), 
            (self.budget_file, "Budget"),
            (self.semesters_file, "Semesters"),
            (self.pending_brothers_file, "Pending Brothers"),
            (self.users_file, "Users")
        ]
        
        for file_path, file_type in data_files:
            if os.path.exists(file_path) or os.path.exists(file_path + '.gz'):
                print(f"\n🗜 Optimizing {file_type}...")
                try:
                    # Load data
                    data = self.load_data(file_path, {} if file_type != "Transactions" else [])
                    
                    if data and len(data) > 0:
                        # Force recompression with maximum settings
                        old_size = 0
                        if os.path.exists(file_path):
                            old_size = os.path.getsize(file_path)
                        elif os.path.exists(file_path + '.gz'):
                            old_size = os.path.getsize(file_path + '.gz')
                        
                        self.save_data(file_path, data)
                        
                        new_size = 0
                        if os.path.exists(file_path):
                            new_size = os.path.getsize(file_path)
                        elif os.path.exists(file_path + '.gz'):
                            new_size = os.path.getsize(file_path + '.gz')
                        
                        if old_size > 0:
                            savings = old_size - new_size
                            print(f"   {old_size} -> {new_size} bytes (saved {savings} bytes)")
                        else:
                            print(f"   Size: {new_size} bytes")
                    else:
                        print(f"   No data to optimize")
                        
                except Exception as e:
                    print(f"   ❌ Error optimizing {file_type}: {e}")
        
        # Aggressive cleanup of unnecessary files
        print(f"\n🧹 Cleaning up unnecessary files...")
        cleanup_count = self._aggressive_cleanup()
        print(f"   Removed {cleanup_count} unnecessary files")
        
        # Remove old backup files if space is tight
        backup_count = self._cleanup_old_backups()
        print(f"   Removed {backup_count} old backup files")
        
        # Final storage report
        final_size = self._get_data_directory_size()
        savings = initial_size - final_size
        savings_percent = (savings / initial_size * 100) if initial_size > 0 else 0
        
        print(f"\n🎉 STORAGE OPTIMIZATION COMPLETE")
        print(f"   Before: {initial_size / 1024:.1f} KB")
        print(f"   After:  {final_size / 1024:.1f} KB")
        print(f"   Saved:  {savings / 1024:.1f} KB ({savings_percent:.1f}%)")
        print(f"   Total data directory size: {final_size / 1024:.1f} KB")
        
        # Warning if still too large
        if final_size > 50 * 1024 * 1024:  # 50MB warning
            print(f"\n⚠️ WARNING: Data directory is {final_size / 1024 / 1024:.1f} MB")
            print(f"   Consider archiving old data for Render deployment")
        
        return final_size
    
    def _get_data_directory_size(self):
        """Calculate total size of data directory"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.data_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except (OSError, FileNotFoundError):
                    pass
        return total_size
    
    def _aggressive_cleanup(self):
        """Aggressively clean up unnecessary files"""
        cleanup_count = 0
        patterns_to_remove = [
            '*.pyc', '*.pyo', '*.pyd', '__pycache__',
            '.DS_Store', '._.DS_Store', 'Thumbs.db',
            '*.tmp', '*.temp', '*.log', '*.bak',
            '.pytest_cache', '.coverage', '*.backup.backup'  # Double backups
        ]
        
        for root, dirs, files in os.walk(self.data_dir.replace('/data', '')):
            # Remove cache directories
            if '__pycache__' in dirs:
                import shutil
                cache_path = os.path.join(root, '__pycache__')
                try:
                    shutil.rmtree(cache_path)
                    cleanup_count += 1
                except Exception:
                    pass
                dirs.remove('__pycache__')
            
            # Remove unwanted files
            for file in files:
                file_path = os.path.join(root, file)
                should_remove = False
                
                for pattern in patterns_to_remove:
                    if pattern.startswith('*.'):
                        if file.endswith(pattern[1:]):
                            should_remove = True
                            break
                    elif file == pattern:
                        should_remove = True
                        break
                
                if should_remove:
                    try:
                        os.remove(file_path)
                        cleanup_count += 1
                    except Exception:
                        pass
        
        return cleanup_count
    
    def _cleanup_old_backups(self):
        """Remove old backup files to save space"""
        backup_count = 0
        backup_extensions = ['.backup', '.bak']
        
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                for ext in backup_extensions:
                    if file.endswith(ext):
                        file_path = os.path.join(root, file)
                        try:
                            # Keep only recent backups (created in last 7 days)
                            file_age = time.time() - os.path.getctime(file_path)
                            if file_age > 7 * 24 * 60 * 60:  # 7 days
                                os.remove(file_path)
                                backup_count += 1
                        except Exception:
                            pass
        
        return backup_count
    
    def _auto_optimize_if_needed(self):
        """Automatically optimize if files are getting large"""
        try:
            # Check if members file is large and uncompressed
            if os.path.exists(self.members_file) and not os.path.exists(self.members_file + '.gz'):
                file_size = os.path.getsize(self.members_file)
                if file_size > 10 * 1024:  # 10KB threshold
                    print("Auto-optimizing storage...")
                    self.optimize_data_storage()
        except Exception:
            pass  # Fail silently to not interrupt startup
    
    def create_default_semester(self):
        """Create the initial semester"""
        from datetime import datetime
        current_date = datetime.now()
        
        # Determine semester based on month
        if current_date.month >= 8:  # August onwards = Fall
            season = 'Fall'
            year = current_date.year
        elif current_date.month <= 5:  # January to May = Spring
            season = 'Spring'
            year = current_date.year
        else:  # June-July = Summer
            season = 'Summer'
            year = current_date.year
        
        semester_id = f"{season.lower()}_{year}"
        semester = Semester(
            id=semester_id,
            name=f"{season} {year}",
            year=year,
            season=season,
            start_date=current_date.isoformat(),
            end_date="",  # To be set later
            is_current=True
        )
        
        self.semesters[semester_id] = semester
        self.save_data(self.semesters_file, self.semesters)
    
    def get_current_semester(self):
        """Get the current active semester"""
        for semester in self.semesters.values():
            if hasattr(semester, 'is_current') and semester.is_current:
                return semester
        
        # If no current semester found, create one
        if self.semesters:
            # Use the most recent semester
            latest_semester = max(self.semesters.values(), 
                                key=lambda s: s.year if hasattr(s, 'year') else 0)
            latest_semester.is_current = True
            return latest_semester
        else:
            self.create_default_semester()
            return self.get_current_semester()

    def save_data(self, file_path, data):
        """Enhanced save_data with backup, compression, and error recovery"""
        print(f"\n💾 SAVING DATA: {os.path.basename(file_path)}")
        print(f"   Data size: {len(str(data))} items")
        
        # Convert objects to dictionaries for JSON serialization
        if 'members.json' in file_path:
            serialized_data = {}
            for member_id, member in data.items():
                serialized_data[member_id] = asdict(member)
        elif 'transactions.json' in file_path:
            serialized_data = [asdict(transaction) for transaction in data]
        elif 'semesters.json' in file_path:
            serialized_data = {}
            for semester_id, semester in data.items():
                serialized_data[semester_id] = asdict(semester)
        elif 'pending_brothers.json' in file_path:
            serialized_data = {}
            for pending_id, pending_brother in data.items():
                serialized_data[pending_id] = asdict(pending_brother)
        else:
            serialized_data = data
        
        # Create backup before saving (for critical data)
        backup_created = False
        if 'members.json' in file_path or 'users.json' in file_path:
            try:
                self._create_backup(file_path)
                backup_created = True
                print(f"   ✅ Backup created")
            except Exception as e:
                print(f"   ⚠️ Backup failed: {e}")
        
        # Determine if compression is needed (optimize for Render space limits)
        json_size = len(json.dumps(serialized_data, separators=(',', ':')))
        should_compress = json_size > 3000  # Lower threshold for better space efficiency
        
        try:
            if should_compress:
                compressed_path = file_path + '.gz'
                print(f"   🗜 Compressing: {json_size} bytes -> ", end="")
                
                with gzip.open(compressed_path, 'wt', encoding='utf-8') as f:
                    json.dump(serialized_data, f, separators=(',', ':'))  # Most compact JSON
                
                compressed_size = os.path.getsize(compressed_path)
                compression_ratio = (1 - compressed_size / json_size) * 100
                print(f"{compressed_size} bytes ({compression_ratio:.1f}% saved)")
                
                # Remove uncompressed version to save space
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"   🗑️ Removed uncompressed version")
            else:
                # Save normally for small files
                with open(file_path, 'w') as f:
                    json.dump(serialized_data, f, separators=(',', ':'))  # Compact JSON
                print(f"   💾 Saved uncompressed: {json_size} bytes")
            
            # Verify the save worked
            test_load = self.load_data(file_path, None)
            if test_load is None or (isinstance(test_load, (dict, list)) and len(test_load) == 0 and len(serialized_data) > 0):
                raise Exception("Save verification failed - data not found after save")
            
            print(f"   ✅ Save successful and verified")
            
        except Exception as e:
            print(f"   ❌ Save failed: {e}")
            
            # Try to restore from backup if available
            if backup_created:
                try:
                    self._restore_from_backup(file_path)
                    print(f"   ⚙️ Restored from backup")
                except Exception as backup_e:
                    print(f"   ❌ Backup restore also failed: {backup_e}")
            
            # Re-raise the original error
            raise e
    
    def _create_backup(self, file_path):
        """Create a backup of critical data files"""
        if os.path.exists(file_path):
            backup_path = file_path + '.backup'
            import shutil
            shutil.copy2(file_path, backup_path)
        elif os.path.exists(file_path + '.gz'):
            backup_path = file_path + '.gz.backup'
            import shutil
            shutil.copy2(file_path + '.gz', backup_path)
    
    def _restore_from_backup(self, file_path):
        """Restore data from backup"""
        backup_path = file_path + '.backup'
        gz_backup_path = file_path + '.gz.backup'
        
        if os.path.exists(backup_path):
            import shutil
            shutil.copy2(backup_path, file_path)
        elif os.path.exists(gz_backup_path):
            import shutil
            shutil.copy2(gz_backup_path, file_path + '.gz')
        
    def setup_reminders(self):
        """Set up automated reminder jobs"""
        # Check for due payments daily at 9 AM
        self.scheduler.add_job(
            func=self.check_and_send_reminders,
            trigger="cron",
            hour=9,
            minute=0,
            id='daily_reminder_check'
        )
    
    def add_member(self, name, contact, dues_amount, payment_plan, custom_schedule=None):
        member_id = str(uuid.uuid4())
        # Auto-detect contact type
        contact_type = 'email' if '@' in contact and '.' in contact else 'phone'
        
        member = Member(
            id=member_id,
            name=name,
            contact=contact,
            dues_amount=dues_amount,
            payment_plan=payment_plan,
            custom_schedule=custom_schedule or [],
            contact_type=contact_type
        )
        self.members[member_id] = member
        # Generate payment schedule based on plan
        self.generate_payment_schedule(member_id)
        # Save data to file
        self.save_data(self.members_file, self.members)
        self.sync_to_google_sheets()
        return member_id
    
    def update_member(self, member_id, name, contact, dues_amount, payment_plan, custom_schedule=None, role=None):
        """Update existing member information"""
        if member_id in self.members:
            member = self.members[member_id]
            member.name = name
            member.contact = contact
            # Auto-detect contact type
            member.contact_type = 'email' if '@' in contact and '.' in contact else 'phone'
            member.dues_amount = dues_amount
            member.payment_plan = payment_plan
            
            # Update role if provided
            if role is not None:
                member.role = role
            elif not hasattr(member, 'role'):
                member.role = 'brother'  # Default role for existing members
            
            # If custom schedule provided, use it; otherwise generate based on plan
            if custom_schedule is not None:
                member.custom_schedule = custom_schedule
            else:
                self.generate_payment_schedule(member_id)
            
            # Save data to file
            self.save_data(self.members_file, self.members)
            self.sync_to_google_sheets()
            return True
        return False
    
    def remove_member(self, member_id):
        """Remove a member from the system"""
        if member_id in self.members:
            del self.members[member_id]
            # Save data to file
            self.save_data(self.members_file, self.members)
            self.sync_to_google_sheets()
            return True
        return False
    
    def generate_payment_schedule(self, member_id):
        """Generate payment schedule based on member's payment plan"""
        if member_id not in self.members:
            return
        
        member = self.members[member_id]
        current_date = datetime.now()
        
        # Clear existing custom schedule
        member.custom_schedule = []
        
        if member.payment_plan == 'monthly':
            # Monthly payments for the semester (assume 4 months)
            monthly_amount = member.dues_amount / 4
            for i in range(4):
                due_date = current_date.replace(day=1) + timedelta(days=32*i)
                due_date = due_date.replace(day=1)  # First of each month
                member.custom_schedule.append({
                    'due_date': due_date.isoformat(),
                    'amount': monthly_amount,
                    'description': f'Monthly payment {i+1}/4'
                })
        
        elif member.payment_plan == 'bimonthly':
            # Bi-monthly payments (2 payments)
            bimonthly_amount = member.dues_amount / 2
            for i in range(2):
                due_date = current_date.replace(day=1) + timedelta(days=60*i)
                due_date = due_date.replace(day=1)  # First of every other month
                member.custom_schedule.append({
                    'due_date': due_date.isoformat(),
                    'amount': bimonthly_amount,
                    'description': f'Bi-monthly payment {i+1}/2'
                })
        
        elif member.payment_plan == 'semester':
            # Full semester payment due immediately
            member.custom_schedule.append({
                'due_date': current_date.isoformat(),
                'amount': member.dues_amount,
                'description': 'Full semester payment'
            })
    
    def get_member_payment_schedule(self, member_id):
        """Get the payment schedule for a member with status"""
        if member_id not in self.members:
            return []
        
        member = self.members[member_id]
        schedule_with_status = []
        total_paid = sum(payment['amount'] for payment in member.payments_made)
        running_total = 0
        
        for scheduled_payment in member.custom_schedule:
            running_total += scheduled_payment['amount']
            status = 'paid' if total_paid >= running_total else 'pending'
            amount_due = max(0, running_total - total_paid) if status == 'pending' else 0
            
            schedule_with_status.append({
                **scheduled_payment,
                'status': status,
                'amount_due': min(amount_due, scheduled_payment['amount'])
            })
        
        return schedule_with_status
    
    def add_transaction(self, category, description, amount, transaction_type):
        transaction_id = str(uuid.uuid4())
        transaction = Transaction(
            id=transaction_id,
            date=datetime.now().isoformat(),
            category=category,
            description=description,
            amount=amount,
            type=transaction_type
        )
        self.transactions.append(transaction)
        # Save data to file
        self.save_data(self.transactions_file, self.transactions)
        self.sync_to_google_sheets()
        return transaction_id
    
    def update_transaction(self, transaction_id, category, description, amount, transaction_type):
        """Update an existing transaction"""
        for transaction in self.transactions:
            if transaction.id == transaction_id:
                transaction.category = category
                transaction.description = description
                transaction.amount = amount
                transaction.type = transaction_type
                # Save data to file
                self.save_data(self.transactions_file, self.transactions)
                self.sync_to_google_sheets()
                return True
        return False
    
    def remove_transaction(self, transaction_id):
        """Remove a transaction from the system"""
        for i, transaction in enumerate(self.transactions):
            if transaction.id == transaction_id:
                # If this is a dues collection transaction, also remove the corresponding member payment
                if transaction.category == 'Dues Collection' and transaction.type == 'income':
                    self._remove_corresponding_member_payment(transaction)
                
                del self.transactions[i]
                # Save data to file
                self.save_data(self.transactions_file, self.transactions)
                self.sync_to_google_sheets()
                return True
        return False
    
    def _remove_corresponding_member_payment(self, transaction):
        """Remove the member payment that corresponds to a dues collection transaction"""
        for member_id, member in self.members.items():
            # Look through the member's payments for one that matches
            for i, payment in enumerate(member.payments_made):
                # First try to match by transaction ID (for newer payments)
                if payment.get('transaction_id') == transaction.id:
                    del member.payments_made[i]
                    self.save_data(self.members_file, self.members)
                    return True
                
                # Fallback: match by amount and time (for older payments without transaction_id)
                try:
                    transaction_date = datetime.fromisoformat(transaction.date.replace('Z', '+00:00'))
                    payment_date = datetime.fromisoformat(payment['date'].replace('Z', '+00:00'))
                    time_diff = abs((payment_date - transaction_date).total_seconds())
                    if (payment['amount'] == transaction.amount and 
                        time_diff < 60):  # Within 60 seconds
                        del member.payments_made[i]
                        self.save_data(self.members_file, self.members)
                        return True
                except Exception as e:
                    print(f"Error processing payment date: {e}")
                    continue
        return False
    
    def get_transaction_by_id(self, transaction_id):
        """Get a transaction by ID"""
        for transaction in self.transactions:
            if transaction.id == transaction_id:
                return transaction
        return None
    
    def record_payment(self, member_id, amount, payment_method, date=None):
        if member_id in self.members:
            # Also record as income transaction first to get the transaction ID
            transaction_id = self.add_transaction(
                'Dues Collection', 
                f'Payment from {self.members[member_id].name}',
                amount,
                'income'
            )
            
            payment = {
                'amount': amount,
                'date': date or datetime.now().isoformat(),
                'method': payment_method,
                'id': str(uuid.uuid4()),
                'transaction_id': transaction_id  # Reference to the corresponding transaction
            }
            self.members[member_id].payments_made.append(payment)
            # Save member data to file after payment update
            self.save_data(self.members_file, self.members)
            
            return True
        return False
    
    def get_member_balance(self, member_id):
        if member_id not in self.members:
            return None
        
        member = self.members[member_id]
        total_paid = sum(payment['amount'] for payment in member.payments_made)
        return member.dues_amount - total_paid
    
    def get_overdue_members(self):
        overdue = []
        current_date = datetime.now()
        
        for member_id, member in self.members.items():
            balance = self.get_member_balance(member_id)
            if balance > 0:
                # Simple logic: if it's past the 1st of the month and they owe money
                if current_date.day > 1:
                    days_overdue = current_date.day - 1
                    overdue.append({
                        'member': member,
                        'balance': balance,
                        'days_overdue': days_overdue
                    })
        return overdue
    
    def send_sms_reminder(self, phone, message, carrier=None):
        """Send SMS reminder using free email-to-SMS gateway or Twilio"""
        
        # First try Twilio if configured
        try:
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            from_phone = os.getenv('TWILIO_PHONE_NUMBER')
            
            if all([account_sid, auth_token, from_phone]):
                try:
                    from twilio.rest import Client
                    client = Client(account_sid, auth_token)
                    sms_message = client.messages.create(
                        body=message,
                        from_=from_phone,
                        to=phone
                    )
                    print(f"SMS sent via Twilio to {phone}")
                    return True
                except ImportError:
                    print("Twilio library not installed, skipping Twilio SMS")
        except Exception as e:
            print(f"Twilio SMS failed: {e}")
        
        # Fallback to free email-to-SMS gateway
        try:
            return self.send_free_sms(phone, message, carrier)
        except Exception as e:
            print(f"Free SMS failed: {e}")
            return False
    
    def send_free_sms(self, phone, message, carrier=None):
        """Send SMS using free email-to-SMS gateways"""
        # Email-to-SMS gateways for major carriers
        carrier_gateways = {
            'verizon': 'vtext.com',
            'att': 'txt.att.net', 
            'tmobile': 'tmomail.net',
            'sprint': 'messaging.sprintpcs.com',
            'uscellular': 'email.uscc.net',
            'boost': 'smsmyboostmobile.com',
            'cricket': 'sms.cricketwireless.net',
            'metropcs': 'mymetropcs.com'
        }
        
        smtp_username = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        
        if not all([smtp_username, smtp_password]):
            print("Gmail credentials not configured for free SMS")
            return False
        
        # Clean phone number (remove non-digits)
        clean_phone = ''.join(filter(str.isdigit, phone))
        if len(clean_phone) == 11 and clean_phone.startswith('1'):
            clean_phone = clean_phone[1:]  # Remove leading 1
        
        if len(clean_phone) != 10:
            print(f"Invalid phone number format: {phone}")
            return False
        
        # Try multiple carriers if none specified
        carriers_to_try = [carrier] if carrier else ['verizon', 'att', 'tmobile', 'sprint']
        
        for carrier_name in carriers_to_try:
            if carrier_name not in carrier_gateways:
                continue
                
            sms_email = f"{clean_phone}@{carrier_gateways[carrier_name]}"
            
            try:
                msg = MIMEText(message)
                msg['From'] = smtp_username
                msg['To'] = sms_email
                msg['Subject'] = ""  # Empty subject for SMS
                
                server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
                server.quit()
                
                print(f"Free SMS sent to {phone} via {carrier_name}")
                return True
            except Exception as e:
                print(f"Failed to send via {carrier_name}: {e}")
                continue
        
        return False
    
    def send_notification(self, contact, message, contact_type):
        """Send notification via SMS or email based on contact type"""
        print(f"DEBUG: Attempting to send {contact_type} notification to {contact}")
        print(f"DEBUG: Message: {message[:50]}...")
        
        try:
            if contact_type == 'email':
                result = self.send_email(contact, "Fraternity Dues Reminder", message)
                print(f"DEBUG: Email send result: {result}")
                return result
            else:
                result = self.send_sms_reminder(contact, message)
                print(f"DEBUG: SMS send result: {result}")
                return result
        except Exception as e:
            print(f"ERROR: Failed to send {contact_type} to {contact}: {e}")
            return False
    
    def send_email(self, email, subject, message):
        """Send email notification"""
        try:
            smtp_username = os.getenv('SMTP_USERNAME')
            smtp_password = os.getenv('SMTP_PASSWORD')
            
            print(f"DEBUG: SMTP_USERNAME configured: {'Yes' if smtp_username else 'No'}")
            print(f"DEBUG: SMTP_PASSWORD configured: {'Yes' if smtp_password else 'No'}")
            
            if not all([smtp_username, smtp_password]):
                print("ERROR: Email credentials not configured properly")
                print(f"SMTP_USERNAME: {smtp_username or 'NOT SET'}")
                print(f"SMTP_PASSWORD: {'SET' if smtp_password else 'NOT SET'}")
                return False
            
            print(f"DEBUG: Creating email message to {email}")
            msg = MIMEText(message)
            msg['From'] = smtp_username
            msg['To'] = email
            msg['Subject'] = subject
            
            print(f"DEBUG: Connecting to Gmail SMTP server...")
            server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
            server.starttls()
            print(f"DEBUG: Logging in with {smtp_username}...")
            server.login(smtp_username, smtp_password)
            print(f"DEBUG: Sending message...")
            server.send_message(msg)
            server.quit()
            
            print(f"SUCCESS: Email sent to {email}")
            return True
        except Exception as e:
            print(f"ERROR: Email sending failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def check_and_send_reminders(self, member_ids=None):
        """Check for upcoming and overdue payments and send notifications
        Args:
            member_ids: List of specific member IDs to send reminders to. If None, send to all eligible members.
        """
        current_date = datetime.now()
        print(f"DEBUG: Starting reminder check at {current_date}")
        
        # Determine which members to check
        members_to_check = self.members if member_ids is None else {mid: self.members[mid] for mid in member_ids if mid in self.members}
        print(f"DEBUG: Checking {len(members_to_check)} members for reminders")
        
        reminders_sent = 0
        members_contacted = []
        
        # Send reminders to members with outstanding balances
        for member_id, member in members_to_check.items():
            balance = self.get_member_balance(member_id)
            print(f"DEBUG: Member {member.name} balance: ${balance:.2f}")
            
            if balance > 0:
                print(f"DEBUG: Sending reminder to {member.name} ({member.contact_type}: {member.contact})")
                message = f"Hi {member.name}! Your fraternity dues balance is ${balance:.2f}. Please pay via Zelle or Venmo. Thanks!"
                
                # Send reminder based on contact type
                if member.contact_type == 'phone':
                    print(f"DEBUG: Sending SMS to {member.contact} via email-to-SMS gateway")
                    result = send_email_to_sms(member.contact, message, self.treasurer_config)
                else:
                    print(f"DEBUG: Sending email to {member.contact}")
                    result = self.send_email(member.contact, "Fraternity Dues Reminder", message)
                
                if result:
                    reminders_sent += 1
                    members_contacted.append(f"{member.name} (${balance:.2f})")
                    print(f"SUCCESS: Reminder sent to {member.name}")
                else:
                    print(f"FAILED: Could not send reminder to {member.name}")
            else:
                print(f"DEBUG: {member.name} has no outstanding balance, skipping")
        
        # Optional: Notify treasurer about reminders sent (you can disable this if too many notifications)
        # if reminders_sent > 0:
        #     summary_message = f"Sent {reminders_sent} payment reminders:\n" + "\n".join(members_contacted)
        #     notify_treasurer(summary_message, self.treasurer_config)
        
        print(f"DEBUG: Reminder check complete. {reminders_sent} reminders sent successfully.")
        return reminders_sent
    
    def update_budget_limit(self, category, amount):
        """Update budget limit for a category"""
        self.budget_limits[category] = amount
        self.save_data(self.budget_file, self.budget_limits)
        return True
    
    def get_budget_limit(self, category):
        """Get budget limit for a specific category"""
        return self.budget_limits.get(category, 0.0)
    
    def get_projected_dues_total(self):
        """Calculate total projected dues from all members"""
        return sum(member.dues_amount for member in self.members.values())
    
    def get_dues_collection_summary(self):
        """Get detailed dues collection information"""
        total_projected = self.get_projected_dues_total()
        
        # Calculate total collected by summing all member payments
        total_collected = 0
        actual_outstanding = 0
        members_paid_up = 0
        members_outstanding = 0
        
        for member_id, member in self.members.items():
            member_paid = sum(payment['amount'] for payment in member.payments_made)
            total_collected += member_paid
            
            balance = member.dues_amount - member_paid
            if balance <= 0:
                members_paid_up += 1
            else:
                members_outstanding += 1
                actual_outstanding += balance
        
        collection_rate = (total_collected / total_projected * 100) if total_projected > 0 else 0
        
        return {
            'total_projected': total_projected,
            'total_collected': total_collected,
            'outstanding': actual_outstanding,  # Use actual calculated outstanding
            'collection_rate': collection_rate,
            'members_paid_up': members_paid_up,
            'members_outstanding': members_outstanding
        }
    
    def get_budget_summary(self):
        """Calculate budget summary by category"""
        summary = {}
        
        for category in BUDGET_CATEGORIES:
            spent = sum(t.amount for t in self.transactions 
                       if t.category == category and t.type == 'expense')
            income = sum(t.amount for t in self.transactions 
                        if t.category == category and t.type == 'income')
            budget_limit = self.budget_limits.get(category, 0)
            
            remaining = budget_limit - spent
            percent_used = (spent / budget_limit * 100) if budget_limit > 0 else 0
            
            summary[category] = {
                'spent': spent,
                'income': income,
                'budget_limit': budget_limit,
                'remaining': remaining,
                'percent_used': percent_used
            }
        
        return summary
    
    def get_monthly_income_summary(self):
        """Get monthly breakdown of dues income"""
        monthly_income = {}
        current_date = datetime.now()
        
        # Get dues collection transactions
        dues_transactions = [t for t in self.transactions 
                           if t.category == 'Dues Collection' and t.type == 'income']
        
        for transaction in dues_transactions:
            try:
                trans_date = datetime.fromisoformat(transaction.date.replace('Z', '+00:00'))
                month_key = f"{trans_date.year}-{trans_date.month:02d}"
                month_name = f"{calendar.month_name[trans_date.month]} {trans_date.year}"
                
                if month_key not in monthly_income:
                    monthly_income[month_key] = {
                        'month_name': month_name,
                        'total_amount': 0,
                        'transaction_count': 0
                    }
                
                monthly_income[month_key]['total_amount'] += transaction.amount
                monthly_income[month_key]['transaction_count'] += 1
            except Exception as e:
                print(f"Error processing transaction date {transaction.date}: {e}")
                continue
        
        # Sort by year-month
        sorted_months = dict(sorted(monthly_income.items(), reverse=True))
        return sorted_months
    
    def get_all_financial_items(self):
        """Get all transactions and dues payments in a comprehensive list"""
        all_items = []
        
        # Add all recorded transactions
        for transaction in self.transactions:
            try:
                trans_date = datetime.fromisoformat(transaction.date.replace('Z', '+00:00'))
                all_items.append({
                    'id': transaction.id,
                    'date': trans_date,
                    'date_str': trans_date.strftime('%Y-%m-%d %H:%M'),
                    'type': 'transaction',
                    'category': transaction.category,
                    'description': transaction.description,
                    'amount': transaction.amount,
                    'transaction_type': transaction.type,
                    'member_name': None,
                    'status': 'completed'
                })
            except Exception as e:
                print(f"Error processing transaction {transaction.id}: {e}")
                continue
        
        # Add outstanding dues for each member
        for member_id, member in self.members.items():
            total_paid = sum(payment['amount'] for payment in member.payments_made)
            balance = member.dues_amount - total_paid
            
            if balance > 0:
                # Calculate next due date based on payment plan
                current_date = datetime.now()
                if member.custom_schedule:
                    # Find the next unpaid scheduled payment
                    running_total = 0
                    for scheduled_payment in member.custom_schedule:
                        running_total += scheduled_payment['amount']
                        if total_paid < running_total:
                            try:
                                due_date = datetime.fromisoformat(scheduled_payment['due_date'].replace('Z', '+00:00'))
                                amount_due = min(balance, scheduled_payment['amount'])
                                
                                all_items.append({
                                    'id': f"due_{member_id}_{len(all_items)}",
                                    'date': due_date,
                                    'date_str': due_date.strftime('%Y-%m-%d'),
                                    'type': 'dues_outstanding',
                                    'category': 'Outstanding Dues',
                                    'description': f"Outstanding dues - {scheduled_payment['description']}",
                                    'amount': amount_due,
                                    'transaction_type': 'outstanding',
                                    'member_name': member.name,
                                    'status': 'overdue' if due_date < current_date else 'pending'
                                })
                                break
                            except Exception:
                                continue
                else:
                    # Default: show as due now
                    all_items.append({
                        'id': f"due_{member_id}",
                        'date': current_date,
                        'date_str': current_date.strftime('%Y-%m-%d'),
                        'type': 'dues_outstanding',
                        'category': 'Outstanding Dues',
                        'description': f"Outstanding dues from {member.name}",
                        'amount': balance,
                        'transaction_type': 'outstanding',
                        'member_name': member.name,
                        'status': 'pending'
                    })
        
        # Sort by date (newest first)
        all_items.sort(key=lambda x: x['date'], reverse=True)
        
        return all_items
    
    def create_user(self, username, password, role='user'):
        """Create a new user account"""
        if username in self.users:
            return False
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        self.users[username] = {
            'password_hash': password_hash,
            'role': role,
            'created_at': datetime.now().isoformat()
        }
        self.save_data(self.users_file, self.users)
        return True
    
    def authenticate_user(self, username, password):
        """Authenticate a user"""
        if username not in self.users:
            return False
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        return self.users[username]['password_hash'] == password_hash
    
    def change_password(self, username, old_password, new_password):
        """Change user password"""
        if not self.authenticate_user(username, old_password):
            return False
        
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        self.users[username]['password_hash'] = password_hash
        self.save_data(self.users_file, self.users)
        return True
    
    def register_brother(self, full_name, phone, email):
        """Register a new brother account for verification with enhanced data validation and backup"""
        import secrets
        
        print(f"\n👥 REGISTERING NEW BROTHER")
        print(f"   Name: {full_name}")
        print(f"   Phone: {phone}")
        print(f"   Email: {email}")
        
        # Validate input data
        if not full_name.strip() or not phone.strip() or not email.strip():
            raise ValueError("All fields (name, phone, email) are required")
        
        if '@' not in email or '.' not in email:
            raise ValueError("Invalid email format")
        
        # Clean phone number
        clean_phone = ''.join(filter(str.isdigit, phone))
        if len(clean_phone) < 10:
            raise ValueError("Phone number must contain at least 10 digits")
        
        pending_id = str(uuid.uuid4())
        verification_token = secrets.token_urlsafe(32)
        
        pending_brother = PendingBrother(
            id=pending_id,
            full_name=full_name.strip(),
            phone=phone.strip(),
            email=email.strip().lower(),
            registration_date=datetime.now().isoformat(),
            verification_token=verification_token
        )
        
        # Add to pending brothers dictionary
        self.pending_brothers[pending_id] = pending_brother
        print(f"   Generated ID: {pending_id}")
        print(f"   Total pending brothers: {len(self.pending_brothers)}")
        
        # Save with error handling
        try:
            self.save_data(self.pending_brothers_file, self.pending_brothers)
            print(f"✅ Pending brother data saved successfully")
            
            # Verify the save worked by reloading
            reloaded_pending = self.load_data(self.pending_brothers_file, {})
            if pending_id in reloaded_pending:
                print(f"✅ Verified: Pending brother {pending_id} found after save")
            else:
                print(f"❌ Warning: Pending brother {pending_id} not found after save!")
                
        except Exception as e:
            print(f"❌ Error saving pending brother data: {e}")
            raise
        
        # Notify treasurer of new registration
        config = self.treasurer_config
        if config.email and config.smtp_username and config.smtp_password:
            message = f"New brother registration:\n\nName: {full_name}\nPhone: {phone}\nEmail: {email}\n\nPlease review and verify in the admin panel."
            try:
                notify_treasurer(message, config, "New Brother Registration")
                print(f"✅ Treasurer notification sent")
            except Exception as e:
                print(f"❌ Treasurer notification failed: {e}")
        else:
            print(f"❌ Treasurer notification skipped - email not configured")
        
        print(f"🎉 Brother registration completed successfully!\n")
        return pending_id
    
    def verify_brother_with_member(self, pending_id, member_id):
        """Link a pending brother to an existing member and create user account"""
        if pending_id not in self.pending_brothers:
            return False, "Pending registration not found"
        
        if member_id not in self.members:
            return False, "Member not found"
        
        pending_brother = self.pending_brothers[pending_id]
        member = self.members[member_id]
        
        # Create user account for the brother
        username = pending_brother.email.lower()
        
        # Generate secure random password
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        secure_password = ''.join(secrets.choice(alphabet) for _ in range(12))
        
        if self.create_user(username, secure_password, 'brother'):
            # Link member to user account
            member.user_id = username
            
            # Update pending brother
            pending_brother.is_verified = True
            pending_brother.member_id = member_id
            pending_brother.user_id = username
            
            # Save changes
            self.save_data(self.members_file, self.members)
            self.save_data(self.pending_brothers_file, self.pending_brothers)
            
            # Send login credentials via SMS
            sms_sent = False
            if self.treasurer_config.smtp_username and self.treasurer_config.smtp_password:
                try:
                    sms_sent = send_brother_credentials_sms(
                        pending_brother.full_name, 
                        pending_brother.phone, 
                        username, 
                        secure_password, 
                        self.treasurer_config
                    )
                except Exception as e:
                    print(f"SMS sending failed: {e}")
            
            if sms_sent:
                # Remove from pending brothers after successful verification and SMS
                del self.pending_brothers[pending_id]
                self.save_data(self.pending_brothers_file, self.pending_brothers)
                
                return True, f"✅ Brother {pending_brother.full_name} verified successfully!\n📱 Login credentials sent via SMS to {pending_brother.phone}\n🔐 Username: {username}"
            else:
                return True, f"✅ Brother {pending_brother.full_name} verified successfully!\n⚠️ SMS failed - Login credentials:\nUsername: {username}\nPassword: {secure_password}\n📞 Please manually share these credentials with the brother."
        
        return False, "Failed to create user account"
    
    def get_member_by_user_id(self, user_id):
        """Get member associated with a user account"""
        for member in self.members.values():
            if hasattr(member, 'user_id') and member.user_id == user_id:
                return member
        return None
    
    def sync_to_google_sheets(self):
        """Sync data to Google Sheets (Optional - only if configured)"""
        try:
            # Check for Google Sheets credentials
            credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
            spreadsheet_id = os.getenv('GOOGLE_SHEETS_ID')
            
            # If no credentials configured, skip silently
            if not credentials_path or not spreadsheet_id:
                # Don't print anything - this is optional functionality
                return False
            
            # Check if credentials file actually exists
            if not os.path.exists(credentials_path):
                # Don't print anything - this is optional functionality
                return False
            
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            
            credentials = Credentials.from_service_account_file(credentials_path, scopes=scope)
            gc = gspread.authorize(credentials)
            
            sheet = gc.open_by_key(spreadsheet_id)
            
            # Update members sheet
            members_worksheet = sheet.worksheet('Members')
            members_data = [['Name', 'Contact', 'Contact Type', 'Dues Amount', 'Total Paid', 'Balance']]
            
            for member in self.members.values():
                total_paid = sum(payment['amount'] for payment in member.payments_made)
                balance = member.dues_amount - total_paid
                members_data.append([
                    member.name, member.contact, member.contact_type,
                    member.dues_amount, total_paid, balance
                ])
            
            members_worksheet.clear()
            members_worksheet.update(members_data)
            
            # Update transactions sheet
            transactions_worksheet = sheet.worksheet('Transactions')
            transactions_data = [['Date', 'Category', 'Description', 'Amount', 'Type']]
            
            for transaction in self.transactions:
                transactions_data.append([
                    transaction.date, transaction.category, transaction.description,
                    transaction.amount, transaction.type
                ])
            
            transactions_worksheet.clear()
            transactions_worksheet.update(transactions_data)
            
            print("Google Sheets sync completed successfully")
            return True
        except Exception as e:
            # Only print errors if Google Sheets was actually configured
            credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
            if credentials_path and os.path.exists(credentials_path):
                print(f"Google Sheets sync failed: {e}")
            return False

# Initialize the app
treasurer_app = TreasurerApp()

# Authentication decorator
def require_auth(f):
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Template context processor to make permission functions available in templates
@app.context_processor
def inject_permission_functions():
    return {
        'has_permission': has_permission,
        'get_current_user_role': get_current_user_role
    }

# Flask routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    username = request.form['username']
    password = request.form['password']
    
    if treasurer_app.authenticate_user(username, password):
        session['user'] = username
        session['role'] = treasurer_app.users[username]['role']
        flash(f'Welcome, {username}!')
        
        # Redirect based on user type
        if treasurer_app.users[username]['role'] == 'brother':
            return redirect(url_for('brother_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    else:
        flash('Invalid username or password')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully')
    return redirect(url_for('login'))

@app.route('/force-logout')
def force_logout():
    """Force logout - clears all sessions and redirects to login"""
    session.clear()
    flash('All sessions cleared - Please log in again')
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@require_auth
def change_password():
    if request.method == 'GET':
        return render_template('change_password.html')
    
    old_password = request.form['old_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    
    if new_password != confirm_password:
        flash('New passwords do not match')
        return redirect(url_for('change_password'))
    
    if treasurer_app.change_password(session['user'], old_password, new_password):
        flash('Password changed successfully!')
        return redirect(url_for('dashboard'))
    else:
        flash('Current password is incorrect')
        return redirect(url_for('change_password'))

@app.route('/monthly_income')
@require_auth
def monthly_income():
    monthly_data = treasurer_app.get_monthly_income_summary()
    return render_template('monthly_income.html', monthly_data=monthly_data)

@app.route('/')
def landing_page():
    # Check if user is already logged in
    if 'user' in session:
        # Redirect to appropriate dashboard based on role
        if session.get('role') == 'brother':
            return redirect(url_for('brother_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    
    # Show login page for unauthenticated users
    return redirect(url_for('login'))

@app.route('/dashboard')
@require_auth
def dashboard():
    dues_summary = treasurer_app.get_dues_collection_summary()
    return render_template('index.html', 
                         members=treasurer_app.members,
                         budget_summary=treasurer_app.get_budget_summary(),
                         dues_summary=dues_summary,
                         categories=BUDGET_CATEGORIES,
                         pending_brothers=treasurer_app.pending_brothers)

@app.route('/enhanced')
@require_auth
def enhanced_dashboard():
    dues_summary = treasurer_app.get_dues_collection_summary()
    return render_template('enhanced_dashboard.html', 
                         members=treasurer_app.members,
                         budget_summary=treasurer_app.get_budget_summary(),
                         dues_summary=dues_summary,
                         categories=BUDGET_CATEGORIES)

@app.route('/add_member', methods=['POST'])
@require_auth
@require_permission('add_members')
def add_member():
    name = request.form['name']
    contact = request.form.get('contact', request.form.get('phone', ''))  # Support both field names
    dues_amount = float(request.form['dues_amount'])
    payment_plan = request.form['payment_plan']
    
    member_id = treasurer_app.add_member(name, contact, dues_amount, payment_plan)
    flash(f'Member {name} added successfully!')
    return redirect(url_for('dashboard'))

@app.route('/add_transaction', methods=['POST'])
@require_auth
@require_permission('add_transactions')
def add_transaction():
    category = request.form['category']
    description = request.form['description']
    amount = float(request.form['amount'])
    transaction_type = request.form['type']
    
    treasurer_app.add_transaction(category, description, amount, transaction_type)
    flash('Transaction added successfully!')
    return redirect(url_for('dashboard'))

@app.route('/edit_transaction/<transaction_id>', methods=['GET', 'POST'])
@require_auth
@require_permission('edit_transactions')
def edit_transaction(transaction_id):
    transaction = treasurer_app.get_transaction_by_id(transaction_id)
    if not transaction:
        flash('Transaction not found!')
        return redirect(url_for('transactions'))
    
    if request.method == 'GET':
        return render_template('edit_transaction.html', 
                             transaction=transaction,
                             categories=BUDGET_CATEGORIES + ['Dues Collection'])
    
    # POST request - update transaction
    category = request.form['category']
    description = request.form['description']
    amount = float(request.form['amount'])
    transaction_type = request.form['type']
    
    if treasurer_app.update_transaction(transaction_id, category, description, amount, transaction_type):
        flash('Transaction updated successfully!')
    else:
        flash('Error updating transaction!')
    
    return redirect(url_for('transactions'))

@app.route('/remove_transaction/<transaction_id>', methods=['POST'])
@require_auth
@require_permission('edit_transactions')
def remove_transaction(transaction_id):
    transaction = treasurer_app.get_transaction_by_id(transaction_id)
    if transaction:
        if treasurer_app.remove_transaction(transaction_id):
            flash(f'Transaction "{transaction.description}" removed successfully!')
        else:
            flash('Error removing transaction!')
    else:
        flash('Transaction not found!')
    
    return redirect(url_for('transactions'))

@app.route('/record_payment', methods=['POST'])
@require_auth
@require_permission('record_payments')
def record_payment():
    member_id = request.form['member_id']
    amount = float(request.form['amount'])
    payment_method = request.form['payment_method']
    
    if treasurer_app.record_payment(member_id, amount, payment_method):
        flash('Payment recorded successfully!')
    else:
        flash('Error recording payment!')
    
    return redirect(url_for('dashboard'))

@app.route('/send_reminders')
@require_auth
@require_permission('send_reminders')
def send_reminders():
    try:
        print("\n🚀 Starting bulk reminder sending...")
        
        # Simple error handling without signal-based timeouts for cloud compatibility
        reminders_sent = treasurer_app.check_and_send_reminders()
        
        if reminders_sent > 0:
            flash(f'✅ {reminders_sent} payment reminders sent successfully!', 'success')
        else:
            flash('ℹ️ No reminders needed - all members are paid up!', 'info')
            
    except Exception as e:
        print(f"Reminder error: {e}")
        flash(f'❌ Error sending reminders: {str(e)}. Try selective reminders for better control.', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/selective_reminders', methods=['GET', 'POST'])
@require_auth
@require_permission('send_reminders')
def selective_reminders():
    if request.method == 'GET':
        # Get members with outstanding balances
        members_with_balance = []
        for member_id, member in treasurer_app.members.items():
            balance = treasurer_app.get_member_balance(member_id)
            if balance > 0:
                members_with_balance.append({
                    'id': member_id,
                    'member': member,
                    'balance': balance
                })
        
        return render_template('selective_reminders.html', 
                             members_with_balance=members_with_balance)
    
    # POST request - send reminders to selected members
    selected_members = request.form.getlist('selected_members')
    
    if not selected_members:
        flash('No members selected for reminders!', 'warning')
        return redirect(url_for('selective_reminders'))
    
    try:
        print(f"\n📱 Sending selective reminders to {len(selected_members)} members...")
        
        # Simple error handling for cloud compatibility
        reminders_sent = treasurer_app.check_and_send_reminders(selected_members)
        
        if reminders_sent > 0:
            flash(f'✅ Reminders sent to {reminders_sent} selected member(s)!', 'success')
        else:
            flash('ℹ️ No reminders sent - check member balances.', 'info')
            
    except Exception as e:
        print(f"Selective reminder error: {e}")
        flash(f'❌ Error sending selective reminders: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/budget_summary')
@require_auth
def budget_summary():
    return jsonify(treasurer_app.get_budget_summary())

@app.route('/bulk_import', methods=['GET', 'POST'])
@require_auth
@require_permission('add_members')
def bulk_import():
    if request.method == 'GET':
        return render_template('bulk_import.html')
    
    # Parse the pasted data
    raw_data = request.form['member_data']
    default_dues = float(request.form.get('default_dues', 0))
    default_payment_plan = request.form.get('default_payment_plan', 'semester')
    
    parsed_members = []
    errors = []
    
    lines = raw_data.strip().split('\n')
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
            
        # Try to parse different formats
        parts = [part.strip() for part in line.split('\t') if part.strip()]  # Tab-separated
        if len(parts) < 2:
            parts = [part.strip() for part in line.split(',') if part.strip()]  # Comma-separated
        if len(parts) < 2:
            parts = line.split()  # Space-separated
            
        if len(parts) >= 2:
            phone = None  # Initialize phone variable
            full_name = ""
            
            # Try different arrangements
            if len(parts) == 2:
                # "John Doe" "1234567890" or "John" "Doe 1234567890"
                name_part = parts[0]
                second_part = parts[1]
                
                # Check if second part contains phone number
                phone_chars = ''.join(filter(str.isdigit, second_part))
                if len(phone_chars) >= 10:
                    # Second part has phone, might have last name too
                    phone = phone_chars[-10:]  # Last 10 digits
                    remaining = second_part.replace(phone, '').replace(phone_chars, '').strip()
                    if remaining:
                        full_name = f"{name_part} {remaining}".strip()
                    else:
                        full_name = name_part
                else:
                    # Assume first is first name, second is last name, need phone
                    full_name = f"{parts[0]} {parts[1]}"
                    phone = None
                    
            elif len(parts) >= 3:
                # "John" "Doe" "1234567890" or similar
                phone_candidates = []
                name_parts = []
                
                for part in parts:
                    digits = ''.join(filter(str.isdigit, part))
                    if len(digits) >= 10:
                        phone_candidates.append(digits[-10:])  # Last 10 digits
                    else:
                        name_parts.append(part)
                
                full_name = ' '.join(name_parts)
                phone = phone_candidates[0] if phone_candidates else None
            
            if phone is None:
                errors.append(f"Line {i}: Could not find phone number - '{line}'")
                continue
                
            # Format phone number
            if len(phone) == 10:
                formatted_phone = f"+1{phone}"
            elif len(phone) == 11 and phone.startswith('1'):
                formatted_phone = f"+{phone}"
            else:
                formatted_phone = phone
            
            parsed_members.append({
                'name': full_name,
                'phone': formatted_phone,
                'dues_amount': default_dues,
                'payment_plan': default_payment_plan
            })
        else:
            errors.append(f"Line {i}: Not enough information - '{line}'")
    
    return render_template('bulk_import.html', 
                         parsed_members=parsed_members, 
                         errors=errors,
                         show_review=True)

@app.route('/confirm_bulk_import', methods=['POST'])
@require_auth
@require_permission('add_members')
def confirm_bulk_import():
    # Get the confirmed member data
    member_count = int(request.form.get('member_count', 0))
    added_count = 0
    
    for i in range(member_count):
        if f'include_{i}' in request.form:  # Only add checked members
            name = request.form.get(f'name_{i}')
            phone = request.form.get(f'phone_{i}')
            dues_amount = float(request.form.get(f'dues_{i}'))
            payment_plan = request.form.get(f'plan_{i}')
            
            treasurer_app.add_member(name, phone, dues_amount, payment_plan)
            added_count += 1
    
    flash(f'Successfully added {added_count} members!')
    return redirect(url_for('dashboard'))

@app.route('/edit_member/<member_id>', methods=['GET', 'POST'])
@require_auth
@require_permission('edit_members')
def edit_member(member_id):
    if request.method == 'GET':
        if member_id not in treasurer_app.members:
            flash('Member not found!')
            return redirect(url_for('dashboard'))
        
        member = treasurer_app.members[member_id]
        payment_schedule = treasurer_app.get_member_payment_schedule(member_id)
        
        return render_template('edit_member.html', 
                             member=member,
                             payment_schedule=payment_schedule)
    
    # POST request - update member
    name = request.form['name']
    contact = request.form.get('contact', request.form.get('phone', ''))  # Support both field names
    dues_amount = float(request.form['dues_amount'])
    payment_plan = request.form['payment_plan']
    role = request.form.get('role', 'brother')  # Get role assignment
    
    if treasurer_app.update_member(member_id, name, contact, dues_amount, payment_plan, role=role):
        flash(f'Member {name} updated successfully!')
    else:
        flash('Error updating member!')
    
    return redirect(url_for('member_details', member_id=member_id))

@app.route('/remove_member/<member_id>', methods=['POST'])
@require_auth
@require_permission('edit_members')
def remove_member(member_id):
    if member_id in treasurer_app.members:
        member_name = treasurer_app.members[member_id].name
        if treasurer_app.remove_member(member_id):
            flash(f'Member {member_name} removed successfully!')
        else:
            flash('Error removing member!')
    else:
        flash('Member not found!')
    
    return redirect(url_for('dashboard'))

@app.route('/member_details/<member_id>')
@require_auth
def member_details(member_id):
    if member_id not in treasurer_app.members:
        flash('Member not found!')
        return redirect(url_for('dashboard'))
    
    member = treasurer_app.members[member_id]
    payment_schedule = treasurer_app.get_member_payment_schedule(member_id)
    balance = treasurer_app.get_member_balance(member_id)
    
    return render_template('member_details.html',
                         member=member,
                         payment_schedule=payment_schedule,
                         balance=balance)

@app.route('/budget_management', methods=['GET', 'POST'])
@require_auth
@require_permission('manage_budgets')
def budget_management():
    if request.method == 'GET':
        dues_summary = treasurer_app.get_dues_collection_summary()
        return render_template('budget_management.html',
                             budget_limits=treasurer_app.budget_limits,
                             budget_summary=treasurer_app.get_budget_summary(),
                             dues_summary=dues_summary,
                             categories=BUDGET_CATEGORIES)
    
    # POST request - update budget limits
    for category in BUDGET_CATEGORIES:
        amount_key = f'budget_{category.replace("(", "_").replace(")", "_").replace(" ", "_").replace(",", "")}'
        if amount_key in request.form:
            amount = float(request.form[amount_key] or 0)
            treasurer_app.update_budget_limit(category, amount)
    
    flash('Budget limits updated successfully!')
    return redirect(url_for('budget_management'))

@app.route('/edit_budget_category/<category>', methods=['GET', 'POST'])
@require_auth
@require_permission('manage_budgets')
def edit_budget_category(category):
    if category not in BUDGET_CATEGORIES:
        flash('Invalid budget category!')
        return redirect(url_for('budget_management'))
    
    if request.method == 'GET':
        current_limit = treasurer_app.get_budget_limit(category)
        budget_summary = treasurer_app.get_budget_summary()
        category_summary = budget_summary.get(category, {})
        
        return render_template('edit_budget_category.html',
                             category=category,
                             current_limit=current_limit,
                             summary=category_summary)
    
    # POST request - update single category
    try:
        amount = float(request.form['amount'])
        treasurer_app.update_budget_limit(category, amount)
        flash(f'Budget limit for {category} updated successfully!')
    except ValueError:
        flash('Invalid amount entered!')
    
    return redirect(url_for('budget_management'))

@app.route('/custom_payment_schedule/<member_id>', methods=['GET', 'POST'])
@require_auth
@require_permission('edit_members')
def custom_payment_schedule(member_id):
    if member_id not in treasurer_app.members:
        flash('Member not found!')
        return redirect(url_for('dashboard'))
    
    member = treasurer_app.members[member_id]
    
    if request.method == 'GET':
        return render_template('custom_payment_schedule.html',
                             member=member)
    
    # POST request - update custom payment schedule
    custom_schedule = []
    payment_count = int(request.form.get('payment_count', 0))
    
    for i in range(payment_count):
        due_date = request.form.get(f'due_date_{i}')
        amount = request.form.get(f'amount_{i}')
        description = request.form.get(f'description_{i}')
        
        if due_date and amount and description:
            try:
                # Validate date format and convert to ISO format
                parsed_date = datetime.strptime(due_date, '%Y-%m-%d')
                custom_schedule.append({
                    'due_date': parsed_date.isoformat(),
                    'amount': float(amount),
                    'description': description
                })
            except (ValueError, TypeError) as e:
                flash(f'Error in payment {i+1}: Invalid date or amount format')
                return redirect(url_for('custom_payment_schedule', member_id=member_id))
    
    # Update member with custom schedule
    member.payment_plan = 'custom'
    success = treasurer_app.update_member(
        member_id, member.name, member.contact, 
        member.dues_amount, 'custom', custom_schedule
    )
    
    if success:
        flash(f'Custom payment schedule updated for {member.name}!')
        return redirect(url_for('member_details', member_id=member_id))
    else:
        flash('Error updating payment schedule!')
        return redirect(url_for('custom_payment_schedule', member_id=member_id))

@app.route('/dues_summary')
@require_auth
def dues_summary_page():
    dues_summary = treasurer_app.get_dues_collection_summary()
    return render_template('dues_summary.html',
                         dues_summary=dues_summary,
                         members=treasurer_app.members)

# Google Sheets sync functionality removed

@app.route('/transactions')
@require_auth
def transactions():
    """Show all transactions and outstanding dues in itemized list"""
    all_items = treasurer_app.get_all_financial_items()
    
    # Calculate totals
    total_income = sum(item['amount'] for item in all_items 
                      if item['transaction_type'] == 'income')
    total_expenses = sum(item['amount'] for item in all_items 
                        if item['transaction_type'] == 'expense')
    total_outstanding = sum(item['amount'] for item in all_items 
                           if item['transaction_type'] == 'outstanding')
    
    return render_template('transactions.html',
                         transactions=all_items,
                         total_income=total_income,
                         total_expenses=total_expenses,
                         total_outstanding=total_outstanding)

# 4) ROUTES (make sure the route comes AFTER the function so Python knows it)

# Google Sheets export route removed

@app.route('/treasurer_setup', methods=['GET', 'POST'])
@require_auth
@require_permission('manage_users')
def treasurer_setup():
    if request.method == 'GET':
        return render_template('treasurer_setup.html', config=treasurer_app.treasurer_config)
    
    # POST - Update treasurer configuration
    config = treasurer_app.treasurer_config
    config.name = request.form.get('name', '')
    config.email = request.form.get('email', '')
    config.phone = request.form.get('phone', '')  # Treasurer's phone for SMS notifications
    config.smtp_username = request.form.get('smtp_username', '')
    config.smtp_password = request.form.get('smtp_password', '')
    
    treasurer_app.save_treasurer_config()
    flash('Treasurer configuration updated successfully!')
    return redirect(url_for('treasurer_setup'))

@app.route('/handover_treasurer', methods=['GET', 'POST'])
@require_auth
@require_permission('manage_users')
def handover_treasurer():
    if request.method == 'GET':
        return render_template('handover_treasurer.html')
    
    # Clear treasurer-specific data
    config = treasurer_app.treasurer_config
    config.name = ""
    config.email = ""
    config.phone = ""
    config.smtp_username = ""
    config.smtp_password = ""
    
    treasurer_app.save_treasurer_config()
    
    # Archive current semester
    current_sem = treasurer_app.get_current_semester()
    if current_sem:
        current_sem.is_current = False
        current_sem.archived = True
        current_sem.end_date = datetime.now().isoformat()
    
    treasurer_app.save_data(treasurer_app.semesters_file, treasurer_app.semesters)
    
    flash('Treasurer handover completed! Please provide setup instructions to the new treasurer.')
    return redirect(url_for('dashboard'))

@app.route('/optimize_storage')
@require_auth
@require_permission('manage_users')
def optimize_storage():
    """Optimize data storage and clean up files"""
    try:
        treasurer_app.optimize_data_storage()
        flash('Storage optimization completed successfully! Temporary files removed and data compressed.')
    except Exception as e:
        flash(f'Optimization failed: {e}')
    return redirect(url_for('dashboard'))

@app.route('/semester_management', methods=['GET', 'POST'])
@require_auth
@require_permission('manage_users')
def semester_management():
    if request.method == 'GET':
        semesters = list(treasurer_app.semesters.values())
        semesters.sort(key=lambda s: (s.year, ['Spring', 'Summer', 'Fall'].index(s.season)), reverse=True)
        return render_template('semester_management.html', semesters=semesters, current_semester=treasurer_app.current_semester)
    
    # POST - Create new semester
    season = request.form.get('season')
    year = int(request.form.get('year'))
    
    # Archive current semester
    if treasurer_app.current_semester:
        treasurer_app.current_semester.is_current = False
        treasurer_app.current_semester.end_date = datetime.now().isoformat()
    
    # Create new semester
    semester_id = f"{season.lower()}_{year}"
    new_semester = Semester(id=semester_id, name=f"{season} {year}", year=year, season=season, 
                           start_date=datetime.now().isoformat(), end_date="", is_current=True)
    
    treasurer_app.semesters[semester_id] = new_semester
    treasurer_app.current_semester = new_semester
    treasurer_app.save_data(treasurer_app.semesters_file, treasurer_app.semesters)
    
    flash(f'New semester {season} {year} created!')
    return redirect(url_for('semester_management'))

# Google Sheets export functionality removed

@app.route('/preview_role/<role_name>')
@require_auth
def preview_role(role_name):
    """Preview dashboard as different role (treasurer only)"""
    # Check if user is treasurer/admin
    if session.get('user') != 'admin':  # Only admin can preview roles
        flash('Only treasurers can preview other roles.')
        return redirect(url_for('dashboard'))
    
    # Valid roles for preview
    valid_roles = ['president', 'vice_president', 'social_chair', 'phi_ed_chair', 'recruitment_chair', 'brotherhood_chair', 'brother']
    if role_name not in valid_roles:
        flash('Invalid role for preview.')
        return redirect(url_for('dashboard'))
    
    # Store current role in session for restoration
    session['preview_mode'] = True
    session['preview_role'] = role_name
    session['original_role'] = 'admin'
    
    flash(f'Now previewing dashboard as: {role_name.replace("_", " ").title()}. Click "Exit Preview" to return to treasurer view.', 'info')
    
    # Redirect based on role type
    if role_name in ['president', 'vice_president']:
        # Presidents/VPs see restricted treasurer dashboard
        return redirect(url_for('dashboard'))
    else:
        # Brothers and chairs see brother dashboard
        return redirect(url_for('brother_dashboard_preview', role_name=role_name))

@app.route('/exit_preview')
@require_auth
def exit_preview():
    """Exit role preview mode"""
    if 'preview_mode' in session:
        del session['preview_mode']
        del session['preview_role']
        del session['original_role']
        flash('Exited preview mode. Back to treasurer view.')
    return redirect(url_for('dashboard'))

@app.route('/test_sms')
@require_auth
@require_permission('send_reminders')
def test_sms():
    """Test SMS functionality with comprehensive diagnostics"""
    config = treasurer_app.treasurer_config
    if not config.phone:
        flash('Please configure your phone number in Treasurer Setup first.', 'error')
        return redirect(url_for('treasurer_setup'))
    
    if not config.smtp_username or not config.smtp_password:
        flash('Please configure your email credentials in Treasurer Setup first.', 'error')
        return redirect(url_for('treasurer_setup'))
    
    test_message = "Test SMS from Fraternity Treasurer App - SMS working correctly! 📱✅"
    
    print(f"\n🧪 SMS TEST STARTING")
    print(f"📱 Phone: {config.phone}")
    print(f"📧 SMTP User: {config.smtp_username}")
    print(f"💬 Message: {test_message}")
    
    if send_email_to_sms(config.phone, test_message, config):
        flash(f'✅ Test SMS sent successfully to {config.phone}!', 'success')
        flash('📱 Check your phone for the message (may take 1-2 minutes).', 'info')
    else:
        flash('❌ Failed to send test SMS. Check the console logs for details.', 'error')
        flash('💡 Common issues: Gmail app password expired, phone number format, or carrier blocking.', 'warning')
    
    return redirect(url_for('notifications_dashboard'))

@app.route('/test_sms_to_number', methods=['POST'])
@require_auth
@require_permission('send_reminders')
def test_sms_to_number():
    """Test SMS to a specific phone number"""
    config = treasurer_app.treasurer_config
    test_phone = request.form.get('test_phone', '').strip()
    
    if not test_phone:
        flash('Please enter a phone number to test.', 'error')
        return redirect(url_for('notifications_dashboard'))
    
    if not config.smtp_username or not config.smtp_password:
        flash('Please configure your email credentials in Treasurer Setup first.', 'error')
        return redirect(url_for('treasurer_setup'))
    
    test_message = f"Test SMS from Fraternity Treasurer App to {test_phone} 📱✅"
    
    print(f"\n🧪 SMS TEST TO CUSTOM NUMBER")
    print(f"📱 Target Phone: {test_phone}")
    print(f"📧 SMTP User: {config.smtp_username}")
    
    if send_email_to_sms(test_phone, test_message, config):
        flash(f'✅ Test SMS sent successfully to {test_phone}!', 'success')
        flash('📱 Check the target phone for the message (may take 1-2 minutes).', 'info')
    else:
        flash(f'❌ Failed to send test SMS to {test_phone}. Check console logs.', 'error')
    
    return redirect(url_for('notifications_dashboard'))

@app.route('/submit_payment_plan', methods=['POST'])
@require_auth
def submit_payment_plan():
    """Brother submits a payment plan request (example route)"""
    member_name = request.form.get('member_name', 'Unknown Member')
    plan_details = request.form.get('plan_details', '')
    
    # Notify treasurer about the request
    if notify_payment_plan_request(member_name, plan_details, treasurer_app.treasurer_config):
        flash('Payment plan request submitted successfully! Treasurer has been notified.')
    else:
        flash('Payment plan request submitted, but treasurer notification failed.')
    
    return redirect(url_for('dashboard'))

@app.route('/submit_reimbursement', methods=['POST'])
@require_auth  
def submit_reimbursement():
    """Submit a reimbursement request (example route)"""
    submitter_name = request.form.get('submitter_name', session.get('user', 'Unknown'))
    amount = float(request.form.get('amount', 0))
    category = request.form.get('category', '')
    description = request.form.get('description', '')
    
    # Notify treasurer about the request
    if notify_reimbursement_request(submitter_name, amount, category, description, treasurer_app.treasurer_config):
        flash('Reimbursement request submitted successfully! Treasurer has been notified.')
    else:
        flash('Reimbursement request submitted, but treasurer notification failed.')
    
    return redirect(url_for('dashboard'))

@app.route('/test_approval_notification')
@require_auth
@require_permission('send_reminders')
def test_approval_notification():
    """Test the approval notification system"""
    config = treasurer_app.treasurer_config
    if not config.phone and not config.email:
        flash('Please configure your phone and/or email in Treasurer Setup first.')
        return redirect(url_for('treasurer_setup'))
    
    # Send a test reimbursement request notification
    if notify_reimbursement_request('John Doe (Test)', 75.50, 'Social', 'Test reimbursement notification - pizza for brotherhood event', config):
        flash('Test approval notification sent successfully! Check your phone and email.')
    else:
        flash('Failed to send test approval notification. Check your configuration.')
    
    return redirect(url_for('notifications_dashboard'))

@app.route('/notifications')
@require_auth
@require_permission('send_reminders')
def notifications_dashboard():
    """Notifications dashboard for approval requests"""
    # Check notification configuration status
    config = treasurer_app.treasurer_config
    email_configured = bool(config.smtp_username and config.smtp_password)
    treasurer_phone_configured = bool(config.phone)
    
    notification_status = {
        'email_configured': email_configured,
        'treasurer_phone_configured': treasurer_phone_configured,
        'email_username': config.smtp_username,
        'treasurer_phone': config.phone
    }
    
    # TODO: In the future, you could add pending approval requests here
    # For example:
    # pending_requests = get_pending_approval_requests()
    
    return render_template('notifications_dashboard.html',
                         notification_status=notification_status)

@app.route('/register', methods=['GET', 'POST'])
def brother_registration():
    """Brother registration form"""
    if request.method == 'GET':
        return render_template('brother_registration.html')
    
    # POST request - process registration
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip().lower()
    
    # Basic validation
    if not all([full_name, phone, email]):
        flash('All fields are required.', 'error')
        return render_template('brother_registration.html')
    
    # Check if email already exists
    if email in treasurer_app.users:
        flash('An account with this email already exists.', 'error')
        return render_template('brother_registration.html')
    
    # Check if already registered
    for pending in treasurer_app.pending_brothers.values():
        if pending.email.lower() == email:
            flash('Registration with this email is already pending approval.', 'warning')
            return render_template('brother_registration.html')
    
    # Register the brother
    try:
        pending_id = treasurer_app.register_brother(full_name, phone, email)
        
        # Success message with clear next steps
        flash('🎉 Registration submitted successfully!', 'success')
        flash('✅ Your information has been sent to the treasurer for verification.', 'info')
        flash('📱 Once approved, your login credentials will be sent to your phone via SMS.', 'info')
        flash('⏰ Please allow 24-48 hours for verification.', 'info')
        
        return render_template('brother_registration_success.html', 
                             full_name=full_name, 
                             phone=phone, 
                             email=email)
    except Exception as e:
        flash(f'Registration failed: {str(e)}', 'error')
        return render_template('brother_registration.html')

@app.route('/brother_dashboard_preview/<role_name>')
@require_auth
def brother_dashboard_preview(role_name):
    """Preview brother dashboard as specific role (admin only)"""
    if session.get('user') != 'admin' or not session.get('preview_mode'):
        return redirect(url_for('brother_dashboard'))
    
    # Create a mock member for preview
    from dataclasses import dataclass
    
    @dataclass
    class MockMember:
        id: str = 'preview'
        name: str = f'Preview {role_name.replace("_", " ").title()}'
        contact: str = 'preview@example.com'
        dues_amount: float = 500.0
        payment_plan: str = 'semester'
        payments_made: list = None
        contact_type: str = 'email'
        role: str = role_name
        
        def __post_init__(self):
            if self.payments_made is None:
                self.payments_made = [
                    {'amount': 250.0, 'date': '2024-09-01', 'method': 'Zelle', 'id': 'preview1'}
                ]
    
    mock_member = MockMember()
    balance = 250.0  # Mock balance
    
    # Mock payment schedule
    payment_schedule = [
        {'description': 'Full semester payment', 'due_date': '2024-09-01', 'amount': 500.0, 'status': 'paid'},
    ]
    
    # Get summary data based on permissions
    data = {
        'member': mock_member,
        'balance': balance,
        'payment_schedule': payment_schedule
    }
    
    # Add additional data for executives
    if role_name in ['president', 'vice_president']:
        data.update({
            'total_members': len(treasurer_app.members),
            'dues_summary': treasurer_app.get_dues_collection_summary(),
            'budget_summary': treasurer_app.get_budget_summary()
        })
    elif role_name in ['social_chair', 'phi_ed_chair', 'brotherhood_chair', 'recruitment_chair']:
        data.update({
            'budget_summary': treasurer_app.get_budget_summary()
        })
    
    return render_template('brother_dashboard.html', **data)

@app.route('/brother_dashboard')
@require_auth
def brother_dashboard():
    """Brother-specific dashboard with role-based content"""
    # Get current user's member info
    member = get_user_member()
    if not member:
        flash('Member information not found. Please contact the treasurer.', 'error')
        return redirect(url_for('logout'))
    
    # Calculate member's balance
    balance = treasurer_app.get_member_balance(member.id)
    
    # Get payment schedule
    payment_schedule = treasurer_app.get_member_payment_schedule(member.id)
    
    # Get summary data based on permissions
    data = {
        'member': member,
        'balance': balance,
        'payment_schedule': payment_schedule
    }
    
    # Add additional data for executives
    if has_permission('view_all_data'):
        data.update({
            'total_members': len(treasurer_app.members),
            'dues_summary': treasurer_app.get_dues_collection_summary(),
            'budget_summary': treasurer_app.get_budget_summary()
        })
    
    return render_template('brother_dashboard.html', **data)

@app.route('/debug_pending_brothers')
@require_auth
@require_permission('manage_users')
def debug_pending_brothers():
    """Debug route to check pending brothers status"""
    print(f"\n🔍 DEBUGGING PENDING BROTHERS")
    print(f"   Pending brothers file: {treasurer_app.pending_brothers_file}")
    print(f"   File exists: {os.path.exists(treasurer_app.pending_brothers_file)}")
    print(f"   Compressed file exists: {os.path.exists(treasurer_app.pending_brothers_file + '.gz')}")
    
    # Force reload from disk
    treasurer_app.pending_brothers = treasurer_app.load_data(treasurer_app.pending_brothers_file, {})
    print(f"   Current pending brothers count: {len(treasurer_app.pending_brothers)}")
    
    for pending_id, pending_brother in treasurer_app.pending_brothers.items():
        print(f"   - {pending_id}: {pending_brother.full_name} ({pending_brother.email})")
    
    flash(f'Debug complete: {len(treasurer_app.pending_brothers)} pending brothers found. Check console for details.')
    return redirect(url_for('verify_brothers'))

@app.route('/verify_brothers', methods=['GET', 'POST'])
@require_auth
@require_permission('manage_users')
def verify_brothers():
    """Treasurer interface to verify pending brother registrations"""
    if request.method == 'GET':
        # Force reload pending brothers from disk
        treasurer_app.pending_brothers = treasurer_app.load_data(treasurer_app.pending_brothers_file, {})
        print(f"\n👥 VERIFY BROTHERS PAGE LOAD")
        print(f"   Pending brothers count: {len(treasurer_app.pending_brothers)}")
        
        return render_template('verify_brothers.html',
                             pending_brothers=treasurer_app.pending_brothers,
                             members=treasurer_app.members)
    
    # POST request - process verification
    pending_id = request.form.get('pending_id')
    member_id = request.form.get('member_id')
    action = request.form.get('action')
    
    if action == 'verify' and pending_id and member_id:
        success, message = treasurer_app.verify_brother_with_member(pending_id, member_id)
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
    elif action == 'reject' and pending_id:
        # Remove pending registration
        if pending_id in treasurer_app.pending_brothers:
            del treasurer_app.pending_brothers[pending_id]
            treasurer_app.save_data(treasurer_app.pending_brothers_file, treasurer_app.pending_brothers)
            flash('Registration rejected and removed.', 'info')
        else:
            flash('Registration not found.', 'error')
    
    return redirect(url_for('verify_brothers'))

@app.route('/role_management')
@require_auth
@require_permission('assign_roles')
def role_management():
    """Role management interface for treasurers"""
    # Force reload member data to ensure fresh data
    treasurer_app.members = treasurer_app.load_data(treasurer_app.members_file, {})
    
    # Log current executive board for debugging
    executive_roles = ['treasurer', 'president', 'vice_president', 'social_chair', 'phi_ed_chair', 'brotherhood_chair', 'recruitment_chair']
    print(f"✅ Current Executive Board:")
    for exec_role in executive_roles:
        assigned_members = []
        for member_id, member in treasurer_app.members.items():
            member_role = member.role if hasattr(member, 'role') else member.get('role', 'brother')
            if member_role == exec_role:
                member_name = member.name if hasattr(member, 'name') else member.get('name', 'Unknown')
                assigned_members.append(member_name)
        
        if assigned_members:
            print(f"  {exec_role}: {', '.join(assigned_members)}")
        else:
            print(f"  {exec_role}: VACANT")
    
    return render_template('role_management.html', members=treasurer_app.members)

@app.route('/assign_role', methods=['POST'])
@require_auth
@require_permission('assign_roles')
def assign_role():
    """Assign a role to a member"""
    member_id = request.form.get('member_id')
    role = request.form.get('role')
    
    if not member_id or not role:
        flash('Member and role must be specified.', 'error')
        return redirect(url_for('role_management'))
    
    if member_id not in treasurer_app.members:
        flash('Member not found.', 'error')
        return redirect(url_for('role_management'))
    
    # Check if role is already taken (except for brother role)
    if role != 'brother':
        for existing_id, existing_member in treasurer_app.members.items():
            if hasattr(existing_member, 'role') and existing_member.role == role and existing_id != member_id:
                flash(f'{role.replace("_", " ").title()} position is already filled by {existing_member.name}.', 'warning')
                return redirect(url_for('role_management'))
    
    # Update member role in JSON system
    member = treasurer_app.members[member_id]
    old_role = member.role if hasattr(member, 'role') and member.role else 'brother'
    member.role = role
    
    # Also update in SQLAlchemy system if user account exists
    try:
        from models import db, User, Role
        if hasattr(member, 'user_id') and member.user_id:
            user = User.query.get(member.user_id)
            if user:
                # Clear existing roles (except admin which should be preserved)
                user.roles = [r for r in user.roles if r.name == 'admin']
                
                # Add new role
                if role != 'brother':  # brother is default, no explicit role needed
                    role_obj = Role.query.filter_by(name=role).first()
                    if not role_obj:
                        # Create role if it doesn't exist
                        role_obj = Role(name=role, description=f'{role.replace("_", " ").title()} role')
                        db.session.add(role_obj)
                    user.roles.append(role_obj)
                
                # Always ensure brother role exists as base
                brother_role = Role.query.filter_by(name='brother').first()
                if not brother_role:
                    brother_role = Role(name='brother', description='Brother role')
                    db.session.add(brother_role)
                if brother_role not in user.roles:
                    user.roles.append(brother_role)
                
                db.session.commit()
                print(f"Updated SQLAlchemy roles for user {user.full_name}: {[r.name for r in user.roles]}")
    except Exception as e:
        print(f"SQLAlchemy role update failed (continuing with JSON): {e}")
        # Continue with JSON-only update if SQLAlchemy fails
    
    # Save JSON changes
    try:
        treasurer_app.save_data(treasurer_app.members_file, treasurer_app.members)
        print(f"✅ Successfully saved role assignment: {member.name} -> {role}")
        print(f"✅ Member data after save: role={member.role}")
    except Exception as e:
        print(f"❌ Failed to save member data: {e}")
        flash(f'Error saving role assignment: {e}', 'error')
        return redirect(url_for('role_management'))
    
    # Verify the assignment was saved
    updated_members = treasurer_app.load_data(treasurer_app.members_file, {})
    updated_member = updated_members.get(member_id)
    if updated_member and hasattr(updated_member, 'role'):
        print(f"✅ Verification: {updated_member.name} role is now {updated_member.role}")
        flash(f'{member.name} has been successfully assigned as {role.replace("_", " ").title()}.', 'success')
    elif updated_member and isinstance(updated_member, dict):
        print(f"✅ Verification: {updated_member.get('name')} role is now {updated_member.get('role')}")
        flash(f'{member.name} has been successfully assigned as {role.replace("_", " ").title()}.', 'success')
    else:
        print(f"❌ Verification failed: could not confirm role assignment")
        flash(f'Role assignment may have failed. Please check the Executive Board.', 'warning')
    
    return redirect(url_for('role_management'))

@app.route('/change_role', methods=['POST'])
@require_auth
@require_permission('assign_roles')
def change_role():
    """Change a member's role"""
    member_id = request.form.get('member_id')
    new_role = request.form.get('role')
    
    if not member_id or not new_role:
        flash('Member and role must be specified.', 'error')
        return redirect(url_for('role_management'))
    
    if member_id not in treasurer_app.members:
        flash('Member not found.', 'error')
        return redirect(url_for('role_management'))
    
    # Check if new role is already taken (except for brother role)
    if new_role != 'brother':
        for existing_id, existing_member in treasurer_app.members.items():
            if hasattr(existing_member, 'role') and existing_member.role == new_role and existing_id != member_id:
                flash(f'{new_role.replace("_", " ").title()} position is already filled by {existing_member.name}.', 'warning')
                return redirect(url_for('role_management'))
    
    # Update member role in JSON system
    member = treasurer_app.members[member_id]
    old_role = member.role if hasattr(member, 'role') and member.role else 'brother'
    member.role = new_role
    
    # Also update in SQLAlchemy system if user account exists
    try:
        from models import db, User, Role
        if hasattr(member, 'user_id') and member.user_id:
            user = User.query.get(member.user_id)
            if user:
                # Clear existing roles (except admin which should be preserved)
                user.roles = [r for r in user.roles if r.name == 'admin']
                
                # Add new role
                if new_role != 'brother':  # brother is default, no explicit role needed
                    role_obj = Role.query.filter_by(name=new_role).first()
                    if not role_obj:
                        # Create role if it doesn't exist
                        role_obj = Role(name=new_role, description=f'{new_role.replace("_", " ").title()} role')
                        db.session.add(role_obj)
                    user.roles.append(role_obj)
                
                # Always ensure brother role exists as base
                brother_role = Role.query.filter_by(name='brother').first()
                if not brother_role:
                    brother_role = Role(name='brother', description='Brother role')
                    db.session.add(brother_role)
                if brother_role not in user.roles:
                    user.roles.append(brother_role)
                
                db.session.commit()
                print(f"Updated SQLAlchemy roles for user {user.full_name}: {[r.name for r in user.roles]}")
    except Exception as e:
        print(f"SQLAlchemy role update failed (continuing with JSON): {e}")
        # Continue with JSON-only update if SQLAlchemy fails
    
    # Save JSON changes
    try:
        treasurer_app.save_data(treasurer_app.members_file, treasurer_app.members)
        print(f"✅ Successfully saved role change: {member.name} {old_role} -> {new_role}")
    except Exception as e:
        print(f"❌ Failed to save member data: {e}")
        flash(f'Error saving role change: {e}', 'error')
        return redirect(url_for('role_management'))
    
    # Verify the change was saved
    updated_members = treasurer_app.load_data(treasurer_app.members_file, {})
    updated_member = updated_members.get(member_id)
    if updated_member:
        updated_role = updated_member.get('role') if isinstance(updated_member, dict) else getattr(updated_member, 'role', 'brother')
        print(f"✅ Verification: {member.name} role is now {updated_role}")
    
    if new_role == old_role:
        flash(f'{member.name} role unchanged.', 'info')
    else:
        flash(f'{member.name} role changed from {old_role.replace("_", " ").title()} to {new_role.replace("_", " ").title()}.', 'success')
    
    return redirect(url_for('role_management'))

@app.route('/ai_assistant', methods=['GET', 'POST'])
@require_auth
def ai_assistant():
    if request.method == 'GET':
        return render_template('ai_assistant.html')
    
    user_message = request.form.get('message', '').lower().strip()
    response = get_ai_response(user_message)
    
    return jsonify({'response': response})

def get_ai_response(message):
    """Simple rule-based AI assistant responses"""
    
    # Troubleshooting responses
    if 'not working' in message or 'broken' in message or 'error' in message:
        return "🔧 **Troubleshooting Steps:**\n1. Try refreshing the page\n2. Check if all required fields are filled\n3. Restart the app using 'Start Treasurer App.command'\n4. Check the terminal for error messages\n\nWhat specific issue are you experiencing?"
    
    if 'email' in message and ('not send' in message or 'fail' in message):
        return "📧 **Email Issues:**\n1. Go to Treasurer Setup → Email Configuration\n2. Verify Gmail username is correct\n3. Use Gmail **App Password**, not regular password\n4. Test with your own email first\n\n**Get App Password:** Google Account → Security → 2-Step Verification → App passwords"
    
    if 'sms' in message or 'text' in message:
        return "📱 **SMS Issues:**\n1. SMS uses free email-to-SMS gateways\n2. Works with all major carriers: Verizon, AT&T, T-Mobile\n3. Use format: +1234567890 (include +1)\n4. Test via Notifications → 'Test SMS to Treasurer'\n\n**Tip:** SMS delivery may take 1-2 minutes"
    
    # Setup help
    if 'setup' in message or 'configure' in message or 'install' in message:
        return "⚙️ **Setup Guide:**\n1. **New Treasurer:** Login → Treasurer Setup → Configure credentials\n2. **Email:** Get Gmail App Password → Enter in Email Config\n3. **Phone:** Add your phone for SMS notifications\n4. **Test:** Use 'Test SMS to Treasurer' to verify setup\n\nNeed help with specific setup?"
    
    # Feature help
    if 'how to' in message or 'add member' in message:
        return "👥 **Member Management:**\n• **Add Single:** Dashboard → Member Management → Fill form\n• **Bulk Import:** Dashboard → 'Bulk Import' → Paste member list\n• **Payment:** Find member → 'Record Payment'\n• **Edit:** Click member name → Edit details\n\n**Tip:** Use bulk import for large member lists!"
    
    if 'payment' in message or 'dues' in message:
        return "💰 **Payment & Dues:**\n• **Record Payment:** Dashboard → Find member → Record Payment\n• **Send Reminders:** Selective Reminders → Choose members\n• **View Status:** Click member name for details\n• **Payment Plans:** Edit member → Choose plan (semester/monthly)\n\n**Custom Schedules:** Member Details → Custom Payment Schedule"
    
    if 'budget' in message or 'expense' in message:
        return "📊 **Budget & Expenses:**\n• **Set Budget:** Budget Management → Set limits per category\n• **Add Expense:** Dashboard → Add Transaction → Select 'Expense'\n• **Track Spending:** Budget Management shows % used\n• **Categories:** Executive, Social, Philanthropy, etc.\n\n**Monthly Reports:** Monthly Income page"
    
    if 'export' in message or 'backup' in message:
        return "📄 **Data Export & Backup:**\n• **CSV Export:** Export data to CSV files\n• **Manual Backup:** Copy entire app folder\n• **Handover:** All data preserved automatically\n• **Local Storage:** All data stored securely locally\n\n**Tip:** Regular backups ensure data safety!"
    
    if 'semester' in message or 'new year' in message:
        return "📅 **Semester Management:**\n• **New Semester:** Semesters → Create New Semester\n• **Auto-Archive:** Previous semester archived automatically\n• **View History:** All semesters page shows past terms\n• **Data:** All member/transaction data preserved\n\n**Best Practice:** Export data before creating new semester"
    
    # General help
    if 'help' in message or 'what can you do' in message:
        return "🤖 **I can help with:**\n• Troubleshooting issues\n• Setup and configuration\n• Member management\n• Payment processing\n• Budget tracking\n• Data export\n• Semester transitions\n\n**Ask me:** 'How to add members?' or 'Email not working?'"
    
    # Default response
    return "💡 **Common Questions:**\n• 'Email not working' - Email troubleshooting\n• 'How to add members' - Member management help\n• 'Setup help' - Configuration guidance\n• 'SMS issues' - Text message problems\n• 'Export data' - Backup and export help\n\n**Tip:** Be specific about your issue for better help!"

# This app is designed to run exclusively on cloud platforms (Render.com)
# Local development has been disabled - use the live deployment only
if __name__ == '__main__':
    # Check if we're on Render (cloud) by checking for PORT environment variable
    port = os.environ.get('PORT')
    
    if port:
        # We're on Render - start the app
        port = int(port)
        debug = os.environ.get('DEBUG', 'False').lower() == 'true'
        print(f"🚀 Starting Flask app on Render.com (port {port})")
        app.run(host='0.0.0.0', port=port, debug=debug)
    else:
        # Local environment - prevent hosting for security
        print("\n❌ LOCAL HOSTING DISABLED")
        print("\n🚀 This app runs exclusively on Render.com")
        print("\n📋 To access your app:")
        print("   Visit your Render dashboard and use the provided URL")
        print("\n🔒 Local hosting permanently disabled for security")
        import sys
        sys.exit(1)
