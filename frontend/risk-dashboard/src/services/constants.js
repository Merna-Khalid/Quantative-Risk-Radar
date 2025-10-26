export const API_BASE_URL = 'http://localhost:8000';

export const RISK_REGIMES = {
  RED: { 
    color: 'text-red-400', 
    bg: 'bg-red-900/30', 
    border: 'border-red-500', 
    label: 'CRISIS', 
    shadow: 'shadow-red-500/50',
    threshold: 0.5
  },
  YELLOW: { 
    color: 'text-yellow-400', 
    bg: 'bg-yellow-900/30', 
    border: 'border-yellow-500', 
    label: 'FRAGILE', 
    shadow: 'shadow-yellow-500/50',
    threshold: 0.0
  },
  GREEN: { 
    color: 'text-green-400', 
    bg: 'bg-green-900/30', 
    border: 'border-green-500', 
    label: 'NORMAL', 
    shadow: 'shadow-green-500/50',
    threshold: -2.0
  }
};

export const CHART_CONFIG = {
  colors: {
    systemic: '#f87171',    // Red-400
    pca: '#60a5fa',         // Blue-400  
    credit: '#fbbf24',      // Amber-400
    volatility: '#34d399',  // Emerald-400
    correlation: '#a78bfa'  // Violet-400
  },
  displayPoints: 250,
  refreshIntervals: {
    realtime: 2000,
    history: 30000,
    metrics: 15000
  }
};