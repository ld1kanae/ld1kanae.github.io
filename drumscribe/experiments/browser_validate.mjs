import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const policy=process.env.KST_POLICY||'baseline';
const outDir=process.env.OUT_DIR||`drumscribe/experiments/gmd-kst/browser-${policy}`;
await fs.mkdir(outDir,{recursive:true});

const browser=await chromium.launch({headless:true});
const page=await browser.newPage({acceptDownloads:true});
page.setDefaultTimeout(20*60*1000);
await page.goto(`http://127.0.0.1:8000/drumscribe/?kstPolicy=${encodeURIComponent(policy)}`,{waitUntil:'domcontentloaded'});
console.log('KST_POLICY',policy);

for(const song of songs){
  console.log('START',song);
  await page.selectOption('#example',song);
  await page.waitForFunction(() => {
    const b=document.querySelector('#analyze');
    return b && !b.disabled;
  });
  console.log('BPM_OVERRIDE',song,await page.locator('#bpm').inputValue());
  await page.click('#analyze');
  await page.waitForFunction(() => {
    const r=document.querySelector('#result');
    const s=document.querySelector('#status');
    const text=s?.textContent||'';
    return (r && !r.hidden && text.includes('ノートを推定しました')) || text.includes('採譜できませんでした');
  },null,{timeout:20*60*1000});
  const status=await page.locator('#status').textContent();
  if(status.includes('採譜できませんでした'))throw new Error(song+': '+status);
  console.log('RESULT',song,await page.locator('#resultSummary').textContent());
  const timing=await page.evaluate(()=>globalThis.__drumscribeResult||null);
  await fs.writeFile(path.join(outDir,song+'.json'),JSON.stringify(timing,null,2));
  console.log('TIMING',song,timing);
  const dlPromise=page.waitForEvent('download');
  await page.click('#download');
  const dl=await dlPromise;
  const target=path.join(outDir,song+'.mid');
  await dl.saveAs(target);
  console.log('SAVED',target);
}
await browser.close();
