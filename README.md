# Macro Meals

Macro Meals is a mobile application designed to help users calculate, track, and meet their daily macronutrient goals. It differentiates itself from traditional calorie tracking apps by connecting users with real-world meals from nearby restaurants or food delivery options that align with their dietary needs. The goal is to simplify nutrition tracking without compromising convenience.

## 📋 Table of Contents

- [🚀 Quick Start](#-quick-start)
- [🏗️ Architecture](#️-architecture)
- [🗄️ Database & Migrations](#️-database--migrations)
- [🧪 Testing](#-testing)

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- Supabase CLI

### 1. Clone & Setup

```bash
git clone https://github.com/mukeez/meal-recommender-saas.git
cd meal-recommender-saas

python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

pip install -r requirements.txt
```

### 2. Database Setup

Find the installation guide here: https://supabase.com/docs/guides/local-development

```bash
# Login to Supabase
supabase login

# List projects (this command will output the project reference)
supabase projects list

# Link to your project (replace with your project reference)
supabase link --project-ref your-project-ref
```

### 3. Run the Application

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-config app/log_config.json

# Or with Docker
docker-compose up
```

## 🏗️ Architecture

### Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Database**: Supabase (PostgreSQL)
- **Authentication**: Supabase Auth
- **File Storage**: S3
- **Background Tasks**: Celery + Redis
- **LLMs**: OpenAI GPT, Google Gemini
- **Containerization**: Docker
- **Cloud**: AWS

### Key Features

- 🔐 **User Authentication** - Secure signup/login with Supabase Auth
- 🧮 **Macro Calculator** - Calculates daily macronutrient targets based on age, sex, activity level, and fitness objectives
- 📊 **Nutrition Tracking** - Log meals and track macros
- 📝 **Meal Logging** - Supports manual entry, barcode scan, and camera-based food recognition
- 📈 **Macro Dashboard** - Visual breakdown of consumed vs remaining calories and macro nutrients
- 🍽️ **Meal Recommendations** - AI-powered personalized suggestions
- 🤖 **AI Recipe Suggestions** - Uses AI prompts to provide simple, macro-aligned recipes that support the user's nutrition goals
- 🏪 **Restaurant Integration** - Find nearby restaurants with menu items
- 📍 **Location-Based Meal Finder** - Identifies real restaurant meals nearby that meet the user's dietary targets
- 📱 **Mobile Support** - Push notifications via FCM
- 💳 **Subscription Management** - Stripe integration for pro features
- 🌍 **Geographic Search** - PostGIS-powered location services
- 🔍 **Vector Search** - Semantic meal similarity search

## 🗄️ Database & Migrations

### Migration System

We use Supabase's native migration system for schema management across environments.

#### Migration Workflow

1. **Create New Migration**

```bash
supabase migration new your_migration_name
```

2. **Edit Migration File**

```sql
-- supabase/migrations/timestamp_your_migration_name.sql
CREATE TABLE IF NOT EXISTS "public"."new_table" (
    "id" uuid DEFAULT gen_random_uuid() NOT NULL,
    "name" varchar(255) NOT NULL,
    "created_at" timestamp with time zone DEFAULT now() NOT NULL,
    PRIMARY KEY ("id")
);

-- Add RLS policies
ALTER TABLE "public"."new_table" ENABLE ROW LEVEL SECURITY;
```

3. **Push Changes to Remote Project**
   Ensure you're linked to the right project before pushing.

```bash
supabase db push
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
pytest --cov=app

# Run specific test file
python -m pytest app/tests/api/test_auth.py

# Run specific test function
python -m pytest -k your_test_function_name

# Run with verbose output
python -m pytest -v
```
