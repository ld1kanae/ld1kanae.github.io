import { chromium } from 'playwright';

const browser=await chromium.launch({headless:true,args:['--autoplay-policy=no-user-gesture-required']});
const page=await browser.newPage();
const consoleErrors=[];
page.on('console',msg=>{ if(msg.type()==='error') consoleErrors.push(msg.text()); });
page.on('pageerror',err=>consoleErrors.push(String(err)));

const url=process.env.DRUMSCRIBE_REVIEW_URL||'http://127.0.0.1:8000/drumscribe/review.html';
console.log('URL',url);
await page.goto(url,{waitUntil:'domcontentloaded'});
await page.waitForFunction(()=>document.querySelector('#candidate')?.options.length>0,{},{timeout:30000});

const selected=await page.locator('#candidate').inputValue();
const status0=await page.locator('#status').textContent();
console.log('SELECTED',selected);
console.log('STATUS0',status0);

await page.waitForFunction(()=>{
  const s=document.querySelector('#status')?.textContent||'';
  return s.includes('準備完了')||s.includes('失敗')||s.includes('エラー');
},{},{timeout:30000});

console.log('READY',await page.locator('#status').textContent());
console.log('DEBUG_BEFORE',await page.evaluate(()=>window.__drumscribeReviewDebug?.()));

await page.click('#syncPlay');
await page.waitForTimeout(5000);

const debug=await page.evaluate(()=>window.__drumscribeReviewDebug?.());
const status=await page.locator('#status').textContent();
console.log('STATUS_AFTER',status);
console.log('DEBUG_AFTER',debug);
console.log('CONSOLE_ERRORS',consoleErrors);

if(selected!=='browser-c225-227') throw new Error('latest candidate is not default: '+selected);
if(!debug || debug.eventCount<=0) throw new Error('latest MIDI has no events');
if(debug.loadedSamples<=0) throw new Error('no MIDI samples loaded');
if(debug.scheduledNotes<=0) throw new Error('no MIDI notes scheduled');
if(consoleErrors.length) throw new Error('browser errors: '+consoleErrors.join(' | '));

await browser.close();
