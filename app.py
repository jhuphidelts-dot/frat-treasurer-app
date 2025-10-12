from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.text import MIMEText
from twilio.rest import Client
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
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Import Flask blueprints
from notifications import notifications_bp
from export_system import export_bp


# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")  # needed for flash()
SHEET_ID = "1im714pqV9b9jA6fQDH_GmIrpBwKm7IWViu27whK6aGo"
SERVICE_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")

# Register blueprints
app.register_blueprint(notifications_bp)
app.register_blueprint(export_bp)

def export_to_google_sheet():
    creds = Credentials.from_service_account_file(
        SERVICE_FILE,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)

    # Brothers
    with open("members.json", "r") as f:
        members = json.load(f)
    df_members = pd.DataFrame(members)
    ws = sheet.worksheet("Brothers")
    ws.clear()
    ws.update([df_members.columns.tolist()] + df_members.values.tolist())

    # Transactions
    with open("transactions.json", "r") as f:
        tx = json.load(f)
    df_tx = pd.DataFrame(tx)
    ws = sheet.worksheet("Transactions")
    ws.clear()
    ws.update([df_tx.columns.tolist()] + df_tx.values.tolist())

    # Overview (budget)
    with open("budget.json", "r") as f:
        budget = json.load(f)
    df_budget = pd.DataFrame(budget)
    ws = sheet.worksheet("Overview")
    ws.clear()
    ws.update([df_budget.columns.tolist()] + df_budget.values.tolist())




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
class TreasurerConfig:
    name: str = ""
    email: str = ""
    phone: str = ""
    smtp_username: str = ""
    smtp_password: str = ""
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_phone: str = ""
    google_credentials_path: str = ""
    google_sheets_id: str = ""

