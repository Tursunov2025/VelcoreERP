package com.azmus.erp;

import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import androidx.core.content.FileProvider;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.File;

@CapacitorPlugin(name = "AppUpdate")
public class AppUpdatePlugin extends Plugin {

    private Long pendingDownloadId = null;
    private BroadcastReceiver downloadReceiver;

    @Override
    public void load() {
        downloadReceiver =
            new BroadcastReceiver() {
                @Override
                public void onReceive(Context context, Intent intent) {
                    long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1);
                    if (pendingDownloadId == null || pendingDownloadId != id) {
                        return;
                    }
                    installDownloadedApk(id);
                }
            };
        IntentFilter filter = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            getContext().registerReceiver(downloadReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            getContext().registerReceiver(downloadReceiver, filter);
        }
    }

    @Override
    protected void handleOnDestroy() {
        if (downloadReceiver != null) {
            try {
                getContext().unregisterReceiver(downloadReceiver);
            } catch (Exception ignored) {
                // already unregistered
            }
        }
    }

    @PluginMethod
    public void downloadApk(PluginCall call) {
        String url = call.getString("url");
        if (url == null || url.isEmpty()) {
            call.reject("url required");
            return;
        }
        try {
            DownloadManager dm = (DownloadManager) getContext().getSystemService(Context.DOWNLOAD_SERVICE);
            DownloadManager.Request req = new DownloadManager.Request(Uri.parse(url));
            req.setMimeType("application/vnd.android.package-archive");
            req.setTitle("Azmus ERP");
            req.setDescription("Downloading update");
            req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            req.setDestinationInExternalFilesDir(
                getContext(),
                Environment.DIRECTORY_DOWNLOADS,
                "azmus-update.apk"
            );
            pendingDownloadId = dm.enqueue(req);
            JSObject ret = new JSObject();
            ret.put("downloadId", pendingDownloadId);
            call.resolve(ret);
        } catch (Exception e) {
            call.reject(e.getMessage());
        }
    }

    private void installDownloadedApk(long downloadId) {
        DownloadManager dm = (DownloadManager) getContext().getSystemService(Context.DOWNLOAD_SERVICE);
        DownloadManager.Query query = new DownloadManager.Query();
        query.setFilterById(downloadId);
        try (Cursor cursor = dm.query(query)) {
            if (!cursor.moveToFirst()) {
                return;
            }
            int uriIndex = cursor.getColumnIndex(DownloadManager.COLUMN_LOCAL_URI);
            if (uriIndex < 0) {
                uriIndex = cursor.getColumnIndex(DownloadManager.COLUMN_LOCAL_FILENAME);
            }
            if (uriIndex < 0) {
                return;
            }
            String local = cursor.getString(uriIndex);
            if (local == null || local.isEmpty()) {
                return;
            }
            Uri parsed = Uri.parse(local);
            if ("file".equals(parsed.getScheme())) {
                File file = new File(parsed.getPath());
                Uri contentUri =
                    FileProvider.getUriForFile(
                        getContext(),
                        getContext().getPackageName() + ".fileprovider",
                        file
                    );
                openInstallIntent(contentUri);
            } else {
                openInstallIntent(parsed);
            }
        } catch (Exception ignored) {
            // User can install from notification
        }
    }

    private void openInstallIntent(Uri uri) {
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(uri, "application/vnd.android.package-archive");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        getActivity().startActivity(intent);
    }
}
