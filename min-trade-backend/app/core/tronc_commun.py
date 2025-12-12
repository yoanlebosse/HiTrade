"""
Tronc Commun (Core Judge) - HiTrade V1 Implementation

Based on the HiTrade V1 technical specification:
- BrainRegistry: Manages registered brains (activate/deactivate)
- BrainWeightsStore: Manages brain weights with history tracking
- ConsensusAnalyzer: Detects consensus/divergence between brains
- TroncCommun: Central orchestrator that aggregates brain outputs
"""

from typing import List, Optional, Dict, Set
from datetime import datetime
import logging
import statistics
import os

from ..models.fund import (
    Fund, FundMetrics, FundData, AssetClass, InvestmentHorizon,
    PortfolioRequest, PortfolioSuggestion, FundAllocation,
    BrainOutput, BrainFundScore, FundCompositeScore, BrainWeights, TrunkOutput, Priority
)
from ..data.ingestion import DataIngestion
from ..data.provider import FundDataProvider, MockDataProvider, TwelveDataProvider, TWELVEDATA_API_KEY
from ..brains.fundamental import CerveauFondamental, AbstractBrain


class BrainRegistry:
    """
    Registry of available brains - HiTrade V1 architecture.
    Allows dynamic registration and activation/deactivation of brains.
    """
    
    def __init__(self):
        self._brains: Dict[str, AbstractBrain] = {}
        self._active_brains: Set[str] = set()
        self.logger = logging.getLogger("BrainRegistry")
    
    def register_brain(self, brain: AbstractBrain) -> None:
        """Register a new brain"""
        brain_id = brain.brain_id
        
        if brain_id in self._brains:
            self.logger.warning(f"Brain {brain_id} already registered, overwriting")
        
        self._brains[brain_id] = brain
        self._active_brains.add(brain_id)
        self.logger.info(f"Brain {brain_id} registered and activated")
    
    def deactivate_brain(self, brain_id: str) -> None:
        """Deactivate a brain (remains registered but not used)"""
        if brain_id in self._active_brains:
            self._active_brains.remove(brain_id)
            self.logger.info(f"Brain {brain_id} deactivated")
    
    def activate_brain(self, brain_id: str) -> None:
        """Reactivate a brain"""
        if brain_id in self._brains:
            self._active_brains.add(brain_id)
            self.logger.info(f"Brain {brain_id} activated")
    
    def get_active_brains(self) -> List[AbstractBrain]:
        """Return list of active brains"""
        return [
            self._brains[brain_id]
            for brain_id in self._active_brains
            if brain_id in self._brains
        ]
    
    def get_all_brain_ids(self) -> List[str]:
        """List all registered brains"""
        return list(self._brains.keys())
    
    def get_brain(self, brain_id: str) -> Optional[AbstractBrain]:
        """Get a specific brain by ID"""
        return self._brains.get(brain_id)