class TreasurerApp:
    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(__file__), 'data')
        self.members_file = os.path.join(self.data_dir, 'members.json')
        self.transactions_file = os.path.join(self.data_dir, 'transactions.json')
        self.budget_file = os.path.join(self.data_dir, 'budget.json')
        self.users_file = os.path.join(self.data_dir, 'users.json')
        self.semesters_file = os.path.join(self.data_dir, 'semesters.json')
        self.treasurer_config_file = os.path.join(self.data_dir, 'treasurer_config.json')
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Load existing data or initialize empty
        self.members = self.load_data(self.members_file, {})
        self.transactions = self.load_data(self.transactions_file, [])
        self.budget_limits = self.load_data(self.budget_file, {category: 0.0 for category in BUDGET_CATEGORIES})
        self.users = self.load_data(self.users_file, {})
        self.semesters = self.load_data(self.semesters_file, {})
        self.treasurer_config = self.load_treasurer_config()
        
        # Create default admin user if no users exist
        if not self.users:
            self.create_user('admin', 'admin123', 'admin')
        
        # Initialize current semester if none exists
        if not self.semesters:
            self.create_default_semester()
        
        self.current_semester = self.get_current_semester()
        
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.setup_reminders()
        
        # Auto-optimize storage on startup (lightweight check)
        self._auto_optimize_if_needed()

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
                            contact_type=contact_type
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
                    config.twilio_sid = config_data.get('twilio_sid', '')
                    config.twilio_token = config_data.get('twilio_token', '')
                    config.twilio_phone = config_data.get('twilio_phone', '')
                    config.google_credentials_path = config_data.get('google_credentials_path', '')
                    config.google_sheets_id = config_data.get('google_sheets_id', '')
            except Exception as e:
                print(f"Error loading treasurer config: {e}")
        
        # Fallback to environment variables if not in file
        if not config.smtp_username:
            config.smtp_username = os.getenv('SMTP_USERNAME', '')
        if not config.smtp_password:
            config.smtp_password = os.getenv('SMTP_PASSWORD', '')
        if not config.twilio_sid:
            config.twilio_sid = os.getenv('TWILIO_ACCOUNT_SID', '')
        if not config.twilio_token:
            config.twilio_token = os.getenv('TWILIO_AUTH_TOKEN', '')
        if not config.twilio_phone:
            config.twilio_phone = os.getenv('TWILIO_PHONE_NUMBER', '')
        if not config.google_credentials_path:
            config.google_credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', '')
        if not config.google_sheets_id:
            config.google_sheets_id = os.getenv('GOOGLE_SHEETS_ID', '')
        
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
        """Optimize all data files for storage"""
        print("Optimizing data storage...")
        
        # Recompress all large files
        data_files = [
            self.members_file,
            self.transactions_file,
            self.budget_file,
            self.semesters_file
        ]
        
        for file_path in data_files:
            if os.path.exists(file_path):
                # Load and resave to trigger compression
                data = self.load_data(file_path, {})
                if data:
                    self.save_data(file_path, data)
        
        # Cleanup unnecessary files
        self.cleanup_old_files()
        
        print("Data storage optimization complete!")
    
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
        else:
            serialized_data = data
        
        # Use compression for large files
        if self.should_compress_file(file_path) or len(str(serialized_data)) > 5000:
            compressed_path = file_path + '.gz'
            with gzip.open(compressed_path, 'wt', encoding='utf-8') as f:
                json.dump(serialized_data, f, separators=(',', ':'))  # Compact JSON
            # Remove uncompressed version if it exists
            if os.path.exists(file_path):
                os.remove(file_path)
        else:
            # Save normally for small files
            with open(file_path, 'w') as f:
                json.dump(serialized_data, f, separators=(',', ':'))  # Compact JSON
        
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
    
    def update_member(self, member_id, name, contact, dues_amount, payment_plan, custom_schedule=None):
        """Update existing member information"""
        if member_id in self.members:
            member = self.members[member_id]
            member.name = name
            member.contact = contact
            # Auto-detect contact type
            member.contact_type = 'email' if '@' in contact and '.' in contact else 'phone'
            member.dues_amount = dues_amount
            member.payment_plan = payment_plan
            
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
                client = Client(account_sid, auth_token)
                sms_message = client.messages.create(
                    body=message,
                    from_=from_phone,
                    to=phone
                )
                print(f"SMS sent via Twilio to {phone}")
                return True
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
                
                server = smtplib.SMTP('smtp.gmail.com', 587)
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
            server = smtplib.SMTP('smtp.gmail.com', 587)
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
        
        # Send reminders to members with outstanding balances
        for member_id, member in members_to_check.items():
            balance = self.get_member_balance(member_id)
            print(f"DEBUG: Member {member.name} balance: ${balance:.2f}")
            
            if balance > 0:
                print(f"DEBUG: Sending reminder to {member.name} ({member.contact_type}: {member.contact})")
                message = f"Hi {member.name}! Your fraternity dues balance is ${balance:.2f}. Please pay via Zelle or Venmo. Thanks!"
                
                result = self.send_notification(member.contact, message, member.contact_type)
                if result:
                    reminders_sent += 1
                    print(f"SUCCESS: Reminder sent to {member.name}")
                else:
                    print(f"FAILED: Could not send reminder to {member.name}")
            else:
                print(f"DEBUG: {member.name} has no outstanding balance, skipping")
        
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
        return redirect(url_for('index'))
    else:
        flash('Invalid username or password')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out')
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
        return redirect(url_for('index'))
    else:
        flash('Current password is incorrect')
        return redirect(url_for('change_password'))

@app.route('/monthly_income')
@require_auth
def monthly_income():
    monthly_data = treasurer_app.get_monthly_income_summary()
    return render_template('monthly_income.html', monthly_data=monthly_data)

@app.route('/')
@require_auth
def index():
    dues_summary = treasurer_app.get_dues_collection_summary()
    return render_template('index.html', 
                         members=treasurer_app.members,
                         budget_summary=treasurer_app.get_budget_summary(),
                         dues_summary=dues_summary,
                         categories=BUDGET_CATEGORIES)

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
def add_member():
    name = request.form['name']
    contact = request.form.get('contact', request.form.get('phone', ''))  # Support both field names
    dues_amount = float(request.form['dues_amount'])
    payment_plan = request.form['payment_plan']
    
    member_id = treasurer_app.add_member(name, contact, dues_amount, payment_plan)
    flash(f'Member {name} added successfully!')
    return redirect(url_for('index'))

