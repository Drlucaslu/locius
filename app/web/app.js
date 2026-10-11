/* OMuse web UI — no build step. Talks to Sentinel (/sentinel/api) and, through it, the Runtime (/api). */
(() => {
'use strict';

// ------------------------------------------------------------------ i18n
// UI strings are written in Simplified Chinese in the source and wrapped in T()/Tf(); English comes from i18n.js and
// Traditional Chinese from i18n_tw.js. The UI language is Settings → ui_language, or the browser's language when that is
// empty; localStorage only caches it for the first paint (syncLang reloads if the server says otherwise).
const UI_LANGS = ['en', 'zh', 'tw'];
const browserLang = () => { const l = (navigator.language || '').toLowerCase(); return !l.startsWith('zh') ? 'en' : /tw|hk|mo|hant/.test(l) ? 'tw' : 'zh'; };
const LANG = (() => {
  try { const v = localStorage.getItem('omuse_ui'); if (UI_LANGS.includes(v)) return v; } catch (e) { /* storage blocked */ }
  return browserLang();
})();
const EN = window.OMUSE_EN || {};
const TW = window.OMUSE_TW || {};
const CJK_RE = /[一-鿿]/;
// Fallback for dynamic bilingual text from the server, e.g. "发送邮件 Send email" or "已拒绝 (user denied)".
function biEn(s) {
  if (typeof s !== 'string' || !CJK_RE.test(s)) return s;
  const parts = s.split(/[；;]\s*/);
  if (parts.length > 1) return parts.map(biEn).join('; ');
  // "中文说明 (english explanation)" -> the part in brackets
  let m = s.match(/^(.*[\u4e00-\u9fff][^()（）]*?)\s*[(（]([^()（）\u4e00-\u9fff]*[A-Za-z][^()（）\u4e00-\u9fff]*)[)）]\s*([^\u4e00-\u9fff]*)$/);
  if (m) { const t = m[2].charAt(0).toUpperCase() + m[2].slice(1); return m[3] ? `${t} ${m[3]}` : t; }
  // "中文标签 English label" -> the trailing English
  m = s.match(/^([^\w\u4e00-\u9fff]*)\S.*[\u4e00-\u9fff](?:[）)」》]\s*|\s+)([A-Za-z][^\u4e00-\u9fff]*)$/);
  if (m) return (m[1] || '') + m[2];
  return s;
}
function T(s) { return LANG === 'en' ? (EN[s] ?? biEn(s)) : LANG === 'tw' ? (TW[s] ?? s) : s; }
function Tf(s, ...a) { return (LANG === 'en' ? (EN[s] ?? s) : LANG === 'tw' ? (TW[s] ?? s) : s).replace(/\{(\d+)\}/g, (_, i) => (a[i] ?? '')); }
const B = s => (LANG === 'en' ? biEn(String(s ?? '')) : s);   // server-provided bilingual text
const ZH = s => (LANG === 'tw' ? (TW[s] ?? s) : s);           // server-provided Simplified labels (domains, profile fields)
document.documentElement.lang = { en: 'en', zh: 'zh-CN', tw: 'zh-TW' }[LANG];
// The theme is a server setting too (auto / ink / paper); localStorage caches it so the first paint has no flash.
function applyTheme(t) {
  t = t === 'ink' || t === 'paper' ? t : 'auto';
  if (t === 'auto') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem('omuse_theme', t); } catch (e) { /* ignore */ }
}
// Settings decide the UI language (ui_language; "" = follow the browser) and the theme. The agent's own language
// (language) is separate; on the first visit it is filled from the browser, so an English browser gets an English agent.
async function syncLang() {
  try {
    const r = await api('settings');
    const s = r.settings || {};
    applyTheme(s.theme);
    const want = UI_LANGS.includes(s.ui_language) ? s.ui_language : browserLang();
    try { localStorage.setItem('omuse_ui', want); } catch (e) { /* ignore */ }
    if (want !== LANG) { location.reload(); return; }
    if (s.language !== 'en' && s.language !== 'zh') await api('settings', { method: 'PUT', body: { language: LANG === 'en' ? 'en' : 'zh' } });
  } catch (e) { /* offline: keep the cached choice */ }
}
function i18nStatic() {
  const set = (sel, text, attr) => { const el = document.querySelector(sel); if (el) { if (attr) el.setAttribute(attr, text); else el.textContent = text; } };
  if (LANG === 'tw') {   // the static strings of index.html, Traditional (i18n-ok: not T() keys)
    set('.brand small', '專屬電腦上的私人 Agent');   // i18n-ok
    set('#menuBtn', '選單 Menu', 'aria-label');   // i18n-ok
    set('#viewTitle', '對話');   // i18n-ok
    set('#approvalBell', '審批 Approvals', 'aria-label'); set('#approvalBell span', '審批');   // i18n-ok
    set('.drawer-head h2', '待審批 Approvals'); set('#drawerClose', '關閉', 'aria-label');   // i18n-ok
    set('#drawer > p', '由 Sentinel 獨立發起，與對話分離。Agent 在你決定前會暫停。');   // i18n-ok
    return;
  }
  if (LANG !== 'en') return;
  set('.brand small', 'Private agent on its own computer');
  set('#menuBtn', 'Menu', 'aria-label');
  set('#viewTitle', 'Chat');
  set('#modelChip', 'Model', 'title'); set('#modelChip', 'Model …');
  set('#sentinelChip', 'Sentinel (guardian)', 'title');
  set('#approvalBell', 'Approvals', 'aria-label'); set('#approvalBell span', 'Approvals');
  set('.drawer-head h2', 'Pending approvals'); set('#drawerClose', 'Close', 'aria-label');
  set('#drawer > p', 'Raised independently by Sentinel, separate from the chat. The Agent pauses until you decide.');
}

// ------------------------------------------------------------------ helpers
const $ = (s, r = document) => r.querySelector(s);
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'style') el.setAttribute('style', v);
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const k of kids.flat(Infinity)) {
    if (k === null || k === undefined || k === false) continue;
    el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return el;
}
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function md(text) {
  try { return DOMPurify.sanitize(marked.parse(String(text || ''), { gfm: true, breaks: true }), { ADD_ATTR: ['target'] }); }
  catch (e) { return esc(text); }
}
function mdEl(text) { const d = h('div', { class: 'md' }); d.innerHTML = md(text); d.querySelectorAll('a').forEach(a => { a.target = '_blank'; a.rel = 'noopener noreferrer'; }); return d; }
const fmtTime = ts => { if (!ts) return ''; const d = new Date(ts * 1000); return d.toLocaleString(undefined, { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }); };
const fmtClock = ts => ts ? new Date(ts * 1000).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '';
const STATUS_ZH = { CREATED: T('已创建'), PLANNING: T('规划中'), RUNNING: T('执行中'), WAITING_APPROVAL: T('等待审批'), WAITING_EXTERNAL: T('等待外部'),
  PAUSED: T('已暂停'), FAILED: T('失败'), COMPLETED: T('已完成'), CANCELLED: T('已取消') };
const pill = st => h('span', { class: 'pill st-' + st, title: st }, LANG === 'en' ? (STATUS_ZH[st] || st) : `${STATUS_ZH[st] || st} ${st}`);
const riskPill = r => r ? h('span', { class: 'pill risk-' + r }, { low: T('低 low'), medium: T('中 medium'), high: T('高 high'), critical: T('极高 critical') }[r] || r) : '';

async function call(url, opts = {}) {
  const o = { method: opts.method || 'GET', headers: { 'X-Persona-UI': '1' } };
  if (opts.body !== undefined) { o.body = JSON.stringify(opts.body); o.headers['Content-Type'] = 'application/json'; }
  const r = await fetch(url, o);
  let data = null;
  try { data = await r.json(); } catch (e) { data = null; }
  if (!r.ok) throw new Error((data && data.detail) || `HTTP ${r.status}`);
  return data;
}
const api = (p, o) => call('api/' + p, o);
const sapi = (p, o) => call('sentinel/api/' + p, o);
function toast(msg, err = false, onclick) {
  const t = h('div', { class: 'toast' + (err ? ' err' : ''), role: 'status' }, typeof msg === 'string' ? B(msg) : msg);
  t.onclick = () => { t.remove(); onclick && onclick(); };
  $('#toasts').append(t);
  setTimeout(() => t.remove(), err ? 9000 : 6000);
}
const isNarrow = () => window.matchMedia('(max-width: 760px)').matches;
const isTouch = () => window.matchMedia('(pointer: coarse)').matches;
const safe = fn => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message, true); } };

// ------------------------------------------------------------------ state
const S = {
  view: 'chat', conv: null, convs: [], convData: null, tasks: {}, events: {}, approvals: [], selTask: null,
  settings: null, browserTimer: null, taskFilter: '', auditTask: '', seenApprovals: new Set(), sending: false,
};

const VIEWS = [
  ['chat', '💬', T('对话'), 'Chat'], ['tasks', '🗂', T('任务'), 'Tasks'], ['browser', '🌐', T('浏览器'), 'Browser'],
  ['schedules', '⚡', T('自动化'), 'Automations'], ['connections', '🔌', T('连接'), 'Connections'], ['memory', '🧠', T('记忆'), 'Memory'],
  ['trust', '📈', T('可信度'), 'Trust'], ['skills', '🎓', T('技能'), 'Skills'], ['activity', '📜', T('活动审计'), 'Audit'], ['settings', '⚙️', T('设置'), 'Settings'],
];

function renderNav() {
  const nav = $('#navlinks'); nav.innerHTML = '';
  for (const [id, ic, zh, en] of VIEWS) {
    const a = h('a', { href: '#' + id, class: S.view === id ? 'active' : '' }, h('span', { class: 'ic' }, ic), LANG === 'en' ? en : zh,
      id === 'tasks' && waitingCount() ? h('span', { class: 'badge' }, waitingCount()) : null, LANG === 'en' ? null : h('span', { class: 'en' }, en));
    nav.append(a);
  }
}
const waitingCount = () => Object.values(S.tasks).filter(t => t.status === 'WAITING_APPROVAL' || t.status === 'WAITING_EXTERNAL').length;

function route() {
  const v = (location.hash || '#chat').slice(1).split('/')[0];
  S.view = VIEWS.some(x => x[0] === v) ? v : 'chat';
  const arg = (location.hash || '').split('/')[1];
  if (S.view === 'tasks' && arg) S.selTask = arg;
  if (S.view === 'browser') S.browserSel = arg || S.browserSel || null;
  if (S.view === 'chat') { const c = arg || null; if (c !== S.conv) { S.conv = c; S.convData = null; } }
  if (S.browserTimer) { clearInterval(S.browserTimer); S.browserTimer = null; }
  $('#nav').classList.remove('open'); if ($('#navBack')) $('#navBack').hidden = true;
  const meta = VIEWS.find(x => x[0] === S.view);
  $('#viewTitle').textContent = LANG === 'en' ? meta[3] : `${meta[2]} ${meta[3]}`;
  renderNav();
  const view = $('#view'); view.innerHTML = '';
  ({ chat: viewChat, tasks: viewTasks, browser: viewBrowser, schedules: viewSchedules, connections: viewConnections,
     memory: viewMemory, trust: viewTrust, skills: viewSkills, activity: viewActivity, settings: viewSettings })[S.view](view);
}

// ================================================================== CHAT
const SUGGESTIONS = [
  T('看看这周有哪些重要邮件需要我回复'),
  T('给 John 回复：周二下午 3 点可以'),
  T('帮我研究东京三家酒店，并做一个比较'),
  T('每天早上 8 点给我总结重要邮件'),
  T('记住：我喜欢直飞航班和安静的精品酒店'),
];

async function viewChat(root) {
  const wrap = h('div', { class: 'chat' });
  const list = h('div', { class: 'convlist' });
  const thread = h('div', { class: 'thread' });
  wrap.append(list, thread, convResizer(wrap)); root.append(wrap);
  passwordReminder();
  await loadConvs();
  if (S.conv && !S.convs.some(c => c.id === S.conv)) { S.conv = null; S.convData = null; }
  renderConvList(list);
  if (S.conv && !S.convData) await openConv(S.conv);
  else renderThread(thread);
  if (S.gmailReady === undefined) {  // only show the "connect your email" hint when no mailbox is connected
    sapi('connections').then(r => {
      const gm = (r.connections || []).find(c => c.name === 'gmail');
      S.gmailReady = !!(gm && gm.has_credential);
      if (!S.gmailReady && !S.conv) renderThread();
    }).catch(() => {});
  }
}

// Drag the divider to make the chat list wider (long titles) or narrower; double-click resets; arrow keys work too.
const CONV_W = { min: 180, max: 560, def: 240 };
function convResizer(wrap) {
  let saved = 0;
  try { saved = parseInt(localStorage.getItem('omuse.convW') || '0', 10); } catch (e) {}
  const set = (w, save) => {
    const max = Math.min(CONV_W.max, Math.max(CONV_W.min, (wrap.clientWidth || 1200) * 0.6));
    w = Math.round(Math.min(max, Math.max(CONV_W.min, w)));
    wrap.style.setProperty('--conv-w', w + 'px');
    bar.setAttribute('aria-valuenow', w);
    if (save) { try { localStorage.setItem('omuse.convW', String(w)); } catch (e) {} }
    return w;
  };
  const cur = () => parseInt(getComputedStyle(wrap).getPropertyValue('--conv-w')) || CONV_W.def;
  const bar = h('div', { class: 'conv-resizer', role: 'separator', tabindex: '0', 'aria-orientation': 'vertical',
    'aria-valuemin': CONV_W.min, 'aria-valuemax': CONV_W.max, 'aria-label': T('调整对话列表宽度 Resize chat list'),
    title: T('拖动调整宽度，双击恢复 Drag to resize, double-click to reset') });
  bar.addEventListener('pointerdown', e => {
    e.preventDefault(); bar.setPointerCapture(e.pointerId); wrap.classList.add('resizing');
    const left = wrap.getBoundingClientRect().left;
    const move = ev => set(ev.clientX - left, false);
    const up = ev => { bar.removeEventListener('pointermove', move); bar.removeEventListener('pointerup', up);
      bar.removeEventListener('pointercancel', up); wrap.classList.remove('resizing'); set(cur(), true); };
    bar.addEventListener('pointermove', move); bar.addEventListener('pointerup', up); bar.addEventListener('pointercancel', up);
  });
  bar.addEventListener('dblclick', () => set(CONV_W.def, true));
  bar.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); set(cur() + (e.key === 'ArrowRight' ? 24 : -24), true); }
  });
  if (saved) requestAnimationFrame(() => set(saved, false));
  return bar;
}

// start a fresh conversation: its own context, its own tasks
function newChat() {
  S.conv = null; S.convData = null; S.draft = '';
  closeHistory();
  if (location.hash !== '#chat') { history.replaceState(null, '', '#chat'); }
  renderConvList(); renderThread();
  const ta = $('#chatInput'); if (ta) { ta.value = ''; ta.dispatchEvent(new Event('input')); if (!isTouch()) ta.focus(); }
}

async function deleteConv(id) {
  const c = S.convs.find(x => x.id === id);
  if (!c) return;
  if (!confirmInline(Tf("删除对话「{0}」？任务记录仍保留在「任务」和「审计」里。", (c.title || T('无标题'))))) return;
  await api('conversations/' + id, { method: 'DELETE' });
  if (S.conv === id) newChat();
  await loadConvs(); renderConvList();
  toast(T('已删除 Deleted'));
}
// window.confirm is fine inside the app window
function confirmInline(msg) { try { return window.confirm(msg); } catch (e) { return true; } }

function toggleHistory() {
  const pop = $('#histPop');
  if (pop) { closeHistory(); return; }
  const box = h('div', { class: 'hist-pop', id: 'histPop' });
  const listEl = h('div', { class: 'convlist in-pop' });
  box.append(listEl);
  $('.thread-head').append(box);
  renderConvList(listEl);
}
function closeHistory() { const p = $('#histPop'); if (p) p.remove(); }

async function loadConvs() {
  const r = await api('conversations');
  S.convs = r.conversations;
}

function renderConvList(list) {
  const lists = list ? [list] : Array.from(document.querySelectorAll('.convlist'));
  for (const el of lists) {
    el.innerHTML = '';
    el.append(h('button', { class: 'btn primary newchat', onclick: newChat, title: T('开始一个新对话（新的上下文）') }, T('＋ 新对话 New chat')));
    const chats = S.convs.filter(c => c.kind === 'chat'), scheds = S.convs.filter(c => c.kind === 'schedule');
    const mk = c => h('div', { class: 'conv' + (S.conv === c.id ? ' active' : ''), title: c.title, role: 'button', tabindex: '0',
        onclick: () => { closeHistory(); openConv(c.id); },
        onkeydown: e => { if (e.key === 'Enter') { closeHistory(); openConv(c.id); } } },
      h('span', { class: 'ct' }, c.title || T('(无标题)')),
      h('span', { class: 'cd faint' }, fmtTime(c.updated_at)),
      h('button', { class: 'cx', title: T('删除对话 Delete'), 'aria-label': T('删除对话'), onclick: e => { e.stopPropagation(); safe(deleteConv)(c.id); } }, '×'));
    if (chats.length) el.append(h('h4', null, T('对话 Chats')), ...chats.map(mk));
    else el.append(h('p', { class: 'small muted', style: 'padding:4px 8px' }, T('还没有对话')));
    if (scheds.length) el.append(h('h4', null, T('自动化 Automations')), ...scheds.map(mk));
  }
}

async function openConv(id) {
  if (id !== S.conv) S.draft = '';
  S.conv = id;
  if (location.hash !== '#chat/' + id) history.replaceState(null, '', '#chat/' + id);
  let r;
  try { r = await api('conversations/' + id); }
  catch (e) { toast(T('对话不存在或已删除'), true); newChat(); return; }
  if (S.conv !== id) return;  // user switched away meanwhile
  S.convData = r;
  mergeTasks(r.tasks);
  renderConvList(); renderThread();
}

// A fetched snapshot can be older than a live event that arrived while the request was in flight: keep the newer one.
function mergeTasks(tasks) {
  for (const t of Object.values(tasks || {})) {
    const o = S.tasks[t.id];
    if (!o || (t.updated_at || 0) >= (o.updated_at || 0)) S.tasks[t.id] = { ...(o || {}), ...t };
  }
}

// Re-read the open conversation and redraw only if something changed (keeps open "Activity" panels open).
async function refreshConv(force) {
  const id = S.conv;
  if (!id || S.view !== 'chat') return;
  let r;
  try { r = await api('conversations/' + id); } catch (e) { return; }
  if (S.conv !== id || S.view !== 'chat') return;
  const old = S.convData;
  const changed = force || !old || old.messages.length !== r.messages.length ||
    Object.values(r.tasks || {}).some(t => { const o = S.tasks[t.id]; return !o || o.status !== t.status || (o.updated_at || 0) < (t.updated_at || 0); });
  if (!changed) return;
  mergeTasks(r.tasks);
  S.convData = r;
  const open = [...document.querySelectorAll('.taskcard details[open]')].map(d => d.closest('.taskcard').id);
  renderThread();
  open.forEach(cid => { const d = document.querySelector('#' + cid + ' details'); if (d) d.open = true; });
}
const convHasActiveTask = () => S.convData && Object.keys(S.convData.tasks || {})
  .some(id => S.tasks[id] && !['COMPLETED', 'FAILED', 'CANCELLED'].includes(S.tasks[id].status));

function renderThread(thread) {
  thread = thread || $('.thread'); if (!thread) return;
  const keepScroll = $('.msgs', thread);
  const oldComp = $('.composer', thread);
  // when a conversation is (re)opened, stick to the latest message for a moment even if other re-renders follow quickly
  if (S._renderedConv !== S.conv || !keepScroll) { S._renderedConv = S.conv; S._stickUntil = Date.now() + 2000; }
  const atBottom = Date.now() < (S._stickUntil || 0) || keepScroll.scrollHeight - keepScroll.scrollTop - keepScroll.clientHeight < 80;
  [...thread.children].forEach(c => { if (c !== oldComp) c.remove(); });
  const d = S.convData;
  const cur = S.convs.find(c => c.id === S.conv);
  const head = h('div', { class: 'thread-head' },
    h('button', { class: 'btn small hist-btn', onclick: toggleHistory, title: T('历史对话 History') }, T('☰ 历史')),
    h('div', { class: 'th-title', title: cur ? cur.title : '' }, cur ? (cur.kind === 'schedule' ? cur.title : cur.title || T('(无标题)')) : T('新对话 New chat')),
    d && d.messages.length ? h('span', { class: 'small faint th-meta' }, Tf("{0} 个任务 tasks", (Object.keys(d.tasks || {}).length))) : null,
    h('button', { class: 'btn small primary', onclick: newChat, title: T('开始新对话（新的上下文）') }, T('＋ 新对话')),
    S.conv ? h('button', { class: 'btn small', onclick: () => safe(deleteConv)(S.conv), title: T('删除当前对话') }, '🗑') : null);
  if (S.passwordDefault) thread.insertBefore(pwBanner(), oldComp || null);
  thread.insertBefore(head, oldComp || null);
  const msgs = h('div', { class: 'msgs', 'aria-live': 'polite' });
  if (!d || !d.messages.length) {
    msgs.append(h('div', { class: 'msg' }, h('div', { class: 'card' },
      h('h3', null, T('你好，我是 OMuse 👋')),
      h('p', { class: 'sub' }, T('我是只为你服务的私人 Agent，运行在一台专属于你的计算机上：上下文、工具和凭据都只属于你。我可以读写邮件、操作浏览器、管理文件、记住你的偏好、定时执行任务。')
        + T('发送邮件、提交表单、付款、删除等高风险动作，都会由独立的 Sentinel（哨兵）弹出审批，你批准后才会执行。')),
      S.gmailReady === false ? h('p', { class: 'small muted' }, T('提示：先到「连接 Connections」连接你的邮箱（Gmail、Outlook、QQ、163 等）。')) : null)));
  } else {
    const shown = new Set();
    const lastUser = d.messages.map(m => m.role).lastIndexOf('user');
    for (const [mi, m] of d.messages.entries()) {
      if (m.role === 'user') {
        const atts = (m.meta && m.meta.attachments) || [];
        if (atts.length) msgs.append(h('div', { class: 'msg user' }, attachStrip(atts)));
        msgs.append(h('div', { class: 'msg user' }, h('div', { class: 'bubble' }, m.content)));
        if (m.task_id && S.tasks[m.task_id]) { msgs.append(taskCard(S.tasks[m.task_id])); shown.add(m.task_id); }
      } else if (m.role === 'assistant') {
        if (m.task_id && !shown.has(m.task_id) && S.tasks[m.task_id]) { msgs.append(taskCard(S.tasks[m.task_id])); shown.add(m.task_id); }
        msgs.append(h('div', { class: 'msg assistant' }, h('div', { class: 'bubble' }, mdEl(m.content))));
      } else if (m.role === 'system') {
        let j = {}; try { j = JSON.parse(m.content); } catch (e) {}
        const t = S.tasks[j.task_id];
        if (j.type === 'approval') {
          const pending = S.approvals.some(a => a.id === j.approval_id);
          msgs.append(h('div', { class: 'msg' }, h('div', { class: 'sys-card' }, '🛡',
            h('span', null, Tf("Sentinel 请求审批：{0}", (j.title || ''))),
            pending ? h('button', { class: 'btn approve small', onclick: () => openApproval(j.approval_id) }, T('去审批 Review')) :
              h('span', { class: 'small muted' }, T('已处理 resolved')))));
        } else if (j.type === 'file') {
          msgs.append(fileCard(j));
        } else if (j.type === 'files') {
          msgs.append(filesCard(j));
        } else if (j.type === 'choices') {
          msgs.append(choicesCard(j, mi > lastUser));
        } else if (j.type === 'takeover') {
          const active = t && t.status === 'WAITING_EXTERNAL';
          msgs.append(h('div', { class: 'msg' }, h('div', { class: 'sys-card takeover' }, '🖐',
            h('span', null, Tf("Agent 请你接管浏览器：{0}", (j.reason || ''))),
            active ? h('a', { class: 'btn small', href: '#browser/' + (t ? t.id : '') }, T('打开浏览器 Open browser')) : h('span', { class: 'small muted' }, T('已结束 done')))));
        }
      }
    }
  }
  thread.insertBefore(msgs, oldComp || null);
  const compKey = `${S.conv || ''}|${d && d.messages.length ? 1 : 0}`;
  if (oldComp && oldComp.dataset.key === compKey) {
    if (atBottom) { msgs.scrollTop = msgs.scrollHeight; requestAnimationFrame(() => { msgs.scrollTop = msgs.scrollHeight; }); }
    else if (keepScroll) msgs.scrollTop = keepScroll.scrollTop;
    return;  // same conversation state: keep the existing input (focus, keyboard, draft) untouched
  }
  if (oldComp) oldComp.remove();
  const comp = h('div', { class: 'composer' }); comp.dataset.key = compKey;
  if (!d || !d.messages.length) comp.append(h('div', { class: 'suggest' }, SUGGESTIONS.map(s => h('button', { onclick: () => { ta.value = s; S.draft = s; grow(); ta.focus(); } }, s))));
  const hadFocus = document.activeElement && document.activeElement.id === 'chatInput';
  const narrow = isNarrow();
  const ph = S.conv ? (narrow ? T('继续这个对话…') : T('继续这个对话… (Enter 发送，Shift+Enter 换行)'))
    : (narrow ? T('告诉 OMuse 要做什么…') : T('开始新对话：告诉 OMuse 要做什么… (Enter 发送)'));
  const ta = h('textarea', { id: 'chatInput', rows: 1, placeholder: ph, enterkeyhint: isTouch() ? 'enter' : 'send', 'aria-label': T('消息 Message') });
  ta.value = S.draft || '';
  const grow = () => { ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight + 2, narrow ? 140 : 200) + 'px'; };
  ta.addEventListener('input', () => { S.draft = ta.value; grow(); });
  // desktop: Enter sends, Shift+Enter = newline. Phones: Enter = newline, tap the send button.
  ta.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && !isTouch()) { e.preventDefault(); send(); } });
  if (hadFocus) requestAnimationFrame(() => { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); });
  const btn = h('button', { class: 'btn primary send', onclick: () => send(), 'aria-label': T('发送 Send'), title: T('发送 Send') },
    h('span', { class: 'lbl' }, T('发送 Send')), h('span', { class: 'ico', 'aria-hidden': 'true' }, '↑'));
  const picker = h('input', { type: 'file', multiple: true, style: 'display:none', 'aria-hidden': 'true',
    accept: 'image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.md,.markdown,.txt,.csv,.json,.zip' });
  picker.onchange = () => { addFiles([...picker.files]); picker.value = ''; };
  const plus = h('button', { class: 'btn attach', type: 'button', onclick: () => picker.click(), 'aria-label': T('添加附件 Attach files'),
    title: T('添加图片、视频、PDF、Word、Markdown 等文件 Attach files') }, '＋');
  const chips = h('div', { class: 'chips' });
  S.attach = S.attach || [];
  const drawChips = () => {
    chips.replaceChildren(...S.attach.map(a => h('div', { class: 'chip-att' + (a.error ? ' bad' : '') },
      a.thumb ? h('img', { src: a.thumb, alt: '' }) : h('span', { class: 'ic' }, FILE_ICON(a.file.type || '')),
      h('span', { class: 'nm', title: a.file.name }, a.file.name),
      h('span', { class: 'small faint' }, a.error ? T('失败') : a.info ? fmtSize(a.file.size) : Math.round(a.progress * 100) + '%'),
      h('button', { class: 'x', type: 'button', 'aria-label': T('移除 Remove'), onclick: () => { S.attach = S.attach.filter(x => x !== a); drawChips(); } }, '×'))));
    chips.style.display = S.attach.length ? '' : 'none';
  };
  const addFiles = (files) => {
    for (const f of files) {
      if (S.attach.length >= 10) { toast(T('一次最多 10 个附件 At most 10 files'), true); break; }
      if (f.size > 50 * 1024 * 1024) { toast(Tf("{0} 超过 50 MB", f.name), true); continue; }
      const a = { file: f, progress: 0, thumb: /^image\//.test(f.type) ? URL.createObjectURL(f) : '' };
      S.attach.push(a);
      a.promise = uploadFile(f, p => { a.progress = p; drawChips(); })
        .then(info => { a.info = info; drawChips(); return info; })
        .catch(e => { a.error = e.message; drawChips(); toast(Tf("上传失败：{0}", e.message), true); return null; });
    }
    drawChips();
  };
  comp.addEventListener('dragover', e => { if ([...e.dataTransfer.types].includes('Files')) { e.preventDefault(); comp.classList.add('drop'); } });
  comp.addEventListener('dragleave', () => comp.classList.remove('drop'));
  comp.addEventListener('drop', e => { if (e.dataTransfer.files.length) { e.preventDefault(); comp.classList.remove('drop'); addFiles([...e.dataTransfer.files]); } });
  ta.addEventListener('paste', e => { const fs = [...(e.clipboardData || {}).files || []]; if (fs.length) { e.preventDefault(); addFiles(fs); } });
  comp.append(chips, h('div', { class: 'box' }, plus, picker, ta, btn));
  drawChips();
  thread.append(comp);
  requestAnimationFrame(grow);
  async function send() {
    const text = ta.value.trim(); if ((!text && !S.attach.length) || S.sending) return;
    S.sending = true; btn.disabled = true;
    try {
      const infos = (await Promise.all(S.attach.map(a => a.promise))).filter(Boolean);
      if (S.attach.length && infos.length < S.attach.length) throw new Error(T('有附件没有上传成功，请移除后再发送 Some files failed to upload'));
      const r = await api('chat', { method: 'POST', body: { message: text, conversation_id: S.conv, attachments: infos.map(i => i.path) } });
      S.attach.forEach(a => a.thumb && URL.revokeObjectURL(a.thumb)); S.attach = []; drawChips();
      ta.value = ''; S.draft = ''; grow();
      S.conv = r.conversation_id;
      await loadConvs(); await openConv(r.conversation_id);
    } catch (e) { toast(e.message, true); }
    finally { S.sending = false; btn.disabled = false; }
  }
  if (atBottom) { msgs.scrollTop = msgs.scrollHeight; requestAnimationFrame(() => { msgs.scrollTop = msgs.scrollHeight; }); }
  else if (keepScroll) msgs.scrollTop = keepScroll.scrollTop;
}

