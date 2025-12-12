"""
Tronc Commun Engine - Min-Trade V0.9/V1.0

Modular "Minecraft-style" architecture:
- Brain Registry: JSON-based registry of available brains ("mods installed")
- Aggregation Service: Generic aggregation without brain-specific logic
- Consensus Analyzer: Detects agreement/divergence between brains
- Composite Score Calculator: Weighted scoring with confidence

Key principle: NO `if brain_id == "..."` in this code.
All brain-specific logic stays in the brain modules themselves.
"""

import json
import logging
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

from ..models.brain import (
    BrainRegistryItem, BrainOutput, FundScoreEntry,
    FundScoreComposite, TrunkRankingEntry, TrunkOutput,
    AdaptiveWeights, ContradictionLog, ConsensusLevel,
    BrainType, BrainRole, BrainHorizon
)


class BrainRegistryLoader:
    """
    Loads and manages the brain registry from JSON file.
    This is the "mods installed" directory.
    """
    
    def __init__(self, registry_path: Optional[str] = None):
        self.logger = logging.getLogger("BrainRegistryLoader")
        
        if registry_path is None:
            # Default path relative to this file
            registry_path = str(Path(__file__).parent.parent / "data" / "brain_registry.json")
        
        self._registry_path = registry_path
        self._registry: Dict[str, BrainRegistryItem] = {}
        self._load_registry()
    
    def _load_registry(self) -> None:
        """Load registry from JSON file"""
        try:
            with open(self._registry_path, 'r') as f:
                data = json.load(f)
            
            for item in data:
                brain_item = BrainRegistryItem(**item)
                self._registry[brain_item.brain_id] = brain_item
            
            self.logger.info(f"Loaded {len(self._registry)} brains from registry")
            
        except FileNotFoundError:
            self.logger.warning(f"Registry file not found: {self._registry_path}")
            self._registry = {}
        except Exception as e:
            self.logger.error(f"Error loading registry: {e}")
            self._registry = {}
    
    def get_all_brains(self) -> List[BrainRegistryItem]:
        """Get all registered brains"""
        return list(self._registry.values())
    
    def get_active_brains(self) -> List[BrainRegistryItem]:
        """Get only active brains"""
        return [b for b in self._registry.values() if b.is_active]
    
    def get_active_brain_ids(self) -> Set[str]:
        """Get IDs of active brains"""
        return {b.brain_id for b in self._registry.values() if b.is_active}
    
    def get_brain(self, brain_id: str) -> Optional[BrainRegistryItem]:
        """Get a specific brain by ID"""
        return self._registry.get(brain_id)
    
    def get_default_weights(self) -> Dict[str, float]:
        """Get default weights for active brains, normalized to sum to 1.0"""
        active_brains = self.get_active_brains()
        if not active_brains:
            return {}
        
        total_weight = sum(b.default_weight for b in active_brains)
        if total_weight == 0:
            # Equal weights if all defaults are 0
            equal_weight = 1.0 / len(active_brains)
            return {b.brain_id: equal_weight for b in active_brains}
        
        return {b.brain_id: b.default_weight / total_weight for b in active_brains}
    
    def activate_brain(self, brain_id: str) -> bool:
        """Activate a brain"""
        if brain_id in self._registry:
            self._registry[brain_id].is_active = True
            self.logger.info(f"Brain {brain_id} activated")
            return True
        return False
    
    def deactivate_brain(self, brain_id: str) -> bool:
        """Deactivate a brain"""
        if brain_id in self._registry:
            self._registry[brain_id].is_active = False
            self.logger.info(f"Brain {brain_id} deactivated")
            return True
        return False


