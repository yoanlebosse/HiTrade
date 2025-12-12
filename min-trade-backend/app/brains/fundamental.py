"""
Cerveau Fondamental - HiTrade V1 Implementation

Based on the HiTrade V1 technical specification:
- Quality Management (40%): Q_mgmt = [(Sharpe + Sortino) / 2] x [1 - (expense_ratio / 100)]
- Valuation (30%): V_score = 100 - 50 x (PE_fund / PE_benchmark)
- Stability (30%): S_stability = 1 / (1 + max_drawdown^2)

Priority classification:
- HIGH: AUM > 100M, expense_ratio < median, sharpe > 1.0
- LOW: max_drawdown > 30%
- MEDIUM: default

=== V1.1 NOTES ===
La logique du Cerveau Fondamental est FIGEE et validee.
Ne pas modifier les formules de scoring sans validation prealable.

TODO: A enrichir avec de vraies donnees AUM / frais / PE des qu'on branche un RealDataProvider
      (Morningstar, FE fundinfo, Quantalys, etc.)

Actuellement en mode "bride" avec le MockDataProvider:
- AUM souvent None -> priorite HIGH rarement atteinte
- expense_ratio souvent None -> penalite frais non appliquee
- pe_ratio souvent None -> score valorisation neutre (50)

La logique est prete, il suffit de brancher les vraies donnees pour debloquer
toute la puissance du scoring.
"""

from typing import List, Optional, Tuple
from datetime import datetime
import logging
from abc import ABC, abstractmethod

from ..models.fund import (
    Fund, FundMetrics, FundData, AssetClass, InvestmentHorizon,
    Priority, BrainFundScore, BrainOutput as LegacyBrainOutput
)
from ..models.brain import (
    BrainOutput, FundScoreEntry, BrainType, BrainRole, BrainHorizon
)


class AbstractBrain(ABC):
    """
    Abstract base class for all brains - Min-Trade Modular Architecture
    
    All brains must implement:
    - brain_id: Unique identifier
    - label: Human-readable name
    - brain_type: Type of brain (fundamental, quant, macro, etc.)
    - version: Version string
    - analyze_all_funds_modular(): Returns standardized BrainOutput
    
    The Tronc Commun ONLY uses brain_id, fund_scores[].score, fund_scores[].confidence
    from the BrainOutput. The rest is metadata for logs/adaptatif.
    """
    
    def __init__(
        self,
        brain_id: str,
        label: str = "",
        brain_type: BrainType = BrainType.FUNDAMENTAL,
        version: str = "1.0.0",
        horizon: BrainHorizon = BrainHorizon.MEDIUM_TERM,
        role: BrainRole = BrainRole.CORE
    ):
        self.brain_id = brain_id
        self.label = label or brain_id
        self.brain_type = brain_type
        self.version = version
        self.horizon = horizon
        self.role = role
        self.logger = logging.getLogger(brain_id)
    
    @abstractmethod
    def analyze_all_funds(self, funds: List[FundData]) -> LegacyBrainOutput:
        """Legacy method - analyze all funds and return old format output"""
        pass
    
    def analyze_all_funds_modular(self, funds: List[FundData]) -> BrainOutput:
        """
        Analyze all funds and return standardized BrainOutput for Tronc Commun.
        This is the "universal port" format that all brains must respect.
        
        Default implementation converts from legacy format.
        Override this method for new brains.
        """
        legacy_output = self.analyze_all_funds(funds)
        
        # Convert legacy BrainFundScore to FundScoreEntry
        fund_scores = [
            FundScoreEntry(
                fund_id=fs.fund_id,
                score=fs.score,
                confidence=fs.confidence
            )
            for fs in legacy_output.fund_scores
        ]
        
        return BrainOutput(
            brain_id=self.brain_id,
            label=self.label,
            brain_type=self.brain_type,
            version=self.version,
            horizon=self.horizon,
            role=self.role,
            timestamp=legacy_output.timestamp,
            fund_scores=fund_scores
        )


