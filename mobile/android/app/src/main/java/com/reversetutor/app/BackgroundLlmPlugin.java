package com.reversetutor.app;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

@CapacitorPlugin(
    name = "BackgroundLlm",
    permissions = {
        @Permission(alias = "notifications", strings = { Manifest.permission.POST_NOTIFICATIONS })
    }
)
public class BackgroundLlmPlugin extends Plugin {
    static final String PREFS_NAME = "BackgroundLlm";
    static final String COMPLETED_KEY = "rt-native-background-llm-completed";
    static final String PENDING_KEY = "rt-native-background-llm-pending";

    @PluginMethod
    public void isAvailable(PluginCall call) {
        JSObject ret = new JSObject();
        ret.put("available", true);
        call.resolve(ret);
    }

    @PluginMethod
    public void requestNotificationPermission(PluginCall call) {
        if (Build.VERSION.SDK_INT < 33) {
            resolveNotificationPermission(call, true, false);
            return;
        }

        if (getPermissionState("notifications") == PermissionState.GRANTED) {
            resolveNotificationPermission(call, true, false);
            return;
        }

        requestPermissionForAlias("notifications", call, "notificationPermissionCallback");
    }

    @PermissionCallback
    private void notificationPermissionCallback(PluginCall call) {
        boolean granted = getPermissionState("notifications") == PermissionState.GRANTED;
        resolveNotificationPermission(call, granted, true);
    }

    private void resolveNotificationPermission(PluginCall call, boolean granted, boolean requested) {
        JSObject ret = new JSObject();
        ret.put("granted", granted);
        ret.put("requested", requested);
        call.resolve(ret);
    }

    @PluginMethod
    public void enqueueTurn(PluginCall call) {
        JSObject data = call.getData();
        if (data == null || !data.has("job_id") || !data.has("sid")) {
            call.reject("missing job_id or sid");
            return;
        }

        try {
            storePending(getContext(), new JSONObject(data.toString()));
        } catch (Exception e) {
            call.reject("pending turn cache failed", e);
            return;
        }

        Intent intent = new Intent(getContext(), BackgroundLlmService.class);
        intent.putExtra(BackgroundLlmService.EXTRA_JOB_JSON, data.toString());
        ContextCompat.startForegroundService(getContext(), intent);

        JSObject ret = new JSObject();
        ret.put("queued", true);
        ret.put("job_id", data.optString("job_id"));
        call.resolve(ret);
    }

    @PluginMethod
    public void getCompletedTurns(PluginCall call) {
        JSONArray arr = readCompleted(getContext());
        JSObject ret = new JSObject();
        try {
            ret.put("jobs", new JSArray(arr.toString()));
            call.resolve(ret);
        } catch (Exception e) {
            call.reject("completed turns decode failed", e);
        }
    }

    @PluginMethod
    public void clearCompletedTurn(PluginCall call) {
        String jobId = call.getString("job_id", "");
        JSONArray current = readCompleted(getContext());
        JSONArray kept = new JSONArray();
        for (int i = 0; i < current.length(); i++) {
            JSONObject item = current.optJSONObject(i);
            if (item == null || jobId.equals(item.optString("job_id"))) {
                continue;
            }
            kept.put(item);
        }
        prefs(getContext()).edit().putString(COMPLETED_KEY, kept.toString()).apply();
        JSObject ret = new JSObject();
        ret.put("ok", true);
        call.resolve(ret);
    }

    @PluginMethod
    public void downloadAndInstallApk(PluginCall call) {
        String url = call.getString("url", "");
        String versionName = call.getString("versionName", "update");
        if (url.trim().isEmpty()) {
            call.reject("missing apk url");
            return;
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !getContext().getPackageManager().canRequestPackageInstalls()) {
            Intent settings = new Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:" + getContext().getPackageName())
            );
            settings.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(settings);

            JSObject ret = new JSObject();
            ret.put("opened", false);
            ret.put("permissionRequired", true);
            ret.put("openedSettings", true);
            call.resolve(ret);
            return;
        }

        new Thread(() -> {
            try {
                File apkFile = downloadApkFile(url, versionName);
                openApkInstaller(apkFile);

                JSObject ret = new JSObject();
                ret.put("opened", true);
                ret.put("path", apkFile.getAbsolutePath());
                call.resolve(ret);
            } catch (Exception e) {
                call.reject("apk download or install failed", e);
            }
        }, "apk-download-install").start();
    }

    private File downloadApkFile(String urlString, String versionName) throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(urlString).openConnection();
        conn.setInstanceFollowRedirects(true);
        conn.setConnectTimeout(20000);
        conn.setReadTimeout(120000);
        conn.setRequestMethod("GET");

        int status = conn.getResponseCode();
        if (status < 200 || status >= 300) {
            throw new Exception("HTTP " + status);
        }

        File baseDir = getContext().getExternalCacheDir();
        if (baseDir == null) {
            baseDir = getContext().getCacheDir();
        }
        File updateDir = new File(baseDir, "updates");
        if (!updateDir.exists() && !updateDir.mkdirs()) {
            throw new Exception("cannot create update cache dir");
        }

        File apkFile = new File(updateDir, "reverse-tutor-" + safeVersionName(versionName) + ".apk");
        try (InputStream in = conn.getInputStream(); FileOutputStream out = new FileOutputStream(apkFile)) {
            byte[] buf = new byte[64 * 1024];
            int n;
            while ((n = in.read(buf)) >= 0) {
                if (n > 0) {
                    out.write(buf, 0, n);
                }
            }
        } finally {
            conn.disconnect();
        }
        return apkFile;
    }

    private String safeVersionName(String versionName) {
        String safe = (versionName == null ? "update" : versionName).replaceAll("[^A-Za-z0-9._-]+", "-");
        return safe.isEmpty() ? "update" : safe;
    }

    private void openApkInstaller(File apkFile) {
        Uri uri = FileProvider.getUriForFile(
            getContext(),
            getContext().getPackageName() + ".fileprovider",
            apkFile
        );
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(uri, "application/vnd.android.package-archive");
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        getContext().startActivity(intent);
    }

    static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    static JSONArray readCompleted(Context context) {
        try {
            return new JSONArray(prefs(context).getString(COMPLETED_KEY, "[]"));
        } catch (Exception e) {
            return new JSONArray();
        }
    }

    static void storePending(Context context, JSONObject job) {
        JSONArray current = readPending(context);
        JSONArray kept = new JSONArray();
        String jobId = job.optString("job_id", "");
        for (int i = 0; i < current.length(); i++) {
            JSONObject item = current.optJSONObject(i);
            if (item != null && !jobId.equals(item.optString("job_id"))) {
                kept.put(item);
            }
        }
        kept.put(job);
        prefs(context).edit().putString(PENDING_KEY, kept.toString()).apply();
    }

    static JSONArray readPending(Context context) {
        try {
            return new JSONArray(prefs(context).getString(PENDING_KEY, "[]"));
        } catch (Exception e) {
            return new JSONArray();
        }
    }
}
