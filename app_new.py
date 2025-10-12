"""
Multi-Role Fraternity Management System
Main Flask Application with Authentication Integration
"""
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import os

# Import our modules
from database import create_app as create_database_app
from models import db, User, Member, Transaction, Role, Semester
from auth import init_auth
from rbac import (
    permission_required, role_or_permission_required,
    has_permission, has_any_permission,
    get_manageable_budget_categories, get_viewable_budget_categories,
    get_primary_managed_category, rbac_context_processor
)

# Create Flask app
def create_app():
    """Create and configure Flask application"""
    app = create_database_app('development')
    
    # Initialize authentication
    init_auth(app)
    
    # Add RBAC context processor
    app.context_processor(rbac_context_processor)
    
    return app

app = create_app()

# Main blueprint for core functionality
from flask import Blueprint
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Redirect to appropriate dashboard based on authentication"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Role-based dashboard routing"""
    primary_role = current_user.get_primary_role()
    
    if not primary_role:
        flash('No role assigned. Please contact the treasurer.', 'warning')
        return redirect(url_for('auth.logout'))
    
    # Route to appropriate dashboard based on primary role
    if primary_role.name == 'treasurer':
        return redirect(url_for('main.treasurer_dashboard'))
    elif primary_role.name == 'president':
        return redirect(url_for('main.president_dashboard'))
    elif primary_role.name == 'vice_president':
        return redirect(url_for('main.vp_dashboard'))
    elif primary_role.name in ['social_chair', 'phi_ed_chair', 'recruitment_chair', 'brotherhood_chair']:
        return redirect(url_for('main.officer_dashboard'))
    else:  # brother or any other role
        return redirect(url_for('main.brother_dashboard'))

@main_bp.route('/dashboard/treasurer')
@permission_required('view_all_data')
def treasurer_dashboard():
    """Treasurer dashboard - full access to all features"""
    # Get summary data
    members = Member.query.all()
    recent_transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(5).all()
    pending_users = User.query.filter_by(status='pending').count()
    
    # Calculate totals
    total_members = len(members)
    total_dues_owed = sum(member.get_balance() for member in members if member.get_balance() > 0)
    total_collected = sum(member.get_total_paid() for member in members)
    
    return render_template('dashboards/treasurer.html',
                         total_members=total_members,
                         total_dues_owed=total_dues_owed,
                         total_collected=total_collected,
                         recent_transactions=recent_transactions,
                         pending_users=pending_users)

@main_bp.route('/dashboard/president')
@permission_required('view_all_data')
def president_dashboard():
    """President dashboard - read-only view of all data"""
    # Get overview data
    members = Member.query.all()
    recent_transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(10).all()
    
    # Calculate financial overview
    total_members = len(members)
    total_dues = sum(member.dues_amount for member in members)
    total_collected = sum(member.get_total_paid() for member in members)
    collection_rate = (total_collected / total_dues * 100) if total_dues > 0 else 0
    
    return render_template('dashboards/president.html',
                         total_members=total_members,
                         total_dues=total_dues,
                         total_collected=total_collected,
                         collection_rate=collection_rate,
                         recent_transactions=recent_transactions)

@main_bp.route('/dashboard/vp')
@permission_required('view_all_budgets')
def vp_dashboard():
    """Vice President dashboard - view budgets with limited edit access"""
    # Get budget categories VP can manage
    manageable_categories = ['Social', 'Phi ED', 'Recruitment', 'Brotherhood']
    
    # Get transactions for manageable categories
    recent_transactions = Transaction.query.filter(
        Transaction.category.in_(manageable_categories)
    ).order_by(Transaction.created_at.desc()).limit(10).all()
    
    # Calculate spending by category
    category_spending = {}
    for category in manageable_categories:
        spent = sum(t.amount for t in Transaction.query.filter_by(
            category=category, type='expense'
        ).all())
        category_spending[category] = spent
    
    return render_template('dashboards/vp.html',
                         category_spending=category_spending,
                         recent_transactions=recent_transactions,
                         manageable_categories=manageable_categories)