const fmtSize = n => n == null ? '' : n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(0) + ' KB' : (n / 1048576).toFixed(1) + ' MB';
const FILE_ICON = m => /pdf/.test(m) ? '📕' : /^image\//.test(m) ? '🖼' : /^video\//.test(m) ? '🎬' : /^audio\//.test(m) ? '🎵' : /sheet|excel|csv/.test(m) ? '📊' : /word|document/.test(m) ? '📘'
  : /presentation|powerpoint/.test(m) ? '📙' : /zip|compressed|tar/.test(m) ? '🗜' : '📄';
// a file the agent sent to the chat (send_file): download it, open it in a new tab, or see an image preview
function fileCard(j) {
  const url = 'api/files/raw?path=' + encodeURIComponent(j.path);
  const mime = j.mime || '';
  const canOpen = /^(application\/pdf|image\/(png|jpe?g|gif|webp)|text\/plain|text\/markdown|text\/csv|audio\/|video\/)/.test(mime);
  return h('div', { class: 'msg assistant' }, h('div', { class: 'bubble filecard', style: 'max-width:420px' },
    h('div', { class: 'row', style: 'gap:10px;align-items:center' },
      h('span', { style: 'font-size:28px;line-height:1' }, FILE_ICON(mime)),
      h('div', { style: 'flex:1;min-width:0' },
        h('div', { style: 'font-weight:600;overflow-wrap:anywhere' }, j.name),
        h('div', { class: 'small muted' }, [fmtSize(j.size), j.path].filter(Boolean).join(' · ')))),
    j.note ? h('div', { class: 'small', style: 'margin-top:6px' }, j.note) : null,
    /^image\/(png|jpe?g|gif|webp|avif|bmp)/.test(mime) ? h('img', { src: url, alt: j.name, loading: 'lazy',
      style: 'display:block;max-width:100%;max-height:260px;margin-top:8px;border-radius:8px' }) : null,
    /^(video|audio)\//.test(mime) ? h('div', { style: 'margin-top:8px' }, mediaEl(j)) : null,
    h('div', { class: 'row', style: 'gap:8px;margin-top:8px' },
      h('a', { class: 'btn small primary', href: url + '&download=1', download: j.name, style: 'text-decoration:none' }, T('⬇ 下载 Download')),
      canOpen ? h('a', { class: 'btn small', href: url, target: '_blank', rel: 'noopener', style: 'text-decoration:none' }, T('打开 Open')) : null)));
}

