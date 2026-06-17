package com.azmus.driver;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import org.json.JSONObject;

@CapacitorPlugin(name = "DriverTracking")
public class DriverTrackingPlugin extends Plugin {

    private static DriverTrackingPlugin instance;

    @Override
    public void load() {
        instance = this;
    }

    public static void notifyStatusFromService(android.content.Context context) {
        if (instance == null) return;
        try {
            SharedPreferences prefs = context.getSharedPreferences(DriverTrackingService.PREFS, android.content.Context.MODE_PRIVATE);
            String raw = prefs.getString(DriverTrackingService.STATUS_KEY, "{}");
            JSONObject obj = new JSONObject(raw);
            JSObject data = JSObject.fromJSONObject(obj);
            instance.notifyListeners("status", data);
        } catch (Exception ignored) {
            // ignore
        }
    }

    @PluginMethod
    public void startTrip(PluginCall call) {
        String apiUrl = call.getString("apiUrl");
        String token = call.getString("token");
        Integer vehicleId = call.getInt("vehicleId");
        if (apiUrl == null || token == null || vehicleId == null || vehicleId <= 0) {
            call.reject("apiUrl, token, and vehicleId required");
            return;
        }

        Intent intent = new Intent(getContext(), DriverTrackingService.class);
        intent.setAction(DriverTrackingService.ACTION_START);
        intent.putExtra("apiUrl", apiUrl);
        intent.putExtra("token", token);
        intent.putExtra("vehicleId", vehicleId);
        Integer driverId = call.getInt("driverId", -1);
        if (driverId != null && driverId >= 0) intent.putExtra("driverId", driverId);
        intent.putExtra("plateNumber", call.getString("plateNumber", ""));
        intent.putExtra("driverName", call.getString("driverName", ""));

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getContext().startForegroundService(intent);
        } else {
            getContext().startService(intent);
        }
        call.resolve();
    }

    @PluginMethod
    public void stopTrip(PluginCall call) {
        Intent intent = new Intent(getContext(), DriverTrackingService.class);
        intent.setAction(DriverTrackingService.ACTION_STOP);
        getContext().startService(intent);
        call.resolve();
    }

    @PluginMethod
    public void getStatus(PluginCall call) {
        try {
            SharedPreferences prefs =
                getContext().getSharedPreferences(DriverTrackingService.PREFS, android.content.Context.MODE_PRIVATE);
            String raw = prefs.getString(DriverTrackingService.STATUS_KEY, "{}");
            JSONObject obj = new JSONObject(raw);
            JSObject data = JSObject.fromJSONObject(obj);
            data.put("active", prefs.getBoolean("active", false));
            try {
                data.put("queued", new org.json.JSONArray(prefs.getString(DriverTrackingService.QUEUE_KEY, "[]")).length());
            } catch (Exception e) {
                data.put("queued", 0);
            }
            call.resolve(data);
        } catch (Exception e) {
            call.reject(e.getMessage());
        }
    }
}
