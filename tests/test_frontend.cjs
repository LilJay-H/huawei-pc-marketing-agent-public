/* Optional browser regression suite: NODE_PATH must resolve Playwright; Edge is used by default.
   Start python server.py first. All generated drafts below are synthetic test fixtures. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const output = path.resolve('.runtime/ui-checks');
fs.mkdirSync(output, {recursive:true});
const base = 'http://127.0.0.1:8765';
(async () => {
 const browser = await chromium.launch({channel: process.env.BROWSER_CHANNEL || 'msedge', headless:true});
 const context = await browser.newContext({viewport:{width:1440,height:1050}, reducedMotion:'reduce', permissions:['clipboard-read','clipboard-write']});
 const page = await context.newPage(); const errors = []; page.on('pageerror', e => errors.push(e.message));
 const reports = [];
 const check = async (name, fn) => { await fn(); reports.push(name); console.log('PASS ' + name); };
 try {
 await page.goto(base); await page.locator('#generate').waitFor({state:'visible'});
 await page.waitForFunction(() => !document.querySelector('#generate').disabled && document.querySelector('#products').options.length > 0);
 const products = await page.locator('#products option').evaluateAll(nodes => nodes.map(n=>n.value));
 const config = await (await context.request.get(base+'/api/config')).json();
 await check('Live configuration, choices and products', async()=>{
  assert.equal(await page.locator('[name="scene"]').count(), Object.keys(config.scenes).length);
  assert.equal(await page.locator('[name="platform"]').count(), Object.keys(config.platforms).length);
  assert.ok(products.length > 0); assert.match(await page.locator('#sourceBadge').innerText(), /待确认/);
  if (!config.model_configured) {
   assert.ok(await page.locator('#setupNotice').isVisible());
   assert.match(await page.locator('#generate').innerText(),/模型待配置/);
  }
 });
 await check('Empty layout at 375, 768, 1024 and 1440 pixels', async()=>{
  for (const width of [375,768,1024,1440]) {
   await page.setViewportSize({width,height:1050});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth), 'overflow at '+width);
   await page.evaluate(()=>window.scrollTo(0,0));
   await page.screenshot({path:path.join(output,`empty-${width}.png`),fullPage:true});
  }
 });
 await check('Live local retrieval and real image endpoint', async()=>{
  await page.locator('#product').fill(products[0]);
  await page.locator('#retrieve').click(); await page.locator('#evidence').waitFor();
  assert.match(await page.locator('#sourceBadge').innerText(), /本地 v7/);
  assert.ok(await page.locator('#evidence details').count()>0);
  await page.locator('#evidence img').first().scrollIntoViewIfNeeded();
  await page.waitForFunction(()=>[...document.querySelectorAll('#evidence img')].some(i=>i.complete&&i.naturalWidth>0));
  assert.equal(await page.locator('#exports').isVisible(), false);
  await page.screenshot({path:path.join(output,'live-retrieval.png'),fullPage:true});
 });
 const liveTask = await page.locator('#task').evaluate(form=>Object.fromEntries(new FormData(form)));
 const realImage = await page.locator('#evidence img').first().getAttribute('src');
 if (!config.model_configured) await check('Live generation reports missing model without inventing a draft',async()=>{
  await page.locator('#generate').click();
  await page.waitForFunction(()=>document.querySelector('#loading').hidden && document.querySelector('#status').textContent.includes('文案模型待配置'));
  assert.equal(await page.locator('#article').count(),0);
  assert.ok(await page.locator('#evidence').isVisible());
  assert.match(await page.locator('#resultMeta').innerText(),/已结束.*正文未生成/);
  assert.match(await page.locator('.output-summary').innerText(),/核验未执行/);
 });
 await check('Configuration refresh preserves task and enables writing when configured',async()=>{
  await page.route('**/api/config',route=>route.fulfill({json:{...config,model_configured:true,model_missing_fields:[]}}));
  if (!config.model_configured) {
   await page.locator('#refreshConfig').click();
   await page.waitForFunction(()=>document.querySelector('#setupNotice').hidden);
   assert.equal(await page.locator('#product').inputValue(),liveTask.product);
   assert.equal(await page.locator('#generate').innerText(),'检索并生成图文');
  }
 });
 const fixture = {
  status:'checked_draft',run_id:'synthetic-ui-test',mode:'local_development',started_at:'2026-10-18T00:00:00Z', source_kind:'local_v7',
  task:liveTask,source_note:'测试夹具 · 仅用于界面验收，不代表产品事实。',
  strategy:{angle:'从每天换教室的真实需求，找到内容切入点',pain:'每天带电脑上课，担心携带负担。',focus:['携带','学习'],style:'具体场景、短段落、保留使用条件',ask:'专业与必用软件是什么？'},
  documents:[{id:'D1',title:'产品事实（测试夹具）',source:'合成验收资料',text:'这是一段用于验证页面渲染的原文。'}],
  facts:[{source_id:'D1',claim:'仅用于验证页面渲染',conditions:'测试数据'}],
  images:[{id:'I1',title:'配图渲染测试',source:'仓库本地素材',url:realImage}],
  draft:{markdown:'# 从教室到图书馆，把需求想清楚\n\n选电脑之前，先看自己一天会在哪些地方使用它。\n\n## 先问自己三个问题\n\n- **携带**：每天需要背多久？\n- **学习**：有哪些必用软件？\n- **使用条件**：教室是否方便充电？\n\n> 此文为浏览器验收夹具，不是产品推荐。\n\n<img src=x onerror="window.__injected=1">',strategy_reason:'这是用于验证界面呈现的合成数据。',image_plan:[{image_id:'I1',position:'正文后',caption:'配图位置测试'}],pending:['确认实际软件版本与使用条件'],claims:[]},
  verification:{facts:[{claim:'仅用于验证页面渲染',status:'quote_matched',source_id:'D1',quote:'这是一段用于验证页面渲染的原文。'}],images:[{image_id:'I1',title:'配图渲染测试',status:'catalog_match',reason:'索引一致，画面和授权仍需人工确认'}],compliance:[]},
  publish_precheck:{status:'text_review_complete',findings:[],rule_review_due:[],not_checked:['图片像素','平台规则实时核验']},issues:[],warnings:[],trace:[{step:'测试',status:'done',detail:'合成验收数据'}]
 };
 let response = structuredClone(fixture), responseMode = 'ok', delayResolve;
 await page.route('**/api/generate',async route=>{
   if(responseMode==='delay'){ await new Promise(resolve=>{delayResolve=resolve}); return route.abort().catch(()=>{}); }
   if(responseMode==='error')return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'合成测试：服务暂不可用'})});
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(response)});
 });
 await check('Four result sections, safe Markdown and copy/export',async()=>{
  await page.locator('#requirements').fill('刚输入需求，第一次点击必须提交');
  await page.locator('#generate').click(); await page.locator('#article').waitFor();
  for(const id of ['strategy','evidence','article','verification'])assert.ok(await page.locator('#'+id).isVisible());
  assert.equal(await page.locator('.article-content img').count(),0);assert.equal(await page.evaluate(()=>window.__injected),undefined);
  assert.ok(await page.locator('.article-content strong').count()>=3);
  await page.locator('#copy').click();assert.equal((await page.evaluate(()=>navigator.clipboard.readText())).replace(/\r\n/g,'\n'),fixture.draft.markdown);
  const downloadPromise=page.waitForEvent('download');await page.locator('#download').click();const download=await downloadPromise;
  assert.equal(fs.readFileSync(await download.path(),'utf8'),fixture.draft.markdown);
  const auditPromise=page.waitForEvent('download');await page.locator('#auditExport').click();const audit=await auditPromise;
  const report=JSON.parse(fs.readFileSync(await audit.path(),'utf8'));assert.equal(report.run_id,fixture.run_id);assert.equal(report.images,undefined);
  await page.locator('#product').fill('另一型号');assert.equal(await page.locator('#rewrite').isDisabled(),true);
  await page.locator('#product').fill(liveTask.product);assert.equal(await page.locator('#rewrite').isDisabled(),false);
 });
 await check('HTTP-compatible copying and asynchronous job completion',async()=>{
  await page.evaluate(()=>{window.testClipboard=navigator.clipboard;Object.defineProperty(navigator,'clipboard',{value:undefined,configurable:true});});
  await page.locator('#copy').click();
  assert.match(await page.locator('#status').innerText(),/已复制文案/);
  assert.equal((await page.evaluate(()=>window.testClipboard.readText())).replace(/\r\n/g,'\n'),fixture.draft.markdown);
  await page.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{value:window.testClipboard,configurable:true});delete window.testClipboard;});
  const jobId='1234567890abcdef1234567890abcdef';let polls=0;
  response={status:'queued',job_id:jobId,ahead:1};
  await page.route('**/api/jobs/'+jobId,route=>route.fulfill({json:++polls===1?{status:'running',job_id:jobId}:{status:'completed',job_id:jobId,result:fixture}}));
  await page.locator('#generate').click();
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('排队'));
  await page.waitForFunction(()=>document.querySelector('#loading').hidden);
  assert.equal(polls,2);assert.ok(await page.locator('#article').isVisible());
  response=structuredClone(fixture);
 });
 await check('Risk findings and mismatched image are visible',async()=>{
  response=structuredClone(fixture);response.status='needs_review';response.verification.facts[0].status='unverified';response.verification.images[0].status='mismatch';response.issues=['事实缺乏证据，需要人工复核'];
  response.publish_precheck={...response.publish_precheck,status:'needs_review',findings:[{text:'绝对领先',decision:'revise',reason:'缺少比较证据',suggestion:'改为有资料支持的功能描述'}]};
  await page.locator('#generate').click();await page.waitForFunction(()=>document.querySelector('#result').textContent.includes('缺少比较证据'));
  assert.ok(await page.locator('.notice.danger').isVisible());assert.match(await page.locator('#verification').innerText(),/型号不符/);
  for(const width of [375,768,1024,1440]){
   await page.setViewportSize({width,height:1050});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'result overflow at '+width);
   await page.evaluate(()=>window.scrollTo(0,0));
   await page.screenshot({path:path.join(output,`result-${width}.png`),fullPage:true});
  }
 });
 await check('Failure preserves prior result; retry completes',async()=>{
  responseMode='error';await page.locator('#generate').click();await page.locator('#requestError').waitFor();
  assert.ok(await page.locator('#article').isVisible());assert.ok(await page.locator('#exports').isVisible());
  responseMode='ok';response=structuredClone(fixture);await page.locator('#retry').click();await page.waitForFunction(()=>!document.querySelector('#loading').hidden===false && document.querySelector('#requestError').hidden);
  assert.ok(await page.locator('#article').isVisible());
 });
 await check('Loading state, duplicate prevention and cancellation',async()=>{
  responseMode='delay';await page.locator('#generate').click();await page.locator('#loading').waitFor();
  assert.ok(await page.locator('#generate').isDisabled());assert.ok(await page.locator('#product').isDisabled());
  await page.locator('#cancel').click();await page.waitForFunction(()=>document.querySelector('#loading').hidden);delayResolve?.();responseMode='ok';
  assert.ok(await page.locator('#article').isVisible());assert.match(await page.locator('#status').innerText(),/停止等待/);
 });
 await check('Snapshot rewrite and source badge',async()=>{
  await page.route('**/api/rewrite',async route=>{
   const posted=route.request().postDataJSON();assert.equal(posted.run_id,fixture.run_id);assert.equal(posted.product,liveTask.product);
   await route.fulfill({json:{...fixture,mode:'snapshot_rewrite',source_kind:'ima_live'}});
  });
  await page.locator('#rewrite').click();await page.waitForFunction(()=>document.querySelector('#sourceBadge').textContent.includes('快照'));
  assert.match(await page.locator('#sourceBadge').innerText(),/ima.*快照/);
 });
 await check('Clarification, blocked, failed and model-required responses',async()=>{
  for(const status of ['needs_input','blocked','failed','model_required']){
   response={status,run_id:'synthetic-'+status,questions:['请补充软件与版本'],...(status==='model_required'?{documents:[],source_kind:'local_v7'}:{}),...(status==='failed'?{error:'合成流程失败'}:{})};
   await page.locator('#generate').click();await page.waitForFunction(()=>document.querySelector('#loading').hidden);
   assert.equal(await page.locator('#article').count(),0);assert.equal(await page.locator('#exports').isVisible(),false);
   assert.match(await page.locator('#result').innerText(),/请补充软件与版本/);
  }
 });
 await check('Hidden required field is opened for validation',async()=>{
  await page.locator('.advanced summary').click();await page.locator('#audience').fill('');await page.locator('.advanced summary').click();
  await page.locator('#generate').click();assert.ok(await page.locator('.advanced').getAttribute('open')!==null);await page.locator('#audience').fill('测试学生');
 });
 await check('Config failure has a working retry',async()=>{
  await page.route('**/api/config',route=>route.fulfill({status:503,json:{error:'配置测试错误'}}));
  await page.reload();await page.locator('#retryConfig').waitFor();assert.ok(await page.locator('#generate').isDisabled());
  await page.unroute('**/api/config');await page.locator('#retryConfig').click();await page.waitForFunction(()=>!document.querySelector('#generate').disabled);
 });
 await check('Reduced motion and zero uncaught browser errors',async()=>{
  assert.equal(await page.locator('.art-window').evaluate(n=>getComputedStyle(n).animationName),'none');assert.deepEqual(errors,[]);
 });
 await check('Keyboard radio navigation, skip link and narrow landscape',async()=>{
  await page.locator('[name="scene"]').first().focus();await page.keyboard.press('ArrowRight');
  assert.ok(await page.locator('[name="scene"]').nth(1).isChecked());
  await page.locator('.skip-link').focus();await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'workspace');
  await page.setViewportSize({width:667,height:375});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 });
 fs.writeFileSync(path.join(output,'report.json'),JSON.stringify({passed:reports,errors,realProducts:products.length,generatedDrafts:'synthetic fixtures only'},null,2));
 console.log('All '+reports.length+' browser checks passed. Screenshots: '+output);
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
