"""
Enhanced Role-Based Access Control (RBAC) System
Comprehensive permission management for fraternity roles
"""
from functools import wraps
from flask import flash, redirect, url_for, request, abort
from flask_login import current_user
from models import User, Role, Member

# Define comprehensive permission structure
ROLE_PERMISSIONS = {
    'treasurer': {
        # Full admin permissions
        'view_all_data': True,
        'edit_all_data': True,
        'manage_users': True,
        'manage_roles': True,
        'approve_requests': True,
        'manage_budgets': True,
        'send_reminders': True,
        'view_financial_reports': True,
        'manage_semesters': True,
        'system_administration': True,
        
        # Budget category permissions
        'edit_executive_budget': True,
        'edit_social_budget': True,
        'edit_brotherhood_budget': True,
        'edit_philanthropy_budget': True,
        'edit_recruitment_budget': True,
        'edit_phi_ed_budget': True,
        'edit_housing_budget': True,
        'edit_bank_budget': True,
        
        # Transaction permissions
        'add_transactions': True,
        'edit_transactions': True,
        'delete_transactions': True,
        'view_all_transactions': True,
        
        # Member management
        'add_members': True,
        'edit_members': True,
        'delete_members': True,
        'view_all_members': True,
        'record_payments': True,
        
        # Reimbursement permissions
        'submit_reimbursement': True,
        'approve_reimbursements': True,
    },
    
    'president': {
        # Read-only access to all treasurer data
        'view_all_data': True,
        'view_financial_reports': True,
        'view_all_transactions': True,
        'view_all_members': True,
        'view_budgets': True,
        
        # Cannot edit anything
        'edit_all_data': False,
        'manage_users': False,
        'approve_requests': False,
        'manage_budgets': False,
    },
    
    'vice_president': {
        # View all budgets, edit specific categories
        'view_all_budgets': True,
        'view_financial_reports': True,
        'view_transactions_filtered': True,
        
        # Can edit specific budget categories
        'edit_social_budget': True,
        'edit_brotherhood_budget': True,
        'edit_recruitment_budget': True,
        'edit_phi_ed_budget': True,
        
        # Cannot edit executive, philanthropy, housing
        'edit_executive_budget': False,
        'edit_philanthropy_budget': False,
        'edit_housing_budget': False,
        'edit_bank_budget': False,
        
        # Limited transaction access
        'add_transactions_filtered': True,
        'view_filtered_transactions': True,
    },
    
    'social_chair': {
        # Social budget management
        'manage_own_budget': True,
        'view_social_budget': True,
        'edit_social_budget': True,
        'add_social_expenses': True,
        'view_social_transactions': True,
        
        # Request permissions
        'submit_reimbursement': True,
        'create_spending_plans': True,
        'edit_spending_plans': True,
        
        # Limited member access
        'view_member_list': True,
        'send_targeted_reminders': True,
        'send_reminders': True,
    },
    
    'phi_ed_chair': {
        # Phi Ed budget management  
        'manage_own_budget': True,
        'view_phi_ed_budget': True,
        'edit_phi_ed_budget': True,
        'add_phi_ed_expenses': True,
        'view_phi_ed_transactions': True,
        
        # Request permissions
        'submit_reimbursement': True,
        'create_spending_plans': True,
        'edit_spending_plans': True,
        
        # Limited member access
        'view_member_list': True,
        'send_targeted_reminders': True,
        'send_reminders': True,
    },
    
    'recruitment_chair': {
        # Recruitment budget management
        'manage_own_budget': True,
        'view_recruitment_budget': True,
        'edit_recruitment_budget': True,
        'add_recruitment_expenses': True,
        'view_recruitment_transactions': True,
        
        # Request permissions
        'submit_reimbursement': True,
        'create_spending_plans': True,
        'edit_spending_plans': True,
        
        # Limited member access
        'view_member_list': True,
        'send_targeted_reminders': True,
        'send_reminders': True,
    },
    
    'brotherhood_chair': {
        # Brotherhood budget management
        'manage_own_budget': True,
        'view_brotherhood_budget': True,
        'edit_brotherhood_budget': True,
        'add_brotherhood_expenses': True,
        'view_brotherhood_transactions': True,
        
        # Request permissions
        'submit_reimbursement': True,
        'create_spending_plans': True,
        'edit_spending_plans': True,
        
        # Limited member access
        'view_member_list': True,
        'send_targeted_reminders': True,
        'send_reminders': True,
    },
    
    'brother': {
        # Personal data access only
        'view_own_dues': True,
        'view_own_payments': True,
        'view_own_payment_schedule': True,
        'suggest_payment_plan': True,
        'view_own_requests': True,
        
        # Basic fraternity info
        'view_public_events': True,
        'view_contact_list': True,
        
        # Cannot access financial data
        'view_budgets': False,
        'view_transactions': False,
        'view_all_members': False,
    }
}

