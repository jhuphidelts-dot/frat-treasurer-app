# 🚀 Replit Deployment Guide

This guide will walk you through deploying your Fraternity Treasurer App on Replit for 24/7 hosting.

## 📋 Prerequisites

1. **GitHub Account** (to store your code)
2. **Replit Account** (free at https://replit.com)
3. **Your app folder ready**

## 🔧 Step 1: Prepare Your Code for GitHub

### Option A: Using Git Command Line

```bash
# Initialize git repository (if not already done)
cd /path/to/your/frat-treasurer-app
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Fraternity Treasurer App ready for deployment"

# Add your GitHub repository (create one first on GitHub)
git remote add origin https://github.com/yourusername/frat-treasurer-app.git

# Push to GitHub
git push -u origin main
```

### Option B: Using GitHub Desktop
1. Download GitHub Desktop
2. Click "Add an Existing Repository from your Hard Drive"
3. Select your `frat-treasurer-app` folder
4. Publish repository to GitHub

## 🌐 Step 2: Deploy to Replit

1. **Create Replit Account**
   - Go to https://replit.com
   - Sign up with GitHub (recommended)

2. **Import Your Repository**
   - Click "Create Repl"
   - Choose "Import from GitHub"
   - Select your `frat-treasurer-app` repository
   - Click "Import from GitHub"

3. **Configure the Repl**
   - Replit will automatically detect it's a Python project
   - It will read the `.replit` file for configuration
   - Dependencies from `requirements.txt` will be installed automatically

4. **Run Your App**
   - Click the "Run" button
   - Your app will start on the URL shown (usually `https://yourproject.yourusername.repl.co`)
   - Login with `admin` / `admin123`

## ⚙️ Step 3: Configure for Production

### Environment Variables (Important!)
1. In your Repl, go to the "Secrets" tab (🔒 icon in sidebar)
2. Add these environment variables:

```
EMAIL_USER=your_gmail@gmail.com
EMAIL_PASS=your_gmail_app_password
TWILIO_ACCOUNT_SID=your_twilio_sid (optional)
TWILIO_AUTH_TOKEN=your_twilio_token (optional)
SECRET_KEY=your_flask_secret_key
```

### Update Your App for Production
The app is already configured to work with Replit's environment:
- `main.py` uses Replit's PORT environment variable
- `.replit` configuration file is set up
- `requirements.txt` includes all dependencies

## 🔒 Step 4: Security Setup

1. **Change Default Password**
   - Login to your deployed app
   - Go to user menu → Change Password
   - Set a strong password

2. **Configure Email/SMS**
   - Go to Treasurer Setup
   - Add your Gmail App Password (not regular password)
   - Test notifications

## 💰 Step 5: Replit Hosting Options

### Free Tier
- ✅ Perfect for testing and small fraternities
- ⚠️ App sleeps after inactivity (spins up in ~10 seconds)
- ✅ Includes everything you need

### Always On ($5/month per Repl)
- ✅ 24/7 uptime
- ✅ No sleep/wake delays
- ✅ Perfect for active fraternities
- ✅ Custom domain support

### Replit Core ($20/month)
- ✅ Multiple Always On repls
- ✅ More computing power
- ✅ Priority support

## 📊 Step 6: Data Management

### Backups
Your Replit automatically backs up your code, but for data:
1. Use the built-in "Export to Google Sheets" feature monthly
2. Download the `data/` folder occasionally as backup
3. Your GitHub repository serves as code backup

### Database
- The app uses JSON files stored in the `data/` folder
- These persist across Repl restarts
- Use the "Optimize Storage" feature to manage size

## 🔧 Troubleshooting

### App Won't Start
```bash
# Check logs in Replit console
# Common issues:
1. Missing environment variables → Add in Secrets tab
2. Port conflicts → Replit handles this automatically
3. Dependencies → Check if requirements.txt installed properly
```

### Performance Issues
```bash
# Check if your Repl needs Always On:
1. High traffic fraternity → Consider Always On
2. Frequent access → Always On recommended  
3. Critical deadline periods → Always On essential
```

### Data Issues
```bash
# Access Replit Shell to check data:
ls -la data/
# Your JSON files should be there

# If data is missing, restore from backup
```

## 🌟 Advanced Features

### Custom Domain
With Always On, you can:
1. Buy a domain (e.g., `yourfrattreasurer.com`)
2. Point it to your Repl
3. Professional URL for your fraternity

### Scaling
As your fraternity grows:
- Free tier: Up to ~50 active members
- Always On: Unlimited members
- Multiple treasurers can access simultaneously

## 📞 Support Resources

1. **Replit Documentation**: https://docs.replit.com
2. **GitHub Issues**: Create issues in your repository
3. **Replit Community**: Ask questions in Replit Discord/forums

## ✅ Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Replit account created
- [ ] Repository imported to Replit
- [ ] App runs successfully
- [ ] Environment variables configured
- [ ] Default password changed
- [ ] Email notifications configured
- [ ] SMS notifications tested (optional)
- [ ] First data backup completed
- [ ] Always On considered (if needed)

## 🎉 You're Live!

Your Fraternity Treasurer App is now:
- ✅ Accessible from anywhere
- ✅ Automatically backed up
- ✅ Scalable as needed
- ✅ Professional and reliable

**Your app URL**: `https://yourproject.yourusername.repl.co`

Remember to share this URL with other fraternity officers who need access!

---

**Need help?** The Replit community is very helpful, and this app includes comprehensive error handling and logging to help diagnose issues.