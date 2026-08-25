(() => {
  const select = document.querySelector('#region');
  const cards = document.querySelector('#cards');
  if (!select || !cards) return;

  let populated = false;

  function items(){
    try {
      return typeof state !== 'undefined' && Array.isArray(state.items) ? state.items : [];
    } catch {
      return [];
    }
  }

  function populate(){
    const rows = items();
    if (!rows.length) return;
    const regions = [...new Set(rows.map(x => String(x.region || '').trim()).filter(Boolean))].sort((a,b) => a.localeCompare(b,'ja'));
    const current = select.value;
    select.innerHTML = '<option value="">すべての地域</option>' + regions.map(region => `<option value="${region.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;')}">${region.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</option>`).join('');
    if (regions.includes(current)) select.value = current;
    populated = true;
  }

  function normalizeHref(value){
    try { return new URL(value, location.href).href; } catch { return value || ''; }
  }

  function apply(){
    if (!populated) populate();
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