@app.route('/add_transaction', methods=['POST'])
@require_auth
def add_transaction():
    category = request.form['category']
    description = request.form['description']
    amount = float(request.form['amount'])
    transaction_type = request.form['type']
    
    treasurer_app.add_transaction(category, description, amount, transaction_type)
    flash('Transaction added successfully!')
    return redirect(url_for('index'))

@app.route('/edit_transaction/<transaction_id>', methods=['GET', 'POST'])
@require_auth
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
def record_payment():
    member_id = request.form['member_id']
    amount = float(request.form['amount'])
    payment_method = request.form['payment_method']
    
    if treasurer_app.record_payment(member_id, amount, payment_method):
        flash('Payment recorded successfully!')
    else:
        flash('Error recording payment!')
    
    return redirect(url_for('index'))

@app.route('/send_reminders')
@require_auth
def send_reminders():
    treasurer_app.check_and_send_reminders()
    flash('Reminders sent to all eligible members!')
    return redirect(url_for('index'))

@app.route('/selective_reminders', methods=['GET', 'POST'])
@require_auth
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
        flash('No members selected for reminders!')
        return redirect(url_for('selective_reminders'))
    
    treasurer_app.check_and_send_reminders(selected_members)
    flash(f'Reminders sent to {len(selected_members)} selected member(s)!')
    return redirect(url_for('index'))

@app.route('/budget_summary')
@require_auth
def budget_summary():
    return jsonify(treasurer_app.get_budget_summary())

@app.route('/bulk_import', methods=['GET', 'POST'])
@require_auth
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
    return redirect(url_for('index'))

@app.route('/edit_member/<member_id>', methods=['GET', 'POST'])
@require_auth
def edit_member(member_id):
    if request.method == 'GET':
        if member_id not in treasurer_app.members:
            flash('Member not found!')
            return redirect(url_for('index'))
        
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
    
    if treasurer_app.update_member(member_id, name, contact, dues_amount, payment_plan):
        flash(f'Member {name} updated successfully!')
    else:
        flash('Error updating member!')
    
    return redirect(url_for('index'))

@app.route('/remove_member/<member_id>', methods=['POST'])
@require_auth
def remove_member(member_id):
    if member_id in treasurer_app.members:
        member_name = treasurer_app.members[member_id].name
        if treasurer_app.remove_member(member_id):
            flash(f'Member {member_name} removed successfully!')
        else:
            flash('Error removing member!')
    else:
        flash('Member not found!')
    
    return redirect(url_for('index'))

@app.route('/member_details/<member_id>')
@require_auth
def member_details(member_id):
    if member_id not in treasurer_app.members:
        flash('Member not found!')
        return redirect(url_for('index'))
    
    member = treasurer_app.members[member_id]
    payment_schedule = treasurer_app.get_member_payment_schedule(member_id)
    balance = treasurer_app.get_member_balance(member_id)
    
    return render_template('member_details.html',
                         member=member,
                         payment_schedule=payment_schedule,
                         balance=balance)

@app.route('/budget_management', methods=['GET', 'POST'])
@require_auth
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
def custom_payment_schedule(member_id):
    if member_id not in treasurer_app.members:
        flash('Member not found!')
        return redirect(url_for('index'))
    
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

@app.route('/sync_status')
@require_auth
def sync_status():
    """Show Google Sheets sync status"""
    credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH')
    spreadsheet_id = os.getenv('GOOGLE_SHEETS_ID')
    
    status = {
        'configured': bool(credentials_path and spreadsheet_id),
        'credentials_exist': bool(credentials_path and os.path.exists(credentials_path)),
        'credentials_path': credentials_path,
        'spreadsheet_id': spreadsheet_id
    }
    
    return jsonify(status)

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

@app.route("/export_to_sheet")
def export_to_sheet():
    try:
        export_to_google_sheet()
        flash("Exported data to Google Sheet successfully!")
    except Exception as e:
        flash(f"Export failed: {e}")
    return redirect(url_for("index"))

