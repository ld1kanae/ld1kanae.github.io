import { chromium } from 'playwright';

const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:900,height:700}});
const errors=[];
page.on('console',msg=>{if(msg.type()==='error')errors.push('console: '+msg.text())});
page.on('pageerror',err=>errors.push('pageerror: '+String(err)));

await page.addInitScript(()=>{
  class FakeSpeechRecognition {
    constructor(){this.lang='';this.continuous=false;this.interimResults=false;this.maxAlternatives=1;}
    start(){
      this.onstart?.();
      setTimeout(()=>{
        const result=[{transcript:'スネアのタイミングを確認してください'}];
        result.isFinal=true;
        this.onresult?.({resultIndex:0,results:[result]});
      },20);
    }
    stop(){this.onend?.();}
    abort(){this.onend?.();}
  }
  window.SpeechRecognition=FakeSpeechRecognition;
  window.webkitSpeechRecognition=FakeSpeechRecognition;
});

const url=process.env.DRUMSCRIBE_FEEDBACK_URL||'http://127.0.0.1:8000/drumscribe/feedback.html';
await page.goto(url,{waitUntil:'domcontentloaded',timeout:60000});
await page.waitForSelector('#reviewVoice',{state:'attached'});

await page.evaluate(()=>{document.querySelector('#result').hidden=false;document.querySelector('#reviewPopover').hidden=false});
await page.fill('#reviewText','既存レビュー');
const mic=page.locator('#reviewVoice');
if(await mic.isDisabled())throw new Error('voice input button is disabled despite SpeechRecognition support');
await mic.click();
await page.waitForFunction(()=>document.querySelector('#reviewText')?.value.includes('スネアのタイミングを確認してください'),{},{timeout:3000});

const active=await page.evaluate(()=>({
  value:document.querySelector('#reviewText')?.value,
  pressed:document.querySelector('#reviewVoice')?.getAttribute('aria-pressed'),
  label:document.querySelector('#reviewVoice')?.textContent,
  status:document.querySelector('#reviewStatus')?.textContent
}));
console.log('VOICE_ACTIVE',JSON.stringify(active));
if(!active.value?.startsWith('既存レビュー'))throw new Error('existing review text was replaced');
if(!active.value?.includes('スネアのタイミングを確認してください'))throw new Error('recognized speech was not appended');
if(active.pressed!=='true')throw new Error('voice input did not enter active state');

await mic.click();
await page.waitForFunction(()=>document.querySelector('#reviewVoice')?.getAttribute('aria-pressed')==='false',{},{timeout:1000});
const stopped=await page.evaluate(()=>({
  value:document.querySelector('#reviewText')?.value,
  pressed:document.querySelector('#reviewVoice')?.getAttribute('aria-pressed'),
  label:document.querySelector('#reviewVoice')?.textContent
}));
console.log('VOICE_STOPPED',JSON.stringify(stopped));
if(stopped.value!==active.value)throw new Error('stopping voice input changed the transcript');
if(errors.length)throw new Error(errors.join(' | '));

await browser.close();
