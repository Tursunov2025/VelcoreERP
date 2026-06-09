import { normalizeFeatureFlags } from "../constants/featureFlags";
import { useUiConfig } from "./useUiConfig";

export function useFeatureFlags() {
  const { config } = useUiConfig();
  const flags = normalizeFeatureFlags(config?.feature_flags);
  return {
    traceabilityEnabled: Boolean(flags.traceability_enabled),
    printAgentEnabled: Boolean(flags.print_agent_enabled),
  };
}