// upload one file for the chat (raw body PUT; progress via XHR)
function uploadFile(f, onProgress) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open('PUT', 'api/upload?name=' + encodeURIComponent(f.name));
    x.setRequestHeader('X-Persona-UI', '1');
    x.upload.onprogress = e => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    x.onload = () => {
      let j = {}; try { j = JSON.parse(x.responseText); } catch (e) {}
      if (x.status >= 200 && x.status < 300) resolve(j); else reject(new Error(j.detail || (x.status === 413 ? T('文件太大 File too large') : 'HTTP ' + x.status)));
    };
    x.onerror = () => reject(new Error(T('网络错误 network error')));
    x.send(f);
  });
}
const rawUrl = p => 'api/files/raw?path=' + encodeURIComponent(p);
// the files the user attached to a message (shown above their bubble)
function attachStrip(atts) {
  return h('div', { class: 'att-strip' }, atts.map(a => /^image\//.test(a.mime || '')
    ? h('a', { href: rawUrl(a.path), target: '_blank', rel: 'noopener', title: a.name }, h('img', { src: rawUrl(a.path), alt: a.name, loading: 'lazy' }))
    : h('a', { class: 'att-doc', href: rawUrl(a.path), target: '_blank', rel: 'noopener', title: a.name },
        h('span', { class: 'ic' }, /^video\//.test(a.mime || '') ? '🎬' : /^audio\//.test(a.mime || '') ? '🎵' : FILE_ICON(a.mime || '')),
        h('span', { class: 'nm' }, a.name), h('span', { class: 'small faint' }, fmtSize(a.size)))));
}
// media inside a card the agent sent: image preview, video / audio player
function mediaEl(it) {
  const url = rawUrl(it.path), m = it.mime || '';
  if (/^image\/(png|jpe?g|gif|webp|avif|bmp)/.test(m)) return h('a', { href: url, target: '_blank', rel: 'noopener' },
    h('img', { src: url, alt: it.name, loading: 'lazy', class: 'media-img' }));
  if (/^video\//.test(m)) return h('video', { src: url, controls: true, preload: 'metadata', playsinline: true, class: 'media-vid' });
  if (/^audio\//.test(m)) return h('audio', { src: url, controls: true, preload: 'metadata', style: 'width:100%' });
  return null;
}
// several files the agent sent at once (send_file paths=[…]): a gallery for photos, players for video, rows for the rest
function filesCard(j) {
  const items = j.items || [];
  const media = items.filter(it => /^(image|video|audio)\//.test(it.mime || ''));
  const other = items.filter(it => !media.includes(it));
  return h('div', { class: 'msg assistant' }, h('div', { class: 'bubble filecard', style: 'max-width:640px' },
    j.note ? h('div', { class: 'small', style: 'margin-bottom:8px' }, j.note) : null,
    media.length ? h('div', { class: 'gallery' + (media.length === 1 ? ' one' : '') }, media.map(it => h('div', { class: 'g-item', title: it.name }, mediaEl(it)))) : null,
    other.map(it => h('div', { class: 'row', style: 'gap:8px;align-items:center;margin-top:6px' },
      h('span', null, FILE_ICON(it.mime || '')), h('span', { style: 'flex:1;min-width:0;overflow-wrap:anywhere' }, it.name),
      h('span', { class: 'small faint' }, fmtSize(it.size)))),
    h('div', { class: 'row small', style: 'gap:10px;margin-top:8px;flex-wrap:wrap' }, items.map(it =>
      h('a', { href: rawUrl(it.path) + '&download=1', download: it.name }, Tf("⬇ {0}", it.name))))));
}

// options the agent offered (present_choices). "verified" = every name/detail was found in pages it actually read
function choicesCard(j, active) {
  const safe = u => /^https?:\/\//i.test(u || '') ? u : '';
  const host = u => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return u; } };
  const pick = async o => {
    if (!active || S.sending) return;
    S.sending = true;
    try {
      const r = await api('chat', { method: 'POST', body: { message: Tf("我选：{0}", o.label), conversation_id: S.conv } });
      await loadConvs(); await openConv(r.conversation_id);
    } catch (e) { toast(e.message, true); } finally { S.sending = false; }
  };
  return h('div', { class: 'msg assistant' }, h('div', { class: 'bubble choices' },
    j.question ? h('div', { class: 'choices-q' }, j.question) : null,
    j.verified ? h('div', { class: 'small', style: 'color:var(--ok);margin-bottom:6px' }, T('✓ 已核对：名称和细节都摘自 Agent 读过的原网页')) : null,
    h('div', { class: 'choice-grid' }, (j.options || []).map(o => h('div', { class: 'choice' },
      h('div', { class: 'choice-title' }, o.label),
      o.details && o.details.length ? h('ul', { class: 'small' }, o.details.map(x => h('li', null, x))) : null,
      o.note ? h('div', { class: 'small muted' }, '💬 ' + o.note) : null,
      safe(o.source_url) ? h('a', { class: 'small', href: safe(o.source_url), target: '_blank', rel: 'noopener noreferrer' }, '🔗 ' + host(o.source_url)) : null,
      h('button', { class: 'btn small' + (active ? ' primary' : ''), disabled: !active, onclick: () => pick(o) },
        active ? T('选这个 Choose') : T('已结束 done')))))));
}

function planList(plan) {
  if (!plan || !plan.steps || !plan.steps.length) return null;
  const mk = { pending: '○', running: '▸', done: '✓', failed: '✕', skipped: '–' };
  return h('ol', { class: 'plan' }, plan.steps.map(s => h('li', { class: s.status || 'pending' },
    h('span', { class: 'mk' }, mk[s.status || 'pending'] || '○'), h('span', { class: 'tx' }, s.description))));
}

function taskCard(t) {
  const active = !['COMPLETED', 'FAILED', 'CANCELLED'].includes(t.status);
  const card = h('div', { class: 'msg' }, h('div', { class: 'taskcard', id: 'tc-' + t.id },
    h('div', { class: 'head' }, pill(t.status),
      h('span', { class: 'goal', title: t.goal }, t.plan && t.plan.objective ? t.plan.objective : t.goal),
      active && t.status !== 'WAITING_APPROVAL' ? h('span', { class: 'typing dots' }, t.status === 'PLANNING' ? T('规划中') : T('执行中')) : null,
      active ? h('span', { class: 'small retry', style: 'color:var(--warn)', hidden: true }) : null,
      h('a', { class: 'small', href: '#tasks/' + t.id }, T('详情 Details'))),
    planList(t.plan),
    t.status === 'WAITING_APPROVAL' && t.waiting ? h('div', { class: 'row', style: 'margin-top:8px' },
      h('button', { class: 'btn approve small', onclick: () => openApproval(t.waiting.approval_id) }, T('🛡 审批：') + ((t.waiting.summary || {}).title || '')))
      : null,
    t.status === 'WAITING_EXTERNAL' ? h('div', { class: 'row', style: 'margin-top:8px' },
      h('a', { class: 'btn small', href: '#browser/' + t.id }, T('🖐 去浏览器接管 Take over'))) : null,
    t.status === 'FAILED' && t.error ? h('p', { class: 'small', style: 'color:var(--danger);margin:8px 0 0' }, t.error) : null,
    traceBox(t)));
  return card;
}

function traceBox(t) {
  const det = h('details', { class: 'trace' }, h('summary', null, T('执行过程 Activity')));
  const tl = h('div', { class: 'timeline', id: 'tl-' + t.id }, h('span', { class: 'small muted' }, T('加载中…')));
  det.append(tl);
  det.addEventListener('toggle', async () => {
    if (!det.open) return;
    const r = await api('tasks/' + t.id);
    S.events[t.id] = r.events;
    fillTimeline(tl, r.events);
  });
  return det;
}

function evLine(e) {
  const d = e.data || {};
  let body;
  switch (e.type) {
    case 'plan': body = h('span', null, Tf("📋 计划 Plan v{0}：{1} 步", (d.version || 1), ((d.steps || []).length))); break;
    case 'thinking': body = h('span', { class: 'muted' }, Tf("🤔 思考 step {0}", (d.step))); break;
    case 'reasoning': body = h('details', null, h('summary', { class: 'muted' }, T('💭 推理 reasoning')), h('pre', null, d.text)); break;
    case 'message': body = h('span', null, '💬 ', d.text); break;
    case 'tool_call': body = h('div', null, d.sub ? '↳ ' : '🔧 ', h('span', { class: 'tool' }, d.name), h('pre', null, JSON.stringify(d.args, null, 1))); break;
    case 'tool_result': body = h('details', null, h('summary', null, (d.ok === false ? '⚠️ ' : '✅ ') + d.name + T(' 结果 result')), h('pre', null, d.preview)); break;
    case 'waiting': body = h('span', { style: 'color:var(--approve)' }, d.type === 'approval' ? Tf("🛡 等待审批：{0}", B((d.summary || {}).title || d.tool)) : Tf("🖐 等待接管：{0}", (d.reason || ''))); break;
    case 'approval_resolved': body = h('span', null, Tf("🛡 审批结果：{0}", (d.decision))); break;
    case 'subagent_start': body = h('span', null, Tf("🧩 子 Agent ({0})：{1}", (d.role), (d.task))); break;
    case 'subagent_done': body = h('details', null, h('summary', null, Tf("🧩 子 Agent 完成 ({0})", (d.role))), h('pre', null, d.report)); break;
    case 'final': body = h('span', null, T('🏁 完成 Final')); break;
    case 'memory_saved': body = h('span', null, [
      (d.facts || []).length ? T('🧠 记住了：') + d.facts.join(T('；')) : '',
      (d.recent || []).length ? ' ' + T('⏳ 近期记忆：') + d.recent.join(T('；')) : '',
      (d.profile_suggestions || []).length ? ' ' + T('📝 档案修改待你确认（记忆页）：') + d.profile_suggestions.join(T('；')) : ''].join('').trim()); break;
    case 'context_used': body = h('details', null, h('summary', null, Tf("🧠 带上了 {0} 条相关记忆", (d.facts || []).length)),
      h('ul', { class: 'small' }, (d.facts || []).map(f => h('li', null, f.fact, f.status === 'pending' ? T('（未确认）') : '', h('span', { class: 'faint' }, f.why ? ' — ' + f.why : ''))))); break;
    case 'context_site': body = h('span', null, Tf("🧠 记得在 {0} 的习惯：{1}", d.site, (d.facts || []).join(T('；')))); break;
    case 'profile_read': body = h('span', { class: 'muted' }, Tf("🪪 读取档案：{0}", (d.fields || []).join(', ') || T('全部'))); break;
    case 'replanning': body = h('span', { style: 'color:var(--warn)' }, T('🔄 重新规划 Re-plan')); break;
    case 'llm_retry': body = h('span', { style: 'color:var(--warn)' }, Tf("🔁 模型重试 {0}/{1}：{2}，{3} 秒后再试", d.attempt, d.of, d.reason || '', d.wait_s)); break;
    case 'chart': body = h('span', null, Tf("📊 图表：{0}", (d.title || d.path || ''))); break;
    case 'image': body = h('span', null, Tf("🎨 生成图片：{0}", ((d.paths || []).join(', ') || d.path || '') + (d.model ? '  (' + d.model + ', ' + (d.size || '') + ', ' + (d.latency_s || '') + 's)' : ''))); break;
    case 'gave_up': body = h('span', { style: 'color:var(--warn)' }, T('🛑 同样的来源反复失败，停止重试，按已有信息作答')); break;
    case 'error': case 'planner_error': body = h('span', { style: 'color:var(--danger)' }, '❌ ' + (d.message || '')); break;
    default: body = h('span', { class: 'muted' }, e.type + ' ' + JSON.stringify(d).slice(0, 200));
  }
  return h('div', { class: 'ev' }, h('span', { class: 't' }, fmtClock(e.ts)), h('div', { class: 'b' }, body));
}
function fillTimeline(tl, events) {
  tl.innerHTML = '';
  if (!events.length) tl.append(h('span', { class: 'small muted' }, T('暂无 none')));
  events.filter(e => e.type !== 'thinking').forEach(e => tl.append(evLine(e)));
}

// ================================================================== TASKS
async function viewTasks(root) {
  const golden = S.taskFilter === 'golden';
  const r = await api('tasks' + (S.taskFilter && !golden ? '?status=' + S.taskFilter : ''));
  // golden (weekly test) runs live on the Trust page; the task list shows them only under their own filter
  r.tasks = r.tasks.filter(t => golden ? t.source === 'golden' : t.source !== 'golden');
  r.tasks.forEach(t => { S.tasks[t.id] = { ...(S.tasks[t.id] || {}), ...t }; });
  const filters = [['', T('全部 All')], ['RUNNING,PLANNING,CREATED', T('执行中 Running')], ['WAITING_APPROVAL,WAITING_EXTERNAL,PAUSED', T('等待中 Waiting')],
    ['COMPLETED', T('已完成 Done')], ['FAILED,CANCELLED', T('失败 Failed')], ['golden', T('🧪 黄金测试')]];
  const left = h('div', null, h('div', { class: 'filters' }, filters.map(([v, l]) => h('button', { class: S.taskFilter === v ? 'on' : '', onclick: () => { S.taskFilter = v; route(); } }, l))));
  const list = h('div', { class: 'list' });
  if (!r.tasks.length) list.append(h('div', { class: 'empty' }, T('还没有任务。去「对话」里给 OMuse 布置一个吧。')));
  for (const t of r.tasks) list.append(h('button', { class: 'item' + (S.selTask === t.id ? ' active' : ''), onclick: () => { location.hash = 'tasks/' + t.id; } },
    h('div', { class: 'top' }, pill(t.status), h('span', { class: 'title' }, t.goal)),
    h('div', { class: 'small muted' }, Tf("{0} · {1} · {2} 步", (fmtTime(t.created_at)), (t.source === 'schedule' ? T('⏰ 定时') : t.source === 'golden' ? T('🧪 黄金测试') : T('💬 对话')), (t.steps || 0)))));
  left.append(list);
  const right = h('div', { id: 'taskDetail' });
  root.append(h('div', { class: 'split' + (S.selTask ? ' has-sel' : '') }, left, right));
  if (S.selTask) renderTaskDetail(right, S.selTask);
  else right.append(h('div', { class: 'card empty' }, T('选择左侧任务查看计划、每一步工具调用和审批记录。')));
}

async function renderTaskDetail(box, id) {
  const t = await api('tasks/' + id);
  S.tasks[id] = { ...(S.tasks[id] || {}), ...t };
  S.events[id] = t.events;
  box.innerHTML = '';
  const active = !['COMPLETED', 'FAILED', 'CANCELLED'].includes(t.status);
  const act = (a) => safe(async () => { await api(`tasks/${id}/${a}`, { method: 'POST', body: {} }); toast(T('已提交 ') + a); setTimeout(() => renderTaskDetail(box, id), 500); });
  const tl = h('div', { class: 'timeline' }); fillTimeline(tl, t.events);
  box.append(h('div', { class: 'card stack' },
    h('button', { class: 'btn small only-narrow', onclick: () => { S.selTask = null; location.hash = 'tasks'; } }, T('← 任务列表 All tasks')),
    h('div', { class: 'row' }, pill(t.status), h('b', { style: 'flex:1' }, t.goal)),
    h('dl', { class: 'kv' },
      h('dt', null, T('任务 ID')), h('dd', { class: 'mono' }, t.id),
      h('dt', null, T('来源 Source')), h('dd', null, t.source === 'schedule' ? T('⏰ 定时任务 schedule') : t.source === 'golden' ? T('🧪 黄金测试（演练，不真正执行）') : T('💬 对话 chat')),
      h('dt', null, T('创建 Created')), h('dd', null, fmtTime(t.created_at)),
      h('dt', null, T('步数 Steps')), h('dd', null, t.steps || 0),
      t.outcome && t.outcome.status !== 'none' ? [h('dt', null, T('结果证据 Evidence')), h('dd', null, outcomeBadge(t.outcome))] : null,
      t.waiting ? [h('dt', null, T('等待 Waiting')), h('dd', null, t.waiting.type === 'approval' ? '🛡 ' + B((t.waiting.summary || {}).title || T('审批')) : '🖐 ' + (t.waiting.reason || t.waiting.type))] : null),
    h('div', { class: 'row' },
      t.status === 'WAITING_APPROVAL' && t.waiting ? h('button', { class: 'btn approve small', onclick: () => openApproval(t.waiting.approval_id) }, T('🛡 去审批')) : null,
      t.status === 'WAITING_EXTERNAL' ? h('a', { class: 'btn small', href: '#browser/' + t.id }, T('🖐 接管浏览器')) : null,
      ['RUNNING', 'PLANNING'].includes(t.status) ? h('button', { class: 'btn small', onclick: act('pause') }, T('⏸ 暂停 Pause')) : null,
      t.status === 'PAUSED' ? h('button', { class: 'btn small', onclick: act('resume') }, T('▶ 继续 Resume')) : null,
      active ? h('button', { class: 'btn danger small', onclick: act('cancel') }, T('■ 取消 Cancel')) : h('button', { class: 'btn small', onclick: act('retry') }, T('↻ 重新执行 Retry')),
      h('a', { class: 'btn small', href: '#activity', onclick: () => { S.auditTask = id; } }, T('📜 审计记录'))),
    t.plan && t.plan.steps && t.plan.steps.length ? h('div', null, h('b', null, T('计划 Plan')), planList(t.plan)) : null,
    t.result ? h('div', null, h('b', null, T('结果 Result')), mdEl(t.result)) : null,
    t.error ? h('p', { style: 'color:var(--danger)' }, t.error) : null,
    h('div', null, h('b', null, T('执行过程 Timeline')), tl)));
}

// Proof that a task which changed something really finished (order number, message id …) — app/runtime/outcome.py
function outcomeBadge(o) {
  const ev = (o.evidence || []).map(e => e.order_number ? Tf("订单号 {0}", e.order_number) : e.reference ? Tf("预订号 {0}", e.reference)
    : e.id ? `${e.kind} ${e.id}` : e.kind).join('，');
  return o.status === 'verified'
    ? h('span', { class: 'chip ok' }, T('✓ 已核实 verified') + (ev ? ' · ' + ev : ''))
    : h('span', { class: 'chip bad', title: (o.missing || []).join(', ') }, T('⚠ 未确认 not confirmed'));
}

// ================================================================== TRUST (metrics, health, golden runs)
async function viewTrust(root) {
  S.trustDays = S.trustDays || 7;
  const r = await api('metrics?days=' + S.trustDays);
  const m = r.metrics, hs = r.health || {}, g = r.golden || {};
  const pct = x => x == null ? '—' : Math.round(x * 100) + '%';
  const kpi = (label, value, note, cls) => h('div', { class: 'kpi' + (cls ? ' ' + cls : '') }, h('div', { class: 'kpi-v' }, value),
    h('div', { class: 'kpi-l' }, label), note ? h('div', { class: 'kpi-n' }, note) : null);
  const days = h('div', { class: 'filters' }, [7, 30].map(d => h('button', { class: S.trustDays === d ? 'on' : '', onclick: () => { S.trustDays = d; route(); } },
    Tf("最近 {0} 天", d))));
  const checkBtn = h('button', { class: 'btn small', onclick: safe(async () => { await api('health/check', { method: 'POST', body: {} }); route(); }) }, T('立即检查 Check now'));
  const runBtn = h('button', { class: 'btn small primary', disabled: !!g.running, onclick: safe(async () => {
    await api('golden/run', { method: 'POST', body: {} }); toast(T('黄金测试已开始，大约需要 30–60 分钟，完成后会通知你')); route(); }) },
    g.running ? T('黄金测试运行中…') : T('▶ 运行黄金测试 Run golden tasks'));
  // health
  const comps = Object.entries(hs.components || {});
  const names = { model: T('模型服务'), browser: T('浏览器'), sentinel: T('安全网关 Sentinel'), tasks: T('任务执行') };
  const health = h('div', { class: 'card stack' }, h('h3', null, T('🩺 运行状态 Health')),
    comps.length ? h('div', { class: 'stack' }, comps.map(([k, c]) => h('div', { class: 'row' },
      h('span', { class: 'chip ' + (c.ok ? 'ok' : 'bad') }, c.ok ? '✓' : '✕'), h('b', null, names[k] || k),
      h('span', { class: 'small muted', style: 'flex:1' }, c.detail || ''), c.down ? h('span', { class: 'small' }, Tf("自 {0}", fmtTime(c.since))) : null)))
      : h('p', { class: 'small muted' }, T('启动后约 1 分钟完成第一次检查。')),
    (hs.alerts || []).length ? h('details', null, h('summary', { class: 'small' }, Tf("最近告警 {0} 条", hs.alerts.length)),
      hs.alerts.slice().reverse().map(a => h('div', { class: 'small' }, `${fmtTime(a.ts)} ${a.title} — ${a.body.split('\n')[0]}`))) : null,
    h('div', { class: 'row' }, checkBtn));
  // metrics
  const tiles = h('div', { class: 'kpis' },
    kpi(T('完成率'), pct(m.completion_rate), Tf("{0}/{1} 个任务完成", m.completed, m.finished)),
    kpi(T('自主完成率'), pct(m.autonomous_rate), T('完成且不需要你批准、接管或回答')),
    kpi(T('需要你介入'), pct(m.intervention_rate), Tf("审批 {0} 次 · 接管 {1} 次", m.approvals, m.takeovers)),
    kpi(T('每个结果的审批次数'), m.approval_burden == null ? '—' : m.approval_burden.toFixed(1), Tf("{0} 个任务改变了外部世界", m.acted)),
    kpi(T('有证据 / 未确认'), `${m.verified} / ${m.unverified}`, T('订单号、邮件 ID 等证据'), m.unverified ? 'warn' : ''),
    kpi(T('失败'), m.failed, Tf("取消 {0}", m.cancelled), m.failed ? 'warn' : ''));
  const maxDay = Math.max(1, ...m.per_day.map(d => d.total));
  const perDay = h('div', { class: 'card stack' }, h('h3', null, T('📅 每天的任务')),
    h('div', { class: 'tablewrap' }, h('table', { class: 'data' },
      h('thead', null, h('tr', null, [T('日期'), T('总数'), T('完成'), T('失败'), T('取消'), ''].map(x => h('th', null, x)))),
      h('tbody', null, m.per_day.slice().reverse().map(d => h('tr', null, h('td', { class: 'mono' }, d.day), h('td', null, d.total),
        h('td', null, d.completed), h('td', { style: d.failed ? 'color:var(--danger)' : '' }, d.failed), h('td', null, d.cancelled),
        h('td', { style: 'width:40%' }, h('div', { class: 'bar' }, h('span', { class: 'ok', style: `width:${100 * d.completed / maxDay}%` }),
          h('span', { class: 'bad', style: `width:${100 * d.failed / maxDay}%` })))))))),
    m.failure_causes.length ? h('div', { class: 'small' }, T('失败原因：'), m.failure_causes.map(c => `${c.label} ${c.count}`).join(' · ')) : null,
    m.top_errors.length ? h('details', null, h('summary', { class: 'small' }, T('最常见的错误')),
      m.top_errors.map(e => h('div', { class: 'small mono' }, `${e.count}× ${e.error}`))) : null);
  // golden runs
  const last = (g.runs || [])[0];
  const golden = h('div', { class: 'card stack' }, h('h3', null, T('🧪 黄金测试任务 Golden tasks')),
    h('p', { class: 'sub' }, T('20 个日常任务，每周日凌晨 3 点自动演练一次：真实读邮件、浏览网页，但在发送、下单、改日历、打电话之前停下，不打扰你。')),
    h('div', { class: 'row' }, runBtn),
    (g.runs || []).length ? h('div', { class: 'small' }, g.runs.map(x => `${fmtTime(x.started_at)} ${x.version || ''}：${x.passed}/${x.total}` + (x.status === 'running' ? T('（运行中）') : '')).join('  ·  ')) : null,
    last ? h('div', { class: 'tablewrap' }, h('table', { class: 'data' },
      h('thead', null, h('tr', null, ['', T('任务'), T('用时'), T('没通过的原因')].map(x => h('th', null, x)))),
      h('tbody', null, (last.results || []).map(x => h('tr', null, h('td', null, x.passed ? '✅' : '❌'),
        h('td', null, x.task_id ? h('a', { href: '#tasks/' + x.task_id }, `${x.id} ${x.title}`) : `${x.id} ${x.title}`),
        h('td', { class: 'mono' }, x.seconds != null ? x.seconds + 's' : ''), h('td', { class: 'small' }, (x.why || []).join('；'))))))) : null);
  const ledgerCard = h('div', { class: 'card stack' }, h('h3', null, T('🧾 交易账本 Ledger')));
  const fewer = h('div', { class: 'stack' });
  root.append(h('div', { class: 'stack' }, h('div', { class: 'row' }, days), tiles, fewer, h('div', { class: 'grid2' }, health, golden), browserCard(m.browser || {}), ledgerCard, perDay));
  fillLedger(ledgerCard).catch(() => ledgerCard.append(h('div', { class: 'muted small' }, T('账本暂时打不开'))));
  fillSuggestions(fewer).catch(() => {});
}

function browserCard(b) {
  const pct = x => x == null ? '—' : Math.round(x * 100) + '%';
  const rows = b.sites || [];
  return h('div', { class: 'card stack' }, h('h3', null, T('🌐 浏览器打开情况 Browsing')),
    h('p', { class: 'sub' }, T('OMuse 打开网页的成功率，以及哪些网站用反机器人拦截挡住了自动浏览器。被挡的网站会记进「网站习惯」，下次优先换别的来源或请你接管。')),
    h('div', { class: 'row', style: 'gap:16px' },
      h('div', null, h('b', null, String(b.opens || 0)), ' ', h('span', { class: 'muted small' }, T('次打开'))),
      h('div', null, h('b', null, String(b.blocked || 0)), ' ', h('span', { class: 'muted small' }, T('次被拦')),
        b.block_rate != null ? h('span', { class: 'muted small' }, ` (${pct(b.block_rate)})`) : null)),
    rows.length ? h('div', { class: 'tablewrap' }, h('table', { class: 'data' },
      h('thead', null, h('tr', null, [T('网站'), T('打开'), T('被拦'), T('拦截率')].map(x => h('th', null, x)))),
      h('tbody', null, rows.map(r => h('tr', null, h('td', null, r.site), h('td', { class: 'mono' }, String(r.opens)),
        h('td', { class: 'mono' }, String(r.blocked)),
        h('td', null, h('span', { class: 'chip' + (r.block_rate > 0.5 ? ' bad' : '') }, pct(r.block_rate)))))))) :
      h('div', { class: 'muted small' }, T('最近没有网站拦截记录。')),
    (b.kinds || []).length ? h('div', { class: 'small muted' }, T('拦截类型：') + b.kinds.map(k => `${k.detail} ×${k.count}`).join('、')) : null);
}

async function fillSuggestions(box) {
  const r = await sapi('grant_suggestions');
  const list = r.suggestions || [];
  if (!list.length) return;
  const go = (k, body) => safe(async () => { await sapi('grant_suggestions', { method: 'POST', body: { key: k, ...body } }); route(); });
  box.append(h('div', { class: 'card stack' }, h('h3', null, T('🔁 可以少批的操作 Fewer approvals')),
    h('p', { class: 'sub' }, T('这些操作你已经批准过 3 次以上。开启后同样的操作不再弹审批卡（可随时在「连接」页撤销）。付款、填卡、打电话、取消/退货和网页点击永远逐次审批。')),
    list.map(x => h('div', { class: 'row', style: 'border-bottom:1px solid var(--line-2);padding-bottom:6px' },
      h('div', { style: 'flex:1;min-width:0' }, h('b', null, T(x.title)), x.destination ? h('span', { class: 'muted small' }, ' → ' + x.destination) : null,
        h('div', { class: 'small muted' }, Tf("最近 30 天批准了 {0} 次", x.count))),
      h('button', { class: 'btn approve small', onclick: go(x.key, { accept: true, days: 30 }) }, T('自动允许 30 天')),
      h('button', { class: 'btn small', onclick: go(x.key, { accept: true, days: 0 }) }, T('一直允许')),
      h('button', { class: 'btn small', onclick: go(x.key, { accept: false }) }, T('不用了'))))));
}

function ledgerProof(o) {
  const ev = (o.evidence || []).slice(-1)[0] || {};
  const proof = String(ev.subject || ev.text || '').slice(0, 80);
  return [o.approval_id ? T('你批准的') : '', proof].filter(Boolean).join(' · ');
}

async function fillLedger(card) {
  const r = await sapi('ledger');
  const rows = r.orders || [];
  const sync = h('button', { class: 'btn small', onclick: safe(async () => {
    const x = await sapi('ledger/reconcile', { method: 'POST', body: {} });
    toast(Tf("核对了 {0} 个订单，更新 {1} 个", x.checked, (x.changed || []).length)); route(); }) }, T('用邮件核对 Check emails'));
  card.append(h('p', { class: 'sub' }, T('OMuse 替你下的每一笔订单：商家、订单号、金额、卡、状态，以及谁批准的、凭什么证据。取消或退货时只认这里的订单。')),
    h('div', { class: 'row' }, sync),
    rows.length ? h('div', { class: 'tablewrap' }, h('table', { class: 'data' },
      h('thead', null, h('tr', null, [T('日期'), T('商家'), T('订单号'), T('金额'), T('卡'), T('状态'), T('批准 / 证据')].map(x => h('th', null, x)))),
      h('tbody', null, rows.map(o => h('tr', null,
        h('td', { class: 'mono small' }, fmtTime(o.created_at)), h('td', null, o.merchant),
        h('td', { class: 'mono' }, o.order_number || '—'),
        h('td', { class: 'mono' }, `${o.currency} ${Number(o.total || 0).toFixed(2)}`), h('td', { class: 'small' }, o.card || '—'),
        h('td', null, h('span', { class: 'chip' + (['placed', 'shipped', 'delivered'].includes(o.status) ? ' ok' : (['unconfirmed'].includes(o.status) ? ' bad' : '')) }, T(o.status_label))),
        h('td', { class: 'small' }, ledgerProof(o))))))) :
      h('div', { class: 'muted small' }, T('还没有订单。')));
}

// ================================================================== APPROVALS
async function loadApprovals() {
  try {
    const r = await sapi('approvals?status=pending');
    S.approvals = r.approvals;
  } catch (e) { return; }
  const n = S.approvals.length;
  $('#approvalCount').textContent = n; $('#approvalCount').hidden = !n;
  $('#approvalBell').classList.toggle('hot', n > 0);
  if (!$('#drawer').hidden) renderDrawer();
  const fresh = S.approvals.filter(a => !S.seenApprovals.has(a.id));
  fresh.forEach(a => S.seenApprovals.add(a.id));
  if (fresh.length && !$('.modal-back')) openApproval(fresh[0].id);
  document.title = n ? `(${n}) OMuse` : 'OMuse';
}

function approvalForm(a, onDone) {
  const s = a.summary || {};
  const editable = new Set(s.editable || []);
  const inputs = {};
  const box = h('div', { class: 'approval' });
  box.append(h('div', { class: 'ttl' }, h('b', null, '🛡 ' + B(s.title || a.tool)), riskPill(a.risk), h('span', { class: 'small muted mono' }, a.tool)));
  box.append(h('div', { class: 'small muted' }, Tf("任务 {0} · {1}", (a.task_id), (fmtTime(a.created_at)))));
  if (a.reason) box.append(h('div', { class: 'why' }, T('为什么需要审批：') + B(a.reason)));
  if (s.warning) box.append(h('div', { class: 'why' }, B(s.warning)));
  const kv = h('dl', { class: 'kv' });
  for (const [k, v] of s.fields || []) {
    const key = { '收件人 To': 'to', '抄送 Cc': 'cc', '主题 Subject': 'subject', '转发给 To': 'to', '标题 Title': 'title', '开始 Start': 'start', '结束 End': 'end', '地点 Location': 'location' }[k];  // i18n-ok: server field ids
    kv.append(h('dt', null, B(k)));
    if (key && editable.has(key)) { const inp = h('input', { type: 'text', value: v || '' }); inputs[key] = inp; kv.append(h('dd', null, inp)); }
    else kv.append(h('dd', null, v || '—'));
  }
  box.append(kv);
  if (Array.isArray(s.items)) {  // e.g. unsubscribe: one checkbox per email, untick to keep
    const METHOD = { 'one-click': T('一键退订 One-click'), email: T('发退订邮件 Email'), link: T('打开退订链接 Link') };
    const checks = [];
    const list = h('div', { class: 'itemlist' });
    for (const it of s.items) {
      const ok = !!it.method;
      const cb = h('input', { type: 'checkbox', checked: ok, disabled: !ok });
      cb.dataset.id = it.id; checks.push(cb);
      list.append(h('label', { class: 'item' + (ok ? '' : ' off') }, cb,
        h('span', { class: 'it-main' }, h('b', null, (it.from || '').replace(/<[^>]*>/, '').replace(/"/g, '').trim() || it.id), h('span', { class: 'muted' }, ' · ' + (it.subject || ''))),
        h('span', { class: 'small faint it-m' }, ok ? METHOD[it.method] || it.method : (B(it.error) || T('无退订信息 N/A')))));
    }
    const count = h('span', { class: 'small muted' });
    const upd = () => { count.textContent = Tf("已选 {0} / {1}（取消勾选 = 保留，不退订）", (checks.filter(c => c.checked).length), (s.items.length)); };
    checks.forEach(c => c.onchange = upd); upd();
    const all = (v) => () => { checks.forEach(c => { if (!c.disabled) c.checked = v; }); upd(); };
    box.append(h('div', { class: 'row' }, h('b', { class: 'small' }, T('要退订的邮件 Emails')), count,
      h('button', { class: 'btn small', onclick: all(true) }, T('全选')), h('button', { class: 'btn small', onclick: all(false) }, T('全不选'))), list);
    if (editable.has('message_ids')) inputs.message_ids = { get value() { return checks.filter(c => c.checked).map(c => c.dataset.id); } };
  }
  if (s.body !== undefined && s.body !== null) {
    const bodyKey = a.tool === 'phone_call' ? 'purpose' : a.tool === 'gmail_forward' ? 'note' : a.tool === 'browser_type' ? 'text' : (a.tool || '').startsWith('calendar_') ? 'description' : (a.tool || '').startsWith('notion_') ? 'content' : 'body';
    if (editable.has(bodyKey)) { const ta = h('textarea', { rows: 8 }); ta.value = s.body || ''; inputs[bodyKey] = ta; box.append(h('label', { class: 'field' }, h('span', null, T('内容（可修改后批准）Content — editable')), ta)); }
    else box.append(h('pre', { class: 'md', style: 'white-space:pre-wrap' }, s.body));
  }
  if (s.screenshot) box.append(h('img', { class: 'shot', src: `sentinel/api/approvals/${a.id}/screenshot`, alt: T('操作时的页面截图 page screenshot'), onerror: e => e.target.remove() }));
  const scope = h('select', { 'aria-label': T('授权范围 scope') },
    h('option', { value: 'ONCE' }, T('仅这一次 Approve once')),
    h('option', { value: 'TASK' }, T('本任务内同类操作 For this task')),
    h('option', { value: 'SESSION' }, T('8 小时内 For this session (8h)')),
    h('option', { value: 'TIME_BOUND' }, T('24 小时内 For 24 hours')),
    h('option', { value: 'PERMANENT' }, T('以后总是允许（同一目标）Always allow')));
  if (a.tool === 'browser_fill_secret') { scope.value = 'ONCE'; scope.disabled = true; }
  const note = h('input', { type: 'text', placeholder: T('拒绝原因（可选，会告诉 Agent）Reason for denying (optional)') });
  const approve = h('button', { class: 'btn approve' }, T('✓ 批准 Approve'));
  const deny = h('button', { class: 'btn danger' }, T('✕ 拒绝 Deny'));
  const resolve = async (decision) => {
    approve.disabled = deny.disabled = true;
    const args = {}; for (const [k, el] of Object.entries(inputs)) args[k] = el.value;
    try {
      const r = await sapi(`approvals/${a.id}/resolve`, { method: 'POST', body: { decision, scope: scope.value, ttl_hours: 24, args, note: note.value } });
      if (decision === 'approve') {
        const st = r.result && r.result.status;
        const res = (r.result && r.result.result) || {};
        const extra = res.results ? Tf("：退订成功 {0}，已打开页面 {1}，需手动/失败 {2}", (res.done || 0), (res.link_opened || 0), (res.manual_or_failed || 0)) : '';
        if (r.status === 'denied') toast(T('没有勾选任何邮件，已取消 Nothing selected'));
        else toast(st === 'ok' ? T('已批准并执行 ✓ Approved & executed') + extra : Tf("已批准，但执行结果：{0}", ((r.result && (r.result.error || st)) || r.reason || '')), st !== 'ok');
      } else toast(T('已拒绝 Denied'));
      onDone && onDone();
      loadApprovals();
    } catch (e) { toast(e.message, true); approve.disabled = deny.disabled = false; }
  };
  approve.onclick = () => resolve('approve');
  deny.onclick = () => resolve('deny');
  box.append(h('div', { class: 'ap-actions' }, h('div', { class: 'actions' }, approve, scope), h('div', { class: 'actions' }, deny, note)));
  return box;
}

function openApproval(id) {
  const a = S.approvals.find(x => x.id === id);
  if (!a) { toast(T('这个审批已处理或已过期 already resolved')); loadApprovals(); return; }
  closeModal();
  const back = h('div', { class: 'modal-back', onclick: e => { if (e.target === back) closeModal(); } });
  const m = h('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': T('审批 Approval') },
    h('div', { class: 'row' }, h('h2', { style: 'flex:1' }, T('OMuse 请求执行操作')), h('button', { class: 'icon-btn', onclick: closeModal, 'aria-label': T('稍后 later') }, '✕')),
    h('p', { class: 'small muted', style: 'margin:0' }, T('此请求来自 Sentinel（独立于 Agent）。你决定前任务会暂停。')),
    approvalForm(a, closeModal));
  back.append(m); $('#modalRoot').append(back);
}
function closeModal() { $('#modalRoot').innerHTML = ''; }

const AP_DONE = { approved: [T('✅ 已批准'), 'st-COMPLETED'], denied: [T('❌ 已拒绝'), 'st-FAILED'], expired: [T('⌛ 已过期'), 'st-CANCELLED'] };
function renderDrawer() {
  const b = $('#drawerBody'); b.innerHTML = '';
  if (!S.approvals.length) b.append(h('div', { class: 'empty' }, T('没有待审批的操作 ✓')));
  S.approvals.forEach(a => b.append(approvalForm(a)));
  const hist = h('div', { class: 'stack', style: 'gap:6px' });
  b.append(h('details', { class: 'ap-history', style: 'margin-top:16px' },
    h('summary', { class: 'small' }, h('b', null, T('最近已处理 Recent decisions'))), hist));
  sapi('approvals?status=resolved&limit=20').then(r => {
    if (!r.approvals.length) { hist.append(h('div', { class: 'small muted' }, T('还没有处理过的审批'))); return; }
    r.approvals.forEach(a => {
      const [lbl, cls] = AP_DONE[a.status] || [a.status, ''];
      const res = a.result || {};
      const why = a.status === 'expired' ? (res.reason || '') : a.decided_by === 'user' && a.scope && a.scope !== 'ONCE' ? Tf("范围 {0}", (a.scope)) : '';
      hist.append(h('div', { class: 'card', style: 'padding:8px 10px' },
        h('div', { class: 'row' }, h('span', { style: 'flex:1' }, B((a.summary || {}).title || a.tool)), h('span', { class: 'pill ' + cls }, lbl)),
        h('div', { class: 'small muted' }, `${fmtTime(a.resolved_at || a.created_at)} · ${a.tool}` + (why ? ' · ' + why : ''))));
    });
  }).catch(() => {});
}

// ================================================================== BROWSER
async function viewBrowser(root) {
  const banner = h('div', { class: 'banner agent' });
  const url = h('input', { type: 'text', class: 'url', placeholder: T('接管时可输入网址 URL (takeover only)'), 'aria-label': 'URL' });
  const img = h('img', { alt: T('Agent 浏览器实时画面 live view'), draggable: 'false' });
  const trap = h('textarea', { class: 'keytrap', 'aria-label': T('键盘输入 keyboard input') });
  const kbd = h('div', { class: 'kbd-hint' });
  const wrap = h('div', { class: 'screen-wrap' }, img, trap, kbd);
  const takeBtn = h('button', { class: 'btn take' }, T('🖐 接管 Take over'));
  const relBtn = h('button', { class: 'btn primary release' }, T('↩ 交还给 Agent Hand back'));
  // One tab per task (each chat's agent has its own page). Take over / screenshot / URL always belong to the SELECTED tab,
  // so a takeover never lands in another chat's browser (it used to follow whichever agent had acted last).
  const tabsBar = h('div', { class: 'btabs', role: 'tablist', 'aria-label': T('任务标签页 task tabs') });
  const reqList = h('div', { class: 'breqs' });
  const bar = h('div', { class: 'bbar' },
    h('button', { class: 'btn small', title: T('后退 back'), onclick: () => input({ type: 'back' }) }, '←'),
    h('button', { class: 'btn small', title: T('刷新 reload'), onclick: () => input({ type: 'reload' }) }, '⟳'),
    url, h('button', { class: 'btn small', onclick: () => go() }, T('前往 Go')));
  S.taskNames = S.taskNames || {};
  const nameOf = tid => {
    if (!tid || tid === 'default') return T('浏览器');
    if (!(tid in S.taskNames)) {
      S.taskNames[tid] = '';
      api('tasks/' + tid).then(t => { S.taskNames[tid] = (t && (t.goal || t.plan && t.plan.objective) || '').replace(/^\[\u6d4b\u8bd5\]\s*/, ''); refresh(true); }).catch(() => {});
    }
    const n = S.taskNames[tid] || tid.slice(0, 14);
    return n.length > 28 ? n.slice(0, 28) + '…' : n;
  };
  const host = u => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } };
  const select = async tid => {
    S.browserSel = tid;
    if (location.hash !== '#browser/' + tid) history.replaceState(null, '', '#browser/' + tid);
    try { await sapi('browser/view', { method: 'POST', body: { task_id: tid } }); } catch (e) {}
    refresh(true);
  };
  const takeOver = async tid => {
    // no task tab at all: the shared page (e.g. to log in to a site before asking OMuse anything)
    if (!tid && ((st.tasks || []).length || (st.requests || []).length)) { toast(T('请先选择要接管的任务标签页'), true); return; }
    S.browserSel = tid || null;
    st = await sapi('browser/takeover', { method: 'POST', body: { task_id: tid } });
    toast(Tf("你已接管「{0}」的浏览器，这个任务已暂停", nameOf(tid)));
    if (!isTouch()) trap.focus({ preventScroll: true });   // typing goes to the page right away (focus was on the button)
    refresh(true);
  };
  let urlDirty = false;
  const go = () => { urlDirty = false; input({ type: 'navigate', url: url.value }); };
  url.addEventListener('input', () => { urlDirty = true; });
  url.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); go(); } });
  const typeBox = h('input', { type: 'text', placeholder: T('接管时在此输入文字后回车发送到页面（密码不会被记录或给 Agent）') });
  const sendText = h('div', { class: 'row' }, typeBox, h('button', { class: 'btn small', onclick: () => { input({ type: 'text', text: typeBox.value }); typeBox.value = ''; } }, T('输入 Type')),
    ['Enter', 'Tab', 'Backspace', 'Escape'].map(k => h('button', { class: 'btn small', onclick: () => input({ type: 'key', key: k }) }, k)));
  typeBox.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); input({ type: 'text', text: typeBox.value }); typeBox.value = ''; } });
  root.append(h('div', { class: 'bview' }, banner, reqList, tabsBar, h('div', { class: 'row' }, takeBtn, relBtn), bar, sendText, wrap,
    h('p', { class: 'small muted' }, T('Agent 只能通过受限 API（打开网址 / 读取无障碍快照 / 点击 / 输入）操作这个浏览器，不能执行任意 JavaScript。接管期间 Agent 完全暂停，你的输入不会进入 Agent 上下文。'))));
  let st = {};
  // Inputs are sent strictly one after another (typing fast used to arrive out of order: "test" -> "tste").
  // Characters typed while a request is in flight are merged into the next "text" event.
  // Scrolling makes dozens of wheel events a second: they are merged while one is on its way, and anything still queued
  // is dropped once the takeover ended (2026-10-05: ~150 queued wheel events kept the user's clicks and keys waiting for
  // seconds, then all failed with "take over first" after the hand-back).
  let queue = Promise.resolve(), buf = null, wheel = null, refreshTimer = null, gen = 0;
  const send = async (ev, g) => {
    if (g !== gen || st.mode !== 'user') return;
    try { await sapi('browser/input', { method: 'POST', body: ev }); }
    catch (e) { if (/409|take over first|接管/.test(e.message)) { gen++; buf = wheel = null; refresh(true); } toast(e.message, true); }
    clearTimeout(refreshTimer); refreshTimer = setTimeout(() => refresh(true), 250);
  };
  function input(ev) {
    if (st.mode !== 'user') { toast(T('请先点击「接管 Take over」')); return queue; }
    const g = gen;
    if (ev.type === 'wheel') {
      if (wheel) { wheel.dx += ev.dx; wheel.dy += ev.dy; wheel.x = ev.x; wheel.y = ev.y; return queue; }
      const mine = wheel = { ...ev };
      buf = null;
      queue = queue.then(() => { if (wheel === mine) wheel = null; return send(mine, g); });
      return queue;
    }
    wheel = null;
    if (ev.type === 'text') {
      if (!ev.text) return queue;
      if (!buf) {   // open a text batch at this point of the queue; later characters join it until it is sent
        const mine = buf = { text: '' };
        queue = queue.then(() => { if (buf === mine) buf = null; return mine.text ? send({ type: 'text', text: mine.text }, g) : null; });
      }
      buf.text += ev.text;
      return queue;
    }
    buf = null;     // characters typed after this key must be sent after it
    queue = queue.then(() => send(ev, g));
    return queue;
  }
  takeBtn.onclick = safe(() => takeOver(S.browserSel));
  relBtn.onclick = safe(async () => { const was = st.takeover_task; gen++; buf = wheel = null; await sapi('browser/release', { method: 'POST', body: {} }); toast(Tf("已交还「{0}」，这个任务继续执行", nameOf(was))); refresh(true); });
  const kbdState = () => {
    const on = document.activeElement === trap;
    wrap.classList.toggle('kbd-on', on && st.mode === 'user');
    kbd.textContent = st.mode !== 'user' ? '' : on ? T('⌨️ 键盘已连接：直接输入（可粘贴 Ctrl/⌘+V）Keyboard connected') : T('👆 先点一下画面里的输入框，再用键盘输入 Click a field first');
  };
  trap.addEventListener('focus', kbdState); trap.addEventListener('blur', kbdState);
  img.addEventListener('click', e => {
    trap.focus({ preventScroll: true });
    if (st.mode !== 'user') { toast(T('请先点击「接管 Take over」')); return; }
    const r = img.getBoundingClientRect(), vw = img.naturalWidth || (st.viewport || {}).width || 1280, vh = img.naturalHeight || (st.viewport || {}).height || 800;
    input({ type: 'click', x: (e.clientX - r.left) / r.width * vw, y: (e.clientY - r.top) / r.height * vh });
  });
  img.addEventListener('wheel', e => {
    if (st.mode !== 'user') return; e.preventDefault();
    const r = img.getBoundingClientRect(), vw = img.naturalWidth || (st.viewport || {}).width || 1280, vh = img.naturalHeight || (st.viewport || {}).height || 800;
    input({ type: 'wheel', x: (e.clientX - r.left) / r.width * vw, y: (e.clientY - r.top) / r.height * vh, dx: e.deltaX, dy: e.deltaY });
  }, { passive: false });
  trap.addEventListener('keydown', e => {
    if (st.mode !== 'user' || e.isComposing) return;
    const special = ['Enter', 'Tab', 'Backspace', 'Delete', 'Escape', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown'];
    if (special.includes(e.key)) { e.preventDefault(); input({ type: 'key', key: e.key }); return; }
    // shortcuts: select all / undo / redo (Mac ⌘ is sent as Ctrl; paste is handled natively via the input event)
    if ((e.ctrlKey || e.metaKey) && /^[azy]$/i.test(e.key)) { e.preventDefault(); input({ type: 'key', key: 'Control+' + e.key.toLowerCase() }); }
  });
  // typing while nothing is focused (e.g. right after a click elsewhere) still goes to the remote page
  const docKeys = e => {
    if (S.view !== 'browser') { document.removeEventListener('keydown', docKeys); return; }
    if (st.mode !== 'user' || e.isComposing || e.ctrlKey || e.metaKey || e.altKey) return;
    const ae = document.activeElement;
    // the user is typing in the URL bar / text box etc. (a focused button, e.g. "Take over" just clicked, does not count:
    // keys typed then used to vanish)
    if (ae && ae !== trap && (/^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName) || ae.isContentEditable)) return;
    if (ae === trap) return;
    trap.focus({ preventScroll: true });
    if (e.key.length === 1) { e.preventDefault(); input({ type: 'text', text: e.key }); }
    else if (['Enter', 'Tab', 'Backspace', 'Delete', 'Escape'].includes(e.key)) { e.preventDefault(); input({ type: 'key', key: e.key }); }
  };
  if (S.browserKeys) document.removeEventListener('keydown', S.browserKeys);
  S.browserKeys = docKeys; document.addEventListener('keydown', docKeys);
  // Chinese / Japanese input methods: send the committed text once composition ends, not the pinyin letters in between
  let composing = false;
  trap.addEventListener('compositionstart', () => { composing = true; });
  trap.addEventListener('compositionend', () => { composing = false; if (st.mode === 'user' && trap.value) { input({ type: 'text', text: trap.value }); trap.value = ''; } });
  trap.addEventListener('input', e => { if (composing || e.isComposing) return; if (st.mode === 'user' && trap.value) { input({ type: 'text', text: trap.value }); trap.value = ''; } });
  let busy = false;
  async function refresh(force) {
    if (busy && !force) return; busy = true;
    try {
      st = await sapi('browser/state');
      const reqs = st.requests || (st.requested ? [st.requested] : []);
      const req = reqs[0];
      const tasks = (st.tasks || []).slice();
      reqs.forEach(r => { if (r.task_id && !tasks.some(t => t.task_id === r.task_id)) tasks.push({ task_id: r.task_id, url: '' }); });
      // which tab is selected: the one being taken over > the user's pick > the newest request > what agents show
      const ids = tasks.map(t => t.task_id);
      if (st.mode === 'user' && st.takeover_task) S.browserSel = st.takeover_task;
      else if (!S.browserSel || !ids.includes(S.browserSel)) S.browserSel = (req && req.task_id) || st.view_task || ids[0] || null;
      const sel = S.browserSel;
      banner.className = 'banner ' + (st.mode === 'user' ? 'user' : req ? 'req' : 'agent');
      banner.textContent = st.mode === 'offline' ? T('⚠️ 浏览器服务未就绪 browser offline: ') + (st.error || '') :
        st.mode === 'user' ? Tf("🖐 你正在控制「{0}」的浏览器（只有这个任务暂停，其他任务照常进行）。完成登录/验证后点击「交还给 Agent」。", nameOf(st.takeover_task)) :
        reqs.length > 1 ? Tf("🙋 {0} 个任务在等你接管，见下方列表，每个任务有自己的「接管」按钮", reqs.length) :
        req ? Tf("🙋「{0}」请求你接管：{1}", nameOf(req.task_id), (req.reason || '')) : T('🤖 Agent 控制中 — 实时画面 Live view');
      reqList.innerHTML = '';
      if (st.mode !== 'offline') reqs.forEach(r => reqList.append(h('div', { class: 'breq' + (r.task_id === sel ? ' on' : '') },
        h('span', { class: 'who' }, '🙋 ' + nameOf(r.task_id)), h('span', { class: 'why small' }, r.reason || ''),
        h('button', { class: 'btn small', disabled: st.mode === 'user' && st.takeover_task !== r.task_id,
          title: st.mode === 'user' && st.takeover_task !== r.task_id ? T('请先交还当前接管的任务') : '',
          onclick: safe(() => r.task_id === st.takeover_task ? null : takeOver(r.task_id)) },
          r.task_id === st.takeover_task ? T('接管中') : T('🖐 接管这个')))));
      tabsBar.innerHTML = '';
      tasks.forEach(t => {
        const asking = reqs.some(r => r.task_id === t.task_id), mine = st.mode === 'user' && st.takeover_task === t.task_id;
        tabsBar.append(h('button', { class: 'btab' + (t.task_id === sel ? ' on' : '') + (asking ? ' ask' : ''), role: 'tab',
          'aria-selected': String(t.task_id === sel), title: t.task_id + (t.url ? ' · ' + t.url : ''),
          onclick: safe(() => (st.mode === 'user' ? null : select(t.task_id))) },
          (mine ? '🖐 ' : asking ? '🙋 ' : '') + nameOf(t.task_id), host(t.url) ? h('span', { class: 'host' }, host(t.url)) : null));
      });
      if (!tasks.length) tabsBar.append(h('span', { class: 'small muted' }, T('（无标签页 no tabs）')));
      const selTask = tasks.find(t => t.task_id === sel);
      if (st.popup && st.mode !== 'offline') banner.textContent += T(' ｜ 🪟 正在显示弹出窗口（如 Google 登录）；它关闭后会自动回到原页面 Popup window shown — returns to the page automatically when it closes.');
      wrap.classList.toggle('user', st.mode === 'user'); kbdState();
      takeBtn.disabled = st.mode === 'user' || (!sel && tasks.length > 0); relBtn.disabled = st.mode !== 'user';
      takeBtn.textContent = sel ? Tf("🖐 接管「{0}」", nameOf(sel)) : T('🖐 接管 Take over');
      relBtn.textContent = st.mode === 'user' ? Tf("↩ 交还「{0}」给 Agent", nameOf(st.takeover_task)) : T('↩ 交还给 Agent Hand back');
      if (document.activeElement !== url && !urlDirty) url.value = (selTask && selTask.url) || st.url || '';
      const shotTask = st.mode === 'user' ? st.takeover_task : sel;
      const r = await fetch('sentinel/api/browser/screenshot?ts=' + Date.now() + (shotTask ? '&task_id=' + encodeURIComponent(shotTask) : ''));
      if (r.status === 200) { const b = await r.blob(); const u = URL.createObjectURL(b); const old = img.src; img.src = u; if (old.startsWith('blob:')) URL.revokeObjectURL(old); }
    } catch (e) { banner.textContent = '⚠️ ' + e.message; }
    finally { busy = false; }
  }
  refresh(true);
  S.browserTimer = setInterval(() => { if (!document.hidden) refresh(); }, 1200);
}

