# yupi API Documentation

This document provides detailed information about all available endpoints in the Yupi API.

## Table of Contents

- [Authentication](#authentication)
  - [Register](#register)
  - [Login](#login)
  - [Refresh Token](#refresh-token)
  - [Logout](#logout)
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

**Success Response**: `201 Created`
```json
{
  "id": 0,
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

### Get All Users

Get a list of all users (superuser only).

**URL**: `/auth/users`  
**Method**: `GET`  
**Auth required**: Yes (Superuser)  

**Success Response**: `200 OK`
```json
[
  {
    "id": 0,
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

## Blog Management

### Create Post

Create a new blog post.

**URL**: `/blog/admin`  
**Method**: `POST`  
**Auth required**: Yes (Any authenticated user)  
**Status Code**: `200 OK`

**Request Body**:
```json
{
  "title": "string",
  "content": "string",
  "excerpt": "string (optional)",
  "tags": ["string"] (optional),
  "published": true
}
```

**Notes**:
- If `excerpt` is not provided, it will be automatically generated using AI
- If `tags` are not provided, they will be automatically generated using AI based on the content and existing tags in the system
- Post reading time is automatically calculated
- URL-friendly slug is automatically generated from the title
- Post embeddings for vector search are generated using the title, excerpt, and a preview of the content

**Success Response**: `200 OK`
```json
{
  "id": 0,
  "uuid": "string",
  "title": "string",
  "slug": "string",
  "content": "string",
  "excerpt": "string",
  "tags": ["string"],
  "reading_time": 0,
  "published": true,
  "created_at": "2023-01-01T00:00:00.000Z",
  "updated_at": "2023-01-01T00:00:00.000Z",
  "author": {
    "id": 0,
    "username": "string"
  }
}
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `422 Unprocessable Entity` - Validation error

### Get Posts

Get all published blog posts. Supports pagination and filtering.

**URL**: `/blog`  
**Method**: `GET`  
**Auth required**: No  

**Query Parameters:**

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `skip` | integer | Number of posts to skip (default: 0) |
| `limit` | integer | Number of posts per page (default: 3) |
| `search` | string | Search query to filter posts by title or content |
| `tag` | string | Filter posts by tag (case-insensitive) |
| `published_status` | string | Filter by publication status: 'published' (default), 'unpublished', or 'all' |
| `use_rag` | boolean | When true and search is provided, uses vector search with OpenAI embeddings (default: false) |

**Success Response**: `200 OK`
```json
{
  "items": [
    {
      "id": 0,
      "title": "string",
      "excerpt": "string",
      "reading_time": 0,
      "tags": ["string"],
      "author": {
        "id": 0,
        "username": "string",
        "email": "string"
      },
      "created_at": "2023-01-01T00:00:00.000Z",
      "slug": "string",
      "published": true
    }
  ],
  "total_count": 0,
  "has_more": false,
  "limit": 3,
  "skip": 0
}
```

**Error Responses**:
- `422 Unprocessable Entity` - Invalid query parameters

### Get Post by Slug

Get a specific blog post by its slug.

**URL**: `/blog/{slug}`  
**Method**: `GET`  
**Auth required**: No  
**Status Code**: `200 OK`

**URL Parameters**:
- `slug` - The slug of the post to retrieve

**Success Response**: `200 OK`
```json
{
  "id": 0,
  "uuid": "string",
  "title": "string",
  "slug": "string",
  "content": "string",
  "excerpt": "string",
  "tags": ["string"],
  "reading_time": 0,
  "published": true,
  "created_at": "2023-01-01T00:00:00.000Z",
  "updated_at": "2023-01-01T00:00:00.000Z",
  "author": {
    "id": 0,
    "username": "string",
    "email": "string"
  }
}
```

**Error Responses**:
- `404 Not Found` - Post not found

### Update Post

Update a blog post by ID (author or superuser only).

**URL**: `/blog/admin/{post_id}`  
**Method**: `PUT`  
**Auth required**: Yes (Post author or Superuser)  
**Status Code**: `200 OK`

**URL Parameters**:
- `post_id` - The ID of the post to update

**Request Body**:
```json
{
  "title": "string",
  "content": "string",
  "excerpt": "string (optional)",
  "tags": ["string"] (optional),
  "published": true
}
```

**Notes**:
- If `excerpt` is not provided or empty, it will be automatically regenerated using AI
- If `tags` are not provided or empty, they will be automatically generated using AI based on the content and existing tags in the system
- Slug is automatically updated if title changes
- Reading time is recalculated if content changes
- Post embeddings are regenerated if title or excerpt changes

**Success Response**: `200 OK`
```json
{
  "id": 0,
  "uuid": "string",
  "title": "string",
  "slug": "string",
  "content": "string",
  "excerpt": "string",
  "tags": ["string"],
  "reading_time": 0,
  "published": true,
  "created_at": "2023-01-01T00:00:00.000Z",
  "updated_at": "2023-01-01T00:00:00.000Z",
  "author": {
    "id": 0,
    "username": "string",
    "email": "string"
  }
}
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not enough permissions (not the author)
- `404 Not Found` - Post not found
- `422 Unprocessable Entity` - Validation error

### Delete Post

Delete a blog post by ID (superuser only).

**URL**: `/blog/admin/{post_id}`  
**Method**: `DELETE`  
**Auth required**: Yes (Superuser)  
**Status Code**: `200 OK`

**URL Parameters**:
- `post_id` - The ID of the post to delete

**Success Response**: `200 OK`
```json
{
  "message": "Post has been deleted successfully",
  "deleted_item": {
    "id": 0,
    "title": "string",
    "uuid": "string"
  }
}
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not enough permissions
- `404 Not Found` - Post not found

## Bill Splitting

### Analyze Bill Image

Analyze a bill image to extract items and suggest how to split the costs.

**URL**: `/splitbill/analyze`  
**Method**: `POST`  
**Auth required**: Yes  
**Content-Type**: `multipart/form-data`  

**Request Parameters**:
- `image`: Image file (JPEG, PNG, WEBP)
- `description`: String describing how to split the bill
- `image_description`: Optional pre-analyzed image text (if already processed)

**Notes**:
- Maximum file size: 5MB
- Supported image formats: JPEG, PNG, WEBP
- The API uses OpenAI's vision model to extract items from the bill image
- If image_description is provided, the image processing step is skipped

**Success Response**: `200 OK`
```json
{
  "split_details": {
    "person_name": {
      "items": [
        {
          "item": "string",
          "price": "string"
        }
      ],
      "individual_total": "string",
      "vat_share": "string",
      "other_share": "string",
      "discount_share": "string",
      "final_total": "string"
    }
  },
  "total_bill": "string",
  "subtotal": "string",
  "subtotal_vat": "string",
  "subtotal_other": "string",
  "subtotal_discount": "string",
  "currency": "string",
  "image_description": "string",
  "token_count": {
    "image": 0,
    "analysis": 0
  }
}
```

**Error Responses**:
- `400 Bad Request` - Invalid bill image
- `401 Unauthorized` - Not authenticated
- `413 Request Entity Too Large` - File too large (>5MB)
- `415 Unsupported Media Type` - Unsupported file type
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Processing error

## Personal Transactions

Personal finance tracking system with accounts, categories, and transactions.

### Account Management

#### Create Account

Create a new financial account.

**URL**: `/personal-transactions/accounts`  
**Method**: `POST`  
**Auth required**: Yes  

**Request Body**:
```json
{
  "name": "string",
  "type": "string",
  "description": "string",
  "limit": 0.00
}
```

**Notes**:
- `type` options: "bank_account", "credit_card", "other"
- `limit` is required for "credit_card" accounts
- `description` is optional

**Success Response**: `200 OK`
```json
{
  "data": {
    "account_id": 0,
    "uuid": "string",
    "name": "string",
    "type": "string",
    "description": "string",
    "limit": 0.00,
    "user_id": 0,
    "created_at": "2023-01-01T00:00:00.000Z",
    "updated_at": "2023-01-01T00:00:00.000Z"
  },
  "message": "Success"
}
```

**Error Responses**:
- `400 Bad Request` - Missing required fields
- `401 Unauthorized` - Not authenticated
- `422 Unprocessable Entity` - Validation error

#### Update Account

Update an existing account.

**URL**: `/personal-transactions/accounts/{account_id}`  
**Method**: `PUT`  
**Auth required**: Yes  

**URL Parameters**:
- `account_id` - The ID of the account to update

**Request Body**:
```json
{
  "name": "string",
  "type": "string",
  "description": "string",
  "limit": 0.00
}
```

**Notes**:
- `type` options: "bank_account", "credit_card", "other"
- `limit` is required for "credit_card" accounts
- `description` is optional

**Success Response**: `200 OK`
```json
{
  "data": {
    "account_id": 0,
    "uuid": "string",
    "name": "string",
    "type": "string",
    "description": "string",
    "limit": 0.00,
    "user_id": 0,
    "created_at": "2023-01-01T00:00:00.000Z",
    "updated_at": "2023-01-01T00:00:00.000Z"
  },
  "message": "Success"
}
```

**Error Responses**:
- `400 Bad Request` - Missing required fields
- `401 Unauthorized` - Not authenticated
- `404 Not Found` - Account not found
- `422 Unprocessable Entity` - Validation error

#### Delete Account

Delete an account.

**URL**: `/personal-transactions/accounts/{account_id}`  
**Method**: `DELETE`  
**Auth required**: Yes  

**URL Parameters**:
- `account_id` - The ID of the account to delete

**Success Response**: `200 OK`
```json
{
  "message": "Account with id {account_id} deleted successfully",
  "deleted_item": {
    "id": 0,
    "uuid": "string",
    "name": "string",
    "type": "string"
  }
}
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `404 Not Found` - Account not found

#### Get Account Balance

Get the current balance of an account.

**URL**: `/personal-transactions/accounts/{account_id}/balance`  
**Method**: `GET`  
**Auth required**: Yes  

**URL Parameters**:
- `account_id` - The ID of the account

**Success Response**: `200 OK`
```json
{
  "data": {
    "account_id": 0,
    "balance": 0.00,
    "total_income": 0.00,
    "total_expenses": 0.00,
    "total_transfers_in": 0.00,
    "total_transfers_out": 0.00,
    "account": {
      "account_id": 0,
      "uuid": "string",
      "name": "string",
      "type": "string",
      "description": "string",
      "limit": 0.00,
      "user_id": 0,
      "created_at": "2023-01-01T00:00:00.000Z",
      "updated_at": "2023-01-01T00:00:00.000Z"
    }
  },
  "message": "Success"
}
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `404 Not Found` - Account not found

#### Get All Accounts

Get a list of all user accounts with current balances.

**URL**: `/personal-transactions/accounts`  
**Method**: `GET`  
**Auth required**: Yes  

**Query Parameters**:
- `account_type` - Optional filter by account type

**Success Response**: `200 OK`
```json
[
  {
    "account_id": 0,
    "uuid": "string",
    "name": "string",
    "type": "string",
    "description": "string",
    "limit": 0.00,
    "user_id": 0,
    "created_at": "2023-01-01T00:00:00.000Z",
    "updated_at": "2023-01-01T00:00:00.000Z",
    "balance": 0.00
  }
]
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated

### Category Management

#### Create Category

Create a new transaction category.

**URL**: `/personal-transactions/categories`  
**Method**: `POST`  
**Auth required**: Yes  

**Request Body**:
```json
{
  "name": "string",
  "type": "string"
}
```

**Notes**:
- `type` options: "income", "expense"

**Success Response**: `200 OK`
```json
{
  "data": {
    "category_id": 0,
    "uuid": "string",
    "name": "string",
    "type": "string",
    "user_id": 0,
    "created_at": "2023-01-01T00:00:00.000Z",
    "updated_at": "2023-01-01T00:00:00.000Z"
  },
  "message": "Success"
}
```

**Error Responses**:
- `400 Bad Request` - Missing required fields
- `401 Unauthorized` - Not authenticated
- `422 Unprocessable Entity` - Validation error

#### Update Category

Update an existing category.

**URL**: `/personal-transactions/categories/{category_id}`  
**Method**: `PUT`  
**Auth required**: Yes  

**URL Parameters**:
- `category_id` - The ID of the category to update

**Request Body**:
```json
{
  "name": "string",
  "type": "string"
}
```

**Success Response**: `200 OK`
```json
{
  "data": {
    "category_id": 0,
    "uuid": "string",
    "name": "string",
    "type": "string",
    "user_id": 0,
    "created_at": "2023-01-01T00:00:00.000Z",
    "updated_at": "2023-01-01T00:00:00.000Z"
  },
  "message": "Success"
}
```

**Error Responses**:
- `400 Bad Request` - Missing required fields
- `401 Unauthorized` - Not authenticated
- `404 Not Found` - Category not found
- `422 Unprocessable Entity` - Validation error

#### Delete Category

Delete a category.

**URL**: `/personal-transactions/categories/{category_id}`  
**Method**: `DELETE`  
**Auth required**: Yes  

**URL Parameters**:
- `category_id` - The ID of the category to delete

**Success Response**: `200 OK`
```json
{
  "message": "Category with id {category_id} deleted successfully",
  "deleted_item": {
    "id": 0,
    "uuid": "string",
    "name": "string",
    "type": "string"
  }
}
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `404 Not Found` - Category not found

#### Get All Categories

Get a list of all user categories.

**URL**: `/personal-transactions/categories`  
**Method**: `GET`  
**Auth required**: Yes  

**Query Parameters**:
- `category_type` - Optional filter by category type

**Success Response**: `200 OK`
```json
[
  {
    "category_id": 0,
    "uuid": "string",
    "name": "string",
    "type": "string",
    "user_id": 0,
    "created_at": "2023-01-01T00:00:00.000Z",
    "updated_at": "2023-01-01T00:00:00.000Z"
  }
]
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated

### Transaction Management

#### Create Transaction

Create a new financial transaction.

**URL**: `/personal-transactions/transactions`  
**Method**: `POST`  
**Auth required**: Yes  

**Request Body**:
```json
{
  "amount": 0.00,
  "description": "string",
  "transaction_date": "2023-01-01T00:00:00.000Z",
  "transaction_type": "string",
  "account_id": 0,
  "category_id": 0,
  "destination_account_id": 0
}
```

**Notes**:
- `transaction_type` options: "income", "expense", "transfer"
- `destination_account_id` is required only for "transfer" type transactions
- `category_id` is optional (required for "income" and "expense" types)

**Success Response**: `200 OK`
```json
{
  "data": {
    "transaction_id": 0,
    "uuid": "string",
    "amount": 0.00,
    "description": "string",
    "transaction_date": "2023-01-01T00:00:00.000Z",
    "transaction_type": "string",
    "account_id": 0,
    "category_id": 0,
    "destination_account_id": 0,
    "user_id": 0,
    "created_at": "2023-01-01T00:00:00.000Z",
    "updated_at": "2023-01-01T00:00:00.000Z",
    "account": {
      "account_id": 0,
      "name": "string",
      "type": "string"
    },
    "category": {
      "category_id": 0,
      "name": "string",
      "type": "string"
    },
    "destination_account": {
      "account_id": 0,
      "name": "string",
      "type": "string"
    }
  },
  "message": "Success"
}
```

**Error Responses**:
- `400 Bad Request` - Missing required fields or invalid transaction type
- `401 Unauthorized` - Not authenticated
- `404 Not Found` - Account or category not found
- `422 Unprocessable Entity` - Validation error

#### Update Transaction

Update an existing transaction.

**URL**: `/personal-transactions/transactions/{transaction_id}`  
**Method**: `PUT`  
**Auth required**: Yes  

**URL Parameters**:
- `transaction_id` - The ID of the transaction to update

**Request Body**:
```json
{
  "amount": 0.00,
  "description": "string",
  "transaction_date": "2023-01-01T00:00:00.000Z",
  "transaction_type": "string",
  "account_id": 0,
  "category_id": 0,
  "destination_account_id": 0
}
```

**Success Response**: `200 OK`
```json
{
  "data": {
    "transaction_id": 0,
    "uuid": "string",
    "amount": 0.00,
    "description": "string",
    "transaction_date": "2023-01-01T00:00:00.000Z",
    "transaction_type": "string",
    "account_id": 0,
    "category_id": 0,
    "destination_account_id": 0,
    "user_id": 0,
    "created_at": "2023-01-01T00:00:00.000Z",
    "updated_at": "2023-01-01T00:00:00.000Z",
    "account": {
      "account_id": 0,
      "name": "string",
      "type": "string"
    },
    "category": {
      "category_id": 0,
      "name": "string",
      "type": "string"
    },
    "destination_account": {
      "account_id": 0,
      "name": "string",
      "type": "string"
    }
  },
  "message": "Success"
}
```

**Error Responses**:
- `400 Bad Request` - Missing required fields or invalid transaction type
- `401 Unauthorized` - Not authenticated
- `404 Not Found` - Transaction, account, or category not found
- `422 Unprocessable Entity` - Validation error

#### Delete Transaction

Delete a transaction.

**URL**: `/personal-transactions/transactions/{transaction_id}`  
**Method**: `DELETE`  
**Auth required**: Yes  

**URL Parameters**:
- `transaction_id` - The ID of the transaction to delete

**Success Response**: `200 OK`
```json
{
  "message": "Transaction with id {transaction_id} deleted successfully",
  "deleted_item": {
    "id": 0,
    "uuid": "string",
    "description": "string",
    "amount": 0.00,
    "transaction_type": "string"
  }
}
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `404 Not Found` - Transaction not found

#### Get All Transactions

Get a list of user transactions with filtering options.

**URL**: `/personal-transactions/transactions`  
**Method**: `GET`  
**Auth required**: Yes  

**Query Parameters**:
- `account_name` - Optional filter by account name
- `category_name` - Optional filter by category name
- `start_date` - Optional filter for transactions after this date
- `end_date` - Optional filter for transactions before this date
- `date_filter_type` - Optional filter by predefined date range
- `limit` - Number of transactions to return (default: 10)
- `skip` - Number of transactions to skip (for pagination, default: 0)

**Success Response**: `200 OK`
```json
{
  "data": [
    {
      "transaction_id": 0,
      "uuid": "string",
      "amount": 0.00,
      "description": "string",
      "transaction_date": "2023-01-01T00:00:00.000Z",
      "transaction_type": "string",
      "account_id": 0,
      "category_id": 0,
      "destination_account_id": 0,
      "user_id": 0,
      "created_at": "2023-01-01T00:00:00.000Z",
      "updated_at": "2023-01-01T00:00:00.000Z",
      "account": {
        "name": "string"
      },
      "category": {
        "name": "string",
        "type": "string"
      },
      "destination_account": {
        "name": "string"
      }
    }
  ],
  "total_count": 0,
  "has_more": false,
  "limit": 10,
  "skip": 0,
  "message": "Success"
}
```

**Error Responses**:
- `401 Unauthorized` - Not authenticated
- `422 Unprocessable Entity` - Invalid query parameters