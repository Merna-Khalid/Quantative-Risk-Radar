import React from 'react';
import Plot from 'react-plotly.js';
import { CHART_CONFIG, RISK_REGIMES } from '../../services/constants';

export const RiskTimelineChart = ({ 
  data, 
  onDataPointClick,
  summaryData,
  currentMetrics,
  showAllSignals = false
}) => {
  const displayData = data;

  if (!displayData.length) {
    return (
      <div className="h-96 flex items-center justify-center text-gray-500 bg-gray-900 rounded-xl">
        No chart data available
      </div>
    );
  }

  const dates = displayData.map(d => d.date);
  const systemicScores = displayData.map(d => d.systemic_risk_score);
  const pcaScores = displayData.map(d => d.pca_signal_score);
  const creditScores = displayData.map(d => d.credit_signal_score);
  
  const quantileSignals = displayData.map(d => d.quantile_signal);
  const dccCorrelations = displayData.map(d => d.dcc_correlation);
  const harExcessVols = displayData.map(d => d.har_excess_vol);
  const compositeScores = displayData.map(d => d.composite_risk_score);
  const warningFlags = displayData.map(d => d.is_warning);
  const creditSpreadChanges = displayData.map(d => d.credit_spread_change);
  const vixChanges = displayData.map(d => d.vix_change);

  const zScores = displayData.map(d => d.z_score || 0);
  const percentiles = displayData.map(d => d.percentile || 0);
  const regimes = displayData.map(d => d.market_regime);
  const components = displayData.map(d => d.components || {});

  // Base plotly data with core signals
  const plotlyData = [
    // Systemic Risk Score (main line)
    {
      type: 'scatter',
      mode: 'lines',
      name: 'Systemic Risk',
      x: dates,
      y: systemicScores,
      line: {
        color: CHART_CONFIG.colors.systemic,
        width: 3.5
      },
      hovertemplate: 
        '<b>Systemic Risk Score</b><br>' +
        'Date: %{x}<br>' +
        'Score: %{y:.4f}<br>' +
        'Z-Score: %{customdata[0]:.2f}σ<br>' +
        'Percentile: %{customdata[1]:.0f}%<br>' +
        'Regime: %{customdata[2]}<br>' +
        'PCA: %{customdata[3]:.3f}<br>' +
        'Credit: %{customdata[4]:.3f}<extra></extra>',
      customdata: displayData.map((d, i) => [
        zScores[i],
        (percentiles[i] * 100),
        regimes[i],
        components[i].pca_contribution || 0,
        components[i].credit_contribution || 0
      ])
    },
    // PCA Co-Movement
    {
      type: 'scatter',
      mode: 'lines',
      name: 'PCA Signal',
      x: dates,
      y: pcaScores,
      line: {
        color: CHART_CONFIG.colors.pca,
        width: 2,
        dash: 'dot'
      },
      opacity: 0.7,
      hovertemplate: '<b>PCA Co-Movement</b><br>%{x}<br>Score: %{y:.4f}<extra></extra>'
    },
    // Credit Stress Signal
    {
      type: 'scatter',
      mode: 'lines',
      name: 'Credit Signal',
      x: dates,
      y: creditScores,
      line: {
        color: CHART_CONFIG.colors.credit,
        width: 2,
        dash: 'dash'
      },
      opacity: 0.7,
      hovertemplate: '<b>Credit Stress Signal</b><br>%{x}<br>Score: %{y:.4f}<extra></extra>'
    }
  ];

  // ... (Additional signals remain the same)
  // ADDITIONAL RISK SIGNALS - Show when enabled
  if (showAllSignals) {
    // Quantile Signal (5th percentile of HYG returns)
    if (quantileSignals.some(val => val !== undefined && val !== null)) {
      plotlyData.push({
        type: 'scatter',
        mode: 'lines',
        name: 'Quantile Signal',
        x: dates,
        y: quantileSignals,
        yaxis: 'y2',
        line: {
          color: '#8b5cf6', // Purple
          width: 1.5
        },
        opacity: 0.7,
        hovertemplate: '<b>Quantile Signal (5th %ile)</b><br>%{x}<br>Value: %{y:.4f}<extra></extra>'
      });
    }

    // DCC Correlation (XLK vs XLF)
    if (dccCorrelations.some(val => val !== undefined && val !== null)) {
      plotlyData.push({
        type: 'scatter',
        mode: 'lines',
        name: 'DCC Correlation',
        x: dates,
        y: dccCorrelations,
        yaxis: 'y3',
        line: {
          color: '#06b6d4', // Cyan
          width: 1.5
        },
        opacity: 0.7,
        hovertemplate: '<b>DCC Correlation</b><br>%{x}<br>Correlation: %{y:.3f}<extra></extra>'
      });
    }

    // HAR Excess Volatility Z-Score
    if (harExcessVols.some(val => val !== undefined && val !== null)) {
      plotlyData.push({
        type: 'scatter',
        mode: 'lines',
        name: 'HAR Excess Vol',
        x: dates,
        y: harExcessVols,
        yaxis: 'y4',
        line: {
          color: '#f97316', // Orange
          width: 1.5
        },
        opacity: 0.7,
        hovertemplate: '<b>HAR Excess Volatility</b><br>%{x}<br>Z-Score: %{y:.2f}<extra></extra>'
      });
    }

    // Composite Risk Score
    if (compositeScores.some(val => val !== undefined && val !== null)) {
      plotlyData.push({
        type: 'scatter',
        mode: 'lines',
        name: 'Composite Score',
        x: dates,
        y: compositeScores,
        line: {
          color: '#ec4899', // Pink
          width: 2,
          dash: 'solid'
        },
        opacity: 0.8,
        hovertemplate: '<b>Composite Risk Score</b><br>%{x}<br>Score: %{y:.4f}<extra></extra>'
      });
    }

    // Credit Spread Changes
    if (creditSpreadChanges.some(val => val !== undefined && val !== null)) {
      plotlyData.push({
        type: 'scatter',
        mode: 'lines',
        name: 'Credit Spread Δ',
        x: dates,
        y: creditSpreadChanges,
        yaxis: 'y5',
        line: {
          color: '#84cc16', // Lime
          width: 1.5
        },
        opacity: 0.6,
        hovertemplate: '<b>Credit Spread Change</b><br>%{x}<br>Change: %{y:.3f}%<extra></extra>'
      });
    }

    // VIX Changes
    if (vixChanges.some(val => val !== undefined && val !== null)) {
      plotlyData.push({
        type: 'scatter',
        mode: 'lines',
        name: 'VIX Change',
        x: dates,
        y: vixChanges,
        yaxis: 'y6',
        line: {
          color: '#f43f5e', // Rose
          width: 1.5
        },
        opacity: 0.6,
        hovertemplate: '<b>VIX Change</b><br>%{x}<br>Change: %{y:.3f}%<extra></extra>'
      });
    }

    // Warning flags as markers
    if (warningFlags.some(val => val !== undefined && val !== null)) {
      const warningDates = dates.filter((_, i) => warningFlags[i]);
      const warningScores = systemicScores.filter((_, i) => warningFlags[i]);
      
      if (warningDates.length > 0) {
        plotlyData.push({
          type: 'scatter',
          mode: 'markers',
          name: 'Risk Warning',
          x: warningDates,
          y: warningScores,
          marker: {
            color: '#ef4444',
            size: 8,
            symbol: 'triangle-up',
            line: {
              color: 'white',
              width: 1
            }
          },
          hovertemplate: '<b>⚠️ Risk Warning</b><br>%{x}<br>Systemic Score: %{y:.4f}<extra></extra>'
        });
      }
    }
  }

  // Current risk level marker (from comprehensive currentMetrics)
  if (currentMetrics && typeof currentMetrics.systemic_risk === 'number') {
    plotlyData.push({
      type: 'scatter',
      mode: 'markers',
      name: 'Current Risk',
      x: [dates[dates.length - 1]],
      y: [currentMetrics.systemic_risk],
      marker: {
        color: '#60a5fa',
        size: 12,
        symbol: 'star',
        line: {
          color: 'white',
          width: 2
        }
      },
      hovertemplate: 
        '<b>Current Risk Level</b><br>' +
        'Date: %{x}<br>' +
        'Score: %{y:.4f}<br>' +
        'Regime: ' + (currentMetrics.risk_level || 'Unknown') + '<br>' +
        'DCC: ' + (currentMetrics.dcc_correlation?.toFixed(3) || 'N/A') + '<br>' +
        'Quantile: ' + (currentMetrics.quantile_signal?.toFixed(3) || 'N/A') + '<extra></extra>'
    });
  }

  // Enhanced risk threshold lines using comprehensive data
  const riskLines = [];

  if (summaryData && summaryData.risk_distribution) {
    riskLines.push(
      {
        type: 'line',
        x0: dates[0],
        x1: dates[dates.length - 1],
        y0: summaryData.risk_distribution.high_threshold,
        y1: summaryData.risk_distribution.high_threshold,
        line: {
          color: '#ef4444',
          dash: 'dash',
          width: 2
        },
        opacity: 0.8
      },
      {
        type: 'line',
        x0: dates[0],
        x1: dates[dates.length - 1],
        y0: summaryData.risk_distribution.medium_threshold,
        y1: summaryData.risk_distribution.medium_threshold,
        line: {
          color: '#f59e0b',
          dash: 'dash',
          width: 2
        },
        opacity: 0.8
      }
    );
  } else {
    // Fallback to static thresholds
    riskLines.push(
      {
        type: 'line',
        x0: dates[0],
        x1: dates[dates.length - 1],
        y0: RISK_REGIMES.RED.threshold,
        y1: RISK_REGIMES.RED.threshold,
        line: {
          color: '#ef4444',
          dash: 'dash',
          width: 2
        }
      },
      {
        type: 'line',
        x0: dates[0],
        x1: dates[dates.length - 1],
        y0: RISK_REGIMES.YELLOW.threshold,
        y1: RISK_REGIMES.YELLOW.threshold,
        line: {
          color: '#f59e0b',
          dash: 'dash',
          width: 2
        }
      }
    );
  }

  // Add zero line
  riskLines.push({
    type: 'line',
    x0: dates[0],
    x1: dates[dates.length - 1],
    y0: 0,
    y1: 0,
    line: {
      color: '#4b5563',
      dash: 'dot',
      width: 1
    }
  });

  if (summaryData && summaryData.period_mean) {
    riskLines.push({
      type: 'line',
      x0: dates[0],
      x1: dates[dates.length - 1],
      y0: summaryData.period_mean,
      y1: summaryData.period_mean,
      line: {
        color: '#6b7280',
        dash: 'solid',
        width: 1
      },
      opacity: 0.6
    });
  }

  const baseLayout = {
    title: {
      text: `Systemic Risk Timeline - ${showAllSignals ? 'All Signals' : 'Core Metrics'} (${displayData.length} Trading Days)`,
      font: { 
        size: 18, 
        family: 'Inter, sans-serif',
        color: '#e5e7eb'
      },
      x: 0.05,
      y: 0.95
    },
    xaxis: {
      title: 'Date',
      type: 'date',
      rangeslider: {
        visible: true,
        thickness: 0.05,
        bgcolor: '#1f2937',
        bordercolor: '#374151'
      },
      gridcolor: '#1f2937',
      linecolor: '#4b5563',
      tickfont: { color: '#9ca3af', size: 10 },
      tickformat: '%Y-%m-%d',
      tickangle: -25,
      ticklen: 8,
      tickwidth: 1,
      tickcolor: '#4b5563'
    },
    yaxis: {
      title: 'Risk Score (Z-Score)',
      range: summaryData ? [
        Math.min(-2.5, summaryData.period_min - 0.5),
        Math.max(2.5, summaryData.period_max + 0.5)
      ] : [-2.5, 2.5],
      gridcolor: '#1f2937', 
      linecolor: '#4b5563', 
      tickfont: { color: '#9ca3af', size: 10 },
      zeroline: false,
      ticklen: 5,
      tickwidth: 1
    },
    shapes: riskLines,
    hovermode: 'x unified',
    hoverdistance: 50,
    plot_bgcolor: '#111827',
    paper_bgcolor: '#111827',
    font: {
      family: 'Inter, sans-serif',
      color: '#e5e7eb' 
    },
    margin: {
      l: 80,
      r: 80,
      b: 60,
      t: 60,
      pad: 8
    },
    showlegend: true
  };

  if (showAllSignals) {
    baseLayout.yaxis2 = {
      title: 'Quantile',
      overlaying: 'y',
      side: 'right',
      position: 0.80,
      gridcolor: 'rgba(139, 92, 246, 0.1)',
      tickfont: { color: '#8b5cf6', size: 8 }
    };

    baseLayout.yaxis3 = {
      title: 'Correlation',
      overlaying: 'y',
      side: 'right',
      position: 0.85,
      range: [-1, 1],
      gridcolor: 'rgba(6, 182, 212, 0.1)',
      tickfont: { color: '#06b6d4', size: 8 }
    };

    baseLayout.yaxis4 = {
      title: 'HAR Z-Score',
      overlaying: 'y',
      side: 'right',
      position: 0.90,
      gridcolor: 'rgba(249, 115, 22, 0.1)',
      tickfont: { color: '#f97316', size: 8 }
    };

    baseLayout.yaxis5 = {
      title: 'Spread Δ%',
      overlaying: 'y',
      side: 'right',
      position: 0.70,
      gridcolor: 'rgba(132, 204, 22, 0.1)',
      tickfont: { color: '#84cc16', size: 8 }
    };

    baseLayout.yaxis6 = {
      title: 'VIX Δ%',
      overlaying: 'y',
      side: 'right',
      position: 0.75,
      gridcolor: 'rgba(244, 63, 94, 0.1)',
      tickfont: { color: '#f43f5e', size: 8 }
    };
  }

  const annotations = [
    ...(summaryData ? [{
      x: 0.02,
      y: 0.98,
      xref: 'paper',
      yref: 'paper',
      text: `Mean: ${summaryData.period_mean?.toFixed(3)} | Std: ${summaryData.period_std?.toFixed(3)}`,
      showarrow: false,
      font: {
        size: 11,
        color: '#9ca3af'
      },
      bgcolor: 'rgba(17, 24, 39, 0.8)',
      bordercolor: '#374151',
      borderwidth: 1,
      borderpad: 4,
      align: 'left'
    }] : []),
    ...(currentMetrics && currentMetrics.risk_level ? [{
      x: 0.98,
      y: 0.98,
      xref: 'paper',
      yref: 'paper',
      text: `Current: ${currentMetrics.risk_level.toUpperCase()}`,
      showarrow: false,
      font: {
        size: 11,
        color: currentMetrics.risk_level === 'high' ? '#ef4444' : 
               currentMetrics.risk_level === 'medium' ? '#f59e0b' : '#10b981'
      },
      bgcolor: 'rgba(17, 24, 39, 0.8)',
      bordercolor: '#374151',
      borderwidth: 1,
      borderpad: 4,
      align: 'right'
    }] : [])
  ];

  if (showAllSignals && currentMetrics) {
    annotations.push({
      x: 0.02,
      y: 0.02,
      xref: 'paper',
      yref: 'paper',
      text: `Signals: ${plotlyData.length} | DCC: ${currentMetrics.dcc_correlation?.toFixed(3) || 'N/A'} | Quantile: ${currentMetrics.quantile_signal?.toFixed(3) || 'N/A'}`,
      showarrow: false,
      font: {
        size: 9,
        color: '#6b7280'
      },
      bgcolor: 'rgba(17, 24, 39, 0.6)',
      borderpad: 2,
      align: 'left'
    });
  }

  const layout = {
    ...baseLayout,
    annotations
  };

  const config = {
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToAdd: [
      'drawline',
      'drawopenpath',
      'eraseshape'
    ],
    modeBarButtonsToRemove: [
      'pan2d',
      'select2d',
      'lasso2d',
      'autoScale2d'
    ],
    scrollZoom: true,
    responsive: true,
    doubleClick: 'reset',
    showTips: true
  };

  const handleClick = (event) => {
    if (event.points && event.points[0]) {
      const point = event.points[0];
      const clickedData = displayData[point.pointIndex];
      onDataPointClick?.(clickedData);
    }
  };

  const availableSignals = [
    'systemic', 'pca', 'credit', 
    ...(quantileSignals.some(v => v != null) ? ['quantile'] : []),
    ...(dccCorrelations.some(v => v != null) ? ['dcc'] : []),
    ...(harExcessVols.some(v => v != null) ? ['har'] : []),
    ...(compositeScores.some(v => v != null) ? ['composite'] : []),
    ...(creditSpreadChanges.some(v => v != null) ? ['credit_spread'] : []),
    ...(vixChanges.some(v => v != null) ? ['vix'] : []),
    ...(warningFlags.some(v => v != null) ? ['warning'] : [])
  ];

  return (
    <div className="w-full bg-gray-900 rounded-xl p-0">
      <div className="flex justify-between items-center p-4 pb-2">
        <div className="text-sm text-gray-400">
          {availableSignals.length} signals available
          {currentMetrics && ` • Last: ${new Date(currentMetrics.timestamp).toLocaleTimeString()}`}
        </div>
        <button
          onClick={() => window.dispatchEvent(new CustomEvent('toggleSignals', { detail: !showAllSignals }))}
          className={`px-3 py-1 text-xs rounded border transition-colors ${
            showAllSignals 
              ? 'bg-purple-600 border-purple-500 text-white hover:bg-purple-700' 
              : 'bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700'
          }`}
        >
          {showAllSignals ? 'Show Core Only' : 'Show All Signals'}
        </button>
      </div>
      
      <div className="h-[700px]"> 
        <Plot
          data={plotlyData}
          layout={layout}
          config={config}
          onClick={handleClick}
          style={{ width: '100%', height: '100%' }}
          useResizeHandler={true}
        />
      </div>
      
      {/* <RiskSignalLegend 
        signals={availableSignals} 
        currentMetrics={currentMetrics}
      /> */}

      <p className="text-xs text-gray-500 mt-4 text-center px-4 pb-4">
        Comprehensive risk visualization with {showAllSignals ? 'all' : 'core'} components. 
        {summaryData && ` Data range: ${summaryData.date_range?.start} to ${summaryData.date_range?.end}`}
        {currentMetrics && ` • Computation: ${currentMetrics.computation_duration?.toFixed(2)}s`}
        {showAllSignals && ' • Multiple y-axes for different signal scales'}
      </p>
    </div>
  );
};