class AggregationService:
    """
    Generic aggregation service for brain outputs.
    NO brain-specific logic here - just data transformation.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("AggregationService")
    
    def aggregate_brain_outputs(
        self,
        brain_outputs: List[BrainOutput]
    ) -> Dict[str, Dict[str, Tuple[float, float]]]:
        """
        Aggregate brain outputs into a mapping:
        fund_id -> { brain_id -> (score, confidence) }
        
        This is the generic aggregation step - no brain-specific logic.
        """
        aggregated: Dict[str, Dict[str, Tuple[float, float]]] = {}
        
        for output in brain_outputs:
            brain_id = output.brain_id
            
            for fund_score in output.fund_scores:
                fund_id = fund_score.fund_id
                
                if fund_id not in aggregated:
                    aggregated[fund_id] = {}
                
                aggregated[fund_id][brain_id] = (fund_score.score, fund_score.confidence)
        
        self.logger.debug(f"Aggregated {len(aggregated)} funds from {len(brain_outputs)} brains")
        return aggregated


class ConsensusAnalyzer:
    """
    Analyzes consensus level between brains.
    Detects agreement, moderate consensus, or divergence.
    """
    
    # Thresholds from spec section 6.2
    SIGMA_STRONG = 10.0
    SIGMA_MODERATE = 20.0
    SIGMA_WEAK = 30.0
    
    # Threshold for contradiction detection
    CONTRADICTION_THRESHOLD = 30.0
    CONTRADICTION_CONFIDENCE_MIN = 0.8
    
    def __init__(self):
        self.logger = logging.getLogger("ConsensusAnalyzer")
    
    def compute_consensus(
        self,
        scores: Dict[str, float]
    ) -> Tuple[float, ConsensusLevel]:
        """
        Compute consensus level from a dict of brain_id -> score.
        Returns (sigma, consensus_level).
        """
        if len(scores) < 2:
            # Single brain = perfect consensus
            return 0.0, ConsensusLevel.STRONG
        
        score_values = list(scores.values())
        
        try:
            sigma = statistics.stdev(score_values)
        except statistics.StatisticsError:
            sigma = 0.0
        
        if sigma < self.SIGMA_STRONG:
            level = ConsensusLevel.STRONG
        elif sigma < self.SIGMA_MODERATE:
            level = ConsensusLevel.MODERATE
        elif sigma < self.SIGMA_WEAK:
            level = ConsensusLevel.WEAK
        else:
            level = ConsensusLevel.DIVERGENCE
        
        return sigma, level
    
    def detect_contradictions(
        self,
        scores: Dict[str, float],
        confidences: Dict[str, float]
    ) -> List[ContradictionLog]:
        """
        Detect pairs of brains with contradictory scores.
        A contradiction = score diff > threshold AND both have high confidence.
        """
        contradictions = []
        brain_ids = list(scores.keys())
        
        for i, brain_1 in enumerate(brain_ids):
            for brain_2 in brain_ids[i+1:]:
                score_1 = scores[brain_1]
                score_2 = scores[brain_2]
                conf_1 = confidences.get(brain_1, 0.5)
                conf_2 = confidences.get(brain_2, 0.5)
                
                diff = abs(score_1 - score_2)
                
                if (diff > self.CONTRADICTION_THRESHOLD and 
                    conf_1 > self.CONTRADICTION_CONFIDENCE_MIN and
                    conf_2 > self.CONTRADICTION_CONFIDENCE_MIN):
                    
                    contradictions.append(ContradictionLog(
                        fund_id="",  # Will be set by caller
                        brain_1=brain_1,
                        brain_2=brain_2,
                        score_1=score_1,
                        score_2=score_2,
                        confidence_1=conf_1,
                        confidence_2=conf_2,
                        score_diff=diff
                    ))
        
        return contradictions


class CompositeScoreCalculator:
    """
    Calculates composite scores using weighted aggregation.
    Formula: S_composite = sum(alpha_i * S_i * c_i) for each brain i
    """
    
    def __init__(self):
        self.logger = logging.getLogger("CompositeScoreCalculator")
    
    def calculate_composite(
        self,
        scores: Dict[str, float],
        confidences: Dict[str, float],
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate composite score for a fund.
        
        Formula: S_composite = sum(alpha_i * S_i * c_i)
        where:
        - alpha_i = weight for brain i
        - S_i = score from brain i
        - c_i = confidence from brain i
        """
        if not scores:
            return 50.0  # Neutral score if no data
        
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for brain_id, score in scores.items():
            alpha = weights.get(brain_id, 0.0)
            confidence = confidences.get(brain_id, 0.5)
            
            weighted_score = alpha * score * confidence
            total_weighted_score += weighted_score
            total_weight += alpha * confidence
        
        if total_weight == 0:
            return 50.0
        
        # Normalize to account for confidence < 1
        composite = total_weighted_score / total_weight
        
        return max(0.0, min(100.0, composite))


