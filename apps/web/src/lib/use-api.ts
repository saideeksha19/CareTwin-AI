"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "@/lib/session";
import { apiRequest } from "@/lib/api";

type ApiState<T> = {
  data: T | null;
  error: unknown;
  loading: boolean;
  refresh: () => void;
  setData: (value: T | null) => void;
};

export function useApi<T>(path: string | null, enabled = true): ApiState<T> {
  const { selectedUser } = useSession();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState(0);
  const mounted = useRef(true);
  const requestKey = `${selectedUser?.id ?? "anonymous"}:${path ?? ""}`;
  const lastRequestKey = useRef(requestKey);

  const refresh = useCallback(() => setToken((value) => value + 1), []);

  useEffect(() => {
    mounted.current = true;
    if (lastRequestKey.current !== requestKey) {
      lastRequestKey.current = requestKey;
      setData(null);
      setError(null);
    }
    if (!path || !enabled || !selectedUser) {
      setLoading(false);
      return () => {
        mounted.current = false;
      };
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    apiRequest<T>(path, {
      userId: selectedUser.id,
      signal: controller.signal,
    })
      .then((payload) => {
        if (!mounted.current) return;
        setData(payload);
        setLoading(false);
      })
      .catch((err) => {
        if (!mounted.current) return;
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err);
        setLoading(false);
      });
    return () => {
      mounted.current = false;
      controller.abort();
    };
  }, [path, enabled, selectedUser, token, requestKey]);

  return { data, error, loading, refresh, setData };
}
