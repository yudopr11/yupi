from pydantic import BaseModel, Field
from typing import Dict, List
from decimal import Decimal

class BillItem(BaseModel):
    item: str = Field(..., description="Name or description of the item")
    price: Decimal = Field(..., description="Price of the item")

class PersonBillDetails(BaseModel):
    items: List[BillItem] = Field(..., description="List of items ordered by this person")
    individual_total: Decimal = Field(..., description="Total cost of items ordered by this person")
    vat_share: Decimal = Field(..., description="Person's share of VAT charges")
    other_share: Decimal = Field(..., description="Person's share of other charges (e.g., service charge)")
    discount_share: Decimal = Field(..., description="Person's share of discounts applied")
    final_total: Decimal = Field(..., description="Final amount to be paid by this person")

class TokenCount(BaseModel):
    image: int = Field(..., description="Number of tokens used for image processing")
    analysis: int = Field(..., description="Number of tokens used for bill analysis")

class BillAnalysisResponse(BaseModel):
    split_details: Dict[str, PersonBillDetails] = Field(..., description="Bill details split by person")
    total_bill: Decimal = Field(..., description="Total amount of the bill including all charges")
    subtotal: Decimal = Field(..., description="Subtotal before VAT and other charges")
    subtotal_vat: Decimal = Field(..., description="Total VAT charges")
    subtotal_other: Decimal = Field(..., description="Total other charges (e.g., service charge)")
    subtotal_discount: Decimal = Field(..., description="Total discounts applied")
    currency: str = Field(..., description="Currency code (e.g., USD, EUR)")
    image_description: str = Field(..., description="Description of the bill image")
    token_count: TokenCount = Field(..., description="Token usage statistics for the analysis")