// Human description of a schedule / trigger / goal check (server sends Chinese; build English here).
function cronText(spec) {
  const p = String(spec || '').trim().split(/\s+/);
  if (p.length !== 5 || !/^\d+$/.test(p[0]) || !/^\d+$/.test(p[1]) || p[2] !== '*' || p[3] !== '*') return null;
  const t = `${p[1]}:${p[0].padStart(2, '0')}`;
  const en = LANG === 'en';
  const DAYS = en ? ['Sundays', 'Mondays', 'Tuesdays', 'Wednesdays', 'Thursdays', 'Fridays', 'Saturdays', 'Sundays']
    : ['每周日', '每周一', '每周二', '每周三', '每周四', '每周五', '每周六', '每周日'];
  if (p[4] === '*') return en ? `Daily at ${t}` : `每天 ${t}`;
  if (p[4] === '1-5') return en ? `Weekdays at ${t}` : `工作日 ${t}`;
  if (/^[0-7]$/.test(p[4])) return en ? `${DAYS[+p[4]]} at ${t}` : `${DAYS[+p[4]]} ${t}`;
  return null;
}
// Human description of a schedule / trigger / goal check (server sends Chinese; build English here).
function schedDesc(x) {
  if (x.kind === 'cron' && cronText(x.spec)) return cronText(x.spec);
  if (LANG !== 'en') return x.describe || x.check || '';
  if (x.kind === 'event') {
    let d = {}; try { d = JSON.parse(x.spec || '{}'); } catch (e) { /* ignore */ }
    const src = { 'gmail.new_email': 'New email', 'slack.new_message': 'New Slack message', 'notion.db_changed': 'Notion database changed' }[d.source] || d.source;
    const p = Object.entries(d.params || {}).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join(', ');
    return `${src}${p ? ' · ' + p : ''} · checked every ${d.every || 3} min`;
  }
  if (x.kind === 'interval') return `every ${x.spec} min`;
  return `cron ${x.spec || ''}`;
}

// ================================================================== AUTOMATIONS (goals, triggers, schedules)
const GOAL_ST = { active: [T('进行中 Active'), 'st-RUNNING'], paused: [T('已暂停 Paused'), 'st-PAUSED'], achieved: [T('已达成 Achieved'), 'st-COMPLETED'],
  failed: [T('未达成 Failed'), 'st-FAILED'], expired: [T('已过期 Expired'), 'st-CANCELLED'], cancelled: [T('已取消 Cancelled'), 'st-CANCELLED'],
  blocked: [T('需要你帮忙 Blocked'), 'st-WAITING_EXTERNAL'] };
const SRC_FIELDS = {
  'gmail.new_email': [['query', T('邮件搜索条件（可选）'), T('例如 from:boss@acme.com 或 is:important；留空 = 所有新邮件')], ['account', T('只看某个邮箱（可选）'), 'you@gmail.com']],
  'slack.new_message': [['channel', T('Slack 频道'), '#general'], ['keyword', T('包含关键词才触发（可选）'), T('例如 urgent')], ['mentions_only', T('只在 @我 时触发（填 yes）'), 'yes']],
  'notion.db_changed': [['database_id', T('Notion 数据库 ID 或链接'), 'https://www.notion.so/…']],
  'web.page': [['url', T('要监控的网页'), 'https://…'], ['mode', T('条件：change / text / price_below'), 'price_below'],
    ['text', T('等待出现的文字（mode=text）'), 'In stock'], ['threshold', T('价格低于（mode=price_below）'), '15'],
    ['keyword', T('只看这个词附近（可选，如商品名）'), 'iPhone 17 Pro Max']],
};
function checkPicker(defKind = 'interval') {
  const kind = h('select', null, h('option', { value: 'interval' }, T('每隔 N 分钟 Interval')), h('option', { value: 'cron' }, T('按时间 Cron')),
    h('option', { value: 'event' }, T('有新事件时 Event')));
  kind.value = defKind;
  const spec = h('input', { type: 'text', value: '60' });
  const src = h('select', null, Object.keys(SRC_FIELDS).map(k => h('option', { value: k }, { 'gmail.new_email': T('📧 收到新邮件'), 'slack.new_message': T('💬 Slack 新消息'), 'notion.db_changed': T('📝 Notion 数据库变化'), 'web.page': T('🌐 网页变化 / 降价 / 到货') }[k])));
  const every = h('input', { type: 'number', min: '1', value: '3', style: 'width:80px' });
  const pbox = h('div', { class: 'stack' });
  const inputs = {};
  const renderParams = () => { pbox.innerHTML = ''; for (const k in inputs) delete inputs[k];
    SRC_FIELDS[src.value].forEach(([k, l, ph]) => { inputs[k] = h('input', { type: 'text', placeholder: ph }); pbox.append(h('label', { class: 'field' }, h('span', null, l), inputs[k])); }); };
  src.onchange = renderParams; renderParams();
  const specField = h('label', { class: 'field', style: 'flex:1' }, h('span', null, T('规则 Spec')), spec);
  const evBox = h('div', { class: 'stack' }, h('div', { class: 'row' }, h('label', { class: 'field', style: 'flex:2' }, h('span', null, T('事件来源 Source')), src),
    h('label', { class: 'field', style: 'flex:1' }, h('span', null, T('每几分钟检查')), every)), pbox);
  const sync = () => { const ev = kind.value === 'event'; evBox.style.display = ev ? '' : 'none'; specField.style.display = ev ? 'none' : '';
    if (kind.value === 'cron' && /^\d+$/.test(spec.value)) spec.value = '0 9 * * *'; if (kind.value === 'interval' && !/^\d+$/.test(spec.value)) spec.value = '60'; };
  kind.onchange = sync;
  const el = h('div', { class: 'stack' }, h('div', { class: 'row' }, h('label', { class: 'field', style: 'flex:1' }, h('span', null, T('检查方式 How often')), kind), specField), evBox);
  const onlyEvent = () => { kind.value = 'event'; kind.closest('label').style.display = 'none'; sync(); };
  sync();
  return { el, onlyEvent, value: () => kind.value === 'event'
    ? { kind: 'event', spec: { source: src.value, every: Number(every.value) || 3, params: Object.fromEntries(Object.entries(inputs).map(([k, i]) => [k, i.value.trim()]).filter(([, v]) => v)) } }
    : { kind: kind.value, spec: spec.value } };
}

// Why a schedule did not produce a result: its last run is still waiting on you, or runs were skipped / superseded.
const LAST_RUN = { WAITING_APPROVAL: T('⏳ 上次运行在等你审批'), WAITING_EXTERNAL: T('⏳ 上次运行在等你接管浏览器'), PAUSED: T('⏸ 上次运行已暂停'),
  CREATED: T('▶ 正在运行'), PLANNING: T('▶ 正在运行'), RUNNING: T('▶ 正在运行'), COMPLETED: T('✅ 上次运行完成'), FAILED: T('❌ 上次运行失败'),
  CANCELLED: T('⛔ 上次运行已取消') };
function schedNotice(s) {
  const b = s.blocked || {}, out = [];
  if (s.last_status && LAST_RUN[s.last_status]) {
    const waitingYou = s.last_status === 'WAITING_APPROVAL';
    out.push(h('div', { class: 'row', style: 'gap:8px' }, h('span', { class: 'pill st-' + s.last_status }, LAST_RUN[s.last_status]),
      waitingYou ? h('button', { class: 'btn small', onclick: () => { $('#drawer').hidden = false; renderDrawer(); } }, T('去审批 Review')) : null));
  }
  if (b.skipped) out.push(h('div', { class: 'small', style: 'color:var(--warn)' },
    Tf("⚠️ {0} 到点时上一次运行还没结束，这次被跳过了（共 {1} 次）", (fmtTime(b.skipped.ts)), (b.skipped.count || 1))));
  if (b.superseded) out.push(h('div', { class: 'small muted' },
    Tf("ℹ️ {0} 上一次运行一直没完成，已自动取消并重新运行", (fmtTime(b.superseded.ts)))));
  return out.length ? h('div', { class: 'stack', style: 'gap:4px' }, out) : null;
}

async function viewSchedules(root) {
  const [r, gr] = await Promise.all([api('schedules'), api('goals')]);
  const scheds = r.schedules.filter(s => s.kind !== 'event'), triggers = r.schedules.filter(s => s.kind === 'event');
  // ---- goals
  const gTitle = h('input', { type: 'text', placeholder: T('例如：拿到 John 对合同的确认') });
  const gObj = h('textarea', { rows: 3, placeholder: T('要达成什么？背景是什么？OMuse 每次检查时会读这段话。例如：John 还没确认合同条款。每天检查他有没有回信；3 天没回就起草一封礼貌的跟进邮件（发送需要我批准）。') });
  const gCrit = h('input', { type: 'text', placeholder: T('怎样算完成？例如：John 回信确认同意') });
  const gDl = h('input', { type: 'date' });
  const gCheck = checkPicker('interval');
  const goalForm = h('details', { open: !gr.goals.length }, h('summary', null, h('b', null, T('＋ 新目标 New goal'))),
    h('div', { class: 'stack', style: 'margin-top:10px' },
      h('label', { class: 'field' }, h('span', null, T('标题 Title')), gTitle),
      h('label', { class: 'field' }, h('span', null, T('目标描述 Objective')), gObj),
      h('label', { class: 'field' }, h('span', null, T('完成标准 Success criteria')), gCrit),
      gCheck.el,
      h('label', { class: 'field' }, h('span', null, T('截止日期 Deadline（可选）')), gDl),
      h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: safe(async () => {
        await api('goals', { method: 'POST', body: { title: gTitle.value, objective: gObj.value, criteria: gCrit.value, deadline: gDl.value, run_now: true, ...gCheck.value() } });
        toast(T('已创建目标，正在进行第一次检查')); route();
      }) }, T('创建并开始 Create & start')))));
  const goalCard = g => {
    const [stl, stc] = GOAL_ST[g.status] || [g.status, ''];
    const last = (g.progress || []).slice(-1)[0];
    const blocked = last && last.status === 'blocked' && g.status === 'active';
    return h('div', { class: 'card stack goal-card' },
      h('div', { class: 'row' }, h('b', { style: 'flex:1' }, '🎯 ' + g.title), blocked ? h('span', { class: 'pill st-WAITING_EXTERNAL' }, T('🙋 需要你帮忙')) : null, h('span', { class: 'pill ' + stc }, stl)),
      h('div', { class: 'small' }, g.objective),
      g.criteria ? h('div', { class: 'small muted' }, T('✅ 完成标准：') + g.criteria) : null,
      h('div', { class: 'small muted' }, `🔁 ${schedDesc(g)}` + (g.deadline ? Tf(" · ⏳ 截止 {0}", (fmtTime(g.deadline))) : '') + (g.status === 'active' && g.next_run ? Tf(" · 下次检查 {0}", (fmtTime(g.next_run))) : '')),
      g.state_error ? h('div', { class: 'small', style: 'color:var(--danger)' }, '⚠️ ' + B(g.state_error)) : null,
      (g.progress || []).length ? h('details', { open: g.status === 'active' }, h('summary', { class: 'small' }, Tf("进展记录 Progress（{0}）", (g.progress.length))),
        h('ol', { class: 'goal-log' }, g.progress.slice().reverse().slice(0, 12).map(p => h('li', null,
          h('span', { class: 'muted' }, `${p.at} `), h('span', { class: 'pill ' + ((GOAL_ST[p.status] || [])[1] || '') }, (GOAL_ST[p.status] || [p.status])[0].split(' ')[0]), ' ', p.note)))) : h('div', { class: 'small muted' }, T('还没有进展记录')),
      h('div', { class: 'row' },
        g.status === 'active' ? h('button', { class: 'btn small', onclick: safe(async () => { await api(`goals/${g.id}/run`, { method: 'POST', body: {} }); toast(T('已开始检查')); }) }, T('▶ 立即检查 Check now')) : null,
        g.status === 'active' ? h('button', { class: 'btn small', onclick: safe(async () => { await api('goals/' + g.id, { method: 'PUT', body: { status: 'paused' } }); route(); }) }, T('⏸ 暂停')) : null,
        g.status === 'paused' ? h('button', { class: 'btn small', onclick: safe(async () => { await api('goals/' + g.id, { method: 'PUT', body: { status: 'active' } }); route(); }) }, T('▶ 继续')) : null,
        h('button', { class: 'btn small', onclick: () => { location.hash = 'chat'; setTimeout(() => openConv(g.conv_id), 50); } }, T('查看运行记录')),
        h('button', { class: 'btn danger small', onclick: safe(async () => { if (!confirmInline(Tf("删除目标「{0}」？", (g.title)))) return; await api('goals/' + g.id, { method: 'DELETE' }); route(); }) }, T('删除'))));
  };
  const goals = h('div', { class: 'card stack' },
    h('div', { class: 'row' }, h('h3', { style: 'flex:1' }, T('🎯 场景目标 Goals')), h('span', { class: 'chip' }, Tf("{0} 个进行中", (gr.goals.filter(g => g.status === 'active').length)))),
    h('p', { class: 'sub' }, T('交给 OMuse 一个需要几天才能完成的目标，它会按你设定的频率（或有新事件时）检查进展、推进下一步，直到达成或到截止时间。发送、提交等操作照常需要你审批；达成、失败或需要你帮忙时会通知你（包括 Telegram）。也可以直接在对话里说「帮我盯着……直到……」。')),
    goalForm, gr.goals.length ? gr.goals.map(goalCard) : null);
  // ---- triggers
  const tName = h('input', { type: 'text', placeholder: T('例如：老板来信提醒') });
  const tGoal = h('textarea', { rows: 3, placeholder: T('有新事件时要做什么（完整指令）。例如：总结这封邮件的要点和需要我做的事，用 notify_user 发给我；如果是会议邀请，查一下我那天的安排。') });
  const tCheck = checkPicker('event'); tCheck.onlyEvent();
  const trigForm = h('details', { open: !triggers.length }, h('summary', null, h('b', null, T('＋ 新触发器 New trigger'))),
    h('div', { class: 'stack', style: 'margin-top:10px' },
      h('label', { class: 'field' }, h('span', null, T('名称 Name')), tName), tCheck.el,
      h('label', { class: 'field' }, h('span', null, T('要做什么 Then do')), tGoal),
      h('p', { class: 'small muted' }, T('创建后第一次检查只记录现状，之后出现的新邮件/消息/修改才会触发。OMuse 自己发的消息、自己改的页面不会触发，避免循环。')),
      h('p', { class: 'small muted' }, T('网页监控：「要做什么」留空 = 只给你发通知（不运行 Agent）。同一个变化只提醒一次；检查失败会自动拉长间隔，连续失败会停用并告诉你。')),
      h('div', null, h('button', { class: 'btn primary', onclick: safe(async () => {
        const v = tCheck.value();
        let goal = tGoal.value;
        if (v.spec.source === 'web.page' && !goal.trim()) { v.spec.action = 'notify'; goal = T('（只通知）') + tName.value; }  // a watch that just tells you
        const s = await api('schedules', { method: 'POST', body: { name: tName.value, goal, kind: 'event', spec: v.spec } });
        await api(`schedules/${s.id}/poll`, { method: 'POST', body: {} }).catch(() => {});
        toast(T('已创建触发器 Created')); route();
      }) }, T('创建 Create')))));
  const schedRow = (s, isTrig) => h('div', { class: 'card stack' },
    h('div', { class: 'row' }, h('b', { style: 'flex:1' }, (isTrig ? '⚡ ' : '⏰ ') + s.name),
      h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: !!s.enabled, onchange: safe(async e => { await api('schedules/' + s.id, { method: 'PUT', body: { enabled: e.target.checked } }); }) }), T('启用'))),
    h('div', { class: 'small' }, s.goal),
    h('div', { class: 'small muted' }, isTrig ? `${schedDesc(s)}` + (s.trigger._checked ? Tf(" · 上次检查 {0}", (s.trigger._checked)) : '') + (s.trigger._seen ? Tf(" · 读到 {0}", (s.trigger._seen)) : '') + (s.last_run ? Tf(" · 上次触发 {0}", (fmtTime(s.last_run))) : '')
      : Tf("{0} · {1} · 下次 next: {2} · 上次 last: {3}", (schedDesc(s)), (s.tz), (fmtTime(s.next_run)), (fmtTime(s.last_run) || '—'))),
    isTrig && s.trigger._error ? h('div', { class: 'small', style: 'color:var(--danger)' }, '⚠️ ' + B(s.trigger._error)) : null,
    schedNotice(s),
    Object.keys(s.state || {}).length ? h('pre', { class: 'small', style: 'white-space:pre-wrap;margin:0' }, JSON.stringify(s.state, null, 1)) : null,
    h('div', { class: 'row' },
      isTrig ? h('button', { class: 'btn small', onclick: safe(async () => { const p = await api(`schedules/${s.id}/poll`, { method: 'POST', body: {} });
        toast(p.error ? '⚠️ ' + p.error : p.fired ? T('发现新事件，已开始运行') : T('没有新事件 Nothing new'), !!p.error); route(); }) }, T('🔍 立即检查 Check now'))
        : h('button', { class: 'btn small', onclick: safe(async () => { await api(`schedules/${s.id}/run`, { method: 'POST', body: {} }); toast(T('已开始运行')); }) }, T('▶ 立即运行 Run now')),
      h('button', { class: 'btn small', onclick: () => { location.hash = 'chat'; setTimeout(() => openConv(s.conv_id), 50); } }, T('查看结果 Results')),
      h('button', { class: 'btn danger small', onclick: safe(async () => { await api('schedules/' + s.id, { method: 'DELETE' }); route(); }) }, T('删除 Delete'))));
  const trig = h('div', { class: 'card stack' }, h('h3', null, T('⚡ 事件触发 Triggers')),
    h('p', { class: 'sub' }, T('「当……发生时，自动做……」。例如：收到老板的邮件就总结给我；Slack #support 有人提到 urgent 就整理问题；Notion 任务表有新任务就排进计划。')),
    trigForm, triggers.map(s => schedRow(s, true)));
  // ---- schedules
  const name = h('input', { type: 'text', placeholder: T('例如：每日邮件简报') });
  const goal = h('textarea', { rows: 3, placeholder: T('每次运行时 Agent 要做什么（完整指令）。例如：总结过去 24 小时的重要邮件，如有需要我回复的，用 notify_user 通知我。') });
  const kind = h('select', null, h('option', { value: 'cron' }, T('Cron 表达式')), h('option', { value: 'interval' }, T('间隔（分钟）Interval')));
  const spec = h('input', { type: 'text', value: '0 8 * * *' });
  const presets = [[T('每天 8:00'), 'cron', '0 8 * * *'], [T('工作日 9:00'), 'cron', '0 9 * * 1-5'], [T('每周五 17:00'), 'cron', '0 17 * * 5'], [T('每小时'), 'interval', '60']];
  const sch = h('div', { class: 'card stack' }, h('h3', null, T('⏰ 定时任务 Schedules')),
    h('details', { open: !scheds.length }, h('summary', null, h('b', null, T('＋ 新定时任务 New schedule'))),
      h('div', { class: 'stack', style: 'margin-top:10px' },
        h('p', { class: 'sub' }, T('也可以直接在对话里说「每天早上 8 点……」，Agent 会自动创建。')),
        h('label', { class: 'field' }, h('span', null, T('名称 Name')), name),
        h('label', { class: 'field' }, h('span', null, T('任务 Goal')), goal),
        h('div', { class: 'row' }, h('label', { class: 'field', style: 'flex:1' }, h('span', null, T('类型 Kind')), kind), h('label', { class: 'field', style: 'flex:1' }, h('span', null, T('规则 Spec')), spec)),
        h('div', { class: 'row' }, presets.map(([l, k, v]) => h('button', { class: 'btn small', onclick: () => { kind.value = k; spec.value = v; } }, l))),
        h('div', null, h('button', { class: 'btn primary', onclick: safe(async () => {
          await api('schedules', { method: 'POST', body: { name: name.value, goal: goal.value, kind: kind.value, spec: spec.value } });
          toast(T('已创建 Created')); route();
        }) }, T('创建 Create'))))),
    scheds.map(s => schedRow(s, false)));
  root.append(goals, h('div', { style: 'height:16px' }), h('div', { class: 'grid2' }, trig, sch));
}

