"""
Executive Views Blueprint - For President, VP, and Treasurer to view chair spending plans
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Event, SpendingPlan, Semester, BudgetLimit, User
from rbac import permission_required, has_permission
from sqlalchemy import func

# Create blueprint
exec_bp = Blueprint('executive', __name__, url_prefix='/executive')

@exec_bp.route('/chair-spending-overview')
@login_required
@permission_required('view_chair_spending_plans')
def chair_spending_overview():
    """Overview of all chair spending plans and budgets"""
    current_semester = Semester.query.filter_by(is_current=True).first()
    
    if not current_semester:
        flash('No active semester found.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get all budget categories and their limits
    budget_limits = BudgetLimit.query.filter_by(semester_id=current_semester.id).all()
    
    # Get spending data by category
    spending_overview = []
    
    categories = ['Social', 'Brotherhood', 'Recruitment', 'Phi ED']
    
    for category in categories:
        # Get budget limit
        budget_limit = next((bl for bl in budget_limits if bl.category == category), None)
        budget_amount = budget_limit.amount if budget_limit else 0
        
        # Get all events in this category
        events = Event.query.filter_by(
            category=category,
            semester_id=current_semester.id
        ).all()
        
        # Get spending plans in this category
        spending_plans = SpendingPlan.query.filter_by(
            category=category,
            semester_id=current_semester.id,
            is_active=True
        ).all()
        
        # Calculate totals
        total_estimated = sum(event.estimated_cost or 0 for event in events)
        total_actual = sum(event.actual_cost or 0 for event in events if event.actual_cost)
        
        # Get chair info
        chair_role_name = f"{category.lower().replace(' ', '_')}_chair"
        chair_user = User.query.join(User.roles).filter_by(name=chair_role_name).first()
        
        spending_overview.append({
            'category': category,
            'budget_amount': budget_amount,
            'total_estimated': total_estimated,
            'total_actual': total_actual,
            'remaining_budget': budget_amount - total_actual,
            'events_count': len(events),
            'spending_plans_count': len(spending_plans),
            'chair_name': chair_user.full_name if chair_user else 'Unassigned',
            'chair_user': chair_user,
            'events': events[:3],  # Show first 3 events
            'latest_spending_plan': spending_plans[0] if spending_plans else None
        })
    
    return render_template('executive/chair_spending_overview.html',
                         spending_overview=spending_overview,
                         current_semester=current_semester)

@exec_bp.route('/chair-spending/<category>')
@login_required
@permission_required('view_chair_spending_plans')
def category_detail(category):
    """Detailed view of a specific category's spending"""
    current_semester = Semester.query.filter_by(is_current=True).first()
    
    # Get all events for this category
    events = Event.query.filter_by(
        category=category,
        semester_id=current_semester.id
    ).order_by(Event.date.asc()).all()
    
    # Get all spending plans for this category
    spending_plans = SpendingPlan.query.filter_by(
        category=category,
        semester_id=current_semester.id
    ).order_by(SpendingPlan.created_at.desc()).all()
    
    # Get budget limit
    budget_limit = BudgetLimit.query.filter_by(
        category=category,
        semester_id=current_semester.id
    ).first()
    
    # Get chair info
    chair_role_name = f"{category.lower().replace(' ', '_')}_chair"
    chair_user = User.query.join(User.roles).filter_by(name=chair_role_name).first()
    
    return render_template('executive/category_detail.html',
                         category=category,
                         events=events,
                         spending_plans=spending_plans,
                         budget_limit=budget_limit,
                         chair_user=chair_user,
                         current_semester=current_semester)

@exec_bp.route('/spending-plan/<int:plan_id>')
@login_required
@permission_required('view_chair_spending_plans')
def view_spending_plan(plan_id):
    """View a specific spending plan"""
    spending_plan = SpendingPlan.query.get_or_404(plan_id)
    plan_data = spending_plan.get_plan_data()
    
    # Get related events
    event_ids = [item['event_id'] for item in plan_data.get('events', [])]
    related_events = Event.query.filter(Event.id.in_(event_ids)).all() if event_ids else []
    
    return render_template('executive/spending_plan_detail.html',
                         spending_plan=spending_plan,
                         plan_data=plan_data,
                         related_events=related_events)

