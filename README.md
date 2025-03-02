# Yupi - yudopr API

A FastAPI-based API service that provides various utility endpoints including blog management, bill splitting analysis, and user authentication.

## Features

- **Authentication System**
  - JWT-based authentication with secure refresh token handling
  - HTTP-only cookie-based refresh tokens
  - User registration and management
  - Role-based access control (User/Superuser)
  - Automatic token refresh
  - Secure logout mechanism

- **Blog Management**
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

- **Bill Splitting Analysis**
  - Upload bill images for analysis
  - AI-powered bill recognition using LLM
  - Automatic item and price detection
  - Smart cost distribution
  - VAT and service charge handling

## Tech Stack

- **Backend**: FastAPI (Python 3.8+)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Authentication**: JWT (JSON Web Tokens)
- **AI Integration**: OpenAI LLMs
- **Migration**: Alembic
- **Deployment**: Railway

## Prerequisites

- Python 3.8 or higher
- PostgreSQL
- OpenAI API key
- Git

## Installation

1. **Clone the Repository**
```bash
git clone https://github.com/yourusername/yupi.git
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

# Superuser credentials
SUPERUSER_USERNAME=admin
SUPERUSER_EMAIL=admin@example.com
SUPERUSER_PASSWORD=admin123

# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key

# API Info
API_TITLE=yupi - yudopr API
API_DESCRIPTION=API for many yudopr webapp projects
API_VERSION=1.0.0
```

Important: Make sure to:
- Never commit your `.env` file to version control
- Use strong, unique values for SECRET_KEY and passwords in production
- Keep your OpenAI API key secure
- Update the CORS settings if needed for your frontend
- Adjust token expiration times based on your security requirements:
  - ACCESS_TOKEN_EXPIRE_MINUTES: Short-lived tokens (e.g., 30 minutes)
  - REFRESH_TOKEN_EXPIRE_DAYS: Long-lived tokens (e.g., 30 days)
- Enable HTTPS in production for secure cookie handling

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

## Deployment

### Railway

Deploying to Railway is simple:

1. Create an account on [Railway](https://railway.app)
2. Click "New Project" on the Railway dashboard or "New Services" inside Railway Project
3. Select "Deploy from GitHub repo"
4. Choose your cloned repository
5. Railway will automatically detect the Vite configuration and deploy your site

That's it! Railway will automatically build and deploy your application. If needed, you can add environment variables in your project settings.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


## Acknowledgments
- Created by [yudopr](https://github.com/yudopr11)
- Built with [FastAPI](https://fastapi.tiangolo.com/) and [Python](https://python.org/)
- Deploy with [Railway](https://railway.app)