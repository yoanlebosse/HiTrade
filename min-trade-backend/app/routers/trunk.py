"""
Tronc Commun API Endpoints - Min-Trade V1.0

Endpoints for the modular Tronc Commun engine:
- GET /trunk/ranking: Get global fund ranking
- GET /trunk/funds_for_allocation: Get funds filtered by RSI target
- GET /trunk/brains: List registered brains
- GET /trunk/stats: Get consensus statistics
- POST /trunk/weights: Update brain weights (for Cerveau Adaptatif)
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
import logging

from ..models.brain import (
    BrainRegistryItem, TrunkRankingEntry, TrunkOutput,
    AdaptiveWeights, ConsensusLevel, FundScoreComposite
)
from ..models.fund import FundData
from ..core.trunk_engine import TrunkEngine
from ..brains.fundamental import CerveauFondamental
from ..data.ingestion import DataIngestion
from ..data.provider import MockDataProvider
import os
from pathlib import Path

router = APIRouter(prefix="/trunk", tags=["trunk"])
logger = logging.getLogger("TrunkRouter")

# Initialize components
_current_dir = Path(__file__).parent.parent
DATA_FILE_PATH = os.environ.get(
    "DATA_FILE_PATH",
    str(_current_dir / "data" / "files" / "funds_data.xlsx")
)

_trunk_engine: Optional[TrunkEngine] = None
_fundamental_brain: Optional[CerveauFondamental] = None
_fund_data_cache: Optional[List[FundData]] = None
_trunk_output_cache: Optional[TrunkOutput] = None


def get_trunk_engine() -> TrunkEngine:
    """Get or initialize the TrunkEngine singleton"""
    global _trunk_engine
    if _trunk_engine is None:
        _trunk_engine = TrunkEngine()
        logger.info("TrunkEngine initialized")
    return _trunk_engine


def get_fundamental_brain() -> CerveauFondamental:
    """Get or initialize the CerveauFondamental singleton"""
    global _fundamental_brain
    if _fundamental_brain is None:
        _fundamental_brain = CerveauFondamental()
        logger.info("CerveauFondamental initialized")
    return _fundamental_brain


def get_fund_data() -> List[FundData]:
    """Load and cache fund data"""
    global _fund_data_cache
    if _fund_data_cache is None:
        ingestion = DataIngestion(DATA_FILE_PATH)
        ingestion.load_data()
        funds = ingestion.normalize_and_parse()
        
        # Enrich with mock data
        provider = MockDataProvider()
        funds = provider.enrich_funds(funds)
        
        # Convert Fund to FundData
        _fund_data_cache = []
        for fund in funds:
            fund_data = FundData(
                fund_id=fund.isin,
                fund_name=fund.name,
                isin=fund.isin,
                category=fund.asset_class if isinstance(fund.asset_class, str) else fund.asset_class.value,
                manager=fund.management_company,
                sri=fund.sri,
                volatility_annualized=fund.metrics.vol_60d if fund.metrics else None,
                max_drawdown=fund.metrics.max_drawdown if fund.metrics else None,
                sharpe_ratio=fund.metrics.sharpe_ratio if fund.metrics else None,
                sortino_ratio=fund.metrics.sortino_ratio if fund.metrics else None,
                returns_1y=fund.metrics.perf_1y if fund.metrics else None,
                returns_3y=fund.metrics.perf_3y if fund.metrics else None,
                available_platforms=fund.available_platforms,
                is_standard_isin=fund.is_standard_isin,
                label=fund.label
            )
            _fund_data_cache.append(fund_data)
        
        logger.info(f"Loaded {len(_fund_data_cache)} funds")
    
    return _fund_data_cache


def get_trunk_output() -> TrunkOutput:
    """Process brain outputs and cache the result"""
    global _trunk_output_cache
    
    if _trunk_output_cache is None:
        engine = get_trunk_engine()
        brain = get_fundamental_brain()
        fund_data = get_fund_data()
        
        # Build fund SRI map
        fund_sri_map = {fd.fund_id: fd.sri for fd in fund_data}
        engine.set_fund_sri_cache(fund_sri_map)
        
        # Get brain output using the modular interface
        brain_output = brain.analyze_all_funds_modular(fund_data)
        
        # Process through trunk engine
        _trunk_output_cache = engine.process_brain_outputs(
            brain_outputs=[brain_output],
            fund_sri_map=fund_sri_map
        )
        
        logger.info(f"Processed {_trunk_output_cache.total_funds} funds through TrunkEngine")
    
    return _trunk_output_cache


@router.get("/ranking", response_model=List[TrunkRankingEntry])
async def get_ranking(
    top_n: int = Query(100, ge=1, le=2000, description="Number of top funds to return"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum composite score")
):
    """
    Get global fund ranking from Tronc Commun.
    
    Returns funds sorted by composite score (highest first).
    """
    engine = get_trunk_engine()
    trunk_output = get_trunk_output()
    
    ranking = engine.get_ranking(
        trunk_output=trunk_output,
        top_n=top_n,
        min_score=min_score
    )
    
    return ranking


@router.get("/funds_for_allocation", response_model=List[TrunkRankingEntry])
async def get_funds_for_allocation(
    sri_target: int = Query(4, ge=1, le=7, description="Target SRI (1-7)"),
    tolerance: float = Query(0.5, ge=0, le=3, description="Tolerance around target SRI")
):
    """
    Get funds eligible for allocation based on SRI target.
    
    This is the main interface for the Module Allocation RSI.
    Returns funds within the SRI range, sorted by composite score.
    """
    engine = get_trunk_engine()
    trunk_output = get_trunk_output()
    
    eligible = engine.get_funds_for_allocation(
        trunk_output=trunk_output,
        sri_target=sri_target,
        tolerance=tolerance
    )
    
    return eligible


@router.get("/brains", response_model=List[BrainRegistryItem])
async def list_brains(
    active_only: bool = Query(False, description="Only return active brains")
):
    """
    List all registered brains in the registry.
    
    This shows the "mods installed" in the system.
    """
    engine = get_trunk_engine()
    
    if active_only:
        return engine.registry.get_active_brains()
    else:
        return engine.registry.get_all_brains()


@router.get("/stats")
async def get_stats():
    """
    Get statistics about the Tronc Commun processing.
    
    Includes consensus levels, active brains, and weights.
    """
    engine = get_trunk_engine()
    trunk_output = get_trunk_output()
    
    consensus_stats = engine.get_consensus_stats(trunk_output)
    contradiction_count = len(engine.get_contradiction_logs())
    
    return {
        "total_funds": trunk_output.total_funds,
        "active_brains": trunk_output.active_brains,
        "brain_weights": trunk_output.brain_weights_used,
        "consensus_distribution": consensus_stats,
        "contradiction_count": contradiction_count,
        "timestamp": trunk_output.timestamp
    }


@router.get("/composite/{fund_id}", response_model=FundScoreComposite)
async def get_fund_composite(fund_id: str):
    """
    Get composite score details for a specific fund.
    
    Shows scores from each brain, consensus level, and final composite.
    """
    trunk_output = get_trunk_output()
    
    for score in trunk_output.fund_composite_scores:
        if score.fund_id == fund_id:
            return score
    
    raise HTTPException(status_code=404, detail=f"Fund {fund_id} not found")


@router.post("/weights")
async def update_weights(weights: AdaptiveWeights):
    """
    Update brain weights.
    
    Called by Cerveau Adaptatif or manual configuration.
    Weights are applied by brain_id (not brain_type).
    """
    global _trunk_output_cache
    
    engine = get_trunk_engine()
    
    try:
        engine.update_weights(weights)
        
        # Invalidate cache to force reprocessing with new weights
        _trunk_output_cache = None
        
        return {
            "status": "success",
            "message": f"Weights updated: {weights.weights}",
            "reason": weights.reason
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/brain/{brain_id}/activate")
async def activate_brain(brain_id: str):
    """Activate a brain in the registry"""
    global _trunk_output_cache
    
    engine = get_trunk_engine()
    
    if engine.registry.activate_brain(brain_id):
        _trunk_output_cache = None  # Invalidate cache
        return {"status": "success", "message": f"Brain {brain_id} activated"}
    else:
        raise HTTPException(status_code=404, detail=f"Brain {brain_id} not found")


@router.post("/brain/{brain_id}/deactivate")
async def deactivate_brain(brain_id: str):
    """Deactivate a brain in the registry"""
    global _trunk_output_cache
    
    engine = get_trunk_engine()
    
    if engine.registry.deactivate_brain(brain_id):
        _trunk_output_cache = None  # Invalidate cache
        return {"status": "success", "message": f"Brain {brain_id} deactivated"}
    else:
        raise HTTPException(status_code=404, detail=f"Brain {brain_id} not found")


@router.get("/contradictions")
async def get_contradictions():
    """
    Get contradiction logs for debugging and Cerveau Adaptatif.
    
    Shows pairs of brains with contradictory scores (diff > 30 with high confidence).
    """
    engine = get_trunk_engine()
    
    # Ensure processing has been done
    get_trunk_output()
    
    logs = engine.get_contradiction_logs()
    
    return {
        "count": len(logs),
        "contradictions": [
            {
                "fund_id": log.fund_id,
                "brain_1": log.brain_1,
                "brain_2": log.brain_2,
                "score_1": log.score_1,
                "score_2": log.score_2,
                "score_diff": log.score_diff,
                "timestamp": log.timestamp
            }
            for log in logs
        ]
    }
