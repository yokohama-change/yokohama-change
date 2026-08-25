(() => {
  const $ = (s) => document.querySelector(s);
  const cards = $('#cards');
  const summary = $('#resultSummary');

  function scrollToId(id){
    const el = document.querySelector(id);
    if (el) el.scrollIntoView({behavior:'smooth', block:'start'});
  }

  function dispatch(el, type='input'){
    if (!el) return;
    el.dispatchEvent(new Event(type, {bubbles:true}));
  }

  function setOpenOnly(){
    const status = $('#applicationStatus');
    if (status) {
      status.value = 'open';
      dispatch(status, 'input');
    }
  }

  function chooseSupport(){
    setOpenOnly();
    const category = $('#category');
    const search = $('#search');
    if (category) {
      const option = [...category.options].find(o => /補助|助成|支援/.test(o.textContent || ''));
      if (option) {
        category.value = option.value;
        dispatch(category, 'input');
        if (search) search.value = '';
      } else if (search) {
        search.value = '補助金';
        dispatch(search, 'input');
      }
    }
    scrollToId('#exploreTitle');
  }

  document.querySelectorAll('[data-quick-action]').forEach(button => {
    button.addEventListener('click', () => {
      const action = button.dataset.quickAction;
      if (action === 'open') {
        setOpenOnly();
        scrollToId('#priorityTitle');
      }
      if (action === 'support') chooseSupport();
    });
  });

  $('#resetFilters')?.addEventListener('click', () => {
    const values = {
      search: '', region: '', category: '', buyer: '', commercial: '0', applicationStatus: 'open'
    };
    Object.entries(values).forEach(([id,value]) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.value = value;
      dispatch(el, id === 'region' ? 'change' : 'input');
    });
    const details = $('#advancedFilters');
    if (details) details.open = false;
    updateResultSummary();
  });

  function updateResultSummary(){
    if (!summary || !cards) return;
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

  // Make keyboard focus obvious for people who do not use a mouse often.
  document.addEventListener('keydown', event => {
    if (event.key === 'Tab') document.documentElement.classList.add('using-keyboard');
  }, {once:true});

  setTimeout(updateResultSummary, 700);
})();
