# Yupi - yudopr API

A FastAPI-based API service that provides various utility endpoints including blog management, bill splitting analysis, transaction management, and user authentication.

## Features

- **Authentication System (Auth)**
  - JWT-based authentication with secure refresh token handling
  - HTTP-only cookie-based refresh tokens
  - User registration and management
    - User creation (superuser only)
    - User list retrieval (superuser only)
    - User deletion (superuser only)
  - Role-based access control (User/Superuser)
  - Automatic token refresh
  - Secure logout mechanism
  - Password recovery system
    - "Forgot Password" email-based reset flow
    - Secure reset token generation and validation
    - Time-limited reset links
    - Email notifications for password reset requests
  - Automatic superuser creation on app startup

- **Blog Management (Yulog & Yudas)**
  - Create, read, update, delete blog posts
  - Markdown content support
  - Tag system
    - Filter posts by specific tag (case-insensitive)
    - Search within post tags
    - AI-powered tag generation based on content
      - Considers existing tags for consistency
      - Prioritizes reusing relevant tags from database
      - Capitalizes tags for better readability
  - Author information included in responses
  - AI-powered excerpt generation
    - Automatically creates engaging summaries
    - Optional manual override
  - Optimized AI content generation
    - Single LLM call generates both excerpts and tags
    - Reduces API usage and latency
  - Reading time calculation
  - Search functionality across title, excerpt, content, and tags
  - Flexible post filtering options
    - Filter by published status (published, unpublished, or all)
    - Filter by tags (case-insensitive)
    - Pagination with customizable limits
  - Semantic search using OpenAI embeddings (RAG-based approach)
    - 1536-dimension embeddings via `text-embedding-3-small`
    - Vector storage in PostgreSQL via pgvector
    - Cosine similarity ranking
  - URL-friendly slugs

- **Transaction Management (Cuan)**
  - Account management
    - Support for bank accounts, credit cards, and other account types
    - Credit card limit tracking and balance validation
    - Auto-generated initial balance transaction for credit cards
    - Year-based balance history
  - Category management (income/expense categories)
  - Transaction management
    - Support for income, expense, and transfer transaction types
    - Transfer fee handling
    - Advanced filtering: by account, category, type, date range
    - Pagination and sorting
  - Comprehensive financial statistics
    - Summary: total income, expense, transfer, and net balance
    - Breakdown by category with percentage distribution
    - Trends over time (grouped by hour, day, week, month, or year)
    - Account summary with credit utilization metrics

- **Bill Splitting Analysis (Ngakak)**
  - Upload bill images for analysis
  - AI-powered bill recognition using GPT-4 Vision
  - Automatic item and price detection with quantity handling
  - Multi-currency support with automatic detection
  - Smart cost distribution per person
  - VAT/GST, service charge, and discount handling
  - Per-person breakdown: items, subtotal, VAT share, service share, discount share, final amount
  - Rate limiting for guest users (3 requests/day per IP)

## Tech Stack

- **Backend**: FastAPI (Python 3.12+)
- **Database**: PostgreSQL with pgvector
- **ORM**: SQLAlchemy 2.0
- **Authentication**: JWT (JSON Web Tokens)
- **AI Integration**: OpenAI LLMs & Embeddings
- **Email**: fastapi-mail with async SMTP
- **Migration**: Alembic
- **Deployment**: Railway

## Prerequisites

- Python 3.12 or higher
- PostgreSQL (with pgvector extension)
- OpenAI API key
- Git

## Installation

1. **Clone the Repository**
```bash
git clone https://github.com/yudopr11/yupi.git
cd yupi
```

2. **Create Virtual Environment**
```bash
python -m venv venv
# For Windows
venv\Scripts\activate
# For Unix or MacOS
source venv/bin/activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment Setup**

Copy the `.env.example` file to create your `.env`:
```bash
cp .env.example .env
```

Then update the values in `.env` with your actual configuration:
```env
# Database settings
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/yupi_db

# JWT settings
SECRET_KEY=your-super-secret-key-that-should-be-very-long-and-random
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30  # Short-lived access tokens
REFRESH_TOKEN_EXPIRE_DAYS=30    # Long-lived refresh tokens in HTTP-only cookies
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=15  # Short-live password reset tokens

