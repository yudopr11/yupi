from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from openai import OpenAI
import json, base64
from datetime import datetime, timedelta
from collections import defaultdict

from app.utils.auth import get_current_user
from app.models.user import User
from app.schemas.bill import BillAnalysisResponse
from app.schemas.error import ErrorDetail
from app.core.config import settings

router = APIRouter(
    prefix="/splitbill",
    tags=["Bill Analysis"]
    )

# In-memory rate limiting storage
# Structure: {ip_address: {date: count}}
request_counts = defaultdict(lambda: defaultdict(int))
last_cleanup = datetime.now()

# Rate limiting constants
GUEST_RATE_LIMIT = 3  # Max requests per day for guest users
CLEANUP_INTERVAL = timedelta(hours=1)  # Clean old records every hour

def cleanup_old_records():
    """
    Remove rate limiting records older than 1 day to prevent memory leaks
    
    This function is called periodically to clean up old rate limiting records
    and prevent unbounded memory growth. It removes all records older than 24 hours.
    """
    global last_cleanup
    now = datetime.now()
    
    # Only run cleanup every CLEANUP_INTERVAL
    if now - last_cleanup < CLEANUP_INTERVAL:
        return
        
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    for ip in list(request_counts.keys()):
        for date in list(request_counts[ip].keys()):
            if date < yesterday:
                del request_counts[ip][date]
        # Remove IP entries with no dates
        if not request_counts[ip]:
            del request_counts[ip]
            
    last_cleanup = now

# Define allowed image MIME types
ALLOWED_IMAGE_TYPES = [
    'image/jpeg',
    'image/png',
    'image/jpg',
    'image/webp',
]

def validate_image(file: UploadFile) -> None:
    """
    Validate that the uploaded file is an image and meets size requirements
    
    This function checks if the uploaded file:
    1. Has an allowed MIME type
    2. Is under the maximum file size limit (5MB)
    
    Args:
        file (UploadFile): The uploaded file to validate
        
    Raises:
        HTTPException: If file type is not allowed or file is too large
    """
    if not file.content_type in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type not allowed. Only {', '.join(ALLOWED_IMAGE_TYPES)} are allowed"
        )
    
    # Optional: Check file size (e.g., max 5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes
    try:
        file.file.seek(0, 2)  # Seek to end of file
        file_size = file.file.tell()  # Get file size
        file.file.seek(0)  # Reset file pointer to beginning
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size too large. Maximum size allowed is 5MB"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not validate file size"
        )

