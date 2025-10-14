#!/usr/bin/env python3
"""
Fix Marco Lambert's role assignment - he should NOT be treasurer
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app import treasurer_app

def fix_marco_role():
    """Fix Marco Lambert's incorrect role assignment"""
    print("🔧 FIXING MARCO LAMBERT ROLE ASSIGNMENT")
    print("=" * 50)
    
    # Find Marco Lambert in members
    marco_member = None
    marco_id = None
    
    for member_id, member in treasurer_app.members.items():
        member_name = member.name if hasattr(member, 'name') else member.get('name', '')
        if 'Marco Lambert' in member_name:
            marco_member = member
            marco_id = member_id
            break
    
    if not marco_member:
        print("❌ Marco Lambert not found in members")
        return
    
    current_role = marco_member.role if hasattr(marco_member, 'role') else marco_member.get('role', 'brother')
    print(f"📝 Found Marco Lambert: {marco_member.name if hasattr(marco_member, 'name') else marco_member.get('name')}")
    print(f"   Current role: {current_role}")
    
    # Change his role to 'brother' (default)
    if hasattr(marco_member, 'role'):
        marco_member.role = 'brother'
    else:
        marco_member['role'] = 'brother'
    
    print(f"✅ Changed Marco Lambert's role to: brother")
    
    # Save the changes
    try:
        treasurer_app.save_data(treasurer_app.members_file, treasurer_app.members)
        print("✅ Changes saved successfully")
        
        # Verify the change
        reloaded_members = treasurer_app.load_data(treasurer_app.members_file, {})
        if marco_id in reloaded_members:
            reloaded_member = reloaded_members[marco_id]
            new_role = reloaded_member.role if hasattr(reloaded_member, 'role') else reloaded_member.get('role', 'brother')
            print(f"✅ Verified: Marco Lambert's role is now: {new_role}")
        else:
            print("❌ Could not verify change - member not found after reload")
            
    except Exception as e:
        print(f"❌ Error saving changes: {e}")

if __name__ == "__main__":
    fix_marco_role()