import { access, cp, mkdir, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises';
import { extname, join, relative, resolve } from 'node:path';

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
      // Remove only the final "gz", preserving the dot:
      // chart.mid.gz -> chart.mid.gzip
      await rename(path, `${path.slice(0, -2)}gzip`);
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

// Web playback stores large WAV stems as extensionless split chunks for
// GitHub Pages. Capacitor's local asset server can fall back to index.html for
// those extensionless chunk URLs. Reconstruct every packaged
// audio-manifest-v2.json stem into one normal .wav file and point the Android
// manifest at that file. Only the packaged copy is changed.
const songRoot = join(target, 'songs');
async function reconstructSongAudio(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      await reconstructSongAudio(path);
      continue;
    }
    if (entry.name !== 'audio-manifest-v2.json') continue;

    const manifest = JSON.parse(await readFile(path, 'utf8'));
    let changed = false;
    for (const [stemName, spec] of Object.entries(manifest)) {
      if (!spec || typeof spec !== 'object') continue;
      const parts = Number(spec.parts || 0);
      const prefix = String(spec.pathPrefix || '');
      if (!(parts > 0) || !prefix) continue;

      const digits = Number(spec.digits || 3);
      const chunks = [];
      const sourceParts = [];
      let totalBytes = 0;
      for (let i = 0; i < parts; i++) {
        const rel = `${prefix}${String(i).padStart(digits, '0')}`;
        const abs = join(target, rel);
        const bytes = await readFile(abs);
        chunks.push(bytes);
        sourceParts.push(abs);
        totalBytes += bytes.byteLength;
      }
      if (Number.isFinite(Number(spec.bytes)) && Number(spec.bytes) > 0 && totalBytes !== Number(spec.bytes)) {
        throw new Error(`Android song WAV reconstruction size mismatch for ${stemName}: ${totalBytes} / ${spec.bytes}`);
      }

      const manifestDir = relative(target, dir).replaceAll('\\', '/');
      const outRel = `${manifestDir}/android-audio/${stemName}.wav`;
      const outAbs = join(target, outRel);
      await mkdir(join(dir, 'android-audio'), { recursive: true });
      await writeFile(outAbs, Buffer.concat(chunks, totalBytes));
      await Promise.all(sourceParts.map(p => rm(p, { force: true })));

      spec.paths = [outRel];
      delete spec.pathPrefix;
      delete spec.parts;
      delete spec.digits;
      changed = true;
    }
    if (changed) await writeFile(path, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  }
}
await reconstructSongAudio(songRoot);

// Score Playback on the Web uses the gzip MIDI to reduce network transfer.
// In the Android package every chart.mid is already embedded locally, so the
// gzip path adds no benefit and introduces a second Android asset-serving
// path. Use the embedded raw MIDI directly for Score Playback and its offline
// cache. This is an Android-copy-only patch; DruMaster/ remains untouched.
const scorePlaybackPath = join(target, 'js', 'score-playback.js');
let scorePlayback = await readFile(scorePlaybackPath, 'utf8');
const webMidiLoader = `      const r=await nativeFetch(song.midiGzip,{cache:"force-cache"});\n      if(!r.ok)throw Error(\`${'${song.title}'} の楽譜を取得できません（HTTP ${'${r.status}'}）\`);\n      if(typeof DecompressionStream!=="function")throw Error("このブラウザではMIDI展開機能を利用できません");\n      const ab=await new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();`;
const androidMidiLoader = `      const r=await nativeFetch(song.midi,{cache:"force-cache"});\n      if(!r.ok)throw Error(\`${'${song.title}'} の楽譜を取得できません（HTTP ${'${r.status}'}）\`);\n      const ab=await r.arrayBuffer();`;
if (!scorePlayback.includes(webMidiLoader)) {
  throw new Error('Android score-playback raw-MIDI patch target was not found');
}
scorePlayback = scorePlayback.replace(webMidiLoader, androidMidiLoader);
await writeFile(scorePlaybackPath, scorePlayback, 'utf8');

const scoreCachePath = join(target, 'js', 'score-playback-offline-cache.js');
let scoreCache = await readFile(scoreCachePath, 'utf8');
const webDescriptor = '    addDescriptor(song.midiGzip,`midi:${song.id}:${song.midiGzip}`);';
const androidDescriptor = '    addDescriptor(song.midi,`midi:${song.id}:${song.midi}`);';
if (!scoreCache.includes(webDescriptor)) {
  throw new Error('Android score-playback cache raw-MIDI patch target was not found');
}
scoreCache = scoreCache.replace(webDescriptor, androidDescriptor);
await writeFile(scoreCachePath, scoreCache, 'utf8');