async def _analyze_bill(
    image: UploadFile,
    description: str,
    image_description: str = None,
    model: str = "o3-mini",
    temperature: float = 1
):
    """
    Internal helper function to analyze bill images using OpenAI's vision and language models
    
    This function performs the core bill analysis by:
    1. Validating and processing the uploaded image
    2. Using GPT-4 Vision to analyze the bill image if no description is provided
    3. Using the specified model to generate a detailed breakdown of the bill
    4. Calculating individual shares, VAT, service charges, and discounts
    
    Args:
        image (UploadFile): The bill image to analyze
        description (str): Order details description
        image_description (str, optional): Pre-analyzed image description
        model (str): OpenAI model to use for analysis
        temperature (float): Temperature parameter for model generation
        
    Returns:
        dict: Detailed bill analysis including individual shares and totals
        
    Raises:
        HTTPException: If image is invalid or analysis fails
    """
    try:
        # Initialize OpenAI client with API key from settings
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        image_tokens = 0
        analysis_tokens = 0

        # If image_description is not provided or empty, validate and process the image
        if image_description is None or image_description.strip() == "":
            # Validate image file
            validate_image(image)
            
            # Read image bytes
            image_bytes = await image.read()
            # Convert to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            # Create data URL
            mime_type = image.content_type
            image_data_url = f"data:{mime_type};base64,{image_base64}"

            # Get image description
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                messages=[
                    {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": """Analyze this image and determine if it's a bill/receipt:
Task:
1. First, determine if the image is a bill/receipt
2. If NOT a bill/receipt, output exactly "0"
3. If it IS a bill/receipt, provide a detailed description\
Do not add any explanatory text or labels - just output the raw information."""
                        },
                        {"type": "image_url", "image_url": {"url": image_data_url}}
                    ]
                }],
                # max_completion_tokens=1000
            )

            image_tokens = response.usage.total_tokens
            image_description = response.choices[0].message.content

            try:
                if float(image_description) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid bill image"
                    )
            except ValueError:
                # If conversion fails, it means image_description is not a number
                # so we can proceed with the analysis
                pass
        
        # Generate prompt
        prompt = f'''
You are analyzing a bill below 
{image_description}

with the following order details description:
{description}

Task: Create a detailed breakdown of individual payments including items, shared costs, and adjustments.

1. Item Analysis:
- Pay careful attention to quantities (e.g., if bill shows "2 Nasi Goreng 110000", the unit price is 55000)
- For each item line:
    * Extract the quantity (number at the start of line)
    * Total price is shown in the amount column
    * Calculate unit price = total price ÷ quantity
    * List each item with its UNIT price (not the total price)
- Ensure prices match exactly as shown in the bill after quantity calculation
- Do not include crossed-out prices (these are marketing displays, not actual prices)
- Be aware that price formats vary by currency (e.g., "1,234.56", "1.234,56", "1 234,56")

2. Currency Detection:
- Identify and use the exact currency shown in the bill
- Format all monetary values consistently using the detected currency
- Recognize different price formatting conventions:
  * Some currencies use "." as decimal separator and "," as thousands separator (e.g., USD: $1,234.56)
  * Others use "," as decimal separator and "." as thousands separator (e.g., EUR: €1.234,56)
  * Some use spaces as thousands separators (e.g., 1 234,56)
- Correctly parse prices according to the detected currency's format

3. Tax (VAT) Calculation:
- Use the VAT rate shown in the bill or from order details description
- Calculate individual VAT shares proportionally based on each person's order total
- Round VAT calculations to nearest integer

4. Service Charges & Additional Fees:
- Identify all service charges and additional fees
- Divide these costs equally among all individuals
- Include items like: service charge, packaging fees, delivery fees, etc.

5. Discount Handling:
For percentage-based discounts (e.g., "20% off"):
- Calculate the total discount amount
- Distribute proportionally based on each person's order total

For fixed-amount discounts (e.g., "5000 off delivery"):
- Divide equally among all individuals

6. Individual Final Calculations:
- Calculate individual_total = sum of (unit_price × quantity) for each person's items
- Calculate vat_share = proportional VAT based on individual_total
- Calculate other_share = equal split of service charges and fees
- Calculate discount_share = proportional or equal split of discounts
- Calculate final_total = individual_total + vat_share + other_share - discount_share

7. Total Calculations:
- Calculate total_bill = sum of final_total for all individuals
- Calculate subtotal = sum of individual_total for all individuals
- Calculate subtotal_vat = sum of vat_share for all individuals
- Calculate subtotal_other = sum of other_share for all individuals
- Calculate subtotal_discount = sum of discount_share for all individuals

Important Notes:
- Always divide total item price by quantity to get the correct unit price
- Crossed out prices are marketing displays, NOT discounts
- All calculations must be mathematically precise
- All monetary values must be in integer format
- The sum of all individual shares must equal the total bill

Return the analysis in this exact JSON structure:
{{
"split_details": {{
    "person_name": {{
        "items": [
            {{"item": "exact_item_name_from_bill", "price": unit_price_after_quantity_calculation}}
        ],
        "individual_total": integer,
        "vat_share": integer,
        "other_share": integer,
        "discount_share": integer,
        "final_total": integer
    }}
}},
"total_bill": integer,
"subtotal": integer,
"subtotal_vat": integer,
"subtotal_other": integer,
"subtotal_discount": integer,
"currency": "currency_code"
}}

Ensure the response is valid JSON with no additional text or explanations.
'''
        
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {
                "role": "user",
                "content":  prompt
            }]
        )
        # Clean the response and convert to JSON
        content = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
        result = json.loads(content)
        
        # Check if the response contains an error
        if 'error' in result:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"The bill analysis failed: {result['error']}"
            )
            
        # Make sure all required fields are present
        required_fields = ['split_details', 'total_bill', 'subtotal', 'subtotal_vat', 
                          'subtotal_other', 'subtotal_discount', 'currency']
        missing_fields = [field for field in required_fields if field not in result]
        
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Missing required fields in analysis result: {', '.join(missing_fields)}"
            )

        # Add the image_description and token counts to the result
        result["image_description"] = image_description
        analysis_tokens = response.usage.total_tokens
        result["token_count"] = {
            "image": image_tokens,
            "analysis": analysis_tokens
        }
        
        # Return the complete result
        return BillAnalysisResponse(**result)
    
    except HTTPException as http_ex:
        # Re-raise HTTP exceptions (like 415, 413, etc.) without modification
        raise http_ex
    except Exception as e:
        # Handle other unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while analyzing the bill: {str(e)}"
        ) 

@router.post(
    "/analyze",
    response_model=BillAnalysisResponse,
    responses={
        400: {"model": ErrorDetail, "description": "Invalid bill image"},
        401: {"model": ErrorDetail, "description": "Not authenticated"},
        413: {"model": ErrorDetail, "description": "File too large"},
        415: {"model": ErrorDetail, "description": "Unsupported file type"},
        422: {"model": ErrorDetail, "description": "Validation error"},
        429: {"model": ErrorDetail, "description": "Rate limit exceeded"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def analyze_bill(
    request: Request,
    image: UploadFile = File(...),
    description: str = Form(...),
    image_description: str = Form(None),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze a bill image and calculate fair splits between multiple people
    
    This endpoint processes a bill image and order description to:
    1. Validate the uploaded image
    2. Use AI to analyze the bill contents
    3. Calculate individual shares including:
       - Item costs
       - VAT shares
       - Service charges
       - Discounts
    4. Generate a detailed breakdown of the bill split
    
    Args:
        request (Request): FastAPI request object for rate limiting
        image (UploadFile): The bill image to analyze
        description (str): Order details description
        image_description (str, optional): Pre-analyzed image description
        current_user (User): The authenticated user making the request
        
    Returns:
        BillAnalysisResponse: Detailed analysis of the bill split
        
    Raises:
        HTTPException: If image is invalid, rate limit exceeded, or analysis fails
    """
    
    # Check rate limit for guest users
    if current_user.username == "guest":
        # Clean up old records to prevent memory leaks
        cleanup_old_records()
        client_ip = request.client.host
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in request_counts[client_ip]:
            request_counts[client_ip][today] = 0
        if request_counts[client_ip][today] >= GUEST_RATE_LIMIT:
            # Rate limit exceeded
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Guest users are limited to {GUEST_RATE_LIMIT} bill analyses per day."
            )
        else:
            # Increment counter
            request_counts[client_ip][today] += 1
    
    # Use gpt-4o-mini model if username is guest
    model = "gpt-4o-mini" if current_user.username == "guest" else "o3-mini"
    temperature = 0 if current_user.username == "guest" else 1
    return await _analyze_bill(image, description, image_description, model=model, temperature=temperature)
