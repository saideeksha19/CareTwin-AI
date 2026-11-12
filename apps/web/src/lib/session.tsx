"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { DemoSession, DemoUser } from "@caretwin/contracts";
import { apiRequest, errorMessage } from "@/lib/api";
import { AUTH_MODE } from "@/lib/auth";

type SessionState = {
  session: DemoSession | null;
  users: DemoUser[];
  selectedUser: DemoUser | null;
  patientId: string | null;
  loading: boolean;
  error: string | null;
  switching: boolean;
  switchError: string | null;
  selectUser: (user: DemoUser) => void;
  switchUser: (user: DemoUser) => Promise<DemoUser>;
  clearUser: () => void;
  clearSwitchError: () => void;
  reload: () => void;
};

type AuthSessionPayload = {
  user: {
    id: string;
    role: string;
  };
};

const STORAGE_KEY = "caretwin.demoUserId";
const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<DemoSession | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) setSelectedId(stored);
    } catch {
      // localStorage may be unavailable in privacy modes.
    }
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    // The synthetic account switcher is demo-only. Production sign-in depends on
    // the configured identity provider, so no demo identity is offered here.
    if (AUTH_MODE === "production") {
      setError("Sign-in is required through the configured identity provider.");
      setLoading(false);
      return () => {
        active = false;
      };
    }
    apiRequest<DemoSession>("/demo/session", { signal: controller.signal })
      .then((payload) => {
        if (!active) return;
        setSession(payload);
        setLoading(false);
      })
      .catch((err) => {
        if (!active) return;
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(errorMessage(err));
        setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [reloadToken]);

  const selectUser = useCallback((user: DemoUser) => {
    setSelectedId(user.id);
    try {
      window.localStorage.setItem(STORAGE_KEY, user.id);
    } catch {
      // ignore storage failures
    }
  }, []);

  const switchUser = useCallback(async (user: DemoUser) => {
    if (AUTH_MODE === "production") {
      const message = "Demo role switching is not available in production mode.";
      setSwitchError(message);
      throw new Error(message);
    }
    setSwitching(true);
    setSwitchError(null);
    try {
      const payload = await apiRequest<DemoSession>("/demo/session/switch", {
        method: "POST",
        body: { userId: user.id },
      });
      const next = payload.users.find((candidate) => candidate.id === user.id);
      if (!next) {
        throw new Error("The backend did not confirm this demo identity.");
      }
      const confirmed = await apiRequest<AuthSessionPayload>("/auth/session", {
        userId: next.id,
      });
      if (
        confirmed.user.id !== next.id ||
        confirmed.user.role !== next.role
      ) {
        throw new Error("The backend returned a different demo identity.");
      }
      setSession(payload);
      selectUser(next);
      return next;
    } catch (err) {
      setSwitchError(errorMessage(err));
      throw err;
    } finally {
      setSwitching(false);
    }
  }, [selectUser]);

  const clearSwitchError = useCallback(() => setSwitchError(null), []);

  const clearUser = useCallback(() => {
    setSelectedId(null);
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  const users = useMemo(() => session?.users ?? [], [session]);
  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedId) ?? null,
    [users, selectedId],
  );

  const value = useMemo<SessionState>(
    () => ({
      session,
      users,
      selectedUser,
      patientId: selectedUser?.patientId ?? session?.patient.id ?? null,
      loading,
      error,
      switching,
      switchError,
      selectUser,
      switchUser,
      clearUser,
      clearSwitchError,
      reload: () => setReloadToken((token) => token + 1),
    }),
    [
      session,
      users,
      selectedUser,
      loading,
      error,
      switching,
      switchError,
      selectUser,
      switchUser,
      clearUser,
      clearSwitchError,
    ],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionState {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used inside SessionProvider.");
  }
  return context;
}
