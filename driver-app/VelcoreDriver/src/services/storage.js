import AsyncStorage from "@react-native-async-storage/async-storage";

import { API_URL } from "../config";

export const STORAGE_KEYS = {
  ACCESS_TOKEN: "@velcore/access_token",
  REFRESH_TOKEN: "@velcore/refresh_token",
  DRIVER_ID: "@velcore/driver_id",
  DRIVER_NAME: "@velcore/driver_name",
  USERNAME: "@velcore/username",
};

export async function getToken() {
  return AsyncStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
}

export async function saveSession({ accessToken, refreshToken, driver, username }) {
  const pairs = [
    [STORAGE_KEYS.ACCESS_TOKEN, accessToken],
    [STORAGE_KEYS.REFRESH_TOKEN, refreshToken || ""],
    [STORAGE_KEYS.USERNAME, username || ""],
  ];
  if (driver?.id != null) {
    pairs.push([STORAGE_KEYS.DRIVER_ID, String(driver.id)]);
    pairs.push([STORAGE_KEYS.DRIVER_NAME, driver.full_name || ""]);
  }
  await AsyncStorage.multiSet(pairs);
}

export async function clearSession() {
  await AsyncStorage.multiRemove(Object.values(STORAGE_KEYS));
}

export async function getStoredSession() {
  const token = await getToken();
  if (!token) return null;
  const [[, driverId], [, driverName], [, username]] = await AsyncStorage.multiGet([
    STORAGE_KEYS.DRIVER_ID,
    STORAGE_KEYS.DRIVER_NAME,
    STORAGE_KEYS.USERNAME,
  ]);
  return {
    accessToken: token,
    driverId: driverId ? Number(driverId) : null,
    driverName: driverName || "",
    username: username || "",
  };
}

export { API_URL };
