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
import android.os.PowerManager;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.SocketException;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class BackgroundLlmService extends Service {
    static final String EXTRA_JOB_JSON = "job_json";
    // Completed jobs are stored under rt-native-background-llm-completed.
    private static final String RUNNING_CHANNEL_ID = "background_llm_running";
    private static final String RESULT_CHANNEL_ID = "background_llm_result_v4";
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
            jobJson = readPending();
            if (jobJson == null || jobJson.trim().isEmpty()) {
                stopSelf(startId);
                return START_NOT_STICKY;
            }
        }

        startForeground(
            RUNNING_NOTIFICATION_ID,
            buildNotification("LLM 正在回复", "退出应用后仍在继续生成当前回复。", true)
        );

        final String finalJobJson = jobJson;
        new Thread(() -> {
            PowerManager.WakeLock wakeLock = acquireBackgroundWakeLock();
            boolean keepForegroundNotification = false;
            try {
                JSONObject job = new JSONObject(finalJobJson);
                String rawContent = callOpenAi(job);
                storeCompleted(job, "success", rawContent, "");
                clearPending(job);
                String replyPreview = replyPreviewFromRawContent(rawContent);
                keepForegroundNotification = notifyFinished(job, "学生有新回复", replyPreview.isEmpty() ? "后台回复已生成。" : replyPreview);
            } catch (Exception e) {
                try {
                    JSONObject job = new JSONObject(finalJobJson);
                    storeCompleted(job, "error", "", e.getMessage() == null ? e.toString() : e.getMessage());
                    clearPending(job);
                    keepForegroundNotification = notifyFinished(job, "后台回复失败", e.getMessage() == null ? "打开应用查看错误。" : e.getMessage());
                } catch (Exception ignored) {
                    keepForegroundNotification = notifyFinished(null, "后台回复失败", "任务数据无法读取。");
                }
            } finally {
                if (wakeLock != null && wakeLock.isHeld()) {
                    wakeLock.release();
                }
                finishForegroundNotification(keepForegroundNotification);
                stopSelf(startId);
            }
        }, "background-llm").start();

        return START_REDELIVER_INTENT;
    }

    private PowerManager.WakeLock acquireBackgroundWakeLock() {
        try {
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            if (pm == null) {
                return null;
            }
            PowerManager.WakeLock wakeLock = pm.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                "ReverseTutor:BackgroundLlm"
            );
            wakeLock.setReferenceCounted(false);
            wakeLock.acquire(3 * 60 * 1000L);
            return wakeLock;
        } catch (Exception e) {
            return null;
        }
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private String callOpenAi(JSONObject job) throws Exception {
        if (isAnthropic(job)) {
            return callAnthropic(job);
        }

        JSONObject payload = buildPayload(job, true);
        HttpResult first = post(job, payload);
        if (first.statusCode >= 400 && (first.statusCode == 400 || first.statusCode == 422)) {
            payload = buildPayload(job, false);
            first = post(job, payload);
        }
        if (first.statusCode < 200 || first.statusCode >= 300) {
            throw new Exception("LLM " + first.statusCode + ": " + first.body);
        }

        String content = contentFromResponse(first.body);
        String extracted = extractJsonObject(content);
        if (extracted != null) {
            return extracted;
        }

        JSONObject retryPayload = buildPayload(job, false, strictJsonSystem(job), Math.min(job.optDouble("temperature", 0.85), 0.3));
        HttpResult retry = post(job, retryPayload);
        if (retry.statusCode < 200 || retry.statusCode >= 300) {
            throw new Exception("LLM retry " + retry.statusCode + ": " + retry.body);
        }
        String retryContent = contentFromResponse(retry.body);
        extracted = extractJsonObject(retryContent);
        if (extracted != null) {
            return extracted;
        }

        String fallback = fallbackReplyJson(retryContent);
        if (fallback != null) {
            return fallback;
        }

        throw new Exception(
            "LLM did not return valid JSON after background retry: first="
                + preview(content)
                + "; retry="
                + preview(retryContent)
        );
    }

    private String callAnthropic(JSONObject job) throws Exception {
        JSONObject payload = buildAnthropicPayload(job, job.optString("system", ""), job.optDouble("temperature", 0.85));
        HttpResult first = postAnthropic(job, payload);
        if (first.statusCode < 200 || first.statusCode >= 300) {
            throw new Exception("LLM " + first.statusCode + ": " + first.body);
        }

        String content = contentFromAnthropicResponse(first.body);
        String extracted = extractJsonObject(content);
        if (extracted != null) {
            return extracted;
        }

        JSONObject retryPayload = buildAnthropicPayload(
            job,
            strictJsonSystem(job),
            Math.min(job.optDouble("temperature", 0.85), 0.3)
        );
        HttpResult retry = postAnthropic(job, retryPayload);
        if (retry.statusCode < 200 || retry.statusCode >= 300) {
            throw new Exception("LLM retry " + retry.statusCode + ": " + retry.body);
        }
        String retryContent = contentFromAnthropicResponse(retry.body);
        extracted = extractJsonObject(retryContent);
        if (extracted != null) {
            return extracted;
        }

        String fallback = fallbackReplyJson(retryContent);
        if (fallback != null) {
            return fallback;
        }

        throw new Exception(
            "LLM did not return valid JSON after background retry: first="
                + preview(content)
                + "; retry="
                + preview(retryContent)
        );
    }

    private boolean isAnthropic(JSONObject job) {
        return "anthropic".equalsIgnoreCase(job.optString("api_type", ""));
    }

    private boolean isMiniMax(JSONObject job) {
        String provider = job.optString("provider", "").toLowerCase();
        String baseUrl = job.optString("base_url", "").toLowerCase();
        String model = job.optString("model", "").toLowerCase();
        return provider.startsWith("minimax")
            || baseUrl.contains("api.minimax.io")
            || model.startsWith("minimax-");
    }

    private boolean isStrictOpenAiCompatible(JSONObject job) {
        String provider = job.optString("provider", "").toLowerCase();
        String baseUrl = job.optString("base_url", "").toLowerCase();
        String model = job.optString("model", "").toLowerCase();
        return provider.equals("glm")
            || provider.equals("deepseek")
            || provider.startsWith("minimax")
            || provider.equals("qwen")
            || provider.equals("kimi")
            || provider.equals("kimi-global")
            || provider.equals("trial")
            || baseUrl.contains("open.bigmodel.cn")
            || baseUrl.contains("api.deepseek.com")
            || baseUrl.contains("api.minimax.io")
            || baseUrl.contains("dashscope.aliyuncs.com")
            || baseUrl.contains("api.moonshot.cn")
            || baseUrl.contains("api.moonshot.ai")
            || model.startsWith("glm-")
            || model.startsWith("qwen-")
            || model.startsWith("moonshot-")
            || model.startsWith("minimax-")
            || model.startsWith("deepseek-");
    }

    private double providerTemperature(JSONObject job, double temperature) {
        if (!isMiniMax(job)) {
            return temperature;
        }
        if (temperature <= 0) {
            return 0.01;
        }
        return Math.min(1.0, temperature);
    }

    private JSONObject buildPayload(JSONObject job, boolean jsonMode) throws Exception {
        return buildPayload(job, jsonMode, job.optString("system", ""), job.optDouble("temperature", 0.85));
    }

    private String contentText(Object content) {
        if (content == null || JSONObject.NULL.equals(content)) {
            return "";
        }
        if (content instanceof JSONArray) {
            JSONArray arr = (JSONArray) content;
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < arr.length(); i++) {
                JSONObject part = arr.optJSONObject(i);
                if (part == null) {
                    continue;
                }
                String type = part.optString("type", "");
                String text = "text".equals(type)
                    ? part.optString("text", "")
                    : ("image_url".equals(type) ? "[图片]" : part.optString("content", ""));
                if (!text.isEmpty()) {
                    if (sb.length() > 0) {
                        sb.append("\n");
                    }
                    sb.append(text);
                }
            }
            return sb.toString();
        }
        return String.valueOf(content);
    }

    private JSONArray buildOpenAiMessages(JSONObject job, String systemText) throws Exception {
        StringBuilder systemParts = new StringBuilder(systemText == null ? "" : systemText.trim());
        JSONArray messages = new JSONArray();
        int nonSystemCount = 0;

        JSONArray input = job.optJSONArray("messages");
        if (input != null) {
            for (int i = 0; i < input.length(); i++) {
                JSONObject item = input.optJSONObject(i);
                if (item == null) {
                    continue;
                }
                String role = item.optString("role", "user");
                Object content = item.opt("content");
                String text = contentText(content).trim();
                if (text.isEmpty()) {
                    continue;
                }
                if ("system".equals(role)) {
                    if (systemParts.length() > 0) {
                        systemParts.append("\n\n");
                    }
                    systemParts.append(text);
                    continue;
                }
                JSONObject msg = new JSONObject();
                msg.put("role", "assistant".equals(role) ? "assistant" : "user");
                msg.put("content", content);
                messages.put(msg);
                nonSystemCount += 1;
            }
        }

        JSONArray normalized = new JSONArray();
        if (systemParts.length() > 0) {
            JSONObject system = new JSONObject();
            system.put("role", "system");
            system.put("content", systemParts.toString());
            normalized.put(system);
        }
        for (int i = 0; i < messages.length(); i++) {
            normalized.put(messages.getJSONObject(i));
        }
        if (nonSystemCount == 0) {
            JSONObject msg = new JSONObject();
            msg.put("role", "user");
            msg.put("content", "开始吧");
            normalized.put(msg);
        }
        return normalized;
    }

    private JSONObject buildPayload(JSONObject job, boolean jsonMode, String systemText, double temperature) throws Exception {
        JSONObject payload = new JSONObject();
        payload.put("model", job.optString("model", ""));
        payload.put("temperature", providerTemperature(job, temperature));
        if (isMiniMax(job)) {
            payload.put("max_completion_tokens", job.optInt("max_tokens", 900));
        } else {
            payload.put("max_tokens", job.optInt("max_tokens", 900));
        }

        payload.put("messages", buildOpenAiMessages(job, systemText));

        if (jsonMode && !isStrictOpenAiCompatible(job)) {
            JSONObject responseFormat = new JSONObject();
            responseFormat.put("type", "json_object");
            payload.put("response_format", responseFormat);
        }
        return payload;
    }

    private JSONObject buildAnthropicPayload(JSONObject job, String systemText, double temperature) throws Exception {
        JSONObject payload = new JSONObject();
        payload.put("model", job.optString("model", ""));
        payload.put("temperature", providerTemperature(job, temperature));
        payload.put("max_tokens", job.optInt("max_tokens", 900));

        StringBuilder system = new StringBuilder(systemText == null ? "" : systemText);
        JSONArray messages = new JSONArray();
        JSONArray input = job.optJSONArray("messages");
        if (input != null) {
            for (int i = 0; i < input.length(); i++) {
                JSONObject item = input.optJSONObject(i);
                if (item == null) {
                    continue;
                }
                String role = item.optString("role", "user");
                String content = contentAsText(item.opt("content")).trim();
                if (content.isEmpty()) {
                    continue;
                }
                if ("system".equals(role)) {
                    if (system.length() > 0) {
                        system.append("\n\n");
                    }
                    system.append(content);
                    continue;
                }
                JSONObject msg = new JSONObject();
                msg.put("role", "assistant".equals(role) ? "assistant" : "user");
                msg.put("content", content);
                messages.put(msg);
            }
        }
        if (messages.length() == 0) {
            JSONObject msg = new JSONObject();
            msg.put("role", "user");
            msg.put("content", "ping");
            messages.put(msg);
        }

        payload.put("system", system.toString());
        payload.put("messages", messages);
        return payload;
    }

    private String contentAsText(Object content) {
        if (content == null || JSONObject.NULL.equals(content)) {
            return "";
        }
        if (content instanceof String) {
            return (String) content;
        }
        if (content instanceof JSONArray) {
            JSONArray arr = (JSONArray) content;
            StringBuilder out = new StringBuilder();
            for (int i = 0; i < arr.length(); i++) {
                JSONObject part = arr.optJSONObject(i);
                if (part == null) {
                    continue;
                }
                String type = part.optString("type", "");
                String text = "text".equals(type) ? part.optString("text", "") : "";
                if (!text.trim().isEmpty()) {
                    if (out.length() > 0) {
                        out.append("\n");
                    }
                    out.append(text.trim());
                }
            }
            return out.toString();
        }
        return String.valueOf(content);
    }

    private String strictJsonSystem(JSONObject job) {
        return job.optString("system", "")
            + "\n\nIMPORTANT: Return only one valid JSON object. Do not use markdown, comments, <think> tags, "
            + "or explanations before/after the JSON. Start with { and end with }.";
    }

    private String contentFromResponse(String body) throws Exception {
        JSONObject data = new JSONObject(body);
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

    private String contentFromAnthropicResponse(String body) throws Exception {
        JSONObject data = new JSONObject(body);
        StringBuilder out = new StringBuilder();
        Object content = data.opt("content");
        if (content instanceof String) {
            out.append((String) content);
        } else if (content instanceof JSONArray) {
            JSONArray arr = (JSONArray) content;
            for (int i = 0; i < arr.length(); i++) {
                JSONObject item = arr.optJSONObject(i);
                if (item == null) {
                    continue;
                }
                String text = item.optString("text", "");
                if (text.trim().isEmpty()) {
                    text = item.optString("content", "");
                }
                if (!text.trim().isEmpty()) {
                    if (out.length() > 0) {
                        out.append("\n");
                    }
                    out.append(text.trim());
                }
            }
        }
        if (out.length() == 0 && !data.optString("completion", "").trim().isEmpty()) {
            out.append(data.optString("completion", ""));
        }
        if (out.toString().trim().isEmpty()) {
            throw new Exception("LLM returned empty anthropic content. stop_reason=" + data.optString("stop_reason", "unknown"));
        }
        return out.toString();
    }

    private String extractJsonObject(String raw) {
        String s = normalizeJsonText(raw);
        String parsed = parseObjectOrNull(s);
        if (parsed != null) return parsed;

        int first = s.indexOf('{');
        int last = s.lastIndexOf('}');
        if (first >= 0 && last > first) {
            parsed = parseObjectOrNull(s.substring(first, last + 1));
            if (parsed != null) return parsed;
        }

        String balanced = firstBalancedJsonObject(s, first);
        if (balanced != null) {
            parsed = parseObjectOrNull(balanced);
            if (parsed != null) return parsed;
        }
        return null;
    }

    private String normalizeJsonText(String raw) {
        String s = raw == null ? "" : raw.trim();
        s = Pattern.compile("<think>[\\s\\S]*?</think>", Pattern.CASE_INSENSITIVE).matcher(s).replaceAll("").trim();
        Matcher fence = Pattern.compile("```(?:json)?\\s*([\\s\\S]*?)```", Pattern.CASE_INSENSITIVE).matcher(s);
        if (fence.find()) {
            s = fence.group(1).trim();
        }
        return s;
    }

    private String parseObjectOrNull(String candidate) {
        String[] variants = new String[] {
            candidate == null ? "" : candidate.trim(),
            removeTrailingCommas(candidate == null ? "" : candidate.trim())
        };
        for (String variant : variants) {
            try {
                return new JSONObject(variant).toString();
            } catch (Exception ignored) {
                // Try the next variant.
            }
        }
        return null;
    }

    private String removeTrailingCommas(String s) {
        return s.replaceAll(",(\\s*[}\\]])", "$1");
    }

    private String firstBalancedJsonObject(String s, int first) {
        if (first < 0) return null;
        int depth = 0;
        boolean inString = false;
        boolean escaped = false;
        for (int i = first; i < s.length(); i++) {
            char ch = s.charAt(i);
            if (inString) {
                if (escaped) {
                    escaped = false;
                } else if (ch == '\\') {
                    escaped = true;
                } else if (ch == '"') {
                    inString = false;
                }
                continue;
            }
            if (ch == '"') {
                inString = true;
            } else if (ch == '{') {
                depth += 1;
            } else if (ch == '}') {
                depth -= 1;
                if (depth == 0) {
                    return s.substring(first, i + 1);
                }
            }
        }
        return null;
    }

    private String preview(String s) {
        String compact = (s == null ? "" : s).replaceAll("\\s+", " ").trim();
        return compact.length() > 180 ? compact.substring(0, 180) : compact;
    }

    private String replyPreviewFromRawContent(String rawContent) {
        try {
            JSONObject root = new JSONObject(rawContent == null ? "{}" : rawContent);
            String reply = root.optString("reply", "");
            if (!reply.trim().isEmpty()) {
                return preview(reply);
            }
        } catch (Exception ignored) {
            // Fall through to plain-text extraction for non-JSON fallback content.
        }
        return preview(extractReplyText(rawContent));
    }

    private String fallbackReplyJson(String raw) {
        String reply = extractReplyText(raw);
        if (reply.isEmpty()) {
            return null;
        }
        try {
            JSONObject root = new JSONObject();
            JSONObject evaluation = new JSONObject();
            evaluation.put("correctness", 0);
            evaluation.put("depth", 0);
            evaluation.put("user_emotion", "unknown");
            evaluation.put("new_requirements", new JSONArray());

            JSONObject action = new JSONObject();
            action.put("type", "ask");
            action.put("knowledge_point", "后台回复");
            action.put("difficulty", 0.5);
            action.put("note", "background_fallback");

            root.put("evaluation", evaluation);
            root.put("action", action);
            root.put("reply", reply);
            root.put("anchor_updates", new JSONArray());
            return root.toString();
        } catch (Exception e) {
            return null;
        }
    }

    private String extractReplyText(String raw) {
        String s = raw == null ? "" : raw.trim();
        s = Pattern.compile("<think>[\\s\\S]*?</think>", Pattern.CASE_INSENSITIVE).matcher(s).replaceAll("").trim();
        Matcher fence = Pattern.compile("```(?:json|text|markdown|md)?\\s*([\\s\\S]*?)```", Pattern.CASE_INSENSITIVE).matcher(s);
        if (fence.find()) {
            s = fence.group(1).trim();
        }
        s = s.replaceAll("^\\s*(回复|reply|学生回复|assistant)\\s*[:：]\\s*", "").trim();
        s = s.replaceAll("\\s+", " ").trim();
        if (s.startsWith("{") || s.startsWith("[")) {
            return "";
        }
        return s.length() > 1200 ? s.substring(0, 1200) : s;
    }

    private HttpResult post(JSONObject job, JSONObject payload) throws Exception {
        return postWithRetry(job, payload, false);
    }

    private HttpResult postAnthropic(JSONObject job, JSONObject payload) throws Exception {
        return postWithRetry(job, payload, true);
    }

    private HttpResult postWithRetry(JSONObject job, JSONObject payload, boolean anthropic) throws Exception {
        IOException last = null;
        for (int attempt = 0; attempt < 3; attempt++) {
            try {
                return anthropic ? postAnthropicOnce(job, payload) : postOpenAiOnce(job, payload);
            } catch (IOException e) {
                last = e;
                if (!isTransientNetworkError(e) || attempt >= 2) {
                    throw e;
                }
                sleepBeforeRetry(attempt);
            }
        }
        throw last == null ? new IOException("background llm network retry failed") : last;
    }

    private boolean isTransientNetworkError(IOException e) {
        String message = String.valueOf(e.getMessage()).toLowerCase();
        return e instanceof SocketException
            || e instanceof SocketTimeoutException
            || message.contains("connection abort")
            || message.contains("connection reset")
            || message.contains("unexpected end of stream")
            || message.contains("timeout");
    }

    private void sleepBeforeRetry(int attempt) {
        try {
            Thread.sleep(650L * (attempt + 1));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private HttpResult postOpenAiOnce(JSONObject job, JSONObject payload) throws Exception {
        String baseUrl = job.optString("base_url", "").replaceAll("/+$", "");
        URL url = new URL(baseUrl.endsWith("/chat/completions") ? baseUrl : baseUrl + "/chat/completions");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        try {
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
        } finally {
            conn.disconnect();
        }
    }

    private HttpResult postAnthropicOnce(JSONObject job, JSONObject payload) throws Exception {
        String baseUrl = job.optString("base_url", "").replaceAll("/+$", "");
        URL url = new URL(baseUrl + "/v1/messages");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        try {
            conn.setConnectTimeout(20000);
            conn.setReadTimeout(90000);
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("anthropic-version", "2023-06-01");
            String apiKey = job.optString("api_key", "");
            if (!apiKey.isEmpty()) {
                conn.setRequestProperty("x-api-key", apiKey);
            }

            byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(body);
            }

            int code = conn.getResponseCode();
            InputStream stream = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
            return new HttpResult(code, readStream(stream));
        } finally {
            conn.disconnect();
        }
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

    private String readPending() {
        JSONArray arr = BackgroundLlmPlugin.readPending(this);
        JSONObject item = arr.optJSONObject(0);
        return item == null ? "" : item.toString();
    }

    private void clearPending(JSONObject job) {
        String jobId = job.optString("job_id", "");
        JSONArray current = BackgroundLlmPlugin.readPending(this);
        JSONArray kept = new JSONArray();
        for (int i = 0; i < current.length(); i++) {
            JSONObject item = current.optJSONObject(i);
            if (item != null && !jobId.equals(item.optString("job_id"))) {
                kept.put(item);
            }
        }
        BackgroundLlmPlugin.prefs(this).edit().putString(BackgroundLlmPlugin.PENDING_KEY, kept.toString()).apply();
    }

    private void storeCompleted(JSONObject job, String status, String rawContent, String error) throws Exception {
        JSONObject item = new JSONObject();
        item.put("job_id", job.optString("job_id", ""));
        item.put("sid", job.optString("sid", ""));
        item.put("turn_id", job.optString("turn_id", ""));
        item.put("client_msg_id", job.optString("client_msg_id", ""));
        item.put("reply_to_message_id", job.opt("reply_to_message_id"));
        item.put("status", status);
        item.put("raw_content", rawContent);
        item.put("error", error);
        item.put("created_at", System.currentTimeMillis());

        SharedPreferences prefs = BackgroundLlmPlugin.prefs(this);
        JSONArray arr = BackgroundLlmPlugin.readCompleted(this);
        arr.put(item);
        prefs.edit().putString(BackgroundLlmPlugin.COMPLETED_KEY, arr.toString()).apply();
    }

    private boolean notifyFinished(JSONObject job, String title, String text) {
        boolean updatedForegroundNotification = false;
        try {
            Notification foregroundNotification = buildNotification(title, text, false, RUNNING_CHANNEL_ID);
            try {
                startForeground(RUNNING_NOTIFICATION_ID, foregroundNotification);
                updatedForegroundNotification = true;
            } catch (Exception ignored) {
                // Fall back to NotificationManager below. The stored result remains importable on next app open.
            }

            NotificationManagerCompat manager = NotificationManagerCompat.from(this);
            try {
                manager.notify(RUNNING_NOTIFICATION_ID, foregroundNotification);
                updatedForegroundNotification = true;
            } catch (Exception ignored) {
                // Notification permission may be denied; the stored result is still imported on next app open.
            }
        } catch (Exception ignored) {
            // Notification permission may be denied; the stored result is still imported on next app open.
        }
        return updatedForegroundNotification;
    }

    private void finishForegroundNotification(boolean keepNotification) {
        if (Build.VERSION.SDK_INT >= 24) {
            stopForeground(keepNotification ? Service.STOP_FOREGROUND_DETACH : Service.STOP_FOREGROUND_REMOVE);
        } else {
            stopForeground(!keepNotification);
        }
    }

    private Notification buildNotification(String title, String text, boolean ongoing) {
        return buildNotification(title, text, ongoing, ongoing ? RUNNING_CHANNEL_ID : RESULT_CHANNEL_ID);
    }

    private Notification buildNotification(String title, String text, boolean ongoing, String channelId) {
        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }
        PendingIntent pi = PendingIntent.getActivity(this, 0, open, flags);

        return new NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_stat_reverse_tutor)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
            .setOngoing(ongoing)
            .setOnlyAlertOnce(ongoing)
            .setContentIntent(pi)
            .setAutoCancel(!ongoing)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setPriority(ongoing ? NotificationCompat.PRIORITY_DEFAULT : NotificationCompat.PRIORITY_HIGH)
            .setDefaults(ongoing ? 0 : (NotificationCompat.DEFAULT_SOUND | NotificationCompat.DEFAULT_VIBRATE))
            .setWhen(System.currentTimeMillis())
            .setShowWhen(true)
            .build();
    }

    private void ensureChannel() {
        if (Build.VERSION.SDK_INT < 26) {
            return;
        }
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }

        NotificationChannel running = new NotificationChannel(
            RUNNING_CHANNEL_ID,
            "后台 LLM 运行",
            NotificationManager.IMPORTANCE_LOW
        );
        running.setDescription("退出应用后继续生成当前 LLM 回复。");

        NotificationChannel result = new NotificationChannel(
            RESULT_CHANNEL_ID,
            "后台 LLM 回复",
            NotificationManager.IMPORTANCE_HIGH
        );
        result.setDescription("后台 LLM 回复完成后弹出实际回复内容。");
        result.enableVibration(true);

        manager.createNotificationChannel(running);
        manager.createNotificationChannel(result);
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
