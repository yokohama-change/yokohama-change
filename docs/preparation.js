(() => {
  const shell = document.querySelector('#preparationShell');
  const target = document.querySelector('#preparationCards');
  const count = document.querySelector('#preparationCount');
  if (!shell || !target || !count) return;

  const safe = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmtDate = (iso) => {
    try {
      return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short',timeZone:'Asia/Tokyo'}).format(new Date(`${iso}T12:00:00+09:00`));
    } catch { return iso || '—'; }
  };

  function healthy(){
    try { return typeof alertDataHealthy === 'function' && alertDataHealthy(); }
    catch { return false; }
  }

  function rows(){
    try {
      if (typeof state === 'undefined' || !Array.isArray(state.items)) return [];
      return state.items.filter(x =>
        x.is_open_now === true &&
        x.status_confidence === 'high' &&
        x.preparation_status === '準備開始推奨' &&
        Number(x.commercial_score || 0) >= 50
      ).sort((a,b) =>
        Number(b.commercial_score || 0) - Number(a.commercial_score || 0) ||
        Number(a.days_left ?? 9999) - Number(b.days_left ?? 9999)
      );
    } catch { return []; }
  }

  function render(){
    if (!healthy()) {
      shell.hidden = true;
      target.innerHTML = '';
      return false;
    }
    const items = rows();
    if (!items.length) {
      shell.hidden = true;
      target.innerHTML = '';
      return false;
    }

    shell.hidden = false;
    count.textContent = items.length;
    target.innerHTML = items.slice(0,4).map(x => {
      const lead = Number(x.preparation_days || 0);
      const start = x.preparation_start_date ? fmtDate(x.preparation_start_date) : '—';
      const deadline = x.participation_deadline ? fmtDate(x.participation_deadline) : '—';
      return `
        <article class="preparation-card">
          <div>
            <a class="preparation-title" href="${safe(x.url)}" target="_blank" rel="noopener">${safe(x.title)}</a>
            <div class="preparation-meta">
              <span>${safe(x.region || '')}</span>
              <span>商用 ${safe(x.commercial_score || 0)}</span>
              <span>${safe(x.opportunity_type || '')}</span>
              <span class="prep-guide">標準準備目安 ${safe(lead)}日前</span>
            </div>
          </div>
          <div class="preparation-deadline">
            <strong>${safe(start)}から準備目安</strong>
            <small>公式締切 ${safe(deadline)}${x.deadline_time_exact === true && x.participation_deadline_at ? '・時刻確認済' : '・時刻未確認'}</small>
          </div>
        </article>`;
    }).join('');
    return true;
  }

  let tries = 0;
  const timer = setInterval(() => {
    tries += 1;
    const done = render();
    if (done || tries > 40) clearInterval(timer);
  }, 250);

  setInterval(render, 15 * 60 * 1000);
})();
