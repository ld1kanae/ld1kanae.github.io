import { cp, mkdir, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises';
import { extname, join, resolve } from 'node:path';

const packageRoot = resolve(import.meta.dirname, '..');
const source = resolve(packageRoot, '../../DruMaster');
const target = resolve(packageRoot, 'www');

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
await cp(source, target, { recursive: true });

// Android's asset merger treats "chart.mid" and "chart.mid.gz" as the same
// asset name. Keep both payloads, but rename only the packaged copy of the
// gzip file. DecompressionStream reads the bytes, so the extension itself is
// not semantically significant. The Web source tree remains untouched.
async function walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      await walk(path);
      continue;
    }

    if (entry.name.endsWith('.mid.gz')) {
      await rename(path, `${path.slice(0, -3)}gzip`);
      continue;
    }

    if (['.js', '.json', '.html'].includes(extname(entry.name))) {
      const text = await readFile(path, 'utf8');
      if (text.includes('.mid.gz')) {
        await writeFile(path, text.replaceAll('.mid.gz', '.mid.gzip'), 'utf8');
      }
    }
  }
}

await walk(target);

console.log(`Synced DruMaster web core:\n  ${source}\n→ ${target}`);
console.log('Android package transform: *.mid.gz → *.mid.gzip (packaged copy only)');
