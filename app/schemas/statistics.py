from pydantic import BaseModel, Field, UUID4
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

class PeriodInfo(BaseModel):
    """
    Schema for period information used in statistics
    """
    start_date: datetime = Field(..., description="Start date of the period")
    end_date: datetime = Field(..., description="End date of the period")
    period_type: str = Field(..., description="Type of period (day, week, month, year, all)")

class FinancialTotals(BaseModel):
    """
    Schema for financial totals in a given period
    """
    income: Decimal = Field(Decimal('0.0'), description="Total income in the period")
    expense: Decimal = Field(Decimal('0.0'), description="Total expenses in the period")
    transfer: Decimal = Field(Decimal('0.0'), description="Total transfers in the period")
    net: Decimal = Field(Decimal('0.0'), description="Net balance (income - expense)")

class FinancialSummaryResponse(BaseModel):
    """
    Schema for financial summary response including period and totals
    """
    period: PeriodInfo = Field(..., description="Period information for the summary")
    totals: FinancialTotals = Field(..., description="Financial totals for the period")

class CategoryDistributionItem(BaseModel):
    """
    Schema for individual category distribution item
    """
    name: str = Field(..., description="Category name")
    uuid: UUID4 = Field(..., description="Category UUID")
    total: Decimal = Field(..., description="Total amount for this category")
    percentage: Optional[Decimal] = Field(None, description="Percentage of total (0-100)")

class CategoryDistributionResponse(BaseModel):
    """
    Schema for category distribution response showing how transactions are distributed across categories
    """
    period: PeriodInfo = Field(..., description="Period information for the distribution")
    transaction_type: str = Field(..., description="Type of transactions analyzed (income, expense, or transfer)")
    total: Decimal = Field(..., description="Total amount for all categories")
    categories: List[CategoryDistributionItem] = Field(..., description="List of categories with their distribution")

class TrendPeriodInfo(PeriodInfo):
    """
    Schema for trend period information with grouping level
    """
    group_by: str = Field(..., description="Grouping level (day, week, month, year)")

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
    Schema for transaction trends response showing financial data over time
    """
    period: TrendPeriodInfo = Field(..., description="Period information with grouping level")
    trends: List[TrendDataPoint] = Field(..., description="List of data points showing trends over time")

class AccountTypeBalances(BaseModel):
    """
    Schema for account balances grouped by account type
    """
    bank_account: Decimal = Field(Decimal('0.0'), description="Total balance in bank accounts")
    credit_card: Decimal = Field(Decimal('0.0'), description="Total balance in credit cards")
    other: Decimal = Field(Decimal('0.0'), description="Total balance in other accounts")

class AccountSummaryItem(BaseModel):
    """
    Schema for individual account summary item
    """
    account_id: int = Field(..., description="Account ID")
    uuid: UUID4 = Field(..., description="Account UUID")
    name: str = Field(..., description="Account name")
    type: str = Field(..., description="Account type (bank_account, credit_card, other)")
    balance: Decimal = Field(..., description="Current balance")
    payable_balance: Optional[Decimal] = Field(None, description="Payable balance (for credit cards)")
    limit: Optional[Decimal] = Field(None, description="Credit limit (for credit cards)")
    utilization_percentage: Optional[Decimal] = Field(None, description="Credit utilization percentage (for credit cards)")

class AccountSummaryResponse(BaseModel):
    """
    Schema for account summary response showing overall financial position
    """
    total_balance: Decimal = Field(..., description="Total balance across all accounts")
    available_credit: Decimal = Field(..., description="Available credit across all credit cards")
    credit_utilization: Decimal = Field(..., description="Overall credit utilization percentage")
    by_account_type: AccountTypeBalances = Field(..., description="Balances grouped by account type")
    accounts: List[AccountSummaryItem] = Field(..., description="List of accounts with balance details") 