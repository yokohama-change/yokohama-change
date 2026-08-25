(() => {
  function mountPreparationFeature(){
    if (!document.querySelector('link[data-preparation-style]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'preparation.css';
      link.dataset.preparationStyle = '1';
      document.head.appendChild(link);
    }

    if (!document.querySelector('#preparationShell')) {
      const priority = document.querySelector('.priority-shell');
      if (priority) {
        const section = document.createElement('section');
        section.id = 'preparationShell';
        section.className = 'preparation-shell';
        section.hidden = true;
        section.setAttribute('aria-labelledby','preparationTitle');
        section.innerHTML = `
          <div class="preparation-head">
            <div>
              <span class="preparation-kicker">応募準備の目安</span>
              <h2 id="preparationTitle">そろそろ準備を始めたい案件</h2>
            </div>
            <div class="preparation-count"><b id="preparationCount">—</b><span>件</span></div>
          </div>
          <p class="preparation-note">公式の締切とは別に、案件の種類ごとの標準的な準備日数から「準備を始める目安」を表示しています。</p>
          <div id="preparationCards" class="preparation-cards" aria-live="polite"></div>
          <div class="preparation-legal"><strong>参考情報：</strong>準備開始日はYOKOHAMA CHANGE独自の目安です。必要書類・応募条件・実際の準備期間は必ず公式情報をご確認ください。 <a href="disclaimer.html">免責事項</a></div>`;
        priority.insertAdjacentElement('afterend', section);
      }
    }

    if (!document.querySelector('script[data-preparation-script]') && document.querySelector('#preparationShell')) {
      const script = document.createElement('script');
      script.src = 'preparation.js';
      script.dataset.preparationScript = '1';
      document.body.appendChild(script);
    }
  }

  mountPreparationFeature();

  const shell = document.querySelector('#nextHighValueShell');
  const target = document.querySelector('#nextHighValueCard');
  if (!shell || !target) return;
  let snapshot = {data:{items:[]}, status:{}, quality:{}};

  const safe = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const detailUrl = (x) => {
    const id = String(x?.id || '').trim();
    return /^[A-Za-z0-9_-]{6,80}$/.test(id) && x?.status_confidence === 'high' && x?.participation_deadline_at ? `opportunities/${encodeURIComponent(id)}.html` : '';
  };
  const fmtDeadline = (iso) => { try { return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tokyo'}).format(new Date(iso)); } catch { return iso || '—'; } };

  function dataHealthy(status, quality){
    const errorLists = [status.errors,status.application_status_errors,status.application_status_warnings,status.support_period_errors,status.gbiz_errors,quality.errors,quality.warnings];
    const noProblems = errorLists.every(v => !Array.isArray(v) || v.length === 0);
    const sourcesHealthy = Number(status.sources_total) > 0 && Number(status.sources_ok) === Number(status.sources_total);
    const checks = quality.checks && typeof quality.checks === 'object' ? Object.values(quality.checks) : [];
    const checksHealthy = checks.length > 0 && checks.every(Boolean);
    const generatedAt = Date.parse(status.generated_at || '');
    const ageMs = Number.isFinite(generatedAt) ? Date.now() - generatedAt : Infinity;
    return quality.health === 'good' && noProblems && sourcesHealthy && checksHealthy && status.state_preserved === false && ageMs >= -300000 && ageMs <= 26 * 3600000;
  }

  function remainingLabel(ms){
    const totalHours = Math.max(0, Math.floor(ms / 3600000));
    const days = Math.floor(totalHours / 24);
    const hours = totalHours % 24;
    if (days >= 1) return hours ? `あと${days}日${hours}時間` : `あと${days}日`;
    if (totalHours >= 1) return `あと${totalHours}時間`;
    return 'あと1時間未満';
  }

  function render(){
    const {data,status,quality} = snapshot;
    if (typeof renderUrgent === 'function') { try { renderUrgent(); } catch {} }
    if (!dataHealthy(status, quality)) { shell.hidden = true; target.innerHTML = ''; return; }

    const highValue = (Array.isArray(data.items) ? data.items : []).map(x => {
      const deadline = Date.parse(x.participation_deadline_at || '');
      return {x, deadline, ms: deadline - Date.now()};
    }).filter(({x,deadline,ms}) =>
      x.is_open_now === true && x.status_confidence === 'high' && Number(x.commercial_score || 0) >= 70 && x.deadline_time_exact === true && Number.isFinite(deadline) && ms > 0
    );

    const hasUrgent = highValue.some(({ms}) => ms <= 48 * 3600000);
    const next = highValue.filter(({ms}) => ms > 48 * 3600000).sort((a,b) => a.deadline-b.deadline || Number(b.x.commercial_score||0)-Number(a.x.commercial_score||0))[0];
    if (hasUrgent || !next) { shell.hidden = true; target.innerHTML = ''; return; }

    const {x,ms} = next;
    const detail = detailUrl(x);
    shell.hidden = false;
    target.innerHTML = `
      <div class="next-high-value-countdown">
        <small>次の締切</small>
        <strong>${safe(remainingLabel(ms))}</strong>
        <span>${safe(fmtDeadline(x.participation_deadline_at))} 締切</span>
      </div>
      <div class="next-high-value-main">
        <div class="next-high-value-topline">
          <span>${safe(x.region || '')}</span>
          <span>見る優先度 ${safe(x.commercial_score ?? 0)}</span>
          <span>受付中</span>
        </div>
        <a class="next-high-value-title" href="${safe(detail || x.url)}" ${detail ? '' : 'target="_blank" rel="noopener"'}>${safe(x.title)}</a>
        <p>締切が近づく前に、優先して確認したい案件を1件だけ表示しています。</p>
      </div>
      <div class="card-actions">${detail ? `<a class="details-link" href="${safe(detail)}">かんたん詳細</a>` : ''}<a class="external-link" href="${safe(x.url)}" target="_blank" rel="noopener">自治体公式サイト ↗</a></div>`;
  }

  async function load(){
    try {
      const urls = ['./data/latest.json','./data/status.json','./data/quality.json'];
      const responses = await Promise.all(urls.map(url => fetch(url,{cache:'no-store'})));
      if (responses.some(r => !r.ok)) throw new Error('preview data unavailable');
      const [data,status,quality] = await Promise.all(responses.map(r => r.json()));
      snapshot = {data,status,quality};
      render();
    } catch { shell.hidden = true; target.innerHTML = ''; }
  }

  load();
  setInterval(render, 60 * 1000);
  setInterval(load, 15 * 60 * 1000);
})();
