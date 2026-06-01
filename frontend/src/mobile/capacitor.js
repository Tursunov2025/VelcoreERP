import { Capacitor } from "@capacitor/core";
import { PushNotifications } from "@capacitor/push-notifications";
import { SplashScreen } from "@capacitor/splash-screen";
import { StatusBar, Style } from "@capacitor/status-bar";

export function isNativeMobile() {
  return Capacitor.isNativePlatform();
}

export async function initMobileRuntime() {
  if (!isNativeMobile()) return;

  try {
    await StatusBar.setStyle({ style: Style.Dark });
  } catch {
    // Keep startup resilient if status bar plugin is unavailable.
  }

  try {
    await SplashScreen.hide();
  } catch {
    // Auto-hide is enabled; this is a safe fallback.
  }

// Push notifications temporarily disabled on Android
}
