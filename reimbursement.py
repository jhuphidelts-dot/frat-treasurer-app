"""
Reimbursement Request Management Module
Handles creation, approval, and tracking of reimbursement requests
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, ReimbursementRequest, Member, BudgetLimit, Transaction
from rbac import permission_required, has_permission
from notifications import NotificationEvents
from datetime import datetime
import os
from werkzeug.utils import secure_filename

reimbursement_bp = Blueprint('reimbursement', __name__)

# Configuration
UPLOAD_FOLDER = 'uploads/receipts'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'heic'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_receipt_file(file):
    """Save uploaded receipt file and return filename"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to filename to avoid conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        # Ensure upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        return filename
    return None

@reimbursement_bp.route('/reimbursements')
@login_required
def list_reimbursements():
    """List reimbursement requests based on user permissions"""
    
    # Check permissions to determine what requests to show
    if has_permission('view_all_data'):
        # Treasurer/President can see all requests
        requests = ReimbursementRequest.query.order_by(
            ReimbursementRequest.created_at.desc()
        ).all()
        template = 'reimbursement/admin_list.html'
    elif has_permission('manage_own_budget'):
        # Officers can see their own requests
        requests = ReimbursementRequest.query.filter_by(
            requested_by=current_user.id
        ).order_by(ReimbursementRequest.created_at.desc()).all()
        template = 'reimbursement/officer_list.html'
    else:
        # Brothers can only see their own requests (if any)
        requests = ReimbursementRequest.query.filter_by(
            requested_by=current_user.id
        ).order_by(ReimbursementRequest.created_at.desc()).all()
        template = 'reimbursement/member_list.html'
    
    return render_template(template, requests=requests)

