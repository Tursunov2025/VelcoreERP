import { API_URL } from "../config";
import { getToken } from "./storage";

export const loginDriver = async (phone, password) => {
  const response = await fetch(`${API_URL}/driver/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, password }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || body.message || "Login xato");
  }
  return body;
};

export const postDriverLocation = async (latitude, longitude, status, token) => {
  const authToken = token || (await getToken());
  if (!authToken) {
    throw new Error("Token yo'q");
  }

  const response = await fetch(`${API_URL}/driver/location/me`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify({ latitude, longitude, status }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Server ${response.status}`);
  }
  return response.json();
};
