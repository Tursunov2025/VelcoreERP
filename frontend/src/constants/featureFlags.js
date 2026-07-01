import { DEFAULT_DASHBOARD_WIDGETS } from "../constants/controlCenter";

/** Build-time defaults; runtime values come from GET /control-center/config/ui */

function envFlag(name) {
  const v = import.meta.env[name];
  return v === "true" || v === "1";
}

export const DEFAULT_FEATURE_FLAGS = {
  traceability_enabled: envFlag("VITE_TRACEABILITY_ENABLED"),
  print_agent_enabled: envFlag("VITE_PRINT_AGENT_ENABLED"),
};

/** Synchronous route gating — never waits on API. */
export function isTraceabilityEnabledForRoutes() {
  return DEFAULT_FEATURE_FLAGS.traceability_enabled;
}

export function isPrintAgentEnabledForRoutes() {
  return DEFAULT_FEATURE_FLAGS.print_agent_enabled;
}

export function normalizeFeatureFlags(raw) {
  return {
    traceability_enabled:
      raw?.traceability_enabled ?? DEFAULT_FEATURE_FLAGS.traceability_enabled,
    print_agent_enabled:
      raw?.print_agent_enabled ?? DEFAULT_FEATURE_FLAGS.print_agent_enabled,
  };
}

export function buildDefaultUiConfig() {
  return {
    nav_visibility: {},
    dashboard_widgets: DEFAULT_DASHBOARD_WIDGETS,
    mobile_app: null,
    feature_flags: { ...DEFAULT_FEATURE_FLAGS },
  };
}

export function normalizeUiConfig(data) {
  const base = buildDefaultUiConfig();
  if (!data || typeof data !== "object") return base;
  return {
    ...base,
    ...data,
    nav_visibility: data.nav_visibility || base.nav_visibility,
    dashboard_widgets: data.dashboard_widgets?.length
      ? data.dashboard_widgets
      : base.dashboard_widgets,
    feature_flags: normalizeFeatureFlags(data.feature_flags),
    super_admin: data.super_admin || null,
  };
}
