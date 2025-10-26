// src/hooks/useWebSocket.js
import { useEffect, useRef, useCallback } from 'react';
import { useRiskStore } from '../stores/riskStore';

export const useWebSocket = (endpoint, onMessageCallback = null) => {
  const socketRef = useRef(null);
  const { setRealtimeData, setError } = useRiskStore();

  const connect = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}${endpoint}`;
      
      socketRef.current = new WebSocket(wsUrl);

      socketRef.current.onopen = () => {
        console.log(`WebSocket connected to ${endpoint}`);
        setError(null);
      };

      socketRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data && data.timestamp && !data.error) {
            setRealtimeData(data);
            
            if (onMessageCallback) {
              onMessageCallback(data);
            }
          }
        } catch (error) {
          console.error('Error processing WebSocket message:', error);
          setError('Failed to process WebSocket message');
        }
      };

      socketRef.current.onclose = (event) => {
        console.log(`WebSocket disconnected: ${event.code} ${event.reason}`);
        
        setTimeout(() => {
          connect();
        }, 5000);
      };

      socketRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('WebSocket connection error');
      };

    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      setError('Failed to establish WebSocket connection');
    }
  }, [endpoint, setRealtimeData, setError, onMessageCallback]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected: socketRef.current?.readyState === WebSocket.OPEN
  };
};