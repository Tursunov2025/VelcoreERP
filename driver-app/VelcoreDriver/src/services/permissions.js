import { Alert, Linking, Platform } from "react-native";
import * as Location from "expo-location";

export async function requestLocationPermissions() {
  const { status: foregroundStatus } = await Location.requestForegroundPermissionsAsync();
  if (foregroundStatus !== "granted") {
    Alert.alert("Ruxsat kerak", "Joylashuvni aniqlash uchun ruxsat bering.");
    return false;
  }

  const { status: backgroundStatus } = await Location.requestBackgroundPermissionsAsync();
  if (backgroundStatus !== "granted") {
    Alert.alert(
      "Doimiy ruxsat kerak",
      "YouTube yoki boshqa ilovaga o'tganda ham kuzatish uchun sozlamalardan «Doim ruxsat berish» (Always Allow) ni tanlang.",
      [
        { text: "Bekor qilish", style: "cancel" },
        {
          text: "Sozlamalar",
          onPress: () => {
            if (Platform.OS === "ios") {
              Linking.openURL("app-settings:");
            } else {
              Linking.openSettings();
            }
          },
        },
      ]
    );
    return false;
  }

  return true;
}
