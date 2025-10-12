"""
Email/SMS Notification System
Automated notifications for payment reminders, reimbursement updates, and other fraternity events
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, User, Member, Payment, ReimbursementRequest, SpendingPlan, PaymentPlanSuggestion
from rbac import permission_required, has_permission
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Email configuration (using environment variables for security)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'treasurer@fraternity.org')
REPLY_TO = os.getenv('REPLY_TO', 'treasurer@fraternity.org')

# SMS configuration (Twilio)
TWILIO_SID = os.getenv('TWILIO_SID', '')
TWILIO_TOKEN = os.getenv('TWILIO_TOKEN', '')
TWILIO_PHONE = os.getenv('TWILIO_PHONE', '')

class NotificationService:
    """Service class for sending notifications"""
    
    @staticmethod
    def send_email(to_email, subject, html_content, text_content=None):
        """Send email notification"""
        try:
            if not SMTP_USERNAME or not SMTP_PASSWORD:
                logger.warning("SMTP credentials not configured - email not sent")
                return False
            
            msg = MIMEMultipart('alternative')
            msg['From'] = FROM_EMAIL
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Reply-To'] = REPLY_TO
            
            # Add text content
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    @staticmethod
    def send_sms(to_phone, message):
        """Send SMS notification using Twilio"""
        try:
            if not TWILIO_SID or not TWILIO_TOKEN:
                logger.warning("Twilio credentials not configured - SMS not sent")
                return False
            
            from twilio.rest import Client
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            
            message = client.messages.create(
                body=message,
                from_=TWILIO_PHONE,
                to=to_phone
            )
            
            logger.info(f"SMS sent successfully to {to_phone}")
            return True
            
        except ImportError:
            logger.warning("Twilio library not installed - SMS not sent")
            return False
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_phone}: {str(e)}")
            return False
    
    @staticmethod
    def get_user_contact_info(user):
        """Get user's preferred contact information"""
        contact_info = {
            'email': getattr(user, 'email', None),
            'phone': getattr(user, 'phone', None),
            'prefers_sms': getattr(user, 'prefers_sms', False)
        }
        return contact_info

