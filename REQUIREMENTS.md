# Fraternity Management System - Technical Requirements

## 🎯 **Project Vision**
Transform the current local Flask treasurer app into a cloud-hosted, multi-role fraternity management platform accessible to all brothers with role-based permissions and workflows.

## 👥 **User Roles & Permissions**

### **1. Brother (Basic Member)**
- **Dashboard**: Personal dues balance, payment history, upcoming payments
- **Actions**: 
  - Suggest payment plans (approval workflow with treasurer)
  - View personal reimbursement request status
- **Restrictions**: Cannot view other members' data or budgets

### **2. Treasurer (Full Admin)**
- **Dashboard**: Complete financial overview, all member data
- **Actions**: Everything current app does PLUS:
  - Approve/modify payment plan suggestions
  - Approve/reject reimbursement requests
  - Link new accounts to existing member records
  - Manage user roles and account approvals
  - Approve new user registrations

### **3. President**
- **Dashboard**: Read-only view of all treasurer data
- **Actions**: View all budgets, spending, and member information
- **Restrictions**: Cannot edit/modify anything

### **4. Vice President**
- **Dashboard**: View all budgets with edit access to specific categories
- **Actions**: Edit social, phi ed, recruitment, brotherhood budgets only
- **Restrictions**: Cannot edit executive, philanthropy, housing budgets

### **5. Social Chair**
- **Dashboard**: Social budget overview and transaction history
- **Actions**:
  - Add social expenses
  - Submit reimbursement requests
  - Create/edit semester spending plans for social events
- **Budget Access**: Social category only

### **6. Phi Ed Chair**
- **Dashboard**: Phi Ed budget overview and transaction history
- **Actions**: Same as Social Chair but for Phi Ed budget
- **Budget Access**: Phi ED category only

### **7. Recruitment Chair**
- **Dashboard**: Recruitment budget overview
- **Actions**: Same as Social Chair but for Recruitment budget
- **Budget Access**: Recruitment category only

### **8. Brotherhood Chair**
- **Dashboard**: Brotherhood budget overview
- **Actions**: Same as Social Chair but for Brotherhood budget
- **Budget Access**: Brotherhood category only

## 🔄 **Key Workflows**

### **A. Payment Plan Suggestion Workflow**
1. Brother submits payment plan suggestion
2. System notifies treasurer
3. Treasurer can:
   - **Approve**: Plan becomes active
   - **Modify**: Send counter-proposal to brother
4. If modified, brother can accept/request changes
5. Final approval activates the plan

### **B. Reimbursement Request Workflow**
1. Officer submits request (amount, purpose, receipt)
2. Status: "Pending Review"
3. Treasurer approves/rejects with optional notes
4. Status updates to "Approved/Rejected"
5. If approved, treasurer records payment
6. Email notifications at each status change

### **C. Semester Spending Plan Workflow**
1. Officers submit plans at semester start
2. Plans editable throughout semester
3. Treasurer can view all plans for budget oversight
4. Version history maintained

### **D. User Registration & Account Linking**
1. New user registers with phone + password
2. Account status: "Pending Approval"
3. Treasurer reviews and can:
   - **Approve**: Create new member record OR
   - **Link**: Connect to existing member data
4. Account activated with appropriate role

## 🗄️ **Database Schema Design**

### **Users Table**
```sql
- id (Primary Key)
- phone (Unique)
- password_hash
- first_name
- last_name
- email (Optional)
- status (pending, active, suspended)
- created_at
- approved_by (Foreign Key to Users)
- approved_at
```

### **Roles Table**
```sql
- id (Primary Key)
- name (brother, treasurer, president, etc.)
- permissions (JSON field)
```

### **User_Roles Table** (Many-to-Many)
```sql
- user_id (Foreign Key)
- role_id (Foreign Key)
- assigned_by (Foreign Key to Users)
- assigned_at
```

### **Members Table** (Enhanced from current)
```sql
- id (Primary Key)
- user_id (Foreign Key, nullable for legacy data)
- name
- contact
- contact_type
- dues_amount
- payment_plan
- custom_schedule (JSON)
- semester_id
- created_at
```

