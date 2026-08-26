(() => {
  const $ = (s) => document.querySelector(s);
  const cards = $('#cards');
  const summary = $('#resultSummary');
  let criticalFailure = false;

  function rows(){
    try { return typeof state !== 'undefined' && Array.isArray(state.items) ? state.items : []; }
    catch { return []; }
  }

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
    applyValues({search:'',region:'',category:'',buyer:'',commercial:'0',applicationStatus:'open'});
    const details = $('#advancedFilters');
    if (details) details.open = false;
  }

  function chooseCategory(pattern, fallbackQuery=''){
    resetForQuickAction();
    const category = $('#category');
    const search = $('#search');
    const option = category ? [...category.options].find(o => pattern.test(o.textContent || '')) : null;
    if (option && category) {
      category.value = option.value;
      dispatch(category, 'input');
    } else if (fallbackQuery && search) {
      search.value = fallbackQuery;
      dispatch(search, 'input');
    }
    scrollToId('#find');
  }

  function performSearch(query){
    if (criticalFailure) return;
    resetForQuickAction();
    const search = $('#search');
    if (search) {
      search.value = String(query || '').trim();
      dispatch(search, 'input');
    }
    scrollToId('#find');
  }

  document.querySelectorAll('[data-quick-action]').forEach(control => {
    control.addEventListener('click', () => {
      if (criticalFailure) return;
      const action = control.dataset.quickAction;
      if (action === 'open') {
        resetForQuickAction();
        scrollToId('#find');
      }
      if (action === 'procurement') chooseCategory(/入札|調達/, '入札');
      if (action === 'support') chooseCategory(/補助|助成|支援/, '補助金');
    });
  });

  $('#heroSearchForm')?.addEventListener('submit', event => {
    event.preventDefault();
    performSearch($('#heroSearch')?.value || '');
  });
  document.querySelectorAll('[data-hero-query]').forEach(button => {
    button.addEventListener('click', () => {
      const query = button.dataset.heroQuery || '';
      const heroSearch = $('#heroSearch');
      if (heroSearch) heroSearch.value = query;
      performSearch(query);
    });
  });

  $('#resetFilters')?.addEventListener('click', () => {
    if (criticalFailure) return;
    resetForQuickAction();
    const heroSearch = $('#heroSearch');
    if (heroSearch) heroSearch.value = '';
    updateResultSummary();
  });

  function openItems(){ return rows().filter(x => x?.is_open_now === true); }
  function updatePurposeCounts(){
    const open = openItems();
    if (!open.length && !rows().length) return false;
    const procurement = open.filter(x => x?.category === '入札・調達').length;
    const support = open.filter(x => x?.category === '補助金・支援').length;
    const p = $('#quickProcurementCount');
    const s = $('#quickSupportCount');
    if (p) p.textContent = `${procurement}件`;
    if (s) s.textContent = `${support}件`;
    return true;
  }

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
    const observer = new MutationObserver(() => requestAnimationFrame(() => {
      updateResultSummary();
      updatePurposeCounts();
    }));
    observer.observe(cards, {childList:true, subtree:true, attributes:true, attributeFilter:['hidden']});
  }
  ['search','region','category','buyer','commercial','applicationStatus'].forEach(id => {
    const el = document.getElementById(id);
    el?.addEventListener(id === 'region' ? 'change' : 'input', () => requestAnimationFrame(updateResultSummary));
  });

  function disableInteractiveSearch(){
    document.querySelectorAll('[data-quick-action], #heroSearch, #heroSearchForm button, [data-hero-query], #search, #region, #category, #buyer, #commercial, #applicationStatus, #resetFilters').forEach(el => {
      if ('disabled' in el) el.disabled = true;
      el.setAttribute('aria-disabled','true');
    });
  }

  function showCriticalLoadFailure(){
    if (criticalFailure) return;
    criticalFailure = true;
    disableInteractiveSearch();
    ['#openCount','#hotCount','#qualityLabel','#updated','#quickProcurementCount','#quickSupportCount'].forEach(selector => {
      const node = $(selector); if (node) node.textContent = '—';
    });
    ['#urgentShell','#nextHighValueShell','#preparationShell','#qualityProof'].forEach(selector => {
      const node = $(selector); if (node) node.hidden = true;
    });
    const priority = document.querySelector('.priority-shell');
    if (priority) priority.hidden = true;

    let notice = $('#loadGuardNotice');
    if (!notice) {
      notice = document.createElement('div');
      notice.id = 'loadGuardNotice';
      notice.className = 'notice load-guard-notice';
      const quick = $('#quickStart');
      if (quick) quick.insertAdjacentElement('beforebegin', notice);
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

  function expectedOpenCount(status, quality){
    const candidates = [quality?.open_now, status?.application_status_open_now];
    for (const value of candidates) {
      const count = Number(value);
      if (Number.isInteger(count) && count >= 0) return count;
    }
    return null;
  }

  async function verifyCriticalData(){
    try {
      // latest.json is already loaded by app.js and is comparatively large.
      // Re-fetch only the small health manifests, then compare them with app.js state.
      const [status, quality] = await Promise.all([
        fetchRequiredJson('./data/status.json'),
        fetchRequiredJson('./data/quality.json')
      ]);
      if (!status || typeof status !== 'object' || !quality || typeof quality !== 'object') throw new Error('critical payload invalid');
      const expectedOpen = expectedOpenCount(status, quality);
      if (expectedOpen == null) throw new Error('open count missing');

      // Slow mobile connections can legitimately need several seconds to parse/render latest.json.
      // Poll until the app and quality manifest agree instead of failing on a fixed 1.4s race.
      const deadline = Date.now() + 10000;
      const verifyRendered = () => {
        if (criticalFailure) return;
        const stateRows = rows();
        const actualOpen = stateRows.filter(item => item?.is_open_now === true).length;
        const shown = Number.parseInt($('#openCount')?.textContent || '', 10);
        const priorityCards = document.querySelectorAll('#priorityCards .priority-card').length;
        const stateReady = stateRows.length > 0 || expectedOpen === 0;
        const renderMatches = stateReady && actualOpen === expectedOpen && shown === expectedOpen && (expectedOpen === 0 || priorityCards > 0);
        if (renderMatches) {
          updatePurposeCounts();
          return;
        }
        if (Date.now() >= deadline) {
          showCriticalLoadFailure();
          return;
        }
        setTimeout(verifyRendered, 250);
      };
      verifyRendered();
    } catch {
      showCriticalLoadFailure();
    }
  }

  document.addEventListener('keydown', event => {
    if (event.key === 'Tab') document.documentElement.classList.add('using-keyboard');
  }, {once:true});

  verifyCriticalData();
  let countTries = 0;
  const countTimer = setInterval(() => {
    countTries += 1;
    if (updatePurposeCounts() || countTries > 40) clearInterval(countTimer);
  }, 250);
  setTimeout(updateResultSummary, 700);
})();

