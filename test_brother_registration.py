#!/usr/bin/env python3
"""
Test script to register a brother and verify data persistence
"""

import sys
import os
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app import treasurer_app

def test_brother_registration():
    """Test brother registration process"""
    print("🧪 TESTING BROTHER REGISTRATION")
    print("=" * 50)
    
    # Test data
    test_name = "Test Brother"
    test_phone = "5551234567"
    test_email = "testbrother@example.com"
    
    print(f"📝 Registering test brother:")
    print(f"   Name: {test_name}")
    print(f"   Phone: {test_phone}")
    print(f"   Email: {test_email}")
    
    try:
        # Register the brother
        pending_id = treasurer_app.register_brother(test_name, test_phone, test_email)
        print(f"✅ Registration successful! Pending ID: {pending_id}")
        
        # Check if it's in memory
        if pending_id in treasurer_app.pending_brothers:
            print(f"✅ Found in memory: {treasurer_app.pending_brothers[pending_id].full_name}")
        else:
            print("❌ Not found in memory!")
        
        # Force reload from disk to test persistence
        print("\n🔄 Testing data persistence by reloading from disk...")
        reloaded_pending = treasurer_app.load_data(treasurer_app.pending_brothers_file, {})
        
        if pending_id in reloaded_pending:
            brother = reloaded_pending[pending_id]
            print(f"✅ Found after reload: {brother['full_name']} ({brother['email']})")
            print(f"   Registration date: {brother['registration_date']}")
            
            # Clean up test data
            print("\n🧹 Cleaning up test data...")
            del treasurer_app.pending_brothers[pending_id]
            treasurer_app.save_data(treasurer_app.pending_brothers_file, treasurer_app.pending_brothers)
            print("✅ Test data cleaned up")
            
        else:
            print("❌ NOT FOUND after reload - persistence failed!")
            return False
            
    except Exception as e:
        print(f"❌ Registration failed: {e}")
        return False
    
    return True

def check_current_data():
    """Check current state of data"""
    print("\n📊 CURRENT DATA STATE")
    print("=" * 50)
    
    print(f"Members: {len(treasurer_app.members)}")
    print(f"Pending Brothers: {len(treasurer_app.pending_brothers)}")
    print(f"Users: {len(treasurer_app.users)}")
    
    # Check file existence
    files_to_check = [
        ('Members file', treasurer_app.members_file),
        ('Members compressed', treasurer_app.members_file + '.gz'),
        ('Pending brothers file', treasurer_app.pending_brothers_file),
        ('Pending brothers compressed', treasurer_app.pending_brothers_file + '.gz'),
        ('Users file', treasurer_app.users_file),
    ]
    
    print("\n📁 File Status:")
    for name, path in files_to_check:
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        print(f"   {name}: {'✅ EXISTS' if exists else '❌ MISSING'} ({size} bytes)")

if __name__ == "__main__":
    print("🚀 Starting Brother Registration Test\n")
    
    # Check current data state
    check_current_data()
    
    # Test registration
    success = test_brother_registration()
    
    print(f"\n🎯 Test Result: {'✅ PASSED' if success else '❌ FAILED'}")
    
    # Final data check
    check_current_data()