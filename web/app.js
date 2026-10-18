'use strict';
const $ = selector => document.querySelector(selector);
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
};
const icons = {
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 12 3 3 5-6"/>',
  sparkles: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/><path d="M20 2v4m-2-2h4"/>',
  sliders: '<path d="M4 6h7m4 0h5M4 12h2m4 0h10M4 18h10m4 0h2"/><circle cx="13" cy="6" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="16" cy="18" r="2"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
  bulb: '<path d="M9 18h6m-5 3h4M8 14a7 7 0 1 1 8 0l-1 2H9z"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m16 8-3 5-5 3 3-5z"/>',
  book: '<path d="M12 5C8 2 3 4 3 4v15s5-2 9 1c4-3 9-1 9-1V4s-5-2-9 1zm0 0v15"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 7a7.5 7.5 0 0 1 13-1L20 12M4 12l1.5 6a7.5 7.5 0 0 0 13-1"/>',
  warning: '<path d="m12 3 10 18H2zM12 9v5m0 3v.1"/>'
};
function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('class', 'icon'); svg.setAttribute('aria-hidden', 'true');
  // Only static, locally authored SVG paths enter this sink. API text always uses textContent.
  svg.innerHTML = icons[name] || icons.book;
  return svg;
}
document.querySelectorAll('[data-icon]').forEach(node => {
  if (node.className) node.replaceChildren(icon(node.dataset.icon));
  else node.replaceWith(icon(node.dataset.icon));
});
let config, lastResult, markdown = '', activeRequest = null, retryAction = null, productRequest = 0;
const form = $('#task');
const statusNames = {
  needs_input: '还需要一点信息', retrieved: '产品资料已就绪', model_required: '检索已完成，正文未生成：文案模型待配置',
  blocked: '资料存在缺口，已停止生成', needs_review: '草稿已生成，有内容待复核',
  checked_draft: '已完成本次检查，发布前请人工确认', failed: '本次创作未完成'
};
function setStatus(text) { $('#status').textContent = text; }
function task() { return Object.fromEntries(new FormData(form)); }
function syncControls() {
  const busy = !!activeRequest;
  $('#taskFields').disabled = busy || !config;
  $('#source_mode').disabled = busy || !config;
  for (const id of ['generate', 'retrieve', 'connect']) $('#' + id).disabled = busy || !config;
  for (const id of ['copy', 'download', 'auditExport']) $('#' + id).disabled = busy || !lastResult?.draft;
  $('#retry').disabled = busy; $('#retryConfig').disabled = busy; $('#refreshConfig').disabled = busy;
  const changed = lastResult?.draft && ['product', 'version', 'source_mode'].some(k => (task()[k] || '') !== (lastResult.task?.[k] || (k === 'source_mode' ? 'ima' : '')));
  $('#rewrite').disabled = busy || !lastResult?.draft || !!changed;
  $('#rewriteHint').hidden = !changed;
  $('#rewriteHint').textContent = '型号、版本或资料来源已改变，请重新检索并生成；改写只能复用原稿的证据。';
  const unavailable = config && !config.model_configured;
  const generateLabel = busy ? '正在处理…' : unavailable ? '检索资料（模型待配置）' : '检索并生成图文';
  // An input's blur/change can fire between mousedown and click on this button.
  // Preserve its children when the label is unchanged so that click is not lost.
  if ($('#generate').textContent.trim() !== generateLabel) {
    $('#generate').replaceChildren(icon(unavailable ? 'search' : 'sparkles'), el('span', generateLabel), icon('arrow'));
  }
  $('#generationReadiness').hidden = !unavailable;
  $('#generationReadiness').textContent = '文案模型未配置，本次只能读取资料，不能生成正文。';
  $('#generationTiming').textContent = unavailable ? '完成模型配置并重启服务后，即可生成图文' : '生成与审稿可能需要数分钟';
  $('#setupNotice').hidden = !unavailable;
  const fields = config?.model_missing_fields || ['LLM_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL'];
  $('#missingFields').textContent = '当前缺少配置项：' + fields.join('、');
}
async function request(path, body, signal) {
  const response = await fetch(path, body === undefined ? { signal } : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal
  });
  let data;
  try { data = await response.json(); } catch { throw new Error('服务返回了无法读取的数据，请确认后端正常运行后重试。'); }
  if (!response.ok) throw new Error(data.error || '服务请求失败（' + response.status + '），请稍后重试。');
  return data;
}
async function awaitJob(data, signal) {
  if (!data?.job_id) return data;
  if (!/^[a-f0-9]{32}$/.test(data.job_id)) throw new Error('服务返回的任务编号无效。');
  const jobPath = '/api/jobs/' + data.job_id;
  while (data.status !== 'completed') {
    setStatus(data.status === 'queued' ? '正在排队，前面还有 ' + (data.ahead || 0) + ' 个任务。请保留此页面。' : '正在生成与核验，请保留此页面…');
    await new Promise((resolve, reject) => {
      if (signal.aborted) return reject(new DOMException('已停止等待', 'AbortError'));
      const abort = () => { clearTimeout(timer); reject(new DOMException('已停止等待', 'AbortError')); };
      const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, 1500);
      signal.addEventListener('abort', abort, {once:true});
    });
    data = await request(jobPath, undefined, signal);
    if (!['queued', 'running', 'completed'].includes(data.status)) throw new Error('任务状态无效，请检查服务。');
  }
  return data.result;
}
function errorMessage(error) {
  return error instanceof TypeError ? '无法连接后端服务，请在项目目录运行 python server.py 后重试。' : error.message;
}
function showError(error) {
  $('#errorText').textContent = errorMessage(error);
  $('#requestError').hidden = false;
  setStatus('请求未完成。已保留输入' + (lastResult ? '和上一份结果。' : '。'));
}
function sourceBadge(result) {
  const badge = $('#sourceBadge');
  const mode = result.source_kind === 'local_v7' ? 'local' : result.source_kind === 'ima_live' ? 'ima' : null;
  badge.className = 'source-badge' + (mode ? ' ' + mode : '');
  badge.replaceChildren(el('i'), el('span', mode ? '结果来源：' + (mode === 'local' ? '本地 v7' : 'ima') + (result.mode === 'snapshot_rewrite' ? ' · 快照' : '') : '本次未取得资料'));
}
function choices(container, name, values) {
  container.replaceChildren();
  values.forEach((value, i) => {
    const label = el('label', undefined, 'chip');
    const input = el('input'); input.type = 'radio'; input.name = name; input.value = value; input.checked = i === 0; input.required = true;
    const caption = el('span');
    if (name === 'platform') {
      const dot = el('i', undefined, 'platform-dot ' + ({ '小红书': 'xhs', '公众号': 'wechat', '朋友圈': 'moments' }[value] || ''));
      caption.append(dot);
    }
    caption.append(document.createTextNode(value)); label.append(input, caption); container.append(label);
  });
}
function sceneChanged() {
  const scene = form.elements.scene?.value;
  $('#sceneHint').textContent = config.scenes[scene]?.ask || '选择一个校园场景。';
  const select = $('#micro_scene_id'); select.replaceChildren(new Option('按任务自动匹配', ''));
  (config.micro_scenes || []).filter(x => x.broad_scenes.includes(scene)).forEach(x => select.append(new Option(x.label, x.id)));
}
async function sourceChanged() {
  const sequence = ++productRequest;
  const local = $('#source_mode').value === 'local';
  $('#sourceHint').textContent = local ? '读取仓库本地 v7，非实时 ima 结果；生成与审稿仍需模型服务。' : '读取指定 ima 共享库，不会自动切换为本地资料。';
  $('#products').replaceChildren();
  $('#productHint').textContent = local ? '正在读取本地型号列表…' : '请输入 ima 知识库内的准确型号';
  if (local) {
    try {
      const data = await request('/api/products', undefined, AbortSignal.timeout(20000));
      if (sequence !== productRequest) return;
      if (!Array.isArray(data.products)) throw new Error('型号列表格式无效，请重新测试资料连接。');
      data.products.forEach(p => $('#products').append(new Option(p, p)));
      $('#productHint').textContent = data.products.length ? '已读取 ' + data.products.length + ' 个型号，可输入名称筛选' : '本地资料中没有可用型号，请检查资料目录';
    } catch (error) {
      if (sequence !== productRequest) return;
      $('#productHint').textContent = errorMessage(error);
    }
  }
  syncControls();
}
async function initialize() {
  const previous = config ? task() : null;
  $('#retryConfig').hidden = true;
  $('#connection').textContent = '正在检查配置…';
  try {
    const data = await request('/api/config', undefined, AbortSignal.timeout(20000));
    if (!data.scenes || !Object.keys(data.scenes).length || !data.platforms || !Object.keys(data.platforms).length) throw new Error('服务配置缺少场景或平台，请检查后端。');
    config = data;
    choices($('#sceneChoices'), 'scene', Object.keys(data.scenes)); choices($('#platformChoices'), 'platform', Object.keys(data.platforms));
    if (previous) for (const name of ['scene', 'platform']) {
      const item = [...form.querySelectorAll('input[type="radio"]')].find(n => n.name === name && n.value === previous[name]);
      if (item) item.checked = true;
    }
    $('#source_mode').value = ['local', 'ima'].includes(data.default_source) ? data.default_source : 'local';
    $('#source_mode').querySelector('[value="local"]').disabled = !data.local_configured;
    if (!data.local_configured && $('#source_mode').value === 'local') $('#source_mode').value = 'ima';
    if (previous && (previous.source_mode === 'ima' || data.local_configured)) $('#source_mode').value = previous.source_mode;
    $('#connection').replaceChildren();
    [['本地资料', data.local_configured], ['ima', data.ima_configured], ['文案模型', data.model_configured]].forEach(([label, ready]) => $('#connection').append(el('span', label + (ready ? '已配置' : '未配置'), ready ? 'ready' : '')));
    sceneChanged();
    if (previous && [...$('#micro_scene_id').options].some(o => o.value === previous.micro_scene_id)) $('#micro_scene_id').value = previous.micro_scene_id;
    syncControls(); await sourceChanged();
  } catch (error) {
    config = null; $('#connection').textContent = errorMessage(error); $('#sourceHint').textContent = '配置加载失败，创作暂不可用。'; $('#retryConfig').hidden = false; syncControls();
  }
}
function validate() {
  for (const field of form.querySelectorAll('[required]')) {
    if (field.type !== 'radio' && !field.value.trim()) field.value = '';
    if (!field.checkValidity()) {
      const details = field.closest('details'); if (details) details.open = true;
      field.reportValidity(); return false;
    }
  }
  return true;
}
async function run(path, body) {
  if (activeRequest || !config || !validate()) return;
  const payload = body || task();
  const controller = new AbortController(); activeRequest = controller;
  retryAction = () => run(path, payload);
  $('#requestError').hidden = true; $('#loading').hidden = false; $('#result').hidden = true; $('#exports').hidden = true;
  $('#workspace').setAttribute('aria-busy', 'true');
  $('#loadingTitle').textContent = path === '/api/retrieve' || !config.model_configured ? '正在读取产品资料' : path === '/api/rewrite' ? '正在基于原稿证据改写' : '正在检索、创作与核验';
  setStatus('请求已提交，正在等待后端结果…'); syncControls();
  const timer = setTimeout(() => setStatus('服务仍在处理中。生成与核验可能需要数分钟，请耐心等待。'), 20000);
  const timeout = setTimeout(() => controller.abort('timeout'), 600000);
  try {
    const result = await awaitJob(await request(path, payload, controller.signal), controller.signal);
    if (!result || typeof result.status !== 'string') throw new Error('服务结果缺少状态信息，请检查后端返回格式。');
    show(result);
    $('#result').hidden = false;
    $('#workspace').focus({ preventScroll: true });
    $('#workspace').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
  } catch (error) {
    if (controller.signal.aborted) {
      if (controller.signal.reason === 'timeout') showError(new Error('等待超过 10 分钟，请检查服务状态后重试。'));
      else setStatus('已停止等待。输入与上一份结果已保留；服务端任务可能仍在运行。');
    } else showError(error);
  } finally {
    clearTimeout(timer); clearTimeout(timeout); activeRequest = null;
    $('#loading').hidden = true; $('#result').hidden = false; $('#exports').hidden = !lastResult?.draft;
    $('#workspace').setAttribute('aria-busy', 'false'); syncControls();
  }
}
function notice(root, title, description, tone = 'neutral') {
  const box = el('div', undefined, 'notice ' + tone);
  const content = el('div'); content.append(el('strong', title));
  if (description) content.append(el('p', description));
  box.append(icon(tone === 'success' ? 'shield' : tone === 'neutral' ? 'bulb' : 'warning'), content); root.append(box); return content;
}
function section(root, number, title, caption, id) {
  const card = el('section', undefined, 'panel result-card'); card.id = id;
  const heading = el('div', undefined, 'card-heading'); heading.append(el('span', number, 'card-number'), el('h3', title));
  if (caption) heading.append(el('span', caption, 'card-caption'));
  const body = el('div', undefined, 'card-body'); card.append(heading, body); root.append(card); return body;
}
function details(root, title, text, source) {
  const node = el('details', undefined, 'source'); node.append(el('summary', title));
  const body = el('div'); if (source) body.append(el('p', source, 'muted-copy')); body.append(el('pre', text)); node.append(body); root.append(node);
}
function inline(node, text) {
  // A deliberately small Markdown subset; never parse HTML or remotely supplied links.
  String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g).forEach(part => {
    if (part.startsWith('**') && part.endsWith('**')) node.append(el('strong', part.slice(2, -2)));
    else if (part.startsWith('`') && part.endsWith('`')) node.append(el('code', part.slice(1, -1)));
    else node.append(document.createTextNode(part));
  });
}
function renderMarkdown(text) {
  const body = el('div', undefined, 'article-content'); let paragraph = null, list = null;
  String(text).split(/\r?\n/).forEach(line => {
    if (!line.trim()) { paragraph = null; list = null; return; }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    const item = line.match(/^\s*(?:([-*+])|\d+[.)])\s+(.+)$/);
    if (heading) { const n = el('h' + Math.min(heading[1].length + 3, 6)); inline(n, heading[2]); body.append(n); paragraph = null; list = null; }
    else if (/^\s*([-*_])\1{2,}\s*$/.test(line)) { body.append(el('hr')); paragraph = null; list = null; }
    else if (item) { const tag = item[1] ? 'UL' : 'OL'; if (!list || list.tagName !== tag) { list = el(tag.toLowerCase()); body.append(list); } const n = el('li'); inline(n, item[2]); list.append(n); paragraph = null; }
    else if (line.startsWith('> ')) { const n = el('blockquote'); inline(n, line.slice(2)); body.append(n); paragraph = null; list = null; }
    else { if (!paragraph) { paragraph = el('p'); body.append(paragraph); } else paragraph.append(document.createTextNode('\n')); inline(paragraph, line); list = null; }
  });
  return body;
}
function safeImage(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value, location.origin);
    if (url.username || url.password) return null;
    if (value.startsWith('/api/local-image?') && url.origin === location.origin) return value;
    if (url.protocol === 'https:') return url.href;
  } catch { /* Invalid URLs are shown as unavailable, never assigned. */ }
  return null;
}
function gallery(root, images, plans = []) {
  const grid = el('div', undefined, 'gallery');
  images.forEach(image => {
    const card = el('figure', undefined, 'image-card'); const frame = el('div', undefined, 'image-frame');
    const url = safeImage(image.url);
    if (url) { const img = el('img'); img.src = url; img.alt = image.title || '产品资料图片'; img.loading = 'lazy'; img.referrerPolicy = 'no-referrer'; img.addEventListener('error', () => frame.replaceChildren(el('span', '图片暂不可用'))); frame.append(img); }
    else frame.append(el('span', '图片暂不可用'));
    const caption = el('figcaption'); caption.append(el('strong', '[' + image.id + '] ' + image.title));
    const plan = plans.find(p => p.image_id === image.id);
    if (plan) { caption.append(el('span', plan.position, 'tag accent'), el('p', plan.caption)); }
    else caption.append(el('p', '检索素材 · 未指定插入位置'));
    if (image.source) caption.append(el('p', image.source));
    card.append(frame, caption); grid.append(card);
  }); root.append(grid);
}
function checks(root, title, rows, imageMode = false) {
  root.append(el('h4', title));
  if (!rows.length) { root.append(el('p', '本次未返回核验条目。', 'muted-copy')); return; }
  const list = el('ul', undefined, 'check-list');
  rows.forEach(row => {
    const item = el('li', undefined, 'check-row'); const content = el('div'); content.append(el('p', imageMode ? row.title || row.image_id : row.claim));
    const pass = ['quote_matched', 'catalog_match'].includes(row.status);
    const fail = row.status === 'mismatch';
    if (row.source_id) content.append(el('small', '依据 [' + row.source_id + '] ' + (row.quote || '')));
    if (row.reason) content.append(el('small', row.reason));
    const labels = { quote_matched: '✓ 原文匹配', catalog_match: '✓ 索引相符', mismatch: '× 型号不符', unverified: '待核验' };
    item.append(content, el('span', labels[row.status] || '待核验', 'check-badge ' + (pass ? 'pass' : fail ? 'fail' : ''))); list.append(item);
  }); root.append(list);
}
function show(data) {
  const root = $('#result'); root.replaceChildren();
  lastResult = data; markdown = data.draft?.markdown || ''; sourceBadge(data);
  setStatus(statusNames[data.status] || '已收到服务结果');
  $('#resultMeta').textContent = data.status === 'model_required' ? '已结束 · 正文未生成' : data.task?.platform ? data.task.platform + ' · ' + (data.draft ? '草稿' : '资料') : '本次结果';
  const risky = ['needs_review', 'blocked', 'failed'].includes(data.status);
  const banner = notice(root, statusNames[data.status] || '服务返回结果', data.error || (data.draft ? '结果供运营判断；发布前仍需核对动态信息、图片型号和使用权限。' : data.source_note || '请查看本次返回的信息。'), risky ? 'danger' : data.status === 'checked_draft' ? 'success' : ['needs_input', 'model_required'].includes(data.status) ? 'warning' : 'neutral');
  (data.questions || []).forEach(q => banner.append(el('p', q)));
  if (data.status === 'model_required') {
    banner.append(el('p', '本次请求已经结束，写作与审稿均未执行。完成模型配置并重启服务后，请重新生成。'));
    const summary = el('div', undefined, 'output-summary');
    summary.append(el('span', (data.documents || []).length + ' 份资料'), el('span', (data.images || []).length + ' 张素材'), el('span', '正文未生成'), el('span', '核验未执行'));
    banner.append(summary);
  }
  if (data.mode === 'snapshot_rewrite') banner.append(el('p', '本次复用原稿证据快照，未重新实时检索资料。'));
  if (data.draft) {
    const nav = el('nav', undefined, 'jump-links'); nav.setAttribute('aria-label', '跳转到结果分段');
    [['strategy', '场景策略'], ['evidence', '知识库依据'], ['article', '图文草稿'], ['verification', '核验结果']].forEach(([id, label]) => { if ((id === 'strategy' && !data.strategy) || (id === 'evidence' && !data.documents)) return; const link = el('a', label); link.href = '#' + id; nav.append(link); }); root.append(nav);
  }
  if (data.strategy) {
    const body = section(root, '01', '场景判断', '从需求找到切入点', 'strategy'); const tags = el('div', undefined, 'tag-row');
    [data.task?.audience, data.task?.scene, data.task?.platform, data.task?.stage].filter(Boolean).forEach((text, i) => tags.append(el('span', text, 'tag' + (!i ? ' accent' : '')))); body.append(tags);
    body.append(el('p', data.strategy.angle, 'angle'));
    if (data.strategy.pain) body.append(el('p', data.strategy.pain, 'muted-copy'));
    if (data.harness?.scene) body.append(el('p', '细分场景：' + data.harness.scene.label, 'muted-copy'));
    details(body, '内容目标与写作策略', ['目标：' + (data.task?.goal || '待补充'), '关注：' + (data.strategy.focus || []).join(' / '), data.strategy.style, '建议补充：' + (data.strategy.ask || '无')].filter(Boolean).join('\n'));
  }
  if (data.documents) {
    const body = section(root, '02', '知识库依据', data.documents.length + ' 份资料', 'evidence');
    body.append(el('p', data.task?.product || '产品资料', 'angle'));
    if (data.source_note) body.append(el('p', data.source_note, 'muted-copy'));
    if (!data.documents.length) body.append(el('p', '未取得产品原文，请核对准确型号后重新检索。', 'muted-copy'));
    if (data.facts?.length) { const list = el('ul', undefined, 'fact-list'); data.facts.forEach(f => list.append(el('li', f.claim + ' [' + f.source_id + ']' + (f.conditions ? ' · ' + f.conditions : '')))); body.append(list); }
    data.documents.forEach(doc => details(body, '[' + doc.id + '] ' + doc.title, doc.text, doc.source));
    if (!data.draft && data.images?.length) { body.append(el('h4', '检索到的图片素材')); gallery(body, data.images); }
  }
  if (data.draft) {
    const article = section(root, '03', '图文草稿', data.task?.platform || '', 'article'); article.parentElement.classList.add('article-card'); article.append(renderMarkdown(markdown));
    if (data.draft.strategy_reason) details(article, '查看写作说明', data.draft.strategy_reason);
    article.append(el('h4', '配图与插入建议'), el('p', '以下为资料库素材；图片实际内容、型号与使用权限需人工确认。', 'muted-copy'));
    const plans = data.draft.image_plan || [];
    const selected = (data.images || []).filter(x => plans.some(p => p.image_id === x.id));
    if (selected.length) gallery(article, selected, plans);
    else article.append(el('p', '暂无可展示的配图，请查看配图计划和核验结果。', 'muted-copy'));
    const remaining = (data.images || []).filter(x => !selected.includes(x));
    if (remaining.length) { const det = el('details', undefined, 'source'); det.append(el('summary', '其他检索素材 · ' + remaining.length + ' 张')); const content = el('div'); gallery(content, remaining); det.append(content); article.append(det); }
    plans.filter(p => !selected.some(x => x.id === p.image_id)).forEach(p => article.append(el('p', [p.image_id, p.position, p.caption].join(' · '), 'muted-copy')));
    const review = section(root, '04', '核验结果', '发布前请人工确认', 'verification');
    const pc = data.publish_precheck;
    if (pc) {
      review.append(el('h4', '发布前文本预检'), el('p', pc.status === 'needs_review' ? '发现需要修改或补充依据的内容' : '已完成本次文本预检，不代表平台审核通过', 'muted-copy'));
      (pc.findings || []).forEach(f => { const n = el('div', undefined, 'finding'); n.append(el('strong', f.text + ' · ' + ({ allow: '语境允许', revise: '建议修改', uncertain: '需复核' }[f.decision] || '需复核')), el('p', f.reason)); if (f.suggestion) n.append(el('p', '建议：' + f.suggestion, 'advice')); review.append(n); });
      if (pc.rule_review_due?.length) review.append(el('p', '部分规则快照已到复核日期，尚未实时核验。', 'muted-copy'));
      if (pc.not_checked?.length) review.append(el('p', '未检查：' + pc.not_checked.join('、'), 'muted-copy'));
    }
    checks(review, '产品事实核验', data.verification?.facts || []);
    checks(review, '图片型号核验', data.verification?.images || [], true);
    (data.verification?.compliance || []).forEach(c => review.append(el('p', '合规复核：' + c.text + ' · ' + c.reason, 'finding')));
    const pending = [...new Set([...(data.issues || []), ...(data.draft.pending || [])])];
    if (pending.length) { review.append(el('h4', '待处理与待确认')); const list = el('ul', undefined, 'pending-list'); pending.forEach(p => list.append(el('li', p))); review.append(list); }
    review.append(el('p', data.review_note || '检查结果不替代人工确认。', 'muted-copy'));
    $('#exportHint').textContent = data.status === 'needs_review' ? '草稿含待解决问题，请先查看核验结果' : '发布前请人工确认';
  }
  if (data.warnings?.length) { const box = notice(root, '资料读取提醒', '', 'warning'); data.warnings.forEach(w => box.append(el('p', w))); }
  if (data.trace?.length) {
    const trace = el('details', undefined, 'trace'); trace.append(el('summary', '运行追踪与来源记录 · ' + data.run_id));
    if (data.started_at) trace.append(el('p', '运行时间：' + data.started_at));
    if (data.evidence_started_at) trace.append(el('p', '原稿证据时间：' + data.evidence_started_at));
    data.trace.forEach(t => trace.append(el('p', t.step + ' / ' + t.status + ' / ' + t.detail))); root.append(trace);
  }
}
function saveFile(text, type, filename) {
  const url = URL.createObjectURL(new Blob([text], { type })); const link = el('a'); link.href = url; link.download = filename; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    try { await navigator.clipboard.writeText(text); return; } catch { /* Try the HTTP-compatible path below. */ }
  }
  const previous = document.activeElement;
  const field = el('textarea'); field.value = text; field.setAttribute('readonly', '');
  field.style.cssText = 'position:fixed;left:-9999px;top:0';
  document.body.append(field); field.select();
  try { if (!document.execCommand('copy')) throw new Error('Clipboard unavailable'); }
  finally { field.remove(); previous?.focus({preventScroll:true}); }
}
form.addEventListener('submit', event => { event.preventDefault(); run('/api/generate'); });
form.addEventListener('invalid', event => { const details = event.target.closest('details'); if (details) details.open = true; }, true);
form.addEventListener('change', event => { if (event.target.name === 'scene') sceneChanged(); syncControls(); });
form.addEventListener('input', () => syncControls());
$('#source_mode').addEventListener('change', sourceChanged);
$('#retrieve').onclick = () => run('/api/retrieve');
$('#cancel').onclick = () => activeRequest?.abort('user');
$('#retry').onclick = () => retryAction?.();
$('#retryConfig').onclick = initialize;
$('#refreshConfig').onclick = initialize;
$('#rewrite').onclick = () => { if (lastResult?.run_id) run('/api/rewrite', { ...task(), run_id: lastResult.run_id }); };
$('#connect').onclick = async () => {
  if (activeRequest) return;
  const controller = new AbortController(); activeRequest = controller; syncControls();
  $('#connection').textContent = '正在测试资料连接…';
  const timeout = setTimeout(() => controller.abort(), 30000);
  try { $('#connection').textContent = (await request('/api/connect', { source_mode: $('#source_mode').value }, controller.signal)).message; }
  catch (error) { $('#connection').textContent = controller.signal.aborted ? '连接测试超时，请检查服务后重试。' : errorMessage(error); }
  finally { clearTimeout(timeout); activeRequest = null; syncControls(); }
};
$('#copy').onclick = async () => {
  try { await copyText(markdown); setStatus('已复制文案。' + (lastResult.status === 'needs_review' ? '仍有待解决问题，请查看核验结果。' : '发布前请人工确认。')); }
  catch { setStatus('复制失败，请使用「导出 Markdown」保存文案。'); }
};
$('#download').onclick = () => { saveFile(markdown, 'text/markdown;charset=utf-8', '校园营销图文-' + (lastResult.task?.platform || '草稿') + '.md'); setStatus('已导出 Markdown，发布前请人工确认。'); };
$('#auditExport').onclick = () => {
  const report = {};
  for (const key of ['run_id', 'parent_run_id', 'status', 'mode', 'started_at', 'evidence_started_at', 'task', 'source_kind', 'knowledge_base', 'snapshot_modified_at', 'trace', 'evidence_manifest', 'verification', 'issues', 'harness', 'publish_precheck', 'product_identity']) report[key] = lastResult[key];
  for (const key of ['claims', 'image_plan', 'pending', 'strategy_reason']) report[key] = lastResult.draft?.[key];
  saveFile(JSON.stringify(report, null, 2), 'application/json;charset=utf-8', '核验记录-' + lastResult.run_id + '.json'); setStatus('已导出核验记录。');
};
initialize();
