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

// The game drum source is a split PCM WAV. Extensionless assets are Deflate-
// compressed by Android packaging, which can make Capacitor's local asset
// server return the compressed payload instead of the original bytes. Rename
// only the Android package copies to .wav so AAPT stores them uncompressed,
// and point the packaged manifest at those files explicitly. Web files remain
// exactly as they are in DruMaster/.
const drumManifestPath = join(target, 'assets', 'drumsound-manifest.json');
const drumManifest = JSON.parse(await readFile(drumManifestPath, 'utf8'));
const drumParts = Number(drumManifest?.wav?.parts || 0);
const drumDigits = Number(drumManifest?.wav?.digits || 3);
const drumPrefix = String(drumManifest?.wav?.pathPrefix || '');

if (drumParts > 0 && drumPrefix) {
  const packagedPaths = [];
  for (let i = 0; i < drumParts; i++) {
    const stem = `${drumPrefix}${String(i).padStart(drumDigits, '0')}`;
    const sourcePart = join(target, stem);
    const packagedPart = `${sourcePart}.wav`;
    await rename(sourcePart, packagedPart);
    packagedPaths.push(`${stem}.wav`);
  }

  drumManifest.wav.paths = packagedPaths;
  delete drumManifest.wav.pathPrefix;
  delete drumManifest.wav.parts;
  delete drumManifest.wav.digits;
  await writeFile(drumManifestPath, `${JSON.stringify(drumManifest, null, 2)}\n`, 'utf8');
}

console.log(`Synced DruMaster web core:\n  ${source}\n→ ${target}`);
console.log('Android package transform: *.mid.gz → *.mid.gzip (packaged copy only)');
console.log('Android package transform: drumsound WAV chunks → *.wav (uncompressed Android assets)');
