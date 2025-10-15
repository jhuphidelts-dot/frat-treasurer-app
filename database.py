"""
Database configuration and utilities
"""
import os
from flask import Flask
from models import db, init_default_roles, User, Role, Member, Transaction, Semester

def create_app(config_mode='development'):
    """Create and configure Flask app"""
    app = Flask(__name__)
    
    # Database configuration
    if config_mode == 'production':
        # PostgreSQL for production (Render.com)
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            # Fix postgres:// to postgresql:// for SQLAlchemy
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
            print(f"🔗 Using PostgreSQL: {database_url[:50]}...")
        else:
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fraternity.db'
            print("🔗 Using SQLite fallback")
    else:
        # SQLite for development
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fraternity.db'
        print("🔗 Using SQLite for development")
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-production')
    
    # Initialize database
    db.init_app(app)
    
    return app

def init_database(app):
    """Initialize database tables and default data"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Initialize default roles
        init_default_roles()
        
        # Check if there's a treasurer user
        from models import User, Role
        treasurer = User.query.join(User.roles).filter(Role.name == 'treasurer').first()
        if not treasurer:
            print("No treasurer user found, creating Ebubechi Onyia with treasurer role...")
            # Create Ebubechi as a brother and assign treasurer role
            ebubechi = User(
                phone="4808198055",  # Correct phone number
                first_name="Ebubechi",
                last_name="Onyia",
                email="ebubechi@example.com",  # Update with your real email
                status="active"
            )
            ebubechi.set_password("treasurer2024")  # Secure initial password
            
            # Assign treasurer role (this brother is currently the treasurer)
            treasurer_role = Role.query.filter_by(name='treasurer').first()
            if treasurer_role:
                ebubechi.roles.append(treasurer_role)
            
            db.session.add(ebubechi)
            db.session.commit()
            print("✅ Created Ebubechi Onyia and assigned treasurer role")
            print("📱 Phone: 4808198055")
            print("🔒 Password: treasurer2024")
            print("💡 Treasurer role can be transferred to other brothers via admin panel")
        
        print("Database initialized successfully!")

def check_database_status():
    """Check current database status"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if tables exist
            users_count = User.query.count()
            roles_count = Role.query.count()
            members_count = Member.query.count()
            transactions_count = Transaction.query.count()
            semesters_count = Semester.query.count()
            
            print("📊 Database Status:")
            print(f"   Users: {users_count}")
            print(f"   Roles: {roles_count}")
            print(f"   Members: {members_count}")
            print(f"   Transactions: {transactions_count}")
            print(f"   Semesters: {semesters_count}")
            
            # Check current semester
            current_semester = Semester.query.filter_by(is_current=True).first()
            if current_semester:
                print(f"   Current Semester: {current_semester.name}")
            
            # Check treasurer user
            treasurer = User.query.join(User.roles).filter(Role.name == 'treasurer').first()
            if treasurer:
                print(f"   Treasurer: {treasurer.full_name} ({treasurer.phone})")
            
            return True
            
        except Exception as e:
            print(f"❌ Database error: {e}")
            return False

def create_treasurer_user(phone, first_name, last_name, password, email=None):
    """Create a new treasurer user"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if user already exists
            existing_user = User.query.filter_by(phone=phone).first()
            if existing_user:
                print(f"❌ User with phone {phone} already exists")
                return False
            
            # Create new user
            user = User(
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                email=email,
                status='active'
            )
            user.set_password(password)
            
            # Assign treasurer role
            treasurer_role = Role.query.filter_by(name='treasurer').first()
            if treasurer_role:
                user.roles.append(treasurer_role)
            
            db.session.add(user)
            db.session.commit()
            
            print(f"✅ Created treasurer user: {user.full_name} ({user.phone})")
            return True
            
        except Exception as e:
            print(f"❌ Failed to create user: {e}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'init':
            app = create_app()
            init_database(app)
        
        elif command == 'status':
            check_database_status()
        
        elif command == 'create-treasurer':
            if len(sys.argv) != 6:
                print("Usage: python database.py create-treasurer <phone> <first_name> <last_name> <password>")
                sys.exit(1)
            
            phone, first_name, last_name, password = sys.argv[2:6]
            create_treasurer_user(phone, first_name, last_name, password)
        
        elif command == 'force-init':
            # Force initialize database with production config
            app = create_app('production')
            print("🚀 Force initializing database for production...")
            init_database(app)
        
        else:
            print("Available commands: init, status, create-treasurer, force-init")
    
    else:
        print("Usage: python database.py <command>")
        print("Commands:")
        print("  init              - Initialize database")
        print("  status            - Check database status")  
        print("  create-treasurer  - Create treasurer user")
        print("  force-init        - Force initialize database for production")
