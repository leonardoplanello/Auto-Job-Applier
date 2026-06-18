import { useEffect, useRef, useCallback, useState } from 'react';
import { useBot } from './useBot';
import type { LogEntry, PopupPayload } from './useBot';
import api, { API_BASE_URL } from '../lib/api';

export const useWebSocket = () => {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectDelayRef = useRef(1000);
  const [isConnected, setIsConnected] = useState(false);
  
  const {
    setBotStatus,
    setSessionId,
    setBotMode,
    setStats,
    setCurrentJob,
    setActivePopup,
    addLog,
    triggerJobsRefresh,
  } = useBot();

  const connect = useCallback(() => {
    // Convert http://localhost:7000 to ws://localhost:7000
    const wsUrl = API_BASE_URL.replace(/^http/, 'ws') + '/ws';
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected.');
      reconnectDelayRef.current = 1000;
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        const { type, payload } = message;

        switch (type) {
          case 'bot_status':
            setBotStatus(payload.status);
            setSessionId(payload.session_id);
            setBotMode(payload.mode);
            setStats(payload.stats);
            setCurrentJob(payload.current_job);
            if (payload.active_popup) {
              setActivePopup(payload.active_popup);
            }
            triggerJobsRefresh();
            break;
            
          case 'popup':
            setActivePopup(payload as PopupPayload);
            break;
            
          case 'popup_close':
            setActivePopup(null);
            break;
            
          case 'log_entry':
            addLog(payload as LogEntry);
            break;

          default:
            break;

        }
      } catch (err) {
        console.error('Error processing WS message:', err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      scheduleReconnect();
    };

    ws.onerror = () => {
      setIsConnected(false);
      ws.close();
    };
  }, [setBotStatus, setSessionId, setBotMode, setStats, setCurrentJob, setActivePopup, addLog, triggerJobsRefresh]);

  const scheduleReconnect = () => {
    if (reconnectTimeoutRef.current) return;
    
    reconnectTimeoutRef.current = window.setTimeout(() => {
      reconnectTimeoutRef.current = null;
      reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 1.5, 30000);
      connect();
    }, reconnectDelayRef.current);
  };

  useEffect(() => {
    connect();

    const fetchInitialStatus = async () => {
      try {
        const res = await api.get('/api/bot/status');
        const payload = res.data;
        setBotStatus(payload.status);
        setSessionId(payload.session_id);
        setBotMode(payload.mode);
        setStats(payload.stats);
        setCurrentJob(payload.current_job);
        if (payload.active_popup) {
          setActivePopup(payload.active_popup);
        }
      } catch (err) {
        console.error('Failed to fetch initial bot status:', err);
      }
    };
    fetchInitialStatus();

    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect, setBotStatus, setSessionId, setBotMode, setStats, setCurrentJob, setActivePopup]);

  const sendMessage = (type: string, payload: any) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type, payload }));
    }
  };

  const answerPopup = (popupId: string, answer: any, save: boolean) => {
    sendMessage('answer_popup', { popup_id: popupId, answer, save });
  };

  const skipJob = (popupId: string) => {
    sendMessage('skip_job', { popup_id: popupId });
  };

  const closePopup = (popupId: string) => {
    sendMessage('close_popup', { popup_id: popupId });
  };

  const manualDone = (popupId: string) => {
    sendMessage('manual_done', { popup_id: popupId });
  };

  return {
    answerPopup,
    skipJob,
    closePopup,
    manualDone,
    isConnected,
  };
};
