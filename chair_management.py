"""
Chair Management Blueprint - Event Planning and Budget Management for Chairs
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from models import db, Event, SpendingPlan, Semester, BudgetLimit
from rbac import permission_required, has_permission, get_primary_managed_category
import json

# Create blueprint
chair_bp = Blueprint('chair', __name__, url_prefix='/chair')

@chair_bp.route('/dashboard')
@login_required
@permission_required('create_events', 'create_spending_plans')
def chair_dashboard():
    """Main dashboard for chairs to manage their category"""
    primary_category = get_primary_managed_category(current_user)
    
    if not primary_category:
        flash('You are not assigned to manage any budget category.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get current semester
    current_semester = Semester.query.filter_by(is_current=True).first()
    if not current_semester:
        flash('No active semester found.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get chair's events for current semester
    events = Event.query.filter_by(
        created_by=current_user.id,
        category=primary_category,
        semester_id=current_semester.id
    ).order_by(Event.date.asc()).all()
    
    # Get chair's spending plans
    spending_plans = SpendingPlan.query.filter_by(
        created_by=current_user.id,
        category=primary_category,
        semester_id=current_semester.id
    ).order_by(SpendingPlan.created_at.desc()).all()
    
    # Get budget limit for this category
    budget_limit = BudgetLimit.query.filter_by(
        category=primary_category,
        semester_id=current_semester.id
    ).first()
    
    # Calculate spending so far
    total_estimated_cost = sum(event.estimated_cost or 0 for event in events)
    total_actual_cost = sum(event.actual_cost or 0 for event in events if event.actual_cost)
    
    return render_template('chair/dashboard.html',
                         primary_category=primary_category,
                         current_semester=current_semester,
                         events=events,
                         spending_plans=spending_plans,
                         budget_limit=budget_limit,
                         total_estimated_cost=total_estimated_cost,
                         total_actual_cost=total_actual_cost)

@chair_bp.route('/events')
@login_required
@permission_required('view_own_events')
def events_list():
    """List all events created by this chair"""
    primary_category = get_primary_managed_category(current_user)
    current_semester = Semester.query.filter_by(is_current=True).first()
    
    events = Event.query.filter_by(
        created_by=current_user.id,
        category=primary_category,
        semester_id=current_semester.id
    ).order_by(Event.date.asc()).all()
    
    return render_template('chair/events.html',
                         events=events,
                         primary_category=primary_category,
                         current_semester=current_semester)

@chair_bp.route('/events/create', methods=['GET', 'POST'])
@login_required
@permission_required('create_events')
def create_event():
    """Create a new event"""
    primary_category = get_primary_managed_category(current_user)
    current_semester = Semester.query.filter_by(is_current=True).first()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        date_str = request.form.get('date', '')
        location = request.form.get('location', '').strip()
        estimated_cost = float(request.form.get('estimated_cost', 0))
        max_attendees = request.form.get('max_attendees')
        notes = request.form.get('notes', '').strip()
        
        if not title:
            flash('Event title is required.', 'error')
            return render_template('chair/create_event.html', 
                                 primary_category=primary_category)
        
        # Parse date
        event_date = None
        if date_str:
            try:
                event_date = datetime.fromisoformat(date_str)
            except ValueError:
                flash('Invalid date format.', 'error')
                return render_template('chair/create_event.html', 
                                     primary_category=primary_category)
        
        # Create event
        event = Event(
            created_by=current_user.id,
            category=primary_category,
            semester_id=current_semester.id,
            title=title,
            description=description,
            date=event_date,
            location=location,
            estimated_cost=estimated_cost,
            max_attendees=int(max_attendees) if max_attendees else None,
            notes=notes
        )
        
        try:
            db.session.add(event)
            db.session.commit()
            flash(f'Event "{title}" created successfully!', 'success')
            return redirect(url_for('chair.events_list'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating event. Please try again.', 'error')
    
    return render_template('chair/create_event.html',
                         primary_category=primary_category,
                         current_semester=current_semester)

@chair_bp.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('edit_own_events')
def edit_event(event_id):
    """Edit an existing event"""
    event = Event.query.get_or_404(event_id)
    
    # Check if user can edit this event
    if event.created_by != current_user.id:
        flash('You can only edit your own events.', 'error')
        return redirect(url_for('chair.events_list'))
    
    if request.method == 'POST':
        event.title = request.form.get('title', '').strip()
        event.description = request.form.get('description', '').strip()
        date_str = request.form.get('date', '')
        event.location = request.form.get('location', '').strip()
        event.estimated_cost = float(request.form.get('estimated_cost', 0))
        max_attendees = request.form.get('max_attendees')
        event.max_attendees = int(max_attendees) if max_attendees else None
        event.notes = request.form.get('notes', '').strip()
        event.status = request.form.get('status', 'planned')
        
        # Handle actual cost for completed events
        if event.status == 'completed':
            actual_cost = request.form.get('actual_cost')
            event.actual_cost = float(actual_cost) if actual_cost else None
        
        # Parse date
        if date_str:
            try:
                event.date = datetime.fromisoformat(date_str)
            except ValueError:
                flash('Invalid date format.', 'error')
                return render_template('chair/edit_event.html', event=event)
        
        try:
            db.session.commit()
            flash(f'Event "{event.title}" updated successfully!', 'success')
            return redirect(url_for('chair.events_list'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating event. Please try again.', 'error')
    
    return render_template('chair/edit_event.html', event=event)

@chair_bp.route('/spending-plans')
@login_required
@permission_required('view_own_spending_plans')
def spending_plans_list():
    """List all spending plans created by this chair"""
    primary_category = get_primary_managed_category(current_user)
    current_semester = Semester.query.filter_by(is_current=True).first()
    
    spending_plans = SpendingPlan.query.filter_by(
        created_by=current_user.id,
        category=primary_category,
        semester_id=current_semester.id
    ).order_by(SpendingPlan.created_at.desc()).all()
    
    return render_template('chair/spending_plans.html',
                         spending_plans=spending_plans,
                         primary_category=primary_category,
                         current_semester=current_semester)

@chair_bp.route('/spending-plans/create', methods=['GET', 'POST'])
@login_required
@permission_required('create_spending_plans')
def create_spending_plan():
    """Create a new spending plan"""
    primary_category = get_primary_managed_category(current_user)
    current_semester = Semester.query.filter_by(is_current=True).first()
    
    # Get budget limit
    budget_limit = BudgetLimit.query.filter_by(
        category=primary_category,
        semester_id=current_semester.id
    ).first()
    
    # Get chair's events for selection
    events = Event.query.filter_by(
        created_by=current_user.id,
        category=primary_category,
        semester_id=current_semester.id
    ).all()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        total_budget = float(request.form.get('total_budget', 0))
        
        # Get selected events and their allocations
        plan_items = []
        selected_event_ids = request.form.getlist('events')
        
        for event_id in selected_event_ids:
            event = Event.query.get(int(event_id))
            if event and event.created_by == current_user.id:
                allocated_amount = float(request.form.get(f'amount_{event_id}', 0))
                plan_items.append({
                    'event_id': int(event_id),
                    'event_title': event.title,
                    'allocated_amount': allocated_amount,
                    'event_date': event.date.isoformat() if event.date else None
                })
        
        # Add custom line items
        custom_items = []
        for i in range(5):  # Allow up to 5 custom items
            custom_title = request.form.get(f'custom_title_{i}', '').strip()
            if custom_title:
                custom_amount = float(request.form.get(f'custom_amount_{i}', 0))
                custom_date = request.form.get(f'custom_date_{i}', '')
                custom_items.append({
                    'title': custom_title,
                    'amount': custom_amount,
                    'date': custom_date
                })
        
        plan_data = {
            'events': plan_items,
            'custom_items': custom_items,
            'notes': request.form.get('plan_notes', '').strip()
        }
        
        if not title:
            flash('Spending plan title is required.', 'error')
            return render_template('chair/create_spending_plan.html',
                                 primary_category=primary_category,
                                 budget_limit=budget_limit,
                                 events=events)
        
        # Create spending plan
        spending_plan = SpendingPlan(
            created_by=current_user.id,
            category=primary_category,
            semester_id=current_semester.id,
            title=title,
            total_budget=total_budget
        )
        spending_plan.set_plan_data(plan_data)
        
        try:
            db.session.add(spending_plan)
            db.session.commit()
            flash(f'Spending plan "{title}" created successfully!', 'success')
            return redirect(url_for('chair.spending_plans_list'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating spending plan. Please try again.', 'error')
    
    return render_template('chair/create_spending_plan.html',
                         primary_category=primary_category,
                         current_semester=current_semester,
                         budget_limit=budget_limit,
                         events=events)

@chair_bp.route('/spending-plans/<int:plan_id>/view')
@login_required
@permission_required('view_own_spending_plans')
def view_spending_plan(plan_id):
    """View a spending plan in detail"""
    spending_plan = SpendingPlan.query.get_or_404(plan_id)
    
    # Check if user can view this plan
    if spending_plan.created_by != current_user.id and not has_permission('view_chair_spending_plans'):
        flash('You can only view your own spending plans.', 'error')
        return redirect(url_for('chair.spending_plans_list'))
    
    plan_data = spending_plan.get_plan_data()
    
    return render_template('chair/view_spending_plan.html',
                         spending_plan=spending_plan,
                         plan_data=plan_data)

# API endpoints for chair management
@chair_bp.route('/api/events/<int:event_id>/status', methods=['POST'])
@login_required
@permission_required('edit_own_events')
def update_event_status(event_id):
    """API endpoint to update event status"""
    event = Event.query.get_or_404(event_id)
    
    if event.created_by != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.get_json()
    status = data.get('status')
    
    if status not in ['planned', 'approved', 'cancelled', 'completed']:
        return jsonify({'error': 'Invalid status'}), 400
    
    event.status = status
    
    # If marking as completed, allow setting actual cost
    if status == 'completed' and 'actual_cost' in data:
        event.actual_cost = float(data['actual_cost'])
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Event status updated'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Database error'}), 500

@chair_bp.route('/api/budget-remaining')
@login_required
@permission_required('view_own_spending_plans')
def get_budget_remaining():
    """API endpoint to get remaining budget for chair's category"""
    primary_category = get_primary_managed_category(current_user)
    current_semester = Semester.query.filter_by(is_current=True).first()
    
    if not primary_category or not current_semester:
        return jsonify({'error': 'Category or semester not found'}), 404
    
    # Get budget limit
    budget_limit = BudgetLimit.query.filter_by(
        category=primary_category,
        semester_id=current_semester.id
    ).first()
    
    # Get total spending so far
    events = Event.query.filter_by(
        created_by=current_user.id,
        category=primary_category,
        semester_id=current_semester.id
    ).all()
    
    total_estimated = sum(event.estimated_cost or 0 for event in events)
    total_actual = sum(event.actual_cost or 0 for event in events if event.actual_cost)
    
    budget_amount = budget_limit.amount if budget_limit else 0
    remaining = budget_amount - total_actual
    
    return jsonify({
        'budget_limit': budget_amount,
        'total_estimated': total_estimated,
        'total_actual': total_actual,
        'remaining': remaining,
        'category': primary_category
    })