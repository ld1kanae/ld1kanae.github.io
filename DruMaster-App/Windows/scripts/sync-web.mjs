import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const packageRoot = resolve(import.meta.dirname, '..');
const source = resolve(packageRoot, '../../DruMaster');
const target = resolve(packageRoot, 'www');
const overlaySource = resolve(packageRoot, 'app-close-overlay.js');
const overlayTarget = resolve(target, 'app-close-overlay.js');
const indexPath = resolve(target, 'index.html');

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
await cp(source, target, { recursive: true });

// Windows app-only shell UI. Keep the shared Web version unchanged.
await cp(overlaySource, overlayTarget);
let indexHtml = await readFile(indexPath, 'utf8');
if (!indexHtml.includes('app-close-overlay.js')) {
  indexHtml = indexHtml.replace(/<\/body>/i, '  <script src="app-close-overlay.js"></script>\n</body>');
  await writeFile(indexPath, indexHtml, 'utf8');
}

console.log(`Synced DruMaster web core:\n  ${source}\n→ ${target}`);
console.log('Injected Windows app-only close overlay.');
