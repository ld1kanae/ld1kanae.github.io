import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const packageRoot = resolve(import.meta.dirname, '..');
const source = resolve(packageRoot, '../../DruMaster');
const target = resolve(packageRoot, 'www');
const overlaySource = resolve(packageRoot, 'app-close-overlay.js');
const overlayTarget = resolve(target, 'app-close-overlay.js');
const performanceSource = resolve(packageRoot, 'pc-performance-opt.js');
const performanceTarget = resolve(target, 'pc-performance-opt.js');
const updaterSource = resolve(packageRoot, 'auto-update.js');
const updaterTarget = resolve(target, 'auto-update.js');
const indexPath = resolve(target, 'index.html');
const buildNumber = String(process.env.DRUMASTER_BUILD_NUMBER || process.env.GITHUB_RUN_NUMBER || Date.now());

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
await cp(source, target, { recursive: true });

// Ranking persistence/sync is entirely in the shared DruMaster core. Windows
// adds only shell/performance/updater code; it must never inject a second score
// database/capture layer.
await Promise.all([
  cp(overlaySource, overlayTarget),
  cp(performanceSource, performanceTarget),
  cp(updaterSource, updaterTarget)
]);

let indexHtml = await readFile(indexPath, 'utf8');
const injections = [
  'app-close-overlay.js',
  'pc-performance-opt.js',
  'auto-update.js',
  // These already exist in the shared index; including them here replaces their
  // cache key with the Windows build number so WebView2 cannot retain an older
  // timer-based ranking loader across app upgrades.
  'js/offline-playback.js',
  'js/setup-visual-final.js'
];
for (const script of injections) {
  const barePattern = new RegExp(`<script\\s+src=["']${script.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[^"']*["'][^>]*><\\/script>`, 'i');
  const tag = `<script src="${script}?v=${encodeURIComponent(buildNumber)}"></script>`;
  if (barePattern.test(indexHtml)) {
    indexHtml = indexHtml.replace(barePattern, tag);
  } else {
    indexHtml = indexHtml.replace(/<\/body>/i, `  ${tag}\n</body>`);
  }
}
await writeFile(indexPath, indexHtml, 'utf8');

console.log(`Synced DruMaster web core:\n  ${source}\n→ ${target}`);
console.log(`Injected Windows shell scripts and refreshed shared ranking loaders with build cache key v=${buildNumber}.`);
