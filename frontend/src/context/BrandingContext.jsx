import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api } from "../api/client";
import { DEFAULT_BRANDING, mergeBranding } from "../constants/brandingDefaults";
import {
  applyBrandingToDocument,
  applyThemeToDocument,
  getNavEmoji,
  resolveAssetUrl,
} from "../utils/applyBranding";

const BrandingContext = createContext(null);

export function BrandingProvider({ children }) {
  const [branding, setBranding] = useState(DEFAULT_BRANDING);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await api.getBranding();
      const merged = mergeBranding(data);
      setBranding(merged);
      applyBrandingToDocument(merged);
    } catch {
      applyBrandingToDocument(DEFAULT_BRANDING);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const updateLocal = useCallback((next) => {
    const merged = mergeBranding(next);
    setBranding(merged);
    applyBrandingToDocument(merged);
  }, []);

  const save = useCallback(async (payload) => {
    const data = await api.adminUpdateBranding(payload);
    const merged = mergeBranding(data);
    setBranding(merged);
    applyBrandingToDocument(merged);
    return merged;
  }, []);

  const reset = useCallback(async () => {
    const data = await api.adminResetBranding();
    const merged = mergeBranding(data);
    setBranding(merged);
    applyBrandingToDocument(merged);
    return merged;
  }, []);

  const navEmoji = useCallback(
    (iconKey) => getNavEmoji(branding, iconKey),
    [branding]
  );

  const assetUrl = useCallback((path) => resolveAssetUrl(path), []);

  const value = useMemo(
    () => ({
      branding,
      loading,
      reload: load,
      updateLocal,
      save,
      reset,
      navEmoji,
      assetUrl,
    }),
    [branding, loading, load, updateLocal, save, reset, navEmoji, assetUrl]
  );

  return (
    <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>
  );
}

export function useBranding() {
  const ctx = useContext(BrandingContext);
  if (!ctx) throw new Error("useBranding must be used within BrandingProvider");
  return ctx;
}
