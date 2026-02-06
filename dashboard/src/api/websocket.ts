import { useCallback, useEffect, useRef, useState } from "react";
import type { WsMessage, Opportunity } from "@/types";

interface UseAnalysisWebSocketOptions {
  runId: string | null;
  onComplete?: (totalOpportunities: number, durationMs: number) => void;
  onError?: (message: string) => void;
}

interface WebSocketState {
  connected: boolean;
  messages: WsMessage[];
  currentStep: string | null;
  completedSteps: { agent: string; duration_ms: number }[];
  opportunities: Opportunity[];
  isComplete: boolean;
  error: string | null;
}

export function useAnalysisWebSocket({
  runId,
  onComplete,
  onError,
}: UseAnalysisWebSocketOptions): WebSocketState {
  const [state, setState] = useState<WebSocketState>({
    connected: false,
    messages: [],
    currentStep: null,
    completedSteps: [],
    opportunities: [],
    isComplete: false,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const maxRetries = 3;

  const connect = useCallback(() => {
    if (!runId) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const token = localStorage.getItem("nba_dashboard_token") ?? "";
    const url = `${protocol}//${host}/ws/analysis/${runId}?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setState((s) => ({ ...s, connected: true }));
      retriesRef.current = 0;
    };

    ws.onmessage = (event) => {
      const msg: WsMessage = JSON.parse(event.data);

      if (msg.type === "heartbeat") return;

      setState((s) => {
        const newState = { ...s, messages: [...s.messages, msg] };

        switch (msg.type) {
          case "status":
            newState.currentStep = msg.step;
            break;
          case "agent_complete":
            newState.completedSteps = [
              ...s.completedSteps,
              { agent: msg.agent, duration_ms: msg.duration_ms },
            ];
            break;
          case "opportunity":
            newState.opportunities = [...s.opportunities, msg.opportunity];
            break;
          case "complete":
            newState.isComplete = true;
            newState.currentStep = null;
            onComplete?.(msg.total_opportunities, msg.duration_ms);
            break;
          case "error":
            newState.error = msg.message;
            onError?.(msg.message);
            break;
        }

        return newState;
      });
    };

    ws.onclose = () => {
      setState((s) => ({ ...s, connected: false }));
      // Reconnect with backoff if not complete
      if (retriesRef.current < maxRetries) {
        const delay = Math.min(1000 * Math.pow(2, retriesRef.current), 8000);
        retriesRef.current++;
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [runId, onComplete, onError]);

  useEffect(() => {
    // Reset state on new run
    setState({
      connected: false,
      messages: [],
      currentStep: null,
      completedSteps: [],
      opportunities: [],
      isComplete: false,
      error: null,
    });
    retriesRef.current = 0;
    connect();

    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return state;
}
