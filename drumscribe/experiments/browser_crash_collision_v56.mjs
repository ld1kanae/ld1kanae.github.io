import { chromium } from 'playwright';
import fs from 'node:fs/promises';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const outDir='drumscribe/experiments/generated-crash-collision-v56';
await fs.mkdir(outDir,{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(20*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/?cymbalVariant=competition-hybrid',{waitUntil:'domcontentloaded'});
for(const song of songs){
  console.log('START',song);
  await page.selectOption('#example',song);
  await page.waitForFunction(()=>{const b=document.querySelector('#analyze');return b&&!b.disabled;});
  await page.click('#analyze');
  await page.waitForFunction(()=>{
    const r=document.querySelector('#result'),s=document.querySelector('#status'),t=s?.textContent||'';
    return (r&&!r.hidden&&t.includes('ノートを推定しました'))||t.includes('採譜できませんでした');
  },null,{timeout:20*60*1000});
  const status=await page.locator('#status').textContent();
  if(status.includes('採譜できませんでした'))throw new Error(song+': '+status);
  const side=await page.evaluate(()=>globalThis.__drumscribeResult||null);
  await fs.writeFile(outDir+'/'+song+'.json',JSON.stringify(side,null,2));
  console.log('DONE',song,side?.adtofInfo?.cymbalPolicy?.crashCompetition?.decisions?.length||0);
}
await browser.close();
