import { useCallback, useEffect, useState } from "react";
import { App } from "@capacitor/app";
import { api } from "../api/client";
import { isNativeMobile } from "../mobile/capacitor";
import { downloadApk } from "../mobile/appUpdate";

const DISMISS_KEY = "azmus_update_dismissed_code";

export function useMobileAppUpdate() {
  const [state, setState] = useState({
    checking: false,
    ready: false,
    updateAvailable: false,
    forceUpdate: false,
    latest: null,
    installedCode: 0,
    error: null,
    downloading: false,
  });

  const check = useCallback(async () => {
    if (!isNativeMobile()) {
      setState((s) => ({ ...s, ready: true, updateAvailable: false }));
      return;
    }
    setState((s) => ({ ...s, checking: true, error: null }));
    try {
      const info = await App.getInfo();
      const installedCode = parseInt(String(info.build || "0"), 10) || 0;
      const remote = await api.getMobileVersion();
      const remoteCode = Number(remote.version_code) || 0;
      const hasApk = Boolean(remote.apk_url);
      const updateAvailable = hasApk && remoteCode > installedCode;
      const dismissed = Number(localStorage.getItem(DISMISS_KEY) || "0");
      const showPrompt =
        updateAvailable && (remote.force_update || dismissed < remoteCode);

      setState({
        checking: false,
        ready: true,
        updateAvailable,
        forceUpdate: Boolean(remote.force_update) && updateAvailable,
        latest: remote,
        installedCode,
        showPrompt,
        error: null,
        downloading: false,
      });
    } catch (e) {
      setState((s) => ({
        ...s,
        checking: false,
        ready: true,
        error: e.message,
        updateAvailable: false,
        showPrompt: false,
      }));
    }
  }, []);

  useEffect(() => {
    check();
  }, [check]);

  const dismissLater = useCallback(() => {
    if (state.latest?.version_code) {
      localStorage.setItem(DISMISS_KEY, String(state.latest.version_code));
    }
    setState((s) => ({ ...s, showPrompt: false }));
  }, [state.latest]);

  const startUpdate = useCallback(async () => {
    const url = state.latest?.apk_url;
    if (!url) return;
    setState((s) => ({ ...s, downloading: true, error: null }));
    try {
      await downloadApk(url);
    } catch (e) {
      setState((s) => ({ ...s, downloading: false, error: e.message }));
      throw e;
    } finally {
      setState((s) => ({ ...s, downloading: false }));
    }
  }, [state.latest]);

  return {
    ...state,
    check,
    dismissLater,
    startUpdate,
  };
}