// ================================================================== CONNECTIONS
async function viewConnections(root) {
  const [r, g] = await Promise.all([sapi('connections'), sapi('grants')]);
  const byName = Object.fromEntries(r.connections.map(c => [c.name, c]));
  const gm = byName.gmail, br = byName.browser, tg = byName.telegram;
  const permRow = (conn, key, zh, en, risk) => h('div', { class: 'perm' },
    h('div', null, h('div', null, zh + ' ', LANG === 'en' ? null : h('span', { class: 'muted small' }, en)), h('div', { class: 'small muted' }, riskPill(risk))),
    h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: !!conn.permissions[key], onchange: safe(async e => {
      await sapi('connections/' + conn.name, { method: 'PUT', body: { permissions: { [key]: e.target.checked } } }); toast(T('已保存 Saved'));
    }) })));

  // --- Email (Gmail and other providers)
  const gmail = emailCard(gm, permRow);

  // --- Browser
  const blocked = h('textarea', { rows: 2, placeholder: T('每行一个域名，如 example.com') }); blocked.value = (br.config.blocked_domains || []).join('\n');
  const allowed = h('textarea', { rows: 2, placeholder: T('信任的域名：即使任务读过机密数据也可直接访问') }); allowed.value = (br.config.allowed_domains || []).join('\n');
  const browser = h('div', { class: 'card stack' },
    h('div', { class: 'row' }, h('h3', { style: 'flex:1' }, T('🌐 浏览器 Browser')), h('span', { class: 'chip ok' }, 'Chromium')),
    h('p', { class: 'sub' }, T('独立的 Chromium，登录状态保存在本机。Agent 只能用受限 API，不能执行 JS；无法访问内网/集群地址。')),
    h('div', null, permRow(br, 'browse', T('浏览与读取'), 'browse', 'low'), permRow(br, 'interact', T('点击与输入（提交/购买/删除类需审批）'), 'interact', 'medium'),
      permRow(br, 'upload', T('上传文件（需审批）'), 'upload', 'high'), permRow(br, 'download', T('下载（隔离扫描）'), 'download', 'low')),
    h('label', { class: 'field' }, h('span', null, T('禁止访问的域名 Blocked domains')), blocked),
    h('label', { class: 'field' }, h('span', null, T('信任的域名 Trusted domains')), allowed),
    h('div', null, h('button', { class: 'btn small', onclick: safe(async () => { await sapi('connections/browser', { method: 'PUT', body: { config: { blocked_domains: blocked.value, allowed_domains: allowed.value } } }); toast(T('已保存 Saved')); }) }, T('保存 Save'))));

  // --- Telegram (two-way control)
  const tok = h('input', { type: 'password', placeholder: tg.has_credential ? T('已保存 saved（不改可留空）') : '123456:AA…', autocomplete: 'new-password' });
  const chat = h('input', { type: 'text', value: tg.config.chat_id || '', placeholder: 'chat id' });
  const tgState = h('span', { class: 'small muted' });
  const detect = safe(async () => {
    const r = await sapi('connections/telegram/detect', { method: 'POST', body: { bot_token: tok.value } });
    if (!r.chats.length) { toast(T('没找到：请先在 Telegram 里给你的机器人发一条 /start，再点检测 (send /start to your bot first)'), true); return; }
    chat.value = r.chats[r.chats.length - 1].chat_id; toast(Tf("找到 {0}：{1}", (r.chats[r.chats.length - 1].name), (chat.value)));
  });
  const telegram = h('div', { class: 'card stack' },
    h('div', { class: 'row' }, h('h3', { style: 'flex:1' }, T('📱 Telegram 遥控 Remote control')), h('span', { class: 'chip ' + (tg.has_credential && tg.enabled ? 'ok' : '') }, tg.has_credential && tg.enabled ? T('已连接') : T('未配置'))),
    h('p', { class: 'sub' }, T('在 Telegram 里直接给 OMuse 发消息布置任务、看进度和结果；需要审批时点 ✅ 批准 / ❌ 拒绝；需要登录时发来浏览器接管链接。只响应下面这个 chat id（你本人），其他人发消息一律忽略。')),
    h('ol', { class: 'steps-help' },
      h('li', null, T('在 Telegram 找 @BotFather，发 /newbot 创建机器人，复制它给的 Bot Token')),
      h('li', null, T('给你的新机器人发一条 /start')),
      h('li', null, T('在下面填 Token，点「检测 Chat ID」，再点「保存并连接」')),
      h('li', null, T('建议在 Telegram 设置里开启「两步验证 Two-Step Verification」'))),
    h('label', { class: 'field' }, h('span', null, 'Bot Token'), tok),
    h('label', { class: 'field' }, h('span', null, T('Chat ID（你本人）')), h('div', { class: 'row', style: 'flex-wrap:nowrap' }, chat, h('button', { class: 'btn small', onclick: detect }, T('检测 Chat ID')))),
    h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: safe(async () => { await sapi('connections/telegram/credential', { method: 'POST', body: { bot_token: tok.value, chat_id: chat.value } }); toast(T('Telegram 已连接，已发送测试消息')); route(); }) }, T('保存并连接 Save & connect')),
      tg.has_credential ? h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: tg.enabled, onchange: safe(async e => { await sapi('connections/telegram', { method: 'PUT', body: { enabled: e.target.checked } }); }) }), T('启用')) : null,
      tgState));
  if (tg.has_credential) sapi('telegram/status').then(st => {
    tgState.textContent = st.running ? Tf("🟢 在线 @{0}", (st.username || '')) : st.last_error ? `🔴 ${B(st.last_error)}` : T('⏳ 连接中…');
  }).catch(() => {});

  // --- Grants
  const grants = h('div', { class: 'card stack' }, h('h3', null, T('🛡 已授权规则 Standing approvals')),
    h('p', { class: 'sub' }, T('你在审批时选择「本任务 / 8 小时 / 24 小时 / 总是允许」后生成的规则。疑似提示注入的任务会忽略这些规则。')),
    g.grants.length ? h('div', { class: 'tablewrap' }, h('table', { class: 'data' },
      h('thead', null, h('tr', null, [T('操作 Tool'), T('范围 Scope'), T('目标 Destination'), T('到期 Expires'), ''].map(x => h('th', null, x)))),
      h('tbody', null, g.grants.map(x => h('tr', null, h('td', { class: 'mono' }, x.tool), h('td', null, x.scope), h('td', null, (x.match || {}).destination || T('任意 any')),
        h('td', null, x.expires_at ? fmtTime(x.expires_at) : (x.scope === 'TASK' ? T('任务结束') : T('永久'))),
        h('td', null, h('button', { class: 'btn danger small', onclick: safe(async () => { await sapi('grants/' + x.id, { method: 'DELETE' }); route(); }) }, T('撤销 Revoke'))))))))
      : h('div', { class: 'muted small' }, T('暂无。所有高风险操作都会逐次询问你。')));
  // --- Notion
  const nt = byName.notion, sl = byName.slack;
  const tokenCard = (conn, o) => {
    const inp = h('input', { type: 'password', placeholder: conn.has_credential ? T('已保存 saved — 粘贴新令牌可替换') : o.ph, autocomplete: 'new-password' });
    const connected = conn.has_credential && conn.enabled;
    return h('div', { class: 'card stack' },
      h('div', { class: 'row' }, h('h3', { style: 'flex:1' }, o.title), h('span', { class: 'chip ' + (connected ? 'ok' : '') }, connected ? Tf("已连接 {0}", (o.who(conn.config))) : T('未连接 Not connected'))),
      h('p', { class: 'sub' }, o.desc),
      h('details', { open: !conn.has_credential }, h('summary', null, h('b', null, conn.has_credential ? T('更换令牌 Change token') : T('连接 Connect'))),
        h('div', { class: 'stack', style: 'margin-top:10px' }, h('ol', { class: 'steps-help' }, o.steps.map(x => h('li', null, x))),
          h('label', { class: 'field' }, h('span', null, o.label), inp),
          h('div', null, h('button', { class: 'btn primary', onclick: safe(async e => {
            e.target.disabled = true;
            try { const r = await sapi(`connections/${conn.name}/credential`, { method: 'POST', body: { token: inp.value } }); toast(o.ok(r)); route(); }
            finally { e.target.disabled = false; }
          }) }, T('连接并测试 Connect & test'))))),
      h('div', null, h('b', null, T('权限 Permissions')), o.perms.map(([k, zh, en, risk]) => permRow(conn, k, zh, en, risk))),
      conn.has_credential ? h('div', { class: 'row' },
        h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: conn.enabled, onchange: safe(async e => { await sapi('connections/' + conn.name, { method: 'PUT', body: { enabled: e.target.checked } }); }) }), T('启用')),
        h('button', { class: 'btn danger small', onclick: safe(async () => { if (!confirmInline(Tf("断开 {0}？令牌会被删除。", (o.title)))) return; await sapi(`connections/${conn.name}/credential`, { method: 'DELETE' }); route(); }) }, T('断开 Disconnect'))) : null);
  };
  const notion = tokenCard(nt, {
    title: '📝 Notion', ph: 'ntn_…', label: T('集成令牌 Internal integration secret'), who: c => c.workspace || '',
    desc: T('读写你的 Notion 页面和数据库：查资料、把报告写进 Notion、更新任务表。OMuse 只能看到你主动共享给它的页面。'),
    steps: [h('span', null, T('打开 '), h('a', { href: 'https://www.notion.so/my-integrations', target: '_blank', rel: 'noopener' }, 'notion.so/my-integrations'), T('，新建一个「内部集成 Internal integration」，名字填 OMuse')),
      T('复制它的「密钥 Internal Integration Secret」（ntn_ 开头），粘贴到下面'),
      T('在要给 OMuse 用的页面或数据库右上角 ••• → 连接 Connections → 选择 OMuse（子页面会自动继承）')],
    ok: r => Tf("Notion 已连接 ✓ {0}，能看到 {1} 个页面", (r.workspace), (r.visible.length)) + (r.visible.length ? '' : T('（记得把页面共享给集成）')),
    perms: [['read', T('读取与搜索'), 'read', 'low'], ['write', T('新建 / 追加 / 修改页面（归档需审批）'), 'write', 'medium']] });
  const slack = tokenCard(sl, {
    title: '💬 Slack', ph: T('xoxb-… 或 xoxp-…'), label: T('Slack 令牌 Token'), who: c => `${c.team || ''}${c.token_type === 'user' ? T(' · 用户令牌') : T(' · 机器人')}`,
    desc: T('读取频道和讨论串、在你批准后发消息；配合「自动化」可以做到「#support 有人提到 urgent 就整理给我」。'),
    steps: [h('span', null, T('打开 '), h('a', { href: 'https://api.slack.com/apps', target: '_blank', rel: 'noopener' }, 'api.slack.com/apps'), ' → Create New App → From scratch'),
      T('OAuth & Permissions 里添加 Bot Token Scopes：channels:history, channels:read, groups:history, groups:read, im:history, im:read, users:read, chat:write（想用搜索：再加 User Token Scope search:read，并使用 xoxp- 用户令牌）'),
      T('Install to Workspace，复制 Bot User OAuth Token（xoxb- 开头）粘贴到下面'),
      T('在要让 OMuse 读取的频道里输入 /invite @你的应用名')],
    ok: r => Tf("Slack 已连接 ✓ {0}，已加入 {1} 个频道", (r.team), (r.member_of.length)),
    perms: [['read', T('读取频道 / 讨论串 / 搜索'), 'read', 'low'], ['send', T('发送消息（每次需审批）'), 'send — approval', 'high']] });
  const calendar = calendarCard(byName.calendar, permRow);
  const phoneC = phoneCard(byName.phone);
  const mcp = await mcpCard();
  root.append(h('div', { class: 'grid2' }, gmail, h('div', { class: 'stack' }, browser, telegram)), h('div', { style: 'height:16px' }),
    h('div', { class: 'grid2' }, notion, slack), h('div', { style: 'height:16px' }), calendar, h('div', { style: 'height:16px' }), phoneC, h('div', { style: 'height:16px' }), mcp,
    h('div', { style: 'height:16px' }), grants);
}

// --- Phone calls (Telnyx number + OpenAI Realtime voice); keys stay in Sentinel's vault
// OAuth 2.1 sign-in (DialMCP, MCP servers): opens the provider's login page; the callback page tells us when it's done
async function oauthPopup(path, body) {
  const redirect_uri = new URL('sentinel/api/oauth/callback', location.href).href.split('#')[0];
  const r = await sapi(path, { method: 'POST', body: Object.assign({}, body || {}, { redirect_uri }) });
  const done = e => {
    if (e.origin !== location.origin || !e.data || !('omuseOAuth' in e.data)) return;
    window.removeEventListener('message', done);
    if (e.data.omuseOAuth) { toast(T('登录完成 ✓ Signed in')); route(); }
  };
  window.addEventListener('message', done);
  const w = window.open(r.auth_url, '_blank');
  if (!w) location.href = r.auth_url;
  else toast(T('请在新打开的页面里登录，完成后回到这里'));
}

function phoneCard(c) {
  c = c || { name: 'phone', config: {}, permissions: {}, enabled: false, has_credential: false };
  const cf = c.config || {};
  const dm = c.dialmcp || {};
  const dmConnect = safe(async () => { await oauthPopup('connections/phone/dialmcp/start', {}); });
  const dmDisconnect = safe(async () => { if (!confirmInline(T('断开 DialMCP？令牌会被删除。'))) return; await sapi('connections/phone/dialmcp', { method: 'DELETE' }); route(); });
  const provider = h('select', { onchange: safe(async e => { await sapi('connections/phone', { method: 'PUT', body: { config: { provider: e.target.value } } }); toast(T('已保存')); }) },
    [['auto', T('自动：+1 号码走 DialMCP，其他走 Telnyx')], ['dialmcp', T('只用 DialMCP')], ['telnyx', T('只用 Telnyx')]]
      .map(([v, l]) => h('option', { value: v, selected: (cf.provider || 'auto') === v }, l)));
  const dmBox = h('div', { class: 'card stack', style: 'background:var(--bg2,transparent)' },
    h('div', { class: 'row' }, h('b', { style: 'flex:1' }, T('DialMCP — 用你自己的号码打美国/加拿大电话')),
      h('span', { class: 'chip ' + (dm.connected ? 'ok' : '') }, dm.connected ? Tf("已连接 {0}", ((dm.account || {}).phone || '')) : T('未连接'))),
    h('div', { class: 'small muted' }, T('DialMCP 的语音 AI 会先说明自己是替你打电话的 AI、通话会录音；只能打 +1（美国/加拿大）号码，对方当地时间 8:00–21:00，每通最长 10 分钟。登录一次即可，令牌加密保存在 Sentinel 保险箱。')),
    h('div', { class: 'row' }, dm.connected
      ? h('button', { class: 'btn danger small', onclick: dmDisconnect }, T('断开 DialMCP'))
      : h('button', { class: 'btn primary small', onclick: dmConnect }, T('连接 DialMCP（登录）')),
      h('label', { class: 'field', style: 'flex:1;min-width:220px' }, h('span', null, T('线路选择 Line')), provider)));
  const inp = (v, ph, type) => { const i = h('input', { type: type || 'text', placeholder: ph || '', autocomplete: 'off' }); i.value = v || ''; return i; };
  const owner = inp(cf.owner_name, 'Lucas Lu');
  const from = inp(cf.from_number, '+19793471777');
  const connId = inp(cf.connection_id, '2xxxxxxxxxxxxxxxxxx');
  const pub = inp(cf.public_url, 'https://omuse.example.com');
  const tkey = inp('', c.has_credential ? T('已保存 saved — 不改可留空') : 'KEY0…', 'password');
  const okey = inp('', c.has_credential ? T('已保存 saved — 不改可留空') : 'sk-…', 'password');
  const pkey = inp('', T('可选 optional — Telnyx 公钥 (webhook 签名)'), 'password');
  const prefixes = inp((cf.allowed_prefixes || ['+65', '+1']).join(', '), '+65, +1');
  const maxm = inp(String(cf.max_minutes || 10), '10', 'number');
  const daily = inp(String(cf.daily_limit || 10), '10', 'number');
  const voice = h('select', null, ['marin', 'cedar', 'alloy', 'coral', 'sage', 'verse', 'shimmer', 'echo', 'ash', 'ballad'].map(v => h('option', { value: v, selected: (cf.voice || 'marin') === v }, v)));
  const checks = h('div', { class: 'small stack' });
  const LABEL = { telnyx: T('Telnyx API Key'), number: T('号码与 Voice API 应用'), openai: T('OpenAI API Key / 模型'), public_url: T('公开地址（Telnyx 连得上）') };
  const showChecks = (r) => { checks.innerHTML = ''; Object.entries(r.checks || {}).forEach(([k, v]) => checks.append(h('div', null, (v === 'ok' ? '✅ ' : '⚠️ ') + (LABEL[k] || k) + (v === 'ok' ? '' : ' — ' + B(v))))); };
  const body = () => ({ owner_name: owner.value, from_number: from.value, connection_id: connId.value, public_url: pub.value,
    telnyx_api_key: tkey.value, openai_api_key: okey.value, telnyx_public_key: pkey.value, allowed_prefixes: prefixes.value,
    max_minutes: maxm.value, daily_limit: daily.value, voice: voice.value });
  const save = safe(async e => {
    e.target.disabled = true;
    try { const r = await sapi('connections/phone/credential', { method: 'POST', body: body() }); showChecks(r); toast(r.ready ? T('电话已配置 ✓') : T('已保存，但还有项目没通过检查')); }
    finally { e.target.disabled = false; }
  });
  const check = safe(async () => showChecks(await sapi('connections/phone/test', { method: 'POST', body: {} })));
  const testTo = inp('', '+65 8xxx xxxx');
  const testCall = safe(async e => {
    e.target.disabled = true;
    try { const r = await sapi('phone/test_call', { method: 'POST', body: { to: testTo.value } }); toast(Tf("正在拨打 {0}，请接听", (r.to))); setTimeout(() => loadCalls(), 5000); }
    finally { e.target.disabled = false; }
  });
  const calls = h('div', { class: 'stack small' });
  const ST = { dialing: T('📞 拨号中'), connected: T('🟢 通话中'), ended: T('✔ 已结束'), no_answer: T('无人接听'), failed: T('❌ 失败') };
  const link = (u, label) => u ? h('a', { href: u, target: '_blank', rel: 'noopener noreferrer' }, label) : null;
  const loadCalls = async () => {
    const r = await sapi('phone/calls?limit=10'); calls.innerHTML = '';
    if (!r.calls.length) { calls.append(h('div', { class: 'muted' }, T('还没有通话记录'))); return; }
    r.calls.forEach(x => calls.append(h('details', null,
      h('summary', null, h('b', null, x.to), ' · ', ST[x.status] || x.status, ' · ', fmtTime(x.created_at), x.outcome ? ' · ' + x.outcome : '',
        x.line === 'dialmcp' ? ' · DialMCP' : ''),
      h('div', { class: 'stack', style: 'margin:6px 0 10px' },
        (x.listen_url || x.recording_url) ? h('div', { class: 'row' }, link(x.listen_url, T('🎧 旁听 / 通话页 Listen')), link(x.recording_url, T('⏺ 录音 Recording'))) : null,
        h('div', null, h('b', null, T('目的 Purpose')), ' ', x.purpose),
        x.summary ? h('div', null, h('b', null, T('结果 Summary')), ' ', x.summary) : null,
        (x.hangup_cause || x.error) ? h('div', { class: 'muted' }, B(x.error || x.hangup_cause)) : null,
        h('pre', { class: 'md', style: 'white-space:pre-wrap;max-height:260px;overflow:auto' },
          (x.transcript || []).map(t => `[${t.t}s] ${t.who === 'omuse' ? 'OMuse' : T('对方')}: ${t.text}`).join('\n') || T('（没有对话内容）'))))));
  };
  const tReady = c.has_credential && c.enabled && cf.connection_id && cf.from_number && /^https?:\/\//.test(cf.public_url || '');
  const ready = c.enabled && (tReady || dm.connected);
  const field = (label, el, hint) => h('label', { class: 'field' }, h('span', null, label), el, hint ? h('small', { class: 'muted' }, hint) : null);
  const card = h('div', { class: 'card stack' },
    h('div', { class: 'row' }, h('h3', { style: 'flex:1' }, T('☎️ 电话 Phone calls')), h('span', { class: 'chip ' + (ready ? 'ok' : '') }, ready ? Tf("已配置 {0}", (tReady ? cf.from_number : ((dm.account || {}).phone || 'DialMCP'))) : T('未配置 Not set up'))),
    h('p', { class: 'sub' }, T('让 OMuse 替你打电话（问客服、预约、确认订单）。每通电话都要你批准，开头会说明自己是替你打电话的 AI；不会付款、不会报卡号密码验证码。两条线路：DialMCP（美国/加拿大，用你自己的号码）和 Telnyx（自己的号码 + OpenAI Realtime，可打其他国家）。')),
    dmBox,
    h('details', { open: !tReady && !dm.connected }, h('summary', null, h('b', null, tReady ? T('Telnyx 线路设置 Settings') : T('Telnyx 线路（可选）Set up'))),
      h('div', { class: 'stack', style: 'margin-top:10px' },
        h('ol', { class: 'steps-help' },
          h('li', null, T('Telnyx 控制台 → Voice → Programmable Voice → 新建 Voice API 应用（Call Control），Webhook 填下面「公开地址」+ /voice/webhook；复制它的 Application ID')),
          h('li', null, T('Numbers → 你的号码 → 分配给这个 Voice API 应用')),
          h('li', null, T('Voice → Outbound Voice Profiles → 新建并关联这个应用，允许要拨打的国家（如新加坡、美国），建议设每日消费上限')),
          h('li', null, T('Account → API Keys 新建一个 Key；OpenAI 平台新建一个 API Key')),
          h('li', null, T('公开地址：这台 OMuse 的 https 网址（电话端口只提供通话音频接口）'))),
        field(T('你的名字（AI 会说“替 … 打电话”）'), owner),
        h('div', { class: 'grid2' }, field(T('外呼号码 From number'), from), field(T('Voice API 应用 ID (Connection ID)'), connId)),
        field(T('公开地址 Public URL'), pub),
        h('div', { class: 'grid2' }, field('Telnyx API Key', tkey), field('OpenAI API Key', okey)),
        field(T('Telnyx 公钥（可选）Public key'), pkey, T('填了才会接受 Telnyx 的 webhook 状态通知；不填也能打电话')),
        h('div', { class: 'grid2' }, field(T('允许拨打的国家码'), prefixes), field(T('声音 Voice'), voice)),
        h('div', { class: 'grid2' }, field(T('每通最长（分钟）'), maxm), field(T('每天最多几通'), daily)),
        h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: save }, T('保存并检查 Save & check')),
          c.has_credential ? h('button', { class: 'btn small', onclick: check }, T('重新检查 Check')) : null), checks)),
    ready ? h('div', { class: 'row', style: 'flex-wrap:nowrap' }, testTo, h('button', { class: 'btn small', style: 'white-space:nowrap', onclick: testCall }, T('打给我测试 Test call'))) : null,
    h('div', null, h('b', null, T('最近通话 Recent calls')), ' ', h('button', { class: 'btn small', onclick: safe(loadCalls) }, T('刷新'))), calls,
    (c.has_credential || dm.connected) ? h('div', { class: 'row' },
      h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: c.enabled, onchange: safe(async e => { await sapi('connections/phone', { method: 'PUT', body: { enabled: e.target.checked } }); }) }), T('启用')),
      c.has_credential ? h('button', { class: 'btn danger small', onclick: safe(async () => { if (!confirmInline(T('断开电话？密钥会被删除。'))) return; await sapi('connections/phone/credential', { method: 'DELETE' }); route(); }) }, T('断开 Telnyx Disconnect')) : null) : null);
  loadCalls().catch(() => {});
  return card;
}