class CerveauFondamental(AbstractBrain):
    """
    Cerveau Fondamental - HiTrade V1 Implementation
    
    Evaluates each fund according to three dimensions:
    1. Quality Management (40%): Based on Sharpe/Sortino ratios and expense ratio
    2. Valuation (30%): Based on P/E ratio vs benchmark
    3. Stability (30%): Based on maximum drawdown
    
    Formula: S_F = 0.4 x Q_mgmt + 0.3 x V_score + 0.3 x S_stability
    """
    
    WEIGHTS = {
        'quality': 0.40,
        'valuation': 0.30,
        'stability': 0.30
    }
    
    # P/E benchmarks by category
    PE_BENCHMARKS = {
        'actions': 20.0,
        'obligations': None,
        'diversifie': 15.0,
        'immobilier': 18.0,
        'monetaire': None,
        'fonds_euros': None,
        'autres': 15.0
    }
    
    # Thresholds for priority classification
    AUM_THRESHOLD = 100_000_000  # 100M EUR
    SHARPE_THRESHOLD = 1.0
    MAX_DD_THRESHOLD = 30.0  # %
    
    def __init__(self):
        super().__init__(
            brain_id="fundamental_v1",
            label="Cerveau Fondamental",
            brain_type=BrainType.FUNDAMENTAL,
            version="1.1.0",
            horizon=BrainHorizon.MEDIUM_TERM,
            role=BrainRole.CORE
        )
        self._median_expense_ratio = 1.5  # Default, calculated dynamically
    
    def analyze_all_funds(self, funds: List[FundData]) -> LegacyBrainOutput:
        """Analyze all funds and return BrainOutput"""
        # Calculate median expense ratio for priority determination
        expense_ratios = [f.expense_ratio for f in funds if f.expense_ratio is not None]
        if expense_ratios:
            expense_ratios.sort()
            mid = len(expense_ratios) // 2
            self._median_expense_ratio = expense_ratios[mid]
        
        fund_scores = [self.analyze_fund(fund) for fund in funds]
        
        return LegacyBrainOutput(
            brain_id=self.brain_id,
            timestamp=datetime.utcnow().isoformat(),
            fund_scores=fund_scores
        )
    
    def analyze_fund(self, fund: FundData) -> BrainFundScore:
        """Analyze a single fund and return its score"""
        try:
            # 1. Quality Management Score
            q_mgmt_raw = self._compute_quality_mgmt(fund)
            q_mgmt_score = self._normalize_quality(q_mgmt_raw)
            
            # 2. Valuation Score
            pe_benchmark = self.PE_BENCHMARKS.get(fund.category)
            v_score = self._compute_valuation(fund.pe_ratio, pe_benchmark)
            
            # 3. Stability Score
            s_score = self._compute_stability(fund.max_drawdown)
            
            # 4. Final Score: S_F = 0.4 x Q + 0.3 x V + 0.3 x S
            score_fundamental = (
                self.WEIGHTS['quality'] * q_mgmt_score +
                self.WEIGHTS['valuation'] * v_score +
                self.WEIGHTS['stability'] * s_score
            )
            
            # 5. Priority Classification
            priority = self._determine_priority(fund, q_mgmt_score)
            
            # 6. Confidence (based on data completeness)
            confidence = self._calculate_confidence(fund)
            
            # 7. Generate reasoning
            reasoning = self._generate_reasoning(fund, q_mgmt_score, v_score, s_score, priority)
            
            return BrainFundScore(
                fund_id=fund.fund_id,
                score=round(max(0, min(100, score_fundamental)), 2),
                confidence=confidence,
                reasoning=reasoning,
                priority=priority,
                quality_score=round(q_mgmt_score, 2),
                valuation_score=round(v_score, 2),
                stability_score=round(s_score, 2)
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing fund {fund.fund_id}: {e}")
            return BrainFundScore(
                fund_id=fund.fund_id,
                score=50.0,
                confidence=0.3,
                reasoning=f"Analysis error: {str(e)}",
                priority=Priority.MEDIUM
            )
    
    def _compute_quality_mgmt(self, fund: FundData) -> float:
        """
        Q_mgmt = [(Sharpe + Sortino) / 2] x [1 - (expense_ratio / 100)]
        
        TODO: Avec un RealDataProvider, sharpe_ratio et sortino_ratio seront
              calcules a partir des NAV historiques reelles.
              expense_ratio viendra des fiches fonds (Morningstar/FE).
        """
        # TODO: Remplacer les valeurs par defaut par des donnees reelles
        sharpe = fund.sharpe_ratio or 0.5  # Fallback: valeur neutre
        sortino = fund.sortino_ratio or sharpe  # Use Sharpe as fallback
        expense = fund.expense_ratio or 1.5  # Fallback: frais moyens du marche
        
        avg_ratio = (sharpe + sortino) / 2
        expense_factor = 1 - (expense / 100)
        
        return avg_ratio * expense_factor
    
    def _normalize_quality(self, q_mgmt: float) -> float:
        """
        Normalize Q_mgmt to 0-100 scale.
        Typical Q_mgmt range: -2 to +4
        """
        q_clamped = max(-2, min(4, q_mgmt))
        score = ((q_clamped + 2) / 6) * 100
        return score
    
    def _compute_valuation(self, pe_fund: Optional[float], pe_benchmark: Optional[float]) -> float:
        """
        V_score = 100 - 50 x (PE_fund / PE_benchmark)
        Returns neutral score (50) if data unavailable
        
        TODO: Avec un RealDataProvider, pe_ratio viendra des donnees fondamentales
              du fonds (Morningstar, Bloomberg, etc.). Actuellement souvent None
              donc score neutre (50) par defaut.
        """
        # TODO: pe_fund sera disponible avec vraies donnees -> score valorisation actif
        if pe_fund is None or pe_benchmark is None or pe_benchmark == 0:
            return 50.0  # Score neutre en l'absence de donnees PE
        
        ratio = pe_fund / pe_benchmark
        score = 100 - 50 * ratio
        return max(0, min(100, score))
    
    def _compute_stability(self, max_drawdown: Optional[float]) -> float:
        """
        S_stability = 1 / (1 + max_drawdown^2)
        max_drawdown in % (e.g., 30 for 30%)
        """
        if max_drawdown is None:
            return 50.0
        
        dd_decimal = max_drawdown / 100.0
        s_stability = 1 / (1 + dd_decimal ** 2)
        return s_stability * 100
    
    def _determine_priority(self, fund: FundData, q_mgmt_score: float) -> Priority:
        """
        Determine fund priority based on HiTrade V1 rules:
        - HIGH: AUM > 100M, expense < median, sharpe > 1.0
        - LOW: max_drawdown > 30%
        - MEDIUM: default
        
        TODO: Avec un RealDataProvider, AUM sera disponible -> priorite HIGH
              pourra etre atteinte. Actuellement AUM souvent None donc
              priorite HIGH quasi jamais attribuee.
        """
        # TODO: aum sera disponible avec vraies donnees -> classification HIGH active
        aum = fund.aum or 0  # Fallback: 0 -> jamais HIGH sans vraies donnees
        expense = fund.expense_ratio or 2.0
        sharpe = fund.sharpe_ratio or 0
        max_dd = fund.max_drawdown or 0
        
        if (aum > self.AUM_THRESHOLD and 
            expense < self._median_expense_ratio and 
            sharpe > self.SHARPE_THRESHOLD):
            return Priority.HIGH
        
        if max_dd > self.MAX_DD_THRESHOLD:
            return Priority.LOW
        
        return Priority.MEDIUM
    
    def _calculate_confidence(self, fund: FundData) -> float:
        """
        Calculate confidence based on data completeness.
        More complete data = higher confidence.
        """
        fields = [
            fund.sharpe_ratio,
            fund.sortino_ratio,
            fund.max_drawdown,
            fund.expense_ratio,
            fund.aum,
            fund.returns_1y
        ]
        
        available = sum(1 for f in fields if f is not None)
        base_confidence = 0.5 + (available / len(fields)) * 0.4
        
        return round(min(0.95, base_confidence), 2)
    
    def _generate_reasoning(
        self,
        fund: FundData,
        q_score: float,
        v_score: float,
        s_score: float,
        priority: Priority
    ) -> str:
        """Generate textual explanation for the score"""
        parts = []
        
        if q_score > 70:
            parts.append("excellente qualite de gestion")
        elif q_score > 50:
            parts.append("qualite de gestion correcte")
        elif q_score < 40:
            parts.append("qualite de gestion mediocre")
        
        if fund.expense_ratio and fund.expense_ratio < 1.0:
            parts.append("frais bas")
        elif fund.expense_ratio and fund.expense_ratio > 2.0:
            parts.append("frais eleves")
        
        if v_score > 60:
            parts.append("valorisation attractive")
        elif v_score < 40:
            parts.append("valorisation elevee")
        
        if s_score > 70:
            parts.append("grande stabilite")
        elif s_score < 40:
            parts.append("volatilite elevee")
        
        if priority == Priority.HIGH:
            parts.append("priorite haute")
        elif priority == Priority.LOW:
            parts.append("priorite basse")
        
        return ", ".join(parts) if parts else "Profil equilibre"
    
    # === Legacy compatibility methods ===
    
    def calculate_score(
        self,
        fund: Fund,
        target_sri: int = 4,
        horizon: InvestmentHorizon = InvestmentHorizon.MEDIUM
    ) -> Tuple[float, float, float, float, float, Priority, str]:
        """
        Calculate score for legacy Fund model.
        Returns: (total_score, quality_score, valuation_score, stability_score, confidence, priority, reasoning)
        """
        # Convert Fund to FundData for analysis
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
            pe_ratio=None,  # Not available in legacy model
            expense_ratio=None,  # Not available in legacy model
            aum=None  # Not available in legacy model
        )
        
        result = self.analyze_fund(fund_data)
        
        return (
            result.score,
            result.quality_score or 50.0,
            result.valuation_score or 50.0,
            result.stability_score or 50.0,
            result.confidence,
            result.priority or Priority.MEDIUM,
            result.reasoning or ""
        )
    
    def calculate_top_week_score(self, fund: Fund) -> float:
        """Calculate Top of the Week score: perf_1w / (1 + vol_60d/100)"""
        if fund.metrics is None:
            return 0.0
        
        perf_1w = fund.metrics.perf_1w or 0
        vol_60d = fund.metrics.vol_60d or 15
        
        score = perf_1w / (1 + vol_60d / 100)
        return round(score, 4)
    
    def score_funds(
        self,
        funds: List[Fund],
        target_sri: int = 4,
        horizon: InvestmentHorizon = InvestmentHorizon.MEDIUM
    ) -> List[Fund]:
        """Score all funds with HiTrade V1 algorithm"""
        for fund in funds:
            score_data = self.calculate_score(fund, target_sri, horizon)
            fund.fundamental_score = score_data[0]
            fund.quality_score = score_data[1]
            fund.valuation_score = score_data[2]
            fund.stability_score = score_data[3]
            fund.confidence = score_data[4]
            fund.priority = score_data[5]
            fund.reasoning = score_data[6]
            fund.top_week_score = self.calculate_top_week_score(fund)
        
        return sorted(funds, key=lambda f: f.fundamental_score or 0, reverse=True)
    
    def get_top_week_funds(self, funds: List[Fund], limit: int = 20) -> List[Fund]:
        """Get top funds for the week based on risk-adjusted weekly performance"""
        for fund in funds:
            fund.top_week_score = self.calculate_top_week_score(fund)
            # Also calculate fundamental scores
            score_data = self.calculate_score(fund)
            fund.fundamental_score = score_data[0]
            fund.quality_score = score_data[1]
            fund.valuation_score = score_data[2]
            fund.stability_score = score_data[3]
            fund.confidence = score_data[4]
            fund.priority = score_data[5]
            fund.reasoning = score_data[6]
        
        sorted_funds = sorted(funds, key=lambda f: f.top_week_score or 0, reverse=True)
        return sorted_funds[:limit]
    
    def get_explanation(self, fund: Fund, target_sri: int, horizon: InvestmentHorizon) -> str:
        """Generate explanation for fund score"""
        score_data = self.calculate_score(fund, target_sri, horizon)
        return score_data[6]
