import { chromium } from 'playwright';

const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
page.setDefaultTimeout(30000);
await page.goto('http://127.0.0.1:8000/drumscribe/review.html',{waitUntil:'networkidle'});

const songCount=await page.locator('#song option').count();
const candidateCount=await page.locator('#candidate option').count();
if(songCount<5)throw new Error('song options missing: '+songCount);
if(candidateCount<3)throw new Error('candidate options missing: '+candidateCount);

await page.selectOption('#song','nanairo');
await page.selectOption('#candidate','crash-ml');
await page.waitForFunction(()=>document.querySelector('#candidate')?.value==='crash-ml'&&!document.querySelector('#saveReview')?.disabled);
await page.waitForFunction(()=>document.querySelectorAll('#metricCards .metric').length>=10);

const midiHref=await page.locator('#midiDownload').getAttribute('href');
if(!midiHref||!midiHref.includes('generated-search-ml/cycle15/c15_head_015/nanairo.mid'))throw new Error('wrong MIDI href: '+midiHref);
const midiResponse=await page.request.get(new URL(midiHref,page.url()).href);
if(!midiResponse.ok())throw new Error('MIDI fetch failed: '+midiResponse.status());
const bytes=await midiResponse.body();
if(bytes.subarray(0,4).toString()!=='MThd')throw new Error('download is not MIDI');

await page.locator('#overall').fill('5');
await page.locator('#notes').fill('review-smoke-note');
await page.locator('#tags input').first().check();
await page.locator('#saveReview').click();
await page.reload({waitUntil:'networkidle'});
await page.selectOption('#song','nanairo');
await page.selectOption('#candidate','crash-ml');
await page.waitForFunction(()=>document.querySelector('#candidate')?.value==='crash-ml'&&!document.querySelector('#saveReview')?.disabled);
await page.waitForFunction(()=>document.querySelector('#notes')?.value==='review-smoke-note');
if(await page.locator('#notes').inputValue()!=='review-smoke-note')throw new Error('review did not persist');
if(await page.locator('#overall').inputValue()!=='5')throw new Error('rating did not persist');

console.log('review smoke OK',{songCount,candidateCount,midiBytes:bytes.length});
await browser.close();