// Verify every score-playback raw MIDI reference exists in the packaged copy.
const registryPath = join(target, 'songs', 'registry.json');
const registry = JSON.parse(await readFile(registryPath, 'utf8'));
for (const song of Object.values(registry)) {
  const rawRef = String(song?.midi || '');
  if (!rawRef) throw new Error(`Android packaged raw MIDI reference is missing for ${song?.id || song?.title || 'unknown'}`);
  const rawPath = rawRef.split(/[?#]/, 1)[0];
  try {
    await access(join(target, rawPath));
  } catch {
    throw new Error(`Android packaged raw MIDI is missing for ${song?.id || song?.title || 'unknown'}: ${rawPath}`);
  }

  const gzipRef = String(song?.midiGzip || '');
  if (!gzipRef) continue;
  const gzipPath = gzipRef.split(/[?#]/, 1)[0];
  try {
    await access(join(target, gzipPath));
  } catch {
    throw new Error(`Android packaged MIDI gzip is missing for ${song?.id || song?.title || 'unknown'}: ${gzipPath}`);
  }
}

// Validate reconstructed song manifests and their single WAV targets.
async function validateSongAudio(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      await validateSongAudio(path);
      continue;
    }
    if (entry.name !== 'audio-manifest-v2.json') continue;
    const manifest = JSON.parse(await readFile(path, 'utf8'));
    for (const [stemName, spec] of Object.entries(manifest)) {
      if (!spec || typeof spec !== 'object' || !Number.isFinite(Number(spec.bytes))) continue;
      if (!Array.isArray(spec.paths) || spec.paths.length !== 1 || !String(spec.paths[0]).endsWith('.wav')) {
        throw new Error(`Android song manifest did not collapse ${stemName} to one WAV: ${path}`);
      }
      const wavPath = join(target, spec.paths[0]);
      const bytes = await readFile(wavPath);
      if (bytes.byteLength !== Number(spec.bytes)) {
        throw new Error(`Android packaged song WAV size mismatch for ${stemName}: ${bytes.byteLength} / ${spec.bytes}`);
      }
    }
  }
}
await validateSongAudio(songRoot);

// The game drum WAV is split only for the Web/GitHub Pages distribution.
// Capacitor's local asset server can fall back to index.html for the split
// extensionless chunks even though they are present in the APK. For Android,
// reconstruct the original WAV at package time. Keep the manifest contract
// expected by audio.js: loadDrumSource() calls fetchJoined(), which consumes
// wav.paths (or parts/pathPrefix), so expose the single packaged WAV as a
// one-element paths array rather than wav.path. DruMaster/ remains untouched.
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
  await Promise.all(sourceParts.map(path => rm(path, { force: true })));

  drumManifest.wav.paths = [relativeWav];
  delete drumManifest.wav.path;
  delete drumManifest.wav.pathPrefix;
  delete drumManifest.wav.parts;
  delete drumManifest.wav.digits;
  await writeFile(drumManifestPath, `${JSON.stringify(drumManifest, null, 2)}\n`, 'utf8');
}

// manifest-fallback.js exists for GitHub Pages and deliberately intercepts
// requests for assets/drumsound-manifest.json with an embedded 22-part Web
// manifest. In a packaged Android app that interception is harmful: it hides
// the Android-specific one-file manifest written above and makes audio.js
// fetch the obsolete split paths. Local packaged assets do not need the Pages
// network fallback, so make this script a no-op in the Android copy only.
const drumFallbackPath = join(target, 'js', 'manifest-fallback.js');
await writeFile(
  drumFallbackPath,
  '"use strict";\n// Android package: GitHub Pages drum-manifest fallback intentionally disabled.\n',
  'utf8'
);

// Fail the package build immediately if a future edit reintroduces a mismatch.
const packagedManifest = JSON.parse(await readFile(drumManifestPath, 'utf8'));
if (!Array.isArray(packagedManifest?.wav?.paths) || packagedManifest.wav.paths.length !== 1 || packagedManifest.wav.paths[0] !== 'assets/drumsound-v2.wav') {
  throw new Error('Android drum manifest contract is invalid after packaging');
}
const packagedFallback = await readFile(drumFallbackPath, 'utf8');
if (packagedFallback.includes('pathPrefix') || packagedFallback.includes('embeddedDrumManifest')) {
  throw new Error('Android drum manifest fallback was not disabled');
}
const packagedScorePlayback = await readFile(scorePlaybackPath, 'utf8');
if (packagedScorePlayback.includes('nativeFetch(song.midiGzip')) {
  throw new Error('Android Score Playback still fetches midiGzip');
}
const packagedScoreCache = await readFile(scoreCachePath, 'utf8');
if (packagedScoreCache.includes('addDescriptor(song.midiGzip')) {
  throw new Error('Android Score Playback cache still targets midiGzip');
}

console.log(`Synced DruMaster web core:\n  ${source}\n→ ${target}`);
console.log('Android package transform: *.mid.gz → *.mid.gzip (packaged copy only; dot preserved)');
console.log('Android package transform: split song WAV stems → one .wav per stem');
console.log('Android package transform: Score Playback uses embedded raw chart.mid files');
console.log('Android package validation: all registry raw MIDI and midiGzip references resolve to packaged files');
console.log('Android package validation: reconstructed song WAV manifests resolve to exact-size .wav files');
console.log('Android package transform: split game-drum source → one-element wav.paths for assets/drumsound-v2.wav');
console.log('Android package transform: Web drum manifest fallback disabled');