### **Payment_Plan_Suggestions Table** (New)
```sql
- id (Primary Key)
- member_id (Foreign Key)
- suggested_by (Foreign Key to Users)
- original_plan (JSON)
- suggested_plan (JSON)
- treasurer_modified_plan (JSON, nullable)
- status (pending, approved, modified, rejected)
- notes
- created_at
- reviewed_at
```

### **Reimbursement_Requests Table** (New)
```sql
- id (Primary Key)
- requested_by (Foreign Key to Users)
- category
- amount
- purpose
- receipt_url (Optional)
- status (pending, approved, rejected)
- reviewer_notes
- reviewed_by (Foreign Key to Users)
- reviewed_at
- created_at
```

### **Spending_Plans Table** (New)
```sql
- id (Primary Key)
- created_by (Foreign Key to Users)
- category
- semester_id
- plan_data (JSON - events, amounts, timeline)
- version
- is_active
- created_at
- updated_at
```

### **Transactions Table** (Enhanced)
```sql
- id (Primary Key)
- date
- category
- description
- amount
- type (income/expense)
- created_by (Foreign Key to Users)
- related_request_id (Foreign Key to Reimbursement_Requests, nullable)
- semester_id
- created_at
```

## 🏗️ **Technical Stack**

### **Backend**
- **Framework**: Flask with Flask-SQLAlchemy
- **Database**: 
  - Development: SQLite
  - Production: PostgreSQL (Render.com free tier)
- **Authentication**: Flask-Login + werkzeug password hashing
- **API**: RESTful endpoints for AJAX interactions

### **Frontend**
- **Framework**: Jinja2 templates (server-side rendering)
- **CSS**: Bootstrap 5 + custom fraternity theming
- **JavaScript**: Vanilla JS + Chart.js for visualizations
- **Responsive**: Mobile-first design

### **Hosting & Infrastructure**
- **Platform**: Render.com (free tier)
  - Free PostgreSQL database (1GB)
  - Free web service (750 hours/month)
  - Custom subdomain: yourfrat.onrender.com
- **File Storage**: Local filesystem (receipts as base64 in DB for free tier)
- **Email**: Keep existing SMTP integration
- **Environment**: Environment variables for secrets

### **Development Tools**
- **Version Control**: Git + GitHub
- **Testing**: pytest + Flask-Testing
- **Linting**: flake8 + black
- **CI/CD**: GitHub Actions

## 📱 **User Experience Design**

### **Navigation Structure**
```
Role-Based Navigation:
├── Brother: Dashboard, Payment Plans, Profile
├── Officers: Dashboard, Budget Management, Reimbursements, Spending Plans
├── President: Overview, All Budgets, Reports
├── VP: Overview, Select Budgets, Reports  
└── Treasurer: Full Access (current features + approvals)
```

### **Dashboard Layouts**
- **Brother**: Personal financial summary + quick actions
- **Officers**: Budget overview + category-specific management
- **President/VP**: High-level financial overview + drill-down
- **Treasurer**: Comprehensive admin dashboard

## 🔐 **Security Requirements**

1. **Password Policy**: Minimum 8 characters
2. **Session Management**: Secure session cookies, auto-logout
3. **Role Enforcement**: Server-side permission checks on all endpoints
4. **Input Validation**: Sanitize all user inputs
5. **HTTPS**: Required in production
6. **Rate Limiting**: Prevent abuse of registration/login endpoints

## 📊 **Data Migration Strategy**

1. **Backup**: Create backup of existing JSON files
2. **Schema Creation**: Build new database schema
3. **Data Import**: 
   - Import existing members → Members table
   - Import transactions → Transactions table  
   - Import budget data → Budget tables
4. **User Creation**: Create initial treasurer account
5. **Testing**: Verify all existing features work

## 🚀 **Deployment Pipeline**

1. **Development**: Local SQLite database
2. **Testing**: Automated tests on GitHub Actions
3. **Production**: Render.com with PostgreSQL
4. **Monitoring**: Basic logging and error tracking

## 📋 **Success Metrics**

- All existing treasurer features preserved
- All 7 user roles implemented with correct permissions
- Payment plan suggestion workflow operational
- Reimbursement request system functional
- Mobile-responsive design
- Zero-cost hosting solution deployed
- User documentation complete

---

**Next Steps**: Move to Phase 2 - Database Design & Migration Strategy