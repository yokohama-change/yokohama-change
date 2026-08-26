(() => {
  const select = document.querySelector('#region');
  const cards = document.querySelector('#cards');
  if (!select || !cards) return;

  let populated = false;
  const safe = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const dateLabel = (iso) => { try { return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short',timeZone:'Asia/Tokyo'}).format(new Date(`${iso}T12:00:00+09:00`)); } catch { return iso || '—'; } };
  const dateTimeLabel = (iso) => { try { return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tokyo'}).format(new Date(iso)); } catch { return iso || '—'; } };

  try {
    if (typeof deadlineMs === 'function') {
      const originalDeadlineMs = deadlineMs;
      deadlineMs = (item) => item?.deadline_time_exact === true ? originalDeadlineMs(item) : null;
    }
    if (typeof deadlineBlock === 'function') {
      deadlineBlock = (item) => {
        if (!item?.participation_deadline) return '';
        const label = item.deadline_label || `締切 ${dateLabel(item.participation_deadline)}`;
        const exact = item.deadline_time_exact === true && item.participation_deadline_at ? ` · ${dateTimeLabel(item.participation_deadline_at)}` : '';
        const timeNote = item.deadline_time_exact === true ? '' : ' · 時刻未確認';
        return `<div class="deadline ${item.is_open_now===true?'live':''}"><strong>${safe(label)}</strong><span>参加期限 ${safe(dateLabel(item.participation_deadline))}${safe(exact)}${safe(timeNote)}</span></div>`;
      };
    }
  } catch {}

  function items(){ try { return typeof state !== 'undefined' && Array.isArray(state.items) ? state.items : []; } catch { return []; } }
  function statusData(){ try { return typeof state !== 'undefined' && state.status ? state.status : {}; } catch { return {}; } }

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
    const regions = Array.isArray(status.coverage_regions) ? status.coverage_regions : [];
    if (!regions.length) return;
    let strip = document.querySelector('#coverageStrip');
    if (!strip) {
      strip = document.createElement('details');
      strip.id = 'coverageStrip';
      strip.className = 'coverage-strip';
      strip.setAttribute('aria-label','現在の対応地域');
      const trustArea = document.querySelector('#trustArea');
      if (trustArea) trustArea.appendChild(strip);
      else document.querySelector('main')?.appendChild(strip);
    }
    const health = Number(status.sources_total) > 0 && Number(status.sources_ok) === Number(status.sources_total);
    const healthText = health ? `公式ソース ${status.sources_ok}/${status.sources_total} 正常` : '公式ソースを確認中';
    strip.innerHTML = `
      <summary><strong>現在の対応地域 ${regions.length}地域</strong><span>${safe(healthText)}</span><em>地域を見る</em></summary>
      <div class="coverage-strip-body">${regions.map(region => `<span>${safe(region)}</span>`).join('')}<p>神奈川県内すべてを網羅済みではありません。公式情報を安全に取得できる地域から順次拡大しています。</p></div>`;
  }

  function normalizeHref(value){ try { return new URL(value, location.href).href; } catch { return value || ''; } }

  function apply(){
    if (!populated) populate();
    renderCoverage();
    const region = select.value;
    const rows = items();
    const byUrl = new Map(rows.map(x => [normalizeHref(x.url), x]));
    let visible = 0;
    cards.querySelectorAll('.card').forEach(card => {
      const link = card.querySelector('a.external-link') || card.querySelector('a.title');
      const item = link ? byUrl.get(normalizeHref(link.getAttribute('href'))) : null;
      const itemRegion = String(item?.region || '').trim();
      const show = !region || itemRegion === region;
      card.hidden = !show;
      if (show) visible += 1;
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
  const observer = new MutationObserver(() => { populate(); apply(); });
  observer.observe(cards, {childList:true});
  const timer = setInterval(() => {
    if (items().length) { populate(); apply(); clearInterval(timer); }
  }, 250);
})();
