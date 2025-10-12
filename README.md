# 🏛️ Fraternity Treasurer App

A comprehensive financial management system designed for fraternity treasurers to manage dues, transactions, budgets, and member communications.

## 🚀 Quick Start

### For Current Users
1. Double-click `Start Treasurer App.command` to launch the app
2. Open your browser to `http://127.0.0.1:8080`
3. Login with username: `admin` and password: `admin123`

### For New Treasurers (Handover Setup)
1. Receive the app folder from the previous treasurer
2. Follow the Quick Start steps above
3. Go to **Treasurer Setup** in the user menu to configure your credentials
4. Change the admin password in **Change Password**

## 📋 Current Features (Fully Working)

### **Member Management**
- Add/edit/remove fraternity members
- Bulk import members from text/spreadsheet data
- Automatic contact type detection (email vs phone)
- Custom payment schedules for each member
- Individual member details and payment history

### **Payment Processing**
- Record payments with multiple methods (Zelle, Venmo, Cash, etc.)
- Automatic balance calculations
- Payment schedule tracking
- Dues collection summary with collection rates

### **Transaction Management**
- Add/edit/remove expenses and income
- Categorized transactions (Executive, Social, Philanthropy, etc.)
- Comprehensive transaction history
- Budget vs actual spending tracking

### **Communication System**
- **Email notifications** (Gmail SMTP) ✅ WORKING
- **SMS notifications** (Free email-to-SMS gateways + Twilio) ✅ WORKING
- Selective reminders to specific members ✅ WORKING
- Automated reminder scheduling
- Overdue payment notifications

### **Treasurer Handover System** ⭐ NEW
- **Clear treasurer-specific credentials** while preserving data
- **Archive current semester** automatically  
- **Generate setup instructions** for new treasurer
- **Preserve all member data**, transactions, and budgets

## 🔧 Setup & Configuration

### Environment Setup

1. **Email Configuration (Required for notifications)**
   - Get Gmail App Password (not regular password)
   - Go to **Treasurer Setup** → Email Configuration
   - Enter Gmail username and app password

2. **SMS Configuration (Optional)**
   - **Free Option**: Uses email-to-SMS gateways
   - **Premium Option**: Configure Twilio credentials
   - Supports major carriers (Verizon, AT&T, T-Mobile, etc.)

## 🔄 Treasurer Handover Process

### For Outgoing Treasurer:
1. Complete all pending transactions
2. Collect/record all outstanding dues  
3. Review budget and expenses
4. Export data to Google Sheets (backup)
5. Go to **Treasurer Setup** → User Menu → **Handover to New Treasurer**
6. Complete handover checklist
7. Click **Complete Handover**
8. Provide setup instructions to new treasurer

### For Incoming Treasurer:
1. Receive app folder from previous treasurer
2. Launch app using `Start Treasurer App.command`
3. Login with `admin` / `admin123`
4. Go to **Treasurer Setup** (in user dropdown menu)
5. Configure your personal information
6. Set up email/SMS credentials
7. Change admin password
8. Create new semester if needed

## 📁 File Structure

```
frat-treasurer-app/
├── app.py                          # Main application
├── Start Treasurer App.command     # Double-click launcher
├── requirements.txt                # Python dependencies
├── .env                           # Environment variables
├── README.md                      # This file
├── data/                          # Data storage
│   ├── members.json               # Member information
│   ├── transactions.json          # Financial transactions
│   ├── budget.json               # Budget limits
│   ├── semesters.json            # Semester data (NEW)
│   ├── treasurer_config.json     # Treasurer settings (NEW)
│   └── users.json                # User accounts
├── templates/                     # Web interface
│   ├── index.html                # Dashboard
│   ├── treasurer_setup.html      # Configuration (NEW)
│   ├── handover_treasurer.html   # Handover process (NEW)
│   └── [other templates]
└── service_account.json          # Google credentials (optional)
```

## 💡 Tips & Best Practices

### Data Backup
- Export to Google Sheets monthly
- Keep local backups of the `data/` folder
- Test email/SMS notifications after setup

### Member Management
- Use bulk import for large member lists
- Set up custom payment schedules for payment plans
- Use selective reminders for overdue members

### Communication Testing
- Send test reminders to yourself first
- Verify Gmail App Password works
- Check phone carrier compatibility for SMS

### Storage Optimization ⚡ NEW
- App automatically compresses large data files (>5KB)
- Use **Treasurer Setup** → **Optimize Storage** for manual cleanup
- Removes temporary files (.DS_Store, __pycache__, test files)
- **87% smaller data files** with gzip compression

## 📞 Troubleshooting

### App Won't Start
- Make sure Python 3 is installed
- Check that port 8080 isn't in use
- Try restarting your computer

### Notifications Not Working
- Verify email configuration in **Treasurer Setup**
- Check Gmail App Password is correct (not regular password)
- Test with your own phone/email first

### Data Issues
- Check the `data/` folder exists
- Ensure JSON files aren't corrupted
- Restore from backup if needed

## 🔒 Security Notes

- **Change default admin password** immediately
- **Use Gmail App Passwords**, not regular passwords
- **Keep backups** of all data before major changes
- **Never share** your treasurer configuration file

---

**Need Help?** The app includes detailed setup instructions and troubleshooting guides. Contact your previous treasurer for additional assistance.
