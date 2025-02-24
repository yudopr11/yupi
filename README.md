# yupi API Documentation

A FastAPI-based API for blog management with authentication.

## Authentication Endpoints

### Register New User (Superuser Only)
```http
POST /auth/register
```
**Required Headers:**
- `Authorization: Bearer <token>` (Superuser token required)

**Request Body:**
```json
{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "strongpassword123",
    "is_superuser": false
}
```

**Response:** `201 Created`
```json
{
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "username": "johndoe",
    "email": "john@example.com",
    "is_superuser": false,
    "created_at": "2024-03-20T10:00:00"
}
```

### Login
```http
POST /auth/login
```
**Request Body (form-data):**
- `username`: string
- `password`: string

**Response:** `200 OK`
```json
{
    "access_token": "eyJhbGciOiJIUzI1...",
    "token_type": "bearer"
}
```

### Delete User (Superuser Only)
```http
DELETE /auth/users/{user_id}
```
**Required Headers:**
- `Authorization: Bearer <token>` (Superuser token required)

**Response:** `200 OK`
```json
{
    "message": "User has been deleted successfully",
    "deleted_user": {
        "id": 1,
        "username": "johndoe",
        "uuid": "123e4567-e89b-12d3-a456-426614174000"
    }
}
```

## Blog Endpoints

### Create New Post
```http
POST /blog
```
**Required Headers:**
- `Authorization: Bearer <token>`

**Request Body:**
```json
{
    "title": "My First Blog Post",
    "excerpt": "A brief introduction to my blog post",
    "content": "# Introduction\n\nThis is my first blog post...",
    "tags": ["tech", "programming"],
    "published": false
}
```

**Response:** `201 Created`
```json
{
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "title": "My First Blog Post",
    "excerpt": "A brief introduction to my blog post",
    "content": "# Introduction\n\nThis is my first blog post...",
    "slug": "my-first-blog-post",
    "reading_time": 5,
    "tags": ["tech", "programming"],
    "published": false,
    "created_at": "2024-03-20T10:00:00",
    "updated_at": "2024-03-20T10:00:00"
}
```

### Get All Published Posts
```http
GET /blog
```
**Query Parameters:**
- `skip`: int (default: 0) - Pagination offset
- `limit`: int (default: 3) - Posts per page
- `search`: string (optional) - Search in title, excerpt, and content

**Response:** `200 OK`
```json
[
    {
        "id": 1,
        "uuid": "123e4567-e89b-12d3-a456-426614174000",
        "title": "My First Blog Post",
        "excerpt": "A brief introduction to my blog post",
        "slug": "my-first-blog-post",
        "reading_time": 5,
        "tags": ["tech", "programming"],
        "published": true
    }
]
```

### Get Post by Slug
```http
GET /blog/{slug}
```

**Response:** `200 OK`
```json
{
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "title": "My First Blog Post",
    "excerpt": "A brief introduction to my blog post",
    "content": "# Introduction\n\nThis is my first blog post...",
    "slug": "my-first-blog-post",
    "reading_time": 5,
    "tags": ["tech", "programming"],
    "published": true,
    "created_at": "2024-03-20T10:00:00",
    "updated_at": "2024-03-20T10:00:00"
}
```

### Update Post (Author or Superuser Only)
```http
PUT /blog/admin/{post_id}
```
**Required Headers:**
- `Authorization: Bearer <token>` (Post author or superuser)

**Request Body:**
```json
{
    "title": "Updated Blog Post",
    "excerpt": "Updated brief introduction",
    "content": "# Updated Content\n\nThis is the updated content...",
    "tags": ["tech", "tutorial"],
    "published": true
}
```

**Response:** `200 OK`
```json
{
    "id": 1,
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "title": "Updated Blog Post",
    "excerpt": "Updated brief introduction",
    "content": "# Updated Content\n\nThis is the updated content...",
    "slug": "updated-blog-post",
    "reading_time": 5,
    "tags": ["tech", "tutorial"],
    "published": true,
    "created_at": "2024-03-20T10:00:00",
    "updated_at": "2024-03-20T10:30:00"
}
```

### Delete Post (Superuser Only)
```http
DELETE /blog/admin/{post_id}
```
**Required Headers:**
- `Authorization: Bearer <token>` (Superuser token required)

**Response:** `200 OK`
```json
{
    "message": "Post has been deleted successfully",
    "deleted_post": {
        "id": 1,
        "title": "Updated Blog Post",
        "uuid": "123e4567-e89b-12d3-a456-426614174000"
    }
}
```

## Split Bill Endpoints

### Analyze Bill Image
```http
POST /splitbill/analyze
```
**Required Headers:**
- `Authorization: Bearer <token>`

**Request Body (form-data):**
- `image`: file (JPEG, PNG, JPG, or WebP, max 5MB)
- `description`: string (Description of who ordered what)

**Example Description:**
```text
Alice ordered:
- Nasi Goreng Special
- Es Teh Manis

Bob ordered:
- Mie Goreng
- Juice Alpukat
- Extra Kerupuk
```

**Response:** `200 OK`
```json
{
    "split_details": {
        "Alice": {
            "items": [
                {"item": "Nasi Goreng Special", "price": 25000},
                {"item": "Es Teh Manis", "price": 5000}
            ],
            "individual_total": 30000,
            "vat_share": 3300,
            "other_share": 2000,
            "discount_share": 1500,
            "final_total": 33800
        },
        "Bob": {
            "items": [
                {"item": "Mie Goreng", "price": 23000},
                {"item": "Juice Alpukat", "price": 15000},
                {"item": "Extra Kerupuk", "price": 5000}
            ],
            "individual_total": 43000,
            "vat_share": 4730,
            "other_share": 2000,
            "discount_share": 2150,
            "final_total": 47580
        }
    },
    "total_bill": 73000,
    "total_vat": 8030,
    "total_other": 4000,
    "total_discount": 3650,
    "currency": "IDR"
}
```

**Error Responses:**

### 413 File Too Large
```json
{
    "detail": "File size too large. Maximum size allowed is 5MB"
}
```

### 415 Unsupported Media Type
```json
{
    "detail": "File type not allowed. Only image/jpeg, image/png, image/jpg, image/webp are allowed"
}
```

### Notes:
1. The API uses OpenAI's GPT-4o to analyze the bill image, AI can be wrong
2. VAT (11%) is automatically applied for Indonesian Rupiah if not stated in the bill
3. Service charges and other fees are split equally among all individuals
4. Discounts are handled in two ways:
   - Percentage-based discounts: Distributed proportionally based on order totals
   - Fixed-amount discounts: Split equally among all individuals
5. Crossed-out prices in the bill are ignored (considered marketing displays)
6. All monetary calculations are rounded to 2 decimal places

## Error Responses

### 401 Unauthorized
```json
{
    "detail": "Not authenticated"
}
```

### 403 Forbidden
```json
{
    "detail": "Only superuser can perform this action"
}
```

### 404 Not Found
```json
{
    "detail": "Post not found"
}
```

### 422 Validation Error
```json
{
    "detail": [
        {
            "loc": ["body", "field_name"],
            "msg": "field required",
            "type": "value_error.missing"
        }
    ]
}
``` 