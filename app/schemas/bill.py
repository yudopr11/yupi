from pydantic import BaseModel
from typing import Dict, List
from decimal import Decimal

class BillItem(BaseModel):
    item: str
    price: Decimal

class PersonBillDetails(BaseModel):
    items: List[BillItem]
    individual_total: Decimal
    vat_share: Decimal
    other_share: Decimal
    discount_share: Decimal
    final_total: Decimal

class TokenCount(BaseModel):
    image: int
    analysis: int

class BillAnalysisResponse(BaseModel):
    split_details: Dict[str, PersonBillDetails]
    total_bill: Decimal
    subtotal: Decimal
    subtotal_vat: Decimal
    subtotal_other: Decimal
    subtotal_discount: Decimal
    currency: str
    image_description: str
    token_count: TokenCount 