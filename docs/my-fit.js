(() => {
  const root = document.querySelector('#myFit');
  if (!root) return;

  const result = document.querySelector('#myFitResult');
  const showButton = document.querySelector('#myFitShowResults');
  const saveButton = document.querySelector('#myFitSave');
  const clearButton = document.querySelector('#myFitClear');
  const saveStatus = document.querySelector('#myFitSaveStatus');
  const STORAGE_KEY = 'yokohama-change-alert-profile-v2';
  const LEGACY_STORAGE_KEY = 'yokohama-change-alert-profile-v1';
  let snapshot = {data:{items:[]}, status:{}, quality:{}};
  let profileRestored = false;

  const esc = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const checked = (name) => [...root.querySelectorAll(`input[name="${name}"]:checked`)].map(x => x.value);

  function dataHealthy(status, quality){
    const errorLists = [status.errors,status.application_status_errors,status.application_status_warnings,status.support_period_errors,status.gbiz_errors,quality.errors,quality.warnings];
    const noProblems = errorLists.every(v => !Array.isArray(v) || v.length === 0);
    const sourcesHealthy = Number(status.sources_total) > 0 && Number(status.sources_ok) === Number(status.sources_total);
    const checks = quality.checks && typeof quality.checks === 'object' ? Object.values(quality.checks) : [];
    const checksHealthy = checks.length > 0 && checks.every(Boolean);
    const generatedAt = Date.parse(status.generated_at || '');
    const ageMs = Number.isFinite(generatedAt) ? Date.now() - generatedAt : Infinity;
    const freshEnough = ageMs >= -5 * 60 * 1000 && ageMs <= 26 * 3600000;
    return quality.health === 'good' && noProblems && sourcesHealthy && checksHealthy && status.state_preserved === false && freshEnough;
  }

  function detailUrl(item){
    const id = String(item?.id || '').trim();
    return /^[A-Za-z0-9_-]{6,80}$/.test(id) && item?.status_confidence === 'high' && item?.participation_deadline_at
      ? `opportunities/${encodeURIComponent(id)}.html` : '';
  }

  function formatDeadline(item){
    try {
      if (item.deadline_time_exact === true && item.participation_deadline_at) {
        return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tokyo'}).format(new Date(item.participation_deadline_at));
      }
      return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short',timeZone:'Asia/Tokyo'}).format(new Date(`${item.participation_deadline}T12:00:00+09:00`)) + '・時刻未確認';
    } catch { return item.participation_deadline || '—'; }
  }

  function remaining(item, deadline){
    if (item.deadline_time_exact !== true) {
      const days = Number(item.days_left);
      return Number.isFinite(days) ? `残り${Math.max(0, days)}日` : '締切日を確認';
    }
    const ms = deadline - Date.now();
    if (ms <= 0) return '締切済み';
    const hours = Math.ceil(ms / 3600000);
    if (hours < 24) return `残り約${hours}時間`;
    return `残り${Math.ceil(hours / 24)}日`;
  }

  function readProfile(){
    return {segments:checked('fitSegment'), opportunities:checked('fitOpportunity'), regions:checked('fitRegion')};
  }

  function saveProfile(profile){
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
      localStorage.removeItem(LEGACY_STORAGE_KEY);
    } catch {}
  }

  function loadStoredProfile(){
    try {
      const current = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (current) return current;
      const legacy = JSON.parse(localStorage.getItem(LEGACY_STORAGE_KEY) || 'null');
      if (legacy) return {...legacy, regions:[]};
    } catch {}
    return null;
  }

  function restoreProfile(){
    if (profileRestored) return false;
    const profile = loadStoredProfile();
    profileRestored = true;
    if (!profile) return false;
    for (const input of root.querySelectorAll('input[type="checkbox"]')) {
      let list = [];
      if (input.name === 'fitSegment') list = profile.segments;
      if (input.name === 'fitOpportunity') list = profile.opportunities;
      if (input.name === 'fitRegion') list = profile.regions;
      input.checked = Array.isArray(list) && list.includes(input.value);
    }
    return true;
  }

  function bindInput(input){
    if (input.dataset.fitBound) return;
    input.dataset.fitBound = '1';
    input.addEventListener('change', render);
  }

  function buildRegionOptions(){
    const form = root.querySelector('.my-fit-form');
    if (!form) return;
    let field = root.querySelector('#myFitRegionField');
    if (!field) {
      field = document.createElement('fieldset');
      field.id = 'myFitRegionField';
      field.className = 'my-fit-field';
      field.innerHTML = '<legend>③ 希望地域（任意）</legend><p class="novice-note">選ばなければ対応地域全体から探します。</p><div id="myFitRegionOptions" class="my-fit-options"></div>';
      form.appendChild(field);
    }
    const target = root.querySelector('#myFitRegionOptions');
    if (!target) return;
    const configured = Array.isArray(snapshot.status.coverage_regions) ? snapshot.status.coverage_regions : [];
    const observed = [...new Set((snapshot.data.items || []).map(x => String(x.region || '').trim()).filter(Boolean))];
    const regions = [...new Set([...configured, ...observed])];
    const selected = new Set(checked('fitRegion'));
    target.innerHTML = regions.map(region => `<label class="my-fit-choice"><input type="checkbox" name="fitRegion" value="${esc(region)}" ${selected.has(region)?'checked':''}><span>${esc(region)}</span></label>`).join('');
    target.querySelectorAll('input').forEach(bindInput);
  }

  function eligibleItems(){
    return (Array.isArray(snapshot.data.items) ? snapshot.data.items : []).map(x => ({x,deadline:Date.parse(x.participation_deadline_at || '')})).filter(({x,deadline}) =>
      x.is_open_now === true && x.status_confidence === 'high' && Number(x.commercial_score || 0) >= 70 && Number.isFinite(deadline) && deadline > Date.now()
    );
  }

  function matchItem(item, profile){
    const dimensions = [];
    if (profile.segments.length) dimensions.push(profile.segments.some(v => (item.x.buyer_segments || []).includes(v)));
    if (profile.opportunities.length) dimensions.push(profile.opportunities.includes(item.x.opportunity_type));
    if (profile.regions.length) dimensions.push(profile.regions.includes(item.x.region));
    if (!dimensions.length) return null;
    const matched = dimensions.filter(Boolean).length;
    if (!matched) return null;
    const grade = matched === dimensions.length ? 'A' : 'B';
    return {...item,grade,matched,total:dimensions.length};
  }

  function render(){
    const profile = readProfile();
    if (!dataHealthy(snapshot.status, snapshot.quality)) {
      result.innerHTML = '<div class="my-fit-empty my-fit-unhealthy">現在データを確認中のため、絞り込みを一時停止しています。時間をおいてもう一度お試しください。</div>';
      return;
    }
    if (!profile.segments.length && !profile.opportunities.length && !profile.regions.length) {
      result.innerHTML = '<div class="my-fit-empty">上の条件を1つ以上選ぶと、一致する案件をここに表示します。</div>';
      return;
    }

    const matches = eligibleItems().map(item => matchItem(item, profile)).filter(Boolean).sort((a,b) =>
      (a.grade === 'A' ? 0 : 1) - (b.grade === 'A' ? 0 : 1) || Number(b.x.commercial_score||0)-Number(a.x.commercial_score||0) || a.deadline-b.deadline
    );
    const profileLabel = [...profile.segments,...profile.opportunities,...profile.regions].join(' / ');
    if (!matches.length) {
      result.innerHTML = `<div class="my-fit-summary"><strong>一致する案件 0件</strong><span>${esc(profileLabel)}</span></div><div class="my-fit-empty">現在の優先案件には一致するものがありません。条件を減らすか、時間をおいてまたご確認ください。</div>`;
      return;
    }

    result.innerHTML = `
      <div class="my-fit-summary"><strong>一致する案件 ${matches.length}件</strong><span>${esc(profileLabel)}</span></div>
      <div class="my-fit-cards">${matches.slice(0,5).map(({x,deadline,grade,matched,total}) => {
        const detail = detailUrl(x);
        const matchLabel = grade === 'A' ? 'よく一致' : '一部一致';
        return `<article class="my-fit-card">
          <div class="my-fit-grade ${grade === 'B' ? 'b' : ''}">${matchLabel}<small>MY FIT ${grade}</small></div>
          <div class="my-fit-main">
            <a class="my-fit-title" href="${esc(detail || x.url)}" ${detail ? '' : 'target="_blank" rel="noopener"'}>${esc(x.title)}</a>
            <div class="my-fit-meta"><span>${esc(x.region || '地域未設定')}</span><span>見る優先度 ${esc(x.commercial_score)}</span><span>${esc(x.opportunity_type || '')}</span><span>条件 ${matched}/${total} 一致</span></div>
            <div class="card-actions">${detail ? `<a class="details-link" href="${esc(detail)}">かんたん詳細</a>` : ''}<a class="external-link" href="${esc(x.url)}" target="_blank" rel="noopener">自治体公式サイト ↗</a></div>
          </div>
          <div class="my-fit-deadline"><strong>${esc(remaining(x,deadline))}</strong><small>${esc(formatDeadline(x))}</small></div>
        </article>`;
      }).join('')}</div>`;
  }

  function showResults(){
    render();
    result?.focus({preventScroll:true});
    result?.scrollIntoView({
      behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'start'
    });
  }

  async function load(){
    try {
      const urls = ['./data/latest.json','./data/status.json','./data/quality.json'];
      const responses = await Promise.all(urls.map(url => fetch(url,{cache:'no-store'})));
      if (responses.some(r => !r.ok)) throw new Error('fit data unavailable');
      const [data,status,quality] = await Promise.all(responses.map(r => r.json()));
      snapshot = {data,status,quality};
      buildRegionOptions();
      const restored = restoreProfile();
      root.querySelectorAll('input[type="checkbox"]').forEach(bindInput);
      render();
      if (restored && saveStatus) saveStatus.textContent = '前回保存した条件を復元しました。';
    } catch {
      result.innerHTML = '<div class="my-fit-empty my-fit-unhealthy">案件データを確認できません。時間をおいてもう一度お試しください。</div>';
    }
  }

  showButton?.addEventListener('click', showResults);
  saveButton?.addEventListener('click', () => {
    saveProfile(readProfile());
    render();
    const original = '条件を保存（任意）';
    saveButton.textContent = '保存しました ✓';
    if (saveStatus) saveStatus.textContent = 'この端末に条件を保存しました。';
    setTimeout(() => { saveButton.textContent = original; }, 1400);
  });
  clearButton?.addEventListener('click', () => {
    for (const input of root.querySelectorAll('input[type="checkbox"]')) input.checked = false;
    try { localStorage.removeItem(STORAGE_KEY); localStorage.removeItem(LEGACY_STORAGE_KEY); } catch {}
    if (saveStatus) saveStatus.textContent = '選択と保存済み条件を消しました。';
    render();
  });
  root.querySelectorAll('input[type="checkbox"]').forEach(bindInput);

  load();
  setInterval(load, 15 * 60 * 1000);
})();
