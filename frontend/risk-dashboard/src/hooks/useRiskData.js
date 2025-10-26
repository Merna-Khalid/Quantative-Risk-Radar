// src/hooks/useRiskData.js
import { useEffect, useCallback, useState, useRef } from 'react';
import { useRiskStore } from '../stores/riskStore';
import { apiService } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';

export const useRiskData = (daysRange = 180, useRealtime = true) => {
  const {
    riskHistory,
    summaryData,
    currentMetrics,
    isLoading,
    error,
    lastUpdated,
    setRiskData,
    setLoading,
    setError,
    getLatestRisk,
    getDisplayData
  } = useRiskStore();

  const previousRangeRef = useRef(null);

  const { isConnected: wsConnected } = useWebSocket(
    useRealtime ? '/ws/risk' : null
  );

  // Helper to normalize input into an object { days, startDate, endDate }
  const normalizeRange = (range) => {
    if (range == null) return { days: undefined, startDate: undefined, endDate: undefined };
    if (typeof range === 'number') return { days: range, startDate: undefined, endDate: undefined };
    const { days, startDate, endDate } = range;
    return { days, startDate, endDate };
  };

  // Fetch function sends proper range object to apiService
  const fetchRiskHistory = useCallback(async (rangeInput) => {
    const range = normalizeRange(rangeInput);
    if (isLoading) return;

    try {
      setLoading(true);
      const response = await apiService.getRiskHistory(range);
      
      // Handle enhanced response format
      if (response && response.data && Array.isArray(response.data)) {
        setRiskData(response); // Pass the full enhanced response
        setError(null);
      } else {
        throw new Error('Invalid response format from API');
      }
    } catch (err) {
      const msg = err?.message || String(err);
      setError(msg);
      console.error('Risk history fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [setLoading, setError, setRiskData, isLoading]);

  // Smart fetching: only when the provided range actually changes
  useEffect(() => {
    const currentRange = normalizeRange(daysRange);
    const prev = previousRangeRef.current;

    const changed = !prev ||
      prev.days !== currentRange.days ||
      prev.startDate !== currentRange.startDate ||
      prev.endDate !== currentRange.endDate;

    if (changed) {
      previousRangeRef.current = currentRange;
      fetchRiskHistory(currentRange);
    }
  }, [daysRange, fetchRiskHistory]);

  // Initial fetch on mount if store is empty
  useEffect(() => {
    if (!riskHistory || riskHistory.length === 0) {
      fetchRiskHistory(daysRange);
    }
  }, []);

  // Refresh wrapper
  const refreshData = useCallback(async (forceRefresh = false) => {
    try {
      setLoading(true);
      await fetchRiskHistory(daysRange);
    } catch (err) {
      setError(`Refresh failed: ${err?.message || String(err)}`);
    } finally {
      setLoading(false);
    }
  }, [fetchRiskHistory, daysRange, setLoading, setError]);

  const latestRisk = getLatestRisk();
  const displayData = getDisplayData();

  return {
    // Data
    riskHistory,
    displayData,
    latestRisk,
    currentMetrics,
    summaryData,
    
    // State
    isLoading,
    error,
    lastUpdated,
    
    // WebSocket state
    wsConnected,
    
    // Actions
    refreshData,
    hasData: Array.isArray(riskHistory) && riskHistory.length > 0,
    
    // Derived state
    hasComprehensiveData: currentMetrics && currentMetrics.systemic_risk !== undefined,
    currentRegime: currentMetrics?.risk_level || 'unknown',
    isWarning: currentMetrics?.composite_warning || false
  };
};