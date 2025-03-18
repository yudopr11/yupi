# yupi API Documentation

This document provides detailed information about all available endpoints in the Yupi API.

## Table of Contents

- [Authentication](#authentication)
  - [Register](#register)
  - [Login](#login)
  - [Refresh Token](#refresh-token)
  - [Logout](#logout)
  - [Forgot Password](#forgot-password)
  - [Reset Password](#reset-password)
  - [Get All Users](#get-all-users)
  - [Delete User](#delete-user)
- [Blog Management](#blog-management)
  - [Create Post](#create-post)
  - [Get Posts](#get-posts)
  - [Get Post by Slug](#get-post-by-slug)
  - [Update Post](#update-post)
  - [Delete Post](#delete-post)
- [Bill Splitting](#bill-splitting)
- [Personal Transactions](#personal-transactions)
  - [Account Management](#account-management)
  - [Category Management](#category-management)
  - [Transaction Management](#transaction-management)

## Authentication

All authenticated endpoints require a valid JWT token to be included in the request header. 

**Authorization Header Format**:
```
Authorization: Bearer YOUR_ACCESS_TOKEN
```

### Register

Create a new user account (superuser only).

**URL**: `/auth/register`  
**Method**: `POST`  
**Auth required**: Yes (Superuser)  

**Request Body**:
```json
{
  "username": "string",
  "email": "user@example.com",
  "password": "string",
  "is_superuser": false
}
```

**Success Response**: `200 OK`
```json
{
  "user_id": 0,
  "uuid": "string",
  "username": "string",
  "email": "user@example.com",
  "is_superuser": false,
  "created_at": "2023-01-01T00:00:00.000Z"
}
```

**Error Responses**:
- `400 Bad Request` - Username or email already registered
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not enough permissions
- `422 Unprocessable Entity` - Validation error

### Login

Log in to obtain an access token.

**URL**: `/auth/login`  
**Method**: `POST`  
**Auth required**: No  

**Request Body** (form data):
```
username=string&password=string
```

**Success Response**: `200 OK`
```json
{
  "access_token": "string",
  "token_type": "bearer"
}
```

**Notes**:
- Access token is returned in the response
- Refresh token is set as an HTTP-only cookie

**Error Responses**:
- `401 Unauthorized` - Incorrect username or password
- `422 Unprocessable Entity` - Validation error

### Refresh Token

Get a new access token using the refresh token stored in cookies.

**URL**: `/auth/refresh`  
**Method**: `POST`  
**Auth required**: No (but requires refresh token cookie)  

**Success Response**: `200 OK`
```json
{
  "access_token": "string",
  "token_type": "bearer"
}
```

**Error Responses**:
- `401 Unauthorized` - Invalid refresh token
- `422 Unprocessable Entity` - Validation error

### Logout

Log out by clearing the refresh token cookie.

**URL**: `/auth/logout`  
**Method**: `POST`  
**Auth required**: No  

**Success Response**: `200 OK`
```json
{
  "message": "Successfully logged out"
}
```

### Forgot Password

Request a password reset link sent via email.

**URL**: `/auth/forgot-password`  
**Method**: `POST`  
**Auth required**: No  

**Request Body**:
```json
{
  "email": "user@example.com"
}
```

**Success Response**: `200 OK`
```json
{
  "message": "If the email exists in our system, a reset token will be sent."
}
```

**Notes**:
- For security reasons, the API returns the same response whether the email exists or not
- If the email exists in the system, a reset token will be sent
- The reset token expires after the time specified in PASSWORD_RESET_TOKEN_EXPIRE_MINUTES

**Error Responses**:
- `404 Not Found` - Email not found
- `422 Unprocessable Entity` - Validation error (invalid email format)

### Reset Password

Reset a user's password using a valid reset token.

**URL**: `/auth/reset-password`  
**Method**: `POST`  
**Auth required**: No  

**Request Body**:
```json
{
  "token": "string",
  "new_password": "string"
}
```

**Success Response**: `200 OK`
```json
{
  "message": "Password has been reset successfully"
}
```

**Error Responses**:
- `401 Bad Request` - Invalid or expired token
- `404 Not Found` - User not found
- `422 Unprocessable Entity` - Validation error (password requirements not met)

### Get All Users

Get a list of all users (superuser only).

**URL**: `/auth/users`  
**Method**: `GET`  
**Auth required**: Yes (Superuser)  

**Success Response**: `200 OK`
```json
[
  {
    "user_id": 0,
    "uuid": "string",
    "username": "string",
    "email": "user@example.com",
    "is_superuser": false,
    "created_at": "2023-01-01T00:00:00.000Z"
  }
]
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not enough permissions

### Delete User

Delete a user by ID (superuser only).

**URL**: `/auth/users/{user_id}`  
**Method**: `DELETE`  
**Auth required**: Yes (Superuser)  

**URL Parameters**:
- `user_id` - The ID of the user to delete

**Success Response**: `200 OK`
```json
{
  "message": "User has been deleted successfully",
  "deleted_item": {
    "id": 0,
    "username": "string",
    "uuid": "string"
  }
}
```

**Error Responses**:
- `400 Bad Request` - Cannot delete own superuser account
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not enough permissions
- `404 Not Found` - User not found
- `422 Unprocessable Entity` - Validation error

## Blog Management

Manage blog posts for the platform.

### Create Post

Create a new blog post.

**URL**: `/blog`  
**Method**: `POST`  
**Auth required**: Yes (Superuser)  

**Request Body**:
```json
{
  "title": "string",
  "slug": "string",
  "excerpt": "string",
  "content": "string",
  "featured_image": "string",
  "tags": ["tag1", "tag2"],
  "is_published": true
}
```

**Success Response**: `200 OK`
```json
{
  "post_id": 0,
  "uuid": "string",
  "title": "string",
  "slug": "string",
  "excerpt": "string",
  "content": "string",
  "featured_image": "string",
  "tags": ["tag1", "tag2"],
  "is_published": true,
  "created_at": "2023-01-01T00:00:00.000Z",
  "updated_at": "2023-01-01T00:00:00.000Z"
}
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not enough permissions
- `422 Unprocessable Entity` - Validation error

### Get Posts

Get a list of blog posts with pagination and filtering options.

**URL**: `/blog`  
**Method**: `GET`  
**Auth required**: No  

**Query Parameters**:
- `skip` (integer, default=0) - Number of items to skip
- `limit` (integer, default=3) - Number of items to return
- `search` (string, optional) - Search term for title, excerpt, content, and tags
- `tag` (string, optional) - Filter by tag (case-insensitive)
- `status` (string, default="published") - Filter by status: 'published', 'unpublished', or 'all'

**Success Response**: `200 OK`
```json
{
  "items": [
    {
      "post_id": 0,
      "uuid": "string",
      "title": "string",
      "slug": "string",
      "excerpt": "string", 
      "content": "string",
      "featured_image": "string",
      "tags": ["tag1", "tag2"],
      "is_published": true,
      "created_at": "2023-01-01T00:00:00.000Z",
      "updated_at": "2023-01-01T00:00:00.000Z"
    }
  ],
  "total": 10,
  "has_more": true
}
```

**Notes**:
- Supports semantic search using OpenAI embeddings when search parameter is provided
- Default limit is 3 posts per page

### Get Post by Slug

Get a specific blog post by its slug.

**URL**: `/blog/{slug}`  
**Method**: `GET`  
**Auth required**: No  

**URL Parameters**:
- `slug` - The slug of the post to retrieve

**Success Response**: `200 OK`
```json
{
  "post_id": 0,
  "uuid": "string",
  "title": "string",
  "slug": "string",
  "excerpt": "string",
  "content": "string",
  "featured_image": "string",
  "tags": ["tag1", "tag2"],
  "is_published": true,
  "created_at": "2023-01-01T00:00:00.000Z",
  "updated_at": "2023-01-01T00:00:00.000Z"
}
```

**Error Responses**:
- `404 Not Found` - Post not found

### Update Post

Update an existing blog post.

**URL**: `/blog/{slug}`  
**Method**: `PUT`  
**Auth required**: Yes (Superuser)  

**URL Parameters**:
- `slug` - The slug of the post to update

**Request Body**:
```json
{
  "title": "string",
  "slug": "string",
  "excerpt": "string",
  "content": "string",
  "featured_image": "string",
  "tags": ["tag1", "tag2"],
  "is_published": true
}
```

**Success Response**: `200 OK`
```json
{
  "post_id": 0,
  "uuid": "string",
  "title": "string",
  "slug": "string",
  "excerpt": "string",
  "content": "string",
  "featured_image": "string",
  "tags": ["tag1", "tag2"],
  "is_published": true,
  "created_at": "2023-01-01T00:00:00.000Z",
  "updated_at": "2023-01-01T00:00:00.000Z"
}
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not enough permissions
- `404 Not Found` - Post not found
- `422 Unprocessable Entity` - Validation error

### Delete Post

Delete a blog post.

**URL**: `/blog/{slug}`  
**Method**: `DELETE`  
**Auth required**: Yes (Superuser)  

**URL Parameters**:
- `slug` - The slug of the post to delete

**Success Response**: `200 OK`
```json
{
  "message": "Post deleted successfully"
}
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not enough permissions
- `404 Not Found` - Post not found

## Personal Transactions

Manage personal financial transactions including accounts, categories, and transactions.

### Account Management

Endpoints for managing transaction accounts.

#### Create Account

Create a new transaction account.

**URL**: `/trx/accounts`  
**Method**: `POST`  
**Auth required**: Yes  

**Request Body**:
```json
{
  "name": "string",
  "type": "bank_account", // Can be "bank_account", "credit_card", or "other"
  "description": "string",
  "limit": 0
}
```

**Success Response**: `200 OK`
```json
{
  "data": {
    "name": "string",
    "type": "bank_account",
    "description": "string",
    "limit": "0",
    "account_id": 0,
    "uuid": "string",
    "user_id": 0,
    "created_at": "2023-01-01T00:00:00.000Z",
    "updated_at": "2023-01-01T00:00:00.000Z"
  },
  "message": "Success"
}
```

#### Get Accounts

Get a list of transaction accounts with balances.

**URL**: `/trx/accounts`  
**Method**: `GET`  
**Auth required**: Yes  

**Success Response**: `200 OK`
```json
{
  "data": [
    {
      "name": "string",
      "type": "bank_account",
      "description": "string",
      "limit": "0",
      "account_id": 0,
      "uuid": "string",
      "user_id": 0,
      "created_at": "2023-01-01T00:00:00.000Z",
      "updated_at": "2023-01-01T00:00:00.000Z",
      "balance": "0.00"
    }
  ],
  "message": "Success"
}
```

### Category Management

Endpoints for managing transaction categories.

#### Create Category

Create a new transaction category.

**URL**: `/trx/categories`  
**Method**: `POST`  
**Auth required**: Yes  

**Request Body**:
```json
{
  "name": "string",
  "type": "income", // Can be "income", "expense", or "transfer"
  "icon": "string",
  "color": "string"
}
```

**Success Response**: `200 OK`
```json
{
  "data": {
    "name": "string",
    "type": "income",
    "icon": "string",
    "color": "string",
    "category_id": 0,
    "uuid": "string",
    "user_id": 0,
    "created_at": "2023-01-01T00:00:00.000Z",
    "updated_at": "2023-01-01T00:00:00.000Z"
  },
  "message": "Success"
}
```

#### Get Categories

Get a list of transaction categories.

**URL**: `/trx/categories`  
**Method**: `GET`  
**Auth required**: Yes  

**Query Parameters**:
- `type` (string, optional) - Filter by type: 'income', 'expense', or 'transfer'

**Success Response**: `200 OK`
```json
{
  "data": [
    {
      "name": "string",
      "type": "income",
      "icon": "string",
      "color": "string",
      "category_id": 0,
      "uuid": "string",
      "user_id": 0,
      "created_at": "2023-01-01T00:00:00.000Z",
      "updated_at": "2023-01-01T00:00:00.000Z"
    }
  ],
  "message": "Success"
}
```

### Transaction Management

Endpoints for managing financial transactions.

#### Create Transaction

Create a new financial transaction.

**URL**: `/trx/transactions`  
**Method**: `POST`  
**Auth required**: Yes  

**Request Body**:
```json
{
  "amount": "100.00",
  "type": "income", // Can be "income", "expense", or "transfer"
  "description": "string",
  "date": "2023-01-01T00:00:00.000Z",
  "account_id": 0,
  "category_id": 0,
  "transfer_account_id": 0, // Required only for transfer type
  "notes": "string"
}
```

**Success Response**: `200 OK`
```json
{
  "data": {
    "transaction_id": 0,
    "uuid": "string",
    "user_id": 0,
    "amount": "100.00",
    "type": "income",
    "description": "string",
    "date": "2023-01-01T00:00:00.000Z",
    "account_id": 0,
    "category_id": 0,
    "transfer_account_id": null,
    "notes": "string",
    "created_at": "2023-01-01T00:00:00.000Z",
    "updated_at": "2023-01-01T00:00:00.000Z"
  },
  "message": "Success"
}
```

#### Get Transactions

Get a list of financial transactions with various filtering options.

**URL**: `/trx/transactions`  
**Method**: `GET`  
**Auth required**: Yes  

**Query Parameters**:
- `skip` (integer, default=0) - Number of items to skip
- `limit` (integer, default=50) - Number of items to return
- `start_date` (string, optional) - Filter by start date
- `end_date` (string, optional) - Filter by end date
- `account_id` (integer, optional) - Filter by account ID
- `category_id` (integer, optional) - Filter by category ID
- `type` (string, optional) - Filter by type: 'income', 'expense', or 'transfer'
- `search` (string, optional) - Search in description and notes

**Success Response**: `200 OK`
```json
{
  "data": [
    {
      "transaction_id": 0,
      "uuid": "string",
      "user_id": 0,
      "amount": "100.00",
      "type": "income",
      "description": "string",
      "date": "2023-01-01T00:00:00.000Z",
      "account_id": 0,
      "category_id": 0,
      "transfer_account_id": null,
      "notes": "string",
      "created_at": "2023-01-01T00:00:00.000Z",
      "updated_at": "2023-01-01T00:00:00.000Z",
      "account": {
        "name": "string",
        "type": "bank_account"
      },
      "category": {
        "name": "string",
        "type": "income",
        "icon": "string",
        "color": "string"
      },
      "transfer_account": null
    }
  ],
  "total": 100,
  "has_more": true,
  "message": "Success"
}
```

#### Get Transaction Trends

Get transaction trends over a specified period.

**URL**: `/trx/transactions/trends`  
**Method**: `GET`  
**Auth required**: Yes  

**Query Parameters**:
- `period` (string, default="month") - Period type: 'day', 'week', 'month', 'year', or 'all'
- `start_date` (string, optional) - Custom start date (overrides period)
- `end_date` (string, optional) - Custom end date (overrides period)
- `group_by` (string, default="day") - Group results by: 'day', 'week', 'month', or 'year'
- `account_id` (integer, optional) - Filter by account ID

**Success Response**: `200 OK`
```json
{
  "period": {
    "start_date": "2023-01-01T00:00:00Z",
    "end_date": "2023-01-31T23:59:59Z",
    "period_type": "month",
    "group_by": "day"
  },
  "trends": [
    {
      "date": "2023-01-01",
      "income": "500.0",
      "expense": "200.0",
      "transfer": "0.0",
      "net": "300.0"
    },
    {
      "date": "2023-01-02",
      "income": "0.0",
      "expense": "150.0",
      "transfer": "100.0",
      "net": "-150.0"
    }
  ]
}
```

## Security

The API uses OAuth2 with password flow for authentication. Security is implemented using:

```
OAuth2PasswordBearer: {
  "type": "oauth2",
  "flows": {
    "password": {
      "scopes": {},
      "tokenUrl": "auth/login"
    }
  }
}
```