const fs = require('fs');
const path = require('path');

const dataDir = path.resolve(__dirname, '..', 'data');
const rows = [];
for (let number = 1; number <= 999; number += 1) {
  const filename = path.join(dataDir, `vocabulary_${String(number).padStart(3, '0')}.txt`);
  if (!fs.existsSync(filename)) break;
  const entries = JSON.parse(fs.readFileSync(filename, 'utf8'));
  if (!Array.isArray(entries)) throw new Error(`${filename}: 配列ではありません`);
  rows.push(...entries.map((entry) => ({ ...entry, source: path.basename(filename) })));
}

const required = ['id', 'phrase', 'reading', 'meaning', 'example', 'category', 'genres', 'similar'];
const duplicateFields = ['id', 'phrase', 'reading', 'meaning', 'example'];
const problems = [];

for (const row of rows) {
  for (const key of required) {
    if (row[key] == null || row[key] === '') problems.push(`${row.id || row.source}: ${key} が不足`);
  }
  if (!Array.isArray(row.genres) || !row.genres.length) problems.push(`${row.id}: genres が空`);
  if (!Array.isArray(row.similar) || !row.similar.length) problems.push(`${row.id}: similar が空`);
}

for (const field of duplicateFields) {
  const seen = new Map();
  for (const row of rows) {
    const value = row[field];
    if (seen.has(value)) problems.push(`${field} 重複: ${value} (${seen.get(value)} / ${row.id})`);
    else seen.set(value, row.id);
  }
}

const normalize = (value) => value
  .normalize('NFKC')
  .replace(/[\s・、。！？「」『』（）()]/g, '')
  .replace(/撫で/g, 'なで')
  .replace(/噤/g, 'つぐ')
  .replace(/摘ま/g, 'つま')
  .replace(/項垂/g, 'うなだ')
  .replace(/甦/g, '蘇');

const normalized = new Map();
for (const row of rows) {
  const key = normalize(row.phrase);
  if (normalized.has(key)) problems.push(`表記揺れ候補: ${normalized.get(key).phrase} / ${row.phrase}`);
  else normalized.set(key, row);
}

if (problems.length) {
  console.error(problems.join('\n'));
  process.exitCode = 1;
} else {
  const newRows = rows.filter((row) => Number(row.id.slice(3)) >= 1201);
  console.log(`検査合格: 全${rows.length}件、追加${newRows.length}件、ID・表記・読み・意味・用例の重複なし`);
}

