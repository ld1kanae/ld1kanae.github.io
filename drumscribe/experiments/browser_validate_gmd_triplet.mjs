import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const root=process.cwd();
const dataDir=path.join(root,'drumscribe/experiments/gmd-triplet-heldout-v32');
const manifest=JSON.parse(await fs.readFile(path.join(dataDir,'manifest.json'),'utf8'));
const outDir=path.join(dataDir,'generated');
await fs.mkdir(outDir,{recursive:true});

const browser=await chromium.launch({headless:true});
const page=await browser.newPage({acceptDownloads:true});
page.setDefaultTimeout(20*60*1000);

for(const item of manifest.cases){
  for(const mode of ['auto','oracle_bpm']){
    await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
    const audioPath=path.resolve(root,item.local_audio);
    await page.setInputFiles('#file',audioPath);
    await page.waitForFunction(()=>{
      const b=document.querySelector('#analyze');
      return b && !b.disabled;
    });
    if(mode==='oracle_bpm')await page.locator('#bpm').fill(String(item.bpm));
    console.log('START',item.case_id,mode,item.style,item.split,item.bpm);
    await page.click('#analyze');
    await page.waitForFunction(()=>{
      const r=document.querySelector('#result');
      const s=document.querySelector('#status');
      const text=s?.textContent||'';
      return (r && !r.hidden && text.includes('ノートを推定しました')) || text.includes('採譜できませんでした');
    },null,{timeout:20*60*1000});
    const status=await page.locator('#status').textContent();
    if(status.includes('採譜できませんでした'))throw new Error(`${item.case_id}/${mode}: ${status}`);
    const summary=await page.locator('#resultSummary').textContent();
    const timing=await page.evaluate(()=>globalThis.__drumscribeResult||null);
    const stem=`${item.case_id}-${mode}`;
    await fs.writeFile(path.join(outDir,stem+'.json'),JSON.stringify({item,mode,summary,timing},null,2));
    const dlPromise=page.waitForEvent('download');
    await page.click('#download');
    const dl=await dlPromise;
    await dl.saveAs(path.join(outDir,stem+'.mid'));
    console.log('RESULT',item.case_id,mode,summary,timing?.rhythmGridInfo);
  }
}

await browser.close();