class TrunkEngine:
    """
    Main Tronc Commun Engine - the central orchestrator.
    
    This is the "stable engine" that should rarely change.
    Brains are "mods" that can be added/removed without touching this code.
    
    Pipeline:
    1. Receive brain outputs (standardized format)
    2. Aggregate scores by fund
    3. Calculate consensus/divergence
    4. Compute composite scores with weights
    5. Produce global ranking
    6. Provide filtered views for allocation module
    """
    
    def __init__(self, registry_path: Optional[str] = None):
        self.logger = logging.getLogger("TrunkEngine")
        
        # Initialize components
        self._registry = BrainRegistryLoader(registry_path)
        self._aggregator = AggregationService()
        self._consensus = ConsensusAnalyzer()
        self._calculator = CompositeScoreCalculator()
        
        # Current weights (can be updated by Cerveau Adaptatif)
        self._current_weights = self._registry.get_default_weights()
        
        # Cache for fund SRI values (needed for allocation filtering)
        self._fund_sri_cache: Dict[str, int] = {}
        
        # Contradiction logs for debugging/adaptatif
        self._contradiction_logs: List[ContradictionLog] = []
    
    @property
    def registry(self) -> BrainRegistryLoader:
        """Access to brain registry"""
        return self._registry
    
    def update_weights(self, weights: AdaptiveWeights) -> None:
        """
        Update brain weights (called by Cerveau Adaptatif or manual config).
        Weights are applied by brain_id, not by brain_type.
        """
        # Validate weights sum to ~1.0
        total = sum(weights.weights.values())
        if abs(total - 1.0) > 0.01:
            self.logger.warning(f"Weights sum to {total}, normalizing to 1.0")
            normalized = {k: v/total for k, v in weights.weights.items()}
            self._current_weights = normalized
        else:
            self._current_weights = weights.weights.copy()
        
        self.logger.info(f"Weights updated: {self._current_weights} (reason: {weights.reason})")
    
    def set_fund_sri_cache(self, fund_sri_map: Dict[str, int]) -> None:
        """Set the fund SRI cache for allocation filtering"""
        self._fund_sri_cache = fund_sri_map
    
    def process_brain_outputs(
        self,
        brain_outputs: List[BrainOutput],
        fund_sri_map: Optional[Dict[str, int]] = None
    ) -> TrunkOutput:
        """
        Main processing pipeline.
        
        1. Aggregate brain outputs
        2. Calculate consensus for each fund
        3. Compute composite scores
        4. Generate global ranking
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Update SRI cache if provided
        if fund_sri_map:
            self._fund_sri_cache = fund_sri_map
        
        # Step 1: Aggregate brain outputs
        aggregated = self._aggregator.aggregate_brain_outputs(brain_outputs)
        
        # Get active brain IDs and normalize weights
        active_brain_ids = self._registry.get_active_brain_ids()
        weights = self._normalize_weights_for_active(active_brain_ids)
        
        # Step 2-3: Process each fund
        composite_scores: List[FundScoreComposite] = []
        self._contradiction_logs = []  # Reset logs
        
        for fund_id, brain_scores in aggregated.items():
            # Extract scores and confidences
            scores = {bid: sc[0] for bid, sc in brain_scores.items()}
            confidences = {bid: sc[1] for bid, sc in brain_scores.items()}
            
            # Calculate consensus
            sigma, consensus_level = self._consensus.compute_consensus(scores)
            
            # Detect contradictions
            contradictions = self._consensus.detect_contradictions(scores, confidences)
            for c in contradictions:
                c.fund_id = fund_id
                self._contradiction_logs.append(c)
            
            # Calculate composite score
            composite = self._calculator.calculate_composite(scores, confidences, weights)
            
            # Get SRI from cache
            sri = self._fund_sri_cache.get(fund_id, 4)  # Default to 4 if not found
            
            composite_scores.append(FundScoreComposite(
                fund_id=fund_id,
                score_composite=round(composite, 2),
                scores_by_brain=scores,
                confidences_by_brain=confidences,
                consensus_sigma=round(sigma, 2),
                consensus_level=consensus_level,
                sri=sri
            ))
        
        # Step 4: Generate global ranking
        sorted_scores = sorted(composite_scores, key=lambda x: x.score_composite, reverse=True)
        
        ranking: List[TrunkRankingEntry] = []
        for rank, score in enumerate(sorted_scores, start=1):
            ranking.append(TrunkRankingEntry(
                fund_id=score.fund_id,
                score_composite=score.score_composite,
                sri=score.sri,
                rank=rank
            ))
        
        # Log contradictions
        if self._contradiction_logs:
            self.logger.warning(f"Detected {len(self._contradiction_logs)} contradictions")
        
        return TrunkOutput(
            timestamp=timestamp,
            fund_composite_scores=composite_scores,
            global_ranking=ranking,
            brain_weights_used=weights,
            active_brains=list(active_brain_ids),
            total_funds=len(composite_scores)
        )
    
    def _normalize_weights_for_active(self, active_brain_ids: Set[str]) -> Dict[str, float]:
        """Normalize weights for active brains only"""
        active_weights = {
            bid: w for bid, w in self._current_weights.items()
            if bid in active_brain_ids
        }
        
        total = sum(active_weights.values())
        if total == 0:
            # Equal weights if no weights defined
            if active_brain_ids:
                equal = 1.0 / len(active_brain_ids)
                return {bid: equal for bid in active_brain_ids}
            return {}
        
        return {bid: w/total for bid, w in active_weights.items()}
    
    def get_ranking(
        self,
        trunk_output: TrunkOutput,
        top_n: Optional[int] = None,
        min_score: Optional[float] = None
    ) -> List[TrunkRankingEntry]:
        """
        Get global ranking with optional filters.
        
        Args:
            trunk_output: Output from process_brain_outputs
            top_n: Limit to top N funds
            min_score: Minimum composite score
        """
        ranking = trunk_output.global_ranking
        
        if min_score is not None:
            ranking = [r for r in ranking if r.score_composite >= min_score]
        
        if top_n is not None:
            ranking = ranking[:top_n]
        
        return ranking
    
    def get_funds_for_allocation(
        self,
        trunk_output: TrunkOutput,
        sri_target: int,
        tolerance: float = 0.5
    ) -> List[TrunkRankingEntry]:
        """
        Get funds eligible for allocation based on SRI target.
        
        This is the main interface for the Module Allocation RSI.
        
        Args:
            trunk_output: Output from process_brain_outputs
            sri_target: Target SRI (1-7)
            tolerance: Tolerance around target (e.g., 0.5 means +/- 0.5)
        """
        sri_min = max(1, int(sri_target - tolerance))
        sri_max = min(7, int(sri_target + tolerance + 0.99))  # Round up
        
        eligible = [
            r for r in trunk_output.global_ranking
            if sri_min <= r.sri <= sri_max
        ]
        
        self.logger.debug(f"Found {len(eligible)} funds for SRI {sri_target} (+/- {tolerance})")
        return eligible
    
    def get_contradiction_logs(self) -> List[ContradictionLog]:
        """Get contradiction logs for debugging/adaptatif"""
        return self._contradiction_logs.copy()
    
    def get_consensus_stats(self, trunk_output: TrunkOutput) -> Dict[str, int]:
        """Get statistics on consensus levels"""
        stats = {level.value: 0 for level in ConsensusLevel}
        
        for score in trunk_output.fund_composite_scores:
            stats[score.consensus_level.value] += 1
        
        return stats
