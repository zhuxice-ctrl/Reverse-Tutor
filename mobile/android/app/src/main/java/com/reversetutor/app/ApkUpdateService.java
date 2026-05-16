package com.reversetutor.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.IBinder;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.FileProvider;

import org.json.JSONArray;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class ApkUpdateService extends Service {
    static final String EXTRA_URLS_JSON = "urls_json";
    static final String EXTRA_VERSION_NAME = "version_name";

    private static final String RUNNING_CHANNEL_ID = "app_update_download";
    private static final String RESULT_CHANNEL_ID = "app_update_result";
    private static final int RUNNING_NOTIFICATION_ID = 44100;
    private static final int RESULT_NOTIFICATION_ID = 44101;

    private long lastProgressNotifyAt = 0L;

    @Override
    public void onCreate() {
        super.onCreate();
        ensureChannels();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String urlsJson = intent == null ? "" : intent.getStringExtra(EXTRA_URLS_JSON);
        String versionName = intent == null ? "update" : intent.getStringExtra(EXTRA_VERSION_NAME);
        JSONArray urls = parseUrls(urlsJson);
        if (urls.length() == 0) {
            stopSelf(startId);
            return START_NOT_STICKY;
        }

        startForeground(
            RUNNING_NOTIFICATION_ID,
            buildProgressNotification("正在准备下载更新", 0L, 0L, true)
        );

        new Thread(() -> {
            try {
                File apkFile = downloadWithMirrors(urls, versionName);
                notifyReadyToInstall(apkFile, versionName);
                tryOpenInstaller(apkFile);
            } catch (Exception e) {
                notifyFailed(e.getMessage() == null ? e.toString() : e.getMessage());
            } finally {
                stopForeground(true);
                stopSelf(startId);
            }
        }, "apk-update-download").start();

        return START_REDELIVER_INTENT;
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private JSONArray parseUrls(String urlsJson) {
        try {
            return new JSONArray(urlsJson == null ? "[]" : urlsJson);
        } catch (Exception ignored) {
            return new JSONArray();
        }
    }

    private File downloadWithMirrors(JSONArray urls, String versionName) throws Exception {
        Exception last = null;
        for (int i = 0; i < urls.length(); i++) {
            String url = urls.optString(i, "").trim();
            if (url.isEmpty()) {
                continue;
            }
            try {
                return downloadApkFile(url, versionName);
            } catch (Exception e) {
                last = e;
                notifyProgressText("当前下载源失败，正在切换备用源");
            }
        }
        throw last == null ? new Exception("no apk url") : last;
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

        long total = Build.VERSION.SDK_INT >= 24 ? conn.getContentLengthLong() : conn.getContentLength();
        File updateDir = updateDir();
        String safeVersion = safeVersionName(versionName);
        File partFile = new File(updateDir, "reverse-tutor-" + safeVersion + ".apk.part");
        File apkFile = new File(updateDir, "reverse-tutor-" + safeVersion + ".apk");

        long received = 0L;
        try (InputStream in = conn.getInputStream(); FileOutputStream out = new FileOutputStream(partFile)) {
            byte[] buf = new byte[64 * 1024];
            int n;
            while ((n = in.read(buf)) >= 0) {
                if (n > 0) {
                    out.write(buf, 0, n);
                    received += n;
                    notifyProgress(received, total);
                }
            }
        } finally {
            conn.disconnect();
        }

        if (apkFile.exists() && !apkFile.delete()) {
            throw new Exception("cannot replace old apk");
        }
        if (!partFile.renameTo(apkFile)) {
            throw new Exception("cannot finalize apk");
        }
        return apkFile;
    }

    private File updateDir() throws Exception {
        File baseDir = getExternalCacheDir();
        if (baseDir == null) {
            baseDir = getCacheDir();
        }
        File updateDir = new File(baseDir, "updates");
        if (!updateDir.exists() && !updateDir.mkdirs()) {
            throw new Exception("cannot create update cache dir");
        }
        return updateDir;
    }

    private void notifyProgress(long received, long total) {
        long now = System.currentTimeMillis();
        if (now - lastProgressNotifyAt < 700) {
            return;
        }
        lastProgressNotifyAt = now;
        notifyRunning(buildProgressNotification(progressText(received, total), received, total, false));
    }

    private void notifyProgressText(String text) {
        notifyRunning(buildProgressNotification(text, 0L, 0L, true));
    }

    private String progressText(long received, long total) {
        if (total > 0) {
            int pct = Math.min(100, Math.round(received * 100f / total));
            return pct + "% · " + formatMb(received) + " / " + formatMb(total) + " MB";
        }
        return "已下载 " + formatMb(received) + " MB";
    }

    private String formatMb(long bytes) {
        return String.format(java.util.Locale.US, "%.1f", bytes / 1048576.0);
    }

    private Notification buildProgressNotification(String text, long received, long total, boolean indeterminate) {
        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, RUNNING_CHANNEL_ID)
            .setSmallIcon(getApplicationInfo().icon)
            .setContentTitle("正在后台下载更新")
            .setContentText(text)
            .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .setPriority(NotificationCompat.PRIORITY_LOW);

        if (indeterminate || total <= 0) {
            builder.setProgress(0, 0, true);
        } else {
            builder.setProgress(100, Math.min(100, Math.round(received * 100f / total)), false);
        }
        return builder.build();
    }

    private void notifyRunning(Notification notification) {
        try {
            NotificationManagerCompat.from(this).notify(RUNNING_NOTIFICATION_ID, notification);
        } catch (Exception ignored) {
            // The foreground service keeps running even if notification permission is denied.
        }
    }

    private void notifyReadyToInstall(File apkFile, String versionName) {
        Intent install = buildInstallIntent(apkFile);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        PendingIntent pi = PendingIntent.getActivity(this, 0, install, flags);
        String text = "下载完成，点击安装 " + (versionName == null || versionName.trim().isEmpty() ? "新版" : versionName);
        Notification notification = new NotificationCompat.Builder(this, RESULT_CHANNEL_ID)
            .setSmallIcon(getApplicationInfo().icon)
            .setContentTitle("更新包已下载")
            .setContentText(text)
            .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(pi)
            .setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_STATUS)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build();
        try {
            NotificationManagerCompat.from(this).notify(RESULT_NOTIFICATION_ID, notification);
        } catch (Exception ignored) {
            // Installation can still be opened directly when the system allows it.
        }
    }

    private void notifyFailed(String error) {
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        PendingIntent pi = PendingIntent.getActivity(this, 1, open, flags);
        String text = "下载失败：" + (error == null || error.trim().isEmpty() ? "网络或地址不可用" : error);
        Notification notification = new NotificationCompat.Builder(this, RESULT_CHANNEL_ID)
            .setSmallIcon(getApplicationInfo().icon)
            .setContentTitle("更新下载失败")
            .setContentText(text)
            .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
            .setContentIntent(pi)
            .setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_ERROR)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build();
        try {
            NotificationManagerCompat.from(this).notify(RESULT_NOTIFICATION_ID, notification);
        } catch (Exception ignored) {
            // Ignore notification failures.
        }
    }

    private Intent buildInstallIntent(File apkFile) {
        Uri uri = FileProvider.getUriForFile(
            this,
            getPackageName() + ".fileprovider",
            apkFile
        );
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(uri, "application/vnd.android.package-archive");
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        return intent;
    }

    private void tryOpenInstaller(File apkFile) {
        try {
            startActivity(buildInstallIntent(apkFile));
        } catch (Exception ignored) {
            // Android may block background activity starts; the notification remains as fallback.
        }
    }

    private String safeVersionName(String versionName) {
        String safe = (versionName == null ? "update" : versionName).replaceAll("[^A-Za-z0-9._-]+", "-");
        return safe.isEmpty() ? "update" : safe;
    }

    private void ensureChannels() {
        if (Build.VERSION.SDK_INT < 26) {
            return;
        }
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }

        NotificationChannel running = new NotificationChannel(
            RUNNING_CHANNEL_ID,
            "应用更新下载",
            NotificationManager.IMPORTANCE_LOW
        );
        running.setDescription("后台下载新版 APK。");

        NotificationChannel result = new NotificationChannel(
            RESULT_CHANNEL_ID,
            "应用更新结果",
            NotificationManager.IMPORTANCE_HIGH
        );
        result.setDescription("更新包下载完成或失败后的安装提示。");
        result.enableVibration(true);

        manager.createNotificationChannel(running);
        manager.createNotificationChannel(result);
    }
}
