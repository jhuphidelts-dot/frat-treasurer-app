"""
Advanced Reporting & Analytics Module
Provides comprehensive financial reporting with visualizations and export capabilities
"""

from flask import Blueprint, render_template, request, jsonify, Response, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Member, Transaction, Payment, ReimbursementRequest, SpendingPlan, BudgetLimit, Semester
from rbac import permission_required, has_permission
from datetime import datetime, timedelta
from sqlalchemy import func, extract, and_
import csv
import io
import json

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
@permission_required('view_financial_reports')
def dashboard():
    """Main analytics dashboard"""
    return render_template('reports/dashboard.html')

@reports_bp.route('/financial-overview')
@login_required
@permission_required('view_financial_reports')
def financial_overview():
    """Comprehensive financial overview report"""
    
    # Get current semester
    current_semester = Semester.query.filter_by(is_current=True).first()
    if not current_semester:
        flash('No active semester found.', 'warning')
        return redirect(url_for('reports.dashboard'))
    
    # Calculate financial metrics
    total_members = Member.query.filter_by(semester_id=current_semester.id).count()
    total_dues = db.session.query(func.sum(Member.dues_amount)).filter_by(semester_id=current_semester.id).scalar() or 0
    total_collected = db.session.query(func.sum(Payment.amount)).join(Member).filter(Member.semester_id == current_semester.id).scalar() or 0
    collection_rate = (total_collected / total_dues * 100) if total_dues > 0 else 0
    
    # Outstanding balances
    members = Member.query.filter_by(semester_id=current_semester.id).all()
    outstanding_dues = sum(member.get_balance() for member in members if member.get_balance() > 0)
    
    # Budget analysis
    total_budget = db.session.query(func.sum(BudgetLimit.amount)).filter_by(semester_id=current_semester.id).scalar() or 0
    total_spent = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.semester_id == current_semester.id,
        Transaction.type == 'expense'
    ).scalar() or 0
    budget_utilization = (total_spent / total_budget * 100) if total_budget > 0 else 0
    
    # Reimbursement metrics
    pending_reimbursements = ReimbursementRequest.query.filter_by(status='pending').count()
    pending_amount = db.session.query(func.sum(ReimbursementRequest.amount)).filter_by(status='pending').scalar() or 0
    
    # Recent activity
    recent_transactions = Transaction.query.filter_by(semester_id=current_semester.id).order_by(
        Transaction.created_at.desc()
    ).limit(10).all()
    
    return render_template('reports/financial_overview.html',
                         current_semester=current_semester,
                         total_members=total_members,
                         total_dues=total_dues,
                         total_collected=total_collected,
                         collection_rate=collection_rate,
                         outstanding_dues=outstanding_dues,
                         total_budget=total_budget,
                         total_spent=total_spent,
                         budget_utilization=budget_utilization,
                         pending_reimbursements=pending_reimbursements,
                         pending_amount=pending_amount,
                         recent_transactions=recent_transactions)

@reports_bp.route('/budget-analysis')
@login_required
@permission_required('view_financial_reports')
def budget_analysis():
    """Detailed budget vs actual spending analysis"""
    
    current_semester = Semester.query.filter_by(is_current=True).first()
    if not current_semester:
        flash('No active semester found.', 'warning')
        return redirect(url_for('reports.dashboard'))
    
    # Get budget categories with spending
    budget_data = []
    categories = ['Social', 'Phi ED', 'Recruitment', 'Brotherhood', 'Executive', 'Philanthropy']
    
    for category in categories:
        budget_limit = BudgetLimit.query.filter_by(
            category=category,
            semester_id=current_semester.id
        ).first()
        
        allocated = budget_limit.amount if budget_limit else 0
        
        # Calculate actual spending
        spent = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.category == category,
            Transaction.semester_id == current_semester.id,
            Transaction.type == 'expense'
        ).scalar() or 0
        
        # Get pending reimbursements
        pending = db.session.query(func.sum(ReimbursementRequest.amount)).filter(
            ReimbursementRequest.category == category,
            ReimbursementRequest.status == 'pending'
        ).scalar() or 0
        
        remaining = allocated - spent
        utilization = (spent / allocated * 100) if allocated > 0 else 0
        
        budget_data.append({
            'category': category,
            'allocated': allocated,
            'spent': spent,
            'pending': pending,
            'remaining': remaining,
            'utilization': utilization
        })
    
    # Calculate totals
    total_allocated = sum(item['allocated'] for item in budget_data)
    total_spent = sum(item['spent'] for item in budget_data)
    total_pending = sum(item['pending'] for item in budget_data)
    total_remaining = sum(item['remaining'] for item in budget_data)
    
    return render_template('reports/budget_analysis.html',
                         current_semester=current_semester,
                         budget_data=budget_data,
                         total_allocated=total_allocated,
                         total_spent=total_spent,
                         total_pending=total_pending,
                         total_remaining=total_remaining)

