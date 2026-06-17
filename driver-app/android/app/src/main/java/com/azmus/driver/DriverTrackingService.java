package com.azmus.driver;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.location.Location;
import android.os.BatteryManager;
import android.os.Build;
import android.os.IBinder;
import android.os.Looper;
import androidx.core.app.NotificationCompat;
import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationCallback;
import com.google.android.gms.location.LocationRequest;
import com.google.android.gms.location.LocationResult;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.location.Priority;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONArray;
import org.json.JSONObject;

public class DriverTrackingService extends Service {

    public static final String ACTION_START = "com.azmus.driver.action.START";
    public static final String ACTION_STOP = "com.azmus.driver.action.STOP";
    public static final String PREFS = "azmus_driver_tracking";
    public static final String STATUS_KEY = "last_status_json";
    public static final String QUEUE_KEY = "offline_queue_json";

    private static final String CHANNEL_ID = "azmus_driver_gps";
    private static final int NOTIFICATION_ID = 88001;

    private FusedLocationProviderClient fusedClient;
    private LocationCallback locationCallback;
    private String plateNumber = "";
    private String driverName = "";

    @Override
    public void onCreate() {
        super.onCreate();
        fusedClient = LocationServices.getFusedLocationProviderClient(this);
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            stopTracking();
            stopSelf();
            return START_NOT_STICKY;
        }

        if (intent != null) {
            SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
            SharedPreferences.Editor editor = prefs.edit();
            if (intent.hasExtra("apiUrl")) editor.putString("api_url", intent.getStringExtra("apiUrl"));
            if (intent.hasExtra("token")) editor.putString("token", intent.getStringExtra("token"));
            if (intent.hasExtra("vehicleId")) editor.putInt("vehicle_id", intent.getIntExtra("vehicleId", 0));
            if (intent.hasExtra("driverId")) editor.putInt("driver_id", intent.getIntExtra("driverId", -1));
            plateNumber = intent.getStringExtra("plateNumber") != null ? intent.getStringExtra("plateNumber") : "";
            driverName = intent.getStringExtra("driverName") != null ? intent.getStringExtra("driverName") : "";
            editor.putBoolean("active", true);
            editor.apply();
        }