// --- Google Calendar (OAuth with the user's own Google Cloud client; tokens stay in Sentinel's vault)
// ================================================================== EMAIL (Gmail, Outlook, Yahoo, iCloud, QQ, 163/126, Zoho, AOL, any IMAP)
const MAIL_LABELS = { qq: 'QQ 邮箱 / Foxmail', netease: '网易邮箱 163 / 126 / yeah.net', custom: '其他邮箱（IMAP / SMTP）' };  // i18n-ok (translated via T below)
function mailLabel(p) { return MAIL_LABELS[p.key] ? T(MAIL_LABELS[p.key]) : p.label; }
function mailLink(url, text) { return h('a', { href: url, target: '_blank', rel: 'noopener' }, text || url.replace(/^https:\/\//, '').replace(/\/.*$/, '')); }
function mailSteps(key) {
  const li = (...k) => h('li', null, ...k);
  const S = {
    gmail: [li(T('确认该 Google 账号已开启两步验证 (2-Step Verification)。')),
      li(T('打开 '), mailLink('https://myaccount.google.com/apppasswords', 'myaccount.google.com/apppasswords'), T('，新建一个应用专用密码。')),
      li(T('把 16 位密码粘贴到下方，点击「连接并测试」。同一邮箱再添加一次 = 更新密码。'))],
    outlook: [li(T('微软从 2024 年 9 月起不再允许 Outlook / Hotmail 用密码连接第三方应用，需要用 OAuth 2.0（开放授权）登录。为此要先在微软 Entra 注册一个你自己的应用（免费，约 5 分钟；只有个人微软账号的话，可能要先免费开通 Azure 账号）。')),
      li(T('打开 '), mailLink('https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade', 'entra.microsoft.com'), T(' →「应用注册 App registrations」→「新注册 New registration」；支持的账户类型选「任何组织目录中的帐户和个人 Microsoft 帐户」。')),
      li(T('在「身份验证 Authentication」里打开「允许公共客户端流 Allow public client flows」。')),
      li(T('在「API 权限 API permissions」→「添加权限」→ Microsoft Graph →「委托的权限」，勾选 IMAP.AccessAsUser.All、SMTP.Send、offline_access。')),
      li(T('复制「概述 Overview」页的「应用程序(客户端) ID」，和邮箱一起填到下方，点「用微软账号登录」，再按提示在微软页面输入登录码。'))],
    yahoo: [li(T('打开 '), mailLink('https://login.yahoo.com/account/security'), T('（账户安全 Account security）。')),
      li(T('点「生成应用密码 Generate app password」，名称填 OMuse。')), li(T('把生成的密码粘贴到下方，点击「连接并测试」。'))],
    aol: [li(T('打开 '), mailLink('https://login.aol.com/account/security'), T('（账户安全 Account security）。')),
      li(T('点「生成应用密码 Generate app password」，名称填 OMuse。')), li(T('把生成的密码粘贴到下方，点击「连接并测试」。'))],
    icloud: [li(T('确认 Apple 账户已开启双重认证，并且已在 iPhone / Mac 上启用 iCloud 邮件。')),
      li(T('打开 '), mailLink('https://account.apple.com'), T(' →「登录与安全 Sign-In and Security」→「App 专用密码 App-Specific Passwords」，新建一个。')),
      li(T('邮箱填你的 @icloud.com 地址，把密码粘贴到下方。'))],
    qq: [li(T('登录 '), mailLink('https://mail.qq.com'), T(' →「设置 → 账号」，找到「POP3/IMAP/SMTP/Exchange/CardDAV 服务」，开启「IMAP/SMTP 服务」。')),
      li(T('按提示用手机验证后，会得到一个授权码 (authorization code)。')), li(T('把授权码（不是 QQ 密码）粘贴到下方，点击「连接并测试」。'))],
    netease: [li(T('登录网页版 163 / 126 邮箱 →「设置 → POP3/SMTP/IMAP」，开启「IMAP/SMTP 服务」。')),
      li(T('按提示获取授权码 (authorization code)。')), li(T('把授权码（不是登录密码）粘贴到下方，点击「连接并测试」。'))],
    zoho: [li(T('在 Zoho 邮箱「设置 → 邮件帐户 → IMAP 访问」里开启 IMAP。')),
      li(T('开了两步验证的话，到 '), mailLink('https://accounts.zoho.com/home#security/app_password', 'accounts.zoho.com'), T(' 生成应用专用密码；否则用登录密码。')),
      li(T('欧洲、印度等地区的数据中心请改选「其他邮箱」，服务器填 imap.zoho.eu / smtp.zoho.eu 等。'))],
    custom: [li(T('填写邮箱服务商提供的 IMAP（收信）和 SMTP（发信）服务器、端口和加密方式。常见组合：IMAP 993 + SSL/TLS，SMTP 465 + SSL/TLS 或 587 + STARTTLS。')),
      li(T('用户名一般就是邮箱地址；很多邮箱要求用「应用专用密码」或「授权码」，而不是登录密码。'))],
  };
  return h('ol', { class: 'steps-help' }, ...(S[key] || S.custom));
}

function emailCard(gm, permRow) {
  const accs = gm.accounts || [], presets = gm.providers || [];
  const byKey = Object.fromEntries(presets.map(p => [p.key, p]));
  const prov = h('select', { 'aria-label': T('邮箱服务商 Provider') }, presets.map(p => h('option', { value: p.key }, mailLabel(p))));
  const email = h('input', { type: 'email', value: '', placeholder: 'you@example.com', autocomplete: 'off' });
  const pw = h('input', { type: 'password', placeholder: '••••••••••••••••', autocomplete: 'new-password' });
  const dname = h('input', { type: 'text', value: '', placeholder: T('发件人显示名 (可选) e.g. Alex Chen') });
  const cid = h('input', { type: 'text', value: '', placeholder: '00000000-0000-0000-0000-000000000000', autocomplete: 'off', spellcheck: 'false' });
  const sec = v => { const s = h('select', null, h('option', { value: 'ssl' }, 'SSL/TLS'), h('option', { value: 'starttls' }, 'STARTTLS'), h('option', { value: 'none' }, T('不加密（仅限本机地址）'))); s.value = v; return s; };
  const ih = h('input', { type: 'text', placeholder: 'imap.example.com' }), ip = h('input', { type: 'number', value: '993', min: 1, max: 65535 }), is = sec('ssl');
  const sh = h('input', { type: 'text', placeholder: 'smtp.example.com' }), sp = h('input', { type: 'number', value: '465', min: 1, max: 65535 }), ss = sec('ssl');
  const user = h('input', { type: 'text', placeholder: T('留空 = 邮箱地址') });
  const steps = h('div'), pwLabel = h('span'), msBox = h('div', { class: 'stack' });
  const fPw = h('label', { class: 'field' }, pwLabel, pw), fCid = h('label', { class: 'field' }, h('span', null, T('应用程序(客户端) ID Application (client) ID')), cid);
  const fCustom = h('div', { class: 'stack' },
    h('div', { class: 'row' }, h('label', { class: 'field', style: 'flex:3' }, h('span', null, T('IMAP 服务器（收信）')), ih), h('label', { class: 'field', style: 'flex:1' }, h('span', null, T('端口')), ip), h('label', { class: 'field', style: 'flex:1.4' }, h('span', null, T('加密')), is)),
    h('div', { class: 'row' }, h('label', { class: 'field', style: 'flex:3' }, h('span', null, T('SMTP 服务器（发信）')), sh), h('label', { class: 'field', style: 'flex:1' }, h('span', null, T('端口')), sp), h('label', { class: 'field', style: 'flex:1.4' }, h('span', null, T('加密')), ss)),
    h('label', { class: 'field' }, h('span', null, T('用户名 Username')), user));
  ss.onchange = () => { if (ss.value === 'starttls' && sp.value === '465') sp.value = '587'; if (ss.value === 'ssl' && sp.value === '587') sp.value = '465'; };
  const btn = h('button', { class: 'btn primary' });
  const show = () => {
    const k = prov.value, oauth = (byKey[k] || {}).auth === 'oauth';
    steps.replaceChildren(mailSteps(k));
    pwLabel.textContent = k === 'qq' || k === 'netease' ? T('授权码 Authorization code') : k === 'custom' ? T('密码 Password') : T('应用专用密码 App Password');
    fPw.style.display = oauth ? 'none' : ''; fCid.style.display = oauth ? '' : 'none'; fCustom.style.display = k === 'custom' ? '' : 'none';
    btn.textContent = oauth ? T('用微软账号登录 Sign in with Microsoft') : T('连接并测试 Connect & test');
    email.placeholder = { gmail: 'you@gmail.com', outlook: 'you@outlook.com', yahoo: 'you@yahoo.com', icloud: 'you@icloud.com', qq: '12345678@qq.com', netease: 'you@163.com', zoho: 'you@zohomail.com', aol: 'you@aol.com' }[k] || 'you@example.com';
    msBox.replaceChildren();
  };
  prov.onchange = show;
  email.addEventListener('change', () => {  // pick the provider from the address
    const dom = (email.value.split('@')[1] || '').toLowerCase().trim();
    const p = presets.find(x => (x.domains || []).includes(dom));
    if (p && p.key !== prov.value) { prov.value = p.key; show(); }
  });
  const body = () => ({ provider: prov.value, email: email.value.trim(), app_password: pw.value, display_name: dname.value,
    imap_host: ih.value.trim(), imap_port: +ip.value, imap_security: is.value, smtp_host: sh.value.trim(), smtp_port: +sp.value, smtp_security: ss.value, username: user.value.trim() });
  const msPoll = async (flow, interval) => {
    for (;;) {
      await new Promise(r => setTimeout(r, Math.max(3, interval) * 1000));
      if (!document.body.contains(msBox)) return;  // left the page
      const r = await sapi('connections/gmail/oauth/' + flow);
      if (r.status === 'pending') continue;
      if (r.status === 'done') { toast(Tf("{0} 已连接 ✓ 收件箱未读 {1} 封", (email.value), (r.test.unread_inbox ?? '?'))); route(); return; }
      msBox.replaceChildren(h('div', { class: 'small', style: 'color:var(--danger)' }, r.error || r.status)); return;
    }
  };
  btn.onclick = safe(async e => {
    const label = btn.textContent; btn.disabled = true; btn.textContent = T('连接中…');
    try {
      if ((byKey[prov.value] || {}).auth === 'oauth') {
        const r = await sapi('connections/gmail/oauth/start', { method: 'POST', body: { email: email.value.trim(), client_id: cid.value.trim(), display_name: dname.value } });
        msBox.replaceChildren(h('div', { class: 'card stack', style: 'background:var(--bg2,transparent)' },
          h('div', null, T('1. 打开 '), mailLink(r.verification_uri, r.verification_uri.replace(/^https:\/\//, '')), T('，输入下面的登录码：')),
          h('div', { style: 'font-size:28px;font-weight:700;letter-spacing:4px;user-select:all' }, r.user_code),
          h('div', null, T('2. 用这个 Outlook 邮箱登录并同意授权。完成后这里会自动连接（等待中…）')),
          h('div', { class: 'small muted' }, Tf("登录码 {0} 分钟内有效", (Math.round(r.expires_in / 60))))));
        msPoll(r.flow, r.interval);
      } else {
        const res = await sapi('connections/gmail/credential', { method: 'POST', body: body() });
        toast(Tf("{0} 已连接 ✓ 收件箱未读 {1} 封", (email.value), (res.test.unread_inbox ?? '?'))); route();
      }
    } finally { btn.disabled = false; btn.textContent = label; }
  });
  show();
  const gmStatus = h('span', { class: 'chip ' + (accs.length ? 'ok' : '') }, accs.length ? Tf("已连接 {0} 个邮箱", (accs.length)) : T('未连接 Not connected'));
  const accRows = accs.map(a => h('div', { class: 'perm' },
    h('div', { style: 'min-width:0' }, h('b', null, a.email), a.id === gm.default ? h('span', { class: 'chip ok', style: 'margin-left:6px' }, T('默认 Default')) : null,
      h('div', { class: 'small muted' }, [mailLabel(byKey[a.provider] || { key: a.provider, label: a.provider_label || a.provider }), a.display_name].filter(Boolean).join(' · ')),
      a.ready ? null : h('div', { class: 'small', style: 'color:var(--danger)' }, T('缺少密码，请重新添加 (password missing)'))),
    h('div', { class: 'row', style: 'flex-wrap:nowrap' },
      h('button', { class: 'btn small', onclick: safe(async () => { const t = await sapi('connections/gmail/test', { method: 'POST', body: { account: a.id } }); toast(t.ok ? Tf("{0} 正常 ✓ 未读 {1}", (a.email), (t.test.unread_inbox)) : t.error, !t.ok); }) }, T('测试')),
      a.id !== gm.default ? h('button', { class: 'btn small', onclick: safe(async () => { await sapi('connections/gmail/default', { method: 'POST', body: { account: a.id } }); toast(T('已设为默认发件邮箱')); route(); }) }, T('设为默认')) : null,
      h('button', { class: 'btn danger small', onclick: safe(async () => { if (!confirmInline(Tf("断开 {0}？", (a.email)))) return; await sapi('connections/gmail/accounts/' + a.id, { method: 'DELETE' }); route(); }) }, T('断开')))));
  return h('div', { class: 'card stack' },
    h('div', { class: 'row' }, h('h3', { style: 'flex:1' }, T('📧 邮箱 Email')), gmStatus),
    h('p', { class: 'sub' }, T('支持 Gmail、Outlook / Hotmail、Yahoo、iCloud、QQ 邮箱、网易 163 / 126、Zoho、AOL 和任何 IMAP 邮箱，可以同时连接多个：搜索时一起查，发信时默认用「默认邮箱」，回复总是用原邮件所在的邮箱。密码 / 授权码加密保存在 Sentinel 保险箱 (Vault) 里，Agent 和模型永远看不到。')),
    accs.length ? h('div', null, ...accRows) : null,
    h('details', { open: !accs.length },
      h('summary', null, h('b', null, accs.length ? T('＋ 添加另一个邮箱 Add another mailbox') : T('连接邮箱 Connect a mailbox'))),
      h('div', { class: 'stack', style: 'margin-top:10px' },
        h('label', { class: 'field' }, h('span', null, T('邮箱服务商 Provider')), prov),
        steps,
        h('label', { class: 'field' }, h('span', null, T('邮箱 Email')), email),
        fPw, fCid, fCustom,
        h('label', { class: 'field' }, h('span', null, T('显示名 Display name')), dname),
        h('div', { class: 'row' }, btn), msBox)),
    h('div', null, h('b', null, T('权限 Permissions（读写分离）')),
      permRow(gm, 'read', T('读取与搜索'), 'read / search', 'low'),
      permRow(gm, 'organize', T('整理（归档、标签、已读）'), 'organize', 'medium'),
      permRow(gm, 'draft', T('创建草稿'), 'draft', 'medium'),
      permRow(gm, 'send', T('发送 / 回复 / 转发（每次需审批）'), 'send — approval', 'high')));
}

function calendarCard(c, permRow) {
  c = c || { name: 'calendar', config: {}, permissions: {}, enabled: false, has_credential: false };
  const connected = c.has_credential && c.enabled;
  const mode = c.mode || '';
  const redirect = location.origin + '/sentinel/api/connections/calendar/callback';
  const cid = h('input', { type: 'text', placeholder: '1234567890-abc….apps.googleusercontent.com', autocomplete: 'off' });
  const csec = h('input', { type: 'password', placeholder: mode === 'google_own' ? T('已保存 saved（同一个客户端可留空）') : 'GOCSPX-…', autocomplete: 'new-password' });
  const icalUrl = h('input', { type: 'password', placeholder: 'https://calendar.google.com/calendar/ical/…/private-…/basic.ics', autocomplete: 'off' });
  const copyBtn = h('button', { class: 'btn small', onclick: safe(async () => { await navigator.clipboard.writeText(redirect); toast(T('已复制 Copied')); }) }, T('复制 Copy'));
  const relay = c.relay_url || 'https://drlucaslu.github.io/omuse-oauth/';
  const copyRelay = h('button', { class: 'btn small', onclick: safe(async () => { await navigator.clipboard.writeText(relay); toast(T('已复制 Copied')); }) }, T('复制 Copy'));
  const modeLabel = { google: T('Google 登录'), google_own: T('自己的 Google Cloud 客户端'), ical: T('iCal 只读 read-only') }[mode] || '';
  const googleBtn = h('button', { class: 'btn primary', onclick: safe(async e => {
    e.target.disabled = true;
    try { const r = await sapi('connections/calendar/google/start', { method: 'POST', body: { origin: location.origin } }); location.href = r.auth_url; }
    finally { e.target.disabled = false; }
  }) }, connected && mode === 'google' ? T('重新用 Google 登录 Sign in again') : T('用 Google 登录 Sign in with Google'));
  const icalBtn = h('button', { class: c.managed_available ? 'btn' : 'btn primary', onclick: safe(async e => {
    e.target.disabled = true;
    try {
      const r = await sapi('connections/calendar/ical', { method: 'POST', body: { url: icalUrl.value.trim(), time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || '' } });
      toast(Tf("已连接 {0}（{1} 个日程）", (r.name || 'iCal'), (r.events)));
      route();
    } finally { e.target.disabled = false; }
  }) }, T('连接 iCal Connect'));
  return h('div', { class: 'card stack' },
    h('div', { class: 'row' }, h('h3', { style: 'flex:1' }, T('📅 Google 日历 Google Calendar')),
      h('span', { class: 'chip ' + (connected ? 'ok' : '') }, connected ? Tf("已连接 {0}", (c.config.email || '')) : T('未连接 Not connected'))),
    h('p', { class: 'sub' }, T('查看日程、找空闲时间、帮你建日程和改期（有参会人、修改或删除时每次需审批）。授权信息加密保存在本机 Sentinel 保险箱里，Agent 和模型看不到。')),
    connected ? h('div', { class: 'small muted' }, Tf("方式 {0} · 时区 {1}", modeLabel, (c.config.time_zone || '—'))) : null,
    c.managed_available ? h('div', { class: 'stack' },
      h('div', null, googleBtn),
      h('div', { class: 'small muted' }, T('一键授权：在弹出的 Google 页面登录并点「允许」即可，可读写日程。'))) : null,
    h('details', { open: !c.has_credential && !c.managed_available },
      h('summary', null, h('b', null, T('最快：粘贴日历的 iCal 私密地址（只读，30 秒）'))),
      h('div', { class: 'stack', style: 'margin-top:10px' },
        h('ol', { class: 'steps-help' },
          h('li', null, T('电脑上打开 '), h('a', { href: 'https://calendar.google.com/calendar/r/settings', target: '_blank', rel: 'noopener' }, T('Google 日历设置')), T('，左侧「我的日历的设置」里点你的日历')),
          h('li', null, T('往下找到「集成日历 Integrate calendar」，复制「iCal 格式的私密地址 Secret address in iCal format」')),
          h('li', null, T('粘贴到下面点「连接」。只能查看日程和空闲时间，不能新建或修改；iCloud、Outlook 的日历发布链接也可以用'))),
        h('label', { class: 'field' }, h('span', null, T('iCal 地址 iCal address')), icalUrl),
        h('div', null, icalBtn))),
    h('details', { open: mode === 'google_own' && !connected },
      h('summary', null, h('b', null, T('高级：用自己的 Google Cloud 客户端'))),
      h('div', { class: 'stack', style: 'margin-top:10px' },
        c.managed_source === 'box' ? h('div', { class: 'row small muted' }, h('span', { style: 'flex:1' }, T('本机已保存一键登录用的 Google 客户端，上面的「用 Google 登录」会用它。')),
          h('button', { class: 'btn small', onclick: safe(async () => { if (!confirmInline(T('移除本机保存的 Google 客户端？已连接的日历会失效。'))) return; await sapi('connections/calendar/google/client', { method: 'DELETE' }); route(); }) }, T('移除 Remove'))) : null,
        h('ol', { class: 'steps-help' },
          h('li', null, T('打开 '), h('a', { href: 'https://console.cloud.google.com/projectcreate', target: '_blank', rel: 'noopener' }, 'Google Cloud Console'), T('，新建一个项目（名字随意，如 OMuse）')),
          h('li', null, T('在「API 和服务 → 库」里搜索并启用 '), h('a', { href: 'https://console.cloud.google.com/apis/library/calendar-json.googleapis.com', target: '_blank', rel: 'noopener' }, 'Google Calendar API')),
          h('li', null, T('「OAuth 同意屏幕 OAuth consent screen」：用户类型选「外部 External」，把你自己的 Gmail 加为测试用户；建议最后点「发布应用 Publish app」，否则授权 7 天就会过期')),
          h('li', null, T('「凭据 Credentials → 创建凭据 → OAuth 客户端 ID」：应用类型选「Web 应用 Web application」，在「已获授权的重定向 URI」里填下面这个中转页地址（推荐，之后一键重连）：'),
            h('div', { class: 'row', style: 'flex-wrap:nowrap;margin-top:4px' }, h('code', { class: 'mono small', style: 'word-break:break-all' }, relay), copyRelay)),
          h('li', null, T('把生成的「客户端 ID」和「客户端密钥」粘贴到下面，点「保存并用 Google 登录」'))),
        h('label', { class: 'field' }, h('span', null, T('客户端 ID Client ID')), cid),
        h('label', { class: 'field' }, h('span', null, T('客户端密钥 Client secret')), csec),
        h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: safe(async e => {
          e.target.disabled = true;
          try {
            await sapi('connections/calendar/google/client', { method: 'POST', body: { client_id: cid.value.trim(), client_secret: csec.value.trim() } });
            const r = await sapi('connections/calendar/google/start', { method: 'POST', body: { origin: location.origin } }); location.href = r.auth_url;
          } finally { e.target.disabled = false; }
        }) }, T('保存并用 Google 登录 Save & sign in'))),
        h('details', null, h('summary', { class: 'small muted' }, T('不用中转页：用本机回调地址')),
          h('div', { class: 'stack', style: 'margin-top:6px' },
            h('div', { class: 'small muted' }, T('在 Google Cloud 的重定向 URI 里改填本机地址：')),
            h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('code', { class: 'mono small', style: 'word-break:break-all' }, redirect), copyBtn),
            h('div', null, h('button', { class: 'btn small', onclick: safe(async e => {
              e.target.disabled = true;
              try { const r = await sapi('connections/calendar/start', { method: 'POST', body: { client_id: cid.value.trim(), client_secret: csec.value.trim(), origin: location.origin } }); location.href = r.auth_url; }
              finally { e.target.disabled = false; }
            }) }, T('用本机地址连接 Connect'))))))),
    h('div', null, h('b', null, T('权限 Permissions')),
      permRow(c, 'read', T('查看日程与空闲时间'), 'read', 'low'),
      mode === 'ical' ? h('div', { class: 'small muted' }, T('iCal 只读连接不能写入日程；要让 OMuse 帮你建日程，请用 Google 登录。'))
        : permRow(c, 'write', T('新建 / 修改 / 删除日程（邀请他人、修改、删除需审批）'), 'write', 'medium')),
    c.has_credential ? h('div', { class: 'row' },
      h('button', { class: 'btn small', onclick: safe(async () => { const t = await sapi('connections/calendar/test', { method: 'POST', body: {} }); toast(t.ok ? Tf("正常 ✓ 未来 7 天有 {0} 个日程", (t.upcoming)) : t.error, !t.ok); }) }, T('测试')),
      h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: c.enabled, onchange: safe(async e => { await sapi('connections/calendar', { method: 'PUT', body: { enabled: e.target.checked } }); }) }), T('启用')),
      h('button', { class: 'btn danger small', onclick: safe(async () => { if (!confirmInline(T('断开 Google 日历？授权会被删除。'))) return; await sapi('connections/calendar/credential', { method: 'DELETE' }); route(); }) }, T('断开 Disconnect'))) : null);
}

// --- MCP connectors (Model Context Protocol)
const MCP_KIND = { read: [T('只读 read'), 'risk-low'], write: [T('写入 write'), 'risk-medium'], destructive: [T('可能删除/覆盖 destructive'), 'risk-high'] };
const MCP_DC = [['CONFIDENTIAL', T('机密 Confidential（私人文档、工作数据）')], ['PERSONAL', T('个人 Personal')], ['PUBLIC', T('公开 Public（天气、公开网页等）')]];
async function mcpCard() {
  const r = await sapi('mcp/servers');
  const list = r.servers || [];
  const pending = list.reduce((n, s) => n + s.tools.filter(t => t.status !== 'ok').length, 0);
  const authSel = () => h('select', null, h('option', { value: 'none' }, T('无 None')), h('option', { value: 'bearer' }, T('Bearer 令牌 Token')),
    h('option', { value: 'header' }, T('自定义请求头 Custom header')));
  // add form
  const name = h('input', { type: 'text', placeholder: T('例如 GitHub、公司知识库') });
  const url = h('input', { type: 'url', placeholder: 'https://…/mcp', autocomplete: 'off' });
  const auth = authSel();
  auth.append(h('option', { value: 'oauth' }, T('OAuth 登录 Sign in')));
  const hname = h('input', { type: 'text', placeholder: 'X-API-Key' });
  const token = h('input', { type: 'password', placeholder: T('令牌 token（加密保存，不会显示）'), autocomplete: 'new-password' });
  const hnameField = h('label', { class: 'field', style: 'display:none' }, h('span', null, T('请求头名称 Header name')), hname);
  const tokenField = h('label', { class: 'field', style: 'display:none' }, h('span', null, T('令牌 Token')), token);
  auth.onchange = () => { hnameField.style.display = auth.value === 'header' ? '' : 'none'; tokenField.style.display = ['none', 'oauth'].includes(auth.value) ? 'none' : ''; };
  const dc = h('select', null, MCP_DC.map(([v, l]) => h('option', { value: v }, l)));
  const addBtn = h('button', { class: 'btn primary', onclick: safe(async e => {
    e.target.disabled = true; e.target.textContent = T('连接中…');
    try {
      if (auth.value === 'oauth') { await oauthPopup('mcp/oauth/start', { name: name.value, url: url.value, data_class: dc.value }); return; }
      const s = await sapi('mcp/servers', { method: 'POST', body: { name: name.value, url: url.value, auth_type: auth.value, token: token.value, header_name: hname.value, data_class: dc.value } });
      const off = s.tools.filter(t => t.flags && t.flags.length).length;
      toast(Tf("「{0}」已连接 ✓ 读到 {1} 个工具", (s.name), (s.tools.length)) + (off ? Tf("，其中 {0} 个疑似有注入内容，已关闭", (off)) : ''));
      route();
    } finally { e.target.disabled = false; e.target.textContent = T('连接并读取工具 Connect'); }
  }) }, T('连接并读取工具 Connect'));
  const addForm = h('details', { open: !list.length },
    h('summary', null, h('b', null, list.length ? T('＋ 添加 MCP 服务器 Add server') : T('添加第一个 MCP 服务器 Add your first server'))),
    h('div', { class: 'stack', style: 'margin-top:10px' },
      h('ol', { class: 'steps-help' },
        h('li', null, T('准备一个支持 HTTP 的 MCP 服务器地址（Streamable HTTP 或旧版 SSE 都可以）。公网地址必须是 https://；内网服务可以用 http://。')),
        h('li', null, T('如果服务需要令牌（API Key / Personal Access Token），在「认证」里选择方式并粘贴。令牌加密存进 Sentinel 保险箱 (Vault)，模型看不到。')),
        h('li', null, T('连接后会列出它提供的工具：只读工具默认「自动」，会改数据的工具默认「每次审批」，你可以逐个调整。')),
        h('li', null, T('例：GitHub 官方 MCP https://api.githubcopilot.com/mcp/ ，认证选 Bearer，填 GitHub 个人访问令牌 (Personal Access Token)。'))),
      h('div', { class: 'row' }, h('label', { class: 'field', style: 'flex:1;min-width:160px' }, h('span', null, T('名称 Name')), name),
        h('label', { class: 'field', style: 'flex:2;min-width:220px' }, h('span', null, T('服务器地址 Server URL')), url)),
      h('div', { class: 'row' }, h('label', { class: 'field', style: 'flex:1;min-width:160px' }, h('span', null, T('认证 Auth')), auth),
        h('label', { class: 'field', style: 'flex:2;min-width:220px' }, h('span', null, T('数据敏感度 Data class')), dc)),
      hnameField, tokenField, h('div', null, addBtn)));

  const serverBox = s => {
    const setMode = (t, mode, accept) => safe(async () => {
      await sapi(`mcp/servers/${s.id}/tools/${encodeURIComponent(t.name)}`, { method: 'PUT', body: accept ? { accept: true } : { mode } });
      toast(accept ? Tf("已接受「{0}」的新定义", (t.name)) : T('已保存 Saved')); route();
    });
    const toolRow = t => {
      const [kl, kc] = MCP_KIND[t.kind] || [t.kind, ''];
      const sel = h('select', { class: 'small', onchange: e => setMode(t, e.target.value)() },
        [['auto', T('自动 Auto')], ['ask', T('每次审批 Ask')], ['off', T('关闭 Off')]].map(([v, l]) => h('option', { value: v, selected: t.mode === v }, l)));
      const badges = [];
      if (t.status === 'new') badges.push(h('span', { class: 'pill risk-medium' }, T('新工具 New — 选择模式后启用')));
      if (t.status === 'changed') badges.push(h('span', { class: 'pill risk-high' }, T('定义已变化 Changed — 检查后接受')));
      if (t.flags && t.flags.length) badges.push(h('span', { class: 'pill risk-high', title: t.flags.join(', ') }, T('⚠️ 描述疑似含注入指令 injection')));
      return h('div', { class: 'mcp-tool' },
        h('div', { style: 'min-width:0;flex:1' },
          h('div', null, h('b', { class: 'mono' }, t.name), t.title ? h('span', { class: 'muted small' }, ' · ' + t.title) : null, ' ',
            h('span', { class: 'pill ' + kc, title: t.guessed ? T('服务器没有标注，按名称推测 (guessed from the name)') : '' }, kl + (t.guessed ? T('（推测）') : '')), ' ', badges),
          t.description ? h('div', { class: 'small muted mcp-desc' }, t.description) : null,
          t.status === 'changed' && t.previous_description !== undefined ? h('div', { class: 'small', style: 'margin-top:4px' },
            h('div', { class: 'muted' }, T('原来 Before：'), t.previous_description || T('（空）')), h('div', null, T('现在 Now：'), t.description || T('（空）'))) : null),
        h('div', { class: 'row', style: 'flex-wrap:nowrap' }, sel,
          t.status === 'changed' ? h('button', { class: 'btn small', onclick: setMode(t, null, true) }, T('接受 Accept')) : null));
    };
    const tok = h('input', { type: 'password', placeholder: s.has_credential ? T('已保存 saved — 填新令牌可替换') : T('令牌 token'), autocomplete: 'new-password' });
    const a2 = authSel(); a2.value = s.auth || 'none';
    const hn = h('input', { type: 'text', value: s.header_name || '', placeholder: 'X-API-Key' });
    const dcs = h('select', { onchange: safe(async e => { await sapi('mcp/servers/' + s.id, { method: 'PUT', body: { data_class: e.target.value } }); toast(T('已保存 Saved')); }) },
      MCP_DC.map(([v, l]) => h('option', { value: v, selected: s.data_class === v }, l)));
    const active = s.tools.filter(t => t.status === 'ok' && t.mode !== 'off').length;
    return h('details', { class: 'mcp-server', open: s.tools.some(t => t.status !== 'ok') },
      h('summary', null, h('span', { class: 'row', style: 'display:inline-flex;gap:8px;align-items:center' },
        h('b', null, '🧩 ' + s.name), h('span', { class: 'chip ' + (s.enabled && !s.last_error ? 'ok' : s.last_error ? 'bad' : '') },
          !s.enabled ? T('已停用 Disabled') : s.last_error ? T('连接异常') : Tf("{0}/{1} 个工具启用", (active), (s.tools.length))),
        h('span', { class: 'chip' }, s.transport === 'sse' ? T('SSE (旧版)') : 'Streamable HTTP'))),
      h('div', { class: 'stack', style: 'margin-top:8px' },
        h('div', { class: 'small muted mono', style: 'word-break:break-all' }, s.url, s.server_info && s.server_info.name ? `  ·  ${s.server_info.name} ${s.server_info.version || ''}` : ''),
        s.last_error ? h('div', { class: 'small', style: 'color:var(--danger)' }, '⚠️ ' + B(s.last_error)) : null,
        h('div', { class: 'row' },
          h('label', { class: 'toggle' }, h('input', { type: 'checkbox', checked: s.enabled, onchange: safe(async e => { await sapi('mcp/servers/' + s.id, { method: 'PUT', body: { enabled: e.target.checked } }); route(); }) }), T('启用')),
          h('button', { class: 'btn small', onclick: safe(async () => { const t = await sapi(`mcp/servers/${s.id}/test`, { method: 'POST' }); toast(Tf("连接正常 ✓ {0}", (t.transport))); route(); }) }, T('测试 Test')),
          h('button', { class: 'btn small', onclick: safe(async () => {
            const x = await sapi(`mcp/servers/${s.id}/refresh`, { method: 'POST' });
            const d = x.diff || {};
            toast(Tf("已刷新：新增 {0}，变化 {1}，移除 {2}", (d.added.length), (d.changed.length), (d.removed.length)) + (d.added.length + d.changed.length ? T(' — 请检查标黄/标红的工具') : ''));
            route();
          }) }, T('刷新工具 Refresh')),
          h('button', { class: 'btn danger small', onclick: safe(async () => { if (!confirmInline(Tf("删除 MCP 服务器「{0}」？令牌也会一起删除。", (s.name)))) return; await sapi('mcp/servers/' + s.id, { method: 'DELETE' }); route(); }) }, T('删除 Remove'))),
        h('label', { class: 'field' }, h('span', null, T('数据敏感度 Data class（决定外泄检查的严格程度）')), dcs),
        h('details', null, h('summary', { class: 'small' }, T('更换令牌 / 认证方式 Change token')),
          h('div', { class: 'row', style: 'margin-top:8px' }, a2, hn, tok,
            h('button', { class: 'btn small', onclick: safe(async () => { await sapi('mcp/servers/' + s.id, { method: 'PUT', body: { auth_type: a2.value, token: tok.value, header_name: hn.value } }); toast(T('已更新认证 Updated')); route(); }) }, T('保存')))),
        h('div', null, h('b', null, Tf("工具 Tools（{0}）", (s.tools.length))), h('div', { class: 'small muted' },
          T('自动 = 直接执行；每次审批 = 每次弹出审批（手机 Telegram 也能点 ✅）；关闭 = Agent 看不到。工具定义被服务器悄悄修改时会自动停用，等你确认。')),
          s.tools.length ? s.tools.map(toolRow) : h('div', { class: 'muted small' }, T('这个服务器没有提供工具。')))));
  };

  return h('div', { class: 'card stack' },
    h('div', { class: 'row' }, h('h3', { style: 'flex:1' }, T('🧩 MCP 连接器 MCP connectors')),
      pending ? h('span', { class: 'chip bad' }, Tf("{0} 个工具待检查", (pending))) : null,
      h('span', { class: 'chip ' + (list.length ? 'ok' : '') }, list.length ? Tf("{0} 个服务器", (list.length)) : T('未添加'))),
    h('p', { class: 'sub' }, T('MCP（Model Context Protocol，模型上下文协议）是让 AI 连接外部工具的通用标准。添加一个 MCP 服务器后，它提供的工具（查文档、建任务、查代码…）就能被 OMuse 使用。所有调用都经过 Sentinel：按你的设置自动执行或弹出审批，并写入活动审计。返回的内容一律当作不可信数据处理。')),
    list.map(serverBox), addForm);
}

