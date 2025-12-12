import { useState, useEffect, createContext, useContext } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  TrendingUp, 
  Briefcase, 
  Eye, 
  Calculator, 
  ChevronRight, 
  ChevronLeft,
  Menu,
  X,
  Brain,
  Zap,
  Shield,
  Target,
  PieChart,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
  Sparkles,
  DollarSign,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import './App.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// === VIEW MODE CONTEXT ===
type ViewMode = 'simple' | 'advanced';
const ViewModeContext = createContext<{ viewMode: ViewMode; setViewMode: (mode: ViewMode) => void }>({
  viewMode: 'simple',
  setViewMode: () => {}
});

const useViewMode = () => useContext(ViewModeContext);

interface FundMetrics {
  perf_1w: number | null;
  perf_1m: number | null;
  perf_3m: number | null;
  perf_1y: number | null;
  perf_3y: number | null;
  vol_60d: number | null;
  sharpe_ratio: number | null;
  sortino_ratio?: number | null;
  max_drawdown?: number | null;
}

interface Fund {
  isin: string;
  name: string;
  management_company: string | null;
  sri: number;
  asset_class: string;
  description: string | null;
  available_platforms: string[];
  is_standard_isin: boolean;
  label: string | null;
  metrics: FundMetrics | null;
  fundamental_score: number | null;
  top_week_score: number | null;
  // HiTrade V1 fields
  priority: 'high' | 'medium' | 'low' | null;
  confidence: number | null;
  reasoning: string | null;
  quality_score: number | null;
  valuation_score: number | null;
  stability_score: number | null;
  consensus_level: string | null;
}

interface FundAllocation {
  fund: Fund;
  allocation_percent: number;
  amount_eur: number;
}

interface PortfolioSuggestion {
  allocations: FundAllocation[];
  total_amount: number;
  average_sri: number;
  num_funds: number;
  asset_class_distribution: Record<string, number>;
  explanation: string;
  // HiTrade V1 fields
  average_confidence: number | null;
  consensus_summary: string | null;
}

interface Stats {
  total_funds: number;
  standard_isin_funds: number;
  special_funds: number;
  sri_distribution: Record<string, number>;
  asset_class_distribution: Record<string, number>;
}

const SRIBadge = ({ sri }: { sri: number }) => {
  const colors: Record<number, string> = {
    1: 'bg-emerald-600 text-white border-emerald-500',
    2: 'bg-green-600 text-white border-green-500',
    3: 'bg-teal-600 text-white border-teal-500',
    4: 'bg-amber-500 text-white border-amber-400',
    5: 'bg-orange-500 text-white border-orange-400',
    6: 'bg-red-500 text-white border-red-400',
    7: 'bg-rose-600 text-white border-rose-500',
  };
  
  return (
    <Badge variant="outline" className={`${colors[sri]} font-bold text-xs px-2 py-0.5`}>
      SRI {sri}
    </Badge>
  );
};

const AssetClassBadge = ({ assetClass }: { assetClass: string }) => {
  const config: Record<string, { label: string; color: string }> = {
    actions: { label: 'Actions', color: 'bg-violet-600 text-white border-violet-500' },
    obligations: { label: 'Obligations', color: 'bg-blue-600 text-white border-blue-500' },
    diversifie: { label: 'Diversifie', color: 'bg-indigo-600 text-white border-indigo-500' },
    immobilier: { label: 'Immobilier', color: 'bg-pink-600 text-white border-pink-500' },
    monetaire: { label: 'Monetaire', color: 'bg-cyan-600 text-white border-cyan-500' },
    fonds_euros: { label: 'Fonds Euros', color: 'bg-sky-600 text-white border-sky-500' },
    autres: { label: 'Autres', color: 'bg-slate-600 text-white border-slate-500' },
  };
  
  const { label, color } = config[assetClass] || { label: assetClass, color: 'bg-slate-600 text-white border-slate-500' };
  
  return (
    <Badge variant="secondary" className={`${color} font-medium text-xs px-2 py-0.5`}>
      {label}
    </Badge>
  );
};

const PriorityBadge = ({ priority }: { priority: 'high' | 'medium' | 'low' | null }) => {
  if (!priority) return null;
  
  const config: Record<string, { label: string; color: string; icon: string }> = {
    high: { label: 'Haute', color: 'bg-emerald-600 text-white border-emerald-500 shadow-emerald-500/30', icon: '★' },
    medium: { label: 'Moyenne', color: 'bg-amber-500 text-white border-amber-400', icon: '◆' },
    low: { label: 'Basse', color: 'bg-slate-500 text-white border-slate-400', icon: '○' },
  };
  
  const { label, color, icon } = config[priority] || { label: priority, color: 'bg-slate-500 text-white border-slate-400', icon: '' };
  
  return (
    <Badge variant="outline" className={`${color} font-medium text-xs px-2 py-0.5 shadow-sm`}>
      {icon} {label}
    </Badge>
  );
};

