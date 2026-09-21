import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const outDir='drumscribe/experiments/generated-v2-browser';
await fs.mkdir(outDir,{recursive:true});

const browser=await chromium.launch({headless:true});
const page=await browser.newPage({acceptDownloads:true});
page.setDefaultTimeout(20*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});

for(const song of songs){
  console.log('START',song);
  await page.selectOption('#example',song);
  await page.waitForFunction(() => {
    const b=document.querySelector('#analyze');
    const bpm=document.querySelector('#bpm');
    return b && !b.disabled && bpm && bpm.value;
  });
  console.log('BPM',song,await page.locator('#bpm').inputValue());
  await page.click('#analyze');
  await page.waitForFunction(() => {
    const r=document.querySelector('#result');
    const s=document.querySelector('#status');
    return r && !r.hidden && s && s.textContent.includes('ノートを推定しました');
  },null,{timeout:20*60*1000});
  console.log('RESULT',song,await page.locator('#resultSummary').textContent());
  const dlPromise=page.waitForEvent('download');
  await page.click('#download');
  const dl=await dlPromise;
  const target=path.join(outDir,song+'.mid');
  await dl.saveAs(target);
  console.log('SAVED',target);
}
await browser.close();
