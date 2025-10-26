import React from 'react';

export const RefreshControls = ({ 
  onRefresh, 
  onForceRefresh, 
  isLoading, 
  lastUpdated 
}) => {
  return (
    <div className="flex flex-col sm:flex-row items-center justify-between space-y-3 sm:space-y-0 p-4 bg-gray-800 rounded-xl shadow-inner border border-gray-700">
      <div className="flex flex-col items-center">
        <div className="flex flex-row space-x-3">
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-md text-sm"
          >
            {isLoading ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
            ) : 'Refresh Data'}
          </button>
          
          <button
            onClick={onForceRefresh}
            disabled={isLoading}
            className="px-4 py-2 bg-orange-600 text-white rounded-lg font-semibold hover:bg-orange-700 transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-md text-sm"
          >
            Force Refresh
          </button>
        </div>
      
      <div className="flex items-center space-x-4 py-3">
        {lastUpdated && (
          <div className="text-sm text-gray-400">
            Last updated: <span className="font-mono text-white">{lastUpdated.toLocaleTimeString()}</span>
          </div>
        )}
        
        {isLoading && (
          <span className="text-sm text-blue-400 font-medium hidden sm:inline">Processing...</span>
        )}
      </div>
    </div>
    </div>
  );
};