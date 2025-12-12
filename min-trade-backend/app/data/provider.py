from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date, datetime, timedelta
import random
import math
import os
import logging
import httpx
from ..models.fund import Fund, FundMetrics, NavPoint

# Configuration from environment variables
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY", "")
TWELVEDATA_BASE_URL = os.getenv("TWELVEDATA_BASE_URL", "https://api.twelvedata.com")


class FundDataProvider(ABC):
    @abstractmethod
    def get_fund_by_isin(self, isin: str) -> Optional[Fund]:
        pass
    
    @abstractmethod
    def get_nav_history(self, isin: str, start_date: date, end_date: date) -> List[NavPoint]:
        pass
    
    @abstractmethod
    def get_fund_metrics(self, isin: str) -> Optional[FundMetrics]:
        pass
    
    @abstractmethod
    def enrich_fund(self, fund: Fund) -> Fund:
        pass


class MockDataProvider(FundDataProvider):
    def __init__(self, seed: int = 42):
        self._seed = seed
        random.seed(seed)
        self._fund_cache: dict[str, Fund] = {}
        self._metrics_cache: dict[str, FundMetrics] = {}
    
    def get_fund_by_isin(self, isin: str) -> Optional[Fund]:
        return self._fund_cache.get(isin)
    
    def get_nav_history(self, isin: str, start_date: date, end_date: date) -> List[NavPoint]:
        random.seed(hash(isin) % (2**32))
        
        nav_points = []
        current_date = start_date
        base_value = 100.0
        
        while current_date <= end_date:
            if current_date.weekday() < 5:
                daily_return = random.gauss(0.0002, 0.01)
                base_value *= (1 + daily_return)
                nav_points.append(NavPoint(date=current_date, value=round(base_value, 4)))
            current_date += timedelta(days=1)
        
        return nav_points
    
    def get_fund_metrics(self, isin: str) -> Optional[FundMetrics]:
        if isin in self._metrics_cache:
            return self._metrics_cache[isin]
        
        random.seed(hash(isin) % (2**32))
        
        base_perf = random.gauss(0.05, 0.15)
        vol = abs(random.gauss(0.12, 0.08))
        
        metrics = FundMetrics(
            perf_1w=round(random.gauss(base_perf / 52, vol / math.sqrt(52)) * 100, 2),
            perf_1m=round(random.gauss(base_perf / 12, vol / math.sqrt(12)) * 100, 2),
            perf_3m=round(random.gauss(base_perf / 4, vol / 2) * 100, 2),
            perf_1y=round(random.gauss(base_perf, vol) * 100, 2),
            perf_3y=round(random.gauss(base_perf * 3, vol * 1.5) * 100, 2),
            vol_60d=round(vol * 100, 2),
            sharpe_ratio=round((base_perf - 0.02) / vol if vol > 0 else 0, 2)
        )
        
        self._metrics_cache[isin] = metrics
        return metrics
    
    def enrich_fund(self, fund: Fund) -> Fund:
        metrics = self.get_fund_metrics(fund.isin)
        fund.metrics = metrics
        self._fund_cache[fund.isin] = fund
        return fund
    
    def enrich_funds(self, funds: List[Fund]) -> List[Fund]:
        return [self.enrich_fund(fund) for fund in funds]


