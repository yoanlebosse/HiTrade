from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import date


class AssetClass(str, Enum):
    ACTIONS = "actions"
    OBLIGATIONS = "obligations"
    DIVERSIFIE = "diversifie"
    IMMOBILIER = "immobilier"
    MONETAIRE = "monetaire"
    FONDS_EUROS = "fonds_euros"
    AUTRES = "autres"


class InvestmentHorizon(str, Enum):
    SHORT = "short"  # 0-3 years
    MEDIUM = "medium"  # 3-7 years
    LONG = "long"  # 7+ years


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NavPoint(BaseModel):
    date: date
    value: float


class FundMetrics(BaseModel):
    """Metrics calculated from NAV history"""
    perf_1w: Optional[float] = None
    perf_1m: Optional[float] = None
    perf_3m: Optional[float] = None
    perf_1y: Optional[float] = None
    perf_3y: Optional[float] = None
    perf_5y: Optional[float] = None
    vol_60d: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None


class FundData(BaseModel):
    """Complete fund data for HiTrade analysis - based on HiTrade V1 spec"""
    fund_id: str
    fund_name: str
    isin: str
    category: str
    geography: Optional[str] = None
    sector: Optional[str] = None
    manager: Optional[str] = None
    
    sri: int = Field(ge=1, le=7)
    volatility_annualized: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    
    returns_1y: Optional[float] = None
    returns_3y: Optional[float] = None
    returns_5y: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    
    aum: Optional[float] = None
    expense_ratio: Optional[float] = None
    turnover_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    
    available_platforms: List[str] = []
    is_standard_isin: bool = True
    label: Optional[str] = None


class BrainFundScore(BaseModel):
    """Score for a single fund from a brain"""
    fund_id: str
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    reasoning: Optional[str] = None
    priority: Optional[Priority] = None
    quality_score: Optional[float] = None
    valuation_score: Optional[float] = None
    stability_score: Optional[float] = None


class BrainOutput(BaseModel):
    """Complete output from a brain for all funds"""
    brain_id: str
    timestamp: str
    fund_scores: List[BrainFundScore]


class FundCompositeScore(BaseModel):
    """Composite score after aggregation by Tronc Commun"""
    fund_id: str
    score_composite: float = Field(ge=0, le=100)
    scores_by_brain: dict[str, float]
    confidences_by_brain: dict[str, float]
    consensus_level: str
    std_dev: float
    priority: Optional[Priority] = None
    reasoning: Optional[str] = None


class BrainWeights(BaseModel):
    """Configuration of brain weights"""
    weights: dict[str, float]
    last_updated: str
    update_reason: str


class TrunkOutput(BaseModel):
    """Complete output from Tronc Commun"""
    timestamp: str
    fund_composite_scores: List[FundCompositeScore]
    global_ranking: List[str]
    brain_weights_used: dict[str, float]


class Fund(BaseModel):
    """Fund model for API responses"""
    isin: str
    name: str
    management_company: Optional[str] = None
    sri: int = Field(ge=1, le=7)
    asset_class: str
    description: Optional[str] = None
    available_platforms: List[str] = []
    is_standard_isin: bool = True
    label: Optional[str] = None
    metrics: Optional[FundMetrics] = None
    fundamental_score: Optional[float] = None
    top_week_score: Optional[float] = None
    priority: Optional[Priority] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    quality_score: Optional[float] = None
    valuation_score: Optional[float] = None
    stability_score: Optional[float] = None
    consensus_level: Optional[str] = None


class FundListResponse(BaseModel):
    funds: List[Fund]
    total: int
    page: int
    page_size: int


class PortfolioRequest(BaseModel):
    amount: float = Field(gt=0, description="Amount to invest in EUR")
    horizon: InvestmentHorizon
    target_sri: int = Field(ge=1, le=7, description="Target risk level (SRI)")
    sri_tolerance: int = Field(default=1, ge=0, le=2, description="Tolerance around target SRI")


class FundAllocation(BaseModel):
    fund: Fund
    allocation_percent: float
    amount_eur: float


class PortfolioSuggestion(BaseModel):
    allocations: List[FundAllocation]
    total_amount: float
    average_sri: float
    num_funds: int
    asset_class_distribution: dict[str, float]
    explanation: str
    average_confidence: Optional[float] = None
    consensus_summary: Optional[str] = None
