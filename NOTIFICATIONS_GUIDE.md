# 📧 Email & SMS Notification System Guide

## Overview

The fraternity treasurer app now includes a comprehensive notification system that automatically sends email and SMS notifications for important events like:

- **Payment Reminders** - Automated reminders for members with outstanding dues
- **Reimbursement Approvals** - Instant notifications when requests are approved
- **Spending Plan Approvals** - Notifications when spending plans are approved
- **Custom Notifications** - Treasurer can send targeted reminders

## ✨ Features

### 🔔 Automatic Notifications
- **Payment Reminders**: Sent to members with outstanding balances
- **Approval Notifications**: Sent when reimbursements/spending plans are approved
- **Smart Delivery**: Uses email or SMS based on user preferences

### 📧 Email Support
- **Professional Templates**: Beautiful HTML emails with fraternity branding
- **SMTP Integration**: Works with Gmail, Outlook, and other email providers
- **Delivery Tracking**: Monitor sent emails and delivery status

### 📱 SMS Support
- **Twilio Integration**: Reliable SMS delivery through Twilio
- **Free Email-to-SMS**: Fallback option using carrier gateways (Verizon, AT&T, etc.)
- **Phone Number Formats**: Supports various formats (+1234567890, 234-567-8901, etc.)

### 🎛️ Management Dashboard
- **Configuration Status**: Real-time status of email/SMS settings
- **Bulk Reminders**: Send reminders to all members with one click
- **Test Features**: Test email configuration with sample messages
- **Activity Logs**: View recent notification activity

## 🚀 Setup Instructions

### 1. Email Configuration (Required)

#### Option A: Gmail (Recommended)
1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate App Password**:
   - Go to Google Account → Security
   - Under "Signing in to Google", click "App passwords"
   - Generate password for "Mail"
3. **Set Environment Variables**:
   ```bash
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-gmail@gmail.com
   SMTP_PASSWORD=your-16-character-app-password
   FROM_EMAIL=treasurer@yourfraternity.org
   ```

#### Option B: Other Email Providers
- **Outlook/Hotmail**: smtp-mail.outlook.com, port 587
- **Yahoo**: smtp.mail.yahoo.com, port 587
- **Custom SMTP**: Contact your email provider for settings

### 2. SMS Configuration (Optional)

