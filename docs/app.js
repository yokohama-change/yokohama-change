const state = {items: [], status: {}, quality: {}, gbiz: {items: []}};
const $ = (s) => document.querySelector(s);
const esc = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (iso) => { try { return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tokyo'}).format(new Date(iso)); } catch { return iso || '—'; } };
const fmtDate = (iso) => { try { return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short',timeZone:'Asia/Tokyo'}).format(new Date(`${iso}T12:00:00+09:00`)); } catch { return iso || '—'; } };
const changeLabel = (v) => v==='added'?'新規':v==='updated'?'更新':'基準データ';
const statusClass = (v) => v==='受付中'?'open':v==='資格者のみ進行中'?'qualified':v==='参加締切済'?'closed':v==='結果掲載済'?'result':'unknown';
const tierClass = (v) => v==='最優先'?'top':v==='高優先'?'high':'normal';
const detailStatuses = new Set(['受付中','参加締切済','結果掲載済','資格者のみ進行中']);

function detailUrl(x){
  const id = String(x?.id || '').trim();
  const safeId = /^[A-Za-z0-9_-]{6,80}$/.test(id);
  const publishable = safeId && x?.status_confidence === 'high' && x?.participation_deadline_at && detailStatuses.has(x?.application_status);
  return publishable ? `opportunities/${encodeURIComponent(id)}.html` : '';
}

function internalLinkAttrs(x){
  const detail = detailUrl(x);
  return detail ? `href="${esc(detail)}"` : `href="${esc(x.url)}" target="_blank" rel="noopener"`;
}

function statusMatch(x, status){
  if (!status || status==='all') return true;
  if (status==='open') return x.is_open_now === true;
  if (status==='closed') return x.is_open_now === false;
  if (status==='unknown') return x.is_open_now == null && x.application_status !== '案件外';
  return x.application_status === status;
}

function rankOpen(a,b){
  return Number(b.commercial_score||0)-Number(a.commercial_score||0) ||
    Number(a.days_left ?? 9999)-Number(b.days_left ?? 9999) ||
    Number(b.urgency||0)-Number(a.urgency||0);
}

function deadlineMs(x){
  if (x?.deadline_time_exact !== true || !x.participation_deadline_at) return null;
  const t = new Date(x.participation_deadline_at).getTime();
  return Number.isFinite(t) ? t - Date.now() : null;
}

function tokyoDateKey(date = new Date()){
  try {
    const parts = new Intl.DateTimeFormat('en-US',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'Asia/Tokyo'}).formatToParts(date);
    const get = (type) => parts.find(p => p.type === type)?.value || '';
    return `${get('year')}-${get('month')}-${get('day')}`;
  } catch {
    return '';
  }
}

function isTodayDeadline(x){
  return Boolean(x.participation_deadline && x.participation_deadline === tokyoDateKey());
}

function alertDataHealthy(){
  const status = state.status || {};
  const quality = state.quality || {};
  const errorLists = [
    status.errors,
    status.application_status_errors,
    status.application_status_warnings,
    status.support_period_errors,
    status.gbiz_errors,
    quality.errors,
    quality.warnings
  ];
  const noReportedProblems = errorLists.every(v => !Array.isArray(v) || v.length === 0);
  const sourcesKnown = Number.isFinite(Number(status.sources_total)) && Number.isFinite(Number(status.sources_ok));
  const sourcesHealthy = sourcesKnown && Number(status.sources_total) > 0 && Number(status.sources_ok) === Number(status.sources_total);
  const checks = quality.checks && typeof quality.checks === 'object' ? Object.values(quality.checks) : [];
  const checksHealthy = checks.length > 0 && checks.every(Boolean);
  const generatedAt = Date.parse(status.generated_at || '');
  const ageMs = Number.isFinite(generatedAt) ? Date.now() - generatedAt : Infinity;
  const freshEnough = ageMs >= -5 * 60 * 1000 && ageMs <= 26 * 3600000;
  return quality.health === 'good' && noReportedProblems && sourcesHealthy && checksHealthy && status.state_preserved === false && freshEnough;
}

function urgentTimeLabel(ms){
  const hours = ms / 3600000;
  if (hours < 1) return '残り1時間未満';
  return `残り約${Math.ceil(hours)}時間`;
}

function deadlineBlock(x){
  if (!x.participation_deadline) return '';
  const label = x.deadline_label || `締切 ${fmtDate(x.participation_deadline)}`;
  const exact = x.deadline_time_exact === true && x.participation_deadline_at ? ` · ${fmt(x.participation_deadline_at)}` : '';
  const note = x.deadline_time_exact === true ? '' : ' · 時刻未確認';
  return `<div class="deadline ${x.is_open_now===true?'live':''}"><strong>${esc(label)}</strong><span>参加期限 ${esc(fmtDate(x.participation_deadline))}${esc(exact)}${esc(note)}</span></div>`;
}

function renderUrgent(){
  const shell = $('#urgentShell');
  const target = $('#urgentCards');
  if (!shell || !target || !alertDataHealthy()) {
    if (shell) shell.hidden = true;
    if (target) target.innerHTML = '';
    return;
  }

  const urgent = state.items.map(x => ({x, ms: deadlineMs(x)})).filter(({x,ms}) =>
    x.is_open_now === true &&
    x.status_confidence === 'high' &&
    Number(x.commercial_score||0) >= 70 &&
    ms != null && ms > 0 && ms <= 48 * 3600000
  ).sort((a,b) =>
    Number(isTodayDeadline(b.x)) - Number(isTodayDeadline(a.x)) ||
    a.ms - b.ms ||
    Number(b.x.commercial_score||0)-Number(a.x.commercial_score||0)
  );

  if (!urgent.length) {
    shell.hidden = true;
    shell.classList.remove('today-mode');
    target.innerHTML = '';
    return;
  }

  const hasToday = urgent.some(({x}) => isTodayDeadline(x));
  const kicker = shell.querySelector('.urgent-kicker');
  const title = shell.querySelector('.urgent-heading h2');
  const note = shell.querySelector('.urgent-note');
  shell.hidden = false;
  shell.classList.toggle('today-mode', hasToday);
  if (kicker) kicker.textContent = hasToday ? '本日締切' : '締切が近い案件';
  if (title) title.textContent = hasToday ? '今日が締切の優先案件' : '締切48時間以内の優先案件';
  if (note) note.textContent = hasToday
    ? '見る優先度70以上・受付中・公式の締切時刻まで確認できた案件のうち、本日締切のものを表示します。'
    : '見る優先度70以上・受付中・公式の締切時刻まで確認できた案件だけを表示します。';

  target.innerHTML = urgent.map(({x,ms}) => {
    const today = isTodayDeadline(x);
    const detail = detailUrl(x);
    return `
    <article class="urgent-card ${today?'today':''}">
      <div class="urgent-topline">
        <span class="urgent-badge ${today?'today':''}">${today?'本日締切':'締切48時間以内'}</span>
        <strong>${esc(urgentTimeLabel(ms))}</strong>
        <span class="business-score">見る優先度 ${esc(x.commercial_score ?? 0)}</span>
      </div>
      <a class="urgent-title" ${internalLinkAttrs(x)}>${esc(x.title)}</a>
      ${deadlineBlock(x)}
      <div class="urgent-meta">${esc(x.opportunity_type || '情報更新')} · ${esc(x.source_name || '')}</div>
      <div class="card-actions">
        ${detail ? `<a class="details-link" href="${esc(detail)}">かんたん詳細を見る →</a>` : ''}
        <a class="external-link" href="${esc(x.url)}" target="_blank" rel="noopener">自治体公式サイト ↗</a>
      </div>
    </article>`;
  }).join('');
}

function recentExpiryProofItems(){
  const now = Date.now();
  const windowMs = 36 * 3600000;
  return state.items.map(x => ({x, deadline: Date.parse(x.participation_deadline_at || '')})).filter(({x,deadline}) => {
    const elapsed = now - deadline;
    return x.is_open_now === false &&
      x.status_confidence === 'high' &&
      Number(x.commercial_score||0) >= 70 &&
      Number.isFinite(deadline) &&
      elapsed >= 0 && elapsed <= windowMs &&
      (x.application_status === '参加締切済' || x.application_status === '結果掲載済');
  }).sort((a,b) => b.deadline - a.deadline || Number(b.x.commercial_score||0)-Number(a.x.commercial_score||0));
}

function renderQualityProof(){
  const shell = $('#qualityProof');
  const target = $('#qualityProofItems');
  const count = $('#qualityProofCount');
  if (!shell || !target || !count || !alertDataHealthy()) {
    if (shell) shell.hidden = true;
    if (target) target.innerHTML = '';
    return;
  }

  const items = recentExpiryProofItems();
  if (!items.length) {
    shell.hidden = true;
    target.innerHTML = '';
    return;
  }

  shell.hidden = false;
  count.textContent = items.length;
  target.innerHTML = items.slice(0,3).map(({x}) => `
    <div class="quality-proof-item">
      <span class="quality-proof-check" aria-hidden="true">✓</span>
      <div class="quality-proof-copy">
        <a class="quality-proof-title" ${internalLinkAttrs(x)}>${esc(x.title)}</a>
        <small>${x.deadline_time_exact === true ? esc(fmt(x.participation_deadline_at)) : esc(fmtDate(x.participation_deadline))} 締切 → 現在は「${esc(x.application_status)}」</small>
      </div>
      <span class="quality-proof-score">優先度 ${esc(x.commercial_score ?? 0)}</span>
    </div>`).join('');
}

function renderPriority(){
  const target = $('#priorityCards');
  if (!target) return;
  const open = state.items.filter(x => x.is_open_now === true).sort(rankOpen);
  target.innerHTML = open.length ? open.slice(0,4).map((x,i) => {
    const detail = detailUrl(x);
    return `
    <article class="priority-card ${tierClass(x.priority_tier)}">
      <div class="priority-topline">
        <span class="rank">${i===0?'#1':'#'+(i+1)}</span>
        <span class="tier">${esc(x.priority_tier || '受付中')}</span>
        <span class="business-score">見る優先度 ${esc(x.commercial_score ?? 0)}</span>
      </div>
      <a class="priority-title" ${internalLinkAttrs(x)}>${esc(x.title)}</a>
      ${deadlineBlock(x)}
      <div class="priority-meta">${esc(x.region || '')} · ${esc(x.opportunity_type || '情報更新')} · ${esc(x.source_name || '')}</div>
      ${(x.buyer_segments||[]).length ? `<div class="buyers">向いていそうな方：${x.buyer_segments.map(v=>`<span>${esc(v)}</span>`).join('')}</div>` : ''}
      <div class="card-actions">
        ${detail ? `<a class="details-link" href="${esc(detail)}">かんたん詳細を見る →</a>` : ''}
        <a class="external-link" href="${esc(x.url)}" target="_blank" rel="noopener">自治体公式サイト ↗</a>
      </div>
    </article>`;
  }).join('') : '<div class="empty priority-empty">現在、公式期限を確認できた「受付中」案件はありません。次回収集で自動更新されます。</div>';
}

function render(){
  const q = $('#search')?.value.trim().toLowerCase() || '';
  const cat = $('#category')?.value || '';
  const buyer = $('#buyer')?.value || '';
  const minCommercial = Number($('#commercial')?.value || 0);
  const status = $('#applicationStatus')?.value || 'open';
  const items = state.items.filter(x =>
    (!q || `${x.title} ${x.description} ${x.source_name} ${x.opportunity_type} ${x.application_status} ${(x.buyer_segments||[]).join(' ')}`.toLowerCase().includes(q)) &&
    (!cat || x.category===cat) &&
    (!buyer || (x.buyer_segments||[]).includes(buyer)) &&
    Number(x.commercial_score||0)>=minCommercial &&
    statusMatch(x, status)
  ).sort((a,b) =>
    (b.is_open_now===true) - (a.is_open_now===true) ||
    Number(b.commercial_score||0)-Number(a.commercial_score||0) ||
    Number(a.days_left ?? 9999)-Number(b.days_left ?? 9999) ||
    Number(b.urgency||0)-Number(a.urgency||0)
  );

  const target = $('#cards');
  if (!target) return;
  target.innerHTML = items.length ? items.map(x => {
    const detail = detailUrl(x);
    return `
    <article class="card">
      <div class="score"><b>${esc(x.commercial_score ?? 0)}</b><small>見る優先度</small><em>重要度 ${esc(x.importance ?? 0)}</em></div>
      <div>
        <div class="signalrow">
          <span class="signal">${esc(x.opportunity_type || '情報更新')}</span>
          ${x.priority_tier ? `<span class="priority-badge ${tierClass(x.priority_tier)}">${esc(x.priority_tier)}</span>` : ''}
          ${x.application_status ? `<span class="appstatus ${statusClass(x.application_status)}">${esc(x.application_status)}</span>` : ''}
        </div>
        <a class="title" ${internalLinkAttrs(x)}>${esc(x.title)}</a>
        <div class="meta">${esc(x.region || '')} · ${esc(x.category)} · ${esc(x.source_name)}</div>
        ${deadlineBlock(x)}
        ${x.next_deadline && x.next_deadline !== x.participation_deadline ? `<div class="next-deadline">次の日程：${esc(fmtDate(x.next_deadline))}</div>` : ''}
        ${x.why_it_matters ? `<p class="why">${esc(x.why_it_matters)}</p>` : ''}
        ${(x.buyer_segments||[]).length ? `<div class="buyers">向いていそうな方：${x.buyer_segments.map(v=>`<span>${esc(v)}</span>`).join('')}</div>` : ''}
        ${x.status_reason ? `<div class="statusreason">受付状況の根拠：${esc(x.status_reason)}</div>` : ''}
        <div class="card-actions">
          ${detail ? `<a class="details-link" href="${esc(detail)}">かんたん詳細</a>` : ''}
          <a class="external-link" href="${esc(x.url)}" target="_blank" rel="noopener">自治体公式サイト ↗</a>
        </div>
      </div>
      <div class="badge ${esc(x.change_type)}">${changeLabel(x.change_type)}</div>
    </article>`;
  }).join('') : '<div class="empty">現在の条件に一致する案件はありません。条件を元に戻すと、もう一度すべて確認できます。</div>';
}

function renderGbiz(){
  const target = $('#gbizSignals');
  if (!target) return;
  const gbiz = state.gbiz || {};
  const items = Array.isArray(gbiz.items) ? gbiz.items : [];
  let html = '';
  if (!gbiz.enabled) {
    target.innerHTML = '<div class="empty small">法人更新の参考情報は現在停止中です。</div>';
    return;
  }
  if (gbiz.stale) {
    html += '<div class="signal-warning">直近取得に失敗したため前回データを保持中です。募集案件には影響しません。</div>';
  }
  html += items.slice(0,8).map(x => `
    <div class="company-signal">
      <div><strong>${esc(x.name || '法人名未取得')}</strong><small>法人番号 ${esc(x.corporate_number || '—')}</small></div>
      <span>法人情報更新</span>
    </div>`).join('');
  target.innerHTML = html || '<div class="empty small">直近期間に横浜市内の法人更新情報はありません。</div>';
}

function setMetrics(data){
  const open = state.items.filter(x=>x.is_open_now===true);
  if ($('#openCount')) $('#openCount').textContent = open.length;
  if ($('#hotCount')) $('#hotCount').textContent = open.filter(x=>Number(x.commercial_score||0)>=70).length;
  if ($('#runCount')) $('#runCount').textContent = data.changes_this_run ?? 0;
  if ($('#updated')) $('#updated').textContent = fmt(data.generated_at);
  const quality = state.quality || {};
  if ($('#qualityLabel')) {
    $('#qualityLabel').textContent = quality.health_label || (state.status.sources_ok===state.status.sources_total ? '正常' : '注意');
    $('#qualityLabel').className = `quality-${quality.health || 'unknown'}`;
  }
}

async function getJson(url, fallback={}){
  try {
    const r = await fetch(url,{cache:'no-store'});
    if (!r.ok) return fallback;
    return await r.json();
  } catch { return fallback; }
}

Promise.all([
  getJson('./data/latest.json',{items:[]}),
  getJson('./data/status.json',{}),
  getJson('./data/quality.json',{}),
  getJson('./data/gbiz_latest.json',{items:[]})
]).then(([data,status,quality,gbiz])=>{
  state.items = data.items || [];
  state.status = status || {};
  state.quality = quality || {};
  state.gbiz = gbiz || {items:[]};
  setMetrics(data);
  const cats = [...new Set(state.items.map(x=>x.category).filter(Boolean))].sort();
  const buyers = [...new Set(state.items.flatMap(x=>x.buyer_segments||[]).filter(Boolean))].sort();
  if ($('#category')) $('#category').innerHTML += cats.map(c=>`<option>${esc(c)}</option>`).join('');
  if ($('#buyer')) $('#buyer').innerHTML += buyers.map(c=>`<option>${esc(c)}</option>`).join('');
  if ($('#notice')) {
    $('#notice').hidden = false;
    $('#notice').innerHTML = '掲載内容は参考情報です。応募・契約前には必ず自治体の公式情報をご確認ください。 <a href="disclaimer.html">免責事項</a>';
  }
  renderUrgent();
  renderPriority();
  renderQualityProof();
  render();
  renderGbiz();
}).catch(err=>{
  if ($('#cards')) $('#cards').innerHTML='<div class="empty">データの読み込みに失敗しました。時間をおいてもう一度お試しください。</div>';
  console.error(err);
});
['search','category','buyer','commercial','applicationStatus'].forEach(id => {
  const el = $('#'+id);
  if (el) el.addEventListener('input',render);
});