def get_user_permissions(user=None):
    """Get all permissions for a user based on their roles"""
    if not user:
        user = current_user
        
    if not user or not user.is_authenticated:
        return {}
    
    permissions = {}
    
    # Combine permissions from all user roles
    for role in user.roles:
        role_perms = ROLE_PERMISSIONS.get(role.name, {})
        for perm, value in role_perms.items():
            # If any role grants permission, user has it
            if value:
                permissions[perm] = True
            # Only set to False if not already True from another role
            elif perm not in permissions:
                permissions[perm] = False
    
    return permissions

def has_permission(permission_name, user=None):
    """Check if user has a specific permission"""
    if not user:
        user = current_user
        
    if not user or not user.is_authenticated:
        return False
    
    # Treasurer always has all permissions
    if user.has_role('treasurer'):
        return True
    
    user_permissions = get_user_permissions(user)
    return user_permissions.get(permission_name, False)

def has_any_permission(*permission_names, user=None):
    """Check if user has any of the specified permissions"""
    return any(has_permission(perm, user) for perm in permission_names)

def has_all_permissions(*permission_names, user=None):
    """Check if user has all of the specified permissions"""
    return all(has_permission(perm, user) for perm in permission_names)

def permission_required(*permissions):
    """Decorator to require specific permissions for route access"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            # Check if user has any of the required permissions
            if not has_any_permission(*permissions):
                flash('You do not have permission to access this page.', 'error')
                if request.is_json:
                    abort(403)
                return redirect(url_for('main.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def role_or_permission_required(roles=None, permissions=None):
    """Decorator requiring either specific roles OR specific permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            # Check roles if specified
            has_role = False
            if roles:
                user_roles = [role.name for role in current_user.roles]
                has_role = any(role in user_roles for role in roles)
            
            # Check permissions if specified
            has_perm = False
            if permissions:
                has_perm = has_any_permission(*permissions)
            
            # User needs either role OR permission
            if not (has_role or has_perm):
                flash('You do not have permission to access this page.', 'error')
                if request.is_json:
                    abort(403)
                return redirect(url_for('main.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_manageable_budget_categories(user=None):
    """Get list of budget categories user can manage"""
    if not user:
        user = current_user
    
    categories = []
    category_permissions = {
        'Executive(GHQ, IFC, Flights)': 'edit_executive_budget',
        'Social': 'edit_social_budget',
        'Brotherhood': 'edit_brotherhood_budget',
        'Philanthropy': 'edit_philanthropy_budget',
        'Recruitment': 'edit_recruitment_budget',
        'Phi ED': 'edit_phi_ed_budget',
        'Housing': 'edit_housing_budget',
        'Bank Maintenance': 'edit_bank_budget',
    }
    
    for category, permission in category_permissions.items():
        if has_permission(permission, user):
            categories.append(category)
    
    return categories

def get_viewable_budget_categories(user=None):
    """Get list of budget categories user can view"""
    if not user:
        user = current_user
    
    # If user can view all budgets, return all categories
    if has_permission('view_all_budgets', user) or has_permission('view_all_data', user):
        return [
            'Executive(GHQ, IFC, Flights)', 'Social', 'Brotherhood', 
            'Philanthropy', 'Recruitment', 'Phi ED', 'Housing', 'Bank Maintenance'
        ]
    
    # Otherwise, check specific category permissions
    categories = []
    category_permissions = {
        'Executive(GHQ, IFC, Flights)': 'view_executive_budget',
        'Social': 'view_social_budget',
        'Brotherhood': 'view_brotherhood_budget',
        'Philanthropy': 'view_philanthropy_budget',
        'Recruitment': 'view_recruitment_budget',
        'Phi ED': 'view_phi_ed_budget',
        'Housing': 'view_housing_budget',
        'Bank Maintenance': 'view_bank_budget',
    }
    
    for category, permission in category_permissions.items():
        if has_permission(permission, user):
            categories.append(category)
    
    return categories

def get_primary_managed_category(user=None):
    """Get the primary budget category managed by this user (for chairs)"""
    if not user:
        user = current_user
    
    user_roles = [role.name for role in user.roles]
    
    role_to_category = {
        'social_chair': 'Social',
        'phi_ed_chair': 'Phi ED',
        'recruitment_chair': 'Recruitment',
        'brotherhood_chair': 'Brotherhood'
    }
    
    for role, category in role_to_category.items():
        if role in user_roles:
            return category
    
    return None

def can_access_member_data(member, user=None):
    """Check if user can access specific member's data"""
    if not user:
        user = current_user
    
    # Treasurer and president can see all
    if has_permission('view_all_members', user):
        return True
    
    # Users can see their own data
    if user.member_record and user.member_record.id == member.id:
        return True
    
    # Officers can see member list for reminders
    if has_permission('view_member_list', user):
        return True
    
    return False

def filter_transactions_by_permissions(transactions, user=None):
    """Filter transactions based on user permissions"""
    if not user:
        user = current_user
    
    # If user can see all transactions, return all
    if has_permission('view_all_transactions', user):
        return transactions
    
    # Get categories user can view
    viewable_categories = get_viewable_budget_categories(user)
    
    # Filter transactions by viewable categories
    filtered = [t for t in transactions if t.category in viewable_categories]
    
    return filtered

def get_accessible_menu_items(user=None):
    """Get menu items accessible to user based on permissions"""
    if not user:
        user = current_user
    
    if not user.is_authenticated:
        return []
    
    menu_items = []
    
    # Dashboard (everyone gets this)
    menu_items.append({
        'name': 'Dashboard',
        'url': 'main.dashboard',
        'icon': 'speedometer2',
        'permission': None
    })
    
    # Financial Management
    if has_permission('view_all_data', user):
        menu_items.append({
            'name': 'Financial Overview',
            'url': 'main.financial_overview',
            'icon': 'graph-up',
            'permission': 'view_all_data'
        })
    
    # Budget Management
    if has_any_permission('view_all_budgets', 'edit_social_budget', 'edit_phi_ed_budget', 
                         'edit_recruitment_budget', 'edit_brotherhood_budget', user=user):
        menu_items.append({
            'name': 'Budget Management',
            'url': 'main.budget_management',
            'icon': 'wallet2',
            'permission': 'view_budgets'
        })
    
    # Member Management (treasurer only)
    if has_permission('manage_users', user):
        menu_items.append({
            'name': 'Member Management',
            'url': 'main.member_management',
            'icon': 'people',
            'permission': 'manage_users'
        })
    
    # User Administration (treasurer only)
    if has_permission('manage_users', user):
        menu_items.append({
            'name': 'User Management',
            'url': 'auth.admin_users',
            'icon': 'person-gear',
            'permission': 'manage_users'
        })
    
    # Reimbursement Requests
    if has_permission('request_reimbursement', user) or has_permission('approve_requests', user):
        menu_items.append({
            'name': 'Reimbursements',
            'url': 'main.reimbursements',
            'icon': 'receipt',
            'permission': 'request_reimbursement'
        })
    
    # Spending Plans
    if has_permission('create_spending_plans', user) or has_permission('view_all_data', user):
        menu_items.append({
            'name': 'Spending Plans',
            'url': 'main.spending_plans',
            'icon': 'calendar-check',
            'permission': 'create_spending_plans'
        })
    
    # Personal Dues (brothers)
    if has_permission('view_own_dues', user):
        menu_items.append({
            'name': 'My Dues',
            'url': 'main.my_dues',
            'icon': 'cash-coin',
            'permission': 'view_own_dues'
        })
    
    return menu_items

# Context processor to make RBAC functions available in templates
def rbac_context_processor():
    """Make RBAC functions available in templates"""
    return dict(
        has_permission=has_permission,
        has_any_permission=has_any_permission,
        has_all_permissions=has_all_permissions,
        get_user_permissions=get_user_permissions,
        get_manageable_budget_categories=get_manageable_budget_categories,
        get_viewable_budget_categories=get_viewable_budget_categories,
        get_primary_managed_category=get_primary_managed_category,
        can_access_member_data=can_access_member_data,
        get_accessible_menu_items=get_accessible_menu_items,
    )