class TwelveDataProvider(FundDataProvider):
    """
    Real data provider using Twelve Data API.
    Fetches actual market data for funds/ETFs/mutual funds.
    
    Twelve Data API docs: https://twelvedata.com/docs
    """
    
    def __init__(
        self, 
        api_key: str = TWELVEDATA_API_KEY, 
        base_url: str = TWELVEDATA_BASE_URL,
        fallback_provider: Optional[FundDataProvider] = None
    ):
        self.api_key = api_key
        self.base_url = base_url
        self._client = httpx.Client(timeout=30.0)
        self._symbol_cache: dict[str, str] = {}
        self._metrics_cache: dict[str, FundMetrics] = {}
        self._fund_cache: dict[str, Fund] = {}
        self._fallback = fallback_provider or MockDataProvider()
        self.logger = logging.getLogger("TwelveDataProvider")
        
        if not self.api_key:
            self.logger.warning("TWELVEDATA_API_KEY not set - will use fallback provider")
    
    def _get(self, path: str, params: dict) -> Optional[dict]:
        """Make a GET request to Twelve Data API with error handling."""
        if not self.api_key:
            self.logger.warning("No API key configured")
            return None
            
        params = {**params, "apikey": self.api_key}
        url = f"{self.base_url}{path}"
        
        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Handle Twelve Data error responses
            if isinstance(data, dict) and data.get("status") == "error":
                self.logger.error(f"Twelve Data API error: {data.get('message', 'Unknown error')}")
                return None
            
            return data
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error {e.response.status_code}: {e}")
            return None
        except httpx.RequestError as e:
            self.logger.error(f"Request error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            return None
    
    def _resolve_symbol(self, isin: str) -> Optional[str]:
        """
        Resolve ISIN to Twelve Data symbol.
        Uses symbol search endpoint to find matching instruments.
        """
        if isin in self._symbol_cache:
            return self._symbol_cache[isin]
        
        # Try searching by ISIN directly
        data = self._get("/symbol_search", {"symbol": isin})
        
        if data and "data" in data and len(data["data"]) > 0:
            # Find best match - prefer exact ISIN match or first result
            for item in data["data"]:
                symbol = item.get("symbol")
                if symbol:
                    self._symbol_cache[isin] = symbol
                    self.logger.info(f"Resolved ISIN {isin} to symbol {symbol}")
                    return symbol
        
        # Try searching by ISIN as a query
        data = self._get("/symbol_search", {"symbol": isin, "outputsize": 10})
        
        if data and "data" in data and len(data["data"]) > 0:
            symbol = data["data"][0].get("symbol")
            if symbol:
                self._symbol_cache[isin] = symbol
                self.logger.info(f"Resolved ISIN {isin} to symbol {symbol} (search)")
                return symbol
        
        self.logger.warning(f"Could not resolve ISIN {isin} to Twelve Data symbol")
        return None
    
    def get_fund_by_isin(self, isin: str) -> Optional[Fund]:
        """Get fund from cache."""
        return self._fund_cache.get(isin)
    
    def get_nav_history(self, isin: str, start_date: date, end_date: date) -> List[NavPoint]:
        """
        Get NAV history from Twelve Data time series API.
        Falls back to mock data if API call fails.
        """
        symbol = self._resolve_symbol(isin)
        
        if not symbol:
            self.logger.warning(f"Using fallback for NAV history: {isin}")
            return self._fallback.get_nav_history(isin, start_date, end_date)
        
        params = {
            "symbol": symbol,
            "interval": "1day",
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "order": "ASC",
        }
        
        data = self._get("/time_series", params)
        
        if not data or "values" not in data:
            self.logger.warning(f"No time series data for {isin}, using fallback")
            return self._fallback.get_nav_history(isin, start_date, end_date)
        
        nav_points: List[NavPoint] = []
        for item in data["values"]:
            try:
                nav_date = datetime.strptime(item["datetime"], "%Y-%m-%d").date()
                nav_value = float(item["close"])
                nav_points.append(NavPoint(date=nav_date, value=nav_value))
            except (KeyError, ValueError) as e:
                self.logger.warning(f"Error parsing NAV point: {e}")
                continue
        
        if not nav_points:
            self.logger.warning(f"No valid NAV points for {isin}, using fallback")
            return self._fallback.get_nav_history(isin, start_date, end_date)
        
        self.logger.info(f"Retrieved {len(nav_points)} NAV points for {isin}")
        return nav_points
    
    def _calculate_returns(self, nav_points: List[NavPoint]) -> List[float]:
        """Calculate daily returns from NAV points."""
        if len(nav_points) < 2:
            return []
        
        returns = []
        for i in range(1, len(nav_points)):
            prev_nav = nav_points[i - 1].value
            curr_nav = nav_points[i].value
            if prev_nav > 0:
                daily_return = (curr_nav - prev_nav) / prev_nav
                returns.append(daily_return)
        
        return returns
    
    def _calculate_performance(self, nav_points: List[NavPoint], days: int) -> Optional[float]:
        """Calculate performance over a specific number of days."""
        if len(nav_points) < 2:
            return None
        
        # Find the NAV point closest to 'days' ago
        target_date = nav_points[-1].date - timedelta(days=days)
        
        # Find closest point to target date
        closest_point = None
        min_diff = float('inf')
        
        for point in nav_points:
            diff = abs((point.date - target_date).days)
            if diff < min_diff:
                min_diff = diff
                closest_point = point
        
        if closest_point and closest_point.value > 0:
            perf = ((nav_points[-1].value - closest_point.value) / closest_point.value) * 100
            return round(perf, 2)
        
        return None
    
    def _calculate_volatility(self, returns: List[float], window: int = 60) -> Optional[float]:
        """Calculate annualized volatility from daily returns."""
        if len(returns) < window:
            window = len(returns)
        
        if window < 5:
            return None
        
        recent_returns = returns[-window:]
        
        # Calculate standard deviation
        mean = sum(recent_returns) / len(recent_returns)
        variance = sum((r - mean) ** 2 for r in recent_returns) / len(recent_returns)
        std_dev = math.sqrt(variance)
        
        # Annualize (assuming 252 trading days)
        annualized_vol = std_dev * math.sqrt(252) * 100
        return round(annualized_vol, 2)
    
    def _calculate_max_drawdown(self, nav_points: List[NavPoint]) -> Optional[float]:
        """Calculate maximum drawdown from NAV history."""
        if len(nav_points) < 2:
            return None
        
        peak = nav_points[0].value
        max_dd = 0.0
        
        for point in nav_points:
            if point.value > peak:
                peak = point.value
            
            if peak > 0:
                drawdown = (peak - point.value) / peak
                max_dd = max(max_dd, drawdown)
        
        return round(max_dd * 100, 2)
    
    def _calculate_sharpe_ratio(
        self, 
        returns: List[float], 
        risk_free_rate: float = 0.02
    ) -> Optional[float]:
        """Calculate Sharpe ratio from daily returns."""
        if len(returns) < 30:
            return None
        
        # Annualized return
        mean_daily = sum(returns) / len(returns)
        annualized_return = mean_daily * 252
        
        # Annualized volatility
        variance = sum((r - mean_daily) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)
        annualized_vol = std_dev * math.sqrt(252)
        
        if annualized_vol == 0:
            return None
        
        sharpe = (annualized_return - risk_free_rate) / annualized_vol
        return round(sharpe, 2)
    
    def _calculate_sortino_ratio(
        self, 
        returns: List[float], 
        risk_free_rate: float = 0.02
    ) -> Optional[float]:
        """Calculate Sortino ratio (downside deviation only)."""
        if len(returns) < 30:
            return None
        
        # Annualized return
        mean_daily = sum(returns) / len(returns)
        annualized_return = mean_daily * 252
        
        # Downside deviation (only negative returns)
        negative_returns = [r for r in returns if r < 0]
        
        if not negative_returns:
            return None
        
        downside_variance = sum(r ** 2 for r in negative_returns) / len(returns)
        downside_dev = math.sqrt(downside_variance)
        annualized_downside = downside_dev * math.sqrt(252)
        
        if annualized_downside == 0:
            return None
        
        sortino = (annualized_return - risk_free_rate) / annualized_downside
        return round(sortino, 2)
    
    def get_fund_metrics(self, isin: str) -> Optional[FundMetrics]:
        """
        Calculate fund metrics from real NAV history.
        Falls back to mock data if API call fails.
        """
        if isin in self._metrics_cache:
            return self._metrics_cache[isin]
        
        # Get 3+ years of history for comprehensive metrics
        end_date = date.today()
        start_date = end_date - timedelta(days=365 * 3 + 30)
        
        nav_points = self.get_nav_history(isin, start_date, end_date)
        
        if not nav_points or len(nav_points) < 10:
            self.logger.warning(f"Insufficient NAV data for {isin}, using fallback metrics")
            return self._fallback.get_fund_metrics(isin)
        
        # Calculate daily returns
        returns = self._calculate_returns(nav_points)
        
        if not returns:
            return self._fallback.get_fund_metrics(isin)
        
        # Calculate all metrics
        metrics = FundMetrics(
            perf_1w=self._calculate_performance(nav_points, 7),
            perf_1m=self._calculate_performance(nav_points, 30),
            perf_3m=self._calculate_performance(nav_points, 90),
            perf_1y=self._calculate_performance(nav_points, 365),
            perf_3y=self._calculate_performance(nav_points, 365 * 3),
            vol_60d=self._calculate_volatility(returns, 60),
            max_drawdown=self._calculate_max_drawdown(nav_points),
            sharpe_ratio=self._calculate_sharpe_ratio(returns),
            sortino_ratio=self._calculate_sortino_ratio(returns),
        )
        
        self._metrics_cache[isin] = metrics
        self.logger.info(f"Calculated real metrics for {isin}: sharpe={metrics.sharpe_ratio}, vol={metrics.vol_60d}")
        return metrics
    
    def enrich_fund(self, fund: Fund) -> Fund:
        """Enrich fund with real metrics from Twelve Data."""
        metrics = self.get_fund_metrics(fund.isin)
        fund.metrics = metrics
        self._fund_cache[fund.isin] = fund
        return fund
    
    def enrich_funds(self, funds: List[Fund]) -> List[Fund]:
        """Enrich multiple funds with real metrics."""
        enriched = []
        total = len(funds)
        
        for i, fund in enumerate(funds):
            if (i + 1) % 100 == 0:
                self.logger.info(f"Enriching funds: {i + 1}/{total}")
            enriched.append(self.enrich_fund(fund))
        
        self.logger.info(f"Enriched {len(enriched)} funds")
        return enriched
    
    def health_check(self) -> dict:
        """
        Perform a health check on the Twelve Data API connection.
        Returns status and sample data.
        """
        if not self.api_key:
            return {"status": "error", "message": "No API key configured"}
        
        # Test with a known symbol
        data = self._get("/quote", {"symbol": "AAPL"})
        
        if data and "symbol" in data:
            return {
                "status": "ok",
                "message": "Twelve Data API connection successful",
                "sample_symbol": data.get("symbol"),
                "sample_price": data.get("close")
            }
        
        return {"status": "error", "message": "Failed to connect to Twelve Data API"}
