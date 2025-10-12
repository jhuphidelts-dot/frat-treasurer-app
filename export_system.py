"""
Advanced Data Export System
Comprehensive export functionality with CSV, PDF, and Excel support
"""

from flask import Blueprint, request, jsonify, send_file, render_template
from flask_login import login_required, current_user
from models import db, Member, Payment, Transaction, ReimbursementRequest, SpendingPlan, Semester, User
from rbac import permission_required, has_permission
from datetime import datetime, timedelta
import io
import csv
import json
from typing import Dict, List, Any, Optional
import tempfile
import os

# Optional dependencies with graceful fallback
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

try:
    import xlsxwriter
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False

export_bp = Blueprint('export', __name__, url_prefix='/export')

class DataExporter:
    """Main class for handling data exports in multiple formats"""
    
    def __init__(self):
        self.supported_formats = ['csv', 'json']
        if HAS_XLSXWRITER:
            self.supported_formats.append('excel')
        if HAS_REPORTLAB:
            self.supported_formats.append('pdf')
        self.export_types = {
            'members': 'Member Data',
            'transactions': 'Transaction History', 
            'financial_summary': 'Financial Summary',
            'reimbursements': 'Reimbursement Requests',
            'spending_plans': 'Spending Plans',
            'semester_report': 'Complete Semester Report',
            'dues_collection': 'Dues Collection Report',
            'budget_analysis': 'Budget vs Actual Analysis'
        }
    
    def get_export_data(self, export_type: str, filters: Dict = None) -> Dict[str, Any]:
        """Get data for export based on type and filters"""
        
        if not filters:
            filters = {}
            
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        semester_id = filters.get('semester_id')
        category = filters.get('category')
        
        if export_type == 'members':
            return self._get_member_data(filters)
        elif export_type == 'transactions':
            return self._get_transaction_data(start_date, end_date, category)
        elif export_type == 'financial_summary':
            return self._get_financial_summary_data(semester_id)
        elif export_type == 'reimbursements':
            return self._get_reimbursement_data(start_date, end_date)
        elif export_type == 'spending_plans':
            return self._get_spending_plans_data(semester_id)
        elif export_type == 'semester_report':
            return self._get_complete_semester_report(semester_id)
        elif export_type == 'dues_collection':
            return self._get_dues_collection_data(semester_id)
        elif export_type == 'budget_analysis':
            return self._get_budget_analysis_data(semester_id)
        else:
            raise ValueError(f"Unknown export type: {export_type}")
    
    def _get_member_data(self, filters: Dict) -> Dict[str, Any]:
        """Get member data with payment information"""
        
        query = Member.query
        
        # Apply filters
        if filters.get('payment_status') == 'overdue':
            # This would need to be implemented based on your Member model
            pass
        elif filters.get('payment_status') == 'paid':
            # Filter for fully paid members
            pass
            
        members = query.all()
        
        data = []
        for member in members:
            total_paid = sum(payment.amount for payment in member.payments)
            balance = member.dues_amount - total_paid
            
            member_data = {
                'ID': member.id,
                'Name': member.name,
                'Email': getattr(member, 'email', ''),
                'Phone': getattr(member, 'phone', ''),
                'Dues Amount': member.dues_amount,
                'Total Paid': total_paid,
                'Balance': balance,
                'Payment Plan': member.payment_plan,
                'Status': 'Paid' if balance <= 0 else f'Owes ${balance:.2f}',
                'Last Payment': max([p.date for p in member.payments], default='Never') if hasattr(member, 'payments') else 'Never',
                'Member Since': member.created_at.strftime('%Y-%m-%d') if hasattr(member, 'created_at') else 'Unknown'
            }
            data.append(member_data)
        
        return {
            'data': data,
            'title': 'Member Data Report',
            'generated_at': datetime.now(),
            'filters_applied': filters,
            'total_records': len(data)
        }
    
    def _get_transaction_data(self, start_date: str, end_date: str, category: str = None) -> Dict[str, Any]:
        """Get transaction data with filtering"""
        
        query = Transaction.query
        
        if start_date:
            query = query.filter(Transaction.date >= start_date)
        if end_date:
            query = query.filter(Transaction.date <= end_date)
        if category:
            query = query.filter(Transaction.category == category)
            
        transactions = query.order_by(Transaction.date.desc()).all()
        
        data = []
        for txn in transactions:
            data.append({
                'ID': txn.id,
                'Date': txn.date.strftime('%Y-%m-%d') if hasattr(txn.date, 'strftime') else str(txn.date),
                'Category': txn.category,
                'Description': txn.description,
                'Amount': txn.amount,
                'Type': txn.type.title(),
                'Balance Impact': f"+${txn.amount:.2f}" if txn.type == 'income' else f"-${txn.amount:.2f}"
            })
        
        # Calculate totals
        total_income = sum(txn.amount for txn in transactions if txn.type == 'income')
        total_expenses = sum(txn.amount for txn in transactions if txn.type == 'expense')
        net_change = total_income - total_expenses
        
        return {
            'data': data,
            'title': 'Transaction History Report',
            'generated_at': datetime.now(),
            'date_range': f"{start_date or 'Beginning'} to {end_date or 'Present'}",
            'summary': {
                'total_income': total_income,
                'total_expenses': total_expenses,
                'net_change': net_change,
                'transaction_count': len(data)
            },
            'filters_applied': {'start_date': start_date, 'end_date': end_date, 'category': category}
        }
    
    def _get_financial_summary_data(self, semester_id: str = None) -> Dict[str, Any]:
        """Get comprehensive financial summary"""
        
        # Get current semester if none specified
        if not semester_id:
            semester = Semester.query.filter_by(is_current=True).first()
            semester_id = semester.id if semester else None
        
        # Get all financial data for semester
        members = Member.query.filter_by(semester_id=semester_id).all() if semester_id else Member.query.all()
        transactions = Transaction.query.filter_by(semester_id=semester_id).all() if semester_id else Transaction.query.all()
        
        # Calculate dues summary
        total_dues_expected = sum(member.dues_amount for member in members)
        total_dues_collected = sum(
            sum(payment.amount for payment in member.payments) 
            for member in members if hasattr(member, 'payments')
        )
        outstanding_dues = total_dues_expected - total_dues_collected
        collection_rate = (total_dues_collected / total_dues_expected * 100) if total_dues_expected > 0 else 0
        
        # Calculate budget summary by category
        budget_categories = {}
        for txn in transactions:
            if txn.category not in budget_categories:
                budget_categories[txn.category] = {'income': 0, 'expenses': 0}
            
            if txn.type == 'income':
                budget_categories[txn.category]['income'] += txn.amount
            else:
                budget_categories[txn.category]['expenses'] += txn.amount
        
        return {
            'title': 'Financial Summary Report',
            'generated_at': datetime.now(),
            'semester_id': semester_id,
            'dues_summary': {
                'total_expected': total_dues_expected,
                'total_collected': total_dues_collected,
                'outstanding': outstanding_dues,
                'collection_rate': collection_rate,
                'members_count': len(members)
            },
            'budget_summary': budget_categories,
            'transaction_summary': {
                'total_transactions': len(transactions),
                'total_income': sum(txn.amount for txn in transactions if txn.type == 'income'),
                'total_expenses': sum(txn.amount for txn in transactions if txn.type == 'expense')
            }
        }
    
    def _get_spending_plans_data(self, semester_id: str = None) -> Dict[str, Any]:
        """Get spending plans data"""
        query = SpendingPlan.query
        if semester_id:
            query = query.filter_by(semester_id=semester_id)
        
        plans = query.all()
        data = []
        for plan in plans:
            creator = User.query.get(plan.created_by)
            plan_data = plan.get_plan_data() if hasattr(plan, 'get_plan_data') else {}
            data.append({
                'ID': plan.id,
                'Title': plan.title,
                'Category': plan.category,
                'Created By': creator.name if creator else 'Unknown',
                'Total Budget': plan_data.get('total_budget', 0),
                'Status': 'Approved' if plan.treasurer_approved else 'Pending',
                'Created Date': plan.created_at.strftime('%Y-%m-%d') if hasattr(plan, 'created_at') else 'Unknown',
                'Version': getattr(plan, 'version', 1)
            })
        
        return {
            'data': data,
            'title': 'Spending Plans Report',
            'generated_at': datetime.now(),
            'total_records': len(data)
        }
    
    def _get_complete_semester_report(self, semester_id: str = None) -> Dict[str, Any]:
        """Get complete semester report combining all data"""
        # This would combine member, transaction, and financial data
        financial_summary = self._get_financial_summary_data(semester_id)
        
        return {
            'title': 'Complete Semester Report',
            'generated_at': datetime.now(),
            'semester_id': semester_id,
            'data': [financial_summary],  # Simplified for now
            'summary': financial_summary
        }
    
    def _get_dues_collection_data(self, semester_id: str = None) -> Dict[str, Any]:
        """Get dues collection specific data"""
        members = Member.query.filter_by(semester_id=semester_id).all() if semester_id else Member.query.all()
        
        data = []
        for member in members:
            total_paid = sum(payment.amount for payment in getattr(member, 'payments', []))
            balance = member.dues_amount - total_paid
            
            data.append({
                'Member ID': member.id,
                'Name': member.name,
                'Dues Amount': member.dues_amount,
                'Amount Paid': total_paid,
                'Outstanding': balance,
                'Payment Plan': member.payment_plan,
                'Collection Status': 'Complete' if balance <= 0 else 'Outstanding'
            })
        
        return {
            'data': data,
            'title': 'Dues Collection Report',
            'generated_at': datetime.now(),
            'total_records': len(data)
        }
    
    def _get_budget_analysis_data(self, semester_id: str = None) -> Dict[str, Any]:
        """Get budget vs actual analysis"""
        # This would compare budgeted amounts vs actual spending
        # Simplified implementation
        return {
            'data': [{'Analysis': 'Budget vs Actual comparison would be implemented here'}],
            'title': 'Budget Analysis Report',
            'generated_at': datetime.now(),
            'total_records': 1
        }
    
    def _get_reimbursement_data(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get reimbursement request data"""
        
        query = ReimbursementRequest.query
        
        if start_date:
            query = query.filter(ReimbursementRequest.created_at >= start_date)
        if end_date:
            query = query.filter(ReimbursementRequest.created_at <= end_date)
            
        reimbursements = query.order_by(ReimbursementRequest.created_at.desc()).all()
        
        data = []
        for reimb in reimbursements:
            user = User.query.get(reimb.requested_by)
            data.append({
                'ID': reimb.id,
                'Date Submitted': reimb.created_at.strftime('%Y-%m-%d'),
                'Requested By': user.name if user else 'Unknown',
                'Category': reimb.category,
                'Purpose': reimb.purpose,
                'Amount': reimb.amount,
                'Status': reimb.status.title(),
                'Approved By': User.query.get(reimb.reviewed_by).name if reimb.reviewed_by else 'Pending',
                'Date Reviewed': reimb.reviewed_at.strftime('%Y-%m-%d') if reimb.reviewed_at else 'Pending'
            })
        
        # Calculate totals by status
        status_totals = {}
        for reimb in reimbursements:
            status = reimb.status
            if status not in status_totals:
                status_totals[status] = {'count': 0, 'amount': 0}
            status_totals[status]['count'] += 1
            status_totals[status]['amount'] += reimb.amount
        
        return {
            'data': data,
            'title': 'Reimbursement Requests Report',
            'generated_at': datetime.now(),
            'date_range': f"{start_date or 'Beginning'} to {end_date or 'Present'}",
            'summary': {
                'total_requests': len(data),
                'total_amount_requested': sum(reimb.amount for reimb in reimbursements),
                'status_breakdown': status_totals
            }
        }
    
    def export_to_csv(self, data: Dict[str, Any]) -> io.StringIO:
        """Export data to CSV format"""
        
        output = io.StringIO()
        
        if 'data' in data and isinstance(data['data'], list) and data['data']:
            # Write main data
            fieldnames = list(data['data'][0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            
            # Write header with metadata
            output.write(f"# {data['title']}\n")
            output.write(f"# Generated: {data['generated_at'].strftime('%Y-%m-%d %H:%M:%S')}\n")
            if 'date_range' in data:
                output.write(f"# Date Range: {data['date_range']}\n")
            output.write(f"# Total Records: {len(data['data'])}\n")
            output.write("\n")
            
            writer.writeheader()
            writer.writerows(data['data'])
            
            # Write summary if available
            if 'summary' in data:
                output.write("\n# SUMMARY\n")
                for key, value in data['summary'].items():
                    if isinstance(value, dict):
                        output.write(f"# {key.replace('_', ' ').title()}:\n")
                        for sub_key, sub_value in value.items():
                            output.write(f"#   {sub_key}: {sub_value}\n")
                    else:
                        output.write(f"# {key.replace('_', ' ').title()}: {value}\n")
        
        output.seek(0)
        return output
    
    def export_to_excel(self, data: Dict[str, Any]) -> io.BytesIO:
        """Export data to Excel format with formatting"""
        
        if not HAS_XLSXWRITER:
            raise ImportError("Excel export requires xlsxwriter. Install with: pip install xlsxwriter")
        
        if not HAS_PANDAS:
            raise ImportError("Excel export requires pandas. Install with: pip install pandas")
        
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Define formats
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#4472C4',
                'font_color': 'white',
                'border': 1
            })
            
            money_format = workbook.add_format({'num_format': '$#,##0.00'})
            date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
            
            # Main data sheet
            if 'data' in data and data['data']:
                df = pd.DataFrame(data['data'])
                df.to_excel(writer, sheet_name='Data', index=False, startrow=4)
                
                worksheet = writer.sheets['Data']
                
                # Add title and metadata
                worksheet.write(0, 0, data['title'], workbook.add_format({'bold': True, 'font_size': 16}))
                worksheet.write(1, 0, f"Generated: {data['generated_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                if 'date_range' in data:
                    worksheet.write(2, 0, f"Date Range: {data['date_range']}")
                worksheet.write(3, 0, f"Total Records: {len(data['data'])}")
                
                # Format headers
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(4, col_num, value, header_format)
                
                # Auto-adjust column widths
                for i, col in enumerate(df.columns):
                    max_len = max(
                        df[col].astype(str).str.len().max(),
                        len(str(col))
                    ) + 2
                    worksheet.set_column(i, i, min(max_len, 50))
                
                # Apply number formatting
                for i, col in enumerate(df.columns):
                    if 'amount' in col.lower() or 'balance' in col.lower() or '$' in str(df[col].iloc[0] if not df.empty else ''):
                        worksheet.set_column(i, i, 12, money_format)
                    elif 'date' in col.lower():
                        worksheet.set_column(i, i, 12, date_format)
            
            # Summary sheet
            if 'summary' in data:
                summary_data = []
                for key, value in data['summary'].items():
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            summary_data.append({
                                'Category': key.replace('_', ' ').title(),
                                'Metric': sub_key.replace('_', ' ').title(),
                                'Value': sub_value
                            })
                    else:
                        summary_data.append({
                            'Category': 'Summary',
                            'Metric': key.replace('_', ' ').title(),
                            'Value': value
                        })
                
                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    
                    summary_sheet = writer.sheets['Summary']
                    for col_num, value in enumerate(summary_df.columns.values):
                        summary_sheet.write(0, col_num, value, header_format)
        
        output.seek(0)
        return output
    
    def export_to_pdf(self, data: Dict[str, Any]) -> io.BytesIO:
        """Export data to PDF format with professional styling"""
        
        if not HAS_REPORTLAB:
            raise ImportError("PDF export requires reportlab. Install with: pip install reportlab")
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=inch)
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12
        )
        
        # Build story
        story = []
        
        # Title
        story.append(Paragraph(data['title'], title_style))
        story.append(Spacer(1, 20))
        
        # Metadata
        story.append(Paragraph(f"<b>Generated:</b> {data['generated_at'].strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        if 'date_range' in data:
            story.append(Paragraph(f"<b>Date Range:</b> {data['date_range']}", styles['Normal']))
        story.append(Paragraph(f"<b>Total Records:</b> {len(data.get('data', []))}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Summary section
        if 'summary' in data:
            story.append(Paragraph("Summary", heading_style))
            
            summary_data = []
            for key, value in data['summary'].items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        summary_data.append([
                            key.replace('_', ' ').title(),
                            sub_key.replace('_', ' ').title(),
                            str(sub_value)
                        ])
                else:
                    summary_data.append([
                        'Summary',
                        key.replace('_', ' ').title(),
                        str(value)
                    ])
            
            if summary_data:
                summary_table = Table(summary_data, colWidths=[2*inch, 2*inch, 1.5*inch])
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(summary_table)
                story.append(PageBreak())
        
        # Data table
        if 'data' in data and data['data']:
            story.append(Paragraph("Detailed Data", heading_style))
            
            # Prepare table data
            table_data = []
            if data['data']:
                headers = list(data['data'][0].keys())
                table_data.append(headers)
                
                # Add rows (limit to prevent huge PDFs)
                max_rows = 100  # Limit for PDF readability
                for i, row in enumerate(data['data'][:max_rows]):
                    table_data.append([str(row.get(header, '')) for header in headers])
                
                if len(data['data']) > max_rows:
                    table_data.append(['...'] * len(headers))
                    table_data.append([f"Showing {max_rows} of {len(data['data'])} records"] + [''] * (len(headers) - 1))
                
                # Create table
                col_widths = [min(1.5*inch, 6*inch / len(headers)) for _ in headers]
                data_table = Table(table_data, colWidths=col_widths)
                data_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP')
                ]))
                story.append(data_table)
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer

# Export routes
@export_bp.route('/')
@login_required
@permission_required('view_all_data')
def export_dashboard():
    """Export dashboard with options"""
    
    exporter = DataExporter()
    semesters = Semester.query.order_by(Semester.year.desc(), Semester.season).all()
    
    return render_template('export/dashboard.html',
                         export_types=exporter.export_types,
                         supported_formats=exporter.supported_formats,
                         semesters=semesters)

@export_bp.route('/generate', methods=['POST'])
@login_required
@permission_required('view_all_data')
def generate_export():
    """Generate and download export file"""
    
    try:
        # Get parameters
        export_type = request.form.get('export_type')
        format_type = request.form.get('format')
        
        # Build filters
        filters = {
            'start_date': request.form.get('start_date'),
            'end_date': request.form.get('end_date'),
            'semester_id': request.form.get('semester_id'),
            'category': request.form.get('category'),
            'payment_status': request.form.get('payment_status')
        }
        
        # Remove empty filters
        filters = {k: v for k, v in filters.items() if v}
        
        # Initialize exporter and get data
        exporter = DataExporter()
        data = exporter.get_export_data(export_type, filters)
        
        # Generate file based on format
        if format_type == 'csv':
            file_data = exporter.export_to_csv(data)
            mimetype = 'text/csv'
            filename = f"{export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            return send_file(
                io.BytesIO(file_data.getvalue().encode()),
                mimetype=mimetype,
                as_attachment=True,
                download_name=filename
            )
            
        elif format_type == 'excel':
            file_data = exporter.export_to_excel(data)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f"{export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            return send_file(
                file_data,
                mimetype=mimetype,
                as_attachment=True,
                download_name=filename
            )
            
        elif format_type == 'pdf':
            file_data = exporter.export_to_pdf(data)
            mimetype = 'application/pdf'
            filename = f"{export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            return send_file(
                file_data,
                mimetype=mimetype,
                as_attachment=True,
                download_name=filename
            )
            
        elif format_type == 'json':
            mimetype = 'application/json'
            filename = f"{export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            return send_file(
                io.BytesIO(json.dumps(data, indent=2, default=str).encode()),
                mimetype=mimetype,
                as_attachment=True,
                download_name=filename
            )
        
        else:
            return jsonify({'error': 'Invalid format specified'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Export failed: {str(e)}'}), 500

@export_bp.route('/preview', methods=['POST'])
@login_required
@permission_required('view_all_data')
def preview_export():
    """Preview export data before downloading"""
    
    try:
        export_type = request.json.get('export_type')
        filters = request.json.get('filters', {})
        
        exporter = DataExporter()
        data = exporter.get_export_data(export_type, filters)
        
        # Return preview (first 10 rows)
        preview_data = data.copy()
        if 'data' in preview_data and len(preview_data['data']) > 10:
            preview_data['data'] = preview_data['data'][:10]
            preview_data['preview_note'] = f"Showing 10 of {len(data['data'])} records"
        
        return jsonify(preview_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500