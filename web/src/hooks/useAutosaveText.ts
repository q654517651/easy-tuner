import { useState, useRef, useCallback, useEffect } from 'react';

interface UseAutosaveTextOptions {
  initial: string;
  autosaveDelay: number;
  onSave: (text: string) => Promise<void> | void;
}

export function useAutosaveText({ initial, autosaveDelay, onSave }: UseAutosaveTextOptions) {
  const [text, setText] = useState(initial);
  const savedRef = useRef(text);
  const timerRef = useRef<number | null>(null);

  // 同步外部更新到内部状态
  useEffect(() => {
    setText(initial);
    savedRef.current = initial;
  }, [initial]);

  // 防抖保存
  const debouncedSave = useCallback((value: string) => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    timerRef.current = window.setTimeout(() => {
      if (value !== savedRef.current) {
        onSave(value);
        savedRef.current = value;
      }
    }, autosaveDelay);
  }, [autosaveDelay, onSave]);

  // 立即保存（Ctrl+Enter / Cmd+Enter）
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      onSave(text);
      savedRef.current = text;
    }
  }, [text, onSave]);

  const handleChange = useCallback((value: string) => {
    setText(value);
    debouncedSave(value);
  }, [debouncedSave]);

  // 清理定时器
  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
  }, []);

  return {
    text,
    setText: handleChange,
    bindTextareaHandlers: {
      onKeyDown: handleKeyDown
    },
    cleanup
  };
}