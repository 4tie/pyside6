import { useCallback, useEffect, useRef, useState } from 'react';

export interface SSEOptions {
  /** URL to connect to. Pass null/undefined to stay disconnected. */
  url: string | null | undefined;
  onMessage?: (data: string, event: string) => void;
  onError?: (err: Event) => void;
  onOpen?: () => void;
}

export type SSEState = 'idle' | 'connecting' | 'open' | 'closed' | 'error';

/**
 * Lightweight hook that manages an EventSource connection.
 * Reconnects automatically when `url` changes.
 */
export function useSSE({ url, onMessage, onError, onOpen }: SSEOptions): SSEState {
  const [state, setState] = useState<SSEState>('idle');
  const esRef = useRef<EventSource | null>(null);

  const close = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setState('closed');
  }, []);

  useEffect(() => {
    if (!url) {
      close();
      setState('idle');
      return;
    }

    setState('connecting');
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setState('open');
      onOpen?.();
    };

    es.onmessage = (ev: MessageEvent<string>) => {
      onMessage?.(ev.data, 'message');
    };

    // Named event listeners for SSE events with explicit event types
    const handleOutput = (ev: MessageEvent<string>) => onMessage?.(ev.data, 'output');
    const handleComplete = (ev: MessageEvent<string>) => onMessage?.(ev.data, 'complete');
    const handleStatus = (ev: MessageEvent<string>) => onMessage?.(ev.data, 'status');

    es.addEventListener('output', handleOutput as EventListener);
    es.addEventListener('complete', handleComplete as EventListener);
    es.addEventListener('status', handleStatus as EventListener);

    es.onerror = (ev) => {
      setState('error');
      onError?.(ev);
    };

    return () => {
      es.removeEventListener('output', handleOutput as EventListener);
      es.removeEventListener('complete', handleComplete as EventListener);
      es.removeEventListener('status', handleStatus as EventListener);
      es.close();
      esRef.current = null;
    };
  }, [url]);

  return state;
}