// Lightweight progressive motion: visual polish without external libraries.
(() => {
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;
  if (reduceMotion) return;
  document.documentElement.classList.add('motion-enhanced');

  const revealObserver = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      revealObserver.unobserve(entry.target);
    });
  }, {rootMargin:'0px 0px -8% 0px',threshold:.08}) : null;

  const decorate = (root=document) => {
    const selectors = [
      '.purpose-card','.priority-card','.find-shell','.how-steps article',
      '.alert-promo','.trust-section','.urgent-card','.next-high-value'
    ];
    const nodes = root.querySelectorAll?.(selectors.join(',')) || [];
    nodes.forEach((node,index) => {
      if (node.dataset.revealBound === '1') return;
      node.dataset.revealBound = '1';
      node.setAttribute('data-reveal','');
      if (index % 4) node.setAttribute('data-reveal-delay',String(index % 4));
      if (revealObserver) revealObserver.observe(node);
      else node.classList.add('is-visible');
    });
  };
  decorate();

  const dynamicRoots = ['#priorityCards','#cards','#urgentCards','#nextHighValueCard'];
  dynamicRoots.forEach(selector => {
    const root = document.querySelector(selector);
    if (!root) return;
    new MutationObserver(() => decorate(root)).observe(root,{childList:true,subtree:true});
  });

  const header = document.querySelector('.site-header');
  if (header) {
    const onScroll = () => header.classList.toggle('is-scrolled',window.scrollY > 10);
    onScroll();
    window.addEventListener('scroll',onScroll,{passive:true});
  }

  const live = document.querySelector('.hero-live');
  const openCount = document.querySelector('#openCount');
  if (live && openCount) {
    new MutationObserver(() => {
      live.classList.remove('is-counting');
      requestAnimationFrame(() => live.classList.add('is-counting'));
      setTimeout(() => live.classList.remove('is-counting'),360);
    }).observe(openCount,{childList:true,characterData:true,subtree:true});
  }
})();
