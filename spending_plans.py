"""
Semester Spending Plans Management Module
Handles creation, submission, and approval of officer spending plans
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, SpendingPlan, BudgetLimit, Semester, User
from rbac import permission_required, has_permission
from notifications import NotificationEvents
from datetime import datetime, timedelta
import json

spending_plans_bp = Blueprint('spending_plans', __name__, url_prefix='/spending-plans')

@spending_plans_bp.route('/')
@login_required
def list_spending_plans():
    """List spending plans based on user permissions"""
    
    if has_permission('view_all_data'):
        # Treasurer/President can see all plans
        plans = SpendingPlan.query.order_by(SpendingPlan.updated_at.desc()).all()
        template = 'spending_plans/admin_list.html'
    elif has_permission('manage_own_budget'):
        # Officers can see their own plans
        user_roles = [role.name for role in current_user.roles]
        category_mapping = {
            'social_chair': 'Social',
            'phi_ed_chair': 'Phi ED',
            'recruitment_chair': 'Recruitment',
            'brotherhood_chair': 'Brotherhood'
        }
        
        user_categories = [category for role, category in category_mapping.items() if role in user_roles]
        plans = SpendingPlan.query.filter(
            SpendingPlan.category.in_(user_categories)
        ).order_by(SpendingPlan.updated_at.desc()).all()
        template = 'spending_plans/officer_list.html'
    else:
        # Brothers can view approved plans (read-only)
        plans = SpendingPlan.query.filter_by(
            treasurer_approved=True, is_active=True
        ).order_by(SpendingPlan.updated_at.desc()).all()
        template = 'spending_plans/member_list.html'
    
    return render_template(template, plans=plans)

@spending_plans_bp.route('/new', methods=['GET', 'POST'])
@login_required
@permission_required('manage_own_budget')
def create_spending_plan():
    """Create a new spending plan"""
    
    if request.method == 'GET':
        # Get user's managed category
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
            return redirect(url_for('spending_plans.list_spending_plans'))
        
        # Get current semester
        current_semester = Semester.query.filter_by(is_current=True).first()
        if not current_semester:
            flash('No active semester found. Please contact the treasurer.', 'error')
            return redirect(url_for('spending_plans.list_spending_plans'))
        
        # Get budget limit for this category
        budget_limit = BudgetLimit.query.filter_by(
            category=managed_category,
            semester_id=current_semester.id
        ).first()
        
        if not budget_limit:
            flash(f'No budget limit found for {managed_category}. Please contact the treasurer.', 'error')
            return redirect(url_for('spending_plans.list_spending_plans'))
        
        return render_template('spending_plans/create.html',
                             managed_category=managed_category,
                             current_semester=current_semester,
                             budget_limit=budget_limit)
    
    # Handle form submission
    try:
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        total_budget = request.form.get('total_budget', type=float)
        
        # Validate required fields
        if not all([title, category, description, total_budget]):
            flash('All fields are required.', 'error')
            return redirect(url_for('spending_plans.create_spending_plan'))
        
        if total_budget <= 0:
            flash('Total budget must be greater than zero.', 'error')
            return redirect(url_for('spending_plans.create_spending_plan'))
        
        # Validate user can manage this category
        user_roles = [role.name for role in current_user.roles]
        category_mapping = {
            'social_chair': 'Social',
            'phi_ed_chair': 'Phi ED',
            'recruitment_chair': 'Recruitment',
            'brotherhood_chair': 'Brotherhood'
        }
        
        allowed_categories = [cat for role, cat in category_mapping.items() if role in user_roles]
        if category not in allowed_categories:
            flash('You can only create spending plans for your assigned categories.', 'error')
            return redirect(url_for('spending_plans.create_spending_plan'))
        
        # Get current semester
        current_semester = Semester.query.filter_by(is_current=True).first()
        
        # Parse events data from form
        events_data = []
        event_count = int(request.form.get('event_count', 0))
        
        for i in range(event_count):
            event_name = request.form.get(f'event_name_{i}', '').strip()
            event_date = request.form.get(f'event_date_{i}')
            event_budget = request.form.get(f'event_budget_{i}', type=float)
            event_description = request.form.get(f'event_description_{i}', '').strip()
            
            if event_name and event_date and event_budget:
                events_data.append({
                    'name': event_name,
                    'date': event_date,
                    'budget': event_budget,
                    'description': event_description
                })
        
        # Validate total budget matches event sum
        events_total = sum(event['budget'] for event in events_data)
        if abs(total_budget - events_total) > 0.01:  # Allow for small rounding errors
            flash(f'Total budget (${total_budget:.2f}) must equal sum of event budgets (${events_total:.2f}).', 'error')
            return redirect(url_for('spending_plans.create_spending_plan'))
        
        # Create spending plan data
        plan_data = {
            'description': description,
            'total_budget': total_budget,
            'events': events_data,
            'submitted_date': datetime.utcnow().isoformat(),
            'version_notes': 'Initial submission'
        }
        
        # Check for existing active plan in this category/semester
        existing_plan = SpendingPlan.query.filter_by(
            category=category,
            semester_id=current_semester.id,
            is_active=True
        ).first()
        
        if existing_plan:
            # Create new version
            existing_plan.is_active = False
            new_version = existing_plan.version + 1
        else:
            new_version = 1
        
        # Create new spending plan
        spending_plan = SpendingPlan(
            created_by=current_user.id,
            category=category,
            semester_id=current_semester.id,
            title=title,
            version=new_version,
            is_active=True,
            treasurer_approved=False
        )
        spending_plan.set_plan_data(plan_data)
        
        db.session.add(spending_plan)
        db.session.commit()
        
        flash(f'Spending plan "{title}" submitted successfully for treasurer review!', 'success')
        return redirect(url_for('spending_plans.view_spending_plan', id=spending_plan.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating spending plan: {str(e)}', 'error')
        return redirect(url_for('spending_plans.create_spending_plan'))

@spending_plans_bp.route('/<int:id>')
@login_required
def view_spending_plan(id):
    """View a specific spending plan"""
    
    spending_plan = SpendingPlan.query.get_or_404(id)
    
    # Check if user can view this plan
    if not has_permission('view_all_data'):
        if has_permission('manage_own_budget'):
            # Officers can view their own category plans
            user_roles = [role.name for role in current_user.roles]
            category_mapping = {
                'social_chair': 'Social',
                'phi_ed_chair': 'Phi ED',
                'recruitment_chair': 'Recruitment',
                'brotherhood_chair': 'Brotherhood'
            }
            
            user_categories = [category for role, category in category_mapping.items() if role in user_roles]
            if spending_plan.category not in user_categories:
                flash('Access denied.', 'error')
                return redirect(url_for('spending_plans.list_spending_plans'))
        else:
            # Brothers can only view approved plans
            if not spending_plan.treasurer_approved:
                flash('Access denied.', 'error')
                return redirect(url_for('spending_plans.list_spending_plans'))
    
    # Get plan data
    plan_data = spending_plan.get_plan_data()
    
    # Get related budget limit
    budget_limit = BudgetLimit.query.filter_by(
        category=spending_plan.category,
        semester_id=spending_plan.semester_id
    ).first()
    
    return render_template('spending_plans/detail.html',
                         spending_plan=spending_plan,
                         plan_data=plan_data,
                         budget_limit=budget_limit)

@spending_plans_bp.route('/<int:id>/approve', methods=['POST'])
@login_required
@permission_required('manage_budgets')
def approve_spending_plan(id):
    """Approve a spending plan (treasurer only)"""
    
    spending_plan = SpendingPlan.query.get_or_404(id)
    
    if spending_plan.treasurer_approved:
        return jsonify({'success': False, 'message': 'Plan is already approved'}), 400
    
    try:
        # Get approval notes
        approval_notes = request.json.get('notes', '') if request.is_json else ''
        
        # Mark as approved
        spending_plan.treasurer_approved = True
        spending_plan.updated_at = datetime.utcnow()
        
        # Update plan data with approval info
        plan_data = spending_plan.get_plan_data()
        plan_data['approval_date'] = datetime.utcnow().isoformat()
        plan_data['approved_by'] = current_user.id
        plan_data['approval_notes'] = approval_notes
        spending_plan.set_plan_data(plan_data)
        
        # Update the budget limit if needed
        budget_limit = BudgetLimit.query.filter_by(
            category=spending_plan.category,
            semester_id=spending_plan.semester_id
        ).first()
        
        if budget_limit:
            plan_total = plan_data.get('total_budget', 0)
            if budget_limit.amount != plan_total:
                budget_limit.amount = plan_total
        
        db.session.commit()
        
        # Send approval notification
        try:
            NotificationEvents.on_spending_plan_approved(spending_plan)
        except Exception as e:
            # Don't fail the approval if notification fails
            print(f"Notification failed: {e}")
        
        return jsonify({
            'success': True, 
            'message': f'Spending plan "{spending_plan.title}" approved successfully!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error approving plan: {str(e)}'}), 500

@spending_plans_bp.route('/<int:id>/reject', methods=['POST'])
@login_required
@permission_required('manage_budgets')
def reject_spending_plan(id):
    """Reject a spending plan with feedback"""
    
    spending_plan = SpendingPlan.query.get_or_404(id)
    
    if spending_plan.treasurer_approved:
        return jsonify({'success': False, 'message': 'Cannot reject an approved plan'}), 400
    
    rejection_reason = request.json.get('reason', '').strip() if request.is_json else ''
    if not rejection_reason:
        return jsonify({'success': False, 'message': 'Rejection reason is required'}), 400
    
    try:
        # Update plan data with rejection info
        plan_data = spending_plan.get_plan_data()
        plan_data['rejection_date'] = datetime.utcnow().isoformat()
        plan_data['rejected_by'] = current_user.id
        plan_data['rejection_reason'] = rejection_reason
        plan_data['status'] = 'rejected'
        spending_plan.set_plan_data(plan_data)
        
        spending_plan.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Spending plan rejected. Officer can revise and resubmit.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error rejecting plan: {str(e)}'}), 500

@spending_plans_bp.route('/summary')
@login_required
@permission_required('view_all_data')
def spending_plans_summary():
    """Dashboard summary of spending plans"""
    
    # Get current semester
    current_semester = Semester.query.filter_by(is_current=True).first()
    
    if not current_semester:
        flash('No active semester found.', 'error')
        return redirect(url_for('spending_plans.list_spending_plans'))
    
    # Get counts by status
    total_plans = SpendingPlan.query.filter_by(
        semester_id=current_semester.id, is_active=True
    ).count()
    
    approved_plans = SpendingPlan.query.filter_by(
        semester_id=current_semester.id,
        is_active=True,
        treasurer_approved=True
    ).count()
    
    pending_plans = total_plans - approved_plans
    
    # Get total budgets
    approved_amount = 0
    pending_amount = 0
    
    for plan in SpendingPlan.query.filter_by(semester_id=current_semester.id, is_active=True).all():
        plan_data = plan.get_plan_data()
        amount = plan_data.get('total_budget', 0)
        if plan.treasurer_approved:
            approved_amount += amount
        else:
            pending_amount += amount
    
    # Get plans by category
    categories = ['Social', 'Phi ED', 'Recruitment', 'Brotherhood']
    category_data = {}
    
    for category in categories:
        plan = SpendingPlan.query.filter_by(
            category=category,
            semester_id=current_semester.id,
            is_active=True
        ).first()
        
        if plan:
            plan_data = plan.get_plan_data()
            category_data[category] = {
                'plan': plan,
                'budget': plan_data.get('total_budget', 0),
                'events_count': len(plan_data.get('events', []))
            }
    
    # Recent activity
    recent_plans = SpendingPlan.query.filter_by(
        semester_id=current_semester.id
    ).order_by(SpendingPlan.updated_at.desc()).limit(5).all()
    
    return render_template('spending_plans/summary.html',
                         current_semester=current_semester,
                         total_plans=total_plans,
                         approved_plans=approved_plans,
                         pending_plans=pending_plans,
                         approved_amount=approved_amount,
                         pending_amount=pending_amount,
                         category_data=category_data,
                         recent_plans=recent_plans)

@spending_plans_bp.route('/api/template/<category>')
@login_required
@permission_required('manage_own_budget')
def get_category_template(category):
    """Get spending plan template for a category"""
    
    # Validate user can access this category
    user_roles = [role.name for role in current_user.roles]
    category_mapping = {
        'social_chair': 'Social',
        'phi_ed_chair': 'Phi ED',
        'recruitment_chair': 'Recruitment',
        'brotherhood_chair': 'Brotherhood'
    }
    
    allowed_categories = [cat for role, cat in category_mapping.items() if role in user_roles]
    if category not in allowed_categories:
        return jsonify({'error': 'Access denied'}), 403
    
    # Return template based on category
    templates = {
        'Social': {
            'suggested_events': [
                {'name': 'Welcome Back Social', 'typical_budget': 300, 'description': 'Start of semester mixer'},
                {'name': 'Date Dash', 'typical_budget': 200, 'description': 'Speed dating event'},
                {'name': 'Semi-Formal', 'typical_budget': 800, 'description': 'Semi-formal dance'},
                {'name': 'Homecoming Activities', 'typical_budget': 400, 'description': 'Homecoming week events'},
                {'name': 'End of Semester Social', 'typical_budget': 300, 'description': 'Closing semester party'}
            ]
        },
        'Phi ED': {
            'suggested_events': [
                {'name': 'Study Skills Workshop', 'typical_budget': 150, 'description': 'Academic improvement session'},
                {'name': 'Professional Development', 'typical_budget': 300, 'description': 'Career and networking skills'},
                {'name': 'Leadership Training', 'typical_budget': 400, 'description': 'Leadership development program'},
                {'name': 'Academic Awards Ceremony', 'typical_budget': 250, 'description': 'Recognizing academic achievement'},
                {'name': 'Graduate School Prep', 'typical_budget': 200, 'description': 'Preparation for graduate studies'}
            ]
        },
        'Recruitment': {
            'suggested_events': [
                {'name': 'Rush Week Activities', 'typical_budget': 600, 'description': 'Main recruitment events'},
                {'name': 'Information Sessions', 'typical_budget': 200, 'description': 'Informational meetings'},
                {'name': 'Recruitment Materials', 'typical_budget': 150, 'description': 'Flyers, brochures, swag'},
                {'name': 'Bid Day Celebration', 'typical_budget': 300, 'description': 'New member celebration'},
                {'name': 'Prospect Events', 'typical_budget': 250, 'description': 'Prospective member activities'}
            ]
        },
        'Brotherhood': {
            'suggested_events': [
                {'name': 'Brotherhood Retreat', 'typical_budget': 500, 'description': 'Weekend bonding retreat'},
                {'name': 'Member Appreciation', 'typical_budget': 300, 'description': 'Recognition events'},
                {'name': 'Alumni Relations', 'typical_budget': 200, 'description': 'Alumni engagement events'},
                {'name': 'Community Service', 'typical_budget': 150, 'description': 'Service projects'},
                {'name': 'Internal Activities', 'typical_budget': 350, 'description': 'Member bonding events'}
            ]
        }
    }
    
    return jsonify(templates.get(category, {'suggested_events': []}))