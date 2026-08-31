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

// The game drum WAV is split only for the Web/GitHub Pages distribution.
// Capacitor's local asset server can fall back to index.html for the split
// extensionless/renamed chunks even though they are present in the APK. For
// Android, reconstruct the original WAV at package time and point only the
// packaged manifest at that single file. This leaves DruMaster/ untouched.
const drumManifestPath = join(target, 'assets', 'drumsound-manifest.json');
const drumManifest = JSON.parse(await readFile(drumManifestPath, 'utf8'));
const drumParts = Number(drumManifest?.wav?.parts || 0);
const drumDigits = Number(drumManifest?.wav?.digits || 3);
const drumPrefix = String(drumManifest?.wav?.pathPrefix || '');

if (drumParts > 0 && drumPrefix) {
  const chunks = [];
  const sourceParts = [];
  let totalBytes = 0;

  for (let i = 0; i < drumParts; i++) {
    const relativePart = `${drumPrefix}${String(i).padStart(drumDigits, '0')}`;
    const absolutePart = join(target, relativePart);
    const bytes = await readFile(absolutePart);
    chunks.push(bytes);
    sourceParts.push(absolutePart);
    totalBytes += bytes.byteLength;
  }

  if (drumManifest.wav.bytes && totalBytes !== Number(drumManifest.wav.bytes)) {
    throw new Error(`Android drum WAV reconstruction size mismatch: ${totalBytes} / ${drumManifest.wav.bytes}`);
  }

  const relativeWav = 'assets/drumsound-v2.wav';
  await writeFile(join(target, relativeWav), Buffer.concat(chunks, totalBytes));

  // Remove package-only source chunks so the APK contains just the WAV that
  // the Android manifest references.
  await Promise.all(sourceParts.map(path => rm(path, { force: true })));

  drumManifest.wav.path = relativeWav;
  delete drumManifest.wav.paths;
  delete drumManifest.wav.pathPrefix;
  delete drumManifest.wav.parts;
  delete drumManifest.wav.digits;
  await writeFile(drumManifestPath, `${JSON.stringify(drumManifest, null, 2)}\n`, 'utf8');
}

console.log(`Synced DruMaster web core:\n  ${source}\n→ ${target}`);
console.log('Android package transform: *.mid.gz → *.mid.gzip (packaged copy only)');
console.log('Android package transform: split game-drum source → assets/drumsound-v2.wav (packaged copy only)');
