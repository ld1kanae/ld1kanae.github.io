import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const variant='ride-open-decay-rescue';
const root='drumscribe/experiments/generated-openhat-combined-v44';
await fs.mkdir(root,{recursive:true});

const browser=await chromium.launch({headless:true});
const page=await browser.newPage({acceptDownloads:true});
page.setDefaultTimeout(20*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/?openHatVariant='+variant,{waitUntil:'domcontentloaded'});
for(const song of songs){
  console.log('START',song);
  await page.selectOption('#example',song);
  await page.waitForFunction(()=>{const b=document.querySelector('#analyze');return b&&!b.disabled;});
  await page.click('#analyze');
  await page.waitForFunction(()=>{
    const r=document.querySelector('#result'),s=document.querySelector('#status');
    const t=s?.textContent||'';
    return (r&&!r.hidden&&t.includes('ノートを推定しました'))||t.includes('採譜できませんでした');
  },null,{timeout:20*60*1000});
  const status=await page.locator('#status').textContent();
  if(status.includes('採譜できませんでした'))throw new Error(song+': '+status);
  const timing=await page.evaluate(()=>globalThis.__drumscribeResult||null);
  await fs.writeFile(path.join(root,song+'.json'),JSON.stringify(timing,null,2));
  const dlPromise=page.waitForEvent('download');
  await page.click('#download');
  const dl=await dlPromise;
  await dl.saveAs(path.join(root,song+'.mid'));
  console.log('DONE',song,timing?.adtofInfo?.openHat||null);
}
await browser.close();
