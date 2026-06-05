package com.reversetutor.app;

import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private static final String APP_SHELL_PREFS = "reverse_tutor_app_shell";
    private static final String LAST_NATIVE_VERSION_KEY = "last_native_version_code";
    private static final String CACHE_REFRESH_ATTEMPT_VERSION_KEY = "cache_refresh_attempt_version_code";
    private static final String CACHE_REFRESH_ATTEMPT_COUNT_KEY = "cache_refresh_attempt_count";
    private static final int MAX_CACHE_REFRESH_ATTEMPTS = 3;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        setTheme(R.style.AppTheme_NoActionBar);
        registerPlugin(BackgroundLlmPlugin.class);
        boolean refreshAppShell = shouldRefreshAppShellForNativeVersion();
        super.onCreate(savedInstanceState);
        if (refreshAppShell) {
            refreshStaleAppShellCache();
        }
    }

    private boolean shouldRefreshAppShellForNativeVersion() {
        long currentVersion = currentNativeVersionCode();
        if (currentVersion <= 0) return false;
        SharedPreferences prefs = getSharedPreferences(APP_SHELL_PREFS, MODE_PRIVATE);
        long lastVersion = prefs.getLong(LAST_NATIVE_VERSION_KEY, -1L);
        if (lastVersion == currentVersion) return false;
        long attemptVersion = prefs.getLong(CACHE_REFRESH_ATTEMPT_VERSION_KEY, -1L);
        int attemptCount = attemptVersion == currentVersion
            ? prefs.getInt(CACHE_REFRESH_ATTEMPT_COUNT_KEY, 0)
            : 0;
        if (attemptCount >= MAX_CACHE_REFRESH_ATTEMPTS) return false;
        prefs.edit()
            .putLong(CACHE_REFRESH_ATTEMPT_VERSION_KEY, currentVersion)
            .putInt(CACHE_REFRESH_ATTEMPT_COUNT_KEY, attemptCount + 1)
            .apply();
        return true;
    }

    private long currentNativeVersionCode() {
        try {
            PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                return info.getLongVersionCode();
            }
            return info.versionCode;
        } catch (PackageManager.NameNotFoundException e) {
            return -1L;
        }
    }

    private void refreshStaleAppShellCache() {
        if (bridge == null || bridge.getWebView() == null) return;
        long currentVersion = currentNativeVersionCode();
        bridge.getWebView().clearCache(true);
        bridge.getWebView().post(() -> bridge.getWebView().evaluateJavascript(
            "(function(){"
                + "if(window.__rtNativeAppShellRefresh)return;"
                + "window.__rtNativeAppShellRefresh=true;"
                + "var tasks=[];"
                + "var didReload=false;"
                + "function reload(){"
                + "if(didReload)return;"
                + "didReload=true;"
                + "try{var url=new URL(location.href);url.searchParams.set('native-cache-bust',String(Date.now()));location.replace(url.toString());}"
                + "catch(e){location.reload();}"
                + "}"
                + "function addTask(task){try{tasks.push(Promise.resolve(task).catch(function(){}));}catch(e){}}"
                + "if(typeof Promise==='undefined'){setTimeout(reload,50);return 'no-promise';}"
                + "if('serviceWorker'in navigator&&navigator.serviceWorker.getRegistrations){"
                + "addTask(navigator.serviceWorker.getRegistrations()"
                + ".then(function(regs){return Promise.all(regs.map(function(reg){return reg.unregister().catch(function(){});}));}));"
                + "}"
                + "if('caches'in window&&caches.keys){"
                + "addTask(caches.keys().then(function(keys){return Promise.all(keys"
                + ".filter(function(key){return key.indexOf(\"rt-mobile-\")===0;})"
                + ".map(function(key){return caches.delete(key).catch(function(){});}));}));"
                + "}"
                + "if(tasks.length){Promise.all(tasks).then(reload).catch(reload);}"
                + "else{setTimeout(reload,50);}"
                + "setTimeout(reload,1500);"
                + "return 'queued';"
                + "})();",
            result -> markAppShellRefreshScheduled(currentVersion)
        ));
    }

    private void markAppShellRefreshScheduled(long currentVersion) {
        if (currentVersion <= 0) return;
        getSharedPreferences(APP_SHELL_PREFS, MODE_PRIVATE)
            .edit()
            .putLong(LAST_NATIVE_VERSION_KEY, currentVersion)
            .remove(CACHE_REFRESH_ATTEMPT_VERSION_KEY)
            .remove(CACHE_REFRESH_ATTEMPT_COUNT_KEY)
            .apply();
    }

    @Override
    public void onBackPressed() {
        if (bridge != null && bridge.getWebView() != null) {
            bridge.getWebView().evaluateJavascript(
                "window.__rtHandleNativeBack ? window.__rtHandleNativeBack() : false",
                result -> runOnUiThread(() -> {
                    if (!"true".equals(result)) {
                        moveTaskToBack(true);
                    }
                })
            );
        } else {
            super.onBackPressed();
        }
    }
}
