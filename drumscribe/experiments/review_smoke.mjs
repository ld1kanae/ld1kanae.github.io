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
await page.selectOption('#candidate','v2-balanced');
await page.waitForFunction(()=>document.querySelector('#candidate')?.value==='v2-balanced'&&!document.querySelector('#saveReview')?.disabled);
await page.waitForFunction(()=>document.querySelectorAll('#metricCards .metric').length>=10);

const midiHref=await page.locator('#midiDownload').getAttribute('href');
if(!midiHref||!midiHref.includes('generated-search-composite-v2/cycle39/c39_crash_balanced/nanairo.mid'))throw new Error('wrong MIDI href: '+midiHref);
const midiResponse=await page.request.get(new URL(midiHref,page.url()).href);
if(!midiResponse.ok())throw new Error('MIDI fetch failed: '+midiResponse.status());
const bytes=await midiResponse.body();
if(bytes.subarray(0,4).toString()!=='MThd')throw new Error('download is not MIDI');

// Playback smoke: click through the real UI, require a running AudioContext,
// decoded drum samples, and at least one scheduled MIDI hit.
await page.locator('#syncPlay').click();
await page.waitForFunction(()=>{
  const d=window.__drumscribeReviewDebug?.();
  return d&&d.contextState==='running'&&d.loadedSamples>0&&!d.sourcePaused;
},{},{timeout:30000});
await page.waitForFunction(()=>{
  const d=window.__drumscribeReviewDebug?.();
  return d&&d.scheduledNotes>0;
},{},{timeout:15000});
const playbackDebug=await page.evaluate(()=>window.__drumscribeReviewDebug());
await page.locator('#stop').click();

// Switch to a different song and prove both the source media and MIDI scheduler
// recover after the source element is replaced.
await page.locator('#stop').click();
await page.selectOption('#song','kaiju');
await page.waitForFunction(()=>document.querySelector('#song')?.value==='kaiju'&&!document.querySelector('#syncPlay')?.disabled);
await page.waitForFunction(()=>document.querySelector('#source')?.dataset?.song==='kaiju'&&document.querySelector('#source')?.readyState>=2);
await page.locator('#syncPlay').click();
await page.waitForFunction(()=>{
  const d=window.__drumscribeReviewDebug?.();
  return d&&d.contextState==='running'&&d.loadedSamples>0&&!d.sourcePaused;
},{},{timeout:30000});
await page.waitForFunction(()=>{
  const d=window.__drumscribeReviewDebug?.();
  return d&&d.scheduledNotes>0;
},{},{timeout:15000});
const switchPlaybackDebug=await page.evaluate(()=>({
  debug:window.__drumscribeReviewDebug(),
  source:document.querySelector('#source')?.currentSrc,
  song:document.querySelector('#song')?.value
}));
if(!switchPlaybackDebug.source.includes('/kaiju/drums.mp3'))throw new Error('song switch kept wrong audio: '+switchPlaybackDebug.source);
await page.locator('#stop').click();

// Candidate switching on the same song must also remain playable.
await page.selectOption('#candidate','tom-ml');
await page.waitForFunction(()=>document.querySelector('#candidate')?.value==='tom-ml'&&!document.querySelector('#syncPlay')?.disabled);
await page.locator('#syncPlay').click();
await page.waitForFunction(()=>window.__drumscribeReviewDebug?.().scheduledNotes>0,{},{timeout:15000});
const candidateSwitchDebug=await page.evaluate(()=>window.__drumscribeReviewDebug());
await page.locator('#stop').click();

await page.selectOption('#song','nanairo');
await page.selectOption('#candidate','v2-balanced');
await page.waitForFunction(()=>document.querySelector('#candidate')?.value==='v2-balanced'&&!document.querySelector('#saveReview')?.disabled);

await page.locator('#overall').fill('5');
await page.locator('#notes').fill('review-smoke-note');
await page.locator('#tags input').first().check();
await page.locator('#saveReview').click();
await page.reload({waitUntil:'networkidle'});
await page.selectOption('#song','nanairo');
await page.selectOption('#candidate','v2-balanced');
await page.waitForFunction(()=>document.querySelector('#candidate')?.value==='v2-balanced'&&!document.querySelector('#saveReview')?.disabled);
await page.waitForFunction(()=>document.querySelector('#notes')?.value==='review-smoke-note');
if(await page.locator('#notes').inputValue()!=='review-smoke-note')throw new Error('review did not persist');
if(await page.locator('#overall').inputValue()!=='5')throw new Error('rating did not persist');

console.log('review smoke OK',{songCount,candidateCount,midiBytes:bytes.length,playbackDebug,switchPlaybackDebug,candidateSwitchDebug});
await browser.close();
