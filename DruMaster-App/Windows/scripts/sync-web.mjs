import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const packageRoot = resolve(import.meta.dirname, '..');
const source = resolve(packageRoot, '../../DruMaster');
const target = resolve(packageRoot, 'www');
const overlaySource = resolve(packageRoot, 'app-close-overlay.js');
const overlayTarget = resolve(target, 'app-close-overlay.js');
const rankingSource = resolve(packageRoot, 'ranking-sync.js');
const rankingTarget = resolve(target, 'ranking-sync.js');
const performanceSource = resolve(packageRoot, 'pc-performance-opt.js');
const performanceTarget = resolve(target, 'pc-performance-opt.js');
const updaterSource = resolve(packageRoot, 'auto-update.js');
const updaterTarget = resolve(target, 'auto-update.js');
const indexPath = resolve(target, 'index.html');

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
await cp(source, target, { recursive: true });

// Windows app-only shell/ranking/performance/updater additions. Keep the shared
// Web and Android builds unchanged.
await Promise.all([
  cp(overlaySource, overlayTarget),
  cp(rankingSource, rankingTarget),
  cp(performanceSource, performanceTarget),
  cp(updaterSource, updaterTarget)
]);

let indexHtml = await readFile(indexPath, 'utf8');
const injections = [
  'app-close-overlay.js',
  'ranking-sync.js',
  'pc-performance-opt.js',
  'auto-update.js'
];
for (const script of injections) {
  if (!indexHtml.includes(script)) {
    indexHtml = indexHtml.replace(/<\/body>/i, `  <script src="${script}"></script>\n</body>`);
  }
}
await writeFile(indexPath, indexHtml, 'utf8');

console.log(`Synced DruMaster web core:\n  ${source}\n→ ${target}`);
console.log('Injected Windows app-only window controls, ranking sync, performance optimization, and automatic updater.');
