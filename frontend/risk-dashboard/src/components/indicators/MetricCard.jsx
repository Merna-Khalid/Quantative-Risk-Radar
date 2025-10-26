import React from 'react';

export const MetricCard = ({ 
  title, 
  value, 
  unit, 
  color = '#a3a3a3', 
  isLoading, 
  trend,
  description 
}) => (
  <div className="relative p-5 bg-gray-900 rounded-xl shadow-xl border border-gray-800 hover:border-gray-700 transition-all duration-200 overflow-hidden">
    <div className="absolute top-0 left-0 bottom-0 w-1.5" style={{ backgroundColor: color }} />
    
    <div className="pl-2">
      <p className="text-sm font-medium text-gray-400">{title}</p>
      {isLoading ? (
        <div className="h-8 mt-2 w-3/4 bg-gray-800 rounded-lg animate-pulse" />
      ) : (
        <>
          <p className="text-3xl font-extrabold mt-1 tracking-tight" style={{ color }}>
            {typeof value === 'number' ? value.toFixed(4) : value || 'N/A'}
            {unit && <span className="text-base font-normal ml-1 text-gray-500">{unit}</span>}
          </p>
          {trend && (
            <p className={`text-xs mt-2 font-semibold ${trend > 0 ? 'text-red-400' : 'text-green-400'}`}>
              {trend > 0 ? '↗' : '↘'} {Math.abs(trend).toFixed(2)}
            </p>
          )}
          {description && (
            <p className="text-xs text-gray-600 mt-2">{description}</p>
          )}
        </>
      )}
    </div>
  </div>
);