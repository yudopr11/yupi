from pydantic import BaseModel, Field
from typing import Dict, List
from decimal import Decimal

class BillItem(BaseModel):
    """
    Schema for individual bill item
    """
    item: str = Field(..., description="Name or description of the item", example="Pizza Margherita")
    price: Decimal = Field(..., description="Price of the item", example="12.99")

class PersonBillDetails(BaseModel):
    """
    Schema for individual person's bill details
    """
    items: List[BillItem] = Field(..., description="List of items ordered by this person")
    individual_total: Decimal = Field(..., description="Total cost of items ordered by this person", example="25.98")
    vat_share: Decimal = Field(..., description="Person's share of VAT charges", example="5.20")
    other_share: Decimal = Field(..., description="Person's share of other charges (e.g., service charge)", example="2.60")
    discount_share: Decimal = Field(..., description="Person's share of discounts applied", example="0.00")
    final_total: Decimal = Field(..., description="Final amount to be paid by this person", example="33.78")

class TokenCount(BaseModel):
    """
    Schema for tracking token usage in bill analysis
    """
    image: int = Field(..., description="Number of tokens used for image processing", example=1000)
    analysis: int = Field(..., description="Number of tokens used for bill analysis", example=500)

class BillAnalysisResponse(BaseModel):
    """
    Schema for bill analysis response
    """
    split_details: Dict[str, PersonBillDetails] = Field(..., description="Bill details split by person")
    total_bill: Decimal = Field(..., description="Total amount of the bill including all charges", example="50.00")
    subtotal: Decimal = Field(..., description="Subtotal before VAT and other charges", example="40.00")
    subtotal_vat: Decimal = Field(..., description="Total VAT charges", example="8.00")
    subtotal_other: Decimal = Field(..., description="Total other charges (e.g., service charge)", example="4.00")
    subtotal_discount: Decimal = Field(..., description="Total discounts applied", example="2.00")
    currency: str = Field(..., description="Currency code (e.g., USD, EUR)", example="USD")
    image_description: str = Field(..., description="Description of the bill image", example="Restaurant bill with multiple items")
    token_count: TokenCount = Field(..., description="Token usage statistics for the analysis") 