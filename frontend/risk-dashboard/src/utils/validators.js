export const isValidRiskData = (data) => {
  // Handle multiple data formats
  if (!data) return false;
  
  // Format 1: Enhanced response with data array and summary
  if (data.data && Array.isArray(data.data)) {
    return data.data.every(item => 
      item &&
      (typeof item.systemic_risk === 'number' || typeof item.systemic_risk_score === 'number') &&
      ['high', 'medium', 'low', 'RED', 'YELLOW', 'GREEN'].includes(item.risk_level || item.market_regime) &&
      typeof item.timestamp === 'string'
    );
  }
  
  // Format 2: Systemic risk data with all signals
  if (data.success && data.data && typeof data.data === 'object') {
    return isValidSystemicRiskData(data);
  }
  
  // Format 3: Legacy array format
  if (Array.isArray(data)) {
    return data.every(item => 
      item &&
      (typeof item.systemic_risk === 'number' || typeof item.systemic_risk_score === 'number') &&
      ['high', 'medium', 'low', 'RED', 'YELLOW', 'GREEN'].includes(item.risk_level || item.market_regime) &&
      typeof item.timestamp === 'string'
    );
  }
  
  return false;
};

export const isValidNumber = (value) => {
  return typeof value === 'number' && !isNaN(value) && isFinite(value);
};

export const validateApiResponse = (response) => {
  if (!response || typeof response !== 'object') {
    throw new Error('Invalid API response format');
  }
  
  if (response.error) {
    throw new Error(response.error);
  }
  
  return true;
};

export const isValidSystemicRiskData = (data) => {
  if (!data || !data.success || !data.data) return false;
  
  const systemicData = data.data;
  
  // Check for core components
  const coreComponents = ['Systemic', 'PCA', 'Credit'];
  const hasCoreComponents = coreComponents.every(component => 
    systemicData[component] !== undefined && isValidNumber(systemicData[component])
  );
  
  if (!hasCoreComponents) return false;
  
  // Check for at least some additional signals
  const additionalSignals = [
    'Quantile_Signal', 'DCC_Corr', 'HAR_ExcessVol_Z', 
    'Credit_Spread_Change', 'VIX_Change', 'is_warning', 'Composite_Risk_Score'
  ];
  
  const hasSomeAdditionalSignals = additionalSignals.some(signal => 
    systemicData[signal] !== undefined
  );
  
  return hasSomeAdditionalSignals;
};

// Validate risk cascade visualization data
export const isValidRiskCascadeData = (data) => {
  if (!data || !data.success || !data.data) return false;
  
  const cascadeData = data.data;
  
  // Should have visualization structure with risk signals
  const hasVisualizationStructure = 
    typeof cascadeData === 'object' && 
    Object.keys(cascadeData).length > 0;
  
  return hasVisualizationStructure;
};

// Validate market overview data
export const isValidMarketOverviewData = (data) => {
  if (!data || !data.success || !data.data) return false;
  
  const overviewData = data.data;
  
  const hasRequiredSections = 
    overviewData.correlation_matrix !== undefined &&
    overviewData.volatilities !== undefined &&
    overviewData.available_assets !== undefined;
  
  return hasRequiredSections;
};

// Validate enhanced risk snapshot
export const isValidEnhancedSnapshot = (snapshot) => {
  if (!snapshot || typeof snapshot !== 'object') return false;
  
  const requiredCoreFields = [
    'systemic_risk',
    'risk_level', 
    'timestamp',
    'start_date',
    'end_date'
  ];
  
  const hasRequiredCore = requiredCoreFields.every(field => 
    snapshot[field] !== undefined && snapshot[field] !== null
  );
  
  if (!hasRequiredCore) return false;
  
  // Validate risk level
  const validRiskLevels = ['high', 'medium', 'low'];
  if (!validRiskLevels.includes(snapshot.risk_level)) return false;
  
  // Validate numeric fields
  const numericFields = ['systemic_risk', 'systemic_mean', 'systemic_std'];
  const validNumerics = numericFields.every(field => 
    snapshot[field] === undefined || isValidNumber(snapshot[field])
  );
  
  return validNumerics;
};

// Validate real-time risk signals
export const isValidRealtimeSignals = (data) => {
  if (!data || !data.signals || typeof data.signals !== 'object') return false;
  
  const signals = data.signals;
  
  // Should have timestamp and at least some signals
  return (
    data.timestamp &&
    typeof data.timestamp === 'string' &&
    Object.keys(signals).length > 0
  );
};

