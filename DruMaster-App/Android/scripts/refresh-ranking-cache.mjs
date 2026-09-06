import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const packageRoot = resolve(import.meta.dirname, '..');
const indexPath = resolve(packageRoot, 'www/index.html');
const buildKey = String(process.env.DRUMASTER_BUILD_NUMBER || process.env.GITHUB_RUN_NUMBER || Date.now());

let html = await readFile(indexPath, 'utf8');
for (const script of ['js/offline-playback.js', 'js/setup-visual-final.js']) {
  const escaped = script.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(`(<script\\s+src=["']${escaped})(?:\\?[^"']*)?(["'][^>]*><\\/script>)`, 'i');
  if (!pattern.test(html)) throw new Error(`Android ranking cache target missing: ${script}`);
  html = html.replace(pattern, `$1?v=${encodeURIComponent(buildKey)}$2`);
}
await writeFile(indexPath, html, 'utf8');
console.log(`Android ranking loaders refreshed with package cache key v=${buildKey}.`);
