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
        prefs.edit().putLong(LAST_NATIVE_VERSION_KEY, currentVersion).apply();
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
        bridge.getWebView().clearCache(true);
        bridge.getWebView().post(() -> bridge.getWebView().evaluateJavascript(
            "(function(){"
                + "if(window.__rtNativeAppShellRefresh)return;"
                + "window.__rtNativeAppShellRefresh=true;"
                + "var tasks=[];"
                + "if('serviceWorker'in navigator){"
                + "tasks.push(navigator.serviceWorker.getRegistrations()"
                + ".then(function(regs){return Promise.all(regs.map(function(reg){return reg.unregister();}));}));"
                + "}"
                + "if('caches'in window){"
                + "tasks.push(caches.keys().then(function(keys){return Promise.all(keys"
                + ".filter(function(key){return key.indexOf(\"rt-mobile-\")===0;})"
                + ".map(function(key){return caches.delete(key);}));}));"
                + "}"
                + "Promise.allSettled(tasks).then(function(){"
                + "try{var url=new URL(location.href);url.searchParams.set('native-cache-bust',String(Date.now()));location.replace(url.toString());}"
                + "catch(e){location.reload();}"
                + "});"
                + "})();",
            null
        ));
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
