import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const packageRoot = resolve(import.meta.dirname, '..');
const source = resolve(packageRoot, '../../DruMaster');
const target = resolve(packageRoot, 'www');
const indexPath = resolve(target, 'index.html');
const overlays = ['app-close-overlay.js', 'ranking-sync.js'];

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
await cp(source, target, { recursive: true });

for (const file of overlays) {
  await cp(resolve(packageRoot, file), resolve(target, file));
}

let indexHtml = await readFile(indexPath, 'utf8');
for (const file of overlays) {
  if (!indexHtml.includes(file)) {
    indexHtml = indexHtml.replace(/<\/body>/i, `  <script src="${file}"></script>\n</body>`);
  }
}
await writeFile(indexPath, indexHtml, 'utf8');

console.log(`Synced DruMaster web core:\n  ${source}\n→ ${target}`);
console.log('Injected Windows app-only close/drag controls and ranking sync queue.');
