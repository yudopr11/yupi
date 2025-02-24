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
    current_user: User = Depends(get_current_user)
):
    """Analyze bill image and split costs based on description (authenticated users only)"""
    try:
        # Validate image file
        validate_image(image)
        
        # Read image bytes
        image_bytes = await image.read()
        # Convert to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        # Create data URL
        mime_type = image.content_type
        image_data_url = f"data:{mime_type};base64,{image_base64}"

        # Initialize OpenAI client with API key from settings
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        prompt = f'''
        You are analyzing a bill image with the following order details:
        {description}

        Task: Create a detailed breakdown of individual payments including items, shared costs, and adjustments.

        1. Item Analysis:
        - List each person's ordered items with exact names and individual prices
        - Ensure prices match exactly as shown in the bill
        - Do not include crossed-out prices (these are marketing displays, not actual prices)

        2. Currency Detection:
        - Identify and use the exact currency shown in the bill
        - Format all monetary values consistently using the detected currency

        3. Tax (VAT) Calculation:
        - For Rupiah currency: Apply 11% VAT if not explicitly stated
        - For other currencies: Use the VAT rate shown in the bill
        - Calculate individual VAT shares proportionally based on each person's order total
        - Round VAT calculations to 2 decimal places

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

        6. Final Calculations:
        - Calculate individual_total = sum of person's items
        - Calculate vat_share = proportional VAT based on individual_total
        - Calculate other_share = equal split of service charges and fees
        - Calculate discount_share = proportional or equal split of discounts
        - Calculate final_total = individual_total + vat_share + other_share - discount_share

        Important Notes:
        - Crossed out prices are marketing displays, NOT discounts
        - All calculations must be mathematically precise
        - All monetary values must be in decimal format
        - The sum of all individual shares must equal the total bill

        Return the analysis in this exact JSON structure:
        {{
        "split_details": {{
            "person_name": {{
                "items": [
                    {{"item": "exact_item_name", "price": decimal}}
                ],
                "individual_total": decimal,
                "vat_share": decimal,
                "other_share": decimal,
                "discount_share": decimal,
                "final_total": decimal
            }}
        }},
        "total_bill": decimal,
        "total_vat": decimal,
        "total_other": decimal,
        "total_discount": decimal,
        "currency": "currency_code"
        }}

        Ensure the response is valid JSON with no additional text or explanations.
        '''
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0,
            messages=[{
                "role": "system",
                "content": "You are a helpful assistant that analyzes bills and splits the bill according to the description of who ordered what."
                },
                {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }],
            max_tokens=1000
        )
        # Clean the response and convert to JSON
        result = json.loads(response.choices[0].message.content.replace("```json", "").replace("```", "").strip())
        return BillAnalysisResponse(**result)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while analyzing the bill: {str(e)}"
        ) 