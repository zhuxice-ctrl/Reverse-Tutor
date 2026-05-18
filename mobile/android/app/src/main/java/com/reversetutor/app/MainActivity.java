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
}