export const RiskSignalLegend = ({ signals, onSignalToggle, currentMetrics }) => {
  const signalColors = {
    systemic: '#ef4444',
    pca: '#3b82f6',
    credit: '#10b981',
    quantile: '#8b5cf6',
    dcc: '#06b6d4',
    har: '#f97316',
    composite: '#ec4899',
    credit_spread: '#84cc16',
    vix: '#f43f5e',
    warning: '#ef4444',
    'current risk': '#60a5fa'
  };

  const signalNames = {
    systemic: 'Systemic Risk',
    pca: 'PCA Signal', 
    credit: 'Credit Signal',
    quantile: 'Quantile Signal',
    dcc: 'DCC Correlation',
    har: 'HAR Excess Vol',
    composite: 'Composite Score',
    credit_spread: 'Credit Spread Δ',
    vix: 'VIX Change',
    warning: 'Risk Warning',
    'current risk': 'Current Risk'
  };
  
  const legendSignals = [...new Set([...signals, 'current risk'])];

  return (
    <div className="flex flex-wrap gap-2 p-3 bg-gray-900 rounded-lg">
      {legendSignals.map(signal => {
        const currentValue = currentMetrics?.[
          signal === 'quantile' ? 'quantile_signal' :
          signal === 'pca' ? 'pca_signal_score' :
          signal === 'credit' ? 'credit_signal_score' :
          signal === 'dcc' ? 'dcc_correlation' :
          signal === 'har' ? 'har_excess_vol' :
          signal === 'composite' ? 'composite_risk_score' :
          signal === 'credit_spread' ? 'credit_spread_change' :
          signal === 'vix' ? 'vix_change' :
          signal === 'systemic' ? 'systemic_risk' : 
          signal === 'current risk' ? 'systemic_risk' : signal
        ];
        
        const isCurrentRisk = signal === 'current risk';
        const displayValue = isCurrentRisk && currentMetrics?.risk_level 
            ? currentMetrics.risk_level.toUpperCase() 
            : (currentValue !== undefined && typeof currentValue === 'number' 
                ? currentValue.toFixed(3) : 'N/A');
        
        return (
          <button
            key={signal}
            onClick={() => onSignalToggle?.(signal)}
            className="flex items-center gap-2 px-3 py-1 text-xs rounded border border-gray-700 bg-gray-800 text-gray-300 hover:bg-gray-700 transition-colors"
          >
            <div 
              className={`w-3 h-3 rounded ${isCurrentRisk ? 'border-2 border-white' : ''}`}
              style={{ backgroundColor: signalColors[signal] || '#6b7280', 
                       borderRadius: isCurrentRisk ? '50%' : '0.25rem' }}
            />
            <span>{signalNames[signal] || signal}</span>
            {displayValue && (
              <span className="text-gray-400 ml-1">
                ({displayValue})
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};