#### Option A: Twilio (Recommended for Reliability)
1. **Sign up** at [twilio.com](https://www.twilio.com)
2. **Get credentials** from your Twilio Console
3. **Set environment variables**:
   ```bash
   TWILIO_SID=your-account-sid
   TWILIO_TOKEN=your-auth-token
   TWILIO_PHONE=your-twilio-phone-number
   ```

#### Option B: Free Email-to-SMS (Less Reliable)
- Uses email-to-SMS gateways (built-in, no extra setup)
- Only requires email configuration
- Supports major carriers automatically

### 3. Environment File Setup

1. **Copy template**: `cp .env.template .env`
2. **Edit .env file** with your credentials
3. **Test configuration** in the app

## 📋 Usage Guide

### Accessing the Notification Dashboard
1. Log in to the treasurer app
2. Click **"Notifications"** in the navigation bar
3. View status cards and configuration

### Sending Payment Reminders
1. **Automatic**: Set up weekly reminders in configuration
2. **Manual Bulk**: Notifications Dashboard → "Send Payment Reminders"
3. **Selective**: Dashboard → "Selective Reminders" → Choose specific members

### Testing Your Setup
1. Go to Notifications Dashboard
2. Click **"Test Email Configuration"**
3. Enter your email address
4. Check for test email delivery

### Managing User Preferences
- **Member Setup**: Edit member → Set contact type (email/phone)
- **SMS Preference**: Members can request SMS notifications
- **Contact Updates**: Keep member contact info current

## 🛠️ Troubleshooting

### Email Not Sending
1. **Check Credentials**: Verify SMTP username/password
2. **App Password**: Use App Password, not regular password (Gmail)
3. **Firewall**: Ensure port 587 is not blocked
4. **Test Email**: Use the built-in test feature

### SMS Not Delivering
1. **Phone Format**: Use +1234567890 format
2. **Carrier Gateway**: Try different carriers for free SMS
3. **Twilio Setup**: Verify Twilio credentials if using paid SMS
4. **Phone Verification**: Ensure phone numbers are correct

### Common Error Messages

| Error | Solution |
|-------|----------|
| "SMTP credentials not configured" | Set SMTP_USERNAME and SMTP_PASSWORD |
| "Authentication failed" | Use App Password, not account password |
| "SMS not sent - Twilio library not installed" | Run: `pip install twilio` |
| "Email not configured" | Check .env file exists with SMTP settings |

## 📊 Notification Templates

### Payment Reminder Email
- **Subject**: "Payment Reminder - $XX.XX Due"
- **Content**: Professional HTML template with:
  - Member name and balance
  - Payment methods (Venmo, Zelle, Cash)
  - Contact information
  - Fraternity branding

### Reimbursement Approval
- **Subject**: "Reimbursement Approved - $XX.XX"
- **Content**: Approval confirmation with:
  - Approved amount and category
  - Processing timeline (3-5 business days)
  - Receipt information

### Spending Plan Approval
- **Subject**: "Spending Plan Approved - [Plan Name]"
- **Content**: Approval details with:
  - Plan summary and total budget
  - Event count and timeline
  - Reimbursement reminders

## 🔒 Security & Privacy

### Data Protection
- **Environment Variables**: Credentials stored securely in .env
- **No Plaintext Storage**: Passwords never stored in database
- **Secure Transmission**: All emails/SMS sent over encrypted connections

### Permission System
- **Role-Based Access**: Only treasurer and authorized officers can send notifications
- **Audit Trail**: All notifications logged with timestamps
- **Member Privacy**: Contact information protected by user permissions

## 🎯 Advanced Features

### Custom Notification Events
Add custom notifications in your code:
```python
from notifications import NotificationEvents

# Trigger custom notification
NotificationEvents.on_reimbursement_approved(reimbursement)
```

### Bulk Operations
- **Weekly Reminders**: Automated reminder schedule
- **Semester Transitions**: Bulk notifications for new semester
- **Event Announcements**: Send notifications for fraternity events

### Integration with Other Systems
- **Google Sheets**: Export notification logs
- **Member Portal**: Brother notifications and preferences
- **Financial Reports**: Include notification statistics

## 🆘 Support

### Getting Help
1. **AI Assistant**: Use the built-in AI assistant for troubleshooting
2. **Documentation**: Refer to this guide and inline help text
3. **Test Features**: Use built-in test tools to diagnose issues

### Common Setup Issues
- **Gmail Security**: Must use App Passwords, not account passwords
- **Phone Numbers**: Use consistent formatting (+1234567890)
- **Environment File**: Ensure .env file is in the correct directory
- **Permissions**: Check user roles for notification sending

## 📈 Best Practices

### Email Setup
- ✅ Use dedicated treasurer Gmail account
- ✅ Set up professional "From" email address
- ✅ Test with multiple recipients
- ✅ Monitor delivery rates

### SMS Setup
- ✅ Use Twilio for important notifications
- ✅ Keep phone numbers updated
- ✅ Respect member communication preferences
- ✅ Test with different carriers

### Member Management
- ✅ Verify contact information regularly
- ✅ Ask members for preferred notification method
- ✅ Update contacts when members change numbers/emails
- ✅ Honor opt-out requests

---

## 🎉 You're All Set!

The notification system is now ready to help streamline communication with your fraternity members. Regular reminders and instant approval notifications will help keep everyone informed and ensure timely dues collection.

**Need more help?** Use the AI Assistant in the app or refer to the troubleshooting section above.