// === BRAIN PROFILE COMPONENT (3 bars) ===
const BrainProfile = ({ 
  quality, 
  valuation, 
  stability,
  showDetails = false 
}: { 
  quality: number | null; 
  valuation: number | null; 
  stability: number | null;
  showDetails?: boolean;
}) => {
  const { viewMode } = useViewMode();
  
  const bars = [
    { 
      label: 'Gestion', 
      icon: <Brain className="w-3 h-3" />, 
      value: quality, 
      color: 'bg-gradient-to-r from-violet-500 to-purple-400',
      bgColor: 'bg-violet-500/20',
      glowColor: 'shadow-violet-500/50',
      detail: 'Sharpe, Sortino, frais'
    },
    { 
      label: 'Valo', 
      icon: <DollarSign className="w-3 h-3" />, 
      value: valuation, 
      color: 'bg-gradient-to-r from-emerald-500 to-green-400',
      bgColor: 'bg-emerald-500/20',
      glowColor: 'shadow-emerald-500/50',
      detail: 'PE vs benchmark'
    },
    { 
      label: 'Stabilite', 
      icon: <Shield className="w-3 h-3" />, 
      value: stability, 
      color: 'bg-gradient-to-r from-amber-500 to-yellow-400',
      bgColor: 'bg-amber-500/20',
      glowColor: 'shadow-amber-500/50',
      detail: 'Max drawdown'
    },
  ];
  
  // Check if all values are null - show "Donnees indisponibles"
  const allNull = quality == null && valuation == null && stability == null;
  
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-xs text-gray-400 font-medium">
        <Sparkles className="w-3 h-3 text-sky-400 animate-pulse" />
        Profil HiTrade
      </div>
      {allNull ? (
        <div className="text-xs text-gray-500 italic py-2 px-3 bg-gray-800/50 rounded-lg border border-gray-700/50">
          Donnees indisponibles (provider)
        </div>
      ) : (
        <div className="space-y-1.5">
          {bars.map((bar) => (
            <div key={bar.label} className="group">
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1 w-16 text-xs text-gray-300">
                  <span className="text-sky-400">{bar.icon}</span>
                  <span>{bar.label}</span>
                </div>
                {bar.value != null ? (
                  <>
                    <div className={`flex-1 h-2.5 rounded-full ${bar.bgColor} overflow-hidden`}>
                      <div 
                        className={`h-full ${bar.color} rounded-full transition-all duration-500 shadow-sm ${bar.glowColor}`}
                        style={{ width: `${Math.min(100, Math.max(0, bar.value))}%` }}
                      />
                    </div>
                    <span className="w-8 text-right text-xs font-bold text-white">
                      {bar.value.toFixed(0)}
                    </span>
                  </>
                ) : (
                  <span className="flex-1 text-xs text-gray-500 italic">N/A</span>
                )}
              </div>
              {bar.value != null && (showDetails || viewMode === 'advanced') && (
                <p className="text-xs text-gray-500 ml-7 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  {bar.detail}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// === VIEW MODE TOGGLE ===
const ViewModeToggle = () => {
  const { viewMode, setViewMode } = useViewMode();
  
  return (
    <div className="flex items-center gap-1 p-1 bg-gray-800 rounded-lg border border-gray-700">
      <button
        onClick={() => setViewMode('simple')}
        className={`px-3 py-1.5 text-xs font-medium rounded transition-all ${
          viewMode === 'simple' 
            ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/30' 
            : 'text-gray-400 hover:text-white'
        }`}
      >
        <Eye className="w-3 h-3 inline mr-1" />
        Vue simple
      </button>
      <button
        onClick={() => setViewMode('advanced')}
        className={`px-3 py-1.5 text-xs font-medium rounded transition-all ${
          viewMode === 'advanced' 
            ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/30' 
            : 'text-gray-400 hover:text-white'
        }`}
      >
        <Brain className="w-3 h-3 inline mr-1" />
        Vue avancee
      </button>
    </div>
  );
};

// === PERFORMANCE STRIP ===
const PerformanceStrip = ({ metrics }: { metrics: FundMetrics | null }) => {
  const { viewMode } = useViewMode();
  
  if (!metrics) {
    return (
      <div className="text-xs text-gray-500 italic">
        Performances indisponibles
      </div>
    );
  }
  
  const items = viewMode === 'simple' 
    ? [
        { label: '1M', value: metrics.perf_1m },
        { label: '1A', value: metrics.perf_1y },
      ]
    : [
        { label: '1S', value: metrics.perf_1w },
        { label: '1M', value: metrics.perf_1m },
        { label: '1A', value: metrics.perf_1y },
        { label: '3A', value: metrics.perf_3y },
      ];
  
  // Check if all performance values are null
  const hasAnyPerf = items.some(item => item.value != null);
  
  if (!hasAnyPerf) {
    return (
      <div className="text-xs text-gray-500 italic">
        Performances indisponibles
      </div>
    );
  }
  
  return (
    <div className="flex flex-wrap gap-3">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1">
          <span className="text-xs text-gray-400">{item.label}:</span>
          {item.value != null ? (
            <span className={`text-xs font-bold flex items-center ${item.value >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {item.value >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
              {item.value.toFixed(2)}%
            </span>
          ) : (
            <span className="text-xs text-gray-500">N/A</span>
          )}
        </div>
      ))}
      {viewMode === 'advanced' && (
        <div className="flex items-center gap-1">
          <span className="text-xs text-gray-400">Vol:</span>
          {metrics.vol_60d != null ? (
            <span className="text-xs font-bold text-amber-400">{metrics.vol_60d.toFixed(1)}%</span>
          ) : (
            <span className="text-xs text-gray-500">N/A</span>
          )}
        </div>
      )}
    </div>
  );
};

// === FUND CARD COMPONENT (Reorganized V1.1) ===
const FundCard = ({ fund, rank }: { fund: Fund; rank?: number }) => {
  const { viewMode } = useViewMode();
  const [expanded, setExpanded] = useState(false);
  
  const isTopRank = rank && rank <= 3;
  const isTop1 = rank === 1;
  const isTop2 = rank === 2;
  const isTop3 = rank === 3;
  
  // Neon glow classes for top 3
  const topRankStyles = isTop1 
    ? 'ring-2 ring-amber-400/70 shadow-xl shadow-amber-500/30 border-amber-500/50' 
    : isTop2 
    ? 'ring-2 ring-sky-400/60 shadow-lg shadow-sky-500/25 border-sky-500/50' 
    : isTop3 
    ? 'ring-1 ring-violet-400/50 shadow-lg shadow-violet-500/20 border-violet-500/50' 
    : '';
  
  return (
    <Card className={`
      gradient-border hover:scale-[1.02] transition-all duration-300
      ${isTopRank ? topRankStyles : 'hover:shadow-lg hover:shadow-sky-500/5'}
    `}>
      <CardContent className="p-4">
        {/* === ZONE TOP: Rang + Nom + Score Global === */}
        <div className="flex justify-between items-start mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              {rank && (
                <span className={`
                  font-bold text-sm px-2 py-0.5 rounded transition-all
                  ${isTop1 ? 'bg-gradient-to-r from-amber-500 to-yellow-400 text-gray-900 shadow-lg shadow-amber-500/40' : ''}
                  ${isTop2 ? 'bg-gradient-to-r from-sky-500 to-cyan-400 text-gray-900 shadow-md shadow-sky-500/30' : ''}
                  ${isTop3 ? 'bg-gradient-to-r from-violet-500 to-purple-400 text-white shadow-md shadow-violet-500/30' : ''}
                  ${!isTopRank ? 'bg-gray-700 text-gray-300' : ''}
                `}>
                  #{rank}
                </span>
              )}
              <h3 className="font-semibold text-sm truncate text-white">{fund.name}</h3>
            </div>
            <p className="text-xs text-gray-500 font-mono">{fund.isin}</p>
          </div>
          
          {/* Score Global - Prominent with glow for top ranks */}
          {fund.fundamental_score != null ? (
            <div className="text-right ml-3">
              <div className={`text-2xl font-bold leading-none ${
                isTop1 ? 'text-amber-400 drop-shadow-[0_0_8px_rgba(251,191,36,0.5)]' :
                isTop2 ? 'text-sky-400 drop-shadow-[0_0_6px_rgba(56,189,248,0.4)]' :
                isTop3 ? 'text-violet-400 drop-shadow-[0_0_6px_rgba(167,139,250,0.4)]' :
                'text-sky-400'
              }`}>
                {fund.fundamental_score.toFixed(0)}
              </div>
              <div className="text-xs text-gray-500">/100</div>
            </div>
          ) : (
            <div className="text-right ml-3">
              <div className="text-sm text-gray-500 italic">N/A</div>
            </div>
          )}
        </div>
        
        {/* === ZONE BADGES: SRI + Classe + Priorite === */}
        <div className="flex flex-wrap gap-1.5 mb-3">
          <SRIBadge sri={fund.sri} />
          <AssetClassBadge assetClass={fund.asset_class} />
          {fund.priority && <PriorityBadge priority={fund.priority} />}
        </div>
        
        {/* === ZONE PROFIL: 3 barres HiTrade === */}
        <div className="py-3 border-t border-b border-gray-700/50">
          <BrainProfile 
            quality={fund.quality_score}
            valuation={fund.valuation_score}
            stability={fund.stability_score}
          />
        </div>
        
        {/* === ZONE PERFORMANCE === */}
        <div className="mt-3">
          <PerformanceStrip metrics={fund.metrics} />
        </div>
        
        {/* === ZONE CONFIANCE (Vue simple) === */}
        {viewMode === 'simple' && fund.confidence != null && (
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-gray-400">Confiance analyse</span>
            <span className="font-medium text-sky-300">{(fund.confidence * 100).toFixed(0)}%</span>
          </div>
        )}
        
        {/* === ZONE DETAILS AVANCES (Vue avancee ou expanded) === */}
        {(viewMode === 'advanced' || expanded) && (
          <div className="mt-3 pt-3 border-t border-gray-700/50 space-y-2">
            {/* Metriques detaillees */}
            {fund.metrics && (
              <div className="grid grid-cols-2 gap-2 text-xs">
                {fund.metrics.sharpe_ratio != null && (
                  <div>
                    <span className="text-gray-500">Sharpe:</span>
                    <span className="ml-1 text-white font-medium">{fund.metrics.sharpe_ratio.toFixed(2)}</span>
                  </div>
                )}
                {fund.metrics.sortino_ratio != null && (
                  <div>
                    <span className="text-gray-500">Sortino:</span>
                    <span className="ml-1 text-white font-medium">{fund.metrics.sortino_ratio.toFixed(2)}</span>
                  </div>
                )}
                {fund.metrics.max_drawdown != null && (
                  <div>
                    <span className="text-gray-500">Max DD:</span>
                    <span className="ml-1 text-rose-400 font-medium">-{fund.metrics.max_drawdown.toFixed(1)}%</span>
                  </div>
                )}
              </div>
            )}
            
            {/* Confiance */}
            {fund.confidence != null && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-400">Confiance analyse</span>
                <div className="flex items-center gap-2">
                  <Progress value={fund.confidence * 100} className="w-16 h-1.5" />
                  <span className="font-medium text-sky-300">{(fund.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            )}
            
            {/* Reasoning */}
            {fund.reasoning && (
              <p className="text-xs text-gray-400 italic bg-gray-800/50 p-2 rounded">
                {fund.reasoning}
              </p>
            )}
            
            {/* Societe de gestion */}
            {fund.management_company && (
              <p className="text-xs text-gray-500 truncate">
                {fund.management_company}
              </p>
            )}
          </div>
        )}
        
        {/* Toggle details (Vue simple only) */}
        {viewMode === 'simple' && (
          <button 
            onClick={() => setExpanded(!expanded)}
            className="mt-2 w-full flex items-center justify-center gap-1 text-xs text-gray-500 hover:text-sky-400 transition-colors"
          >
            {expanded ? (
              <>Moins de details <ChevronUp className="w-3 h-3" /></>
            ) : (
              <>Plus de details <ChevronDown className="w-3 h-3" /></>
            )}
          </button>
        )}
      </CardContent>
    </Card>
  );
};

const PortfolioWizard = ({ onClose, onComplete }: { onClose: () => void; onComplete: (portfolio: PortfolioSuggestion) => void }) => {
  const [step, setStep] = useState(1);
  const [amount, setAmount] = useState<string>('100000');
  const [horizon, setHorizon] = useState<string>('medium');
  const [targetSri, setTargetSri] = useState<number[]>([4]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);

  // Presets configuration
  const presets = [
    { 
      id: 'prudent', 
      label: 'Prudent', 
      sri: 2, 
      horizon: 'short',
      icon: <Shield className="w-4 h-4" />,
      color: 'border-emerald-500 bg-emerald-500/10 text-emerald-400',
      description: 'On privilegie les fonds stables, drawdown limite, peu de volatilite.'
    },
    { 
      id: 'equilibre', 
      label: 'Equilibre', 
      sri: 4, 
      horizon: 'medium',
      icon: <Target className="w-4 h-4" />,
      color: 'border-sky-500 bg-sky-500/10 text-sky-400',
      description: 'On equilibre qualite de gestion et opportunites de valorisation.'
    },
    { 
      id: 'dynamique', 
      label: 'Dynamique', 
      sri: 6, 
      horizon: 'long',
      icon: <Zap className="w-4 h-4" />,
      color: 'border-violet-500 bg-violet-500/10 text-violet-400',
      description: 'On accepte plus de volatilite pour chercher davantage de performance.'
    },
  ];

  const handlePresetSelect = (preset: typeof presets[0]) => {
    setSelectedPreset(preset.id);
    setTargetSri([preset.sri]);
    setHorizon(preset.horizon);
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_URL}/api/portfolio/suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount: parseFloat(amount),
          horizon,
          target_sri: targetSri[0],
          sri_tolerance: 1,
        }),
      });
      
      if (!response.ok) throw new Error('Failed to generate portfolio');
      
      const data = await response.json();
      onComplete(data);
    } catch (err) {
      setError('Erreur lors de la generation du portefeuille');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all ${
                s === step
                  ? 'bg-sky-500 text-white neon-glow'
                  : s < step
                  ? 'bg-sky-600 text-white'
                  : 'bg-gray-600 text-gray-300'
              }`}
            >
              {s}
            </div>
          ))}
        </div>
        <span className="text-sm text-gray-300">Etape {step}/3</span>
      </div>

      {step === 1 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <Calculator className="w-5 h-5 text-sky-400" />
            <h3 className="text-lg font-semibold text-white">Montant a investir</h3>
          </div>
          <div className="space-y-2">
            <Label htmlFor="amount" className="text-gray-200">Montant (EUR)</Label>
            <Input
              id="amount"
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="bg-gray-700 border-gray-600 text-white text-lg font-mono"
              placeholder="100000"
            />
          </div>
          <p className="text-sm text-gray-300">
            Entrez le montant total que vous souhaitez investir.
          </p>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-5 h-5 text-sky-400" />
            <h3 className="text-lg font-semibold text-white">Horizon de placement</h3>
          </div>
          <div className="space-y-2">
            <Label className="text-gray-200">Duree d'investissement</Label>
            <Select value={horizon} onValueChange={setHorizon}>
              <SelectTrigger className="bg-gray-700 border-gray-600 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-gray-700 border-gray-600">
                <SelectItem value="short">Court terme (0-3 ans)</SelectItem>
                <SelectItem value="medium">Moyen terme (3-7 ans)</SelectItem>
                <SelectItem value="long">Long terme (7+ ans)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <p className="text-sm text-gray-300">
            {horizon === 'short' && 'Ideal pour des objectifs a court terme. Privilegiera les fonds stables et liquides.'}
            {horizon === 'medium' && 'Equilibre entre croissance et stabilite. Mix diversifie de classes d\'actifs.'}
            {horizon === 'long' && 'Maximise le potentiel de croissance. Plus d\'exposition aux actions.'}
          </p>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-5 h-5 text-sky-400" />
            <h3 className="text-lg font-semibold text-white">Niveau de risque cible</h3>
          </div>
          
          {/* === PRESETS === */}
          <div className="grid grid-cols-3 gap-2 mb-4">
            {presets.map((preset) => (
              <button
                key={preset.id}
                onClick={() => handlePresetSelect(preset)}
                className={`p-3 rounded-lg border-2 transition-all text-center ${
                  selectedPreset === preset.id 
                    ? preset.color + ' shadow-lg' 
                    : 'border-gray-600 bg-gray-700/50 text-gray-300 hover:border-gray-500'
                }`}
              >
                <div className="flex justify-center mb-1">{preset.icon}</div>
                <div className="text-sm font-medium">{preset.label}</div>
              </button>
            ))}
          </div>
          
          {/* Preset description */}
          {selectedPreset && (
            <div className="p-3 rounded-lg bg-gray-700/50 border border-gray-600 mb-4">
              <p className="text-sm text-gray-200">
                {presets.find(p => p.id === selectedPreset)?.description}
              </p>
            </div>
          )}
          
          <div className="space-y-4">
            <Label className="text-gray-200">SRI cible: {targetSri[0]}</Label>
            <Slider
              value={targetSri}
              onValueChange={(v) => { setTargetSri(v); setSelectedPreset(null); }}
              min={1}
              max={7}
              step={1}
              className="py-4"
            />
            <div className="flex justify-between text-xs text-gray-300">
              <span>1 - Prudent</span>
              <span>4 - Equilibre</span>
              <span>7 - Dynamique</span>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="p-3 rounded-lg bg-red-600/30 border border-red-500 text-red-300 text-sm font-medium">
          {error}
        </div>
      )}

      <div className="flex justify-between pt-4">
        <Button
          variant="outline"
          onClick={() => step === 1 ? onClose() : setStep(step - 1)}
          className="border-gray-500 text-white hover:bg-gray-700"
        >
          <ChevronLeft className="w-4 h-4 mr-1" />
          {step === 1 ? 'Annuler' : 'Retour'}
        </Button>
        
        {step < 3 ? (
          <Button
            onClick={() => setStep(step + 1)}
            className="bg-sky-500 hover:bg-sky-600 text-white font-semibold"
          >
            Suivant
            <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            disabled={loading}
            className="bg-sky-500 hover:bg-sky-600 text-white font-semibold"
          >
            {loading ? (
              <>
                <Zap className="w-4 h-4 mr-1 animate-pulse" />
                Generation...
              </>
            ) : (
              <>
                <Brain className="w-4 h-4 mr-1" />
                Generer le portefeuille
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
};

const PortfolioResults = ({ portfolio, onClose }: { portfolio: PortfolioSuggestion; onClose: () => void }) => {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-gray-700/50 border-gray-600">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-sky-400">
              {portfolio.total_amount.toLocaleString('fr-FR')} EUR
            </p>
            <p className="text-xs text-gray-300">Montant total</p>
          </CardContent>
        </Card>
        <Card className="bg-gray-700/50 border-gray-600">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-violet-400">{portfolio.num_funds}</p>
            <p className="text-xs text-gray-300">Fonds</p>
          </CardContent>
        </Card>
        <Card className="bg-gray-700/50 border-gray-600">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-amber-400">{portfolio.average_sri.toFixed(1)}</p>
            <p className="text-xs text-gray-300">SRI moyen</p>
          </CardContent>
        </Card>
        <Card className="bg-gray-700/50 border-gray-600">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-emerald-400">
              {Object.keys(portfolio.asset_class_distribution).length}
            </p>
            <p className="text-xs text-gray-300">Classes d'actifs</p>
          </CardContent>
        </Card>
      </div>

      <Card className="bg-gray-700/50 border-gray-600">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2 text-white">
            <PieChart className="w-4 h-4 text-sky-400" />
            Repartition par classe d'actifs
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {Object.entries(portfolio.asset_class_distribution).map(([cls, pct]) => (
              <Badge key={cls} variant="outline" className="bg-violet-600 border-violet-500 text-white font-medium">
                {cls}: {pct.toFixed(1)}%
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-gray-700/50 border-gray-600">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2 text-white">
            <Brain className="w-4 h-4 text-sky-400" />
            Analyse HiTrade V1
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-200">{portfolio.explanation}</p>
          {(portfolio.average_confidence != null || portfolio.consensus_summary) && (
            <div className="mt-3 pt-3 border-t border-gray-600/50 grid grid-cols-2 gap-4">
              {portfolio.average_confidence != null && (
                <div>
                  <span className="text-xs text-gray-400">Confiance moyenne</span>
                  <p className="text-lg font-bold text-sky-400">{(portfolio.average_confidence * 100).toFixed(0)}%</p>
                </div>
              )}
              {portfolio.consensus_summary && (
                <div>
                  <span className="text-xs text-gray-400">Repartition priorites</span>
                  <p className="text-sm text-gray-200">{portfolio.consensus_summary}</p>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="space-y-3">
        <h4 className="font-semibold flex items-center gap-2 text-white">
          <BarChart3 className="w-4 h-4 text-sky-400" />
          Allocations detaillees
        </h4>
        <ScrollArea className="h-64">
          <div className="space-y-2">
            {portfolio.allocations.map((alloc, idx) => (
              <Card key={alloc.fund.isin} className="bg-gray-700/30 border-gray-600/50">
                <CardContent className="p-3">
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sky-400 font-bold text-xs">#{idx + 1}</span>
                        <span className="font-medium text-sm truncate text-white">{alloc.fund.name}</span>
                      </div>
                      <p className="text-xs text-gray-400 font-mono">{alloc.fund.isin}</p>
                    </div>
                    <div className="text-right ml-2">
                      <p className="font-bold text-sky-400">{alloc.allocation_percent.toFixed(1)}%</p>
                      <p className="text-xs text-gray-300">
                        {alloc.amount_eur.toLocaleString('fr-FR')} EUR
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-2 flex-wrap">
                    <SRIBadge sri={alloc.fund.sri} />
                    <AssetClassBadge assetClass={alloc.fund.asset_class} />
                    {alloc.fund.priority && <PriorityBadge priority={alloc.fund.priority} />}
                    {alloc.fund.fundamental_score && (
                      <Badge variant="outline" className="bg-sky-600 border-sky-500 text-white font-medium text-xs">
                        Score: {alloc.fund.fundamental_score.toFixed(0)}
                      </Badge>
                    )}
                    {alloc.fund.confidence != null && (
                      <Badge variant="outline" className="bg-violet-600 border-violet-500 text-white font-medium text-xs">
                        Conf: {(alloc.fund.confidence * 100).toFixed(0)}%
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </ScrollArea>
      </div>

      <Button onClick={onClose} className="w-full bg-sky-500 hover:bg-sky-600 text-white font-semibold">
        Fermer
      </Button>
    </div>
  );
};

function App() {
  const [topFunds, setTopFunds] = useState<Fund[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [portfolio, setPortfolio] = useState<PortfolioSuggestion | null>(null);
  const [activeTab, setActiveTab] = useState('top-week');
  const [rankedFunds, setRankedFunds] = useState<Fund[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('simple');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [topRes, statsRes] = await Promise.all([
          fetch(`${API_URL}/api/top-week?limit=20`),
          fetch(`${API_URL}/api/stats`),
        ]);
        
        if (topRes.ok) {
          const topData = await topRes.json();
          setTopFunds(topData);
        }
        
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setStats(statsData);
        }
      } catch (err) {
        console.error('Error fetching data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const fetchRankedFunds = async () => {
    try {
      const res = await fetch(`${API_URL}/api/ranked?limit=50`);
      if (res.ok) {
        const data = await res.json();
        setRankedFunds(data);
      }
    } catch (err) {
      console.error('Error fetching ranked funds:', err);
    }
  };

  useEffect(() => {
    if (activeTab === 'ranked' && rankedFunds.length === 0) {
      fetchRankedFunds();
    }
  }, [activeTab, rankedFunds.length]);

  const handlePortfolioComplete = (newPortfolio: PortfolioSuggestion) => {
    setPortfolio(newPortfolio);
    setWizardOpen(false);
  };

  return (
    <ViewModeContext.Provider value={{ viewMode, setViewMode }}>
      <div className="min-h-screen bg-background">
        {/* === HEADER with gradient === */}
        <header className="sticky top-0 z-50 border-b border-gray-700 bg-gradient-to-r from-sky-900/40 via-slate-900 to-violet-900/40 backdrop-blur">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-sky-500 to-violet-500 flex items-center justify-center shadow-lg shadow-sky-500/50">
                  <Brain className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-sky-400 drop-shadow-[0_0_10px_rgba(56,189,248,0.5)]">
                    HiTrade
                  </h1>
                  <p className="text-xs text-gray-400">Cerveau Fondamental V1.1</p>
                </div>
              </div>
              
              <button
                className="lg:hidden p-2 rounded-lg bg-gray-700 text-white"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>

              <div className="hidden lg:flex items-center gap-4">
                <ViewModeToggle />
                {stats && (
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-gray-300">
                      <span className="text-sky-400 font-bold">{stats.total_funds}</span> fonds analyses
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="lg:hidden fixed inset-0 z-40 bg-gray-900/98 backdrop-blur pt-20">
            <div className="container mx-auto px-4 py-6 space-y-4">
              <div className="flex justify-center mb-4">
                <ViewModeToggle />
              </div>
              <Dialog open={wizardOpen} onOpenChange={setWizardOpen}>
                <DialogTrigger asChild>
                  <Button className="w-full bg-sky-500 hover:bg-sky-600 text-white font-semibold shadow-lg shadow-sky-500/30">
                    <Briefcase className="w-4 h-4 mr-2" />
                    Creer un portefeuille
                  </Button>
                </DialogTrigger>
              </Dialog>
              <Button variant="outline" className="w-full border-gray-600 text-white hover:bg-gray-700">
                <Eye className="w-4 h-4 mr-2" />
                Voir tous les fonds
              </Button>
            </div>
          </div>
        )}

      <main className="container mx-auto px-4 py-6">
        <div className="flex flex-col lg:flex-row gap-6">
          <div className="flex-1">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="w-full bg-gray-800 border border-gray-700 mb-6">
                <TabsTrigger value="top-week" className="flex-1 text-gray-300 data-[state=active]:bg-sky-600 data-[state=active]:text-white">
                  <TrendingUp className="w-4 h-4 mr-2" />
                  Top de la semaine
                </TabsTrigger>
                <TabsTrigger value="ranked" className="flex-1 text-gray-300 data-[state=active]:bg-sky-600 data-[state=active]:text-white">
                  <Brain className="w-4 h-4 mr-2" />
                  Classement Fondamental
                </TabsTrigger>
              </TabsList>

              <TabsContent value="top-week" className="mt-0">
                <div className="mb-4">
                  <h2 className="text-lg font-semibold flex items-center gap-2 text-white">
                    <TrendingUp className="w-5 h-5 text-sky-400" />
                    Top Investissements de la Semaine
                  </h2>
                  <p className="text-sm text-gray-400">
                    Classes par performance ajustee au risque (perf_1w / (1 + vol_60d))
                  </p>
                </div>

                {loading ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {[...Array(6)].map((_, i) => (
                      <Card key={i} className="bg-gray-800 animate-pulse h-48" />
                    ))}
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {topFunds.map((fund, idx) => (
                      <FundCard key={fund.isin} fund={fund} rank={idx + 1} />
                    ))}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="ranked" className="mt-0">
                <div className="mb-4">
                  <h2 className="text-lg font-semibold flex items-center gap-2 text-white">
                    <Brain className="w-5 h-5 text-sky-400" />
                    Classement Fondamental
                  </h2>
                  <p className="text-sm text-gray-400">
                    Score base sur performance, volatilite, SRI et adequation a l'horizon
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {rankedFunds.map((fund, idx) => (
                    <FundCard key={fund.isin} fund={fund} rank={idx + 1} />
                  ))}
                </div>
              </TabsContent>
            </Tabs>
          </div>

          <aside className="lg:w-80 space-y-4">
            <Card className="gradient-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-white">
                  <Zap className="w-4 h-4 text-sky-400" />
                  Actions rapides
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Dialog open={wizardOpen} onOpenChange={setWizardOpen}>
                  <DialogTrigger asChild>
                    <Button className="w-full bg-sky-500 hover:bg-sky-600 text-white font-semibold shadow-lg shadow-sky-500/30">
                      <Briefcase className="w-4 h-4 mr-2" />
                      Creer un portefeuille
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-lg bg-gray-800 border-gray-700">
                    <DialogHeader>
                      <DialogTitle className="flex items-center gap-2 text-white">
                        <Brain className="w-5 h-5 text-sky-400" />
                        Creer un portefeuille
                      </DialogTitle>
                    </DialogHeader>
                    <PortfolioWizard
                      onClose={() => setWizardOpen(false)}
                      onComplete={handlePortfolioComplete}
                    />
                  </DialogContent>
                </Dialog>

                <Button variant="outline" className="w-full border-gray-600 text-white hover:bg-gray-700">
                  <Eye className="w-4 h-4 mr-2" />
                  Voir tous les fonds
                </Button>

                <Button variant="outline" className="w-full border-gray-600 text-white hover:bg-gray-700">
                  <Calculator className="w-4 h-4 mr-2" />
                  Simuler un investissement
                </Button>
              </CardContent>
            </Card>

            {stats && (
              <Card className="gradient-border">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2 text-white">
                    <BarChart3 className="w-4 h-4 text-sky-400" />
                    Statistiques
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="text-center p-3 rounded-lg bg-gray-700/50">
                      <p className="text-2xl font-bold text-sky-400">{stats.total_funds}</p>
                      <p className="text-xs text-gray-300">Fonds totaux</p>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-gray-700/50">
                      <p className="text-2xl font-bold text-violet-400">{stats.standard_isin_funds}</p>
                      <p className="text-xs text-gray-300">ISIN standards</p>
                    </div>
                  </div>

                  <div>
                    <p className="text-xs text-gray-300 mb-2">Distribution SRI</p>
                    <div className="flex gap-1">
                      {Object.entries(stats.sri_distribution).map(([sri, count]) => (
                        <div
                          key={sri}
                          className="flex-1 text-center"
                          title={`SRI ${sri}: ${count} fonds`}
                        >
                          <div
                            className="bg-gradient-to-t from-sky-500/40 to-violet-500/40 rounded-t"
                            style={{ height: `${Math.max(4, (count / stats.total_funds) * 200)}px` }}
                          />
                          <span className="text-xs text-gray-300">{sri}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            <Card className="gradient-border">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-white">
                  <Brain className="w-4 h-4 text-sky-400" />
                  A propos du Cerveau
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-gray-300">
                  <span className="text-sky-400 font-semibold">HiTrade V1.1</span> - Le Cerveau Fondamental 
                  analyse chaque fonds selon 3 dimensions: Qualite de Gestion (40%), 
                  Valorisation (30%), et Stabilite (30%). Chaque analyse inclut un 
                  score de confiance et une priorite.
                </p>
              </CardContent>
            </Card>
          </aside>
        </div>
      </main>

        <Dialog open={portfolio !== null} onOpenChange={() => setPortfolio(null)}>
          <DialogContent className="max-w-2xl bg-gray-800 border-gray-700 max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-white">
                <Briefcase className="w-5 h-5 text-sky-400" />
                Votre portefeuille optimise
              </DialogTitle>
            </DialogHeader>
            {portfolio && (
              <PortfolioResults
                portfolio={portfolio}
                onClose={() => setPortfolio(null)}
              />
            )}
          </DialogContent>
        </Dialog>
      </div>
    </ViewModeContext.Provider>
  );
}

export default App
