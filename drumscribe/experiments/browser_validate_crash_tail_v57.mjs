import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const variants=['legacy','collision-lowmid-final','collision-lowmid-struct','collision-lowmid-run'];
const root='drumscribe/experiments/generated-crash-tail-v57';
await fs.mkdir(root,{recursive:true});

const browser=await chromium.launch({headless:true});
for(const variant of variants){
  const outDir=path.join(root,variant);
  await fs.mkdir(outDir,{recursive:true});
  const page=await browser.newPage({acceptDownloads:true});
  page.setDefaultTimeout(20*60*1000);
  await page.goto('http://127.0.0.1:8000/drumscribe/?cymbalVariant='+encodeURIComponent(variant),{waitUntil:'domcontentloaded'});
  for(const song of songs){
    console.log('START',variant,song);
    await page.selectOption('#example',song);
    await page.waitForFunction(()=>{const b=document.querySelector('#analyze');return b&&!b.disabled;});
    await page.click('#analyze');
    await page.waitForFunction(()=>{
      const r=document.querySelector('#result'),s=document.querySelector('#status'),t=s?.textContent||'';
      return (r&&!r.hidden&&t.includes('ノートを推定しました'))||t.includes('採譜できませんでした');
    },null,{timeout:20*60*1000});
    const status=await page.locator('#status').textContent();
    if(status.includes('採譜できませんでした'))throw new Error(variant+'/'+song+': '+status);
    const side=await page.evaluate(()=>globalThis.__drumscribeResult||null);
    await fs.writeFile(path.join(outDir,song+'.json'),JSON.stringify(side,null,2));
    const dlPromise=page.waitForEvent('download');
    await page.click('#download');
    const dl=await dlPromise;
    await dl.saveAs(path.join(outDir,song+'.mid'));
    console.log('DONE',variant,song,side?.adtofInfo?.cymbalPolicy?.crashTailCompetition||null);
  }
  await page.close();
}
await browser.close();