class BrainWeightsStore:
    """
    Storage and management of brain weights - HiTrade V1 architecture.
    Prepares for future integration of auto-evolution module.
    """
    
    def __init__(self, initial_weights: Optional[Dict[str, float]] = None):
        self._weights = initial_weights or {}
        self._history: List[BrainWeights] = []
        self.logger = logging.getLogger("BrainWeightsStore")
    
    def get_weights(self) -> Dict[str, float]:
        """Get current weights"""
        return self._weights.copy()
    
    def update_weights(self, new_weights: Dict[str, float], reason: str = "manual") -> None:
        """
        Update brain weights.
        Called by manual configuration or auto-evolution module.
        """
        # Validation
        total = sum(new_weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Sum of weights = {total}, must be 1.0")
        
        # Archive old state
        if self._weights:
            old_state = BrainWeights(
                weights=self._weights.copy(),
                last_updated=datetime.utcnow().isoformat(),
                update_reason="archived"
            )
            self._history.append(old_state)
        
        # Update
        self._weights = new_weights
        
        new_state = BrainWeights(
            weights=new_weights,
            last_updated=datetime.utcnow().isoformat(),
            update_reason=reason
        )
        self._history.append(new_state)
        
        self.logger.info(f"Weights updated: {new_weights} (reason: {reason})")
    
    def get_history(self) -> List[BrainWeights]:
        """Return history of weight modifications"""
        return self._history.copy()
    
    def normalize_weights_for_active_brains(self, active_brain_ids: Set[str]) -> Dict[str, float]:
        """
        Renormalize weights for active brains only.
        Useful if a brain is temporarily deactivated.
        """
        active_weights = {
            brain_id: weight
            for brain_id, weight in self._weights.items()
            if brain_id in active_brain_ids
        }
        
        total = sum(active_weights.values())
        if total == 0:
            return {}
        
        return {
            brain_id: weight / total
            for brain_id, weight in active_weights.items()
        }


class ConsensusAnalyzer:
    """
    Analyzes consensus level between brains - HiTrade V1 architecture.
    """
    
    @staticmethod
    def compute_consensus_level(std_dev: float) -> str:
        """
        Classify consensus based on standard deviation of scores.
        Thresholds from HiTrade spec section 5.C
        """
        if std_dev < 10:
            return "fort"
        elif std_dev < 20:
            return "modere"
        elif std_dev < 30:
            return "faible"
        else:
            return "divergence"
    
    @staticmethod
    def detect_contradictions(
        scores: Dict[str, float],
        confidences: Dict[str, float],
        threshold: float = 30.0
    ) -> List[tuple]:
        """
        Detect contradictions between pairs of brains.
        Returns list of (brain_id1, brain_id2) in contradiction.
        """
        contradictions = []
        brain_ids = list(scores.keys())
        
        for i, brain_i in enumerate(brain_ids):
            for brain_j in brain_ids[i+1:]:
                diff = abs(scores[brain_i] - scores[brain_j])
                conf_i = confidences.get(brain_i, 0.5)
                conf_j = confidences.get(brain_j, 0.5)
                
                # Contradiction if diff > threshold AND both have high confidence
                if diff > threshold and conf_i > 0.8 and conf_j > 0.8:
                    contradictions.append((brain_i, brain_j))
        
        return contradictions


class TroncCommun:
    """
    Tronc Commun (Core Judge) - HiTrade V1 Implementation
    
    Central orchestrator that:
    1. Manages data ingestion and normalization
    2. Coordinates with registered brains via BrainRegistry
    3. Aggregates brain outputs using weighted scoring
    4. Applies user constraints for portfolio recommendations
    5. Detects consensus/divergence between brains
    
    In V1, only the Cerveau Fondamental is active.
    Architecture is ready for multiple brains in future versions.
    """
    
    MAX_ALLOCATION_PER_FUND = 0.20  # 20% max per fund
    MIN_FUNDS_IN_PORTFOLIO = 5
    MAX_FUNDS_IN_PORTFOLIO = 15
    
    def __init__(self, data_file_path: str):
        self._data_file_path = data_file_path
        self._ingestion = DataIngestion(data_file_path)
        
        # Select data provider based on environment
        # TwelveData free plan has only 8 API credits/minute - too limited for 2916 funds
        # Use MockDataProvider by default, TwelveDataProvider only with paid plan (HITRADE_ENV=prod_paid)
        hitrade_env = os.getenv("HITRADE_ENV", "dev")
        
        # TODO: Switch to TwelveDataProvider when user upgrades to paid Twelve Data plan
        # For now, use MockDataProvider to avoid API rate limits
        if TWELVEDATA_API_KEY and hitrade_env == "prod_paid":
            self._provider: FundDataProvider = TwelveDataProvider()
            self._provider_name = "TwelveData"
        else:
            self._provider: FundDataProvider = MockDataProvider()
            self._provider_name = "Mock"
        
        # HiTrade V1 architecture components
        self._brain_registry = BrainRegistry()
        self._weights_store = BrainWeightsStore(initial_weights={"fundamental": 1.0})
        self._consensus_analyzer = ConsensusAnalyzer()
        self.logger = logging.getLogger("TroncCommun")
        
        self.logger.info(f"Using data provider: {self._provider_name}")
        
        # Register Cerveau Fondamental
        self._fundamental_brain = CerveauFondamental()
        self._brain_registry.register_brain(self._fundamental_brain)
        
        # Legacy compatibility
        self._brain = self._fundamental_brain
        
        self._funds: List[Fund] = []
        self._initialized = False
    
    def initialize(self) -> None:
        """Load and process all fund data."""
        if self._initialized:
            return
        
        self._ingestion.load_data()
        self._funds = self._ingestion.normalize_and_parse()
        self._funds = self._provider.enrich_funds(self._funds)
        
        self._initialized = True
        self.logger.info(f"Initialized with {len(self._funds)} funds")
    
    @property
    def brain_registry(self) -> BrainRegistry:
        """Access to brain registry for external management"""
        return self._brain_registry
    
    @property
    def weights_store(self) -> BrainWeightsStore:
        """Access to weights store for external management"""
        return self._weights_store
    
    @property
    def funds(self) -> List[Fund]:
        if not self._initialized:
            self.initialize()
        return self._funds
    
    def get_all_funds(
        self,
        page: int = 1,
        page_size: int = 50,
        asset_class: Optional[AssetClass] = None,
        max_sri: Optional[int] = None,
        min_sri: Optional[int] = None,
        search: Optional[str] = None
    ) -> tuple[List[Fund], int]:
        """Get paginated list of funds with optional filters."""
        filtered = self.funds.copy()
        
        if asset_class:
            filtered = [f for f in filtered if f.asset_class == asset_class]
        
        if max_sri is not None:
            filtered = [f for f in filtered if f.sri <= max_sri]
        
        if min_sri is not None:
            filtered = [f for f in filtered if f.sri >= min_sri]
        
        if search:
            search_lower = search.lower()
            filtered = [
                f for f in filtered
                if search_lower in f.name.lower() or search_lower in f.isin.lower()
            ]
        
        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        
        return filtered[start:end], total
    
    def get_fund_by_isin(self, isin: str) -> Optional[Fund]:
        """Get a single fund by ISIN."""
        for fund in self.funds:
            if fund.isin == isin:
                return fund
        return None
    
    def get_top_week_investments(self, limit: int = 20) -> List[Fund]:
        """Get top investments of the week based on risk-adjusted performance."""
        return self._brain.get_top_week_funds(self.funds, limit)
    
    def get_ranked_funds(
        self,
        target_sri: int = 4,
        horizon: InvestmentHorizon = InvestmentHorizon.MEDIUM,
        limit: int = 100
    ) -> List[Fund]:
        """Get funds ranked by fundamental score."""
        scored_funds = self._brain.score_funds(
            self.funds.copy(),
            target_sri=target_sri,
            horizon=horizon
        )
        return scored_funds[:limit]
    
    def suggest_portfolio(self, request: PortfolioRequest) -> PortfolioSuggestion:
        """
        Generate a portfolio suggestion based on user requirements.
        
        Algorithm:
        1. Filter funds by SRI range (target +/- tolerance)
        2. Score remaining funds with Cerveau Fondamental
        3. Select top funds ensuring diversification
        4. Allocate amounts based on scores
        """
        sri_min = max(1, request.target_sri - request.sri_tolerance)
        sri_max = min(7, request.target_sri + request.sri_tolerance)
        
        eligible_funds = [
            f for f in self.funds
            if sri_min <= f.sri <= sri_max and f.is_standard_isin
        ]
        
        scored_funds = self._brain.score_funds(
            eligible_funds.copy(),
            target_sri=request.target_sri,
            horizon=request.horizon
        )
        
        selected_funds = self._select_diversified_funds(scored_funds, request.horizon)
        
        allocations = self._calculate_allocations(selected_funds, request.amount)
        
        avg_sri = sum(a.fund.sri * a.allocation_percent for a in allocations) / 100
        
        asset_distribution = {}
        for alloc in allocations:
            asset_class = alloc.fund.asset_class if isinstance(alloc.fund.asset_class, str) else alloc.fund.asset_class.value
            asset_distribution[asset_class] = asset_distribution.get(asset_class, 0) + alloc.allocation_percent
        
        # Calculate average confidence and consensus summary
        confidences = [a.fund.confidence for a in allocations if a.fund.confidence is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.85
        
        # Count priorities
        priority_counts = {"high": 0, "medium": 0, "low": 0}
        for alloc in allocations:
            if alloc.fund.priority:
                priority_counts[alloc.fund.priority.value] = priority_counts.get(alloc.fund.priority.value, 0) + 1
        
        consensus_summary = f"{priority_counts['high']} fonds priorite haute, {priority_counts['medium']} moyenne, {priority_counts['low']} basse"
        
        explanation = self._generate_explanation(request, allocations, avg_sri)
        
        return PortfolioSuggestion(
            allocations=allocations,
            total_amount=request.amount,
            average_sri=round(avg_sri, 2),
            num_funds=len(allocations),
            asset_class_distribution=asset_distribution,
            explanation=explanation,
            average_confidence=round(avg_confidence, 2),
            consensus_summary=consensus_summary
        )
    
    def _select_diversified_funds(
        self,
        scored_funds: List[Fund],
        horizon: InvestmentHorizon
    ) -> List[Fund]:
        """
        Select funds ensuring diversification across asset classes.
        """
        selected = []
        asset_class_counts: dict[AssetClass, int] = {}
        max_per_class = 4
        
        target_classes = self._get_target_asset_classes(horizon)
        
        for asset_class in target_classes:
            class_funds = [f for f in scored_funds if f.asset_class == asset_class]
            for fund in class_funds[:2]:
                if fund not in selected:
                    selected.append(fund)
                    asset_class_counts[asset_class] = asset_class_counts.get(asset_class, 0) + 1
        
        for fund in scored_funds:
            if len(selected) >= self.MAX_FUNDS_IN_PORTFOLIO:
                break
            if fund in selected:
                continue
            
            class_count = asset_class_counts.get(fund.asset_class, 0)
            if class_count < max_per_class:
                selected.append(fund)
                asset_class_counts[fund.asset_class] = class_count + 1
        
        while len(selected) < self.MIN_FUNDS_IN_PORTFOLIO and scored_funds:
            for fund in scored_funds:
                if fund not in selected:
                    selected.append(fund)
                    break
            else:
                break
        
        return selected
    
    def _get_target_asset_classes(self, horizon: InvestmentHorizon) -> List[AssetClass]:
        """Get prioritized asset classes based on investment horizon."""
        if horizon == InvestmentHorizon.SHORT:
            return [AssetClass.MONETAIRE, AssetClass.FONDS_EUROS, AssetClass.OBLIGATIONS]
        elif horizon == InvestmentHorizon.MEDIUM:
            return [AssetClass.DIVERSIFIE, AssetClass.OBLIGATIONS, AssetClass.IMMOBILIER, AssetClass.ACTIONS]
        else:
            return [AssetClass.ACTIONS, AssetClass.IMMOBILIER, AssetClass.DIVERSIFIE]
    
    def _calculate_allocations(
        self,
        funds: List[Fund],
        total_amount: float
    ) -> List[FundAllocation]:
        """
        Calculate allocation percentages based on fundamental scores.
        Uses score-weighted allocation with max cap per fund.
        """
        if not funds:
            return []
        
        total_score = sum(f.fundamental_score or 50 for f in funds)
        
        allocations = []
        remaining_percent = 100.0
        
        for fund in funds:
            score = fund.fundamental_score or 50
            raw_percent = (score / total_score) * 100 if total_score > 0 else 100 / len(funds)
            
            capped_percent = min(raw_percent, self.MAX_ALLOCATION_PER_FUND * 100)
            capped_percent = min(capped_percent, remaining_percent)
            
            if capped_percent > 0:
                allocations.append(FundAllocation(
                    fund=fund,
                    allocation_percent=round(capped_percent, 2),
                    amount_eur=round(total_amount * capped_percent / 100, 2)
                ))
                remaining_percent -= capped_percent
        
        if remaining_percent > 0.01 and allocations:
            per_fund_extra = remaining_percent / len(allocations)
            for alloc in allocations:
                new_percent = min(alloc.allocation_percent + per_fund_extra, self.MAX_ALLOCATION_PER_FUND * 100)
                extra = new_percent - alloc.allocation_percent
                alloc.allocation_percent = round(new_percent, 2)
                alloc.amount_eur = round(total_amount * alloc.allocation_percent / 100, 2)
        
        return allocations
    
    def _generate_explanation(
        self,
        request: PortfolioRequest,
        allocations: List[FundAllocation],
        avg_sri: float
    ) -> str:
        """Generate a human-readable explanation of the portfolio."""
        horizon_text = {
            InvestmentHorizon.SHORT: "court terme (0-3 ans)",
            InvestmentHorizon.MEDIUM: "moyen terme (3-7 ans)",
            InvestmentHorizon.LONG: "long terme (7+ ans)"
        }
        
        asset_classes = {}
        for alloc in allocations:
            ac = alloc.fund.asset_class if isinstance(alloc.fund.asset_class, str) else alloc.fund.asset_class.value
            asset_classes[ac] = asset_classes.get(ac, 0) + alloc.allocation_percent
        
        main_classes = sorted(asset_classes.items(), key=lambda x: x[1], reverse=True)[:3]
        class_text = ", ".join([f"{c[0]} ({c[1]:.0f}%)" for c in main_classes])
        
        explanation = (
            f"Ce portefeuille de {len(allocations)} fonds est optimise pour un investissement "
            f"de {request.amount:,.0f} EUR sur le {horizon_text[request.horizon]}. "
            f"Le SRI moyen obtenu est de {avg_sri:.1f} (cible: {request.target_sri}). "
            f"La repartition principale est: {class_text}. "
            f"Les fonds ont ete analyses par le Cerveau Fondamental HiTrade V1 selon trois criteres: "
            f"Qualite de Gestion (40%), Valorisation (30%), et Stabilite (30%)."
        )
        
        return explanation