// ================================================================== MEMORY
const MEM_CATS = ['preference', 'person', 'company', 'project', 'habit', 'other'];
const CAT_LABEL = { preference: T('偏好'), person: T('人物'), company: T('公司'), project: T('项目'), habit: T('习惯'), other: T('其他'), general: T('其他') };

async function viewMemory(root) {
  const [r, v] = await Promise.all([api('memory'), sapi('vault').catch(() => ({ items: [], kinds: {}, field_labels: {} }))]);
  root.append(
    h('div', { class: 'grid2' }, memProfileCard(r), h('div', { class: 'stack' }, memLearnedCard(r), memPendingCard(r), memTidyCard(r))),
    h('div', { style: 'margin-top:16px' }, memFactsCard(r)),
    h('div', { class: 'grid2', style: 'margin-top:16px' }, memTryCard(r), memEntitiesCard(r)),
    h('div', { class: 'grid2', style: 'margin-top:16px' }, memRecentCard(r), memVaultCard(v)),
    h('div', { style: 'margin-top:16px' }, memEpisodesCard(r)));
}

const domLabel = (r, k) => { const d = (r.domains || []).find(x => x.key === k); return d ? (LANG === 'en' ? d.en : ZH(d.zh)) : (k || ''); };

function memDomainSelect(r, value, onchange) {
  const sel = h('select', { 'aria-label': T('域 Domain'), style: 'width:auto;flex:0 0 auto;padding:2px 6px;font-size:12px' },
    (r.domains || []).map(d => h('option', { value: d.key }, LANG === 'en' ? d.en : ZH(d.zh))));
  sel.value = value || 'work';
  if (onchange) sel.onchange = () => onchange(sel.value);
  return sel;
}

function memLearnedCard(r) {
  const list = (r.facts || []).filter(f => f.status === 'pending');
  const go = (f, body) => safe(async () => { await api('memory/' + f.id, { method: body ? 'PUT' : 'DELETE', body }); route(); });
  return h('div', { class: 'card stack' },
    h('div', { class: 'row' }, h('h3', { style: 'flex:1' }, T('🌱 OMuse 学到的，待你确认 Learned')), list.length ? h('span', { class: 'chip bad' }, String(list.length)) : h('span', { class: 'chip ok' }, T('无 None'))),
    h('p', { class: 'sub' }, T('任务中 OMuse 自己发现的习惯（比如某个网站电话要填 8 位）。确认之前也会用，但会标明「未确认」。')),
    list.length ? list.map(f => h('div', { class: 'row', style: 'border-bottom:1px solid var(--line-2);padding-bottom:6px;align-items:flex-start' },
      h('div', { style: 'flex:1;min-width:0' }, f.fact, h('div', { class: 'small muted' }, domLabel(r, f.domain))),
      h('button', { class: 'btn approve small', onclick: go(f, { status: 'active' }) }, T('✓ 对 Confirm')),
      h('button', { class: 'btn danger small', onclick: go(f, null) }, T('✕ 不对 Forget')))) : h('div', { class: 'muted small' }, T('暂无')));
}

function memTryCard(r) {
  const inp = h('input', { type: 'text', placeholder: T('输入一个请求，例如：帮我在迪卡侬买双跑鞋') });
  const out = h('div', { class: 'stack' });
  const run = safe(async () => {
    if (!inp.value.trim()) return;
    const x = await api('context/preview?q=' + encodeURIComponent(inp.value));
    out.replaceChildren(...(x.facts.length ? x.facts.map(f => h('div', { class: 'small', style: 'border-bottom:1px solid var(--line-2);padding:4px 0' },
      h('span', { class: 'chip', style: 'margin-right:6px' }, domLabel(r, f.domain)), f.fact,
      f.status === 'pending' ? h('span', { class: 'muted' }, T('（未确认）')) : null,
      h('div', { class: 'faint' }, f.why || ''))) : [h('div', { class: 'muted small' }, T('记忆里没有和这个请求相关的内容。'))]));
  });
  inp.onkeydown = (e) => { if (e.key === 'Enter') run(); };
  return h('div', { class: 'card stack' }, h('h3', null, T('🔎 试一试：这个请求会用到哪些记忆 Try it')),
    h('p', { class: 'sub' }, T('每个任务开始时，OMuse 只带上和这个请求相关的几条记忆（尺码、舱位、口味、网站习惯…），不用你再说一遍。')),
    h('div', { class: 'row' }, inp, h('button', { class: 'btn primary', onclick: run }, T('看看 Preview'))), out);
}

function memEntitiesCard(r) {
  const ents = r.entities || [];
  const edit = (e) => safe(async () => {
    const al = prompt(Tf("「{0}」的别名，用逗号分隔（例如：迪卡侬, Decathlon）", e.name), ((e.attrs || {}).aliases || []).join(', '));
    if (al === null) return;
    let rel = e.relation || '';
    if (e.type === 'person') { const x = prompt(Tf("「{0}」和你的关系（例如：同事、太太、旅伴；可留空）", e.name), rel); if (x !== null) rel = x; }
    await api('entities/' + e.id, { method: 'PUT', body: { aliases: al, relation: rel } }); route();
  });
  const groups = ['person', 'place', 'account', 'site'].map(k => [k, ents.filter(e => e.type === k)]).filter(([, l]) => l.length);
  return h('div', { class: 'card stack' }, h('h3', null, T('👥 人物、地点、账户、网站 Entities')),
    h('p', { class: 'sub' }, T('记忆里提到的人和地方。加上别名或关系后（如「太太」「迪卡侬」），你换个说法 OMuse 也能对上。')),
    groups.length ? groups.map(([k, l]) => h('div', { class: 'stack', style: 'gap:4px' }, h('b', { class: 'small' }, domLabel(r, k)),
      h('div', { class: 'row', style: 'flex-wrap:wrap;gap:6px' }, l.map(e => h('button', { class: 'chip', style: 'cursor:pointer', onclick: edit(e), title: T('点击编辑别名 / 关系') },
        e.name + (e.relation ? ` · ${e.relation}` : '') + (((e.attrs || {}).aliases || []).length ? ` (${e.attrs.aliases.join(', ')})` : '')))))) :
      h('div', { class: 'muted small' }, T('暂无')));
}

function memProfileCard(r) {
  const prof = r.profile || {};
  const inputs = {};
  const rows = (r.profile_fields || []).map(f => {
    const i = h('input', { type: 'text', value: prof[f.key] || '', autocomplete: 'off' }); inputs[f.key] = i;
    return h('label', { class: 'field' }, h('span', null, LANG === 'en' ? f.en : ZH(f.zh)), i);
  });
  for (const k of Object.keys(prof).filter(k => k.startsWith('custom:'))) {
    const i = h('input', { type: 'text', value: prof[k], autocomplete: 'off' }); inputs[k] = i;
    rows.push(h('label', { class: 'field' }, h('span', null, k.slice(7)), i));
  }
  const cLabel = h('input', { type: 'text', placeholder: T('自定义字段名，如：常用航空公司'), style: 'flex:1' });
  const cVal = h('input', { type: 'text', placeholder: T('内容'), style: 'flex:1' });
  const save = safe(async () => {
    let n = 0;
    for (const [k, el] of Object.entries(inputs)) {
      if ((el.value || '').trim() !== (prof[k] || '')) { await api('profile', { method: 'PUT', body: { key: k, value: el.value } }); n++; }
    }
    if (cLabel.value.trim() && cVal.value.trim()) { await api('profile', { method: 'PUT', body: { key: 'custom:' + cLabel.value.trim(), value: cVal.value } }); n++; }
    toast(n ? Tf("已保存 {0} 项", n) : T('没有改动 No changes')); route();
  });
  return h('div', { class: 'card stack' }, h('h3', null, T('🪪 档案 Profile')),
    h('p', { class: 'sub' }, T('填表、写邮件时才会用到的固定信息。Agent 只在需要时读取；它发现的新信息会先放到「待确认」，你同意后才会修改。证件号、会员号、卡号请放进下面的保险箱。')),
    h('div', { class: 'grid2', style: 'gap:4px 12px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr))' }, rows),
    h('div', { class: 'row' }, cLabel, cVal),
    h('div', null, h('button', { class: 'btn primary', onclick: save }, T('保存档案 Save profile'))));
}

function memPendingCard(r) {
  const list = r.pending || [];
  const label = (k) => { const f = (r.profile_fields || []).find(x => x.key === k); return f ? (LANG === 'en' ? f.en : ZH(f.zh)) : k.replace(/^custom:/, ''); };
  return h('div', { class: 'card stack' },
    h('div', { class: 'row' }, h('h3', { style: 'flex:1' }, T('📝 待确认的档案修改 Pending')), list.length ? h('span', { class: 'chip bad' }, String(list.length)) : h('span', { class: 'chip ok' }, T('无 None'))),
    list.length ? list.map(p => {
      const val = h('input', { type: 'text', value: p.value });
      const go = (accept) => safe(async () => { await api('profile/pending/' + p.id, { method: 'POST', body: { accept, value: val.value } }); route(); });
      return h('div', { class: 'stack', style: 'border-bottom:1px solid var(--line-2);padding-bottom:8px' },
        h('div', null, h('b', null, label(p.key)), h('span', { class: 'muted small' }, ' · ' + (p.old ? Tf("原来：{0}", p.old) : T('原来为空')))),
        val, p.reason ? h('div', { class: 'small muted' }, p.reason) : null,
        h('div', { class: 'row' }, h('button', { class: 'btn approve small', onclick: go(true) }, T('✓ 确认修改 Accept')), h('button', { class: 'btn danger small', onclick: go(false) }, T('✕ 不改 Reject'))));
    }) : h('div', { class: 'muted small' }, T('Agent 提出的档案修改会出现在这里，由你决定是否采纳。')));
}

function memTidyCard(r) {
  const job = r.job || {};
  const detail = h('div', { class: 'stack' });
  const start = (body) => safe(async () => { await api('memory/consolidate', { method: 'POST', body }); toast(T('已开始，整理需要几分钟 Started')); route(); });
  const show = (id) => safe(async () => { const run = await api('memory/runs/' + id); detail.replaceChildren(memPlanView(run.report || {})); });
  const runs = (r.runs || []).map(x => h('div', { class: 'small', style: 'border-bottom:1px solid var(--line-2);padding-bottom:6px' },
    h('div', { class: 'row' }, h('b', null, { dry_run: T('预览'), daily: T('每日整理'), manual: T('手动整理'), applied: T('按预览执行') }[x.kind] || x.kind),
      h('span', { class: 'muted' }, fmtTime(x.ts)), x.applied ? h('span', { class: 'chip ok' }, T('已执行')) : null,
      h('span', { style: 'flex:1' }),
      h('button', { class: 'btn small', onclick: show(x.id) }, T('详情 Details')),
      x.kind === 'dry_run' && !x.applied ? h('button', { class: 'btn primary small', disabled: !!job.running, onclick: start({ from_run: x.id }) }, T('按此执行 Apply')) : null),
    (x.lines || []).map(l => h('div', { class: 'muted' }, l)),
    (x.errors || []).length ? h('div', { class: 'small', style: 'color:var(--danger)' }, Tf("模型出错，部分未整理：{0}", x.errors.join('; '))) : null));
  return h('div', { class: 'card stack' }, h('h3', null, T('🧹 记忆整理 Memory tidy')),
    h('p', { class: 'sub' }, Tf("每天 {0} 自动合并重复、清理过期、把一次性的内容降为近期，并把报告发到 Telegram。不会直接改档案，也不会直接删除长期记忆（降为近期后 30 天才过期）。", (r.settings || {}).memory_consolidate_at || '03:30')),
    r.needs_first_review ? h('div', { class: 'small', style: 'color:var(--warn, #b7791f)' }, T('第一次整理前请先预览，确认没问题再执行；之后才会每天自动整理。')) : null,
    (r.settings || {}).memory_consolidation === false ? h('div', { class: 'small muted' }, T('每日自动整理已在设置中关闭。')) : null,
    h('div', { class: 'row' },
      h('button', { class: 'btn', disabled: !!job.running, onclick: start({ dry_run: true }) }, job.running ? T('整理中… Running') : T('预览整理 Preview')),
      job.error ? h('span', { class: 'small', style: 'color:var(--danger)' }, job.error) : null),
    runs.length ? runs : h('div', { class: 'muted small' }, T('还没有整理记录。')), detail);
}

function memPlanView(rep) {
  const p = rep.plan || {}; const L = p.local || {}; const M = p.llm || {};
  const sec = (title, items, fn) => items && items.length ? h('details', { open: items.length <= 8 }, h('summary', null, `${title} (${items.length})`),
    h('ul', { class: 'small' }, items.map(x => h('li', null, fn(x))))) : null;
  return h('div', { class: 'stack', style: 'border:1px solid var(--line);border-radius:10px;padding:10px' },
    h('b', null, rep.applied || rep.done ? T('整理内容 What changed') : T('预览：将会做的修改 Preview')),
    sec(T('合并重复'), [...(L.dups || []).map(d => ({ before: [d.fact], fact: d.fact, n: d.drop.length + 1 })), ...(M.merge || [])],
      x => h('span', null, (x.before || []).map(b => h('div', { class: 'muted' }, '− ' + b)), h('div', null, '→ ' + x.fact + (x.n ? Tf("（{0} 条相同）", x.n) : '')))),
    sec(T('改写'), M.rewrite, x => h('span', null, h('div', { class: 'muted' }, '− ' + x.before), h('div', null, '→ ' + x.fact))),
    sec(T('降为近期（30 天后过期）'), M.demote, x => h('span', null, x.fact, h('span', { class: 'muted' }, ' — ' + (x.reason || '')))),
    sec(T('升为长期'), [...(L.auto_promote || []).map(id => ({ fact: id, reason: T('经常被用到') })), ...(M.promote || [])], x => h('span', null, x.fact, h('span', { class: 'muted' }, ' — ' + (x.reason || '')))),
    sec(T('删除（含证件号/卡号/密码）'), L.sensitive, x => x.preview),
    sec(T('档案修改建议（需要你确认）'), M.profile, x => `${x.field} → ${x.value}`),
    h('div', { class: 'small muted' }, Tf("过期清理：记忆 {0} 条，经历 {1} 条", (L.prune_facts || []).length, L.prune_episodes || 0)));
}

function memFactRow(f, recent, r) {
  const edit = safe(async () => {
    const t = prompt(T('修改这条记忆'), f.fact); if (t === null || !t.trim()) return;
    await api('memory/' + f.id, { method: 'PUT', body: { fact: t } }); route();
  });
  const move = safe(async () => { await api('memory/' + f.id, { method: 'PUT', body: { tier: recent ? 'long' : 'recent' } }); route(); });
  const del = safe(async () => { await api('memory/' + f.id, { method: 'DELETE' }); route(); });
  const left = recent && f.expires_at ? Math.max(0, Math.ceil((f.expires_at * 1000 - Date.now()) / 86400000)) : null;
  const dom = r ? memDomainSelect(r, f.domain, safe(async (v) => { await api('memory/' + f.id, { method: 'PUT', body: { domain: v } }); toast(T('已改 Saved')); })) : (CAT_LABEL[f.category] || f.category || '');
  return h('tr', null, h('td', null, f.fact, f.status === 'pending' ? h('span', { class: 'chip bad', style: 'margin-left:6px' }, T('待确认')) : null,
      f.history ? h('div', { class: 'small faint', title: f.history }, T('（有修改记录）')) : null),
    h('td', { class: 'small' }, dom),
    h('td', { class: 'small muted', style: 'white-space:nowrap' }, recent ? Tf("{0} 天后过期", left ?? '?') : String(f.uses || 0)),
    h('td', { class: 'row', style: 'gap:4px;flex-wrap:nowrap;white-space:nowrap' },
      h('button', { class: 'btn small', onclick: edit }, T('改')),
      h('button', { class: 'btn small', onclick: move, title: recent ? T('保留为长期记忆') : T('降为近期（30 天后过期）') }, recent ? T('保留') : T('降级')),
      h('button', { class: 'btn danger small', onclick: del }, T('忘记'))));
}

function memFactsCard(r) {
  const inp = h('input', { type: 'text', placeholder: T('例如：我穿 43 码运动鞋；订餐厅优先湘菜；James Zhan 是我的合作伙伴') });
  const dom = memDomainSelect(r, 'preference');
  const body = h('tbody');
  const counts = {}; for (const f of r.facts) counts[f.domain || 'work'] = (counts[f.domain || 'work'] || 0) + 1;
  let cur = S.memDomain || '';
  const chips = h('div', { class: 'row', style: 'flex-wrap:wrap;gap:6px' });
  const draw = () => {
    chips.replaceChildren(...[['', T('全部 All'), r.facts.length], ...(r.domains || []).map(d => [d.key, LANG === 'en' ? d.en : ZH(d.zh), counts[d.key] || 0])]
      .map(([k, label, n]) => h('button', { class: 'chip' + (k === cur ? ' ok' : ''), style: 'cursor:pointer', onclick: () => { cur = k; S.memDomain = k; draw(); } }, `${label} ${n}`)));
    body.replaceChildren(...r.facts.filter(f => !cur || (f.domain || 'work') === cur).map(f => memFactRow(f, false, r)));
  };
  draw();
  return h('div', { class: 'card stack' }, h('h3', null, Tf("🧠 长期记忆 Long-term（{0}）", r.facts.length)),
    h('p', { class: 'sub' }, T('按 7 个域整理：人物与关系、偏好、地点、账户与会员、网站习惯、默认规则、工作与其他。域可以直接改；每个任务只取相关的几条。')),
    h('div', { class: 'row' }, inp, dom, h('button', { class: 'btn primary', onclick: safe(async () => { await api('memory', { method: 'POST', body: { fact: inp.value, domain: dom.value } }); route(); }) }, T('记住 Remember'))),
    chips,
    r.facts.length ? h('div', { class: 'tablewrap' }, h('table', { class: 'data memtable' },
      h('thead', null, h('tr', null, [T('事实 Fact'), T('域'), T('用过'), ''].map(x => h('th', null, x)))), body)) : h('div', { class: 'muted small' }, T('还没有记忆。')));
}

function memRecentCard(r) {
  const list = r.recent || [];
  return h('div', { class: 'card stack' }, h('h3', null, Tf("⏳ 近期记忆 Recent（{0}）", list.length)),
    h('p', { class: 'sub' }, T('一次性的细节（订单号、这周的行程…），保留 30 天后自动清除。经常用到的会自动升为长期。')),
    list.length ? h('div', { class: 'tablewrap' }, h('table', { class: 'data memtable' },
      h('thead', null, h('tr', null, [T('事实 Fact'), T('类别'), T('剩余'), ''].map(x => h('th', null, x)))),
      h('tbody', null, list.map(f => memFactRow(f, true))))) : h('div', { class: 'muted small' }, T('暂无')));
}

function memVaultCard(v) {
  const kinds = v.kinds || {}; const FL = v.field_labels || {};
  const form = h('div', { class: 'stack', style: 'display:none;border:1px solid var(--line);border-radius:10px;padding:10px' });
  const openForm = (it) => {
    form.replaceChildren(); form.style.display = '';
    const kind = h('select', { 'aria-label': T('类型'), disabled: !!it }, Object.entries(kinds).map(([k, x]) => h('option', { value: k }, T(x.label))));
    if (it) kind.value = it.kind;
    const label = h('input', { type: 'text', value: it ? it.label : '', placeholder: T('名称，如：护照、新航会员、Visa 卡') });
    const domains = h('input', { type: 'text', value: it ? (it.domains || []).join(', ') : '', placeholder: T('只允许在这些网站使用（可选），如 singaporeair.com') });
    const vals = h('div', { class: 'grid2', style: 'gap:8px' }); const inputs = {};
    const drawFields = () => {
      vals.replaceChildren();
      for (const f of (kinds[kind.value] || {}).fields || []) {
        const i = h('input', { type: 'password', autocomplete: 'new-password', placeholder: it ? T('留空 = 不修改') : '' }); inputs[f] = i;
        vals.append(h('label', { class: 'field' }, h('span', null, T(FL[f] || f)), i));
      }
    };
    kind.onchange = drawFields; drawFields();
    const show = h('label', { class: 'toggle small' }, h('input', { type: 'checkbox', onchange: e => Object.values(inputs).forEach(i => i.type = e.target.checked ? 'text' : 'password') }), T('显示内容'));
    const saveBtn = h('button', { class: 'btn primary', onclick: safe(async () => {
      const values = {}; for (const [k, i] of Object.entries(inputs)) values[k] = i.value;
      await sapi(it ? 'vault/' + it.id : 'vault', { method: it ? 'PUT' : 'POST', body: { kind: kind.value, label: label.value, domains: domains.value, values } });
      toast(T('已存入保险箱 Saved')); route();
    }) }, T('保存 Save'));
    form.append(h('div', { class: 'row' }, kind, label), domains, vals, h('div', { class: 'row' }, show, h('span', { style: 'flex:1' }),
      h('button', { class: 'btn', onclick: () => { form.style.display = 'none'; } }, T('取消')), saveBtn));
  };
  const items = (v.items || []).map(it => h('div', { class: 'row', style: 'border-bottom:1px solid var(--line-2);padding-bottom:6px' },
    h('div', { style: 'flex:1;min-width:0' }, h('b', null, it.label), h('span', { class: 'muted small' }, ` · ${T(it.kind_label || it.kind)} · ${it.masked}`),
      h('div', { class: 'small muted' }, (it.domains || []).length ? Tf("仅限：{0}", it.domains.join(', ')) : T('任何网站（每次都要你批准）'),
        it.uses ? ' · ' + Tf("已用 {0} 次，最近 {1}", it.uses, fmtTime(it.last_used)) : '')),
    h('button', { class: 'btn small', onclick: () => openForm(it) }, T('改')),
    h('button', { class: 'btn danger small', onclick: safe(async () => { if (!confirm(Tf("从保险箱删除「{0}」？", it.label))) return; await sapi('vault/' + it.id, { method: 'DELETE' }); route(); }) }, T('删除'))));
  return h('div', { class: 'card stack' }, h('h3', null, T('🔐 保险箱 Vault')),
    h('p', { class: 'sub' }, T('证件号、会员号、信用卡加密保存在 Sentinel 里。Agent 看不到内容，只能请求「把某一项填进某个输入框」，每一次都要你批准；填完后页面文字里的号码也会被遮住。')),
    items.length ? items : h('div', { class: 'muted small' }, T('保险箱是空的。')),
    h('div', null, h('button', { class: 'btn', onclick: () => openForm(null) }, T('＋ 添加 Add'))), form);
}

