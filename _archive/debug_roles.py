#!/usr/bin/env python3
"""
Debug script to check member roles and data structure
"""
import os
import json
import gzip

def load_data(file_path, default):
    """Load data from file with compression support"""
    # Try compressed version first
    compressed_path = file_path + '.gz'
    if os.path.exists(compressed_path):
        try:
            with gzip.open(compressed_path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✅ Loaded compressed file: {compressed_path}")
                return data
        except Exception as e:
            print(f"❌ Error loading compressed file: {e}")
    
    # Try regular file
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                print(f"✅ Loaded regular file: {file_path}")
                return data
        except Exception as e:
            print(f"❌ Error loading regular file: {e}")
    
    print(f"📝 Using default data for: {file_path}")
    return default

def main():
    """Check current member data and roles"""
    print("🔍 Debugging Member Roles and Data Structure\n")
    
    # Paths
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    members_file = os.path.join(data_dir, 'members.json')
    
    print(f"📁 Data directory: {data_dir}")
    print(f"📄 Members file: {members_file}")
    print()
    
    # Check if data directory exists
    if not os.path.exists(data_dir):
        print("❌ Data directory doesn't exist!")
        return
    
    # List files in data directory
    print("📋 Files in data directory:")
    for file in os.listdir(data_dir):
        file_path = os.path.join(data_dir, file)
        size = os.path.getsize(file_path)
        print(f"  - {file} ({size} bytes)")
    print()
    
    # Load members data
    members = load_data(members_file, {})
    
    print(f"👥 Total members loaded: {len(members)}")
    print()
    
    if not members:
        print("⚠️ No members found! Have you added any members to the system?")
        return
    
    # Show all members and their roles
    print("📊 Member Roles Summary:")
    print("=" * 60)
    
    role_counts = {}
    
    for member_id, member_data in members.items():
        # Handle both dict and object structures
        if isinstance(member_data, dict):
            name = member_data.get('name', 'Unknown')
            role = member_data.get('role', 'brother')
            contact = member_data.get('contact', 'No contact')
            user_id = member_data.get('user_id', None)
        else:
            # Dataclass or object with attributes
            name = getattr(member_data, 'name', 'Unknown')
            role = getattr(member_data, 'role', 'brother')
            contact = getattr(member_data, 'contact', 'No contact')
            user_id = getattr(member_data, 'user_id', None)
        
        # Count roles
        role_counts[role] = role_counts.get(role, 0) + 1
        
        # Show member details
        account_status = "✅ Has Account" if user_id else "❌ No Account"
        print(f"  {name:<25} | {role:<20} | {contact:<25} | {account_status}")
    
    print("=" * 60)
    print()
    
    # Show role summary
    print("🎭 Role Distribution:")
    for role, count in sorted(role_counts.items()):
        print(f"  {role.replace('_', ' ').title():<20}: {count} member(s)")
    print()
    
    # Check for executive positions
    print("👔 Executive Board Status:")
    executive_roles = ['treasurer', 'president', 'vice_president', 'social_chair', 'phi_ed_chair', 'brotherhood_chair', 'recruitment_chair']
    
    for exec_role in executive_roles:
        assigned_members = []
        for member_id, member_data in members.items():
            member_role = member_data.get('role') if isinstance(member_data, dict) else getattr(member_data, 'role', 'brother')
            if member_role == exec_role:
                member_name = member_data.get('name') if isinstance(member_data, dict) else getattr(member_data, 'name', 'Unknown')
                assigned_members.append(member_name)
        
        if assigned_members:
            print(f"  {exec_role.replace('_', ' ').title():<20}: {', '.join(assigned_members)}")
        else:
            print(f"  {exec_role.replace('_', ' ').title():<20}: VACANT")
    
    print()
    
    # Check data structure
    print("🔧 Data Structure Analysis:")
    if members:
        sample_member_id = next(iter(members.keys()))
        sample_member = members[sample_member_id]
        
        print(f"  Sample member ID: {sample_member_id}")
        print(f"  Sample member type: {type(sample_member)}")
        
        if isinstance(sample_member, dict):
            print(f"  Sample member keys: {list(sample_member.keys())}")
            print(f"  Sample member data:")
            for key, value in sample_member.items():
                print(f"    {key}: {value} ({type(value).__name__})")
        else:
            print(f"  Sample member attributes: {dir(sample_member)}")
    
    print("\n✅ Debug complete!")

if __name__ == '__main__':
    main()