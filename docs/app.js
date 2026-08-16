const state = {items: [], status: {}, quality: {}, gbiz: {items: []}};
const $ = (s) => document.querySelector(s);
const esc = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (iso) => { try { return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tokyo'}).format(new Date(iso)); } catch { return iso || '—'; } };
const fmtDate = (iso) => { try { return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short',timeZone:'Asia/Tokyo'}).format(new Date(`${iso}T12:00:00+09:00`)); } catch { return iso || '—'; } };
const changeLabel = (v) => v==='added'?'新規':v==='updated'?'更新':'基準データ';
const statusClass = (v) => v==='受付中'?'open':v==='資格者のみ進行中'?'qualified':v==='参加締切済'?'closed':v==='結果掲載済'?'result':'unknown';
const tierClass = (v) => v==='最優先'?'top':v==='高優先'?'high':'normal';

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
  if (!x.participation_deadline_at) return null;
  const t = new Date(x.participation_deadline_at).getTime();
  return Number.isFinite(t) ? t - Date.now() : null;
}

function urgentTimeLabel(ms){
  const hours = ms / 3600000;
  if (hours < 1) return '残り1時間未満';
  return `残り約${Math.ceil(hours)}時間`;
}

function deadlineBlock(x){
  if (!x.participation_deadline) return '';
  const label = x.deadline_label || `締切 ${fmtDate(x.participation_deadline)}`;
  const exact = x.participation_deadline_at ? ` · ${fmt(x.participation_deadline_at)}` : '';
  return `<div class="deadline ${x.is_open_now===true?'live':''}"><strong>${esc(label)}</strong><span>参加期限 ${esc(fmtDate(x.participation_deadline))}${esc(exact)}</span></div>`;
}

function renderUrgent(){
  const shell = $('#urgentShell');
  const target = $('#urgentCards');
  const urgent = state.items.map(x => ({x, ms: deadlineMs(x)})).filter(({x,ms}) =>
    x.is_open_now === true &&
    x.status_confidence === 'high' &&
    Number(x.commercial_score||0) >= 70 &&
    ms != null && ms > 0 && ms <= 48 * 3600000
  ).sort((a,b) => a.ms - b.ms || Number(b.x.commercial_score||0)-Number(a.x.commercial_score||0));

  if (!urgent.length) {
    shell.hidden = true;
    target.innerHTML = '';
    return;
  }

  shell.hidden = false;
  target.innerHTML = urgent.map(({x,ms}) => `
    <article class="urgent-card">
      <div class="urgent-topline">
        <span class="urgent-badge">締切迫る</span>
        <strong>${esc(urgentTimeLabel(ms))}</strong>
        <span>商用 ${esc(x.commercial_score ?? 0)}</span>
      </div>
      <a class="urgent-title" href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>
      ${deadlineBlock(x)}
      <div class="urgent-meta">${esc(x.opportunity_type || '情報更新')} · ${esc(x.source_name || '')}</div>
      <a class="urgent-cta" href="${esc(x.url)}" target="_blank" rel="noopener">今すぐ公式情報を確認 →</a>
    </article>`).join('');
}

function renderPriority(){
  const open = state.items.filter(x => x.is_open_now === true).sort(rankOpen);
  $('#priorityCards').innerHTML = open.length ? open.slice(0,4).map((x,i) => `
    <article class="priority-card ${tierClass(x.priority_tier)}">
      <div class="priority-topline">
        <span class="rank">${i===0?'#1':'#'+(i+1)}</span>
        <span class="tier">${esc(x.priority_tier || '受付中')}</span>
        <span class="business-score">商用 ${esc(x.commercial_score ?? 0)}</span>
      </div>
      <a class="priority-title" href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>
      ${deadlineBlock(x)}
      <div class="priority-meta">${esc(x.opportunity_type || '情報更新')} · ${esc(x.source_name || '')}</div>
      ${(x.buyer_segments||[]).length ? `<div class="buyers">想定利用者：${x.buyer_segments.map(v=>`<span>${esc(v)}</span>`).join('')}</div>` : ''}
      <a class="official-link" href="${esc(x.url)}" target="_blank" rel="noopener">公式情報を確認 →</a>
    </article>`).join('') : '<div class="empty priority-empty">現在、公式期限を確認できた「受付中」案件はありません。次回収集で自動更新されます。</div>';
}

function render(){
  const q = $('#search').value.trim().toLowerCase();
  const cat = $('#category').value;
  const buyer = $('#buyer').value;
  const minCommercial = Number($('#commercial').value);
  const status = $('#applicationStatus').value;
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

  $('#cards').innerHTML = items.length ? items.map(x => `
    <article class="card">
      <div class="score"><b>${esc(x.commercial_score ?? 0)}</b><small>BUSINESS</small><em>影響 ${esc(x.importance ?? 0)}</em></div>
      <div>
        <div class="signalrow">
          <span class="signal">${esc(x.opportunity_type || '情報更新')}</span>
          <span class="urgent">緊急度 ${esc(x.urgency ?? 0)}</span>
          ${x.priority_tier ? `<span class="priority-badge ${tierClass(x.priority_tier)}">${esc(x.priority_tier)}</span>` : ''}
          ${x.application_status ? `<span class="appstatus ${statusClass(x.application_status)}">${esc(x.application_status)}</span>` : ''}
        </div>
        <a class="title" href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>
        <div class="meta">${esc(x.category)} · ${esc(x.source_name)} · 検出 ${esc(fmt(x.detected_at))}</div>
        ${deadlineBlock(x)}
        ${x.next_deadline && x.next_deadline !== x.participation_deadline ? `<div class="next-deadline">資格者向け次日程：${esc(fmtDate(x.next_deadline))}</div>` : ''}
        ${x.why_it_matters ? `<p class="why">${esc(x.why_it_matters)}</p>` : ''}
        ${x.description ? `<p class="desc">${esc(x.description)}</p>` : ''}
        ${(x.buyer_segments||[]).length ? `<div class="buyers">想定利用者：${x.buyer_segments.map(v=>`<span>${esc(v)}</span>`).join('')}</div>` : ''}
        ${x.status_reason ? `<div class="statusreason">判定根拠：${esc(x.status_reason)}</div>` : ''}
      </div>
      <div class="badge ${esc(x.change_type)}">${changeLabel(x.change_type)}</div>
    </article>`).join('') : '<div class="empty">現在の条件に一致する案件はありません。</div>';
}

function renderGbiz(){
  const gbiz = state.gbiz || {};
  const items = Array.isArray(gbiz.items) ? gbiz.items : [];
  let html = '';
  if (!gbiz.enabled) {
    $('#gbizSignals').innerHTML = '<div class="empty small">gBizINFO法人更新シグナルは現在停止中です。</div>';
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
  $('#gbizSignals').innerHTML = html || '<div class="empty small">直近期間に横浜市内の法人更新シグナルはありません。</div>';
}

function setMetrics(data){
  const open = state.items.filter(x=>x.is_open_now===true);
  $('#openCount').textContent = open.length;
  $('#hotCount').textContent = open.filter(x=>Number(x.commercial_score||0)>=70).length;
  $('#runCount').textContent = data.changes_this_run ?? 0;
  $('#updated').textContent = fmt(data.generated_at);
  const quality = state.quality || {};
  $('#qualityLabel').textContent = quality.health_label || (state.status.sources_ok===state.status.sources_total ? '正常' : '注意');
  $('#qualityLabel').className = `quality-${quality.health || 'unknown'}`;
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
  $('#category').innerHTML += cats.map(c=>`<option>${esc(c)}</option>`).join('');
  $('#buyer').innerHTML += buyers.map(c=>`<option>${esc(c)}</option>`).join('');
  if (data.disclaimer) { $('#notice').hidden=false; $('#notice').textContent=data.disclaimer; }
  renderUrgent();
  renderPriority();
  render();
  renderGbiz();
}).catch(err=>{
  $('#cards').innerHTML='<div class="empty">データの読み込みに失敗しました。次回自動更新後に再度ご確認ください。</div>';
  console.error(err);
});
['search','category','buyer','commercial','applicationStatus'].forEach(id => $('#'+id).addEventListener('input',render));