# Superuser credentials
SUPERUSER_USERNAME=admin
SUPERUSER_EMAIL=admin@example.com
SUPERUSER_PASSWORD=admin123

# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key

# Email configuration
MAIL_USERNAME=your_email@example.com
MAIL_PASSWORD=your_email_app_password
MAIL_FROM=your_email@example.com

# API Info
API_TITLE=yupi - yudopr API
API_DESCRIPTION=API for many yudopr webapp projects
API_VERSION=1.0.0

# Cookie settings
COOKIE_SECURE=False  # False for local dev (HTTP), True for production (HTTPS)
```

Important: Make sure to:
- Never commit your `.env` file to version control
- Use strong, unique values for SECRET_KEY and passwords in production
- Keep your OpenAI API key secure
- Update the CORS settings for your frontend — avoid wildcard `*` when `CORS_CREDENTIALS=True`
- Configure valid email credentials for password reset functionality
  - In this API, I use my Gmail, use an App Password instead of account password
  - Ensure proper SMTP settings for your email provider
- Adjust token expiration times based on your security requirements:
  - ACCESS_TOKEN_EXPIRE_MINUTES: Short-lived tokens (e.g., 30 minutes)
  - REFRESH_TOKEN_EXPIRE_DAYS: Long-lived tokens (e.g., 30 days)
  - PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: Short-lived tokens (e.g., 15 minutes)
- Set `COOKIE_SECURE` correctly for your environment:
  - `False` for local development over HTTP — browser requires this to store the refresh token cookie
  - `True` for production over HTTPS — required for secure cookie transmission
  - **Important**: Using `COOKIE_SECURE=True` on HTTP will silently break the refresh token flow

5. **Database Setup**

Create a PostgreSQL database and run migrations:
```bash
# Create database
createdb yupi_db

# Run migrations
alembic upgrade head
```

## Running Locally

1. **Start the Development Server**
```bash
uvicorn app.main:app --reload --port 8000
```

2. **Access the API Documentation**
    - Swagger UI: http://localhost:8000/docs
    - ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication (`/auth`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/login` | — | Login, returns access token + sets refresh token cookie |
| POST | `/auth/refresh` | Cookie | Get new access token using refresh token cookie |
| POST | `/auth/logout` | Yes | Clear refresh token cookie |
| POST | `/auth/register` | Superuser | Create new user account |
| GET | `/auth/users` | Superuser | List all registered users |
| GET | `/auth/users/me` | Yes | Get current user info |
| DELETE | `/auth/users/{user_id}` | Superuser | Delete a user |
| POST | `/auth/forgot-password` | — | Send password reset email |
| POST | `/auth/reset-password` | — | Reset password with reset token |

### Blog (`/blog`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/blog` | — | Get paginated posts with optional search & filters |
| GET | `/blog/{slug}` | — | Get a single post by URL slug |
| POST | `/blog/admin` | Yes | Create post (auto-generates excerpt & tags via AI) |
| PUT | `/blog/admin/{post_id}` | Yes | Update post |
| DELETE | `/blog/admin/{post_id}` | Superuser | Delete post |

**Query parameters for `GET /blog`:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `skip` | int | Pagination offset |
| `limit` | int | Results per page (default: 3) |
| `search` | str | Full-text search across title, excerpt, content, tags |
| `tag` | str | Filter by tag (case-insensitive) |
| `published_status` | str | `published`, `unpublished`, or `all` |
| `use_rag` | bool | Enable semantic/embedding-based search |

### Financial Transactions (`/cuan`)

**Accounts**

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/cuan/accounts` | Yes | Create account (bank, credit card, other) |
| GET | `/cuan/accounts` | Yes | List all accounts with balances |
| PUT | `/cuan/accounts/{id}` | Yes | Update account |
| DELETE | `/cuan/accounts/{id}` | Yes | Delete account and its transactions |
| GET | `/cuan/accounts/{id}/balance` | Yes | Get detailed balance for an account |

**Categories**

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/cuan/categories` | Yes | Create income/expense category |
| GET | `/cuan/categories` | Yes | List categories |
| PUT | `/cuan/categories/{id}` | Yes | Update category |
| DELETE | `/cuan/categories/{id}` | Yes | Delete category |

