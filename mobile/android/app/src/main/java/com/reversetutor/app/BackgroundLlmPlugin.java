package com.reversetutor.app;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;

import androidx.core.content.ContextCompat;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import org.json.JSONArray;
import org.json.JSONObject;

@CapacitorPlugin(name = "BackgroundLlm")
public class BackgroundLlmPlugin extends Plugin {
    static final String PREFS_NAME = "BackgroundLlm";
    static final String COMPLETED_KEY = "rt-native-background-llm-completed";
    private static final int REQ_NOTIFICATIONS = 7301;

    @PluginMethod
    public void isAvailable(PluginCall call) {
        JSObject ret = new JSObject();
        ret.put("available", true);
        call.resolve(ret);
    }

    @PluginMethod
    public void requestNotificationPermission(PluginCall call) {
        if (Build.VERSION.SDK_INT < 33) {
            JSObject ret = new JSObject();
            ret.put("granted", true);
            call.resolve(ret);
            return;
        }

        boolean granted = ContextCompat.checkSelfPermission(
            getContext(),
            Manifest.permission.POST_NOTIFICATIONS
        ) == PackageManager.PERMISSION_GRANTED;
        if (!granted && getActivity() != null) {
            getActivity().requestPermissions(new String[] { Manifest.permission.POST_NOTIFICATIONS }, REQ_NOTIFICATIONS);
        }

        JSObject ret = new JSObject();
        ret.put("granted", granted);
        ret.put("requested", !granted);
        call.resolve(ret);
    }

    @PluginMethod
    public void enqueueTurn(PluginCall call) {
        JSObject data = call.getData();
        if (data == null || !data.has("job_id") || !data.has("sid")) {
            call.reject("missing job_id or sid");
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
}
