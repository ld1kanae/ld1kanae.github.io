import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const songs=['arcaround','diamondvirgin','kaiju','nanairo','ray'];
const outDir='drumscribe/experiments/generated-arrangement-app-v48';
await fs.mkdir(outDir,{recursive:true});

const browser=await chromium.launch({headless:true});
const page=await browser.newPage({acceptDownloads:true});
page.setDefaultTimeout(30*60*1000);
await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>Boolean(globalThis.ort));

for(const song of songs){
  console.log('START',song);
  await page.selectOption('#example',song);
  await page.waitForFunction(()=>{
    const b=document.querySelector('#analyze');
    const name=document.querySelector('#arrangementFileName')?.textContent||'';
    return b&&!b.disabled&&name.includes('offvocal');
  });
  await page.click('#analyze');
  await page.waitForFunction(()=>{
    const s=document.querySelector('#status')?.textContent||'';
    return s.includes('ノートを推定しました')||s.includes('採譜できませんでした');
  });
  const status=await page.locator('#status').textContent();
  if(status.includes('採譜できませんでした'))throw new Error(song+': '+status);

  const side=await page.evaluate(()=>globalThis.__drumscribeResult||null);
  if(!side?.arrangementInfo?.enabled)throw new Error(song+': arrangement assist not enabled');
  if(side.arrangementInfo?.rescore?.policy?.name!=='family-gmd-plus-egmd-residual-v46r1'){
    throw new Error(song+': wrong production policy '+JSON.stringify(side.arrangementInfo?.rescore?.policy?.name));
  }
  await fs.writeFile(path.join(outDir,song+'.json'),JSON.stringify(side,null,2)+'\n');

  const dlPromise=page.waitForEvent('download');
  await page.click('#download');
  const dl=await dlPromise;
  await dl.saveAs(path.join(outDir,song+'.mid'));
  console.log('DONE',song,{
    policy:side.arrangementInfo.rescore.policy.name,
    accepted:side.arrangementInfo.rescore.accepted,
    arrangement:side.arrangementInfo.rescore.acceptedArrangement,
    egmdResidual:side.arrangementInfo.rescore.acceptedEgmdResidual,
    meter:side.meterInfo,
    grid:side.rhythmGridInfo?.subdivision,
  });
}
await browser.close();