@reports_bp.route('/payment-tracking')
@login_required
@permission_required('view_financial_reports')
def payment_tracking():
    """Payment collection tracking and analysis"""
    
    current_semester = Semester.query.filter_by(is_current=True).first()
    if not current_semester:
        flash('No active semester found.', 'warning')
        return redirect(url_for('reports.dashboard'))
    
    # Payment plan distribution
    payment_plans = db.session.query(
        Member.payment_plan,
        func.count(Member.id).label('count'),
        func.sum(Member.dues_amount).label('total_dues'),
        func.avg(Member.dues_amount).label('avg_dues')
    ).filter_by(semester_id=current_semester.id).group_by(Member.payment_plan).all()
    
    # Payment status analysis
    members = Member.query.filter_by(semester_id=current_semester.id).all()
    payment_status = {
        'paid_in_full': 0,
        'partial_payment': 0,
        'no_payment': 0,
        'overpaid': 0
    }
    
    for member in members:
        balance = member.get_balance()
        if balance == 0:
            payment_status['paid_in_full'] += 1
        elif balance < 0:
            payment_status['overpaid'] += 1
        elif member.get_total_paid() > 0:
            payment_status['partial_payment'] += 1
        else:
            payment_status['no_payment'] += 1
    
    # Monthly collection trends (last 6 months)
    monthly_collections = []
    for i in range(6):
        month_start = (datetime.now() - timedelta(days=30*i)).replace(day=1)
        month_end = (month_start.replace(month=month_start.month % 12 + 1, day=1) if month_start.month < 12 
                    else month_start.replace(year=month_start.year + 1, month=1, day=1)) - timedelta(days=1)
        
        monthly_total = db.session.query(func.sum(Payment.amount)).filter(
            and_(Payment.date >= month_start, Payment.date <= month_end)
        ).join(Member).filter(Member.semester_id == current_semester.id).scalar() or 0
        
        monthly_collections.append({
            'month': month_start.strftime('%B %Y'),
            'amount': monthly_total
        })
    
    monthly_collections.reverse()  # Show chronologically
    
    return render_template('reports/payment_tracking.html',
                         current_semester=current_semester,
                         payment_plans=payment_plans,
                         payment_status=payment_status,
                         monthly_collections=monthly_collections)

@reports_bp.route('/member-analysis')
@login_required
@permission_required('view_financial_reports')
def member_analysis():
    """Individual member financial analysis"""
    
    current_semester = Semester.query.filter_by(is_current=True).first()
    if not current_semester:
        flash('No active semester found.', 'warning')
        return redirect(url_for('reports.dashboard'))
    
    # Get member financial data
    members_data = []
    members = Member.query.filter_by(semester_id=current_semester.id).all()
    
    for member in members:
        total_paid = member.get_total_paid()
        balance = member.get_balance()
        payment_count = len(member.payments)
        
        # Payment history
        recent_payment = member.payments[-1] if member.payments else None
        
        members_data.append({
            'member': member,
            'total_paid': total_paid,
            'balance': balance,
            'payment_count': payment_count,
            'recent_payment': recent_payment,
            'status': 'Paid' if balance <= 0 else 'Outstanding'
        })
    
    # Sort by balance (highest outstanding first)
    members_data.sort(key=lambda x: x['balance'], reverse=True)
    
    return render_template('reports/member_analysis.html',
                         current_semester=current_semester,
                         members_data=members_data)

