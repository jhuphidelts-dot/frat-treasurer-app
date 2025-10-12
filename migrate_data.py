"""
Data Migration Script
Migrates existing JSON data to the new SQLAlchemy database schema
"""
import os
import json
import gzip
from datetime import datetime
from flask import Flask
from models import (
    db, User, Role, Semester, Member, Payment, Transaction, 
    BudgetLimit, TreasurerConfig, init_default_roles
)

# Budget categories from the original app
BUDGET_CATEGORIES = [
    'Executive(GHQ, IFC, Flights)', 'Brotherhood', 'Social', 
    'Philanthropy', 'Recruitment', 'Phi ED', 'Housing', 'Bank Maintenance'
]

def load_json_data(file_path):
    """Load data from JSON file (supports compressed files)"""
    if not os.path.exists(file_path):
        # Try compressed version
        compressed_path = file_path + '.gz'
        if os.path.exists(compressed_path):
            with gzip.open(compressed_path, 'rt', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_app():
    """Create Flask app for migration"""
    app = Flask(__name__)
    
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fraternity.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    return app

def migrate_semesters(data_dir):
    """Migrate semester data"""
    print("📅 Migrating semesters...")
    
    semesters_file = os.path.join(data_dir, 'semesters.json')
    semesters_data = load_json_data(semesters_file)
    
    if not semesters_data:
        # Create default current semester if no data exists
        current_date = datetime.now()
        if current_date.month >= 8:
            season, year = 'Fall', current_date.year
        elif current_date.month <= 5:
            season, year = 'Spring', current_date.year
        else:
            season, year = 'Summer', current_date.year
        
        semester_id = f"{season.lower()}_{year}"
        semester = Semester(
            id=semester_id,
            name=f"{season} {year}",
            year=year,
            season=season,
            start_date=current_date,
            is_current=True
        )
        db.session.add(semester)
        print(f"   Created default semester: {semester.name}")
        return semester_id
    
    current_semester_id = None
    for semester_id, semester_data in semesters_data.items():
        semester = Semester(
            id=semester_data['id'],
            name=semester_data['name'],
            year=semester_data['year'],
            season=semester_data['season'],
            start_date=datetime.fromisoformat(semester_data['start_date']),
            end_date=datetime.fromisoformat(semester_data['end_date']) if semester_data.get('end_date') else None,
            is_current=semester_data.get('is_current', False),
            archived=semester_data.get('archived', False)
        )
        
        if semester.is_current:
            current_semester_id = semester.id
            
        db.session.add(semester)
        print(f"   Migrated semester: {semester.name}")
    
    return current_semester_id

def migrate_users_and_members(data_dir, current_semester_id):
    """Migrate users and members data"""
    print("👥 Migrating users and members...")
    
    # First, create the treasurer user based on existing data
    users_file = os.path.join(data_dir, 'users.json')
    users_data = load_json_data(users_file)
    
    treasurer_user = None
    if users_data:
        for username, user_data in users_data.items():
            if user_data.get('role') == 'admin':
                # Create treasurer user
                treasurer_user = User(
                    phone='+1234567890',  # Default phone, can be updated later
                    first_name='Treasurer',
                    last_name='Admin',
                    email='treasurer@fraternity.com',
                    status='active',
                    approved_at=datetime.utcnow()
                )
                treasurer_user.set_password('admin123')  # Keep existing password
                
                # Assign treasurer role
                treasurer_role = Role.query.filter_by(name='treasurer').first()
                if treasurer_role:
                    treasurer_user.roles.append(treasurer_role)
                
                db.session.add(treasurer_user)
                db.session.flush()  # Get the ID
                print(f"   Created treasurer user: {treasurer_user.full_name}")
                break
    
    # Migrate members
    members_file = os.path.join(data_dir, 'members.json')
    members_data = load_json_data(members_file)
    
    if not members_data:
        print("   No members data found")
        return
    
    for member_id, member_data in members_data.items():
        # Create member record
        member = Member(
            name=member_data['name'],
            contact=member_data.get('contact', member_data.get('phone', '')),
            contact_type=member_data.get('contact_type', 'phone'),
            dues_amount=member_data['dues_amount'],
            payment_plan=member_data['payment_plan'],
            semester_id=current_semester_id
        )
        
        # Set custom schedule if exists
        if member_data.get('custom_schedule'):
            member.set_custom_schedule(member_data['custom_schedule'])
        
        db.session.add(member)
        db.session.flush()  # Get the ID
        
        # Migrate payments for this member
        payments_made = member_data.get('payments_made', [])
        for payment_data in payments_made:
            payment = Payment(
                member_id=member.id,
                amount=payment_data['amount'],
                payment_method=payment_data.get('method', 'Unknown'),
                date=datetime.fromisoformat(payment_data['date']) if payment_data.get('date') else datetime.utcnow(),
                notes=f"Migrated payment ID: {payment_data.get('id', 'unknown')}"
            )
            db.session.add(payment)
        
        print(f"   Migrated member: {member.name} (${member.dues_amount}, {len(payments_made)} payments)")

def migrate_transactions(data_dir, current_semester_id):
    """Migrate transaction data"""
    print("💰 Migrating transactions...")
    
    transactions_file = os.path.join(data_dir, 'transactions.json')
    transactions_data = load_json_data(transactions_file)
    
    if not transactions_data:
        print("   No transactions data found")
        return
    
    for transaction_data in transactions_data:
        transaction = Transaction(
            date=datetime.fromisoformat(transaction_data['date']),
            category=transaction_data['category'],
            description=transaction_data['description'],
            amount=transaction_data['amount'],
            type=transaction_data['type'],
            semester_id=current_semester_id
        )
        
        db.session.add(transaction)
        
    print(f"   Migrated {len(transactions_data)} transactions")

def migrate_budget_limits(data_dir, current_semester_id):
    """Migrate budget limits"""
    print("💵 Migrating budget limits...")
    
    budget_file = os.path.join(data_dir, 'budget.json')
    budget_data = load_json_data(budget_file)
    
    if not budget_data:
        print("   No budget data found, creating default limits")
        # Create default budget limits with 0 amounts
        for category in BUDGET_CATEGORIES:
            budget_limit = BudgetLimit(
                category=category,
                semester_id=current_semester_id,
                amount=0.0
            )
            db.session.add(budget_limit)
        return
    
    for category, amount in budget_data.items():
        budget_limit = BudgetLimit(
            category=category,
            semester_id=current_semester_id,
            amount=float(amount)
        )
        db.session.add(budget_limit)
        print(f"   Migrated budget limit: {category} = ${amount}")

def migrate_treasurer_config(data_dir):
    """Migrate treasurer configuration"""
    print("⚙️  Migrating treasurer configuration...")
    
    config_file = os.path.join(data_dir, 'treasurer_config.json')
    config_data = load_json_data(config_file)
    
    if config_data:
        treasurer_config = TreasurerConfig(
            name=config_data.get('name', ''),
            email=config_data.get('email', ''),
            phone=config_data.get('phone', ''),
            smtp_username=config_data.get('smtp_username', ''),
            smtp_password=config_data.get('smtp_password', ''),
            twilio_sid=config_data.get('twilio_sid', ''),
            twilio_token=config_data.get('twilio_token', ''),
            twilio_phone=config_data.get('twilio_phone', ''),
            google_credentials_path=config_data.get('google_credentials_path', ''),
            google_sheets_id=config_data.get('google_sheets_id', '')
        )
        db.session.add(treasurer_config)
        print(f"   Migrated treasurer config for: {treasurer_config.name}")
    else:
        print("   No treasurer config found, creating empty config")
        treasurer_config = TreasurerConfig()
        db.session.add(treasurer_config)

def backup_existing_data(data_dir):
    """Create backup of existing JSON files"""
    print("🔄 Creating backup of existing data...")
    
    backup_dir = os.path.join(data_dir, 'backup_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    os.makedirs(backup_dir, exist_ok=True)
    
    json_files = ['members.json', 'transactions.json', 'budget.json', 'users.json', 'semesters.json', 'treasurer_config.json']
    
    for json_file in json_files:
        file_path = os.path.join(data_dir, json_file)
        compressed_path = file_path + '.gz'
        
        # Check for regular file
        if os.path.exists(file_path):
            import shutil
            shutil.copy2(file_path, backup_dir)
            print(f"   Backed up: {json_file}")
        
        # Check for compressed file
        elif os.path.exists(compressed_path):
            import shutil
            shutil.copy2(compressed_path, backup_dir)
            print(f"   Backed up: {json_file}.gz")
    
    print(f"   Backup created in: {backup_dir}")
    return backup_dir

def main():
    """Main migration function"""
    print("🚀 Starting data migration...")
    print("=" * 50)
    
    # Setup
    app = create_app()
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    
    if not os.path.exists(data_dir):
        print(f"❌ Data directory not found: {data_dir}")
        return
    
    with app.app_context():
        # Create tables
        print("🏗️  Creating database tables...")
        db.create_all()
        
        # Initialize default roles
        print("👑 Initializing default roles...")
        init_default_roles()
        
        # Create backup
        backup_dir = backup_existing_data(data_dir)
        
        try:
            # Perform migrations
            current_semester_id = migrate_semesters(data_dir)
            migrate_users_and_members(data_dir, current_semester_id)
            migrate_transactions(data_dir, current_semester_id)
            migrate_budget_limits(data_dir, current_semester_id)
            migrate_treasurer_config(data_dir)
            
            # Commit all changes
            db.session.commit()
            
            print("=" * 50)
            print("✅ Migration completed successfully!")
            print(f"📁 Database created: fraternity.db")
            print(f"💾 Backup created: {backup_dir}")
            print(f"👤 Default login: +1234567890 / admin123")
            print("\n📋 Next steps:")
            print("1. Update treasurer phone number and password")
            print("2. Test existing features with new database")
            print("3. Begin implementing role-based access control")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    main()