class NotificationTemplates:
    """Email and SMS templates for different notification types"""
    
    @staticmethod
    def payment_reminder_email(member, amount_due, due_date=None):
        """Payment reminder email template"""
        subject = f"Payment Reminder - ${amount_due:.2f} Due"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px;">
                <h2 style="color: #2c3e50; margin-bottom: 20px;">Payment Reminder</h2>
                
                <p>Hello {member.name},</p>
                
                <p>This is a friendly reminder that you have an outstanding balance of <strong>${amount_due:.2f}</strong> for this semester's dues.</p>
                
                <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Amount Due:</strong> ${amount_due:.2f}</p>
                    <p style="margin: 10px 0 0 0;"><strong>Payment Plan:</strong> {member.payment_plan.title()}</p>
                </div>
                
                <p>You can make payments through:</p>
                <ul>
                    <li>Venmo: @fraternity-treasurer</li>
                    <li>Zelle: treasurer@fraternity.org</li>
                    <li>Cash (see treasurer)</li>
                </ul>
                
                <p>If you have any questions or need to discuss your payment plan, please don't hesitate to reach out.</p>
                
                <p>Best regards,<br>
                The Treasurer Team</p>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="font-size: 12px; color: #666;">This is an automated message. Please do not reply directly to this email.</p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Payment Reminder
        
        Hello {member.name},
        
        This is a friendly reminder that you have an outstanding balance of ${amount_due:.2f} for this semester's dues.
        
        Amount Due: ${amount_due:.2f}
        Payment Plan: {member.payment_plan.title()}
        
        You can make payments through:
        - Venmo: @fraternity-treasurer
        - Zelle: treasurer@fraternity.org
        - Cash (see treasurer)
        
        If you have any questions or need to discuss your payment plan, please don't hesitate to reach out.
        
        Best regards,
        The Treasurer Team
        """
        
        return subject, html_content, text_content
    
    @staticmethod
    def payment_reminder_sms(member, amount_due):
        """Payment reminder SMS template"""
        return f"Hi {member.name.split()[0]}! Friendly reminder: ${amount_due:.2f} dues balance remaining. Payment options: Venmo @fraternity-treasurer, Zelle treasurer@fraternity.org, or cash. Questions? Reply to this text."
    
    @staticmethod
    def reimbursement_approved_email(reimbursement, user):
        """Reimbursement approved email template"""
        subject = f"Reimbursement Approved - ${reimbursement.amount:.2f}"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px;">
                <h2 style="color: #27ae60;">✅ Reimbursement Approved</h2>
                
                <p>Great news! Your reimbursement request has been approved.</p>
                
                <div style="background-color: #d5f4e6; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Amount:</strong> ${reimbursement.amount:.2f}</p>
                    <p style="margin: 10px 0 0 0;"><strong>Category:</strong> {reimbursement.category}</p>
                    <p style="margin: 10px 0 0 0;"><strong>Description:</strong> {reimbursement.purpose}</p>
                </div>
                
                <p>Your reimbursement will be processed shortly. You should receive payment within 3-5 business days.</p>
                
                <p>Thank you for your submission!</p>
                
                <p>Best regards,<br>
                The Treasurer Team</p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Reimbursement Approved
        
        Great news! Your reimbursement request has been approved.
        
        Amount: ${reimbursement.amount:.2f}
        Category: {reimbursement.category}
        Description: {reimbursement.purpose}
        
        Your reimbursement will be processed shortly. You should receive payment within 3-5 business days.
        
        Thank you for your submission!
        
        Best regards,
        The Treasurer Team
        """
        
        return subject, html_content, text_content
    
    @staticmethod
    def spending_plan_approved_email(spending_plan, user):
        """Spending plan approved email template"""
        subject = f"Spending Plan Approved - {spending_plan.title}"
        plan_data = spending_plan.get_plan_data()
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px;">
                <h2 style="color: #3498db;">📋 Spending Plan Approved</h2>
                
                <p>Congratulations! Your spending plan has been approved.</p>
                
                <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Plan:</strong> {spending_plan.title}</p>
                    <p style="margin: 10px 0 0 0;"><strong>Category:</strong> {spending_plan.category}</p>
                    <p style="margin: 10px 0 0 0;"><strong>Total Budget:</strong> ${plan_data.get('total_budget', 0):,.2f}</p>
                    <p style="margin: 10px 0 0 0;"><strong>Events:</strong> {len(plan_data.get('events', []))}</p>
                </div>
                
                <p>You can now proceed with your planned activities according to the approved budget. Please remember to:</p>
                <ul>
                    <li>Keep all receipts for reimbursement requests</li>
                    <li>Submit reimbursement requests promptly after expenses</li>
                    <li>Stay within the approved budget amounts</li>
                </ul>
                
                <p>Best regards,<br>
                The Treasurer Team</p>
            </div>
        </body>
        </html>
        """
        
        return subject, html_content, ""

# Notification routes
@notifications_bp.route('/')
@login_required
@permission_required('view_all_data')
def dashboard():
    """Notification management dashboard"""
    
    # Get notification statistics
    recent_notifications = []  # This would come from a notifications log table
    pending_reminders = Member.query.filter(
        Member.dues_amount > 0
    ).count()
    
    return render_template('notifications/dashboard.html',
                         recent_notifications=recent_notifications,
                         pending_reminders=pending_reminders)

@notifications_bp.route('/send-payment-reminders', methods=['POST'])
@login_required
@permission_required('send_reminders')
def send_payment_reminders():
    """Send payment reminders to members with outstanding balances"""
    
    try:
        # Get members with outstanding balances
        members = Member.query.all()
        reminder_count = 0
        error_count = 0
        
        for member in members:
            balance = member.get_balance()
            if balance > 0:  # Member has outstanding balance
                
                # Get user account if linked
                user = User.query.filter_by(member_record=member).first()
                if not user:
                    continue
                
                # Generate email content
                subject, html_content, text_content = NotificationTemplates.payment_reminder_email(
                    member, balance
                )
                
                # Send email if user has email
                if hasattr(user, 'email') and user.email:
                    success = NotificationService.send_email(
                        user.email, subject, html_content, text_content
                    )
                    if success:
                        reminder_count += 1
                    else:
                        error_count += 1
                
                # Send SMS if user prefers SMS and has phone
                if hasattr(user, 'prefers_sms') and user.prefers_sms and hasattr(user, 'phone') and user.phone:
                    sms_message = NotificationTemplates.payment_reminder_sms(member, balance)
                    success = NotificationService.send_sms(user.phone, sms_message)
                    if success:
                        reminder_count += 1
                    else:
                        error_count += 1
        
        return jsonify({
            'success': True,
            'message': f'Payment reminders sent successfully! {reminder_count} sent, {error_count} errors.'
        })
        
    except Exception as e:
        logger.error(f"Error sending payment reminders: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error sending reminders: {str(e)}'
        }), 500

@notifications_bp.route('/test-email', methods=['POST'])
@login_required
@permission_required('view_all_data')
def test_email():
    """Test email configuration"""
    
    try:
        test_email = request.json.get('email', current_user.email if hasattr(current_user, 'email') else '')
        
        if not test_email:
            return jsonify({'success': False, 'message': 'Email address required'}), 400
        
        subject = "Test Email from Fraternity Management System"
        html_content = """
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #2c3e50;">Email Test Successful!</h2>
            <p>This is a test email from your fraternity management system.</p>
            <p>If you received this email, your email configuration is working correctly.</p>
            <p><strong>Timestamp:</strong> """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
        </body>
        </html>
        """
        
        success = NotificationService.send_email(test_email, subject, html_content)
        
        if success:
            return jsonify({'success': True, 'message': f'Test email sent to {test_email}'})
        else:
            return jsonify({'success': False, 'message': 'Failed to send test email'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

# Event handlers for automatic notifications
class NotificationEvents:
    """Event handlers for automatic notifications"""
    
    @staticmethod
    def on_reimbursement_approved(reimbursement):
        """Send notification when reimbursement is approved"""
        try:
            # Get the user who submitted the reimbursement
            user = User.query.get(reimbursement.requested_by)
            if not user:
                return
            
            # Generate and send email
            subject, html_content, text_content = NotificationTemplates.reimbursement_approved_email(
                reimbursement, user
            )
            
            if hasattr(user, 'email') and user.email:
                NotificationService.send_email(user.email, subject, html_content, text_content)
            
            logger.info(f"Reimbursement approval notification sent to user {user.id}")
            
        except Exception as e:
            logger.error(f"Error sending reimbursement approval notification: {str(e)}")
    
    @staticmethod
    def on_spending_plan_approved(spending_plan):
        """Send notification when spending plan is approved"""
        try:
            # Get the user who created the spending plan
            user = User.query.get(spending_plan.created_by)
            if not user:
                return
            
            # Generate and send email
            subject, html_content, _ = NotificationTemplates.spending_plan_approved_email(
                spending_plan, user
            )
            
            if hasattr(user, 'email') and user.email:
                NotificationService.send_email(user.email, subject, html_content)
            
            logger.info(f"Spending plan approval notification sent to user {user.id}")
            
        except Exception as e:
            logger.error(f"Error sending spending plan approval notification: {str(e)}")

# Utility functions for background tasks
def send_weekly_payment_reminders():
    """Background task to send weekly payment reminders"""
    try:
        members = Member.query.all()
        reminder_count = 0
        
        for member in members:
            balance = member.get_balance()
            if balance > 0:
                user = User.query.filter_by(member_record=member).first()
                if user and hasattr(user, 'email') and user.email:
                    subject, html_content, text_content = NotificationTemplates.payment_reminder_email(
                        member, balance
                    )
                    success = NotificationService.send_email(
                        user.email, subject, html_content, text_content
                    )
                    if success:
                        reminder_count += 1
        
        logger.info(f"Weekly payment reminders sent: {reminder_count}")
        return reminder_count
        
    except Exception as e:
        logger.error(f"Error in weekly payment reminders: {str(e)}")
        return 0