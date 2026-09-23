// Exercise the actual UI and AudioContext in Chromium on the PR branch.
import {chromium} from 'playwright';

const browser=await chromium.launch({headless:true,args:['--autoplay-policy=no-user-gesture-required']});
try{
  const page=await browser.newPage({acceptDownloads:true});
  page.setDefaultTimeout(20*60*1000);
  await page.goto('http://127.0.0.1:8000/drumscribe/',{waitUntil:'domcontentloaded'});
  await page.selectOption('#example','arcaround');
  await page.locator('#analyze').waitFor({state:'visible'});
  await page.waitForFunction(()=>!document.querySelector('#analyze')?.disabled);
  await page.click('#analyze');
  await page.waitForFunction(()=>{
    const status=document.querySelector('#status')?.textContent||'';
    return status.includes('ノートを推定しました')||status.includes('採譜できませんでした');
  });
  const status=await page.locator('#status').textContent();
  if(status.includes('採譜できませんでした'))throw Error(status);
  const info=await page.evaluate(()=>globalThis.__drumscribeResult);
  if(!info||!info.meterInfo?.variableMeterEnabled||info.meterInfo.threeFourBars<1)throw Error('Missing audio-derived 3/4: '+JSON.stringify(info?.meterInfo));
  const download=page.waitForEvent('download');
  await page.locator('#download').click();
  const bytes=await (await download).createReadStream();
  const chunks=[];for await(const chunk of bytes)chunks.push(chunk);
  const midi=Buffer.concat(chunks);
  if(midi.subarray(0,4).toString()!=='MThd')throw Error('Missing MIDI header');
  const signature=Buffer.from([0xff,0x58,0x04,0x03,0x02,0x18,0x08]);
  if(midi.indexOf(signature)<0)throw Error('Missing 3/4 time signature');
  console.log('transcription',info.bpm,info.meterInfo,midi.length);

  await page.goto('http://127.0.0.1:8000/drumscribe/review.html',{waitUntil:'networkidle'});
  await page.selectOption('#song','arcaround');
  await page.selectOption('#candidate','browser-meter-v23');
  await page.waitForFunction(()=>!document.querySelector('#syncPlay')?.disabled);
  await page.locator('#syncPlay').click();
  await page.waitForFunction(()=>{
    const x=window.__drumscribeReviewDebug?.();
    return x&&x.contextState==='running'&&x.loadedSamples>0&&!x.sourcePaused;
  },null,{timeout:30000});
  const playback=await page.evaluate(()=>window.__drumscribeReviewDebug());
  if(playback.candidate!=='browser-meter-v23')throw Error('Wrong review candidate');
  console.log('review playback',playback);
  await page.locator('#stop').click();
}finally{await browser.close();}