@reports_bp.route('/export/financial-summary')
@login_required
@permission_required('view_financial_reports')
def export_financial_summary():
    """Export financial summary as CSV"""
    
    current_semester = Semester.query.filter_by(is_current=True).first()
    if not current_semester:
        return "No active semester found", 404
    
    # Create CSV data
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Financial Summary - ' + current_semester.name])
    writer.writerow(['Generated on:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])  # Empty row
    
    # Summary metrics
    total_members = Member.query.filter_by(semester_id=current_semester.id).count()
    total_dues = db.session.query(func.sum(Member.dues_amount)).filter_by(semester_id=current_semester.id).scalar() or 0
    total_collected = db.session.query(func.sum(Payment.amount)).join(Member).filter(Member.semester_id == current_semester.id).scalar() or 0
    
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Total Members', total_members])
    writer.writerow(['Total Dues', f'${total_dues:,.2f}'])
    writer.writerow(['Total Collected', f'${total_collected:,.2f}'])
    writer.writerow(['Collection Rate', f'{(total_collected/total_dues*100) if total_dues > 0 else 0:.1f}%'])
    writer.writerow([])
    
    # Budget breakdown
    writer.writerow(['Budget Analysis'])
    writer.writerow(['Category', 'Allocated', 'Spent', 'Remaining', 'Utilization %'])
    
    categories = ['Social', 'Phi ED', 'Recruitment', 'Brotherhood', 'Executive', 'Philanthropy']
    for category in categories:
        budget_limit = BudgetLimit.query.filter_by(
            category=category,
            semester_id=current_semester.id
        ).first()
        
        allocated = budget_limit.amount if budget_limit else 0
        spent = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.category == category,
            Transaction.semester_id == current_semester.id,
            Transaction.type == 'expense'
        ).scalar() or 0
        
        remaining = allocated - spent
        utilization = (spent / allocated * 100) if allocated > 0 else 0
        
        writer.writerow([category, f'${allocated:,.2f}', f'${spent:,.2f}', 
                        f'${remaining:,.2f}', f'{utilization:.1f}%'])
    
    # Create response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=financial_summary_{current_semester.id}.csv'}
    )