// Comprehensive schema validation for all risk data types
export const validateRiskSchema = (data, schemaType = 'default') => {
  const schemas = {
    // Legacy schema
    default: (item) => {
      const requiredFields = ['systemic_risk_score', 'market_regime', 'timestamp'];
      const missingFields = requiredFields.filter(field => !(field in item));
      
      if (missingFields.length > 0) {
        throw new Error(`Missing required fields: ${missingFields.join(', ')}`);
      }
      
      return true;
    },
    
    // Enhanced risk snapshot schema
    enhanced_snapshot: (item) => {
      const requiredFields = ['systemic_risk', 'risk_level', 'timestamp'];
      const missingFields = requiredFields.filter(field => !(field in item));
      
      if (missingFields.length > 0) {
        throw new Error(`Missing required snapshot fields: ${missingFields.join(', ')}`);
      }
      
      // Validate risk level
      const validRiskLevels = ['high', 'medium', 'low'];
      if (!validRiskLevels.includes(item.risk_level)) {
        throw new Error(`Invalid risk level: ${item.risk_level}`);
      }
      
      // Validate numeric fields
      const numericFields = ['systemic_risk', 'pca_component', 'credit_component'];
      numericFields.forEach(field => {
        if (item[field] !== undefined && !isValidNumber(item[field])) {
          throw new Error(`Invalid numeric value for ${field}: ${item[field]}`);
        }
      });
      
      return true;
    },
    
    // Systemic risk data schema
    systemic_data: (item) => {
      const coreComponents = ['Systemic', 'PCA', 'Credit'];
      const missingComponents = coreComponents.filter(component => !(component in item));
      
      if (missingComponents.length > 0) {
        throw new Error(`Missing core components: ${missingComponents.join(', ')}`);
      }
      
      // Validate all numeric signals
      Object.keys(item).forEach(key => {
        if (typeof item[key] === 'number' && !isValidNumber(item[key])) {
          throw new Error(`Invalid numeric value for ${key}: ${item[key]}`);
        }
      });
      
      return true;
    }
  };

  const validator = schemas[schemaType] || schemas.default;
  
  if (Array.isArray(data)) {
    data.forEach((item, index) => {
      try {
        validator(item);
      } catch (error) {
        throw new Error(`Item ${index}: ${error.message}`);
      }
    });
  } else {
    validator(data);
  }
  
  return true;
};

// Data quality scoring
export const getDataQualityScore = (data) => {
  if (!data) return 0;
  
  let score = 0;
  let maxScore = 0;
  
  // Check for core systemic risk data
  if (data.systemic_risk !== undefined) {
    maxScore += 20;
    if (isValidNumber(data.systemic_risk)) score += 20;
  }
  
  // Check for risk level
  if (data.risk_level !== undefined) {
    maxScore += 20;
    if (['high', 'medium', 'low'].includes(data.risk_level)) score += 20;
  }
  
  // Check for timestamp
  if (data.timestamp !== undefined) {
    maxScore += 20;
    if (typeof data.timestamp === 'string' && data.timestamp.length > 0) score += 20;
  }
  
  // Check for additional signals
  const additionalSignals = [
    'pca_component', 'credit_component', 'quantile_signal', 
    'dcc_correlation', 'har_excess_vol_z', 'composite_risk_score'
  ];
  
  additionalSignals.forEach(signal => {
    if (data[signal] !== undefined) {
      maxScore += 5;
      if (isValidNumber(data[signal])) score += 5;
    }
  });
  
  return maxScore > 0 ? (score / maxScore) * 100 : 0;
};

// Validate date range parameters
export const validateDateRangeParams = (params) => {
  const { days, startDate, endDate } = params || {};
  
  if (days !== undefined) {
    if (!isValidNumber(days) || days <= 0) {
      throw new Error('Days parameter must be a positive number');
    }
  }
  
  if (startDate !== undefined) {
    if (typeof startDate !== 'string' || !startDate.match(/^\d{4}-\d{2}-\d{2}$/)) {
      throw new Error('startDate must be in YYYY-MM-DD format');
    }
  }
  
  if (endDate !== undefined) {
    if (typeof endDate !== 'string' || !endDate.match(/^\d{4}-\d{2}-\d{2}$/)) {
      throw new Error('endDate must be in YYYY-MM-DD format');
    }
  }
  
  if (startDate && endDate && new Date(startDate) > new Date(endDate)) {
    throw new Error('startDate cannot be after endDate');
  }
  
  return true;
};

// Sanitize risk data for display
export const sanitizeRiskData = (data) => {
  if (!data || typeof data !== 'object') return data;
  
  const sanitized = { ...data };
  
  // Ensure numeric fields are properly formatted
  const numericFields = [
    'systemic_risk', 'systemic_mean', 'systemic_std', 'pca_component', 'credit_component',
    'quantile_signal', 'dcc_correlation', 'har_excess_vol_z', 'credit_spread_change',
    'vix_change', 'composite_risk_score'
  ];
  
  numericFields.forEach(field => {
    if (sanitized[field] !== undefined) {
      sanitized[field] = isValidNumber(sanitized[field]) ? 
        Number(sanitized[field].toFixed(6)) : null;
    }
  });
  
  // Ensure boolean fields are properly typed
  const booleanFields = ['is_warning', 'corr_exceeds_bootstrap'];
  booleanFields.forEach(field => {
    if (sanitized[field] !== undefined) {
      sanitized[field] = Boolean(sanitized[field]);
    }
  });
  
  return sanitized;
};