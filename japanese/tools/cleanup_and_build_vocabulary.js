const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const dataDir = path.join(root, 'data');

// 左側のIDを廃止し、右側の現代的・代表的な表記へ統合する。
const idAliases = {
  'jp-000593': 'jp-000007', // 胸を撫で下ろす → 胸をなで下ろす
  'jp-000801': 'jp-000103', // 口を噤む → 口をつぐむ
  'jp-000705': 'jp-000706', // 指で摘まむ → 指でつまむ
  'jp-000811': 'jp-000810', // 言いよどむ → 言い淀む
  'jp-001118': 'jp-001117', // 記憶がよみがえる → 記憶が蘇る
  'jp-000785': 'jp-000784', // 項垂れる → うなだれる
  'jp-000579': 'jp-000073', // 感無量になる → 感無量
  'jp-001168': 'jp-001167', // 時を忘れる → 時間を忘れる
  'jp-000223': 'jp-000679', // 横目で見る → 横目に見る
  'jp-000138': 'jp-000142', // 耳に挟む → 小耳に挟む
  'jp-001114': 'jp-000317', // 記憶を手繰る → 記憶の糸を手繰る
  'jp-000412': 'jp-000398', // 先が見えない → 先行きが見えない
  'jp-000508': 'jp-000509', // 胸に穴が開く → 心に穴が開く
  'jp-000510': 'jp-000509', // ぽっかり穴が開く → 心に穴が開く
  'jp-000695': 'jp-000512', // 瞳を潤ませる → 目を潤ませる
  'jp-000620': 'jp-000619', // 怒気を孕む → 怒気を含む
  'jp-000621': 'jp-000619', // 怒気を帯びる → 怒気を含む
  'jp-000842': 'jp-000843', // 含みを持たせる → 言葉に含みを持たせる
  'jp-000880': 'jp-001003', // 雨音がそぼ降る（不自然）→ 雨がそぼ降る
  'jp-001082': 'jp-001083', // 壁を作る → 心に壁を作る
  'jp-000609': 'jp-000072'  // 癪に触る → 癪に障る
};

const removedIds = new Set(Object.keys(idAliases));
const phraseAliases = {
  '胸を撫で下ろす': '胸をなで下ろす',
  '口を噤む': '口をつぐむ',
  '指で摘まむ': '指でつまむ',
  '言いよどむ': '言い淀む',
  '記憶がよみがえる': '記憶が蘇る',
  '項垂れる': 'うなだれる',
  '感無量になる': '感無量',
  '時を忘れる': '時間を忘れる',
  '横目で見る': '横目に見る',
  '耳に挟む': '小耳に挟む',
  '記憶を手繰る': '記憶の糸を手繰る',
  '先が見えない': '先行きが見えない',
  '胸に穴が開く': '心に穴が開く',
  'ぽっかり穴が開く': '心に穴が開く',
  '瞳を潤ませる': '目を潤ませる',
  '怒気を孕む': '怒気を含む',
  '怒気を帯びる': '怒気を含む',
  '含みを持たせる': '言葉に含みを持たせる',
  '雨音がそぼ降る': '雨がそぼ降る',
  '壁を作る': '心に壁を作る',
  '癪に触る': '癪に障る'
};
const existing = [];
for (let number = 1; number <= 12; number += 1) {
  const filename = path.join(dataDir, `vocabulary_${String(number).padStart(3, '0')}.txt`);
  const rows = JSON.parse(fs.readFileSync(filename, 'utf8'));
  const kept = rows.filter((row) => !removedIds.has(row.id)).map((row) => ({
    ...row,
    similar: [...new Set((row.similar || []).map((phrase) => phraseAliases[phrase] || phrase))]
      .filter((phrase) => phrase !== row.phrase)
  }));
  fs.writeFileSync(filename, `${JSON.stringify(kept, null, 2)}\n`);
  existing.push(...kept);
}

const additions = [
  'generated_first_200.json',
  'generated_second_part1.json',
  'generated_second_part2.json'
].flatMap((filename) => JSON.parse(fs.readFileSync(path.join(__dirname, filename), 'utf8')));

if (additions.length !== 400) throw new Error(`追加件数が400件ではありません: ${additions.length}`);

const exactPhrases = new Set(existing.map((row) => row.phrase));
const exactReadings = new Map(existing.map((row) => [row.reading, row.phrase]));
for (const row of additions) {
  if (exactPhrases.has(row.phrase)) throw new Error(`既存表現との重複: ${row.phrase}`);
  if (exactReadings.has(row.reading)) throw new Error(`同一読みの重複: ${row.phrase} / ${exactReadings.get(row.reading)}`);
  exactPhrases.add(row.phrase);
  exactReadings.set(row.reading, row.phrase);
}

const numbered = additions.map((row, index) => ({
  id: `jp-${String(1201 + index).padStart(6, '0')}`,
  ...row
}));

for (let part = 0; part < 4; part += 1) {
  const rows = numbered.slice(part * 100, (part + 1) * 100);
  const filename = path.join(dataDir, `vocabulary_${String(13 + part).padStart(3, '0')}.txt`);
  fs.writeFileSync(filename, `${JSON.stringify(rows, null, 2)}\n`);
}

fs.writeFileSync(
  path.join(__dirname, 'vocabulary_id_aliases.json'),
  `${JSON.stringify(idAliases, null, 2)}\n`
);

console.log(`既存 ${existing.length}件（20件統合）+ 新規 ${numbered.length}件 = ${existing.length + numbered.length}件`);
