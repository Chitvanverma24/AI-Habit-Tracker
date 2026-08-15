🎯 AI Habit Tracker

AI-powered habit tracking platform for building consistency through data, insights, and personalized coaching.

AI Habit Tracker is a production-oriented Streamlit application combining habit management, progress analytics, journaling, achievements, AI coaching, secure authentication, and license-based access.

✨ Features

👤 User Experience

Secure account creation and login

License activation

Password reset

Personal profile

Habit creation and management

Daily completion tracking

Streak and completion-rate analytics

Recent activity

Personal journal

Achievements

AI Coach insights

🔑 License Management

Built for one-time digital product distribution.

Unique license generation

License activation and validation

Duplicate activation prevention

License status tracking

License revocation

User/license association

Admin license management

Example:

HT-XXXX-XXXX-XXXX

👑 Admin Console

Admin dashboard

User analytics

User management

License management

Role-based access

Platform statistics

Administrative controls

🛡️ Security

Supabase Authentication

PostgreSQL

Row Level Security (RLS)

Role-based authorization

License validation

Protected admin functionality

Secure secret management

🧱 Technology Stack

Layer

Technology

Language

Python

Application Framework

Streamlit

Database

PostgreSQL

Backend Platform

Supabase

Authentication

Supabase Auth

Data Processing

Pandas

AI

AI API integration

Database Scripts

SQL

Deployment

Streamlit Community Cloud

📁 Project Structure

AI-Habit-Tracker/
│
├── .streamlit/
│   └── secrets.toml
│
├── database/
│   ├── database_schema.sql
│   ├── migration_license_system.sql
│   ├── seed_data.sql
│   └── README.md
│
├── services/
│   └── ...
│
├── utils/
│   └── ...
│
├── views/
│   ├── admin/
│   └── user/
│
├── app.py
├── auth.py
├── database.py
├── utils.py
├── requirements.txt
├── .gitignore
└── README.md

.streamlit/secrets.toml is local configuration and must never be committed.

⚙️ Local Development

Prerequisites

Python 3.x

Git

Supabase project

Required AI/API credentials

1. Clone

git clone https://github.com/YOUR_USERNAME/AI-Habit-Tracker.git
cd AI-Habit-Tracker

2. Create a virtual environment

Windows:

python -m venv venv
.env\Scripts\activate

3. Install dependencies

pip install -r requirements.txt

4. Configure secrets

Create:

.streamlit/secrets.toml

Add the credentials required by the application.

Example:

SUPABASE_URL = "your-supabase-url"
SUPABASE_KEY = "your-supabase-key"
AI_API_KEY = "your-ai-api-key"

Use the exact secret names expected by the application's configuration.

5. Configure Supabase

Database schema and migration scripts are available in:

database/

Run the required SQL scripts through the Supabase SQL Editor.

6. Run

streamlit run app.py

Open:

http://localhost:8501

🔐 Security

Never commit production credentials to GitHub.

Keep the following out of version control:

.streamlit/secrets.toml
.env
API keys
Database credentials
Passwords
Service-role keys
License keys

Use .gitignore and your deployment platform's secret manager.

🗄️ Architecture

                    ┌──────────────────┐
                    │   Streamlit App  │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        Authentication   User Platform   Admin Console
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                     ┌───────────────┐
                     │    Supabase   │
                     │ PostgreSQL DB │
                     └───────────────┘

🔄 License Flow

Customer purchases product
          ↓
Unique license is generated
          ↓
License is delivered
          ↓
Customer opens application
          ↓
Activate Purchase
          ↓
Enter license key
          ↓
Create account
          ↓
License is associated with user
          ↓
Use AI Habit Tracker

License delivery can initially be manual and can later be automated as sales volume grows.

🧪 Testing Areas

Authentication

Sign up

Login

Logout

Password reset

Invalid credentials

Email validation

License System

Generate license

Activate license

Validate license

Invalid license handling

Duplicate activation prevention

Revoke license

User/license association

User Platform

Dashboard

Habit management

Habit completion

Streak calculation

Journal

Achievements

AI Coach

Profile

Navigation

Admin Platform

Admin authentication

Dashboard

User analytics

Manage users

License management

Role-based permissions

Administrative operations

🌐 Deployment

Recommended deployment flow:

GitHub Repository
       ↓
Streamlit Community Cloud
       ↓
Configure Secrets
       ↓
Deploy
       ↓
Production URL
       ↓
Live Application Testing

Always test the production application after deployment.

🛣️ Roadmap

Automated Etsy order → license generation

Automated license delivery

Progressive Web App (PWA)

Improved mobile experience

Advanced notifications

Expanded analytics

Enhanced AI coaching

Performance optimization

Additional security hardening

Production monitoring

📌 Status

Production-ready application / deployment preparation

The project provides a license-controlled habit tracking experience with separate user and administrative functionality.

📄 License

Proprietary Software

This project and its source code are proprietary. Copying, redistribution, resale, modification, sublicensing, or commercial exploitation is not permitted without explicit authorization from the owner.

👨‍💻 Author

Chitvan Verma

Built with Python • Streamlit • Supabase • PostgreSQL • AI

🎯 Build consistency. Track progress. Become better every day.
