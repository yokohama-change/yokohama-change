(() => {
  const main = document.querySelector('main');
  if (!main) return;

  let shell = document.querySelector('#qualityAudit');
  if (!shell) {
    shell = document.createElement('section');
    shell.id = 'qualityAudit';
    shell.className = 'quality-audit';
    shell.setAttribute('aria-labelledby', 'qualityAuditTitle');
    shell.hidden = true;
    shell.innerHTML = `
      <div class="quality-audit-head">
        <div>
          <span class="quality-audit-kicker">QUALITY AUDIT · TRANSPARENCY</span>
          <h2 id="qualityAuditTitle">公開前の品質チェックを可視化</h2>
          <p id="qualityAuditCopy">品質データを確認しています。</p>
        </div>
        <span id="qualityAuditState" class="quality-audit-state">確認中</span>
      </div>
      <div class="quality-audit-metrics">
        <div><b id="qualityAuditSources">—</b><span>非空の公式ソース / 設定数</span></div>
        <div><b id="qualityAuditChecks">—</b><span>品質チェック通過</span></div>
        <div><b id="qualityAuditOpen">—</b><span>受付中案件</span></div>
        <div><b id="qualityAuditDuplicates">—</b><span>残存する重複URL</span></div>
      </div>
      <div id="qualityAuditChips" class="quality-audit-chips" aria-live="polite"></div>
      <div class="quality-audit-foot">
        <span>最終監査 <b id="qualityAuditUpdated">—</b> · 自動品質検査であり、公式情報の正確性を保証するものではありません。</span>
        <a href="data/quality.json">品質データを確認 →</a>
      </div>`;
    main.prepend(shell);
  }

  const esc = (value = '') => String(value).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  const fmt = (iso) => {
    try {
      return new Intl.DateTimeFormat('ja-JP', {
        month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
        timeZone: 'Asia/Tokyo'
      }).format(new Date(iso));
    } catch {
      return iso || '—';
    }
  };

  const put = (id, value) => {
    const node = document.querySelector(id);
    if (node) node.textContent = value;
  };

  const labels = {
    source_inventory_healthy: '公式ソース在庫',
    official_provenance_consistent: '公式出典照合',
    open_deadlines_not_past: '締切超過除外',
    deadline_fields_consistent: '締切データ整合',
    employment_excluded: '求人情報除外',
    counts_consistent: '件数整合',
    open_feed_ids_consistent: '公開案件ID整合',
    high_value_counts_consistent: '高商用件数整合',
    unique_ids: '重複IDなし',
    unique_public_urls: '重複URLなし'
  };

  async function load() {
    try {
      const response = await fetch('data/quality.json', {cache: 'no-store'});
      if (!response.ok) throw new Error(`quality HTTP ${response.status}`);
      const quality = await response.json();
      const inventory = quality.source_inventory || {};
      const dedupe = quality.dedupe || {};
      const checks = quality.checks && typeof quality.checks === 'object' ? quality.checks : {};
      const entries = Object.entries(checks);
      const passed = entries.filter(([, ok]) => ok === true).length;
      const total = entries.length;
      const good = quality.health === 'good' && total > 0 && passed === total;

      shell.hidden = false;
      shell.classList.toggle('is-good', good);
      shell.classList.toggle('is-warning', !good);
      put('#qualityAuditState', good ? '全チェック PASS' : (quality.health_label || '要確認'));
      put('#qualityAuditSources', `${inventory.nonempty_sources ?? '—'}/${inventory.configured_sources ?? '—'}`);
      put('#qualityAuditChecks', `${passed}/${total}`);
      put('#qualityAuditOpen', quality.open_now ?? '—');
      put('#qualityAuditDuplicates', dedupe.remaining_duplicate_urls ?? '—');
      put('#qualityAuditUpdated', fmt(quality.checked_at));

      const copy = document.querySelector('#qualityAuditCopy');
      if (copy) {
        copy.textContent = good
          ? '公式ソース・出典・締切・件数・重複を公開前に自動検査し、すべて通過したデータを表示しています。'
          : '品質検査に注意項目があります。高優先表示は安全側で抑制されます。詳細をご確認ください。';
      }

      const chips = document.querySelector('#qualityAuditChips');
      if (chips) {
        chips.innerHTML = entries.map(([key, ok]) =>
          `<span class="quality-audit-chip ${ok === true ? 'pass' : 'fail'}">${ok === true ? '✓' : '!'} ${esc(labels[key] || key)}</span>`
        ).join('');
      }
    } catch {
      // Never leave a stale-looking PASS visible if the audit file cannot be read.
      shell.hidden = true;
    }
  }

  load();
  setInterval(load, 15 * 60 * 1000);
})();
