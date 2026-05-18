package com.reversetutor.app;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.ContextCompat;

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
    public void showResultNotification(PluginCall call) {
        String title = call.getString("title", "反转家教");
        String body = call.getString("body", "");
        if (body.isEmpty()) {
            call.resolve(new JSObject());
            return;
        }
        try {
            ensureResultChannel();
            android.app.Notification notification = new androidx.core.app.NotificationCompat.Builder(getContext(), "background_llm_result_v2")
                .setSmallIcon(getContext().getApplicationInfo().icon)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new androidx.core.app.NotificationCompat.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setCategory(androidx.core.app.NotificationCompat.CATEGORY_MESSAGE)
                .setVisibility(androidx.core.app.NotificationCompat.VISIBILITY_PUBLIC)
                .setPriority(androidx.core.app.NotificationCompat.PRIORITY_HIGH)
                .build();
            int id = 43300 + Math.abs(body.hashCode() % 500);
            androidx.core.app.NotificationManagerCompat.from(getContext()).notify(id, notification);
            JSObject ret = new JSObject();
            ret.put("shown", true);
            call.resolve(ret);
        } catch (Exception e) {
            JSObject ret = new JSObject();
            ret.put("shown", false);
            ret.put("error", e.getMessage());
            call.resolve(ret);
        }
    }

    private void ensureResultChannel() {
        if (Build.VERSION.SDK_INT < 26) return;
        android.app.NotificationManager mgr = (android.app.NotificationManager) getContext().getSystemService(Context.NOTIFICATION_SERVICE);
        if (mgr == null) return;
        if (mgr.getNotificationChannel("background_llm_result_v2") != null) return;
        android.app.NotificationChannel ch = new android.app.NotificationChannel(
            "background_llm_result_v2", "后台 LLM 回复", android.app.NotificationManager.IMPORTANCE_HIGH);
        ch.setDescription("后台 LLM 回复完成后弹出实际回复内容。");
        ch.enableVibration(true);
        mgr.createNotificationChannel(ch);
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
        JSObject data = call.getData();
        JSONArray urls = normalizeApkUrls(data == null ? null : data.optJSONArray("urls"), call.getString("url", ""));
        String versionName = call.getString("versionName", "update");
        if (urls.length() == 0) {
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

        Intent intent = new Intent(getContext(), ApkUpdateService.class);
        intent.putExtra(ApkUpdateService.EXTRA_URLS_JSON, urls.toString());
        intent.putExtra(ApkUpdateService.EXTRA_VERSION_NAME, versionName);
        ContextCompat.startForegroundService(getContext(), intent);

        JSObject ret = new JSObject();
        ret.put("opened", false);
        ret.put("queued", true);
        ret.put("background", true);
        ret.put("urlCount", urls.length());
        call.resolve(ret);
    }

    private JSONArray normalizeApkUrls(JSONArray rawUrls, String fallbackUrl) {
        JSONArray out = new JSONArray();
        appendApkUrl(out, fallbackUrl);
        if (rawUrls != null) {
            for (int i = 0; i < rawUrls.length(); i++) {
                appendApkUrl(out, rawUrls.optString(i, ""));
            }
        }
        return out;
    }

    private void appendApkUrl(JSONArray out, String url) {
        String clean = url == null ? "" : url.trim();
        if (clean.isEmpty()) {
            return;
        }
        for (int i = 0; i < out.length(); i++) {
            if (clean.equals(out.optString(i))) {
                return;
            }
        }
        out.put(clean);
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
