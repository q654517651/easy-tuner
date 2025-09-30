import React, { createContext, useContext, useMemo, useState } from 'react';

type ReadinessCtx = {
  workspaceReady: boolean;
  runtimeReady: boolean;
  loading: boolean;
  setWorkspaceReady: React.Dispatch<React.SetStateAction<boolean>>;
  setRuntimeReady: React.Dispatch<React.SetStateAction<boolean>>;
  setLoading: React.Dispatch<React.SetStateAction<boolean>>;
  reset: () => void;
};

const Ctx = createContext<ReadinessCtx | null>(null);

export function ReadinessProvider({ children }: { children: React.ReactNode }) {
  const [workspaceReady, setWorkspaceReady] = useState<boolean>(false);
  const [runtimeReady, setRuntimeReady] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);

  const reset = () => {
    setWorkspaceReady(false);
    setRuntimeReady(false);
    setLoading(false);
  };

  const value = useMemo<ReadinessCtx>(() => ({
    workspaceReady,
    runtimeReady,
    loading,
    setWorkspaceReady,
    setRuntimeReady,
    setLoading,
    reset,
  }), [workspaceReady, runtimeReady, loading]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useReadiness() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useReadiness must be used within ReadinessProvider');
  return ctx;
}

