(() => {
  const select = document.querySelector('#region');
  const cards = document.querySelector('#cards');
  if (!select || !cards) return;

  let populated = false;

  const safe = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const dateLabel = (iso) => {
    try {
      return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short',timeZone:'Asia/Tokyo'}).format(new Date(`${iso}T12:00:00+09:00`));
    } catch { return iso || '—'; }
  };
  const dateTimeLabel = (iso) => {
    try {
      return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tokyo'}).format(new Date(iso));
    } catch { return iso || '—'; }
  };

  /*
   * Safety override: the status engine historically fills date-only deadlines with
   * 23:59. `regionalize_outputs.py` now marks only safely explicit clock times as
   * deadline_time_exact=true. 48H/TODAY must never use a date-only inferred time.
   */
  try {
    if (typeof deadlineMs === 'function') {
      const originalDeadlineMs = deadlineMs;
      deadlineMs = (item) => item?.deadline_time_exact === true ? originalDeadlineMs(item) : null;
    }
    if (typeof deadlineBlock === 'function') {
      deadlineBlock = (item) => {
        if (!item?.participation_deadline) return '';
        const label = item.deadline_label || `締切 ${dateLabel(item.participation_deadline)}`;
        const exact = item.deadline_time_exact === true && item.participation_deadline_at
          ? ` · ${dateTimeLabel(item.participation_deadline_at)}`
          : '';
        const timeNote = item.deadline_time_exact === true ? '' : ' · 時刻未確認';
        return `<div class="deadline ${item.is_open_now===true?'live':''}"><strong>${safe(label)}</strong><span>参加期限 ${safe(dateLabel(item.participation_deadline))}${safe(exact)}${safe(timeNote)}</span></div>`;
      };
    }
  } catch {}

  function items(){
    try {
      return typeof state !== 'undefined' && Array.isArray(state.items) ? state.items : [];
    } catch {
      return [];
    }
  }

  function statusData(){
    try {
      return typeof state !== 'undefined' && state.status ? state.status : {};
    } catch {
      return {};
    }
  }

  function populate(){
    const rows = items();
    if (!rows.length) return;
    const configured = Array.isArray(statusData().coverage_regions) ? statusData().coverage_regions : [];
    const observed = [...new Set(rows.map(x => String(x.region || '').trim()).filter(Boolean))];
    const regions = [...new Set([...configured, ...observed])].sort((a,b) => a.localeCompare(b,'ja'));
    const current = select.value;
    select.innerHTML = '<option value="">すべての地域</option>' + regions.map(region => `<option value="${safe(region)}">${safe(region)}</option>`).join('');
    if (regions.includes(current)) select.value = current;
    populated = true;
  }

  function renderCoverage(){
    const status = statusData();
    const regions = Array.isArray(status.coverage_regions) && status.coverage_regions.length
      ? status.coverage_regions
      : ['神奈川県','横浜市','川崎市','相模原市'];
    let strip = document.querySelector('#coverageStrip');
    if (!strip) {
      strip = document.createElement('aside');
      strip.id = 'coverageStrip';
      strip.setAttribute('aria-label','現在の収集範囲');
      strip.style.cssText = 'max-width:1180px;margin:14px auto 0;padding:11px 16px;border:1px solid #334b69;border-radius:12px;background:#0e1723;color:#b8c7d9;font-size:12px;line-height:1.65';
      const main = document.querySelector('main');
      if (main) main.prepend(strip);
    }
    const health = Number(status.sources_total) > 0 && Number(status.sources_ok) === Number(status.sources_total)
      ? ` · 公式ソース ${safe(status.sources_ok)}/${safe(status.sources_total)} 正常`
      : '';
    strip.innerHTML = `<strong style="color:#e7edf3">無料βの収集範囲：</strong> ${regions.map(safe).join(' / ')}${health}<br><span style="color:#8fa2b5">県内全自治体を網羅済みではありません。公式情報を確認できる地域から順次拡大しています。</span>`;
  }

  function normalizeHref(value){
    try { return new URL(value, location.href).href; } catch { return value || ''; }
  }

  function apply(){
    if (!populated) populate();
    renderCoverage();
    const region = select.value;
    const rows = items();
    const byUrl = new Map(rows.map(x => [normalizeHref(x.url), x]));
    let visible = 0;

    cards.querySelectorAll('.card').forEach(card => {
      const link = card.querySelector('a.title');
      const item = link ? byUrl.get(normalizeHref(link.getAttribute('href'))) : null;
      const itemRegion = String(item?.region || '').trim();
      const show = !region || itemRegion === region;
      card.hidden = !show;
      if (show) visible += 1;

      const meta = card.querySelector('.meta');
      if (meta && itemRegion && !meta.dataset.regionDecorated) {
        meta.textContent = `${itemRegion} · ${meta.textContent}`;
        meta.dataset.regionDecorated = '1';
      }
    });

    let empty = document.querySelector('#regionEmpty');
    if (!empty) {
      empty = document.createElement('div');
      empty.id = 'regionEmpty';
      empty.className = 'empty';
      cards.after(empty);
    }
    empty.hidden = !region || visible > 0;
    empty.textContent = region && visible === 0 ? `${region}で現在の条件に一致する案件はありません。` : '';
  }

  select.addEventListener('change', apply);
  const observer = new MutationObserver(() => {
    populate();
    apply();
  });
  observer.observe(cards, {childList:true});

  const timer = setInterval(() => {
    if (items().length) {
      populate();
      apply();
      clearInterval(timer);
    }
  }, 250);
})();
