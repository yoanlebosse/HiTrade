"""
Brain Models - Min-Trade Tronc Commun V0.9

Modular brain architecture ("Minecraft-style mods"):
- BrainRegistryItem: Configuration for each brain in the registry
- BrainOutput: Standardized output format from any brain
- FundScoreEntry: Score for a single fund from a brain
- FundCompositeScore: Aggregated score after Tronc Commun processing
- AdaptiveWeights: Weights provided by Cerveau Adaptatif
- TrunkRankingEntry: Entry in the global ranking
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime


class BrainType(str, Enum):
    """Type of brain for categorization"""
    FUNDAMENTAL = "fundamental"
    QUANT = "quant"
    MACRO = "macro"
    BEHAVIORAL = "behavioral"
    ADAPTIVE = "adaptive"
    HYBRID = "hybrid"


class BrainRole(str, Enum):
    """Role of brain in the system"""
    CORE = "core"  # Essential brain, always active
    EXPERIMENTAL = "experimental"  # Testing phase
    HYBRID = "hybrid"  # Combination of multiple brain types


class BrainHorizon(str, Enum):
    """Investment horizon the brain focuses on"""
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class ConsensusLevel(str, Enum):
    """Level of consensus between brains"""
    STRONG = "STRONG"  # sigma < 10
    MODERATE = "MODERATE"  # 10 <= sigma < 20
    WEAK = "WEAK"  # 20 <= sigma < 30
    DIVERGENCE = "DIVERGENCE"  # sigma >= 30


class BrainRegistryItem(BaseModel):
    """
    Configuration for a brain in the registry.
    This is the "mod" definition that can be added/removed without changing core code.
    """
    brain_id: str = Field(..., description="Unique identifier for the brain")
    label: str = Field(..., description="Human-readable name")
    brain_type: BrainType = Field(..., description="Type of brain")
    version: str = Field(default="1.0.0", description="Version of the brain")
    role: BrainRole = Field(default=BrainRole.CORE, description="Role in the system")
    horizon: BrainHorizon = Field(default=BrainHorizon.MEDIUM_TERM, description="Investment horizon focus")
    default_weight: float = Field(default=0.25, ge=0, le=1, description="Default weight for this brain")
    is_active: bool = Field(default=True, description="Whether the brain is currently active")
    description: Optional[str] = Field(default=None, description="Description of what this brain does")


class FundScoreEntry(BaseModel):
    """
    Score for a single fund from a brain.
    This is the standardized format that ALL brains must output.
    """
    fund_id: str = Field(..., description="Fund identifier (ISIN)")
    score: float = Field(..., ge=0, le=100, description="Score from 0-100")
    confidence: float = Field(..., ge=0, le=1, description="Confidence level 0-1")


class BrainOutput(BaseModel):
    """
    Complete output from a brain for all funds.
    This is the "universal port" that all brains must respect.
    
    The Tronc Commun ONLY uses:
    - brain_id
    - fund_scores[].fund_id
    - fund_scores[].score
    - fund_scores[].confidence
    
    The rest is metadata for logs, adaptatif, evolution.
    """
    brain_id: str = Field(..., description="Unique identifier of the brain")
    label: str = Field(..., description="Human-readable name")
    brain_type: BrainType = Field(..., description="Type of brain")
    version: str = Field(default="1.0.0", description="Version of the brain")
    horizon: BrainHorizon = Field(default=BrainHorizon.MEDIUM_TERM, description="Investment horizon focus")
    role: BrainRole = Field(default=BrainRole.CORE, description="Role in the system")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="When this output was generated")
    fund_scores: List[FundScoreEntry] = Field(default_factory=list, description="Scores for all funds")


class AdaptiveWeights(BaseModel):
    """
    Weights provided by the Cerveau Adaptatif.
    Maps brain_id to weight (not brain_type).
    """
    weights: Dict[str, float] = Field(..., description="Mapping of brain_id to weight")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    reason: str = Field(default="initial", description="Reason for this weight configuration")


class FundScoreComposite(BaseModel):
    """
    Composite score for a fund after aggregation by Tronc Commun.
    This is the output format for each fund.
    """
    fund_id: str = Field(..., description="Fund identifier (ISIN)")
    score_composite: float = Field(..., ge=0, le=100, description="Weighted composite score")
    scores_by_brain: Dict[str, float] = Field(default_factory=dict, description="Score from each brain")
    confidences_by_brain: Dict[str, float] = Field(default_factory=dict, description="Confidence from each brain")
    consensus_sigma: float = Field(..., description="Standard deviation of scores across brains")
    consensus_level: ConsensusLevel = Field(..., description="Classification of consensus")
    sri: int = Field(..., ge=1, le=7, description="Risk indicator (SRI)")


class TrunkRankingEntry(BaseModel):
    """
    Entry in the global ranking produced by Tronc Commun.
    Used for the allocation module.
    """
    fund_id: str = Field(..., description="Fund identifier (ISIN)")
    score_composite: float = Field(..., ge=0, le=100, description="Composite score")
    sri: int = Field(..., ge=1, le=7, description="Risk indicator")
    rank: int = Field(..., ge=1, description="Position in ranking")


class TrunkOutput(BaseModel):
    """
    Complete output from Tronc Commun.
    Contains all composite scores and the global ranking.
    """
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    fund_composite_scores: List[FundScoreComposite] = Field(default_factory=list)
    global_ranking: List[TrunkRankingEntry] = Field(default_factory=list)
    brain_weights_used: Dict[str, float] = Field(default_factory=dict)
    active_brains: List[str] = Field(default_factory=list)
    total_funds: int = Field(default=0)


class ContradictionLog(BaseModel):
    """
    Log entry for when two brains have contradictory scores.
    Used for debugging and feeding the Cerveau Adaptatif.
    """
    fund_id: str
    brain_1: str
    brain_2: str
    score_1: float
    score_2: float
    confidence_1: float
    confidence_2: float
    score_diff: float
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class MarketContext(BaseModel):
    """
    Global market context for V1.5.
    Used to adjust brain weights based on market conditions.
    """
    market_volatility: str = Field(default="medium", description="low / medium / high")
    macro_cycle: str = Field(default="expansion", description="expansion / recession / stagnation")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