@app.route('/treasurer_setup', methods=['GET', 'POST'])
@require_auth
def treasurer_setup():
    if request.method == 'GET':
        return render_template('treasurer_setup.html', config=treasurer_app.treasurer_config)
    
    # POST - Update treasurer configuration
    config = treasurer_app.treasurer_config
    config.name = request.form.get('name', '')
    config.email = request.form.get('email', '')
    config.phone = request.form.get('phone', '')
    config.smtp_username = request.form.get('smtp_username', '')
    config.smtp_password = request.form.get('smtp_password', '')
    config.twilio_sid = request.form.get('twilio_sid', '')
    config.twilio_token = request.form.get('twilio_token', '')
    config.twilio_phone = request.form.get('twilio_phone', '')
    config.google_credentials_path = request.form.get('google_credentials_path', '')
    config.google_sheets_id = request.form.get('google_sheets_id', '')
    
    treasurer_app.save_treasurer_config()
    flash('Treasurer configuration updated successfully!')
    return redirect(url_for('treasurer_setup'))

@app.route('/handover_treasurer', methods=['GET', 'POST'])
@require_auth
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
    config.twilio_sid = ""
    config.twilio_token = ""
    config.twilio_phone = ""
    
    treasurer_app.save_treasurer_config()
    
    # Archive current semester
    current_sem = treasurer_app.get_current_semester()
    if current_sem:
        current_sem.is_current = False
        current_sem.archived = True
        current_sem.end_date = datetime.now().isoformat()
    
    treasurer_app.save_data(treasurer_app.semesters_file, treasurer_app.semesters)
    
    flash('Treasurer handover completed! Please provide setup instructions to the new treasurer.')
    return redirect(url_for('index'))

@app.route('/optimize_storage')
@require_auth
def optimize_storage():
    """Optimize data storage and clean up files"""
    try:
        treasurer_app.optimize_data_storage()
        flash('Storage optimization completed successfully! Temporary files removed and data compressed.')
    except Exception as e:
        flash(f'Optimization failed: {e}')
    return redirect(url_for('index'))

@app.route('/semester_management', methods=['GET', 'POST'])
@require_auth
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

