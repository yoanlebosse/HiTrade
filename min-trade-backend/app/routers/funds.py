from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from ..models.fund import (
    Fund, FundListResponse, AssetClass, InvestmentHorizon,
    PortfolioRequest, PortfolioSuggestion
)
from ..core.tronc_commun import TroncCommun
import os
from pathlib import Path

router = APIRouter(prefix="/api", tags=["funds"])

# Use relative path from this file's location
_current_dir = Path(__file__).parent.parent
DATA_FILE_PATH = os.environ.get(
    "DATA_FILE_PATH",
    str(_current_dir / "data" / "files" / "funds_data.xlsx")
)

_tronc_commun: Optional[TroncCommun] = None


def get_tronc_commun() -> TroncCommun:
    global _tronc_commun
    if _tronc_commun is None:
        _tronc_commun = TroncCommun(DATA_FILE_PATH)
        _tronc_commun.initialize()
    return _tronc_commun


@router.get("/funds", response_model=FundListResponse)
async def get_funds(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    asset_class: Optional[AssetClass] = None,
    max_sri: Optional[int] = Query(None, ge=1, le=7),
    min_sri: Optional[int] = Query(None, ge=1, le=7),
    search: Optional[str] = None
):
    """Get paginated list of all funds with optional filters."""
    tc = get_tronc_commun()
    funds, total = tc.get_all_funds(
        page=page,
        page_size=page_size,
        asset_class=asset_class,
        max_sri=max_sri,
        min_sri=min_sri,
        search=search
    )
    return FundListResponse(
        funds=funds,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/funds/{isin}", response_model=Fund)
async def get_fund(isin: str):
    """Get a single fund by ISIN."""
    tc = get_tronc_commun()
    fund = tc.get_fund_by_isin(isin)
    if not fund:
        raise HTTPException(status_code=404, detail=f"Fund with ISIN {isin} not found")
    return fund


@router.get("/top-week", response_model=List[Fund])
async def get_top_week(
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get top investments of the week.
    
    Ranked by risk-adjusted weekly performance:
    score = perf_1w / (1 + vol_60d/100)
    """
    tc = get_tronc_commun()
    return tc.get_top_week_investments(limit=limit)


@router.get("/ranked", response_model=List[Fund])
async def get_ranked_funds(
    target_sri: int = Query(4, ge=1, le=7),
    horizon: InvestmentHorizon = InvestmentHorizon.MEDIUM,
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get funds ranked by fundamental score.
    
    The Cerveau Fondamental scores funds based on:
    - Performance (35%)
    - Volatility (25%)
    - SRI alignment (25%)
    - Horizon fit (15%)
    """
    tc = get_tronc_commun()
    return tc.get_ranked_funds(
        target_sri=target_sri,
        horizon=horizon,
        limit=limit
    )


@router.post("/portfolio/suggest", response_model=PortfolioSuggestion)
async def suggest_portfolio(request: PortfolioRequest):
    """
    Generate a portfolio suggestion based on user requirements.
    
    The algorithm:
    1. Filters funds by SRI range (target +/- tolerance)
    2. Scores remaining funds with Cerveau Fondamental
    3. Selects top funds ensuring diversification
    4. Allocates amounts based on scores (max 20% per fund)
    """
    tc = get_tronc_commun()
    return tc.suggest_portfolio(request)


@router.get("/stats")
async def get_stats():
    """Get statistics about the fund database."""
    tc = get_tronc_commun()
    funds = tc.funds
    
    sri_distribution = {}
    asset_class_distribution = {}
    platform_distribution = {}
    
    for fund in funds:
        sri_distribution[fund.sri] = sri_distribution.get(fund.sri, 0) + 1
        asset_class = fund.asset_class if isinstance(fund.asset_class, str) else fund.asset_class.value
        asset_class_distribution[asset_class] = asset_class_distribution.get(asset_class, 0) + 1
        for platform in fund.available_platforms:
            platform_distribution[platform] = platform_distribution.get(platform, 0) + 1
    
    return {
        "total_funds": len(funds),
        "standard_isin_funds": len([f for f in funds if f.is_standard_isin]),
        "special_funds": len([f for f in funds if not f.is_standard_isin]),
        "sri_distribution": dict(sorted(sri_distribution.items())),
        "asset_class_distribution": asset_class_distribution,
        "top_platforms": dict(sorted(platform_distribution.items(), key=lambda x: x[1], reverse=True)[:10])
    }
