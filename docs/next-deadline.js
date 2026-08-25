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
              <span class="preparation-kicker">START PREPARING · YOKOHAMA CHANGE GUIDE</span>
              <h2 id="preparationTitle">もう準備を始めたい案件</h2>
            </div>
            <div class="preparation-count"><b id="preparationCount">—</b><span>準備開始目安</span></div>
          </div>
          <p class="preparation-note">公式締切とは別に、案件種別ごとの標準準備日数から「準備を始める目安」を表示します。入札・調達は原則10日前、補助金・支援は7日前、指定管理・開発系は14日前を目安にしています。</p>
          <div id="preparationCards" class="preparation-cards" aria-live="polite"></div>
          <div class="preparation-legal"><strong>独自目安：</strong>この表示は公式期限・応募要件・専門的助言ではありません。実際の準備期間、必要書類、応募可否は必ず公式情報を確認し、利用者ご自身で判断してください。 <a href="disclaimer.html">免責事項</a></div>`;
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
  const fmtDeadline = (iso) => {
    try {
      return new Intl.DateTimeFormat('ja-JP',{
        month:'numeric', day:'numeric', weekday:'short', hour:'2-digit', minute:'2-digit', timeZone:'Asia/Tokyo'
      }).format(new Date(iso));
    } catch {
      return iso || '—';
    }
  };

  function dataHealthy(status, quality){
    const errorLists = [
      status.errors,
      status.application_status_errors,
      status.application_status_warnings,
      status.support_period_errors,
      status.gbiz_errors,
      quality.errors,
      quality.warnings
    ];
    const noProblems = errorLists.every(v => !Array.isArray(v) || v.length === 0);
    const sourcesKnown = Number.isFinite(Number(status.sources_total)) && Number.isFinite(Number(status.sources_ok));
    const sourcesHealthy = sourcesKnown && Number(status.sources_total) > 0 && Number(status.sources_ok) === Number(status.sources_total);
    const checks = quality.checks && typeof quality.checks === 'object' ? Object.values(quality.checks) : [];
    const checksHealthy = checks.length > 0 && checks.every(Boolean);
    const generatedAt = Date.parse(status.generated_at || '');
    const ageMs = Number.isFinite(generatedAt) ? Date.now() - generatedAt : Infinity;
    const freshEnough = ageMs >= -5 * 60 * 1000 && ageMs <= 26 * 3600000;
    return quality.health === 'good' && noProblems && sourcesHealthy && checksHealthy && status.state_preserved === false && freshEnough;
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

    if (typeof renderUrgent === 'function') {
      try { renderUrgent(); } catch {}
    }

    if (!dataHealthy(status, quality)) {
      shell.hidden = true;
      target.innerHTML = '';
      return;
    }

    const highValue = (Array.isArray(data.items) ? data.items : []).map(x => {
      const deadline = Date.parse(x.participation_deadline_at || '');
      return {x, deadline, ms: deadline - Date.now()};
    }).filter(({x,deadline,ms}) =>
      x.is_open_now === true &&
      x.status_confidence === 'high' &&
      Number(x.commercial_score || 0) >= 70 &&
      x.deadline_time_exact === true &&
      Number.isFinite(deadline) &&
      ms > 0
    );

    const hasUrgent = highValue.some(({ms}) => ms <= 48 * 3600000);
    const next = highValue
      .filter(({ms}) => ms > 48 * 3600000)
      .sort((a,b) => a.deadline - b.deadline || Number(b.x.commercial_score||0) - Number(a.x.commercial_score||0))[0];

    if (hasUrgent || !next) {
      shell.hidden = true;
      target.innerHTML = '';
      return;
    }

    const {x,ms} = next;
    shell.hidden = false;
    target.innerHTML = `
      <div class="next-high-value-countdown">
        <small>NEXT DEADLINE</small>
        <strong>${safe(remainingLabel(ms))}</strong>
        <span>${safe(fmtDeadline(x.participation_deadline_at))} 締切</span>
      </div>
      <div class="next-high-value-main">
        <div class="next-high-value-topline">
          <span>${safe(x.region || '')}</span>
          <span>商用 ${safe(x.commercial_score ?? 0)}</span>
          <span>受付中</span>
          <span>confidence high</span>
        </div>
        <a class="next-high-value-title" href="${safe(x.url)}" target="_blank" rel="noopener">${safe(x.title)}</a>
        <p>48時間アラート前の高商用案件を1件だけ予告しています。公式締切時刻を確認できた案件に限定し、条件を緩めて案件数を増やしません。</p>
      </div>
      <a class="next-high-value-link" href="${safe(x.url)}" target="_blank" rel="noopener">公式情報 →</a>`;
  }

  async function load(){
    try {
      const urls = ['./data/latest.json','./data/status.json','./data/quality.json'];
      const responses = await Promise.all(urls.map(url => fetch(url,{cache:'no-store'})));
      if (responses.some(r => !r.ok)) throw new Error('preview data unavailable');
      const [data,status,quality] = await Promise.all(responses.map(r => r.json()));
      snapshot = {data,status,quality};
      render();
    } catch {
      shell.hidden = true;
      target.innerHTML = '';
    }
  }

  load();
  setInterval(render, 60 * 1000);
  setInterval(load, 15 * 60 * 1000);
})();