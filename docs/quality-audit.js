(() => {
  const main = document.querySelector('main');
  if (!main) return;

  let shell = document.querySelector('#qualityAudit');
  if (!shell) {
    shell = document.createElement('details');
    shell.id = 'qualityAudit';
    shell.className = 'quality-audit';
    shell.hidden = true;
    shell.innerHTML = `
      <summary>
        <span class="quality-audit-summary-label">データの自動チェック</span>
        <strong id="qualityAuditState">確認中</strong>
        <span class="quality-audit-summary-hint">詳しく見る</span>
      </summary>
      <div class="quality-audit-body">
        <p id="qualityAuditCopy">品質データを確認しています。</p>
        <div class="quality-audit-metrics">
          <div><b id="qualityAuditSources">—</b><span>公式ソース</span></div>
          <div><b id="qualityAuditOpen">—</b><span>受付中案件</span></div>
          <div><b id="qualityAuditExplainable">—</b><span>根拠を説明可能</span></div>
          <div><b id="qualityAuditExactTime">—</b><span>締切時刻まで確認</span></div>
          <div><b id="qualityAuditChecks">—</b><span>品質チェック</span></div>
          <div><b id="qualityAuditDuplicates">—</b><span>重複URL</span></div>
        </div>
        <div id="qualityAuditChips" class="quality-audit-chips" aria-live="polite"></div>
        <div class="quality-audit-foot">
          <span>最終監査 <b id="qualityAuditUpdated">—</b> · 自動検査であり、公式情報を保証するものではありません。正確性・最新性は必ず公式ページでご確認ください。</span>
          <span class="quality-audit-links"><a href="data/quality.json">品質データ</a><a href="data/explainability.json">判定根拠データ</a></span>
        </div>
      </div>`;
    const trustArea = document.querySelector('#trustArea');
    if (trustArea) trustArea.appendChild(shell);
    else main.appendChild(shell);
  }

  const esc = (value = '') => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (iso) => { try { return new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tokyo'}).format(new Date(iso)); } catch { return iso || '—'; } };
  const put = (id, value) => { const node = document.querySelector(id); if (node) node.textContent = value; };

  const labels = {
    source_inventory_healthy:'公式ソース正常', official_provenance_consistent:'公式出典一致', open_deadlines_not_past:'締切超過を除外', deadline_fields_consistent:'締切データ一致', employment_excluded:'求人情報を除外', counts_consistent:'件数一致', open_feed_ids_consistent:'公開案件一致', high_value_counts_consistent:'優先案件数一致', unique_ids:'重複IDなし', unique_public_urls:'重複URLなし', all_open_items_explainable:'受付中の根拠あり', explicit_participation_reason_required:'参加期限を明示確認'
  };

  async function getJson(url) {
    const response = await fetch(url, {cache:'no-store'});
    if (!response.ok) throw new Error(`${url} HTTP ${response.status}`);
    return response.json();
  }

  async function load(){
    try {
      const [quality, explainability] = await Promise.all([getJson('data/quality.json'),getJson('data/explainability.json')]);
      const inventory = quality.source_inventory || {};
      const dedupe = quality.dedupe || {};
      const qChecks = quality.checks && typeof quality.checks === 'object' ? quality.checks : {};
      const eChecks = explainability.checks && typeof explainability.checks === 'object' ? explainability.checks : {};
      const entries = [...Object.entries(qChecks), ...Object.entries(eChecks)];
      const passed = entries.filter(([,ok]) => ok === true).length;
      const total = entries.length;
      const openNow = Number(quality.open_now ?? explainability.open_now ?? 0);
      const explainable = Number(explainability.explainable_open_now ?? -1);
      const exact = Number(explainability.deadline_time_exact ?? -1);
      const good = quality.health === 'good' && explainability.health === 'good' && explainable === openNow && total > 0 && passed === total;

      shell.hidden = false;
      shell.classList.toggle('is-good', good);
      shell.classList.toggle('is-warning', !good);
      put('#qualityAuditState', good ? '正常' : '要確認');
      put('#qualityAuditSources', `${inventory.nonempty_sources ?? '—'}/${inventory.configured_sources ?? '—'}`);
      put('#qualityAuditOpen', openNow);
      put('#qualityAuditExplainable', explainable >= 0 ? `${explainable}/${openNow}` : '—');
      put('#qualityAuditExactTime', exact >= 0 ? `${exact}/${openNow}` : '—');
      put('#qualityAuditChecks', `${passed}/${total}`);
      put('#qualityAuditDuplicates', dedupe.remaining_duplicate_urls ?? '—');
      put('#qualityAuditUpdated', fmt(explainability.checked_at || quality.checked_at));
      const copy = document.querySelector('#qualityAuditCopy');
      if (copy) copy.textContent = good ? '公式ソース、締切、重複、受付中とした根拠まで、公開前に自動確認しています。' : '品質確認に注意項目があります。詳細データをご確認ください。';
      const chips = document.querySelector('#qualityAuditChips');
      if (chips) chips.innerHTML = entries.map(([key,ok]) => `<span class="quality-audit-chip ${ok===true?'pass':'fail'}">${ok===true?'✓':'!'} ${esc(labels[key] || key)}</span>`).join('');
    } catch {
      shell.hidden = true;
    }
  }

  load();
  setInterval(load, 15 * 60 * 1000);
})();
