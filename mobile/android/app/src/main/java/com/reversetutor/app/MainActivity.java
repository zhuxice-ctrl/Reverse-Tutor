package com.reversetutor.app;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        setTheme(R.style.AppTheme_NoActionBar);
        registerPlugin(BackgroundLlmPlugin.class);
        super.onCreate(savedInstanceState);
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
