"""
Payment Plan Suggestions Management Module
Allows brothers to suggest modifications to their payment plans
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, PaymentPlanSuggestion, Member, Payment
from rbac import permission_required, has_permission
from datetime import datetime
import json

payment_suggestions_bp = Blueprint('payment_suggestions', __name__, url_prefix='/payment-suggestions')

@payment_suggestions_bp.route('/')
@login_required
def list_suggestions():
    """List payment plan suggestions based on user permissions"""
    
    if has_permission('view_all_data'):
        # Treasurer can see all suggestions
        suggestions = PaymentPlanSuggestion.query.order_by(
            PaymentPlanSuggestion.created_at.desc()
        ).all()
        template = 'payment_suggestions/admin_list.html'
    else:
        # Brothers can only see their own suggestions
        if not current_user.member_record:
            flash('Your account is not linked to a member record. Please contact the treasurer.', 'warning')
            return redirect(url_for('main.brother_dashboard'))
        
        suggestions = PaymentPlanSuggestion.query.filter_by(
            member=current_user.member_record
        ).order_by(PaymentPlanSuggestion.created_at.desc()).all()
        template = 'payment_suggestions/member_list.html'
    
    return render_template(template, suggestions=suggestions)

@payment_suggestions_bp.route('/new', methods=['GET', 'POST'])
@login_required
@permission_required('suggest_payment_plan')
def create_suggestion():
    """Create a new payment plan suggestion"""
    
    if not current_user.member_record:
        flash('Your account is not linked to a member record. Please contact the treasurer.', 'error')
        return redirect(url_for('main.brother_dashboard'))
    
    member = current_user.member_record
    
    if request.method == 'GET':
        # Get current payment plan
        current_plan = {
            'payment_plan': member.payment_plan,
            'dues_amount': member.dues_amount,
            'custom_schedule': member.get_custom_schedule() if member.payment_plan == 'custom' else None
        }
        
        # Calculate current balance and payments made
        total_paid = member.get_total_paid()
        balance_due = member.get_balance()
        
        return render_template('payment_suggestions/create.html',
                             member=member,
                             current_plan=current_plan,
                             total_paid=total_paid,
                             balance_due=balance_due)
    
    # Handle form submission
    try:
        suggestion_type = request.form.get('suggestion_type', '').strip()
        reasoning = request.form.get('reasoning', '').strip()
        
        if not all([suggestion_type, reasoning]):
            flash('Please provide a suggestion type and reasoning.', 'error')
            return redirect(url_for('payment_suggestions.create_suggestion'))
        
        # Get original plan
        original_plan = {
            'payment_plan': member.payment_plan,
            'dues_amount': member.dues_amount,
            'custom_schedule': member.get_custom_schedule() if member.payment_plan == 'custom' else None
        }
        
        # Parse suggested plan based on type
        suggested_plan = {}
        
        if suggestion_type == 'change_plan_type':
            new_plan_type = request.form.get('new_plan_type', '').strip()
            if not new_plan_type:
                flash('Please select a new payment plan type.', 'error')
                return redirect(url_for('payment_suggestions.create_suggestion'))
            
            suggested_plan = {
                'payment_plan': new_plan_type,
                'dues_amount': member.dues_amount,
                'custom_schedule': None
            }
        
        elif suggestion_type == 'custom_schedule':
            # Parse custom payment schedule
            payment_count = int(request.form.get('payment_count', 0))
            custom_payments = []
            total_suggested = 0
            
            for i in range(payment_count):
                payment_date = request.form.get(f'payment_date_{i}')
                payment_amount = request.form.get(f'payment_amount_{i}', type=float)
                payment_description = request.form.get(f'payment_description_{i}', '').strip()
                
                if payment_date and payment_amount and payment_amount > 0:
                    custom_payments.append({
                        'date': payment_date,
                        'amount': payment_amount,
                        'description': payment_description or f'Payment {i+1}'
                    })
                    total_suggested += payment_amount
            
            # Validate total matches dues amount
            remaining_balance = member.get_balance()
            if abs(total_suggested - remaining_balance) > 0.01:
                flash(f'Custom payment total (${total_suggested:.2f}) must equal remaining balance (${remaining_balance:.2f}).', 'error')
                return redirect(url_for('payment_suggestions.create_suggestion'))
            
            suggested_plan = {
                'payment_plan': 'custom',
                'dues_amount': member.dues_amount,
                'custom_schedule': custom_payments
            }
        
        elif suggestion_type == 'extension_request':
            extension_months = int(request.form.get('extension_months', 0))
            if extension_months <= 0 or extension_months > 12:
                flash('Extension must be between 1 and 12 months.', 'error')
                return redirect(url_for('payment_suggestions.create_suggestion'))
            
            # Create extended monthly plan
            remaining_balance = member.get_balance()
            monthly_amount = remaining_balance / extension_months
            
            extended_payments = []
            for i in range(extension_months):
                # Start from next month
                payment_date = datetime.now().replace(day=15)
                if i > 0:
                    if payment_date.month + i > 12:
                        payment_date = payment_date.replace(
                            year=payment_date.year + 1,
                            month=(payment_date.month + i) % 12 or 12
                        )
                    else:
                        payment_date = payment_date.replace(month=payment_date.month + i)
                
                extended_payments.append({
                    'date': payment_date.strftime('%Y-%m-%d'),
                    'amount': monthly_amount,
                    'description': f'Extended payment {i+1} of {extension_months}'
                })
            
            suggested_plan = {
                'payment_plan': 'custom',
                'dues_amount': member.dues_amount,
                'custom_schedule': extended_payments
            }
        
        else:
            flash('Invalid suggestion type.', 'error')
            return redirect(url_for('payment_suggestions.create_suggestion'))
        
        # Create suggestion
        suggestion = PaymentPlanSuggestion(
            member=member,
            suggested_by=current_user.id,
            status='pending',
            notes=reasoning
        )
        
        suggestion.set_original_plan(original_plan)
        suggestion.set_suggested_plan(suggested_plan)
        
        db.session.add(suggestion)
        db.session.commit()
        
        flash('Payment plan suggestion submitted successfully! The treasurer will review it shortly.', 'success')
        return redirect(url_for('payment_suggestions.view_suggestion', id=suggestion.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating suggestion: {str(e)}', 'error')
        return redirect(url_for('payment_suggestions.create_suggestion'))

@payment_suggestions_bp.route('/<int:id>')
@login_required
def view_suggestion(id):
    """View a specific payment plan suggestion"""
    
    suggestion = PaymentPlanSuggestion.query.get_or_404(id)
    
    # Check if user can view this suggestion
    if not has_permission('view_all_data'):
        if suggestion.member != current_user.member_record:
            flash('Access denied.', 'error')
            return redirect(url_for('payment_suggestions.list_suggestions'))
    
    # Get plan data
    original_plan = suggestion.get_original_plan()
    suggested_plan = suggestion.get_suggested_plan()
    treasurer_modified_plan = suggestion.get_treasurer_modified_plan()
    
    return render_template('payment_suggestions/detail.html',
                         suggestion=suggestion,
                         original_plan=original_plan,
                         suggested_plan=suggested_plan,
                         treasurer_modified_plan=treasurer_modified_plan)

@payment_suggestions_bp.route('/<int:id>/approve', methods=['POST'])
@login_required
@permission_required('manage_all_finances')
def approve_suggestion(id):
    """Approve a payment plan suggestion"""
    
    suggestion = PaymentPlanSuggestion.query.get_or_404(id)
    
    if suggestion.status != 'pending' and suggestion.status != 'modified':
        return jsonify({'success': False, 'message': 'Suggestion is not pending approval'}), 400
    
    try:
        # Get approval data
        use_modified_plan = request.json.get('use_modified', False) if request.is_json else False
        treasurer_notes = request.json.get('notes', '') if request.is_json else ''
        
        # Determine which plan to apply
        if use_modified_plan and suggestion.treasurer_modified_plan:
            plan_to_apply = suggestion.get_treasurer_modified_plan()
        else:
            plan_to_apply = suggestion.get_suggested_plan()
        
        # Apply the payment plan to the member
        member = suggestion.member
        member.payment_plan = plan_to_apply.get('payment_plan', member.payment_plan)
        
        if plan_to_apply.get('custom_schedule'):
            member.set_custom_schedule(plan_to_apply['custom_schedule'])
        elif member.payment_plan != 'custom':
            member.custom_schedule = None
        
        # Update suggestion status
        suggestion.status = 'approved'
        suggestion.reviewed_at = datetime.utcnow()
        suggestion.treasurer_notes = treasurer_notes
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Payment plan suggestion approved and applied to {member.name}!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error approving suggestion: {str(e)}'}), 500

@payment_suggestions_bp.route('/<int:id>/modify', methods=['POST'])
@login_required
@permission_required('manage_all_finances')
def modify_suggestion(id):
    """Modify a payment plan suggestion (treasurer counter-proposal)"""
    
    suggestion = PaymentPlanSuggestion.query.get_or_404(id)
    
    if suggestion.status not in ['pending', 'modified']:
        return jsonify({'success': False, 'message': 'Suggestion cannot be modified'}), 400
    
    try:
        # Get modification data from form
        modification_type = request.json.get('modification_type') if request.is_json else request.form.get('modification_type')
        treasurer_notes = request.json.get('notes', '') if request.is_json else request.form.get('notes', '')
        
        if not modification_type:
            return jsonify({'success': False, 'message': 'Modification type is required'}), 400
        
        # Create modified plan based on type
        modified_plan = {}
        
        if modification_type == 'adjust_amounts':
            # Parse adjusted custom schedule
            if request.is_json:
                custom_schedule = request.json.get('custom_schedule', [])
            else:
                # Handle form data (similar to create_suggestion)
                payment_count = int(request.form.get('payment_count', 0))
                custom_schedule = []
                for i in range(payment_count):
                    payment_date = request.form.get(f'payment_date_{i}')
                    payment_amount = request.form.get(f'payment_amount_{i}', type=float)
                    payment_description = request.form.get(f'payment_description_{i}', '').strip()
                    
                    if payment_date and payment_amount and payment_amount > 0:
                        custom_schedule.append({
                            'date': payment_date,
                            'amount': payment_amount,
                            'description': payment_description or f'Payment {i+1}'
                        })
            
            modified_plan = {
                'payment_plan': 'custom',
                'dues_amount': suggestion.member.dues_amount,
                'custom_schedule': custom_schedule
            }
        
        elif modification_type == 'different_plan_type':
            new_plan_type = request.json.get('new_plan_type') if request.is_json else request.form.get('new_plan_type')
            modified_plan = {
                'payment_plan': new_plan_type,
                'dues_amount': suggestion.member.dues_amount,
                'custom_schedule': None
            }
        
        # Save modified plan
        suggestion.set_treasurer_modified_plan(modified_plan)
        suggestion.status = 'modified'
        suggestion.treasurer_notes = treasurer_notes
        suggestion.reviewed_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Payment plan suggestion modified. Member can accept or negotiate further.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error modifying suggestion: {str(e)}'}), 500

@payment_suggestions_bp.route('/<int:id>/reject', methods=['POST'])
@login_required
@permission_required('manage_all_finances')
def reject_suggestion(id):
    """Reject a payment plan suggestion"""
    
    suggestion = PaymentPlanSuggestion.query.get_or_404(id)
    
    if suggestion.status != 'pending' and suggestion.status != 'modified':
        return jsonify({'success': False, 'message': 'Suggestion is not pending'}), 400
    
    rejection_reason = request.json.get('reason', '').strip() if request.is_json else ''
    if not rejection_reason:
        return jsonify({'success': False, 'message': 'Rejection reason is required'}), 400
    
    try:
        suggestion.status = 'rejected'
        suggestion.reviewed_at = datetime.utcnow()
        suggestion.treasurer_notes = rejection_reason
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Payment plan suggestion rejected.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error rejecting suggestion: {str(e)}'}), 500

@payment_suggestions_bp.route('/<int:id>/accept', methods=['POST'])
@login_required
def accept_modified_suggestion(id):
    """Accept a treasurer's modified payment plan (member action)"""
    
    suggestion = PaymentPlanSuggestion.query.get_or_404(id)
    
    # Check if user owns this suggestion
    if suggestion.member != current_user.member_record:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    if suggestion.status != 'modified':
        return jsonify({'success': False, 'message': 'No modified plan to accept'}), 400
    
    try:
        # Apply the treasurer's modified plan
        modified_plan = suggestion.get_treasurer_modified_plan()
        member = suggestion.member
        
        member.payment_plan = modified_plan.get('payment_plan', member.payment_plan)
        
        if modified_plan.get('custom_schedule'):
            member.set_custom_schedule(modified_plan['custom_schedule'])
        elif member.payment_plan != 'custom':
            member.custom_schedule = None
        
        # Update suggestion status
        suggestion.status = 'accepted'
        suggestion.reviewed_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Modified payment plan accepted and applied!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error accepting plan: {str(e)}'}), 500

@payment_suggestions_bp.route('/summary')
@login_required
@permission_required('view_all_data')
def suggestions_summary():
    """Dashboard summary of payment plan suggestions"""
    
    # Get counts by status
    pending_count = PaymentPlanSuggestion.query.filter_by(status='pending').count()
    modified_count = PaymentPlanSuggestion.query.filter_by(status='modified').count()
    approved_count = PaymentPlanSuggestion.query.filter_by(status='approved').count()
    rejected_count = PaymentPlanSuggestion.query.filter_by(status='rejected').count()
    
    # Recent suggestions
    recent_suggestions = PaymentPlanSuggestion.query.order_by(
        PaymentPlanSuggestion.created_at.desc()
    ).limit(10).all()
    
    # Get suggestions requiring action
    action_required = PaymentPlanSuggestion.query.filter(
        PaymentPlanSuggestion.status.in_(['pending', 'modified'])
    ).count()
    
    return render_template('payment_suggestions/summary.html',
                         pending_count=pending_count,
                         modified_count=modified_count,
                         approved_count=approved_count,
                         rejected_count=rejected_count,
                         action_required=action_required,
                         recent_suggestions=recent_suggestions)