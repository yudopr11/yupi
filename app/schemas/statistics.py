from pydantic import BaseModel, Field, UUID4
from typing import List, Dict, Optional, Any
from datetime import datetime
from decimal import Decimal

class PeriodInfo(BaseModel):
    """
    Schema for period information in statistics responses
    """
    start_date: datetime = Field(..., description="Start date of the period")
    end_date: datetime = Field(..., description="End date of the period")
    period_type: str = Field(..., description="Type of period (day, week, month, year, all)")

class FinancialTotals(BaseModel):
    """
    Schema for financial totals
    """
    income: Decimal = Field(Decimal('0.0'), description="Total income in the period")
    expense: Decimal = Field(Decimal('0.0'), description="Total expenses in the period")
    transfer: Decimal = Field(Decimal('0.0'), description="Total transfers in the period")
    net: Decimal = Field(Decimal('0.0'), description="Net balance (income - expense)")

class FinancialSummaryResponse(BaseModel):
    """
    Schema for financial summary endpoint response
    
    Example:
        {
            "period": {
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-01-31T23:59:59Z",
                "period_type": "month"
            },
            "totals": {
                "income": 5000.0,
                "expense": 3000.0,
                "transfer": 1000.0,
                "net": 2000.0
            }
        }
    """
    period: PeriodInfo
    totals: FinancialTotals

class CategoryDistributionItem(BaseModel):
    """
    Schema for individual category in distribution
    """
    name: str = Field(..., description="Category name")
    uuid: str = Field(..., description="Category UUID")
    total: Decimal = Field(..., description="Total amount for this category")
    percentage: Optional[Decimal] = Field(None, description="Percentage of total (0-100)")

class CategoryDistributionResponse(BaseModel):
    """
    Schema for category distribution endpoint response
    
    Example:
        {
            "period": {
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-01-31T23:59:59Z",
                "period_type": "month"
            },
            "transaction_type": "expense",
            "total": 3000.0,
            "categories": [
                {
                    "name": "Groceries",
                    "uuid": "123e4567-e89b-12d3-a456-426614174000",
                    "total": 1000.0,
                    "percentage": 33.33
                },
                {
                    "name": "Utilities",
                    "uuid": "123e4567-e89b-12d3-a456-426614174001",
                    "total": 500.0,
                    "percentage": 16.67
                }
            ]
        }
    """
    period: PeriodInfo
    transaction_type: str = Field(..., description="Type of transactions analyzed")
    total: Decimal = Field(..., description="Total amount for all categories")
    categories: List[CategoryDistributionItem]

class TrendPeriodInfo(PeriodInfo):
    """
    Schema for trend period information with group_by
    """
    group_by: str = Field(..., description="Grouping level (day, week, month)")

class TrendDataPoint(BaseModel):
    """
    Schema for a single data point in trends
    """
    date: str = Field(..., description="Date string in YYYY-MM-DD format")
    income: Decimal = Field(Decimal('0.0'), description="Income amount for this date")
    expense: Decimal = Field(Decimal('0.0'), description="Expense amount for this date")
    transfer: Decimal = Field(Decimal('0.0'), description="Transfer amount for this date")
    net: Decimal = Field(Decimal('0.0'), description="Net amount (income - expense)")

class TransactionTrendsResponse(BaseModel):
    """
    Schema for transaction trends endpoint response
    
    Example:
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
                    "income": 500.0,
                    "expense": 200.0,
                    "transfer": 0.0,
                    "net": 300.0
                },
                {
                    "date": "2023-01-02",
                    "income": 0.0,
                    "expense": 150.0,
                    "transfer": 100.0,
                    "net": -150.0
                }
            ]
        }
    """
    period: TrendPeriodInfo
    trends: List[TrendDataPoint]

class AccountTypeBalances(BaseModel):
    """
    Schema for balances by account type
    """
    bank_account: Decimal = Field(Decimal('0.0'), description="Total balance in bank accounts")
    credit_card: Decimal = Field(Decimal('0.0'), description="Total balance in credit cards")
    other: Decimal = Field(Decimal('0.0'), description="Total balance in other accounts")

class AccountSummaryItem(BaseModel):
    """
    Schema for individual account in summary
    """
    account_id: int = Field(..., description="Account ID")
    uuid: str = Field(..., description="Account UUID")
    name: str = Field(..., description="Account name")
    type: str = Field(..., description="Account type")
    balance: Decimal = Field(..., description="Current balance")
    payable_balance: Optional[Decimal] = Field(None, description="Payable balance (for credit cards)")
    limit: Optional[Decimal] = Field(None, description="Credit limit (for credit cards)")
    utilization_percentage: Optional[Decimal] = Field(None, description="Credit utilization percentage (for credit cards)")

class AccountSummaryResponse(BaseModel):
    """
    Schema for account summary endpoint response
    
    Example:
        {
            "total_balance": 8000.0,
            "available_credit": 2000.0,
            "credit_utilization": 60.0,
            "by_account_type": {
                "bank_account": 5000.0,
                "credit_card": 3000.0,
                "other": 0.0
            },
            "accounts": [
                {
                    "account_id": 1,
                    "uuid": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "Main Checking",
                    "type": "bank_account",
                    "balance": 5000.0
                },
                {
                    "account_id": 2,
                    "uuid": "123e4567-e89b-12d3-a456-426614174001",
                    "name": "Credit Card",
                    "type": "credit_card",
                    "balance": 3000.0,
                    "payable_balance": 2000.0,
                    "limit": 5000.0,
                    "utilization_percentage": 60.0
                }
            ]
        }
    """
    total_balance: Decimal = Field(..., description="Total balance across all accounts")
    available_credit: Decimal = Field(..., description="Available credit across all credit cards")
    credit_utilization: Decimal = Field(..., description="Overall credit utilization percentage")
    by_account_type: AccountTypeBalances = Field(..., description="Balances grouped by account type")
    accounts: List[AccountSummaryItem] = Field(..., description="List of accounts with balance details") 