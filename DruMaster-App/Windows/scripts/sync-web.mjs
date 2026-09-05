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

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
await cp(source, target, { recursive: true });

// Ranking sync now lives in the shared DruMaster web core, so Windows must not
// inject its old platform-specific copy or the same result would be captured and
// uploaded twice. Only Windows-shell/performance/updater scripts remain here.
await Promise.all([
  cp(overlaySource, overlayTarget),
  cp(performanceSource, performanceTarget),
  cp(updaterSource, updaterTarget)
]);

let indexHtml = await readFile(indexPath, 'utf8');
const injections = [
  'app-close-overlay.js',
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
console.log('Shared ranking sync retained; injected Windows-only window controls, performance optimization, and automatic updater.');
