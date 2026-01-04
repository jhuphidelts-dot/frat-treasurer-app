# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Quick Start Commands

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.template .env
# Edit .env with your credentials

# Run application locally
python3 app.py
# OR use the GUI launcher
./Start\ Treasurer\ App.command
```

### Database Operations
```bash
# Check database status
python3 database.py status

# Initialize fresh database
python3 database.py init

# Create a treasurer user
python3 database.py create-treasurer <phone> <first_name> <last_name> <password>
```

### Testing & Development
```bash
# Run with debug mode
FLASK_DEBUG=True python3 app.py

# Check Python dependencies
python3 -c "import pkg_resources; pkg_resources.require(open('requirements.txt').read().splitlines())"

# Test notifications (within app)
# Use "Treasurer Setup" → "Test Email/SMS" in the web interface
```

### Deployment
```bash
# Deploy to GitHub
./deploy_to_github.sh

# Production deployment (Render.com)
# Uses render.yaml configuration
# Build: pip install -r requirements.txt
# Start: python app.py

# Railway deployment
# Uses railway.json configuration
```

## Architecture Overview

This Flask application has evolved from a simple JSON-based system to support both legacy file storage and modern SQLAlchemy database patterns.

### Core Components

**Main Application (`app.py`)**
- 1,855 lines containing the primary Flask routes and business logic
- Contains the `TreasurerApp` class that handles all core functionality
- Supports both JSON file storage (legacy) and SQLAlchemy models (newer)

**Database Layer**
```
Legacy Flow:       JSON Files → TreasurerApp → Flask Routes
Modern Flow:       SQLAlchemy → models.py → Flask Routes
Migration Tool:    database.py handles both patterns
```

**Modular Services**
- `notifications.py`: Email/SMS notification system via Flask Blueprint
- `export_system.py`: Multi-format data export (CSV, Excel, PDF, JSON)
- `models.py`: SQLAlchemy ORM definitions for modern database schema
- `auth.py` & `rbac.py`: Authentication and role-based access control

### Data Flow Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Frontend  │────│  Flask Routes    │────│  Business Logic │
│   (Templates)   │    │  (app.py)        │    │  (TreasurerApp) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                              ┌─────────────────────────┼─────────────────────────┐
                              │                         │                         │
                    ┌─────────▼────────┐    ┌──────────▼────────┐    ┌────────▼────────┐
                    │  JSON Storage    │    │  SQLAlchemy ORM   │    │  Service Modules │
                    │  (data/*.json)   │    │  (models.py)      │    │  - notifications │
                    │  - Compressed    │    │  - Users/Roles    │    │  - export_system │
                    │  - Legacy        │    │  - Modern Schema  │    │  - reports       │
                    └──────────────────┘    └───────────────────┘    └─────────────────┘
```

### Key Architectural Patterns

**Dual Storage Pattern**: The application maintains backward compatibility by supporting both JSON file storage (legacy) and SQLAlchemy database models (modern). The `database.py` module provides migration utilities.

**Blueprint-Based Modularity**: 
- Core routes in `app.py`
- Notifications module as Flask Blueprint (`notifications.py`)
- Export system as Flask Blueprint (`export_system.py`)

**Dataclass-to-ORM Evolution**: Legacy code uses Python dataclasses (`Member`, `Transaction`, `Semester`), while newer code uses SQLAlchemy models in `models.py`.

## Development Workflows

### Adding New Features
1. **Legacy Mode**: Extend the `TreasurerApp` class in `app.py`
2. **Modern Mode**: Create SQLAlchemy models in `models.py` and routes in blueprints
3. **Consider both patterns** for backward compatibility

### Database Migrations
The application supports manual migration between JSON and SQLAlchemy:
```bash
# Check current system
python3 database.py status

# Migrate from JSON to SQLAlchemy
python3 migrate_data.py
```

