# Yupi - yudopr API

A FastAPI-based API service providing blog management, bill splitting analysis, personal finance tracking, and user authentication.

[![CI/CD](https://github.com/yudopr11/yupi/actions/workflows/ci.yml/badge.svg)](https://github.com/yudopr11/yupi/actions/workflows/ci.yml)

## Features

- **Authentication**
  - JWT access tokens + HTTP-only refresh token cookies
  - Role-based access control (User / Superuser)
  - Password reset via email
  - Automatic superuser creation on first startup

- **Blog (Yulog)**
  - Full CRUD for blog posts with Markdown content
  - AI-generated excerpts and tags (single OpenAI call)
  - Semantic search via pgvector + `text-embedding-3-small` embeddings
  - Tag filtering, pagination, published/unpublished status

- **Finance Tracker (Cuan)**
  - Account management: bank accounts, credit cards (with limit tracking), other
  - Account number field per account
  - Income / expense / transfer transactions with category assignment
  - Transfer fee support
  - Receipt upload (images/PDF) stored in RustFS (S3-compatible)
  - Cursor-based pagination for transaction lists
  - Financial statistics: summary, category distribution, time-series trends, account summary with credit utilization
  - Year-based balance history
  - Guest data cleanup endpoint (superuser only)

- **File Upload Service**
  - Generic S3-compatible file storage via boto3 + RustFS
  - Upload, download, soft-delete with orphan tracking
  - `file_uploads` table tracks all files with user association
  - Orphan cleanup endpoint for admin

- **Bill Splitting (Ngakak)**
  - GPT-4 Vision receipt parsing
  - Per-person breakdown: items, VAT share, service charge, discounts, final total
  - Multi-currency detection
  - Rate limiting for guest users (3 requests/day per IP)

- **AI Chat (YuChat)**
  - SSE streaming chat via MiMo LLM (Anthropic format)
  - Multi-MCP endpoint support — tools merged from all configured endpoints
  - Image attachments stored as base64 in Anthropic multimodal format
  - Per-user settings with Fernet encryption for API keys and MCP endpoints
  - Conversation history with tool call tracking

- **MCP Server**
  - 31 tools exposing all features at `/mcp/{base64(username:password)}`
  - Permission-matched to API (blog writes superuser-only, cuan CRUD any user)
  - Compatible with Claude Desktop and MCP Inspector

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12+ |
| Framework | FastAPI 0.135 + Starlette 1.1 |
| Database | PostgreSQL 16 + pgvector |
| ORM / Migrations | SQLAlchemy 2.0 + Alembic |
| Auth | PyJWT (HS256) + bcrypt |
| AI | OpenAI (GPT-4o, o3-mini, text-embedding-3-small) |
| File Storage | boto3 + RustFS (S3-compatible) |
| Email | fastapi-mail + aiosmtplib (async SMTP) |
| ID Generation | uuid-utils (Rust-backed UUIDv7) |
| Packaging | uv |
| Deployment | Railway |
| CI/CD | GitHub Actions |

## Prerequisites

- Python 3.12+
- PostgreSQL with pgvector extension
- OpenAI API key
- RustFS or any S3-compatible storage (for file uploads)
- uv (`pip install uv`)

## Installation

```bash
git clone https://github.com/yudopr11/yupi.git
cd yupi
uv sync
cp .env.example .env   # then edit .env
alembic upgrade head
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `SECRET_KEY` | — | JWT signing secret (change in production) |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token TTL |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | `15` | Reset token TTL |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `SUPERUSER_USERNAME` | `admin` | Auto-created admin username |
| `SUPERUSER_EMAIL` | — | Auto-created admin email |
| `SUPERUSER_PASSWORD` | — | Auto-created admin password |
| `COOKIE_SECURE` | `False` | `True` for HTTPS production |
| `RUSTFS_ENDPOINT` | `http://localhost:9000` | RustFS/S3 endpoint URL |
| `RUSTFS_ACCESS_KEY` | — | RustFS access key |
| `RUSTFS_SECRET_KEY` | — | RustFS secret key |
| `RUSTFS_BUCKET` | `yupi-uploads` | S3 bucket name |
| `RUSTFS_REGION` | `us-east-1` | S3 region |
| `MAIL_USERNAME` | — | Gmail address |
| `MAIL_PASSWORD` | — | Gmail App Password |
| `MAIL_FROM` | — | From address for emails |

> Set `COOKIE_SECURE=False` for local HTTP dev — the browser won't store the refresh token cookie over HTTP with `Secure=True`.

## Running Locally

```bash
uv run uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Running Tests

```bash
uv run python -m pytest tests/ -v
```

280 tests covering MCP tools, auth, blog helpers, cuan helpers, file service, crypto, chat orchestrator, and MiMo client. Tests use mocks for all external services (OpenAI, email, S3) — no live credentials needed.

## API Endpoints

### Authentication (`/auth`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/login` | — | Login → access token + refresh cookie |
| POST | `/auth/refresh` | Cookie | New access token from refresh cookie |
| POST | `/auth/logout` | — | Clear refresh cookie |
| POST | `/auth/register` | Superuser | Create user |
| GET | `/auth/users` | Superuser | List all users |
| GET | `/auth/users/me` | Yes | Current user info |
| DELETE | `/auth/users/{id}` | Superuser | Delete user |
| POST | `/auth/forgot-password` | — | Send reset email |
| POST | `/auth/reset-password` | — | Reset password with token |

### Blog (`/blog`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/blog` | — | Paginated posts (search, tag, status filter) |
| GET | `/blog/{slug}` | — | Single post by slug |
| POST | `/blog/admin` | Yes | Create post |
| PUT | `/blog/admin/{id}` | Yes | Update post |
| DELETE | `/blog/admin/{id}` | Superuser | Delete post |

Query params for `GET /blog`: `skip`, `limit`, `search`, `tag`, `published_status` (`published`/`unpublished`/`all`), `use_rag` (semantic search).

### Finance (`/cuan`)

**Accounts**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/cuan/accounts` | Create account |
| GET | `/cuan/accounts` | List with balances (optional `?year=` filter) |
| PUT | `/cuan/accounts/{id}` | Update account |
| DELETE | `/cuan/accounts/{id}` | Delete account + transactions |
| GET | `/cuan/accounts/{id}/balance` | Detailed balance (optional `?year=`) |

**Categories**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/cuan/categories` | Create category |
| GET | `/cuan/categories` | List (optional `?category_type=income\|expense`) |
| PUT | `/cuan/categories/{id}` | Update |
| DELETE | `/cuan/categories/{id}` | Delete |

**Transactions**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/cuan/transactions` | Create (multipart form, optional receipt file) |
| GET | `/cuan/transactions` | Paginated list with filters + cursor pagination |
| PUT | `/cuan/transactions/{id}` | Update (multipart form, optional receipt) |
| DELETE | `/cuan/transactions/{id}` | Delete (marks receipt as orphan) |
| POST | `/cuan/cleanup-guest-data` | Delete guest transactions older than N days (superuser) |

Filters for `GET /cuan/transactions`: `account_name`, `category_name`, `transaction_type`, `start_date`, `end_date`, `date_filter_type` (`day`/`week`/`month`/`year`/`all`), `order_by`, `sort_order`, `limit`, `skip`, `cursor`.

Transaction create/update accepts `multipart/form-data` with optional `receipt` file (image/PDF). Response includes `receipt_file_id` and `receipt_url`.

**Statistics**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cuan/statistics/summary` | Income / expense / net totals |
| GET | `/cuan/statistics/by-category` | Category breakdown with percentages |
| GET | `/cuan/statistics/trends` | Time-series grouped by interval |
| GET | `/cuan/statistics/account-summary` | All accounts + credit utilization |

### Files (`/files`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/files/{id}` | Yes | Download file (owner only) |
| DELETE | `/files/{id}` | Yes | Mark file as orphan (soft delete) |
| POST | `/files/cleanup-orphans` | Superuser | Delete all orphaned files from storage + DB |

### Bill Splitting (`/ngakak`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/ngakak/analyze` | Yes | Analyze bill image and split costs |

Form fields: `image` (JPG/PNG/WebP ≤ 5 MB), `description` (who ordered what), `image_description` (optional, skips vision step).

### Chat (`/chat`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/chat` | Yes | Send message + stream SSE response (supports image attachments) |
| GET | `/chat/conversations` | Yes | List user conversations |
| GET | `/chat/conversations/{id}` | Yes | Get conversation with messages |
| DELETE | `/chat/conversations/{id}` | Yes | Delete conversation |
| PATCH | `/chat/conversations/{id}` | Yes | Update conversation title |
| GET | `/chat/settings` | Yes | Get user MiMo config (keys masked) |
| PUT | `/chat/settings` | Yes | Update MiMo config + MCP endpoints (encrypted) |

### MCP Server

```
/mcp/{base64(username:password)}
```

31 tools across 6 domains, matching all API endpoints (auth flows + SSE chat excluded):

| Domain | Tools | Permissions |
|--------|-------|-------------|
| Auth | `get_current_user`, `list_all_users`, `register_user`, `delete_user` | Superuser-only for admin ops |
| Blog | `list_posts`, `get_post`, `create_post`, `update_post`, `delete_post` | Superuser-only for writes |
| Cuan Accounts | `list_accounts`, `get_account_balance`, `create_account`, `update_account`, `delete_account` | Any authenticated user |
| Cuan Categories | `list_categories`, `create_category`, `update_category`, `delete_category` | Any authenticated user |
| Cuan Transactions | `list_transactions`, `create_transaction`, `update_transaction`, `delete_transaction` | Any authenticated user |
| Cuan Statistics | `get_financial_summary`, `get_category_distribution`, `get_trends`, `get_account_summary` | Any authenticated user |
| Files | `list_files`, `delete_file`, `cleanup_orphaned_files`, `cleanup_guest_data` | Superuser for admin ops |
| Ngakak | `analyze_bill` | Any authenticated user |

```bash
# Test with MCP Inspector (server must be running)
npx @modelcontextprotocol/inspector http://localhost:8000/mcp/<token>
```

## CI/CD

GitHub Actions runs on every push/PR to `main`:

1. Spins up a `pgvector/pgvector:pg16` Postgres service
2. Installs dependencies with `uv sync`
3. Runs the full test suite (`pytest tests/ -v`)
4. **Deploys to Railway only if all tests pass** (push to `main` only)

To enable Railway deployment, add `RAILWAY_TOKEN` as a GitHub Actions secret and disable Railway's auto-deploy from GitHub.

## Deployment (Railway)

1. Fork / clone this repo
2. Create a Railway project and link the repo
3. Add all required environment variables in Railway dashboard
4. Disable Railway's auto-deploy (let GitHub Actions control deploys)
5. Add `RAILWAY_TOKEN` to GitHub repo secrets

Railway uses `railway.toml` for build/start configuration.

## Updating Embeddings

Embeddings regenerate automatically on post create/update and on each deploy. To force-regenerate all:

```bash
uv run python scripts/update_embeddings.py --force
```

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

- Created by [yudopr](https://github.com/yudopr11)
- Built with [FastAPI](https://fastapi.tiangolo.com/) and [Python](https://python.org/)
- Deployed on [Railway](https://railway.app)
