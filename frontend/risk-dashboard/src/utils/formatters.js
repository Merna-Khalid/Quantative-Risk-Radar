import { format, parseISO } from 'date-fns';

// Date formatting
export const formatDate = (dateString, formatStr = 'yyyy-MM-dd') => {
  try {
    return format(parseISO(dateString), formatStr);
  } catch (error) {
    console.error('Date formatting error:', error);
    return dateString;
  }
};

export const formatDateTime = (dateString) => {
  return formatDate(dateString, 'MMM dd, yyyy HH:mm');
};

// Number formatting for financial data
export const formatRiskScore = (score) => {
  if (typeof score !== 'number') return 'N/A';
  return score.toFixed(4);
};

export const formatPercentage = (value) => {
  if (typeof value !== 'number') return 'N/A';
  return `${(value * 100).toFixed(2)}%`;
};

export const formatLargeNumber = (num) => {
  if (typeof num !== 'number') return 'N/A';
  
  if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
  if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
  if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
  
  return num.toFixed(2);
};

// Risk regime formatting
export const getRiskInterpretation = (score, regime) => {
  const interpretations = {
    RED: 'High systemic risk detected. Monitor markets closely.',
    YELLOW: 'Elevated risk levels. Increased vigilance recommended.',
    GREEN: 'Normal market conditions. Standard monitoring procedures.'
  };
  
  return interpretations[regime] || 'Risk assessment unavailable.';
};