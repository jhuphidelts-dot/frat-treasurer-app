#!/bin/bash

# Fraternity Treasurer App - GitHub Deployment Script
echo "🏛️ Fraternity Treasurer App - GitHub Deployment"
echo "================================================"

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Please install Git first."
    echo "Visit: https://git-scm.com/downloads"
    exit 1
fi

# Check if we're already in a git repository
if [ -d ".git" ]; then
    echo "✅ Git repository already exists"
else
    echo "🔧 Initializing Git repository..."
    git init
    echo "✅ Git repository initialized"
fi

# Create .gitignore if it doesn't exist
if [ ! -f ".gitignore" ]; then
    echo "📝 Creating .gitignore file..."
    cat > .gitignore << EOF
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Sensitive files
.env
service_account.json
*.key
*.pem

# Temporary files
*.tmp
*.temp
*.log

# Data backups (keep data/ folder but ignore backups)
data/backups/
*.backup
*.bak
EOF
    echo "✅ .gitignore created"
fi

# Add all files
echo "📦 Adding files to git..."
git add .

# Check if there are changes to commit
if git diff --cached --quiet; then
    echo "ℹ️  No changes to commit"
else
    # Commit changes
    echo "💾 Creating initial commit..."
    git commit -m "Initial commit: Fraternity Treasurer App ready for deployment

Features:
- Complete member management system
- Transaction tracking and budget management  
- Email/SMS notification system
- Data export in multiple formats (CSV, Excel, PDF, JSON)
- Treasurer handover system
- Google Sheets integration
- Enhanced dashboard with financial insights
- Automated reminders and scheduling
- Compressed data storage
- Replit deployment ready

Ready for production use!"
    echo "✅ Initial commit created"
fi

echo ""
echo "🌐 Next Steps for GitHub:"
echo "1. Go to https://github.com/new"
echo "2. Create a new repository named 'frat-treasurer-app'"
echo "3. DO NOT initialize with README, .gitignore, or license"
echo "4. Copy the repository URL (https://github.com/yourusername/frat-treasurer-app.git)"
echo ""
echo "5. Run these commands:"
echo "   git remote add origin YOUR_REPOSITORY_URL"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "🚀 After GitHub setup:"
echo "1. Go to https://replit.com"
echo "2. Click 'Create Repl' → 'Import from GitHub'"
echo "3. Select your repository"
echo "4. Click 'Import from GitHub'"
echo "5. Click 'Run' - your app will be live!"
echo ""
echo "📋 Default Login:"
echo "   Username: admin"
echo "   Password: admin123"
echo "   (Change these after deployment!)"
echo ""
echo "✅ Your app is ready for deployment!"