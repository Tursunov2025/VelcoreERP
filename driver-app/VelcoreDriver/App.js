import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Button,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  isBackgroundTrackingActive,
  startBackgroundTracking,
  stopBackgroundTracking,
} from "./src/background/locationTask";
import { API_URL } from "./src/config";
import { loginDriver } from "./src/services/api";
import { requestLocationPermissions } from "./src/services/permissions";
import { clearSession, getStoredSession, saveSession } from "./src/services/storage";

export default function App() {
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState(null);
  const [isTracking, setIsTracking] = useState(false);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const refreshTrackingState = useCallback(async () => {
    try {
      const active = await isBackgroundTrackingActive();
      setIsTracking(active);
    } catch {
      setIsTracking(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      const stored = await getStoredSession();
      setSession(stored);
      await refreshTrackingState();
      setLoading(false);
    })();
  }, [refreshTrackingState]);

  const handleLogin = async () => {
    setSubmitting(true);
    try {
      const data = await loginDriver(phone.trim(), password);
      await saveSession({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        driver: data.driver,
        username: data.username,
      });
      setSession({
        accessToken: data.access_token,
        driverId: data.driver?.id ?? null,
        driverName: data.driver?.full_name ?? data.username,
        username: data.username,
      });

      const ok = await requestLocationPermissions();
      if (ok) {
        await startBackgroundTracking();
        await refreshTrackingState();
      }
    } catch (err) {
      Alert.alert("Login xato", err.message || "Qayta urinib ko'ring");
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartTracking = async () => {
    const ok = await requestLocationPermissions();
    if (!ok) return;
    try {
      await startBackgroundTracking();
      await refreshTrackingState();
      Alert.alert("Tayyor", "Fon GPS kuzatuvi yoqildi (har 10 soniyada).");
    } catch (err) {
      Alert.alert("Xatolik", err.message);
    }
  };

  const handleStopTracking = async () => {
    await stopBackgroundTracking();
    await refreshTrackingState();
  };

  const handleLogout = async () => {
    await stopBackgroundTracking();
    await clearSession();
    setSession(null);
    setIsTracking(false);
    setPassword("");
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#1e3a8a" />
      </View>
    );
  }

  if (!session) {
    return (
      <View style={styles.container}>
        <StatusBar style="dark" />
        <Text style={styles.title}>Velcore Haydovchi</Text>
        <Text style={styles.subtitle}>ERP logistika — fon GPS kuzatuvi</Text>
        <Text style={styles.apiLabel}>Server: {API_URL}</Text>

        <TextInput
          style={styles.input}
          placeholder="Telefon (+998...)"
          keyboardType="phone-pad"
          autoCapitalize="none"
          value={phone}
          onChangeText={setPhone}
        />
        <TextInput
          style={styles.input}
          placeholder="Parol"
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />

        <Button
          title={submitting ? "Kirish..." : "Kirish va kuzatishni yoqish"}
          onPress={handleLogin}
          disabled={submitting || !phone.trim() || !password}
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      <Text style={styles.title}>Velcore Haydovchi Tizimi</Text>
      <Text style={styles.driverName}>{session.driverName || session.username}</Text>
      <Text style={styles.status}>
        Holat: {isTracking ? "🟢 Kuzatilmoqda (fon rejimida)" : "🔴 O'chiq"}
      </Text>
      <Text style={styles.hint}>
        YouTube yoki boshqa ilovaga o'tsangiz ham har 10 soniyada joylashuv yuboriladi.
      </Text>

      <View style={styles.actions}>
        {!isTracking ? (
          <Button title="Kuzatishni yoqish" onPress={handleStartTracking} />
        ) : (
          <Button title="Kuzatishni to'xtatish" color="#b91c1c" onPress={handleStopTracking} />
        )}
        <View style={styles.spacer} />
        <Button title="Chiqish" onPress={handleLogout} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#f8fafc",
  },
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    backgroundColor: "#f8fafc",
  },
  title: {
    fontSize: 22,
    fontWeight: "bold",
    marginBottom: 8,
    color: "#0f172a",
  },
  subtitle: {
    fontSize: 14,
    color: "#64748b",
    marginBottom: 16,
  },
  apiLabel: {
    fontSize: 12,
    color: "#94a3b8",
    marginBottom: 20,
  },
  driverName: {
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 12,
    color: "#1e3a8a",
  },
  status: {
    fontSize: 16,
    marginBottom: 8,
  },
  hint: {
    fontSize: 13,
    color: "#64748b",
    textAlign: "center",
    marginBottom: 24,
    paddingHorizontal: 12,
  },
  input: {
    width: "100%",
    maxWidth: 320,
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
    backgroundColor: "#fff",
  },
  actions: {
    width: "100%",
    maxWidth: 280,
  },
  spacer: {
    height: 12,
  },
});
