package com.reversetutor.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.IBinder;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class BackgroundLlmService extends Service {
    static final String EXTRA_JOB_JSON = "job_json";
    // Completed jobs are stored under rt-native-background-llm-completed.
    private static final String CHANNEL_ID = "background_llm";
    private static final int RUNNING_NOTIFICATION_ID = 43100;

    @Override
    public void onCreate() {
        super.onCreate();
        ensureChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String jobJson = intent != null ? intent.getStringExtra(EXTRA_JOB_JSON) : null;
        if (jobJson == null || jobJson.trim().isEmpty()) {
            stopSelf(startId);
            return START_NOT_STICKY;
        }

        startForeground(
            RUNNING_NOTIFICATION_ID,
            buildNotification("LLM 正在回复", "退出应用后仍在继续生成当前回复。", true)
        );

        new Thread(() -> {
            try {
                JSONObject job = new JSONObject(jobJson);
                String rawContent = callOpenAi(job);
                storeCompleted(job, "success", rawContent, "");
                notifyFinished(job, "学生有新回复", "打开应用查看后台生成的回复。");
            } catch (Exception e) {
                try {
                    JSONObject job = new JSONObject(jobJson);
                    storeCompleted(job, "error", "", e.getMessage() == null ? e.toString() : e.getMessage());
                    notifyFinished(job, "后台回复失败", e.getMessage() == null ? "打开应用查看错误。" : e.getMessage());
                } catch (Exception ignored) {
                    notifyFinished(null, "后台回复失败", "任务数据无法读取。");
                }
            } finally {
                stopForeground(true);
                stopSelf(startId);
            }
        }, "background-llm").start();

        return START_NOT_STICKY;
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private String callOpenAi(JSONObject job) throws Exception {
        JSONObject payload = buildPayload(job, true);
        HttpResult first = post(job, payload);
        if (first.statusCode >= 400 && (first.statusCode == 400 || first.statusCode == 422)) {
            payload = buildPayload(job, false);
            first = post(job, payload);
        }
        if (first.statusCode < 200 || first.statusCode >= 300) {
            throw new Exception("LLM " + first.statusCode + ": " + first.body);
        }

        JSONObject data = new JSONObject(first.body);
        JSONObject choice = data.getJSONArray("choices").getJSONObject(0);
        JSONObject msg = choice.getJSONObject("message");
        String content = msg.optString("content", "");
        if (content.trim().isEmpty()) {
            content = msg.optString("reasoning_content", "");
        }
        if (content.trim().isEmpty()) {
            throw new Exception("LLM returned empty content. finish_reason=" + choice.optString("finish_reason", "unknown"));
        }
        return content;
    }

    private JSONObject buildPayload(JSONObject job, boolean jsonMode) throws Exception {
        JSONObject payload = new JSONObject();
        payload.put("model", job.optString("model", ""));
        payload.put("temperature", job.optDouble("temperature", 0.85));
        payload.put("max_tokens", job.optInt("max_tokens", 900));

        JSONArray messages = new JSONArray();
        JSONObject system = new JSONObject();
        system.put("role", "system");
        system.put("content", job.optString("system", ""));
        messages.put(system);

        JSONArray input = job.optJSONArray("messages");
        if (input != null) {
            for (int i = 0; i < input.length(); i++) {
                JSONObject item = input.optJSONObject(i);
                if (item != null) {
                    messages.put(item);
                }
            }
        }
        payload.put("messages", messages);

        if (jsonMode) {
            JSONObject responseFormat = new JSONObject();
            responseFormat.put("type", "json_object");
            payload.put("response_format", responseFormat);
        }
        return payload;
    }

    private HttpResult post(JSONObject job, JSONObject payload) throws Exception {
        String baseUrl = job.optString("base_url", "").replaceAll("/+$", "");
        URL url = new URL(baseUrl + "/chat/completions");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setConnectTimeout(20000);
        conn.setReadTimeout(90000);
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/json");
        String apiKey = job.optString("api_key", "");
        if (!apiKey.isEmpty()) {
            conn.setRequestProperty("Authorization", "Bearer " + apiKey);
        }

        byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
        try (OutputStream out = conn.getOutputStream()) {
            out.write(body);
        }

        int code = conn.getResponseCode();
        InputStream stream = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
        return new HttpResult(code, readStream(stream));
    }

    private String readStream(InputStream stream) throws Exception {
        if (stream == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
        }
        return sb.toString();
    }

    private void storeCompleted(JSONObject job, String status, String rawContent, String error) throws Exception {
        JSONObject item = new JSONObject();
        item.put("job_id", job.optString("job_id", ""));
        item.put("sid", job.optString("sid", ""));
        item.put("status", status);
        item.put("raw_content", rawContent);
        item.put("error", error);
        item.put("created_at", System.currentTimeMillis());

        SharedPreferences prefs = BackgroundLlmPlugin.prefs(this);
        JSONArray arr = BackgroundLlmPlugin.readCompleted(this);
        arr.put(item);
        prefs.edit().putString(BackgroundLlmPlugin.COMPLETED_KEY, arr.toString()).apply();
    }

    private void notifyFinished(JSONObject job, String title, String text) {
        try {
            Notification notification = buildNotification(title, text, false);
            int id = 43200 + Math.abs((job == null ? title : job.optString("job_id", title)).hashCode() % 1000);
            NotificationManagerCompat.from(this).notify(id, notification);
        } catch (Exception ignored) {
            // Notification permission may be denied; the stored result is still imported on next app open.
        }
    }

    private Notification buildNotification(String title, String text, boolean ongoing) {
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        PendingIntent pi = PendingIntent.getActivity(this, 0, open, flags);

        return new NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(getApplicationInfo().icon)
            .setContentTitle(title)
            .setContentText(text)
            .setOngoing(ongoing)
            .setContentIntent(pi)
            .setAutoCancel(!ongoing)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build();
    }

    private void ensureChannel() {
        if (Build.VERSION.SDK_INT < 26) {
            return;
        }
        NotificationChannel channel = new NotificationChannel(
            CHANNEL_ID,
            "后台 LLM 回复",
            NotificationManager.IMPORTANCE_DEFAULT
        );
        channel.setDescription("退出应用后继续生成当前 LLM 回复并提示结果");
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.createNotificationChannel(channel);
        }
    }

    private static class HttpResult {
        final int statusCode;
        final String body;

        HttpResult(int statusCode, String body) {
            this.statusCode = statusCode;
            this.body = body == null ? "" : body;
        }
    }
}
