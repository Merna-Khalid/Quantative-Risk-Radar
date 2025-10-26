import React from 'react';
import { RISK_REGIMES } from '../../services/constants';

export const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;

  const srs = payload.find(p => p.dataKey === 'systemic_risk_score')?.value || 0;
  const regime = srs >= RISK_REGIMES.RED.threshold ? 'RED' : srs > RISK_REGIMES.YELLOW.threshold ? 'YELLOW' : 'GREEN';
  const regimeStyle = RISK_REGIMES[regime];

  return (
    <div className="p-4 bg-gray-700/90 border border-gray-600 rounded-lg shadow-xl text-sm min-w-52 text-gray-100 backdrop-blur-sm">
      <p className="font-bold text-white mb-2 border-b border-gray-600 pb-2">{`Date: ${label}`}</p>
      <p className={`font-semibold ${regimeStyle.color.replace('text-', 'text-')} mb-2`}>
        {`Regime: ${regimeStyle.label}`}
      </p>
      {payload.map((entry, index) => (
        <p key={index} style={{ color: entry.color }} className="flex justify-between items-center text-gray-300">
          <span className="font-medium">{entry.name}:</span>
          <span className="font-mono ml-4 font-bold">{entry.value?.toFixed(4)}</span>
        </p>
      ))}
    </div>
  );
};