### Notification System Development
All notification logic is centralized in `notifications.py`:
- Email templates in `NotificationTemplates` class
- SMS support via Twilio and email-to-SMS gateways
- Configuration via environment variables or treasurer setup

### Export System Extension
The `export_system.py` module supports multiple formats:
- CSV, JSON (built-in)
- Excel (requires `xlsxwriter`)
- PDF (requires `reportlab`)

## Configuration & Environment

### Python Version
- **Required**: Python 3.8+
- **Tested**: Python 3.10.0+
- **Production**: Python 3.11.0 (as per render.yaml)

### Environment Variables
Copy `.env.template` to `.env` and configure:

```bash
# Essential Configuration
SECRET_KEY=your-secret-key-here
PORT=8080
DEBUG=False

# Email Notifications (Gmail recommended)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-gmail@gmail.com
SMTP_PASSWORD=your-app-password  # Not regular password!

# SMS Notifications (Optional - Twilio)
TWILIO_SID=your-twilio-account-sid
TWILIO_TOKEN=your-twilio-auth-token
TWILIO_PHONE=+1234567890

# Database (for SQLAlchemy mode)
DATABASE_URL=sqlite:///fraternity.db  # Development
DATABASE_URL=postgresql://...         # Production
```

### Application Modes

**JSON File Mode (Legacy)**:
- Default behavior when no database configuration
- Data stored in `data/` directory with automatic compression
- Members, transactions, budgets stored as JSON files

**SQLAlchemy Mode (Modern)**:
- Activated when `DATABASE_URL` is configured
- Full relational database with proper constraints
- User authentication and role-based access control

### Directory Structure
```
frat-treasurer-app/
├── app.py                 # Main application (1,855 lines)
├── models.py              # SQLAlchemy ORM models
├── database.py            # Database utilities and migration
├── notifications.py       # Email/SMS system (Blueprint)
├── export_system.py       # Data export utilities (Blueprint)
├── data/                  # JSON storage (legacy mode)
│   ├── members.json.gz    # Compressed member data
│   ├── transactions.json.gz
│   └── treasurer_config.json
├── templates/             # Jinja2 HTML templates
│   ├── dashboards/        # Role-specific dashboards
│   ├── notifications/     # Notification management
│   └── export/           # Export interfaces
└── static/               # CSS/JS assets
```

### Treasurer Handover System
The application includes a complete handover workflow:
1. **Archive current semester**: `semester_management.html`
2. **Clear treasurer credentials**: While preserving member data
3. **Generate setup instructions**: For incoming treasurer
4. **Data continuity**: All financial data is preserved

## Important Development Notes

### Data Storage Optimization
- Files >5KB are automatically compressed with gzip
- Use "Treasurer Setup" → "Optimize Storage" for manual cleanup
- Achieves ~87% compression on typical datasets

### Authentication Patterns
- **Legacy**: Simple admin/password in JSON files
- **Modern**: Full user accounts with Flask-Login and role-based permissions
- **Migration**: `database.py create-treasurer` for initial SQLAlchemy setup

### Testing Notifications
- Use the web interface: "Treasurer Setup" → "Test Email/SMS"
- Gmail requires App Passwords (not regular password)
- SMS supports both Twilio and free email-to-SMS gateways

### Deployment Considerations
- **Local Development**: Uses `python3 app.py` on port 8080
- **Production**: Gunicorn-compatible via `render.yaml` or `railway.json`
- **Data Backup**: Export to Google Sheets monthly (built-in feature)

## Reference Documentation

- **README.md**: User-facing setup and feature documentation
- **CODEBASE_ANALYSIS.md**: Technical debt analysis and migration strategy
- **PHASE_*_COMPLETE.md**: Development phase documentation
- **NOTIFICATIONS_GUIDE.md**: Detailed notification setup instructions

For specific deployment instructions, see `DEPLOYMENT.md` and `QUICK_DEPLOY.md`.