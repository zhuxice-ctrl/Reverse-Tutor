package com.reversetutor.app;

import android.Manifest;
import android.app.Activity;
import android.content.ClipData;
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
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;
import androidx.activity.result.ActivityResult;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

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
    private static final String RESULT_CHANNEL_ID = "background_llm_result_v4";

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
            android.app.Notification notification = new androidx.core.app.NotificationCompat.Builder(getContext(), RESULT_CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_stat_reverse_tutor)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new androidx.core.app.NotificationCompat.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setCategory(androidx.core.app.NotificationCompat.CATEGORY_MESSAGE)
                .setVisibility(androidx.core.app.NotificationCompat.VISIBILITY_PUBLIC)
                .setPriority(androidx.core.app.NotificationCompat.PRIORITY_HIGH)
                .setDefaults(androidx.core.app.NotificationCompat.DEFAULT_SOUND | androidx.core.app.NotificationCompat.DEFAULT_VIBRATE)
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

    @PluginMethod
    public void getNotificationStatus(PluginCall call) {
        ensureResultChannel();
        JSObject ret = new JSObject();
        ret.put("available", true);
        ret.put("notificationsEnabled", androidx.core.app.NotificationManagerCompat.from(getContext()).areNotificationsEnabled());
        ret.put("channelId", RESULT_CHANNEL_ID);

        if (Build.VERSION.SDK_INT >= 26) {
            android.app.NotificationManager mgr = (android.app.NotificationManager) getContext().getSystemService(Context.NOTIFICATION_SERVICE);
            android.app.NotificationChannel ch = mgr == null ? null : mgr.getNotificationChannel(RESULT_CHANNEL_ID);
            int importance = ch == null ? android.app.NotificationManager.IMPORTANCE_NONE : ch.getImportance();
            ret.put("channelImportance", importance);
            ret.put("channelBlocked", importance == android.app.NotificationManager.IMPORTANCE_NONE);
            ret.put("channelHighImportance", importance >= android.app.NotificationManager.IMPORTANCE_HIGH);
        } else {
            ret.put("channelImportance", android.app.NotificationManager.IMPORTANCE_HIGH);
            ret.put("channelBlocked", false);
            ret.put("channelHighImportance", true);
        }
        call.resolve(ret);
    }

    @PluginMethod
    public void openBackgroundNotificationSettings(PluginCall call) {
        try {
            ensureResultChannel();
            Intent intent;
            if (Build.VERSION.SDK_INT >= 26) {
                intent = new Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS);
                intent.putExtra(Settings.EXTRA_APP_PACKAGE, getContext().getPackageName());
                intent.putExtra(Settings.EXTRA_CHANNEL_ID, RESULT_CHANNEL_ID);
            } else {
                intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
                intent.setData(Uri.parse("package:" + getContext().getPackageName()));
            }
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            JSObject ret = new JSObject();
            ret.put("opened", true);
            ret.put("channelId", RESULT_CHANNEL_ID);
            call.resolve(ret);
        } catch (Exception e) {
            JSObject ret = new JSObject();
            ret.put("opened", false);
            ret.put("error", e.getMessage());
            call.resolve(ret);
        }
    }

    private void ensureResultChannel() {
        if (Build.VERSION.SDK_INT < 26) return;
        android.app.NotificationManager mgr = (android.app.NotificationManager) getContext().getSystemService(Context.NOTIFICATION_SERVICE);
        if (mgr == null) return;
        if (mgr.getNotificationChannel(RESULT_CHANNEL_ID) != null) return;
        android.app.NotificationChannel ch = new android.app.NotificationChannel(
            RESULT_CHANNEL_ID, "后台 LLM 回复", android.app.NotificationManager.IMPORTANCE_HIGH);
        ch.setDescription("后台 LLM 回复完成后弹出实际回复内容。");
        ch.enableVibration(true);
        mgr.createNotificationChannel(ch);
    }

    @PluginMethod
    public void requestNotificationPermission(PluginCall call) {
        ensureResultChannel();
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

    @PluginMethod
    public void shareJsonFile(PluginCall call) {
        String fileName = safeExportFileName(call.getString("fileName", "reverse-tutor-backup.json"));
        String content = call.getString("content", "");
        if (content == null || content.trim().isEmpty()) {
            call.reject("missing export content");
            return;
        }

        try {
            File exportDir = new File(getContext().getCacheDir(), "exports");
            if (!exportDir.exists() && !exportDir.mkdirs()) {
                call.reject("cannot create export directory");
                return;
            }
            File outFile = new File(exportDir, fileName);
            try (FileOutputStream fos = new FileOutputStream(outFile, false)) {
                fos.write(content.getBytes(StandardCharsets.UTF_8));
            }

            Uri uri = FileProvider.getUriForFile(
                getContext(),
                getContext().getPackageName() + ".fileprovider",
                outFile
            );
            Intent send = new Intent(Intent.ACTION_SEND);
            send.setType("application/json");
            send.putExtra(Intent.EXTRA_STREAM, uri);
            send.putExtra(Intent.EXTRA_SUBJECT, "反转家教数据备份");
            send.setClipData(ClipData.newUri(getContext().getContentResolver(), fileName, uri));
            send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);

            Intent chooser = Intent.createChooser(send, "导出反转家教数据");
            chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(chooser);

            JSObject ret = new JSObject();
            ret.put("shared", true);
            ret.put("fileName", fileName);
            call.resolve(ret);
        } catch (Exception e) {
            call.reject("share export failed", e);
        }
    }

    @PluginMethod
    public void saveJsonFile(PluginCall call) {
        String fileName = safeExportFileName(call.getString("fileName", "reverse-tutor-backup.json"));
        String content = call.getString("content", "");
        if (content == null || content.trim().isEmpty()) {
            call.reject("missing export content");
            return;
        }

        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json");
        intent.putExtra(Intent.EXTRA_TITLE, fileName);
        startActivityForResult(call, intent, "saveJsonFileResult");
    }

    @ActivityCallback
    private void saveJsonFileResult(PluginCall call, ActivityResult result) {
        if (call == null) {
            return;
        }
        if (result.getResultCode() != Activity.RESULT_OK || result.getData() == null || result.getData().getData() == null) {
            JSObject ret = new JSObject();
            ret.put("saved", false);
            ret.put("cancelled", true);
            call.resolve(ret);
            return;
        }

        String content = call.getString("content", "");
        Uri uri = result.getData().getData();
        try (OutputStream os = getContext().getContentResolver().openOutputStream(uri, "w")) {
            if (os == null) {
                call.reject("cannot open export destination");
                return;
            }
            os.write(content.getBytes(StandardCharsets.UTF_8));
            JSObject ret = new JSObject();
            ret.put("saved", true);
            call.resolve(ret);
        } catch (Exception e) {
            call.reject("save export failed", e);
        }
    }

    private String safeExportFileName(String raw) {
        String clean = raw == null ? "" : raw.trim().replaceAll("[^A-Za-z0-9._-]+", "-");
        if (clean.isEmpty()) {
            clean = "reverse-tutor-backup.json";
        }
        if (!clean.toLowerCase().endsWith(".json")) {
            clean = clean + ".json";
        }
        return clean;
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
