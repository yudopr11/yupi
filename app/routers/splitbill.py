from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from openai import OpenAI
import json, base64

from app.utils.auth import get_current_user
from app.models.user import User
from app.schemas.bill import BillAnalysisResponse
from app.schemas.error import ErrorDetail
from app.core.config import settings

router = APIRouter(prefix="/splitbill", tags=["Bill Analysis"])

# Define allowed image MIME types
ALLOWED_IMAGE_TYPES = [
    'image/jpeg',
    'image/png',
    'image/jpg',
    'image/webp',
]

def validate_image(file: UploadFile) -> None:
    """Validate that the uploaded file is an image"""
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

@router.post(
    "/analyze",
    response_model=BillAnalysisResponse,
    responses={
        400: {"model": ErrorDetail, "description": "Invalid bill image"},
        401: {"model": ErrorDetail, "description": "Not authenticated"},
        413: {"model": ErrorDetail, "description": "File too large"},
        415: {"model": ErrorDetail, "description": "Unsupported file type"},
        422: {"model": ErrorDetail, "description": "Validation error"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def analyze_bill(
    image: UploadFile = File(...),
    description: str = Form(...),
    image_description: str = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Analyze bill image and split costs based on description (authenticated users only)"""
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
3. If it IS a bill/receipt, provide a detailed description
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

2. Currency Detection:
- Identify and use the exact currency shown in the bill
- Format all monetary values consistently using the detected currency

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
            model="gpt-4o",
            temperature=1,
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