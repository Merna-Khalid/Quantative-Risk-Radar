import { create } from 'zustand';

export const useRiskStore = create((set, get) => ({
  // State
  riskHistory: [],
  summaryData: null,
  currentMetrics: {},
  systemicData: null,
  isLoading: false,
  error: null,
  lastUpdated: null,
  
  // Actions
  setRiskData: (data) => {
    if (data && data.data && Array.isArray(data.data)) {
      set({ 
        riskHistory: data.data,
        summaryData: data.summary || null,
        currentMetrics: data.current_metrics || {},
        lastUpdated: new Date(),
        error: null 
      });
    } else if (Array.isArray(data)) {
      // Legacy array format
      set({ 
        riskHistory: data,
        summaryData: null,
        currentMetrics: {},
        lastUpdated: new Date(),
        error: null 
      });
    } else {
      console.error('Invalid data format in setRiskData:', data);
      set({ riskHistory: [], summaryData: null, currentMetrics: {}, error: 'Invalid data format' });
    }
  },
  
  setRealtimeData: (realtimeData) => set({ 
    currentMetrics: realtimeData,
    lastUpdated: new Date()
  }),
  
  setSummaryData: (summaryData) => set({ summaryData }),
  
  setCurrentMetrics: (metrics) => set({ 
    currentMetrics: metrics,
    lastUpdated: new Date() 
  }),
  
  setLoading: (loading) => set({ isLoading: loading }),
  
  setError: (error) => set({ error }),
  
  getLatestRisk: () => {
    const history = get().riskHistory;
    return history.length > 0 ? history[history.length - 1] : {};
  },
  
  getDisplayData: () => {
    const history = get().riskHistory;
    return history;
  },
  
  getSummaryData: () => {
    return get().summaryData;
  },
  
  getRiskSignals: () => {
    const currentMetrics = get().currentMetrics;
    if (!currentMetrics) return {};
    
    return {
      // Core components
      systemic: currentMetrics.systemic_risk,
      pca: currentMetrics.component_analysis?.current_pca,
      credit: currentMetrics.component_analysis?.current_credit,
      
      // Risk signals
      quantileSignal: currentMetrics.quantile_signal,
      dccCorrelation: currentMetrics.dcc_correlation,
      harExcessVol: currentMetrics.har_excess_vol,
      creditSpreadChange: currentMetrics.credit_spread_change,
      vixChange: currentMetrics.vix_change,
      isWarning: currentMetrics.composite_warning,
      compositeRiskScore: currentMetrics.composite_risk_score,
      
      // Metadata
      timestamp: currentMetrics.timestamp
    };
  },
  
  getSignalAnalysis: () => {
    const currentMetrics = get().currentMetrics;
    if (!currentMetrics) return {};
    
    return {
      regime: currentMetrics.regime_details,
      componentAnalysis: currentMetrics.component_analysis,
      signalAnalysis: currentMetrics.signal_analysis,
      pcaVariance: currentMetrics.pca_variance,
      quantileSummary: currentMetrics.quantile_summary
    };
  },
  
  getCurrentRegime: () => {
    const currentMetrics = get().currentMetrics;
    if (!currentMetrics) return { level: 'unknown', details: {} };
    
    return {
      level: currentMetrics.risk_level,
      details: currentMetrics.regime_details || {},
      score: currentMetrics.regime_details?.regime_score || 0,
      zScores: currentMetrics.regime_details?.component_z_scores || {}
    };
  },
  
  getWarningStatus: () => {
    const currentMetrics = get().currentMetrics;
    
    if (!currentMetrics) return { isWarning: false, reasons: [] };
    
    const isWarning = currentMetrics.composite_warning || false;
    const reasons = [];
    
    if (currentMetrics.har_excess_vol > 2.0) {
      reasons.push('HAR Excess Volatility above threshold');
    }
    if (currentMetrics.dcc_correlation > 0.95) {
      reasons.push('DCC Correlation elevated');
    }
    if (currentMetrics.systemic_risk > (currentMetrics.systemic_mean + currentMetrics.systemic_std)) {
      reasons.push('Systemic risk above normal range');
    }
    
    return { isWarning, reasons };
  },
  
  // Get data for specific visualization types
  getVisualizationData: (type) => {
    const currentMetrics = get().currentMetrics;
    
    if (!currentMetrics) return null;
    
    switch (type) {
      case 'risk-cascade':
        return {
          systemic: currentMetrics.systemic_risk,
          pca: currentMetrics.component_analysis?.current_pca,
          credit: currentMetrics.component_analysis?.current_credit,
          quantile: currentMetrics.quantile_signal,
          dcc: currentMetrics.dcc_correlation,
          har: currentMetrics.har_excess_vol,
          composite: currentMetrics.composite_risk_score,
          warnings: currentMetrics.composite_warning
        };
        
      case 'component-breakdown':
        return {
          components: {
            pca: currentMetrics.component_analysis?.current_pca,
            credit: currentMetrics.component_analysis?.current_credit,
            systemic: currentMetrics.systemic_risk
          },
          contributions: currentMetrics.component_analysis || {},
          correlations: currentMetrics.component_analysis?.correlation_matrix || {}
        };
        
      case 'signal-timeline':
        const history = get().riskHistory;
        return {
          timestamps: history.map(d => d.date),
          signals: {
            systemic: history.map(d => d.systemic_risk),
            quantile: history.map(d => d.quantile_signal),
            dcc: history.map(d => d.dcc_correlation),
            har: history.map(d => d.har_excess_vol),
            composite: history.map(d => d.composite_risk_score)
          },
          warnings: history.map(d => d.is_warning)
        };
        
      default:
        return currentMetrics;
    }
  },
  
  getDashboardMetrics: () => {
    const currentMetrics = get().currentMetrics;
    
    return {
      // Core metrics
      systemicRisk: currentMetrics.systemic_risk,
      riskLevel: currentMetrics.risk_level,
      compositeScore: currentMetrics.composite_risk_score,
      
      // Signal metrics
      harExcessVol: currentMetrics.har_excess_vol,
      dccCorrelation: currentMetrics.dcc_correlation,
      quantileSignal: currentMetrics.quantile_signal,
      
      // Status
      isWarning: currentMetrics.composite_warning || false,
      dataPoints: currentMetrics.data_points,
      lastUpdated: get().lastUpdated
    };
  },
  
  hasComprehensiveData: () => {
    const currentMetrics = get().currentMetrics;
    return currentMetrics && 
           currentMetrics.systemic_risk !== undefined && 
           currentMetrics.risk_level !== undefined;
  },
  
  // Reset state
  reset: () => set({
    riskHistory: [],
    summaryData: null,
    currentMetrics: {},
    isLoading: false,
    error: null,
    lastUpdated: null
  })
}));