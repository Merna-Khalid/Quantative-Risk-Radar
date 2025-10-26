import { useRiskStore } from '../stores/riskStore';
import { API_BASE_URL } from './constants';
import { validateApiResponse, isValidRiskData } from '../utils/validators';

const getStore = () => useRiskStore.getState();

class ApiService {
  constructor(baseURL = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  async fetchWithRetry(endpoint, options = {}, retries = 3) {
    for (let attempt = 0; attempt < retries; attempt++) {
      try {
        const response = await fetch(`${this.baseURL}${endpoint}`, options);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        validateApiResponse(data);
        return data;
        
      } catch (error) {
        console.error(`Attempt ${attempt + 1} failed:`, error);
        
        if (attempt === retries - 1) {
          getStore().setError(error.message);
          throw error;
        }
        
        const delay = Math.pow(2, attempt) * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  async getRiskHistory({ days = null, startDate = null, endDate = null } = {}) {
    getStore().setLoading(true);
    try {
      const params = new URLSearchParams();
      
      if (days) params.append('days', days);
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);

      if (!days && !startDate && !endDate) {
        params.append('days', 180);
      }
      
      const response = await this.fetchWithRetry(`/risk/history?${params}`);
      
      if (response && response.data && Array.isArray(response.data)) {
        console.log('Received enhanced risk data format:', {
          dataPoints: response.data.length,
          hasSummary: !!response.summary
        });
        return response;
      } else if (Array.isArray(response)) {
        console.log('Received legacy array format, wrapping in enhanced structure');
        return {
          data: response,
          summary: this._generateSummaryFromArray(response)
        };
      } else {
        console.error('Invalid risk data format received:', response);
        throw new Error('Invalid risk data format received');
      }
    } finally {
      getStore().setLoading(false);
    }
  }


  // Helper method to generate summary from array data (for legacy format)
  _generateSummaryFromArray(data) {
    if (!data || !Array.isArray(data) || data.length === 0) {
      return null;
    }

    const systemicRisks = data.map(d => d.systemic_risk || 0).filter(risk => !isNaN(risk));
    if (systemicRisks.length === 0) return null;

    const mean = systemicRisks.reduce((sum, risk) => sum + risk, 0) / systemicRisks.length;
    const std = Math.sqrt(
      systemicRisks.reduce((sum, risk) => sum + Math.pow(risk - mean, 2), 0) / systemicRisks.length
    );

    return {
      period_mean: mean,
      period_std: std,
      period_min: Math.min(...systemicRisks),
      period_max: Math.max(...systemicRisks),
      data_points: data.length,
      date_range: {
        start: data[0]?.date || '',
        end: data[data.length - 1]?.date || ''
      }
    };
  }
}

export const apiService = new ApiService();