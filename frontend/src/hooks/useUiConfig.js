import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { DEFAULT_DASHBOARD_WIDGETS } from "../constants/controlCenter";

let cached = null;
let cachePromise = null;

export function useUiConfig() {
  const [config, setConfig] = useState(
    cached || {
      nav_visibility: {},
      dashboard_widgets: DEFAULT_DASHBOARD_WIDGETS,
      mobile_app: null,
    }
  );
  const [loading, setLoading] = useState(!cached);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getUiConfig();
      cached = data;
      setConfig(data);
      return data;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (cached) {
      setConfig(cached);
      setLoading(false);
      return;
    }
    if (!cachePromise) {
      cachePromise = api.getUiConfig().then((data) => {
        cached = data;
        return data;
      });
    }
    cachePromise
      .then((data) => setConfig(data))
      .catch(() => {})
      .finally(() => {
        setLoading(false);
        cachePromise = null;
      });
  }, []);

  return { config, loading, reload, invalidateCache: () => { cached = null; } };
}

export function invalidateUiConfigCache() {
  cached = null;
  cachePromise = null;
}
