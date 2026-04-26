import { useEffect, useRef, useState } from 'react';

export type SaveState = 'idle' | 'saving' | 'saved' | 'error';

export function useAutosave<T>(
  value: T,
  save: (value: T) => Promise<unknown>,
  options: { enabled: boolean; delay?: number } = { enabled: true, delay: 500 }
): SaveState {
  const [state, setState] = useState<SaveState>('idle');
  const firstValue = useRef(true);
  const serialized = JSON.stringify(value);
  const delay = options.delay ?? 500;

  useEffect(() => {
    if (!options.enabled) {
      return;
    }
    if (firstValue.current) {
      firstValue.current = false;
      return;
    }

    setState('saving');
    const timeout = window.setTimeout(() => {
      save(value)
        .then(() => {
          setState('saved');
          window.setTimeout(() => setState('idle'), 1200);
        })
        .catch(() => setState('error'));
    }, delay);

    return () => window.clearTimeout(timeout);
  }, [serialized, options.enabled, delay]);

  return state;
}