@reports_bp.route('/export/member-payments')
@login_required
@permission_required('view_financial_reports')
def export_member_payments():
    """Export detailed member payment data as CSV"""
    
    current_semester = Semester.query.filter_by(is_current=True).first()
    if not current_semester:
        return "No active semester found", 404
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Member Payment Details - ' + current_semester.name])
    writer.writerow(['Generated on:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])
    
    writer.writerow(['Member Name', 'Contact', 'Dues Amount', 'Total Paid', 'Balance', 
                     'Payment Plan', 'Last Payment Date', 'Last Payment Amount'])
    
    members = Member.query.filter_by(semester_id=current_semester.id).all()
    for member in members:
        last_payment = member.payments[-1] if member.payments else None
        
        writer.writerow([
            member.name,
            member.contact,
            f'${member.dues_amount:,.2f}',
            f'${member.get_total_paid():,.2f}',
            f'${member.get_balance():,.2f}',
            member.payment_plan.title(),
            last_payment.date.strftime('%Y-%m-%d') if last_payment else 'None',
            f'${last_payment.amount:,.2f}' if last_payment else '$0.00'
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=member_payments_{current_semester.id}.csv'}
    )

# API endpoints for Chart.js data
@reports_bp.route('/api/budget-chart-data')
@login_required
@permission_required('view_financial_reports')
def budget_chart_data():
    """API endpoint for budget utilization chart data"""
    
    current_semester = Semester.query.filter_by(is_current=True).first()
    if not current_semester:
        return jsonify({'error': 'No active semester found'}), 404
    
    categories = []
    allocated_amounts = []
    spent_amounts = []
    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40']
    
    budget_categories = ['Social', 'Phi ED', 'Recruitment', 'Brotherhood', 'Executive', 'Philanthropy']
    
    for i, category in enumerate(budget_categories):
        budget_limit = BudgetLimit.query.filter_by(
            category=category,
            semester_id=current_semester.id
        ).first()
        
        allocated = budget_limit.amount if budget_limit else 0
        spent = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.category == category,
            Transaction.semester_id == current_semester.id,
            Transaction.type == 'expense'
        ).scalar() or 0
        
        categories.append(category)
        allocated_amounts.append(allocated)
        spent_amounts.append(spent)
    
    return jsonify({
        'labels': categories,
        'datasets': [
            {
                'label': 'Allocated',
                'data': allocated_amounts,
                'backgroundColor': [color + '80' for color in colors[:len(categories)]],
                'borderColor': colors[:len(categories)],
                'borderWidth': 1
            },
            {
                'label': 'Spent',
                'data': spent_amounts,
                'backgroundColor': [color + 'CC' for color in colors[:len(categories)]],
                'borderColor': colors[:len(categories)],
                'borderWidth': 1
            }
        ]
    })

@reports_bp.route('/api/payment-trends-data')
@login_required
@permission_required('view_financial_reports')
def payment_trends_data():
    """API endpoint for payment collection trends"""
    
    current_semester = Semester.query.filter_by(is_current=True).first()
    if not current_semester:
        return jsonify({'error': 'No active semester found'}), 404
    
    # Get last 6 months of payment data
    months = []
    amounts = []
    
    for i in range(6):
        month_start = (datetime.now() - timedelta(days=30*i)).replace(day=1)
        month_end = (month_start.replace(month=month_start.month % 12 + 1, day=1) if month_start.month < 12 
                    else month_start.replace(year=month_start.year + 1, month=1, day=1)) - timedelta(days=1)
        
        monthly_total = db.session.query(func.sum(Payment.amount)).filter(
            and_(Payment.date >= month_start, Payment.date <= month_end)
        ).join(Member).filter(Member.semester_id == current_semester.id).scalar() or 0
        
        months.append(month_start.strftime('%b %Y'))
        amounts.append(monthly_total)
    
    months.reverse()
    amounts.reverse()
    
    return jsonify({
        'labels': months,
        'datasets': [{
            'label': 'Monthly Collections',
            'data': amounts,
            'borderColor': '#36A2EB',
            'backgroundColor': '#36A2EB20',
            'fill': True,
            'tension': 0.4
        }]
    })

@reports_bp.route('/api/payment-status-data')
@login_required
@permission_required('view_financial_reports')
def payment_status_data():
    """API endpoint for payment status pie chart"""
    
    current_semester = Semester.query.filter_by(is_current=True).first()
    if not current_semester:
        return jsonify({'error': 'No active semester found'}), 404
    
    members = Member.query.filter_by(semester_id=current_semester.id).all()
    status_counts = {
        'Paid in Full': 0,
        'Partial Payment': 0,
        'No Payment': 0,
        'Overpaid': 0
    }
    
    for member in members:
        balance = member.get_balance()
        if balance == 0:
            status_counts['Paid in Full'] += 1
        elif balance < 0:
            status_counts['Overpaid'] += 1
        elif member.get_total_paid() > 0:
            status_counts['Partial Payment'] += 1
        else:
            status_counts['No Payment'] += 1
    
    return jsonify({
        'labels': list(status_counts.keys()),
        'datasets': [{
            'data': list(status_counts.values()),
            'backgroundColor': ['#28a745', '#ffc107', '#dc3545', '#17a2b8'],
            'borderWidth': 2
        }]
    })