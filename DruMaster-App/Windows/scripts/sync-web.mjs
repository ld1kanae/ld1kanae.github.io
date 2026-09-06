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

// Ranking sync lives in the shared DruMaster web core. Windows injects its
// shell/performance/updater scripts plus the local-history safety layer with a
// per-build cache key so a stale WebView cache cannot suppress result storage.
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
  'js/local-play-history.js',
  'js/ranking-result-cloud.js'
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
console.log(`Injected Windows-only scripts and durable local history with build cache key v=${buildNumber}.`);
