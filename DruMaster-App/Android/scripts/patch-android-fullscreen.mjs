import { access, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const packageRoot = resolve(import.meta.dirname, '..');
const mainActivityPath = resolve(
  packageRoot,
  'android/app/src/main/java/io/github/ld1kanae/drumaster/MainActivity.java'
);

await access(mainActivityPath);

const source = `package io.github.ld1kanae.drumaster;

import android.os.Bundle;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        enterImmersiveFullscreen();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            enterImmersiveFullscreen();
        }
    }

    private void enterImmersiveFullscreen() {
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        WindowInsetsControllerCompat controller = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        controller.hide(WindowInsetsCompat.Type.systemBars());
        controller.setSystemBarsBehavior(
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        );
    }
}
`;

await writeFile(mainActivityPath, source, 'utf8');

const written = await readFile(mainActivityPath, 'utf8');
if (!written.includes('WindowInsetsCompat.Type.systemBars()') || !written.includes('BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE')) {
  throw new Error('Android immersive fullscreen patch verification failed');
}

console.log('Android package transform: immersive fullscreen enabled in MainActivity');
