import React from 'react';
import { RISK_REGIMES } from '../../services/constants';

export const TrafficLight = ({ 
  score, 
  regime, 
  interpretation, 
  isLoading,
  zScore,
  percentile,
}) => {
  const style = RISK_REGIMES[regime] || RISK_REGIMES.GREEN;

  if (isLoading) {
    return (
      <div className="p-6 h-full min-h-[280px] flex flex-col items-center justify-center bg-gray-900 rounded-xl shadow-xl border border-gray-800 animate-pulse">
        <div className="text-gray-500 font-semibold text-lg">Loading Risk Signals...</div>
        <div className="w-8 h-8 mt-4 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const regimeBorder = style.border.replace('border-', 'border-');

  return (
    <div className={`p-6 h-full min-h-[280px] rounded-xl bg-gray-900 border-2 ${regimeBorder} transition-all duration-500 shadow-2xl shadow-gray-900 hover:shadow-lg hover:shadow-gray-900`}>
      <div className="flex flex-col items-start">
        <p className="text-base font-semibold text-gray-400">Current Risk Regime</p>
        <div className="flex items-center space-x-3 mt-1">
            <div 
                className={`w-4 h-4 rounded-full transition-all duration-500 flex-shrink-0 ${
                    regime === 'RED' ? 'bg-red-500 shadow-xl shadow-red-500/50' : 
                    regime === 'YELLOW' ? 'bg-yellow-500 shadow-xl shadow-yellow-500/50' : 
                    'bg-green-500 shadow-xl shadow-green-500/50'
                }`}
            />
            <h2 className={`text-5xl font-extrabold ${style.color.replace('text-', 'text-')}`}>
                {style.label}
            </h2>
        </div>
      </div>
      
      <div className="mt-6 space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-400">SRS Score:</span>
          <span className={`font-mono font-bold ${style.color.replace('text-', 'text-')}`}>
            {typeof score === 'number' ? score.toFixed(4) : 'N/A'}
          </span>
        </div>
        
        {typeof zScore === 'number' && (
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-400">Z-Score:</span>
            <span className="font-mono text-gray-300">
              {zScore.toFixed(2)}σ
            </span>
          </div>
        )}
        
        {typeof percentile === 'number' && (
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-400">Percentile:</span>
            <span className="font-mono text-gray-300">
              {Math.round(percentile * 100)}%
            </span>
          </div>
        )}
        
      </div>

      <div className="mt-6 pt-4 border-t border-gray-800">
        <p className="text-sm italic text-gray-500">
          {interpretation || 'No interpretation available'}
        </p>
      </div>
    </div>
  );
};