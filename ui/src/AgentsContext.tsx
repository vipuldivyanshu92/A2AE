import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  AGENTS_STORAGE_KEY,
  loadAgents,
  saveAgents,
  type ExternalAgent,
} from "./agentsRegistry";

type AgentsContextValue = {
  agents: ExternalAgent[];
  setAgents: (next: ExternalAgent[]) => void;
  upsertAgent: (a: ExternalAgent) => void;
  removeAgent: (id: string) => void;
};

const AgentsContext = createContext<AgentsContextValue | null>(null);

export function AgentsProvider({ children }: { children: ReactNode }) {
  const [agents, setAgentsState] = useState<ExternalAgent[]>(() => loadAgents());

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === AGENTS_STORAGE_KEY) {
        setAgentsState(loadAgents());
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setAgents = useCallback((next: ExternalAgent[]) => {
    setAgentsState(next);
    saveAgents(next);
  }, []);

  const upsertAgent = useCallback((a: ExternalAgent) => {
    setAgentsState((prev) => {
      const i = prev.findIndex((x) => x.id === a.id);
      const next = i < 0 ? [...prev, a] : prev.map((x, j) => (j === i ? a : x));
      saveAgents(next);
      return next;
    });
  }, []);

  const removeAgent = useCallback((id: string) => {
    setAgentsState((prev) => {
      const next = prev.filter((x) => x.id !== id);
      saveAgents(next);
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({ agents, setAgents, upsertAgent, removeAgent }),
    [agents, setAgents, upsertAgent, removeAgent]
  );

  return <AgentsContext.Provider value={value}>{children}</AgentsContext.Provider>;
}

export function useAgents(): AgentsContextValue {
  const ctx = useContext(AgentsContext);
  if (!ctx) throw new Error("useAgents must be used within AgentsProvider");
  return ctx;
}
