/** SSE hook for workflow instance stream - NO RECONNECT after completion */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { WorkflowState } from '../types/cowork';

interface UseSSEOptions {
  onMessage?: (data: WorkflowState) => void;
  onError?: (error: Event) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

interface UseSSEReturn {
  isConnected: boolean;
  error: string | null;
  disconnect: () => void;
  reconnect: () => void;
}

export function useSSE(
  instanceId: string | null,
  options: UseSSEOptions = {}
): UseSSEReturn {
  const { onMessage, onError, onConnect, onDisconnect } = options;
  
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const workflowFinishedRef = useRef(false);
  const instanceIdRef = useRef(instanceId);

  // Keep ref in sync
  useEffect(() => {
    instanceIdRef.current = instanceId;
  }, [instanceId]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setIsConnected(false);
      onDisconnect?.();
    }
  }, [onDisconnect]);

  const connect = useCallback(() => {
    const currentInstanceId = instanceIdRef.current;
    if (!currentInstanceId) return;

    // NEVER reconnect if workflow finished
    if (workflowFinishedRef.current) {
      console.log('[SSE] BLOCKED: Workflow already finished');
      return;
    }

    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    console.log(`[SSE] Connecting to ${currentInstanceId}...`);
    const eventSource = new EventSource(
      `/api/workflows/${currentInstanceId}/stream`
    );

    eventSource.onopen = () => {
      console.log('[SSE] Connected');
      setIsConnected(true);
      setError(null);
      onConnect?.();
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WorkflowState & { error?: string };
        
        if (data.error) {
          console.error('[SSE] Server error:', data.error);
        }
        
        // CRITICAL: Mark as finished BEFORE calling onMessage to prevent any race condition
        if (data.status === 'completed' || data.status === 'failed') {
          console.log('[SSE] Workflow finished:', data.status);
          workflowFinishedRef.current = true;
          
          // Process the message first
          onMessage?.(data);
          
          // Then immediately disconnect and prevent any reconnection
          setTimeout(() => {
            disconnect();
          }, 100);
          return;
        }
        
        onMessage?.(data);
      } catch (err) {
        console.error('Failed to parse SSE message:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.log('[SSE] Connection error');
      setIsConnected(false);
      
      // CRITICAL: If workflow finished, don't report error or reconnect
      if (workflowFinishedRef.current) {
        console.log('[SSE] Ignoring error - workflow finished');
        return;
      }
      
      setError('Connection lost');
      onError?.(err);
      
      eventSource.close();
      eventSourceRef.current = null;
      
      // Only reconnect if workflow NOT finished
      if (!workflowFinishedRef.current && instanceIdRef.current === currentInstanceId) {
        setTimeout(() => {
          if (!workflowFinishedRef.current) {
            console.log('[SSE] Attempting reconnect...');
            connect();
          }
        }, 5000);
      }
    };

    eventSourceRef.current = eventSource;
  }, [onMessage, onError, onConnect, disconnect]);

  const reconnect = useCallback(() => {
    // Only allow reconnect if workflow hasn't finished
    if (!workflowFinishedRef.current) {
      disconnect();
      connect();
    }
  }, [disconnect, connect]);

  useEffect(() => {
    // Reset finished flag when instanceId changes (new workflow)
    if (instanceId) {
      workflowFinishedRef.current = false;
      connect();
    }

    return () => {
      // Mark as finished on unmount to prevent any reconnect attempts
      workflowFinishedRef.current = true;
      disconnect();
    };
  }, [instanceId, connect, disconnect]);

  return {
    isConnected,
    error,
    disconnect,
    reconnect,
  };
}
