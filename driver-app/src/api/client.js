import { Preferences } from "@capacitor/preferences";

const API_BASE = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const TOKEN_KEY = "azmus_driver_tokens";
const SETTINGS_KEY = "azmus_driver_settings";
const QUEUE_KEY = "azmus_driver_offline_queue";

export function getApiBase() {
  return API_BASE;
}

export async function getStoredTokens() {
  const { value } = await Preferences.get({ key: TOKEN_KEY });
  if (!value) return null;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

export async function setStoredTokens(tokens) {
  if (tokens) {
    await Preferences.set({ key: TOKEN_KEY, value: JSON.stringify(tokens) });
  } else {
    await Preferences.remove({ key: TOKEN_KEY });
  }
}

export async function getSettings() {
  const { value } = await Preferences.get({ key: SETTINGS_KEY });
  if (!value) return { apiUrl: API_BASE };
  try {
    return { apiUrl: API_BASE, ...JSON.parse(value) };
  } catch {
    return { apiUrl: API_BASE };
  }
}

export async function saveSettings(settings) {
  await Preferences.set({ key: SETTINGS_KEY, value: JSON.stringify(settings) });
}

async function refreshAccessToken(apiUrl) {
  const tokens = await getStoredTokens();
  if (!tokens?.refresh_token) return null;
  const res = await fetch(`${apiUrl}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  });
  if (!res.ok) {
    await setStoredTokens(null);
    return null;
  }
  const data = await res.json();
  const next = {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    username: data.username,
    role: data.role,
  };
  await setStoredTokens(next);
  return next.access_token;
}

async function request(path, options = {}, retry = true) {
  const settings = await getSettings();
  const apiUrl = (settings.apiUrl || API_BASE).replace(/\/+$/, "");
  const tokens = await getStoredTokens();
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (tokens?.access_token) {
    headers.Authorization = `Bearer ${tokens.access_token}`;
  }
  const res = await fetch(`${apiUrl}${path}`, { ...options, headers });
  if (res.status === 401 && retry) {
    const token = await refreshAccessToken(apiUrl);
    if (token) return request(path, options, false);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.message || detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function login(username, password) {
  const settings = await getSettings();
  const apiUrl = (settings.apiUrl || API_BASE).replace(/\/+$/, "");
  const res = await fetch(`${apiUrl}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Login failed");
  }
  const data = await res.json();
  await setStoredTokens({
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    username: data.username,
    role: data.role,
  });
  return data;
}

export async function logout() {
  await setStoredTokens(null);
}

export async function fetchVehicles() {
  const data = await request("/gps/vehicles");
  return data.vehicles || [];
}

export async function fetchDrivers() {
  const data = await request("/gps/drivers");
  return data.drivers || [];
}

export async function postLocation(payload) {
  return request("/gps/location/update", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getOfflineQueue() {
  const { value } = await Preferences.get({ key: QUEUE_KEY });
  if (!value) return [];
  try {
    return JSON.parse(value);
  } catch {
    return [];
  }
}

export async function setOfflineQueue(queue) {
  await Preferences.set({ key: QUEUE_KEY, value: JSON.stringify(queue) });
}

export async function enqueueLocation(item) {
  const queue = await getOfflineQueue();
  queue.push(item);
  if (queue.length > 500) queue.splice(0, queue.length - 500);
  await setOfflineQueue(queue);
  return queue.length;
}

export async function syncOfflineQueue() {
  const queue = await getOfflineQueue();
  if (!queue.length) return { synced: 0, remaining: 0 };
  const remaining = [];
  let synced = 0;
  for (const item of queue) {
    try {
      await postLocation(item);
      synced += 1;
    } catch {
      remaining.push(item);
    }
  }
  await setOfflineQueue(remaining);
  return { synced, remaining: remaining.length };
}
