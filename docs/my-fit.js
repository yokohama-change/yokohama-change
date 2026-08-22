(() => {
  const root = document.querySelector('#myFit');
  if (!root) return;

  const result = document.querySelector('#myFitResult');
  const saveButton = document.querySelector('#myFitSave');
  const clearButton = document.querySelector('#myFitClear');
  const STORAGE_KEY = 'yokohama-change-alert-profile-v1';
  let snapshot = {data:{items:[]}, status:{}, quality:{}};

  const esc = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const checked = (name) => [...root.querySelectorAll(`input[name="${name}"]:checked`)].map(x => x.value);

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
    const sourcesHealthy = Number(status.sources_total) > 0 && Number(status.sources_ok) === Number(status.sources_total);
    const checks = quality.checks && typeof quality.checks === 'object' ? Object.values(quality.checks) : [];
    const checksHealthy = checks.length > 0 && checks.every(Boolean);
    const generatedAt = Date.parse(status.generated_at || '');
    const ageMs = Number.isFinite(generatedAt) ? Date.now() - generatedAt : Infinity;
    const freshEnough = ageMs >= -5 * 60 * 1000 && ageMs <= 26 * 3600000;
    return quality.health === 'good' && noProblems && sourcesHealthy && checksHealthy && status.state_preserved === false && freshEnough;
  }

  function formatDeadline(iso){
    try {
      return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tokyo'}).format(new Date(iso));
    } catch { return iso || '—'; }
  }

  function remaining(deadline){
    const ms = deadline - Date.now();
    if (ms <= 0) return '締切済み';
    const hours = Math.ceil(ms / 3600000);
    if (hours < 24) return `残り約${hours}時間`;
    return `残り${Math.ceil(hours / 24)}日`;
  }

  function readProfile(){
    return {segments: checked('fitSegment'), opportunities: checked('fitOpportunity')};
  }

  function saveProfile(profile){
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(profile)); } catch {}
  }

  function restoreProfile(){
    let profile = null;
    try { profile = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); } catch {}
    if (!profile) return;
    for (const input of root.querySelectorAll('input[type="checkbox"]')) {
      const list = input.name === 'fitSegment' ? profile.segments : profile.opportunities;
      input.checked = Array.isArray(list) && list.includes(input.value);
    }
  }

  function eligibleItems(){
    return (Array.isArray(snapshot.data.items) ? snapshot.data.items : []).map(x => ({x, deadline: Date.parse(x.participation_deadline_at || '')})).filter(({x,deadline}) =>
      x.is_open_now === true &&
      x.status_confidence === 'high' &&
      Number(x.commercial_score || 0) >= 70 &&
      Number.isFinite(deadline) &&
      deadline > Date.now()
    );
  }

  function matchItem(item, profile){
    const dimensions = [];
    if (profile.segments.length) dimensions.push(profile.segments.some(v => (item.x.buyer_segments || []).includes(v)));
    if (profile.opportunities.length) dimensions.push(profile.opportunities.includes(item.x.opportunity_type));
    if (!dimensions.length) return null;
    const matched = dimensions.filter(Boolean).length;
    if (!matched) return null;
    const grade = matched === dimensions.length ? 'A' : 'B';
    return {...item, grade, matched, total: dimensions.length};
  }

  function render(){
    const profile = readProfile();
    if (!dataHealthy(snapshot.status, snapshot.quality)) {
      result.innerHTML = '<div class="my-fit-empty my-fit-unhealthy">現在は品質条件を満たしていないため、フィット判定を停止しています。データ正常化後に自動で再開します。</div>';
      return;
    }
    if (!profile.segments.length && !profile.opportunities.length) {
      result.innerHTML = '<div class="my-fit-empty">自社タイプまたは欲しい機会を1つ以上選ぶと、現在の商用70+・受付中案件から一致案件だけを表示します。</div>';
      return;
    }

    const eligible = eligibleItems();
    const matches = eligible.map(item => matchItem(item, profile)).filter(Boolean).sort((a,b) =>
      (a.grade === 'A' ? 0 : 1) - (b.grade === 'A' ? 0 : 1) ||
      Number(b.x.commercial_score||0) - Number(a.x.commercial_score||0) ||
      a.deadline - b.deadline
    );

    const profileLabel = [...profile.segments, ...profile.opportunities].join(' × ');
    if (!matches.length) {
      result.innerHTML = `
        <div class="my-fit-summary"><strong>MY FIT 0件</strong><span>${esc(profileLabel)}</span></div>
        <div class="my-fit-empty">現在の「商用70+・受付中・confidence high」案件には一致がありません。条件を緩めて水増しせず、該当案件が出たときだけ通知対象にする設計です。</div>`;
      return;
    }

    result.innerHTML = `
      <div class="my-fit-summary"><strong>MY FIT ${matches.length}件</strong><span>${esc(profileLabel)}</span></div>
      <div class="my-fit-cards">${matches.slice(0,3).map(({x,deadline,grade,matched,total}) => `
        <article class="my-fit-card">
          <div class="my-fit-grade ${grade === 'B' ? 'b' : ''}">MY FIT<br>${grade}</div>
          <div class="my-fit-main">
            <a class="my-fit-title" href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>
            <div class="my-fit-meta"><span>商用 ${esc(x.commercial_score)}</span><span>${esc(x.opportunity_type || '')}</span><span>一致 ${matched}/${total}</span></div>
          </div>
          <div class="my-fit-deadline"><strong>${esc(remaining(deadline))}</strong><small>${esc(formatDeadline(x.participation_deadline_at))}</small></div>
        </article>`).join('')}</div>`;
  }

  async function load(){
    try {
      const urls = ['./data/latest.json','./data/status.json','./data/quality.json'];
      const responses = await Promise.all(urls.map(url => fetch(url,{cache:'no-store'})));
      if (responses.some(r => !r.ok)) throw new Error('fit data unavailable');
      const [data,status,quality] = await Promise.all(responses.map(r => r.json()));
      snapshot = {data,status,quality};
      render();
    } catch {
      result.innerHTML = '<div class="my-fit-empty my-fit-unhealthy">データを確認できないため、フィット判定を停止しています。</div>';
    }
  }

  saveButton?.addEventListener('click', () => {
    saveProfile(readProfile());
    render();
    saveButton.textContent = '保存しました';
    setTimeout(() => { saveButton.textContent = 'この条件を端末に保存'; }, 1400);
  });
  clearButton?.addEventListener('click', () => {
    for (const input of root.querySelectorAll('input[type="checkbox"]')) input.checked = false;
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
    render();
  });
  root.querySelectorAll('input[type="checkbox"]').forEach(input => input.addEventListener('change', render));

  restoreProfile();
  load();
  setInterval(load, 15 * 60 * 1000);
})();