**Transactions**

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/cuan/transactions` | Yes | Create income, expense, or transfer transaction |
| GET | `/cuan/transactions` | Yes | Get paginated transactions with filters |
| PUT | `/cuan/transactions/{id}` | Yes | Update transaction |
| DELETE | `/cuan/transactions/{id}` | Yes | Delete transaction |

**Query parameters for `GET /cuan/transactions`:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `account_name` | str | Filter by account |
| `category_name` | str | Filter by category |
| `transaction_type` | str | `income`, `expense`, or `transfer` |
| `start_date` / `end_date` | datetime | Date range |
| `date_filter_type` | str | Preset range: `today`, `week`, `month`, `year`, `all` |
| `order_by` | str | Sort field: `created_at`, `transaction_date`, `amount` |
| `sort_order` | str | `asc` or `desc` |
| `limit` / `skip` | int | Pagination |

**Statistics**

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/cuan/statistics/summary` | Yes | Income, expense, transfer totals and net balance |
| GET | `/cuan/statistics/by-category` | Yes | Breakdown by category with percentages |
| GET | `/cuan/statistics/trends` | Yes | Trends over time grouped by interval |
| GET | `/cuan/statistics/account-summary` | Yes | All accounts status with credit utilization |

**Common statistics query parameters:** `period` (day/week/month/year/all), `start_date`, `end_date`, `group_by` (hour/day/week/month/year), `transaction_types`.

### Bill Splitting (`/ngakak`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/ngakak/analyze` | — | Analyze a bill image and split costs |

**Request form fields:**

| Field | Type | Description |
|-------|------|-------------|
| `image` | file | Bill image (JPG, PNG, WebP, max 5 MB) |
| `description` | str | Order details (who ordered what) |
| `image_description` | str (optional) | Pre-analyzed image text to skip vision step |

**Notes:**
- Unauthenticated (guest) users are limited to **3 requests per day** per IP
- Authenticated users use `o3-mini`; guests use `gpt-4o-mini`

## Deployment

### Railway

1. Create an account on [Railway](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Choose your cloned repository
4. Add environment variables in project settings

Railway will automatically build and deploy your application.

## AI-Powered Features

### Smart Content Generation

The blog component includes two AI-powered features:

1. **Automatic Excerpt Generation**: When a new post is created without an excerpt, the system uses an LLM to generate a concise, engaging excerpt from the post content.

2. **Intelligent Tag Suggestion**: When tags are not provided, the system analyzes the content and suggests relevant tags, reusing existing tags from the database where appropriate and capitalizing them for consistency.

Both features are combined into a **single LLM call** to reduce API usage and latency.

### Semantic Search (RAG)

Blog search supports a Retrieval Augmented Generation approach using OpenAI embeddings:

1. **Embedding Generation**: Title and excerpt of each post are embedded via `text-embedding-3-small` (1536 dimensions).
2. **Vector Storage**: Embeddings are stored in PostgreSQL using the pgvector extension.
3. **Similarity Calculation**: Search queries are embedded and compared to post embeddings using cosine similarity (threshold: 0.3).
4. **Ranked Results**: Posts are returned ranked by semantic relevance.

To use semantic search, add `use_rag=true` to the `/blog` query:
```
GET /blog?search=climate change&use_rag=true
```

### Updating Embeddings

Embeddings are automatically generated on post create/update and refreshed on deployment. To manually batch-update all post embeddings:

```bash
python scripts/update_embeddings.py --force
```

Options:
- `--force`: Update all posts regardless of existing embeddings
- `--batch-size N`: Process N posts per batch (default: 50)

### Bill Analysis

The `/ngakak/analyze` endpoint uses a two-stage AI pipeline:

1. **Image Recognition** (GPT-4 Vision): Extracts raw text and items from the bill image.
2. **Split Calculation** (o3-mini / gpt-4o-mini): Parses the order description and produces a per-person breakdown including item costs, VAT share, service charge share, discount share, and final totals.

Supports quantity-aware pricing, multi-currency detection, and flexible discount formats.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- Created by [yudopr](https://github.com/yudopr11)
- Built with [FastAPI](https://fastapi.tiangolo.com/) and [Python](https://python.org/)
- Deploy with [Railway](https://railway.app)
