const state = {items: []};
const $ = (s) => document.querySelector(s);
const esc = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (iso) => { try { return new Intl.DateTimeFormat('ja-JP',{dateStyle:'short',timeStyle:'short',timeZone:'Asia/Tokyo'}).format(new Date(iso)); } catch { return iso || '—'; } };
const changeLabel = (v) => v==='added'?'新規':v==='updated'?'更新':'基準データ';
function render(){
  const q = $('#search').value.trim().toLowerCase();
  const cat = $('#category').value;
  const buyer = $('#buyer').value;
  const minCommercial = Number($('#commercial').value);
  const items = state.items.filter(x =>
    (!q || `${x.title} ${x.description} ${x.source_name} ${x.opportunity_type} ${(x.buyer_segments||[]).join(' ')}`.toLowerCase().includes(q)) &&
    (!cat || x.category===cat) &&
    (!buyer || (x.buyer_segments||[]).includes(buyer)) &&
    Number(x.commercial_score||0)>=minCommercial
  );
  $('#cards').innerHTML = items.length ? items.map(x => `
    <article class="card">
      <div class="score"><b>${esc(x.commercial_score ?? 0)}</b><small>BUSINESS</small><em>影響 ${esc(x.importance ?? 0)}</em></div>
      <div>
        <div class="signalrow"><span class="signal">${esc(x.opportunity_type || '情報更新')}</span><span class="urgent">緊急度 ${esc(x.urgency ?? 0)}</span></div>
        <a class="title" href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>
        <div class="meta">${esc(x.category)} · ${esc(x.source_name)} · 検出 ${esc(fmt(x.detected_at))}</div>
        ${x.why_it_matters ? `<p class="why">${esc(x.why_it_matters)}</p>` : ''}
        ${x.description ? `<p class="desc">${esc(x.description)}</p>` : ''}
        ${(x.buyer_segments||[]).length ? `<div class="buyers">想定利用者：${x.buyer_segments.map(v=>`<span>${esc(v)}</span>`).join('')}</div>` : ''}
        ${x.matched_keywords?.length ? `<div class="keywords">検出語：${x.matched_keywords.map(esc).join(' / ')}</div>` : ''}
      </div>
      <div class="badge ${esc(x.change_type)}">${changeLabel(x.change_type)}</div>
    </article>`).join('') : '<div class="empty">条件に合う変化はありません。</div>';
}
fetch('./data/latest.json',{cache:'no-store'}).then(r=>r.json()).then(data=>{
  state.items = data.items || [];
  $('#count').textContent = data.count ?? 0;
  $('#runCount').textContent = data.changes_this_run ?? 0;
  $('#hotCount').textContent = state.items.filter(x=>Number(x.commercial_score||0)>=70).length;
  $('#updated').textContent = fmt(data.generated_at);
  const cats = [...new Set(state.items.map(x=>x.category).filter(Boolean))].sort();
  const buyers = [...new Set(state.items.flatMap(x=>x.buyer_segments||[]).filter(Boolean))].sort();
  $('#category').innerHTML += cats.map(c=>`<option>${esc(c)}</option>`).join('');
  $('#buyer').innerHTML += buyers.map(c=>`<option>${esc(c)}</option>`).join('');
  if (data.disclaimer) { $('#notice').hidden=false; $('#notice').textContent=data.disclaimer; }
  render();
}).catch(err=>{ $('#cards').innerHTML='<div class="empty">まだデータがありません。最初の収集を実行してください。</div>'; console.error(err); });
['search','category','buyer','commercial'].forEach(id => $('#'+id).addEventListener('input',render));