        startForeground(NOTIFICATION_ID, buildNotification("Starting GPS…"));
        startLocationUpdates();
        flushQueueAsync();
        return START_STICKY;
    }

    private void startLocationUpdates() {
        if (locationCallback != null) return;

        LocationRequest request =
            new LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 5000L)
                .setMinUpdateIntervalMillis(5000L)
                .setMinUpdateDistanceMeters(0f)
                .build();

        locationCallback =
            new LocationCallback() {
                @Override
                public void onLocationResult(LocationResult result) {
                    if (result == null || result.getLastLocation() == null) return;
                    handleLocation(result.getLastLocation());
                }
            };

        try {
            fusedClient.requestLocationUpdates(request, locationCallback, Looper.getMainLooper());
        } catch (SecurityException ignored) {
            updateNotification("Location permission denied");
        }
    }

    private void handleLocation(Location location) {
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        int vehicleId = prefs.getInt("vehicle_id", 0);
        if (vehicleId <= 0) return;

        int driverId = prefs.getInt("driver_id", -1);
        float speedKmh = location.getSpeed() >= 0 ? location.getSpeed() * 3.6f : 0f;
        float battery = readBatteryLevel();
        long now = System.currentTimeMillis();

        JSONObject payload = new JSONObject();
        try {
            payload.put("vehicle_id", vehicleId);
            if (driverId >= 0) payload.put("driver_id", driverId);
            payload.put("latitude", location.getLatitude());
            payload.put("longitude", location.getLongitude());
            payload.put("speed", speedKmh);
            payload.put("battery_level", battery);
        } catch (Exception ignored) {
            return;
        }

        boolean sent = postLocation(payload, prefs);
        int queued = queueSize(prefs);
        if (!sent) {
            enqueue(prefs, payload);
            queued = queueSize(prefs);
        } else {
            flushQueueAsync();
        }

        JSONObject status = new JSONObject();
        try {
            if (sent) {
                prefs.edit().putString("last_sent_iso", isoNow(now)).apply();
            }
            status.put("lastSent", sent ? isoNow(now) : prefs.getString("last_sent_iso", null));
            status.put("latitude", location.getLatitude());
            status.put("longitude", location.getLongitude());
            status.put("accuracy", location.getAccuracy());
            status.put("speed", speedKmh);
            status.put("battery", battery);
            status.put("queued", queued);
            prefs.edit().putString(STATUS_KEY, status.toString()).apply();
        } catch (Exception ignored) {
            // ignore
        }

        String label = plateNumber.isEmpty() ? "Azmus Driver" : plateNumber;
        updateNotification(label + " · " + Math.round(speedKmh) + " km/h · queue " + queued);
        DriverTrackingPlugin.notifyStatusFromService(this);
    }

    private boolean postLocation(JSONObject payload, SharedPreferences prefs) {
        String apiUrl = prefs.getString("api_url", "");
        String token = prefs.getString("token", "");
        if (apiUrl.isEmpty() || token.isEmpty()) return false;
        HttpURLConnection conn = null;
        try {
            URL url = new URL(apiUrl.replaceAll("/+$", "") + "/gps/location/update");
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(8000);
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Authorization", "Bearer " + token);
            conn.setDoOutput(true);
            byte[] bytes = payload.toString().getBytes("UTF-8");
            conn.setFixedLengthStreamingMode(bytes.length);
            OutputStream os = conn.getOutputStream();
            os.write(bytes);
            os.flush();
            os.close();
            int code = conn.getResponseCode();
            return code >= 200 && code < 300;
        } catch (Exception ignored) {
            return false;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private void enqueue(SharedPreferences prefs, JSONObject payload) {
        try {
            JSONArray queue = new JSONArray(prefs.getString(QUEUE_KEY, "[]"));
            queue.put(payload);
            if (queue.length() > 500) {
                JSONArray trimmed = new JSONArray();
                for (int i = queue.length() - 500; i < queue.length(); i++) trimmed.put(queue.get(i));
                queue = trimmed;
            }
            prefs.edit().putString(QUEUE_KEY, queue.toString()).apply();
        } catch (Exception ignored) {
            // ignore
        }
    }

    private int queueSize(SharedPreferences prefs) {
        try {
            return new JSONArray(prefs.getString(QUEUE_KEY, "[]")).length();
        } catch (Exception e) {
            return 0;
        }
    }

    private void flushQueueAsync() {
        new Thread(
                () -> {
                    SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
                    try {
                        JSONArray queue = new JSONArray(prefs.getString(QUEUE_KEY, "[]"));
                        JSONArray remaining = new JSONArray();
                        for (int i = 0; i < queue.length(); i++) {
                            JSONObject item = queue.getJSONObject(i);
                            if (!postLocation(item, prefs)) remaining.put(item);
                        }
                        prefs.edit().putString(QUEUE_KEY, remaining.toString()).apply();
                        DriverTrackingPlugin.notifyStatusFromService(this);
                    } catch (Exception ignored) {
                        // ignore
                    }
                })
            .start();
    }

    private float readBatteryLevel() {
        IntentFilter filter = new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
        Intent batteryStatus = registerReceiver(null, filter);
        if (batteryStatus == null) return -1f;
        int level = batteryStatus.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = batteryStatus.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
        if (level < 0 || scale <= 0) return -1f;
        return level * 100f / scale;
    }

    private void stopTracking() {
        if (locationCallback != null) {
            fusedClient.removeLocationUpdates(locationCallback);
            locationCallback = null;
        }
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean("active", false).apply();
        stopForeground(true);
    }

    @Override
    public void onDestroy() {
        stopTracking();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel =
                new NotificationChannel(CHANNEL_ID, "GPS Tracking", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Azmus Driver live location");
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(channel);
        }
    }

    private Notification buildNotification(String text) {
        Intent intent = new Intent(this, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pending =
            PendingIntent.getActivity(
                this, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return new NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Azmus Driver")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setOngoing(true)
            .setContentIntent(pending)
            .build();
    }

    private void updateNotification(String text) {
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) manager.notify(NOTIFICATION_ID, buildNotification(text));
    }

    private static String isoNow(long millis) {
        return new java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", java.util.Locale.US) {
            {
                setTimeZone(java.util.TimeZone.getTimeZone("UTC"));
            }
        }.format(new java.util.Date(millis));
    }
}
