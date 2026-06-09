import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { buildDefaultUiConfig, normalizeUiConfig } from "../constants/featureFlags";

const FETCH_TIMEOUT_MS = 12_000;

let cached = normalizeUiConfig(null);
let cachePromise = null;

function fetchUiConfigWithTimeout() {
  return Promise.race([
    api.getUiConfig(),
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error("UI config timeout")), FETCH_TIMEOUT_MS);
    }),
  ]);
}

export function useUiConfig() {
  const [config, setConfig] = useState(cached);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchUiConfigWithTimeout();
      cached = normalizeUiConfig(data);
      setConfig(cached);
      return cached;
    } catch {
      cached = buildDefaultUiConfig();
      setConfig(cached);
      return cached;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (cachePromise) {
      cachePromise
        .then((data) => setConfig(data))
        .catch(() => setConfig(buildDefaultUiConfig()));
      return;
    }

    cachePromise = fetchUiConfigWithTimeout()
      .then((data) => {
        cached = normalizeUiConfig(data);
        return cached;
      })
      .catch(() => {
        cached = buildDefaultUiConfig();
        return cached;
      })
      .finally(() => {
        cachePromise = null;
      });

    cachePromise.then((data) => setConfig(data)).catch(() => setConfig(buildDefaultUiConfig()));
  }, []);

  return {
    config,
    loading,
    reload,
    invalidateCache: () => {
      cached = buildDefaultUiConfig();
      cachePromise = null;
    },
  };
}

export function invalidateUiConfigCache() {
  cached = buildDefaultUiConfig();
  cachePromise = null;
}
