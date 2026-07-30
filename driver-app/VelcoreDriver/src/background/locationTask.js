import * as Location from "expo-location";
import * as TaskManager from "expo-task-manager";

import {
  BACKGROUND_LOCATION_TASK,
  DISTANCE_INTERVAL,
  TRACKING_INTERVAL,
} from "../config";
import { postDriverLocation } from "../services/api";
import { getToken } from "../services/storage";

TaskManager.defineTask(BACKGROUND_LOCATION_TASK, async ({ data, error }) => {
  if (error) {
    console.error("Fondagi GPS xatoligi:", error);
    return;
  }
  if (data) {
    const { locations } = data;
    const { latitude, longitude } = locations[0].coords;

    try {
      const token = await getToken();
      if (!token) return;

      await postDriverLocation(latitude, longitude, "active", token);
      console.log("📍 Fonda koordinata uzatildi:", latitude, longitude);
    } catch (err) {
      console.log("Fonda yuborishda muammo:", err.message);
    }
  }
});

export async function isBackgroundTrackingActive() {
  return Location.hasStartedLocationUpdatesAsync(BACKGROUND_LOCATION_TASK);
}

export async function startBackgroundTracking() {
  const started = await Location.hasStartedLocationUpdatesAsync(BACKGROUND_LOCATION_TASK);
  if (started) {
    return true;
  }

  await Location.startLocationUpdatesAsync(BACKGROUND_LOCATION_TASK, {
    accuracy: Location.Accuracy.High,
    timeInterval: TRACKING_INTERVAL,
    distanceInterval: DISTANCE_INTERVAL,
    deferredUpdatesInterval: TRACKING_INTERVAL,
    showsBackgroundLocationIndicator: true,
    pausesUpdatesAutomatically: false,
    activityType: Location.ActivityType.AutomotiveNavigation,
    foregroundService: {
      notificationTitle: "Velcore ERP",
      notificationBody: "Haydovchi joylashuvi aniqlanmoqda...",
      notificationColor: "#1e3a8a",
    },
  });
  return true;
}

export async function stopBackgroundTracking() {
  const started = await Location.hasStartedLocationUpdatesAsync(BACKGROUND_LOCATION_TASK);
  if (started) {
    await Location.stopLocationUpdatesAsync(BACKGROUND_LOCATION_TASK);
  }
}