function memEpisodesCard(r) {
  return h('div', { class: 'card stack' }, h('h3', null, T('经历 Episodes')), h('p', { class: 'sub' }, T('最近 30 天已完成任务的摘要 (Episodic memory)，用于回溯，到期自动清除。')),
    r.episodes.length ? h('details', null, h('summary', null, Tf("{0} 条", r.episodes.length)), r.episodes.map(e => h('div', { class: 'small', style: 'border-bottom:1px solid var(--line-2);padding:6px 0' },
      h('div', { class: 'muted' }, fmtTime(e.ts)), e.summary))) : h('div', { class: 'muted small' }, T('暂无')));
}

// ================================================================== ACTIVITY / AUDIT
async function viewActivity(root) {
  const q = S.auditTask ? `audit?task_id=${encodeURIComponent(S.auditTask)}&limit=300` : 'audit?limit=300';
  const [r, v] = await Promise.all([sapi(q), sapi('audit/verify')]);
  const taskInp = h('input', { type: 'text', value: S.auditTask, placeholder: T('按任务 ID 过滤 filter by task id'), style: 'max-width:280px' });
  root.append(h('div', { class: 'stack' },
    h('div', { class: 'row' },
      h('span', { class: 'chip ' + (v.ok ? 'ok' : 'bad') }, v.ok ? Tf("✓ 审计链完整 hash chain intact · {0} 条", (v.checked)) : Tf("✕ 审计链在 #{0} 处损坏", (v.broken_at))),
      taskInp, h('button', { class: 'btn small', onclick: () => { S.auditTask = taskInp.value.trim(); route(); } }, T('过滤 Filter')),
      S.auditTask ? h('button', { class: 'btn small', onclick: () => { S.auditTask = ''; route(); } }, T('清除 Clear')) : null),
    h('p', { class: 'small muted', style: 'margin:0' }, T('只追加 (append-only)：每条记录都包含上一条的 SHA-256 哈希，任何篡改都会被检测到。包括模型调用、工具调用、权限决策、审批、浏览器操作。')),
    h('div', { class: 'tablewrap' }, h('table', { class: 'data' },
      h('thead', null, h('tr', null, ['#', T('时间 Time'), T('主体 Actor'), T('动作 Action'), T('资源 Resource'), T('风险 Risk'), T('决策 Decision'), T('结果 Result'), T('任务 Task')].map(x => h('th', null, x)))),
      h('tbody', null, r.events.map(e => {
        const tr = h('tr', { class: 'clickable', title: T('点击查看详情') },
          h('td', { class: 'mono' }, e.seq), h('td', { class: 'mono' }, fmtTime(e.ts)), h('td', null, e.actor), h('td', { class: 'mono' }, e.action),
          h('td', null, (e.resource || '').slice(0, 40)), h('td', null, riskPill(e.risk)), h('td', { class: 'dec-' + e.decision }, e.decision),
          h('td', null, e.result), h('td', { class: 'mono' }, e.task_id ? h('a', { href: '#tasks/' + e.task_id }, e.task_id.slice(0, 13)) : ''));
        tr.onclick = ev => { if (ev.target.tagName === 'A') return; const nx = tr.nextSibling; if (nx && nx.classList && nx.classList.contains('detail')) { nx.remove(); return; }
          tr.after(h('tr', { class: 'detail' }, h('td', { colspan: 9 }, h('pre', { style: 'white-space:pre-wrap;margin:0' }, JSON.stringify(e.detail, null, 2)), h('div', { class: 'small faint mono' }, 'hash ' + e.hash)))); };
        return tr;
      }))))));
}

// ================================================================== SETTINGS
// ================================================================== SKILLS
async function viewSkills(root) {
  const r = await api('skills');
  const boxes = {};
  const row = k => h('label', { class: 'row', style: 'align-items:flex-start;gap:10px;padding:8px 0;border-top:1px solid var(--line-2);cursor:pointer' },
    boxes[k.name] = h('input', { type: 'checkbox', checked: k.enabled, style: 'margin-top:4px' }),
    h('div', { style: 'flex:1;min-width:200px' }, h('span', { class: 'mono' }, k.name), ' ',
      h('span', { class: 'pill ' + (k.source === 'imported' ? 'st-RUNNING' : 'st-CREATED') }, k.source === 'imported' ? T('导入 imported') : T('内置 built-in')),
      h('div', { class: 'small muted' }, B(k.description)),
      k.url ? h('div', { class: 'small faint mono' }, k.url) : null),
    k.source === 'imported' ? h('button', { class: 'btn danger small', onclick: safe(async e => { e.preventDefault(); if (!confirmInline(Tf("删除导入的技能「{0}」？", k.name))) return; await api('skills/' + k.name, { method: 'DELETE' }); route(); }) }, T('删除')) : null);
  const url = h('input', { type: 'text', placeholder: 'https://github.com/owner/repo/tree/main/skills/my-skill' });
  const save = async () => {
    const disabled = Object.entries(boxes).filter(([, b]) => !b.checked).map(([n]) => n);
    await api('skills', { method: 'PUT', body: { disabled } }); toast(T('已保存 Saved'));
  };
  root.append(h('div', { class: 'card stack', id: 'skills' }, h('h3', null, T('🎓 技能 Skills')),
    h('p', { class: 'sub' }, T('技能是一份 SKILL.md：告诉 Agent 某类任务怎么做（网购、订餐厅、回邮件…）。勾选的技能会出现在 Agent 的指令里，由它按需加载；取消勾选的技能 Agent 看不到。默认全部启用。')),
    r.env ? h('p', { class: 'small muted' }, Tf("启动时由环境变量 OMUSE_SKILLS 指定：{0}（保存过的选择优先）", r.env)) : null,
    h('div', { class: 'row' },
      h('button', { class: 'btn small', onclick: () => Object.values(boxes).forEach(b => { b.checked = true; }) }, T('全选')),
      h('button', { class: 'btn small', onclick: () => Object.values(boxes).forEach(b => { b.checked = false; }) }, T('全不选')),
      h('span', { class: 'small muted' }, Tf("{0} 个技能", r.skills.length))),
    h('div', null, ...r.skills.map(row)),
    h('div', null, h('button', { class: 'btn primary', onclick: safe(save) }, T('保存选择 Save')))),
  h('div', { class: 'card stack', style: 'margin-top:16px', id: 'skillImport' }, h('h3', null, T('⬇ 从 GitHub 导入技能 Import')),
    h('p', { class: 'sub' }, T('粘贴 GitHub 上技能的链接：仓库（根目录有 SKILL.md）、技能所在的目录（…/tree/分支/路径）或 SKILL.md 文件本身。导入的技能保存在这台 OMuse 上，默认启用。只导入你信任的技能：它的内容就是给 Agent 的指令。')),
    h('div', { class: 'row' }, h('div', { style: 'flex:1;min-width:260px' }, url),
      h('button', { class: 'btn primary', onclick: safe(async () => {
        const res = await api('skills/import', { method: 'POST', body: { url: url.value } });
        toast(Tf("已导入技能「{0}」", res.skill.name)); route();
      }) }, T('导入 Import')))));
}

async function viewSettings(root) {
  const r = await api('settings');
  const s = r.settings;
  const f = {};
  const field = (k, zh, en, type = 'text', help) => { const i = h('input', { type, value: s[k] ?? '' }); f[k] = i;
    return h('label', { class: 'field' }, h('span', null, `${zh} `, LANG === 'en' ? null : h('span', { class: 'muted' }, en)), i, help ? h('span', null, help) : null); };
  const tog = (k, zh) => { const i = h('input', { type: 'checkbox', checked: !!s[k] }); f[k] = i; return h('label', { class: 'toggle' }, i, zh); };
  const testOut = h('span', { class: 'small muted' });
  const imgOut = h('span', { class: 'small muted' });
  root.append(h('div', { class: 'grid2' },
    interfaceCard(s, f),
    h('div', { class: 'card stack' }, h('h3', null, T('🧠 模型 Model')),
      h('p', { class: 'sub' }, T('任何 OpenAI 兼容接口都可以用。每类请求可以交给不同的提供商，没有哪家模型提供商能看到你的全部信息；推理、网页浏览和工具调用都在云端完成。')),
      field('model_base_url', T('接口地址'), 'Base URL'), field('model_name', T('执行模型'), 'Model'),
      field('planner_model', T('规划模型（留空=同上）'), 'Planner model'),
      field('vision_model', T('视觉模型（看网页截图，留空=同执行模型）'), 'Vision model'),
      field('stt_model', T('语音转文字模型（听音视频附件，留空=自动寻找 whisper 类模型）'), 'Speech-to-text model'),
      field('temperature', T('温度'), 'Temperature', 'number'), field('max_tokens', T('单次最大输出'), 'Max tokens', 'number'),
      field('llm_timeout', T('超时（秒）'), 'Timeout s', 'number'),
      tog('disable_thinking', T('关闭思考模式（更快，复杂任务效果可能下降）Disable thinking')),
      field('extra_body', T('额外请求参数 JSON'), 'Extra body'),
      h('div', { class: 'row' }, h('button', { class: 'btn small', onclick: safe(async () => { testOut.textContent = T('测试中…'); const t = await api('settings/test-model', { method: 'POST', body: {} });
        testOut.textContent = t.ok ? Tf("✓ {0}s：{1}", (t.latency_s), (t.reply)) : '✕ ' + t.error; }) }, T('测试模型 Test model')), testOut),
      h('h3', { style: 'margin-top:12px' }, T('🎨 图片生成 Images')),
      h('p', { class: 'sub' }, T('留空 = 用上面的接口地址并自动寻找图像模型。接 OpenAI 时填 https://api.openai.com/v1 + gpt-image-1；密钥只能通过环境变量 OMUSE_IMAGE_API_KEY 提供，不在这里填。')),
      field('image_base_url', T('图片接口地址（留空=同上）'), 'Image base URL'),
      field('image_model', T('图像模型（留空=自动）'), 'Image model'),
      h('div', { class: 'row' }, h('button', { class: 'btn small', onclick: safe(async () => { imgOut.textContent = T('检查中…');
        const t = await api('settings/test-image', { method: 'POST', body: { image_base_url: f.image_base_url.value, image_model: f.image_model.value } });
        imgOut.textContent = t.ok ? Tf("✓ {0} @ {1}（密钥：{2}）", t.model, t.base, t.key) : '✕ ' + t.error; }) }, T('检查图片接口 Check image endpoint')), imgOut)),
    h('div', { class: 'card stack' }, h('h3', null, '🤖 Agent'),
      langField(s, f),
      field('user_name', T('你的名字'), 'Your name'), field('timezone', T('时区（定时任务）'), 'Timezone'),
      field('max_steps', T('每个任务最多步数'), 'Max steps', 'number'),
      field('max_minutes', T('每个任务最长用时（分钟）'), 'Time limit (minutes)', 'number'),
      tog('memory_extraction', T('任务结束后自动提取长期记忆 Auto memory extraction')),
      tog('memory_consolidation', T('每天自动整理记忆并发送报告到 Telegram Daily memory tidy')),
      field('memory_consolidate_at', T('每天整理时间（HH:MM）'), 'Tidy at'),
      h('div', null, h('b', null, T('技能 Skills')), ' ', h('a', { href: '#skills', class: 'small' }, Tf("{0} 个已启用 · 在「技能」页管理", r.skills.length)))),
  ), h('div', { style: 'margin-top:16px' }, h('button', { class: 'btn primary', onclick: safe(async () => {
    const body = {};
    for (const [k, el] of Object.entries(f)) body[k] = el.type === 'checkbox' ? el.checked : el.type === 'number' ? Number(el.value) : el.value;
    await api('settings', { method: 'PUT', body }); toast(T('已保存 Saved')); refreshModelChip();
    applyTheme(body.theme);
    const want = UI_LANGS.includes(body.ui_language) ? body.ui_language : browserLang();
    if (want !== LANG) { try { localStorage.setItem('omuse_ui', want); } catch (e) { /* ignore */ } location.reload(); }
  }) }, T('保存设置 Save settings'))));
  // standalone installs (OMUSE_PASSWORD): change the login password
  const pw = await sapi('password').catch(() => null);
  if (pw && pw.enabled) root.append(passwordCard(pw));
  // hosted installs only (the three OMUSE_STRIPE_* variables): the last section of Settings
  const sub = await sapi('subscription').catch(() => null);
  if (sub && sub.enabled) root.append(subscriptionCard(sub));
}

// Standalone installs start on the password the host chose (OMUSE_PASSWORD): the chat reminds the user until they set
// their own (renderThread puts the banner above the thread while S.passwordDefault is true).
function passwordReminder() {
  if (S.passwordDefault !== undefined) return;
  sapi('password').then(r => { S.passwordDefault = !!(r.enabled && r.default); if (S.passwordDefault && S.view === 'chat') renderThread(); }).catch(() => {});
}
const pwBanner = () => h('div', { class: 'banner user', id: 'pwReminder', style: 'margin:10px 24px 0' },
  h('span', { style: 'flex:1' }, T('🔑 你还在用初始密码。请到「设置」里改成自己的密码。')),
  h('a', { href: '#settings', class: 'btn small' }, T('去修改 Change')));

function passwordCard(info) {
  const cur = h('input', { type: 'password', autocomplete: 'current-password' });
  const nw = h('input', { type: 'password', autocomplete: 'new-password', minlength: info.min_length || 8 });
  const again = h('input', { type: 'password', autocomplete: 'new-password' });
  const field = (label, i) => h('label', { class: 'field' }, h('span', null, label), i);
  return h('div', { class: 'card stack', id: 'password', style: 'margin-top:16px' }, h('h3', null, T('🔑 登录密码 Password')),
    h('p', { class: 'sub' }, Tf("登录名 {0}。改完后浏览器会要求你用新密码重新登录。", info.user || 'omuse')),
    info.default ? h('p', { class: 'small', id: 'pwDefault', style: 'color:var(--warn)' }, T('你还在用初始密码，请尽快修改。')) : null,
    field(T('当前密码'), cur), field(Tf("新密码（至少 {0} 个字符）", info.min_length || 8), nw), field(T('再输一次新密码'), again),
    h('div', { class: 'row' }, h('button', { class: 'btn primary', onclick: safe(async () => {
      if (nw.value !== again.value) throw new Error(T('两次输入的新密码不一样'));
      await sapi('password', { method: 'POST', body: { current: cur.value, new: nw.value } });
      S.passwordDefault = false; cur.value = nw.value = again.value = '';
      toast(T('密码已修改，请用新密码重新登录')); setTimeout(() => location.reload(), 1500);
    }) }, T('修改密码 Change password'))));
}

function subscriptionCard(sub) {
  const day = sub.current_period_end ? new Date(sub.current_period_end * 1000).toLocaleDateString() : '';
  const state = sub.error ? '' : !sub.status ? '' : sub.status === 'canceled' ? T('订阅已取消。')
    : sub.cancel_at_period_end ? (day ? Tf("订阅已设为到期取消，{0} 结束。", day) : T('订阅已设为到期取消。'))
    : ['active', 'trialing'].includes(sub.status) ? (day ? Tf("订阅生效中，{0} 续订。", day) : T('订阅生效中。'))
    : Tf("订阅状态：{0}", sub.status);
  return h('div', { class: 'card stack', id: 'subscription', style: 'margin-top:16px' }, h('h3', null, T('💳 管理订阅 Manage subscription')),
    h('p', { class: 'sub' }, T('在 Stripe 的页面上取消或续订这台 OMuse 的订阅。')),
    state ? h('p', { class: 'small', id: 'subscriptionState' }, state) : null,
    h('div', { class: 'row' }, h('button', { class: 'btn', onclick: safe(async () => {
      const r = await sapi('subscription/portal', { method: 'POST', body: {} }); location.href = r.url;
    }) }, T('打开订阅页面 Open subscription page'))));
}

// UI language and theme: per install (Settings), so every browser the user signs in from looks the same.
function interfaceCard(s, f) {
  const ui = h('select', { 'aria-label': 'UI language' },
    h('option', { value: '' }, T('跟随浏览器 Follow browser')),
    h('option', { value: 'en' }, 'English'),  // i18n-ok: language names are shown in their own language
    h('option', { value: 'zh' }, '简体中文'),  // i18n-ok
    h('option', { value: 'tw' }, '繁體中文'));  // i18n-ok
  ui.value = UI_LANGS.includes(s.ui_language) ? s.ui_language : '';
  f.ui_language = ui;
  const th = h('select', { 'aria-label': 'Theme' },
    h('option', { value: 'auto' }, T('跟随系统 Follow system')),
    h('option', { value: 'paper' }, T('Paper（米白）')),
    h('option', { value: 'ink' }, T('Ink（深色）')));
  th.value = s.theme === 'ink' || s.theme === 'paper' ? s.theme : 'auto';
  f.theme = th;
  return h('div', { class: 'card stack', id: 'interface' }, h('h3', null, T('🖥 界面 Interface')),
    h('label', { class: 'field' }, h('span', null, T('界面语言'), LANG === 'en' ? null : h('span', { class: 'muted' }, ' UI language')), ui,
      h('div', { class: 'small muted', style: 'font-weight:400' }, T('只影响界面文字。「跟随浏览器」= 英文、简体或繁体浏览器各看各的；选定一种后，你在任何设备上登录都用它。'))),
    h('label', { class: 'field' }, h('span', null, T('外观'), LANG === 'en' ? null : h('span', { class: 'muted' }, ' Theme')), th));
}

function langField(s, f) {
  const sel = h('select', { 'aria-label': 'Language' },
    h('option', { value: 'zh' }, '中文'),  // i18n-ok: language names are shown in their own language
    h('option', { value: 'en' }, 'English'));
  sel.value = s.language === 'en' || s.language === 'zh' ? s.language : LANG;
  f.language = sel;
  const rep = h('select', { 'aria-label': 'Reply language' },
    h('option', { value: '' }, T('和上面的语言一致')),
    h('option', { value: 'match' }, T('跟随我提问用的语言（中文问中文答，英文问英文答）')));
  rep.value = s.reply_language === 'match' ? 'match' : '';
  f.reply_language = rep;
  return h('div', null,
    h('label', { class: 'field' }, h('span', null, T('Agent 语言'), LANG === 'en' ? null : h('span', { class: 'muted' }, ' Agent language')), sel,
      h('div', { class: 'small muted', style: 'font-weight:400' }, T('Agent 用这个语言思考和工作：思考过程、任务计划、回答、通知和定时任务的汇报。界面语言在上面的「界面」里单独设置。'))),
    h('label', { class: 'field' }, h('span', null, T('回答语言')), rep,
      h('div', { class: 'small muted', style: 'font-weight:400' }, T('选「跟随我提问用的语言」时，每个任务按你那条消息的语言来思考和回答；界面、通知和定时任务汇报仍用上面的语言。'))));
}

// ================================================================== live updates
function onEvent(ev) {
  if (ev.kind === 'ping') return;
  if (ev.kind === 'task_update') {
    const t = ev.task; mergeTasks({ [t.id]: t });
    renderNav();
    const card = document.getElementById('tc-' + t.id);
    if (card && S.view === 'chat') { const fresh = taskCard(S.tasks[t.id]); const det = card.querySelector('details'); const wasOpen = det && det.open;
      card.parentElement.replaceWith(fresh); if (wasOpen) { const d2 = fresh.querySelector('details'); d2.open = true; } }
    if (S.view === 'tasks' && S.selTask === t.id) { const box = $('#taskDetail'); if (box) renderTaskDetail(box, t.id); }
    if (t.status === 'COMPLETED' && t.source === 'schedule') toast(Tf("⏰ 定时任务完成：{0}", (t.goal.slice(0, 40))));
  } else if (ev.kind === 'task_event') {
    const tl = document.getElementById('tl-' + ev.task_id);
    if (tl && tl.closest('details').open && ev.type !== 'thinking') { if (tl.querySelector('.muted.small')) tl.innerHTML = ''; tl.append(evLine(ev)); }
    // the model call is being retried: say so on the card ("Retrying 1 of 3"); the next event clears it
    const rt = document.querySelector('#tc-' + ev.task_id + ' .retry');
    if (rt) { if (ev.type === 'llm_retry') { rt.textContent = Tf("🔁 重试中 {0}/{1}（{2}，{3} 秒后）Retrying", ev.data.attempt, ev.data.of, ev.data.reason || '', ev.data.wait_s); rt.hidden = false; } else rt.hidden = true; }
    if (ev.type === 'plan' && S.tasks[ev.task_id]) { S.tasks[ev.task_id].plan = ev.data; const card = document.getElementById('tc-' + ev.task_id);
      if (card && S.view === 'chat') card.parentElement.replaceWith(taskCard(S.tasks[ev.task_id])); }
  } else if (ev.kind === 'conv_update') {
    if (S.view === 'chat') { loadConvs().then(() => renderConvList()); if (ev.conv_id === S.conv) refreshConv(true); }
  } else if (ev.kind === 'approval_requested') {
    loadApprovals();
  } else if (ev.kind === 'takeover_requested') {
    takeoverToast(ev);
  } else if (ev.kind === 'notification') {
    toast('🔔 ' + ev.notification.title + T('：') + ev.notification.body);
  } else if (ev.kind === 'memory_update' && S.view === 'memory') { const a = document.activeElement; if (!(a && /INPUT|TEXTAREA|SELECT/.test(a.tagName) && a.closest('#view'))) route(); }
  else if ((ev.kind === 'schedule_update' || ev.kind === 'goal_update') && S.view === 'schedules') route();
}

// Takeover requests arriving close together (several tasks blocked on the same site) become ONE pop-up, and the same
// task never pops up twice within a minute.
const TK = { q: new Map(), timer: null, last: new Map() };
function takeoverToast(ev) {
  const now = Date.now();
  if (now - (TK.last.get(ev.task_id) || 0) < 60000) return;
  TK.last.set(ev.task_id, now);
  TK.q.set(ev.task_id, ev.reason || '');
  clearTimeout(TK.timer);
  TK.timer = setTimeout(() => {
    const ids = [...TK.q.keys()], reasons = [...TK.q.values()]; TK.q.clear();
    const go = () => { location.hash = 'browser' + (ids.length === 1 ? '/' + ids[0] : ''); };
    if (reasons.length === 1) toast(T('🖐 Agent 请求你接管浏览器：') + reasons[0], false, go);
    else if (reasons.length) toast(Tf("🖐 {0} 个任务在等你接管浏览器（点这里打开浏览器）", reasons.length), false, go);
  }, 800);
}

// The stream can drop without the page noticing (laptop sleep, network change, session refresh): the browser
// may reconnect and silently lose the events of the gap, or give up for good. So: the server sends a ping every 15 s,
// a watchdog reconnects when nothing arrived for 45 s, and every (re)connect re-reads the state that may have been missed.
let ES = null, lastEv = 0;
function connectStream() {
  if (ES) { try { ES.close(); } catch (e) {} }
  const es = ES = new EventSource('api/stream');
  lastEv = Date.now();
  es.onmessage = m => { lastEv = Date.now(); try { onEvent(JSON.parse(m.data)); } catch (e) { console.error(e); } };
  es.onerror = () => {
    $('#sentinelChip').className = 'chip bad';
    if (es.readyState === 2 && ES === es) setTimeout(() => { if (ES === es) connectStream(); }, 3000);  // closed for good: start over
  };
  es.onopen = () => {
    lastEv = Date.now(); $('#sentinelChip').className = 'chip ok';
    if (S._streamSeen) resync();
    S._streamSeen = true;
  };
}
function resync() {
  loadApprovals();
  refreshConv();
  if (S.view === 'tasks' && S.selTask) { const box = $('#taskDetail'); if (box) renderTaskDetail(box, S.selTask); }
}
// A hidden tab talks to the server not at all: the stream is closed and nothing polls, so an idle box can go to
// sleep. When the tab is shown again the stream reconnects and the state that may have changed is re-read.
setInterval(() => { if (!document.hidden && (!ES || ES.readyState === 2 || Date.now() - lastEv > 45000)) connectStream(); }, 10000);
// safety net while a task in the open conversation is still running (costs one small request every 8 s)
setInterval(() => { if (!document.hidden && S.view === 'chat' && convHasActiveTask()) refreshConv(); }, 8000);
// approvals arrive as stream events (approval_requested); this poll only covers a stream that has gone quiet
setInterval(() => { if (!document.hidden && ES && Date.now() - lastEv > 20000) loadApprovals(); }, 30000);
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { if (ES) { try { ES.close(); } catch (e) {} ES = null; } return; }
  if (!ES || ES.readyState === 2 || Date.now() - lastEv > 20000) connectStream(); else resync();
});

async function refreshModelChip() {
  try {
    const r = await api('settings');
    const name = String(r.settings.model_name || '').split('/').pop().replace(/-GGUF.*$/i, '');
    $('#modelChip').textContent = '🧠 ' + name;
    $('#modelChip').title = r.settings.model_base_url;
  } catch (e) { $('#modelChip').textContent = T('模型 ?'); }
}

// ------------------------------------------------------------------ boot
$('#approvalBell').onclick = () => { $('#drawer').hidden = !$('#drawer').hidden; renderDrawer(); };
$('#drawerClose').onclick = () => { $('#drawer').hidden = true; };
const setNav = open => { $('#nav').classList.toggle('open', open); $('#navBack').hidden = !open; };
$('#menuBtn').onclick = () => setNav(!$('#nav').classList.contains('open'));
$('#navBack').onclick = () => setNav(false);
$('#navlinks').addEventListener('click', e => { if (e.target.closest('a')) setNav(false); });
// keep the layout exactly as tall as the visible area (iOS/Android keyboards and toolbars)
if (window.visualViewport) {
  const vv = window.visualViewport;
  const fit = () => {
    document.documentElement.style.setProperty('--app-h', vv.height + 'px');
    if (vv.height < window.innerHeight) window.scrollTo(0, 0);
    const m = $('.msgs'); const ta = $('#chatInput');
    if (m && ta && document.activeElement === ta) m.scrollTop = m.scrollHeight;
  };
  vv.addEventListener('resize', fit); fit();
}
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeModal(); closeHistory(); $('#drawer').hidden = true; }
  if (e.altKey && (e.key === 'n' || e.key === 'N') && S.view === 'chat') { e.preventDefault(); newChat(); }
});
document.addEventListener('click', e => { const p = $('#histPop'); if (p && !p.contains(e.target) && !e.target.closest('.hist-btn')) closeHistory(); });
window.addEventListener('hashchange', () => { route(); });
i18nStatic();
(async () => {
  await syncLang();
  try { const hs = await sapi('health'); $('#navfoot').textContent = Tf("v{0} · 专属计算机 · 私有上下文", (hs.version)); } catch (e) {}
  // seed "seen" so old pending approvals don't all pop at once; open the newest one
  try { const r = await sapi('approvals?status=pending'); S.approvals = r.approvals; } catch (e) {}
  route();
  refreshModelChip();
  connectStream();
  loadApprovals();
})();
})();
