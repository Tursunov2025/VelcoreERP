import { registerPlugin } from "@capacitor/core";

export const DriverTracking = registerPlugin("DriverTracking");

export function isNativeAndroid() {
  try {
    return (
      typeof window !== "undefined" &&
      window.Capacitor?.isNativePlatform?.() &&
      window.Capacitor.getPlatform() === "android"
    );
  } catch {
    return false;
  }
}