@reimbursement_bp.route('/reimbursements/new', methods=['GET', 'POST'])
@login_required
@permission_required('submit_reimbursement')
def create_reimbursement():
    """Create a new reimbursement request"""
    
    if request.method == 'GET':
        # Get available budget categories for the user
        if has_permission('manage_own_budget'):
            # Officers can submit for their assigned categories
            user_roles = [role.name for role in current_user.roles]
            category_mapping = {
                'social_chair': 'Social',
                'phi_ed_chair': 'Phi ED', 
                'recruitment_chair': 'Recruitment',
                'brotherhood_chair': 'Brotherhood'
            }
            
            available_categories = []
            for role, category in category_mapping.items():
                if role in user_roles:
                    available_categories.append(category)
            
            budgets = BudgetLimit.query.filter(BudgetLimit.category.in_(available_categories)).all()
        else:
            # Regular members can see all categories (refined by business rules)
            budgets = BudgetLimit.query.all()
        
        return render_template('reimbursement/create.html', budgets=budgets)
    
    # Handle form submission
    try:
        # Validate required fields
        budget_id = request.form.get('budget_id', type=int)
        amount = request.form.get('amount', type=float)
        description = request.form.get('description', '').strip()
        expense_date = request.form.get('expense_date')
        
        if not all([budget_id, amount, description, expense_date]):
            flash('All fields are required.', 'error')
            return redirect(url_for('reimbursement.create_reimbursement'))
        
        if amount <= 0:
            flash('Amount must be greater than zero.', 'error')
            return redirect(url_for('reimbursement.create_reimbursement'))
        
        # Validate budget access
        budget = BudgetLimit.query.get_or_404(budget_id)
        if has_permission('manage_own_budget'):
            # Check if user can submit for this category
            user_roles = [role.name for role in current_user.roles]
            category_mapping = {
                'social_chair': 'Social',
                'phi_ed_chair': 'Phi ED',
                'recruitment_chair': 'Recruitment', 
                'brotherhood_chair': 'Brotherhood'
            }
            
            allowed_categories = [category for role, category in category_mapping.items() if role in user_roles]
            if budget.category not in allowed_categories:
                flash('You can only submit reimbursement requests for your assigned budget categories.', 'error')
                return redirect(url_for('reimbursement.create_reimbursement'))
        
        # Handle file upload
        receipt_filename = None
        if 'receipt' in request.files:
            file = request.files['receipt']
            if file.filename != '':
                if file.content_length > MAX_FILE_SIZE:
                    flash('File size must be less than 5MB.', 'error')
                    return redirect(url_for('reimbursement.create_reimbursement'))
                
                receipt_filename = save_receipt_file(file)
                if not receipt_filename:
                    flash('Invalid file type. Please upload PDF, PNG, JPG, JPEG, GIF, or HEIC files.', 'error')
                    return redirect(url_for('reimbursement.create_reimbursement'))
        
        # Parse expense date
        expense_date = datetime.strptime(expense_date, '%Y-%m-%d').date()
        
        # Create reimbursement request  
        reimbursement = ReimbursementRequest(
            requested_by=current_user.id,
            category=budget.category,
            amount=amount,
            purpose=description,
            receipt_filename=receipt_filename,
            status='pending'
        )
        
        db.session.add(reimbursement)
        db.session.commit()
        
        flash(f'Reimbursement request for ${amount:.2f} submitted successfully!', 'success')
        return redirect(url_for('reimbursement.view_reimbursement', id=reimbursement.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating reimbursement request: {str(e)}', 'error')
        return redirect(url_for('reimbursement.create_reimbursement'))

@reimbursement_bp.route('/reimbursements/<int:id>')
@login_required
def view_reimbursement(id):
    """View a specific reimbursement request"""
    
    reimbursement = ReimbursementRequest.query.get_or_404(id)
    
    # Check if user can view this request
    if not has_permission('view_all_data'):
        if reimbursement.requested_by != current_user.id:
            flash('Access denied.', 'error')
            return redirect(url_for('reimbursement.list_reimbursements'))
    
    return render_template('reimbursement/detail.html', reimbursement=reimbursement)

@reimbursement_bp.route('/reimbursements/<int:id>/approve', methods=['POST'])
@login_required
@permission_required('approve_reimbursements')
def approve_reimbursement(id):
    """Approve a reimbursement request and create transaction"""
    
    reimbursement = ReimbursementRequest.query.get_or_404(id)
    
    if reimbursement.status != 'pending':
        return jsonify({'success': False, 'message': 'Request is not pending'}), 400
    
    try:
        # Update reimbursement status
        reimbursement.status = 'approved'
        reimbursement.reviewed_by = current_user.id
        reimbursement.reviewed_at = datetime.utcnow()
        
        # Create transaction (need to handle missing fields)
        # Note: Transaction model may need updating to match expected fields
        
        db.session.add(transaction)
        db.session.commit()
        
        # Send approval notification
        try:
            NotificationEvents.on_reimbursement_approved(reimbursement)
        except Exception as e:
            # Don't fail the approval if notification fails
            print(f"Notification failed: {e}")
        
        return jsonify({
            'success': True, 
            'message': f'Reimbursement request for ${reimbursement.amount:.2f} approved successfully!'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error approving request: {str(e)}'}), 500

@reimbursement_bp.route('/reimbursements/<int:id>/reject', methods=['POST'])
@login_required
@permission_required('approve_reimbursements')
def reject_reimbursement(id):
    """Reject a reimbursement request"""
    
    reimbursement = ReimbursementRequest.query.get_or_404(id)
    
    if reimbursement.status != 'pending':
        return jsonify({'success': False, 'message': 'Request is not pending'}), 400
    
    rejection_reason = request.json.get('reason', '').strip()
    if not rejection_reason:
        return jsonify({'success': False, 'message': 'Rejection reason is required'}), 400
    
    try:
        reimbursement.status = 'rejected'
        reimbursement.reviewed_by = current_user.id
        reimbursement.reviewed_at = datetime.utcnow()
        reimbursement.reviewer_notes = rejection_reason
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Reimbursement request rejected successfully.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error rejecting request: {str(e)}'}), 500

@reimbursement_bp.route('/reimbursements/<int:id>/receipt')
@login_required
def view_receipt(id):
    """View receipt file for a reimbursement request"""
    
    reimbursement = ReimbursementRequest.query.get_or_404(id)
    
    # Check if user can view this receipt
    if not has_permission('view_all_data'):
        if reimbursement.requested_by != current_user.id:
            flash('Access denied.', 'error')
            return redirect(url_for('reimbursement.list_reimbursements'))
    
    if not reimbursement.receipt_filename:
        flash('No receipt found for this request.', 'error')
        return redirect(url_for('reimbursement.view_reimbursement', id=id))
    
    # In a production app, you'd serve the file securely
    receipt_path = os.path.join(UPLOAD_FOLDER, reimbursement.receipt_filename)
    if not os.path.exists(receipt_path):
        flash('Receipt file not found.', 'error')
        return redirect(url_for('reimbursement.view_reimbursement', id=id))
    
    # For now, return a simple response
    # In production, use send_from_directory or similar
    return f"Receipt file: {reimbursement.receipt_filename}"

@reimbursement_bp.route('/reimbursements/summary')
@login_required
@permission_required('view_all_data')
def reimbursement_summary():
    """Dashboard summary of reimbursement requests"""
    
    # Get counts by status
    pending_count = ReimbursementRequest.query.filter_by(status='pending').count()
    approved_count = ReimbursementRequest.query.filter_by(status='approved').count()
    rejected_count = ReimbursementRequest.query.filter_by(status='rejected').count()
    
    # Get total amounts
    total_pending = db.session.query(db.func.sum(ReimbursementRequest.amount))\
        .filter_by(status='pending').scalar() or 0
    total_approved = db.session.query(db.func.sum(ReimbursementRequest.amount))\
        .filter_by(status='approved').scalar() or 0
    
    # Recent requests
    recent_requests = ReimbursementRequest.query\
        .order_by(ReimbursementRequest.created_at.desc())\
        .limit(10).all()
    
    return render_template('reimbursement/summary.html', 
                         pending_count=pending_count,
                         approved_count=approved_count,
                         rejected_count=rejected_count,
                         total_pending=total_pending,
                         total_approved=total_approved,
                         recent_requests=recent_requests)