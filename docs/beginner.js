(() => {
  const $ = (s) => document.querySelector(s);
  const cards = $('#cards');
  const summary = $('#resultSummary');
  let criticalFailure = false;

  function scrollToId(id){
    const el = document.querySelector(id);
    if (el) el.scrollIntoView({behavior:'smooth', block:'start'});
  }

  function dispatch(el, type='input'){
    if (!el) return;
    el.dispatchEvent(new Event(type, {bubbles:true}));
  }

  function applyValues(values){
    Object.entries(values).forEach(([id,value]) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.value = value;
      dispatch(el, id === 'region' ? 'change' : 'input');
    });
  }

  function resetForQuickAction(){
    applyValues({
      search: '',
      region: '',
      category: '',
      buyer: '',
      commercial: '0',
      applicationStatus: 'open'
    });
    const details = $('#advancedFilters');
    if (details) details.open = false;
  }

  function chooseSupport(){
    resetForQuickAction();
    const category = $('#category');
    const search = $('#search');
    const option = category ? [...category.options].find(o => /補助|助成|支援/.test(o.textContent || '')) : null;
    if (option && category) {
      category.value = option.value;
      dispatch(category, 'input');
    } else if (search) {
      search.value = '補助金';
      dispatch(search, 'input');
    }
    scrollToId('#exploreTitle');
  }

  document.querySelectorAll('[data-quick-action]').forEach(button => {
    button.addEventListener('click', () => {
      if (criticalFailure) return;
      const action = button.dataset.quickAction;
      if (action === 'open') {
        resetForQuickAction();
        scrollToId('#priorityTitle');
      }
      if (action === 'support') chooseSupport();
    });
  });

  $('#resetFilters')?.addEventListener('click', () => {
    if (criticalFailure) return;
    resetForQuickAction();
    updateResultSummary();
  });

  function updateResultSummary(){
    if (!summary || !cards || criticalFailure) return;
    const allCards = [...cards.querySelectorAll('.card')];
    const visible = allCards.filter(card => !card.hidden);
    const empty = cards.querySelector('.empty');
    if (!allCards.length) {
      summary.textContent = empty ? '現在の条件に一致する案件はありません。' : '案件を読み込んでいます…';
      return;
    }
    summary.innerHTML = `<strong>${visible.length}件</strong> 表示中`;
  }

  if (cards) {
    const observer = new MutationObserver(() => requestAnimationFrame(updateResultSummary));
    observer.observe(cards, {childList:true, subtree:true, attributes:true, attributeFilter:['hidden']});
  }
  ['search','region','category','buyer','commercial','applicationStatus'].forEach(id => {
    const el = document.getElementById(id);
    el?.addEventListener(id === 'region' ? 'change' : 'input', () => requestAnimationFrame(updateResultSummary));
  });

  function disableInteractiveSearch(){
    document.querySelectorAll('#quickStart button, #search, #region, #category, #buyer, #commercial, #applicationStatus, #resetFilters').forEach(el => {
      el.disabled = true;
      el.setAttribute('aria-disabled','true');
    });
  }

  function showCriticalLoadFailure(){
    if (criticalFailure) return;
    criticalFailure = true;
    disableInteractiveSearch();

    ['#openCount','#hotCount','#qualityLabel','#updated'].forEach(selector => {
      const node = $(selector);
      if (node) node.textContent = '—';
    });
    ['#urgentShell','#nextHighValueShell','#preparationShell','#qualityProof'].forEach(selector => {
      const node = $(selector);
      if (node) node.hidden = true;
    });
    const priority = document.querySelector('.priority-shell');
    if (priority) priority.hidden = true;

    let notice = $('#loadGuardNotice');
    if (!notice) {
      notice = document.createElement('div');
      notice.id = 'loadGuardNotice';
      notice.className = 'notice';
      const quick = $('#quickStart');
      if (quick) quick.insertAdjacentElement('afterend', notice);
      else document.querySelector('main')?.prepend(notice);
    }
    notice.hidden = false;
    notice.innerHTML = '<strong>案件データを正しく読み込めませんでした。</strong><br>「0件」という意味ではありません。通信状況をご確認のうえ、もう一度読み込んでください。 <button id="reloadData" class="reset-filters" type="button">再読み込み</button>';
    $('#reloadData')?.addEventListener('click', () => location.reload());

    if (cards) cards.innerHTML = '<div class="empty">現在は案件一覧を表示していません。再読み込みしてご確認ください。</div>';
    if (summary) summary.textContent = 'データ読込エラー';
  }

  async function fetchRequiredJson(url){
    const response = await fetch(url, {cache:'no-store'});
    if (!response.ok) throw new Error(`${url} HTTP ${response.status}`);
    return response.json();
  }

  async function verifyCriticalData(){
    try {
      const [data,status,quality] = await Promise.all([
        fetchRequiredJson('./data/latest.json'),
        fetchRequiredJson('./data/status.json'),
        fetchRequiredJson('./data/quality.json')
      ]);
      if (!data || !Array.isArray(data.items) || !status || typeof status !== 'object' || !quality || typeof quality !== 'object') {
        throw new Error('critical payload invalid');
      }
      const expectedOpen = data.items.filter(item => item?.is_open_now === true).length;
      setTimeout(() => {
        if (criticalFailure) return;
        const shown = Number.parseInt($('#openCount')?.textContent || '', 10);
        const priorityCards = document.querySelectorAll('#priorityCards .priority-card').length;
        const renderMismatch = !Number.isFinite(shown) || shown !== expectedOpen || (expectedOpen > 0 && priorityCards === 0);
        if (renderMismatch) showCriticalLoadFailure();
      }, 1400);
    } catch {
      showCriticalLoadFailure();
    }
  }

  // Make keyboard focus obvious for people who do not use a mouse often.
  document.addEventListener('keydown', event => {
    if (event.key === 'Tab') document.documentElement.classList.add('using-keyboard');
  }, {once:true});

  verifyCriticalData();
  setTimeout(updateResultSummary, 700);
})();
