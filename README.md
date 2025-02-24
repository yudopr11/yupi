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
- 2 Nasi Goreng Special
- 1 Es Teh Manis

Bob ordered:
- 1 Mie Goreng
- 2 Juice Alpukat
- 1 Extra Kerupuk
```

**Response:** `200 OK`
```json
{
    "split_details": {
        "Alice": {
            "items": [
                {"item": "Nasi Goreng Special", "price": 55000},
                {"item": "Es Teh Manis", "price": 5000}
            ],
            "individual_total": 115000,
            "vat_share": 12650,
            "other_share": 2000,
            "discount_share": 5750,
            "final_total": 123900
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
    "total_bill": 171480,
    "total_vat": 17380,
    "total_other": 4000,
    "total_discount": 7900,
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
1. The API uses OpenAI's models to analyze the bill image
2. Item Quantity Handling:
   - Quantities are automatically detected (e.g., "2 Nasi Goreng 110000" means 2 items at 55000 each)
   - Unit prices are calculated by dividing total price by quantity
   - Individual items are listed with their unit prices, not total prices
3. Bill Summary Section:
   - If the bill has a summary section, those exact values are used
   - Summary typically includes: Items Total, VAT, Service Charge, and Final Total
   - These values are used as-is rather than being recalculated
4. VAT Calculation:
   - Uses exact VAT amount if shown in bill summary
   - If not shown: 11% for Indonesian Rupiah, or as stated for other currencies
   - Calculated proportionally based on individual order totals
5. Service Charges:
   - Uses exact amount if shown in summary section
   - Split equally among all individuals
6. Discounts are handled in two ways:
   - Percentage-based discounts: Distributed proportionally based on order totals
   - Fixed-amount discounts: Split equally among all individuals
7. Important:
   - Crossed-out prices in the bill are ignored (considered marketing displays)
   - All monetary calculations are rounded to 2 decimal places
   - The sum of all individual shares always equals the total bill
   - Quantities are always considered when calculating unit prices

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