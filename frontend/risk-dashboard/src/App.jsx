import React, { useState, useEffect } from 'react';
import { useRiskData } from './hooks/useRiskData';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';
import { TrafficLight } from './components/indicators/TrafficLight';
import { MetricCard } from './components/indicators/MetricCard';
import { RiskTimelineChart } from './components/charts/RiskTimelineChart';
import { RefreshControls } from './components/controls/RefreshControls';
import { CHART_CONFIG } from './services/constants';

const App = () => {
  const [daysRange, setDaysRange] = useState(180);
  const [dateRange, setDateRange] = useState({ startDate: '', endDate: '' });
  const [rangeMode, setRangeMode] = useState('days');
  const [appliedRange, setAppliedRange] = useState(daysRange);
  const [showAllSignals, setShowAllSignals] = useState(false);

  const {
    displayData,
    latestRisk,
    currentMetrics,
    summaryData,
    isLoading,
    error,
    lastUpdated,
    refreshData,
    hasData,
    wsConnected
  } = useRiskData(appliedRange);

  useEffect(() => {
    if (rangeMode === 'days') setAppliedRange(daysRange);
  }, [daysRange, rangeMode]);

  useEffect(() => {
    const handleToggleSignals = (event) => {
      setShowAllSignals(event.detail);
    };

    window.addEventListener('toggleSignals', handleToggleSignals);
    return () => window.removeEventListener('toggleSignals', handleToggleSignals);
  }, []);

  // Handle switching between "days" and "dates" modes
  const handleRangeModeChange = (mode) => {
    setRangeMode(mode);
    if (mode === 'days') {
      setDateRange({ startDate: '', endDate: '' });
      setAppliedRange(daysRange);
    }
  };

  const handleDateRangeChange = (field, value) => {
    setDateRange((prev) => ({ ...prev, [field]: value }));
  };

  const handleApplyDateRange = () => {
    if (dateRange.startDate && dateRange.endDate) {
      console.log('Applying date range:', dateRange);
      setAppliedRange({
        startDate: dateRange.startDate,
        endDate: dateRange.endDate
      });
    } else {
      alert('Please select both start and end dates');
    }
  };

  const handleDataPointClick = (data) => {
    console.log('Enhanced data point clicked:', data);
  };

  const handleRefresh = () => refreshData(false);
  const handleForceRefresh = () => refreshData(true);

  const currentRisk = currentMetrics || latestRisk || {};

  const calculatePeriodMetrics = () => {
    if (!displayData.length) {
      console.log('No display data available');
      return currentRisk;
    }

    console.log('=== COMPREHENSIVE RISK DEBUG ===');
    console.log('Current risk object:', currentRisk);
    console.log('Available currentRisk fields with values:');
    Object.keys(currentRisk).forEach(key => {
      const value = currentRisk[key];
      if (value !== null && value !== undefined) {
        console.log(`  ${key}:`, value, `(type: ${typeof value})`);
      }
    });
    console.log('=== END DEBUG ===');
    
    console.log('Display data length:', displayData.length);
    
    const systemicRisks = displayData.map(d => d.systemic_risk).filter(v => !isNaN(v) && v !== null && v !== undefined);
    const pcaScores = displayData.map(d => d.pca_signal_score).filter(v => !isNaN(v) && v !== null && v !== undefined);
    const creditScores = displayData.map(d => d.credit_signal_score).filter(v => !isNaN(v) && v !== null && v !== undefined);
    const zScores = displayData.map(d => d.z_score).filter(v => !isNaN(v) && v !== null && v !== undefined);
    
    console.log('Historical data availability:', {
      systemicRisks: systemicRisks.length,
      pcaScores: pcaScores.length,
      creditScores: creditScores.length,
      zScores: zScores.length
    });
    
    if (systemicRisks.length === 0) {
      console.log('No valid systemic risks found');
      return currentRisk;
    }
    
    const currentPCAScore = currentRisk.regime_details?.component_z_scores?.pca ?? null;
    const currentCreditScore = currentRisk.regime_details?.component_z_scores?.credit ?? null;

    const periodMean = systemicRisks.reduce((sum, val) => sum + val, 0) / systemicRisks.length;
    const periodStd = Math.sqrt(systemicRisks.reduce((sum, val) => sum + Math.pow(val - periodMean, 2), 0) / systemicRisks.length);
    const currentPeriodRisk = systemicRisks[systemicRisks.length - 1]; // Most recent in period
    
    const avgPCASignal = pcaScores.length > 0 ? pcaScores.reduce((sum, val) => sum + val, 0) / pcaScores.length : null;
    const avgCreditSignal = creditScores.length > 0 ? creditScores.reduce((sum, val) => sum + val, 0) / creditScores.length : null;
    const avgZScore = zScores.length > 0 ? zScores.reduce((sum, val) => sum + val, 0) / zScores.length : null;
    
    const highThreshold = periodMean + periodStd;
    const mediumThreshold = periodMean + 0.5 * periodStd;
    let periodRiskLevel = 'low';
    if (currentPeriodRisk >= highThreshold) periodRiskLevel = 'high';
    else if (currentPeriodRisk >= mediumThreshold) periodRiskLevel = 'medium';
    
    const calculatedMetrics = {
      systemic_risk: currentPeriodRisk,
      avg_systemic_risk: periodMean,
      
      systemic_mean: periodMean,
      systemic_std: periodStd,
      pca_signal_score: currentPCAScore ?? avgPCASignal,
      credit_signal_score: currentCreditScore ?? avgCreditSignal,
      z_score: currentRisk.systemic_risk ?? avgZScore,
      
      credit_spread: currentRisk.credit_spread,
      market_volatility: currentRisk.market_volatility,
      dcc_correlation: currentRisk.dcc_correlation,
      macro_oil: currentRisk.macro_oil,
      macro_fx: currentRisk.macro_fx,
      forecast_next_risk: currentRisk.forecast_next_risk,
      
      quantile_signal: currentRisk.quantile_signal,
      har_excess_vol: currentRisk.har_excess_vol,
      credit_spread_change: currentRisk.credit_spread_change,
      vix_change: currentRisk.vix_change,
      composite_warning: currentRisk.composite_warning,
      composite_risk_score: currentRisk.composite_risk_score,

      data_points: displayData.length,
      computation_duration: currentRisk.computation_duration,
      
      risk_level: periodRiskLevel,
      risk_interpretation: `Period Risk: ${periodRiskLevel.toUpperCase()}`,

      quantile_summary: currentRisk.quantile_summary,
      pca_variance: currentRisk.pca_variance,
      pca_metadata: currentRisk.pca_metadata,
      regime_details: currentRisk.regime_details,
      signal_analysis: currentRisk.signal_analysis,
      component_analysis: currentRisk.component_analysis,
      dcc_regime_analysis: currentRisk.dcc_regime_analysis,
      dcc_pair_correlations: currentRisk.dcc_pair_correlations,
      
      percentile: 0.5 + ((avgZScore || 0) / 6),
      
      relative_to_current: periodMean - (currentRisk.systemic_risk || 0),
      
      timestamp: currentRisk.timestamp,
      source: currentRisk.source,
      available_signals: currentRisk.available_signals
    };
    
    console.log('Final calculated COMPREHENSIVE period metrics:', {
      systemic_risk: calculatedMetrics.systemic_risk,
      dcc_correlation: calculatedMetrics.dcc_correlation,
      quantile_signal: calculatedMetrics.quantile_signal,
      har_excess_vol: calculatedMetrics.har_excess_vol,
      composite_risk_score: calculatedMetrics.composite_risk_score,
      risk_level: calculatedMetrics.risk_level
    });
    
    return calculatedMetrics;
  };

  const periodMetrics = calculatePeriodMetrics();

  const calculateRangeMetrics = () => {
    if (!displayData.length) return { 
      pcaSignal: 0, 
      creditSignal: 0,
      avgZScore: 0,
      avgPercentile: 0,
      regimeDistribution: { high: 0, medium: 0, low: 0 }
    };

    const pcaSum = displayData.reduce((s, i) => s + (i.pca_signal_score || 0), 0);
    const creditSum = displayData.reduce((s, i) => s + (i.credit_signal_score || 0), 0);
    const zScoreSum = displayData.reduce((s, i) => s + (i.z_score || 0), 0);
    const percentileSum = displayData.reduce((s, i) => s + (i.percentile || 0), 0);
    
    // Count regime distribution
    const regimeCount = displayData.reduce((acc, item) => {
      const regime = item.market_regime?.toLowerCase() || 'unknown';
      acc[regime] = (acc[regime] || 0) + 1;
      return acc;
    }, { high: 0, medium: 0, low: 0, unknown: 0 });

    const total = displayData.length;
    const regimeDistribution = {
      high: Math.round((regimeCount.high / total) * 100),
      medium: Math.round((regimeCount.medium / total) * 100),
      low: Math.round((regimeCount.low / total) * 100)
    };

    return { 
      pcaSignal: pcaSum / displayData.length, 
      creditSignal: creditSum / displayData.length,
      avgZScore: zScoreSum / displayData.length,
      avgPercentile: percentileSum / displayData.length,
      regimeDistribution
    };
  };

  const { pcaSignal, creditSignal, avgZScore, avgPercentile, regimeDistribution } = calculateRangeMetrics();

  const tradingDays = displayData.length;
  const calendarDays = typeof appliedRange === 'number' ? appliedRange : daysRange;
  const expectedTradingDays = Math.round(calendarDays * 0.7);
  const tradingCoveragePercentage =
    expectedTradingDays > 0 ? Math.round((tradingDays / expectedTradingDays) * 100) : 0;
  const dataDescription =
    tradingCoveragePercentage > 90
      ? 'Excellent coverage'
      : tradingCoveragePercentage > 70
      ? 'Good coverage'
      : tradingCoveragePercentage > 50
      ? 'Moderate coverage'
      : 'Limited coverage';

  const rangePresets = [
    { days: 30, label: '1M' },
    { days: 90, label: '3M' },
    { days: 180, label: '6M' },
    { days: 365, label: '1Y' },
    { days: 730, label: '2Y' },
    { days: 1825, label: '5Y' },
    { days: 3650, label: 'Max' }
  ];

  useEffect(() => {
    console.log('Current appliedRange:', appliedRange);
    console.log('Display data length:', displayData.length);
    console.log('Current comprehensive risk data:', currentRisk);
    console.log('Summary data:', summaryData);
    
    if (displayData.length > 0) {
      console.log('First display data item:', displayData[0]);
      console.log('Last display data item:', displayData[displayData.length - 1]);
    }
  }, [appliedRange, displayData, currentRisk, summaryData]);

  const maxHistoricalDays = 3650;

  const getQuantileMetrics = () => {
    const quantileSummary = periodMetrics.quantile_summary || {};
    if (!quantileSummary.var_95 && !quantileSummary.var_normal) return null;
    
    return {
      var95: quantileSummary.var_95,
      varNormal: quantileSummary.var_normal,
      capitalBuffer: quantileSummary.capital_buffer,
      corrMean: quantileSummary.corr_mean,
      corrVol: quantileSummary.corr_vol
    };
  };

  const quantileMetrics = getQuantileMetrics();

  const availableSignalsCount = currentRisk.available_signals?.length || 0;

  return (
    <div className="min-w-screen items-center min-h-screen bg-gradient-to-b from-gray-950 via-gray-900 to-black text-gray-100 font-inter tracking-wide selection:bg-indigo-500/30 selection:text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-8 py-8 space-y-10">
        <Header />


        <div className="flex items-center justify-center gap-4">
          {wsConnected && (
            <div className="flex items-center gap-2 px-3 py-1 bg-green-600/20 border border-green-500/30 rounded-lg text-green-400 text-sm">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              Live Data Connected
            </div>
          )}
          {availableSignalsCount > 0 && (
            <div className="flex items-center gap-2 px-3 py-1 bg-blue-600/20 border border-blue-500/30 rounded-lg text-blue-400 text-sm">
              <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
              {availableSignalsCount} Risk Signals Active
            </div>
          )}
        </div>

        {/* Error Display */}
        {error && (
          <div className="p-5 bg-gradient-to-r from-red-900/60 to-red-800/40 border border-red-700/40 text-red-200 rounded-2xl backdrop-blur-xl shadow-[0_0_30px_-5px_rgba(255,0,0,0.2)]">
            <p className="font-semibold text-lg flex items-center gap-2">⚠️ Data Error</p>
            <p className="text-sm mt-1 opacity-90">{error}</p>
            <button
              onClick={handleRefresh}
              className="mt-3 px-4 py-1.5 bg-red-600/80 text-white text-sm rounded-lg hover:bg-red-700 transition-all duration-200 shadow-md"
            >
              Retry
            </button>
          </div>
        )}

        {/* Controls */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <RefreshControls
            onRefresh={handleRefresh}
            onForceRefresh={handleForceRefresh}
            isLoading={isLoading}
            lastUpdated={lastUpdated}
          />

          {/* Range Controller */}
          <div className="bg-gradient-to-br from-gray-900/70 to-gray-800/50 border border-gray-700/40 rounded-2xl p-6 backdrop-blur-md w-full sm:w-auto min-w-[350px]">
            <div className="space-y-4">
              {/* Range Mode Toggle */}
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-300">Timeline Range</label>
                <div className="flex bg-gray-800/60 rounded-lg p-1">
                  <button
                    onClick={() => handleRangeModeChange('days')}
                    className={`px-3 py-1 text-xs rounded-md transition-all duration-200 ${
                      rangeMode === 'days'
                        ? 'bg-indigo-600 text-white shadow-md'
                        : 'text-gray-300 hover:text-white'
                    }`}
                  >
                    Days
                  </button>
                  <button
                    onClick={() => handleRangeModeChange('dates')}
                    className={`px-3 py-1 text-xs rounded-md transition-all duration-200 ${
                      rangeMode === 'dates'
                        ? 'bg-indigo-600 text-white shadow-md'
                        : 'text-gray-300 hover:text-white'
                    }`}
                  >
                    Dates
                  </button>
                </div>
              </div>

              {/* Days Range Controls */}
              {rangeMode === 'days' && (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-lg font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
                      {daysRange} days
                    </span>
                    <span className="text-sm text-gray-400">
                      {Math.round(daysRange / 30)} months
                    </span>
                  </div>
                  <div className="space-y-2">
                    <input
                      type="range"
                      min="7"
                      max={maxHistoricalDays}
                      step="1"
                      value={daysRange}
                      onChange={(e) => setDaysRange(parseInt(e.target.value))}
                      className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer slider-thumb"
                    />
                    <div className="flex justify-between text-xs text-gray-400">
                      <span>1 week</span>
                      <span>10 years</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 pt-2">
                    {rangePresets.map((preset) => (
                      <button
                        key={preset.days}
                        onClick={() => setDaysRange(preset.days)}
                        className={`px-3 py-1.5 text-xs rounded-lg transition-all duration-200 ${
                          daysRange === preset.days
                            ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/25'
                            : 'bg-gray-800/60 text-gray-300 hover:bg-gray-700/60 hover:text-white'
                        }`}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </>
              )}

              {/* Date Range Controls */}
              {rangeMode === 'dates' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">Start Date</label>
                      <input
                        type="date"
                        value={dateRange.startDate}
                        onChange={(e) => handleDateRangeChange('startDate', e.target.value)}
                        className="w-full px-3 py-2 bg-gray-800/60 border border-gray-700/50 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                        max={dateRange.endDate || new Date().toISOString().split('T')[0]}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-400 mb-1">End Date</label>
                      <input
                        type="date"
                        value={dateRange.endDate}
                        onChange={(e) => handleDateRangeChange('endDate', e.target.value)}
                        className="w-full px-3 py-2 bg-gray-800/60 border border-gray-700/50 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                        min={dateRange.startDate}
                        max={new Date().toISOString().split('T')[0]}
                      />
                    </div>
                  </div>

                  {/* Apply button */}
                  <button
                    onClick={handleApplyDateRange}
                    disabled={!dateRange.startDate || !dateRange.endDate}
                    className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-all duration-200 font-medium"
                  >
                    Apply Date Range
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Risk Light */}
          <div className="lg:col-span-1">
            <div className="bg-gradient-to-br from-gray-900/70 to-gray-800/50 border border-gray-700/40 rounded-2xl p-6 shadow-lg backdrop-blur-md hover:shadow-[0_0_40px_-10px_rgba(100,100,255,0.25)] transition-all duration-300">
              <TrafficLight
                score={periodMetrics.systemic_risk}
                regime={periodMetrics.risk_level}
                interpretation={`Latest risk in selected ${calendarDays}-day period`}
                isLoading={isLoading && !hasData}
                zScore={periodMetrics.z_score}
                percentile={periodMetrics.percentile}
                additionalMetrics={{
                  dcc: periodMetrics.dcc_correlation,
                  quantile: periodMetrics.quantile_signal,
                  har: periodMetrics.har_excess_vol
                }}
              />
            </div>
          </div>

          {/* Metrics Grid */}
          <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Core Risk Metrics */}
            <MetricCard
              title="Systemic Risk"
              value={periodMetrics.avg_systemic_risk}
              unit="Z-Score"
              description="Average systemic risk in period"
              color={CHART_CONFIG.colors.systemic}
              isLoading={isLoading}
              format={(value) => value?.toFixed(4) || 'N/A'}
            />

            {/* Credit Metrics */}
            <MetricCard
              title="Current Credit Spread"
              value={periodMetrics.credit_spread}
              unit="bps"
              description="Latest daily credit spread change"
              color="#10b981"
              isLoading={isLoading}
              format={(value) => value?.toFixed(1) || 'N/A'}
            />

            {/* Volatility Metrics */}
            <MetricCard
              title="Current Market Volatility"
              value={periodMetrics.market_volatility}
              unit="%"
              description="Latest 30-day rolling volatility"
              color="#f59e0b"
              isLoading={isLoading}
              format={(value) => value?.toFixed(1) || 'N/A'}
            />

            {/* DCC Correlation */}
            {/* <MetricCard
              title="DCC Correlation"
              value={periodMetrics.dcc_correlation}
              unit="ρ"
              description="Dynamic conditional correlation"
              color="#3b82f6"
              isLoading={isLoading}
              format={(value) => value?.toFixed(3) || 'N/A'}
            /> */}

            <MetricCard
              title="Quantile Signal"
              value={periodMetrics.quantile_signal}
              unit=""
              description="5th percentile risk signal"
              color="#8b5cf6"
              isLoading={isLoading}
              format={(value) => value?.toFixed(3) || 'N/A'}
            />

            {/* <MetricCard
              title="HAR Excess Vol"
              value={periodMetrics.har_excess_vol}
              unit="Z-Score"
              description="HAR model excess volatility"
              color="#f97316"
              isLoading={isLoading}
              format={(value) => value?.toFixed(2) || 'N/A'}
            /> */}

            <MetricCard
              title="Composite Risk Score"
              value={periodMetrics.composite_risk_score}
              unit=""
              description="Weighted composite score"
              color="#ec4899"
              isLoading={isLoading}
              format={(value) => value?.toFixed(3) || 'N/A'}
            />

            {/* Macro Metrics */}
            {currentRisk.macro_oil !== null && (
              <MetricCard
                title="Oil Return"
                value={periodMetrics.macro_oil}
                unit="%"
                description="Daily commodity price return"
                color="#f97316"
                isLoading={isLoading}
                format={(value) => value?.toFixed(2) || 'N/A'}
              />
            )}

            {currentRisk.macro_fx !== null && (
              <MetricCard
                title="FX Change"
                value={periodMetrics.macro_fx}
                unit="%"
                description="Daily currency exchange change"
                color="#ec4899"
                isLoading={isLoading}
                format={(value) => value?.toFixed(2) || 'N/A'}
              />
            )}

            <MetricCard
              title="Forecast Risk"
              value={periodMetrics.forecast_next_risk}
              unit="Z-Score"
              description="Next day risk prediction"
              color="#8b5cf6"
              isLoading={isLoading}
              format={(value) => value?.toFixed(3) || 'N/A'}
            />

            {/* Quantile Risk Metrics */}
            {quantileMetrics && (
              <>
                <MetricCard
                  title="VaR 95%"
                  value={quantileMetrics.var95}
                  unit=""
                  description="1-day 95% Value at Risk"
                  color="#ef4444"
                  isLoading={isLoading}
                  format={(value) => value?.toFixed(4) || 'N/A'}
                />

                <MetricCard
                  title="Normal VaR"
                  value={quantileMetrics.varNormal}
                  unit=""
                  description="Normal distribution VaR"
                  color="#f59e0b"
                  isLoading={isLoading}
                  format={(value) => value?.toFixed(4) || 'N/A'}
                />

                <MetricCard
                  title="Capital Buffer"
                  value={quantileMetrics.capitalBuffer}
                  unit=""
                  description="Required capital cushion"
                  color="#10b981"
                  isLoading={isLoading}
                  format={(value) => value?.toFixed(4) || 'N/A'}
                />
              </>
            )}

            {/* Data Quality Metrics */}
            <MetricCard
              title="Trading Days"
              value={tradingDays}
              unit="days"
              description={`${tradingCoveragePercentage}% of expected`}
              isLoading={isLoading}
              color="#9ca3af"
            />

            <MetricCard
              title="Data Points"
              value={periodMetrics.data_points}
              unit="points"
              description="Observations in selected period"
              isLoading={isLoading}
              color="#6b7280"
            />

            <MetricCard
              title="Computation Time"
              value={periodMetrics.computation_duration}
              unit="s"
              description="Last pipeline execution time"
              isLoading={isLoading}
              color="#8b5cf6"
              format={(value) => value?.toFixed(2) || 'N/A'}
            />

            <MetricCard
              title="Active Signals"
              value={availableSignalsCount}
              unit="signals"
              description="Comprehensive risk indicators"
              isLoading={isLoading}
              color="#06b6d4"
            />
          </div>
        </div>

        {summaryData && (
          <div className="bg-gradient-to-br from-blue-900/20 to-indigo-900/20 border border-blue-700/30 rounded-2xl p-6 backdrop-blur-lg">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-sm">
              <div>
                <div className="text-blue-300/60 text-xs">Period Mean</div>
                <div className="text-white font-semibold">{summaryData.period_mean?.toFixed(3) || 'N/A'}</div>
              </div>
              <div>
                <div className="text-blue-300/60 text-xs">Period Std Dev</div>
                <div className="text-white font-semibold">{summaryData.period_std?.toFixed(3) || 'N/A'}</div>
              </div>
              <div>
                <div className="text-blue-300/60 text-xs">Min/Max Risk</div>
                <div className="text-white font-semibold">
                  {summaryData.period_min?.toFixed(3) || 'N/A'} / {summaryData.period_max?.toFixed(3) || 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-blue-300/60 text-xs">Data Quality</div>
                <div className="text-white font-semibold">
                  {tradingCoveragePercentage >= 90 ? 'Excellent' : 
                   tradingCoveragePercentage >= 70 ? 'Good' : 
                   tradingCoveragePercentage >= 50 ? 'Moderate' : 'Limited'}
                </div>
              </div>
            </div>
            {summaryData.risk_distribution && (
              <div className="mt-4 grid grid-cols-3 gap-4 text-xs">
                <div className="text-center">
                  <div className="text-red-400 font-semibold">High Risk</div>
                  <div className="text-white">{summaryData.risk_distribution.high_threshold?.toFixed(3)}+</div>
                </div>
                <div className="text-center">
                  <div className="text-yellow-400 font-semibold">Medium Risk</div>
                  <div className="text-white">{summaryData.risk_distribution.medium_threshold?.toFixed(3)}+</div>
                </div>
                <div className="text-center">
                  <div className="text-green-400 font-semibold">Current Regime</div>
                  <div className="text-white capitalize">{summaryData.risk_distribution.current_regime || 'Unknown'}</div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Enhanced Chart Section */}
        <div className="relative bg-gradient-to-br from-gray-900/70 to-gray-800/60 rounded-2xl border border-gray-700/50 shadow-2xl p-6 overflow-hidden backdrop-blur-lg transition-all duration-300 hover:shadow-[0_0_50px_-10px_rgba(120,120,255,0.25)]">
          <div className="absolute inset-0 bg-gradient-to-t from-gray-950/60 via-transparent to-transparent pointer-events-none rounded-2xl"></div>
          
          {/* Enhanced Chart Header */}
          <div className="relative z-10 flex items-center justify-between mb-6">
            <div>
              <h2 className="text-2xl font-bold bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
                Systemic Risk Timeline
              </h2>
              <p className="text-gray-400 mt-1">
                {rangeMode === 'days' 
                  ? `${tradingDays} trading days • ${calendarDays} calendar days requested`
                  : `${tradingDays} trading days from ${dateRange.startDate} to ${dateRange.endDate}`
                }
                {summaryData && ` • Mean: ${summaryData.period_mean?.toFixed(3)} • Std: ${summaryData.period_std?.toFixed(3)}`}
                {availableSignalsCount > 0 && ` • ${availableSignalsCount} comprehensive signals`}
              </p>
            </div>
            <div className="text-sm text-gray-400 bg-gray-800/40 px-3 py-1.5 rounded-lg border border-gray-700/50">
              {rangeMode === 'days' ? `${calendarDays}d` : 'Custom Range'}
            </div>
          </div>
          
          {hasData ? (
            <RiskTimelineChart 
              data={displayData} 
              onDataPointClick={handleDataPointClick}
              summaryData={summaryData}
              currentMetrics={periodMetrics}
              showAllSignals={showAllSignals}
            />
          ) : (
            <div className="h-96 flex items-center justify-center text-gray-500">
              {isLoading ? 'Loading comprehensive risk data...' : 'No data available'}
            </div>
          )}
        </div>

        {/* Footer */}
        <Footer />
      </div>

      <style jsx>{`
        .slider-thumb::-webkit-slider-thumb {
          appearance: none;
          height: 20px;
          width: 20px;
          border-radius: 50%;
          background: linear-gradient(135deg, #6366f1, #8b5cf6);
          cursor: pointer;
          border: 2px solid #1f2937;
          box-shadow: 0 0 10px rgba(99, 102, 241, 0.5);
          transition: all 0.2s ease;
        }
        
        .slider-thumb::-webkit-slider-thumb:hover {
          transform: scale(1.1);
          box-shadow: 0 0 15px rgba(99, 102, 241, 0.7);
        }
        
        .slider-thumb::-moz-range-thumb {
          height: 20px;
          width: 20px;
          border-radius: 50%;
          background: linear-gradient(135deg, #6366f1, #8b5cf6);
          cursor: pointer;
          border: 2px solid #1f2937;
          box-shadow: 0 0 10px rgba(99, 102, 241, 0.5);
        }
      `}</style>
    </div>
  );
};

export default App;