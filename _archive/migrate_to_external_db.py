#!/usr/bin/env python3
"""
Migrate JSON data to external database
Usage: python migrate_to_external_db.py <DATABASE_URL>
"""
import os
import sys
from migrate_data import main as run_migration

def main():
    if len(sys.argv) != 2:
        print("Usage: python migrate_to_external_db.py <DATABASE_URL>")
        print("Example: python migrate_to_external_db.py postgresql://user:pass@host:port/db")
        sys.exit(1)
    
    database_url = sys.argv[1]
    
    # Fix channel_binding parameter format issue
    if 'channel_binding=require' in database_url and database_url.endswith("require'"):
        database_url = database_url.replace("require'", "require")
    
    # Validate database URL format
    if not database_url.startswith(('postgresql://', 'postgres://')):
        print("❌ Invalid database URL. Must start with postgresql:// or postgres://")
        sys.exit(1)
    
    # Set environment variable for migration
    os.environ['DATABASE_URL'] = database_url
    os.environ['FLASK_ENV'] = 'production'
    
    print(f"🚀 Starting migration to external database...")
    print(f"📊 Database: {database_url[:30]}...")
    
    try:
        # Run the migration
        run_migration()
        
        print("✅ Migration completed successfully!")
        print("📋 Next steps:")
        print("1. Update DATABASE_URL in Render dashboard")
        print("2. Redeploy your app")
        print("3. Login with: 4808198055 / treasurer2024")
            
    except Exception as e:
        print(f"❌ Migration error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()