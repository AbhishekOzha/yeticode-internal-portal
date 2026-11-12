package com.yeticode.yeticode_mobile

import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "yeticode/screenshare").setMethodCallHandler { call, result ->
            val intent = Intent(this, ScreenShareService::class.java)
            when (call.method) {
                "start" -> { startForegroundService(intent); result.success(true) }
                "stop" -> { stopService(intent); result.success(true) }
                else -> result.notImplemented()
            }
        }
    }
}
