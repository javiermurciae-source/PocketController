package com.pocketcontroller.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentValues;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.MediaStore;
import android.text.InputType;
import android.view.KeyEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.JsPromptResult;
import android.webkit.JsResult;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

public class MainActivity extends Activity {

    private static final String PREFS_NAME = "PocketControllerPrefs";
    private static final String KEY_SERVER_URL = "server_url";

    private static final int FILE_CHOOSER_REQUEST = 1001;
    private static final int FILE_IMPORT_REQUEST = 1002;
    private static final int CAMERA_PERMISSION_REQUEST = 2001;

    private WebView mWebView;
    private Vibrator mVibrator;
    private SharedPreferences mPrefs;
    private ValueCallback<Uri[]> mFilePathCallback;

    private boolean mVolDownPressed = false;
    private boolean mVolUpPressed = false;
    private boolean mIsScannerActive = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Pantalla completa sin bordes y mantener pantalla encendida
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);

        // Extender de borde a borde a través del notch / cámara frontal
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            WindowManager.LayoutParams lp = getWindow().getAttributes();
            lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
            getWindow().setAttributes(lp);
        }

        setImmersiveMode();

        mVibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
        mPrefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);

        mWebView = new WebView(this);
        mWebView.setBackgroundColor(0xFF090D16);
        mWebView.setLayerType(View.LAYER_TYPE_HARDWARE, null);
        setContentView(mWebView);

        setupWebView();

        // Solicitar permisos de cámara en Android 6.0+ para el escáner QR
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION_REQUEST);
            }
        }

        // Siempre abrir la pantalla de escaneo QR al inicio para conectar fácilmente a cualquier red
        openScannerView();
    }

    private void setupWebView() {
        WebSettings ws = mWebView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setAllowFileAccess(true);
        ws.setAllowContentAccess(true);

        // Escala y renderizado 1:1 idéntico a Google Chrome Mobile
        ws.setUseWideViewPort(true);
        ws.setLoadWithOverviewMode(true);
        ws.setTextZoom(100);
        ws.setSupportZoom(false);
        ws.setBuiltInZoomControls(false);
        ws.setDisplayZoomControls(false);
        ws.setCacheMode(WebSettings.LOAD_NO_CACHE);

        // Permitir acceso a cámara y reproducción multimedia
        ws.setMediaPlaybackRequiresUserGesture(false);

        mWebView.addJavascriptInterface(new AndroidBridge(this), "AndroidBridge");

        mWebView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame() && !mIsScannerActive) {
                    Toast.makeText(MainActivity.this, "❌ No se pudo conectar. Apunta al QR en la PC.", Toast.LENGTH_LONG).show();
                    openScannerView();
                }
            }
        });

        mWebView.setWebChromeClient(new WebChromeClient() {
            // Conceder permisos de cámara al WebView para escaneo de códigos QR
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        request.grant(request.getResources());
                    }
                });
            }

            @Override
            public boolean onJsAlert(WebView view, String url, String message, final JsResult result) {
                new AlertDialog.Builder(MainActivity.this)
                    .setTitle("PocketController")
                    .setMessage(message)
                    .setPositiveButton(android.R.string.ok, new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface dialog, int which) {
                            result.confirm();
                        }
                    })
                    .setCancelable(false)
                    .show();
                return true;
            }

            @Override
            public boolean onJsConfirm(WebView view, String url, String message, final JsResult result) {
                new AlertDialog.Builder(MainActivity.this)
                    .setTitle("PocketController")
                    .setMessage(message)
                    .setPositiveButton("Sí", new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface dialog, int which) {
                            result.confirm();
                        }
                    })
                    .setNegativeButton("No", new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface dialog, int which) {
                            result.cancel();
                        }
                    })
                    .setCancelable(false)
                    .show();
                return true;
            }

            @Override
            public boolean onJsPrompt(WebView view, String url, String message, String defaultValue, final JsPromptResult result) {
                final EditText input = new EditText(MainActivity.this);
                input.setText(defaultValue != null ? defaultValue : "");
                new AlertDialog.Builder(MainActivity.this)
                    .setTitle(message)
                    .setView(input)
                    .setPositiveButton(android.R.string.ok, new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface dialog, int which) {
                            result.confirm(input.getText().toString());
                        }
                    })
                    .setNegativeButton(android.R.string.cancel, new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface dialog, int which) {
                            result.cancel();
                        }
                    })
                    .setCancelable(false)
                    .show();
                return true;
            }

            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback, FileChooserParams fileChooserParams) {
                if (mFilePathCallback != null) {
                    mFilePathCallback.onReceiveValue(null);
                }
                mFilePathCallback = filePathCallback;
                try {
                    Intent intent = fileChooserParams.createIntent();
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                    return true;
                } catch (Exception e) {
                    Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                    intent.setType("*/*");
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    startActivityForResult(Intent.createChooser(intent, "Seleccionar JSON"), FILE_CHOOSER_REQUEST);
                    return true;
                }
            }
        });
    }

    private String readAssetFile(String filename) {
        try {
            InputStream is = getAssets().open(filename);
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int len;
            while ((len = is.read(buf)) != -1) {
                baos.write(buf, 0, len);
            }
            is.close();
            return baos.toString("UTF-8");
        } catch (Exception e) {
            return null;
        }
    }

    public void openScannerView() {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                mIsScannerActive = true;
                String html = readAssetFile("scanner.html");
                if (html != null) {
                    mWebView.loadDataWithBaseURL("https://pocket.local/", html, "text/html", "UTF-8", null);
                } else {
                    showServerConfigDialog("Conectar a PocketController");
                }
            }
        });
    }

    public void connectToUrl(final String url) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                mIsScannerActive = false;
                String finalUrl = url.trim();
                if (!finalUrl.startsWith("http://") && !finalUrl.startsWith("https://")) {
                    finalUrl = "http://" + finalUrl;
                }
                mPrefs.edit().putString(KEY_SERVER_URL, finalUrl).apply();
                mWebView.loadUrl(finalUrl);
            }
        });
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == CAMERA_PERMISSION_REQUEST) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                // Recargar escáner para que la cámara inicie de inmediato
                if (mIsScannerActive) {
                    openScannerView();
                }
            } else {
                Toast.makeText(this, "Permiso de cámara necesario para escanear QR", Toast.LENGTH_SHORT).show();
            }
        }
    }

    private void setImmersiveMode() {
        View decorView = getWindow().getDecorView();
        decorView.setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_FULLSCREEN
        );
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            setImmersiveMode();
        }
    }

    public void doVibrate(long ms) {
        if (mVibrator == null || !mVibrator.hasVibrator()) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            mVibrator.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE));
        } else {
            mVibrator.vibrate(ms);
        }
    }

    // --- EXPORTACIÓN E IMPORTACIÓN NATIVA DIRECTA ---
    public void exportJsonToStorage(final String filename, final String jsonContent) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    Uri savedUri = null;
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        ContentValues cv = new ContentValues();
                        cv.put(MediaStore.MediaColumns.DISPLAY_NAME, filename);
                        cv.put(MediaStore.MediaColumns.MIME_TYPE, "application/json");
                        cv.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
                        savedUri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                        if (savedUri != null) {
                            OutputStream os = getContentResolver().openOutputStream(savedUri);
                            if (os != null) {
                                os.write(jsonContent.getBytes(StandardCharsets.UTF_8));
                                os.close();
                            }
                        }
                    } else {
                        File dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
                        if (!dir.exists()) dir.mkdirs();
                        File file = new File(dir, filename);
                        FileOutputStream fos = new FileOutputStream(file);
                        fos.write(jsonContent.getBytes(StandardCharsets.UTF_8));
                        fos.close();
                        savedUri = Uri.fromFile(file);
                    }

                    Toast.makeText(MainActivity.this, "✅ Perfil guardado en Descargas:\n" + filename, Toast.LENGTH_LONG).show();

                    Intent shareIntent = new Intent(Intent.ACTION_SEND);
                    shareIntent.setType("application/json");
                    shareIntent.putExtra(Intent.EXTRA_SUBJECT, filename);
                    shareIntent.putExtra(Intent.EXTRA_TEXT, jsonContent);
                    if (savedUri != null) {
                        shareIntent.putExtra(Intent.EXTRA_STREAM, savedUri);
                        shareIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    }
                    startActivity(Intent.createChooser(shareIntent, "Compartir / Guardar Perfil"));

                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, "Error al exportar: " + e.getMessage(), Toast.LENGTH_LONG).show();
                }
            }
        });
    }

    public void pickJsonForImport() {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                try {
                    Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                    intent.setType("*/*");
                    String[] mimetypes = {"application/json", "text/plain", "application/octet-stream"};
                    intent.putExtra(Intent.EXTRA_MIME_TYPES, mimetypes);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    startActivityForResult(Intent.createChooser(intent, "Seleccionar Perfil JSON"), FILE_IMPORT_REQUEST);
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, "Error abriendo selector: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                }
            }
        });
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode == FILE_CHOOSER_REQUEST) {
            if (mFilePathCallback != null) {
                Uri[] results = null;
                if (resultCode == Activity.RESULT_OK && data != null) {
                    if (data.getData() != null) {
                        results = new Uri[]{ data.getData() };
                    } else if (data.getClipData() != null) {
                        int count = data.getClipData().getItemCount();
                        results = new Uri[count];
                        for (int i = 0; i < count; i++) {
                            results[i] = data.getClipData().getItemAt(i).getUri();
                        }
                    }
                }
                mFilePathCallback.onReceiveValue(results);
                mFilePathCallback = null;
            }
        } else if (requestCode == FILE_IMPORT_REQUEST) {
            if (resultCode == Activity.RESULT_OK && data != null && data.getData() != null) {
                readAndImportJson(data.getData());
            }
        }
    }

    private void readAndImportJson(Uri uri) {
        try {
            InputStream is = getContentResolver().openInputStream(uri);
            if (is != null) {
                ByteArrayOutputStream baos = new ByteArrayOutputStream();
                byte[] buf = new byte[4096];
                int len;
                while ((len = is.read(buf)) != -1) {
                    baos.write(buf, 0, len);
                }
                is.close();
                String jsonContent = baos.toString("UTF-8");
                final String safeJson = JSONObject.quote(jsonContent);
                mWebView.post(new Runnable() {
                    @Override
                    public void run() {
                        mWebView.evaluateJavascript("window.onNativeProfileImported && window.onNativeProfileImported(" + safeJson + ");", null);
                    }
                });
            }
        } catch (Exception e) {
            Toast.makeText(this, "Error leyendo archivo: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    // --- INTERCEPCIÓN DE BOTONES FÍSICOS DE VOLUMEN (GATILLOS) ---
    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (mIsScannerActive) {
            return super.dispatchKeyEvent(event);
        }

        int keyCode = event.getKeyCode();
        int action = event.getAction();

        if (keyCode == KeyEvent.KEYCODE_VOLUME_DOWN) {
            // VOLUMEN MENOS -> BOTÓN R (Derrape en Mario Kart)
            if (action == KeyEvent.ACTION_DOWN) {
                if (!mVolDownPressed) {
                    mVolDownPressed = true;
                    sendButtonState("R", true);
                    doVibrate(15);
                }
            } else if (action == KeyEvent.ACTION_UP) {
                mVolDownPressed = false;
                sendButtonState("R", false);
            }
            return true;
        } else if (keyCode == KeyEvent.KEYCODE_VOLUME_UP) {
            // VOLUMEN MÁS -> BOTÓN L (Lanzar Objeto en Mario Kart)
            if (action == KeyEvent.ACTION_DOWN) {
                if (!mVolUpPressed) {
                    mVolUpPressed = true;
                    sendButtonState("L", true);
                    doVibrate(15);
                }
            } else if (action == KeyEvent.ACTION_UP) {
                mVolUpPressed = false;
                sendButtonState("L", false);
            }
            return true;
        }

        return super.dispatchKeyEvent(event);
    }

    private void sendButtonState(final String btn, final boolean pressed) {
        mWebView.post(new Runnable() {
            @Override
            public void run() {
                String js = "if(window.onNativeVolumeKey){window.onNativeVolumeKey('" + btn + "', " + pressed + ");}";
                mWebView.evaluateJavascript(js, null);
            }
        });
    }

    @Override
    public void onBackPressed() {
        if (!mIsScannerActive) {
            openScannerView();
        } else {
            super.onBackPressed();
        }
    }

    private void showServerConfigDialog(String title) {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle(title);

        final EditText input = new EditText(this);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        String currentUrl = mPrefs.getString(KEY_SERVER_URL, "");
        input.setText(currentUrl);
        builder.setView(input);

        builder.setPositiveButton("Conectar", new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                connectToUrl(input.getText().toString());
            }
        });

        builder.setNeutralButton("Escanear QR", new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                openScannerView();
            }
        });

        builder.setNegativeButton("Cancelar", null);
        builder.show();
    }

    public static class AndroidBridge {
        private final MainActivity mActivity;

        public AndroidBridge(MainActivity activity) {
            this.mActivity = activity;
        }

        @JavascriptInterface
        public void vibrate(long ms) {
            mActivity.doVibrate(ms);
        }

        @JavascriptInterface
        public void connectToServer(String url) {
            mActivity.connectToUrl(url);
        }

        @JavascriptInterface
        public void openScanner() {
            mActivity.openScannerView();
        }

        @JavascriptInterface
        public void exportProfile(String filename, String jsonContent) {
            mActivity.exportJsonToStorage(filename, jsonContent);
        }

        @JavascriptInterface
        public void importProfile() {
            mActivity.pickJsonForImport();
        }
    }
}