@exec_bp.route('/member-list')
@login_required
@permission_required('view_member_list', 'view_member_roles', 'view_member_contacts')
def member_list():
    """Member list for VP - shows contacts/roles but not financial info"""
    from models import Member
    
    current_semester = Semester.query.filter_by(is_current=True).first()
    
    if not current_semester:
        flash('No active semester found.', 'error')
        return redirect(url_for('main.dashboard'))
    
    members = Member.query.filter_by(semester_id=current_semester.id).all()
    
    # Check if user can view financial info
    can_view_finances = has_permission('view_member_finances')
    
    return render_template('executive/member_list.html',
                         members=members,
                         can_view_finances=can_view_finances,
                         current_semester=current_semester)

@exec_bp.route('/budget-summary')
@login_required
@permission_required('view_all_budgets')
def budget_summary():
    """Budget summary for executives"""
    current_semester = Semester.query.filter_by(is_current=True).first()
    
    # Get all budget limits
    budget_limits = BudgetLimit.query.filter_by(semester_id=current_semester.id).all()
    
    # Calculate spending by category
    budget_summary = []
    
    for budget_limit in budget_limits:
        # Get events in this category
        events = Event.query.filter_by(
            category=budget_limit.category,
            semester_id=current_semester.id
        ).all()
        
        total_estimated = sum(event.estimated_cost or 0 for event in events)
        total_actual = sum(event.actual_cost or 0 for event in events if event.actual_cost)
        
        budget_summary.append({
            'category': budget_limit.category,
            'budget_limit': budget_limit.amount,
            'estimated_spending': total_estimated,
            'actual_spending': total_actual,
            'remaining': budget_limit.amount - total_actual,
            'percent_used': (total_actual / budget_limit.amount * 100) if budget_limit.amount > 0 else 0
        })
    
    return render_template('executive/budget_summary.html',
                         budget_summary=budget_summary,
                         current_semester=current_semester)

# API endpoints for executive views
@exec_bp.route('/api/spending-plan/<int:plan_id>/approve', methods=['POST'])
@login_required
@permission_required('approve_requests')
def approve_spending_plan(plan_id):
    """Approve a spending plan (President/VP/Treasurer only)"""
    spending_plan = SpendingPlan.query.get_or_404(plan_id)
    
    approval_type = request.json.get('approval_type')  # 'president', 'vp', or 'treasurer'
    
    if approval_type == 'president' and has_permission('view_all_data'):
        spending_plan.president_approved = True
    elif approval_type == 'vp' and current_user.has_role('vice_president'):
        spending_plan.vp_approved = True
    elif approval_type == 'treasurer' and (current_user.has_role('treasurer') or current_user.has_role('admin')):
        spending_plan.treasurer_approved = True
    else:
        return jsonify({'error': 'Permission denied'}), 403
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Spending plan approved'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Database error'}), 500

@exec_bp.route('/api/category-stats/<category>')
@login_required
@permission_required('view_chair_spending_plans')
def get_category_stats(category):
    """Get spending statistics for a category"""
    current_semester = Semester.query.filter_by(is_current=True).first()
    
    # Get budget limit
    budget_limit = BudgetLimit.query.filter_by(
        category=category,
        semester_id=current_semester.id
    ).first()
    
    # Get events
    events = Event.query.filter_by(
        category=category,
        semester_id=current_semester.id
    ).all()
    
    # Calculate stats
    total_events = len(events)
    completed_events = len([e for e in events if e.status == 'completed'])
    total_estimated = sum(event.estimated_cost or 0 for event in events)
    total_actual = sum(event.actual_cost or 0 for event in events if event.actual_cost)
    
    budget_amount = budget_limit.amount if budget_limit else 0
    remaining = budget_amount - total_actual
    
    return jsonify({
        'category': category,
        'budget_limit': budget_amount,
        'total_estimated': total_estimated,
        'total_actual': total_actual,
        'remaining': remaining,
        'total_events': total_events,
        'completed_events': completed_events,
        'percent_budget_used': (total_actual / budget_amount * 100) if budget_amount > 0 else 0
    })