@app.route('/export_improved_sheets')
@require_auth
def export_improved_sheets():
    """Export data in improved Google Sheets format"""
    try:
        # Create formatted data for easy copy-paste
        members_data = [['Name', 'Contact', 'Contact Type', 'Dues Amount', 'Total Paid', 'Balance', 'Status']]
        for member in treasurer_app.members.values():
            total_paid = sum(payment['amount'] for payment in member.payments_made)
            balance = member.dues_amount - total_paid
            status = 'Paid' if balance <= 0 else f'Owes ${balance:.2f}'
            members_data.append([member.name, member.contact, member.contact_type, 
                               f'${member.dues_amount:.2f}', f'${total_paid:.2f}', f'${balance:.2f}', status])
        
        transactions_data = [['Date', 'Category', 'Description', 'Amount', 'Type']]
        for transaction in treasurer_app.transactions:
            date_str = transaction.date[:10] if len(transaction.date) >= 10 else transaction.date
            transactions_data.append([date_str, transaction.category, transaction.description,
                                    f'${transaction.amount:.2f}', transaction.type.title()])
        
        budget_data = [['Category', 'Budget Limit', 'Spent', 'Remaining', 'Percent Used']]
        budget_summary = treasurer_app.get_budget_summary()
        for category, summary in budget_summary.items():
            budget_data.append([category, f'${summary["budget_limit"]:.2f}', 
                              f'${summary["spent"]:.2f}', f'${summary["remaining"]:.2f}',
                              f'{summary["percent_used"]:.1f}%'])
        
        # Save to temporary files for easy access
        import csv, tempfile, os
        temp_dir = tempfile.gettempdir()
        
        with open(os.path.join(temp_dir, 'members_export.csv'), 'w', newline='') as f:
            csv.writer(f).writerows(members_data)
        with open(os.path.join(temp_dir, 'transactions_export.csv'), 'w', newline='') as f:
            csv.writer(f).writerows(transactions_data)
        with open(os.path.join(temp_dir, 'budget_export.csv'), 'w', newline='') as f:
            csv.writer(f).writerows(budget_data)
        
        flash(f'Data exported successfully! CSV files saved to: {temp_dir}')
        flash('Files: members_export.csv, transactions_export.csv, budget_export.csv')
        
    except Exception as e:
        flash(f'Export failed: {e}')
    
    return redirect(url_for('index'))

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
        return "📱 **SMS Issues:**\n1. SMS uses email-to-SMS gateways (free but slower)\n2. Try different carriers: Verizon, AT&T, T-Mobile\n3. Use format: +1234567890 (include +1)\n4. For reliable SMS, configure Twilio in Treasurer Setup\n\n**Test:** Send reminder to yourself first"
    
    # Setup help
    if 'setup' in message or 'configure' in message or 'install' in message:
        return "⚙️ **Setup Guide:**\n1. **New Treasurer:** Login → Treasurer Setup → Configure credentials\n2. **Email:** Get Gmail App Password → Enter in Email Config\n3. **Handover:** Complete checklist → Click 'Complete Handover'\n4. **Backup:** Export to Google Sheets monthly\n\nNeed help with specific setup?"
    
    # Feature help
    if 'how to' in message or 'add member' in message:
        return "👥 **Member Management:**\n• **Add Single:** Dashboard → Member Management → Fill form\n• **Bulk Import:** Dashboard → 'Bulk Import' → Paste member list\n• **Payment:** Find member → 'Record Payment'\n• **Edit:** Click member name → Edit details\n\n**Tip:** Use bulk import for large member lists!"
    
    if 'payment' in message or 'dues' in message:
        return "💰 **Payment & Dues:**\n• **Record Payment:** Dashboard → Find member → Record Payment\n• **Send Reminders:** Selective Reminders → Choose members\n• **View Status:** Click member name for details\n• **Payment Plans:** Edit member → Choose plan (semester/monthly)\n\n**Custom Schedules:** Member Details → Custom Payment Schedule"
    
    if 'budget' in message or 'expense' in message:
        return "📊 **Budget & Expenses:**\n• **Set Budget:** Budget Management → Set limits per category\n• **Add Expense:** Dashboard → Add Transaction → Select 'Expense'\n• **Track Spending:** Budget Management shows % used\n• **Categories:** Executive, Social, Philanthropy, etc.\n\n**Monthly Reports:** Monthly Income page"
    
    if 'export' in message or 'backup' in message or 'google sheets' in message:
        return "📄 **Data Export & Backup:**\n• **CSV Export:** Semesters → 'Export Current Semester'\n• **Google Sheets:** Configure in Treasurer Setup first\n• **Manual Backup:** Copy entire app folder\n• **Handover:** All data preserved automatically\n\n**Tip:** Export monthly for backup!"
    
    if 'semester' in message or 'new year' in message:
        return "📅 **Semester Management:**\n• **New Semester:** Semesters → Create New Semester\n• **Auto-Archive:** Previous semester archived automatically\n• **View History:** All semesters page shows past terms\n• **Data:** All member/transaction data preserved\n\n**Best Practice:** Export data before creating new semester"
    
    # General help
    if 'help' in message or 'what can you do' in message:
        return "🤖 **I can help with:**\n• Troubleshooting issues\n• Setup and configuration\n• Member management\n• Payment processing\n• Budget tracking\n• Data export\n• Semester transitions\n\n**Ask me:** 'How to add members?' or 'Email not working?'"
    
    # Default response
    return "💡 **Common Questions:**\n• 'Email not working' - Email troubleshooting\n• 'How to add members' - Member management help\n• 'Setup help' - Configuration guidance\n• 'SMS issues' - Text message problems\n• 'Export data' - Backup and export help\n\n**Tip:** Be specific about your issue for better help!"

if __name__ == '__main__':
    import os
    # Use port from environment (Replit sets this automatically)
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    # Use 0.0.0.0 for Replit compatibility
    app.run(host='0.0.0.0', port=port, debug=debug)