@main_bp.route('/dashboard/officer')
@permission_required('manage_own_budget')
def officer_dashboard():
    """Officer dashboard - manage specific budget category"""
    # Determine which category this officer manages
    user_roles = [role.name for role in current_user.roles]
    category_mapping = {
        'social_chair': 'Social',
        'phi_ed_chair': 'Phi ED',
        'recruitment_chair': 'Recruitment',
        'brotherhood_chair': 'Brotherhood'
    }
    
    managed_category = None
    for role, category in category_mapping.items():
        if role in user_roles:
            managed_category = category
            break
    
    if not managed_category:
        flash('No budget category assigned to your role.', 'error')
        return redirect(url_for('auth.logout'))
    
    # Get transactions for this category
    transactions = Transaction.query.filter_by(
        category=managed_category
    ).order_by(Transaction.created_at.desc()).limit(20).all()
    
    # Calculate budget info
    total_spent = sum(t.amount for t in transactions if t.type == 'expense')
    
    # Get pending reimbursement requests (TODO: implement)
    pending_requests = []
    
    return render_template('dashboards/officer.html',
                         managed_category=managed_category,
                         transactions=transactions,
                         total_spent=total_spent,
                         pending_requests=pending_requests)

@main_bp.route('/dashboard/brother')
@permission_required('view_own_dues')
def brother_dashboard():
    """Brother dashboard - personal dues and payment information"""
    # Get linked member record
    member = current_user.member_record
    
    if not member:
        # Show message that account needs to be linked
        return render_template('dashboards/brother_not_linked.html')
    
    # Get payment history
    payments = member.payments
    payment_schedule = member.get_custom_schedule()
    
    # Calculate balances
    total_paid = member.get_total_paid()
    balance_due = member.get_balance()
    
    # Get payment plan suggestions (TODO: implement)
    pending_suggestions = []
    
    return render_template('dashboards/brother.html',
                         member=member,
                         payments=payments,
                         payment_schedule=payment_schedule,
                         total_paid=total_paid,
                         balance_due=balance_due,
                         pending_suggestions=pending_suggestions)

@main_bp.route('/api/user-stats')
@login_required
def user_stats():
    """API endpoint for user statistics (for AJAX updates)"""
    stats = {
        'user_count': User.query.filter_by(status='active').count(),
        'pending_users': User.query.filter_by(status='pending').count(),
        'total_members': Member.query.count(),
    }
    
    # Add role-specific stats
    if has_permission('view_all_data'):
        stats.update({
            'total_dues': sum(member.dues_amount for member in Member.query.all()),
            'total_collected': sum(member.get_total_paid() for member in Member.query.all()),
            'recent_transactions': Transaction.query.count()
        })
    
    return jsonify(stats)

# Import and register blueprints
from reimbursement import reimbursement_bp
from spending_plans import spending_plans_bp
from payment_suggestions import payment_suggestions_bp
from reports import reports_bp
app.register_blueprint(main_bp)
app.register_blueprint(reimbursement_bp)
app.register_blueprint(spending_plans_bp)
app.register_blueprint(payment_suggestions_bp)
app.register_blueprint(reports_bp)

# Error handlers
@app.errorhandler(403)
def forbidden(error):
    """Handle permission denied errors"""
    return render_template('errors/403.html'), 403

@app.errorhandler(404)
def not_found(error):
    """Handle page not found errors"""
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    db.session.rollback()
    return render_template('errors/500.html'), 500

# Utility functions for templates
@app.context_processor
def utility_processor():
    """Add utility functions to template context"""
    return dict(
        has_permission=has_permission,
        current_user=current_user,
        datetime=datetime
    )

# Development server configuration
if __name__ == '__main__':
    with app.app_context():
        # Ensure database is initialized
        db.create_all()
        
        # Check if we have a treasurer user
        treasurer = User.query.join(User.roles).filter(Role.name == 'treasurer').first()
        if not treasurer:
            print("⚠️  No treasurer account found!")
            print("📞 Default login: +1234567890 / admin123")
            print("🔧 Or create a new treasurer with: python3 database.py create-treasurer")
        else:
            print(f"✅ Treasurer account: {treasurer.full_name} ({treasurer.phone})")
    
    # Run development server
    app.run(debug=True, host='0.0.0.0', port=8080)