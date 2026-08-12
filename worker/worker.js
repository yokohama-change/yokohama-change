/**
 * Optional zero-cost API facade for Cloudflare Workers Free.
 * Set DATA_URL to the public latest.json URL after GitHub Pages is enabled.
 */
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const headers = {
      'content-type': 'application/json; charset=utf-8',
      'access-control-allow-origin': '*',
      'cache-control': 'public, max-age=60'
    };

    if (url.pathname === '/health') {
      return Response.json({ok:true, service:'yokohama-change-api'}, {headers});
    }
    if (url.pathname !== '/changes') {
      return Response.json({
        service:'YOKOHAMA CHANGE API',
        endpoints:['/changes','/health'],
        example:'/changes?buyer=不動産・建設&min_commercial=70&q=道路'
      }, {headers});
    }

    if (!env.DATA_URL) {
      return Response.json({error:'DATA_URL is not configured'}, {status:503, headers});
    }

    const upstream = await fetch(env.DATA_URL, {cf:{cacheTtl:60, cacheEverything:true}});
    if (!upstream.ok) {
      return Response.json({error:'upstream unavailable', status:upstream.status}, {status:502, headers});
    }
    const data = await upstream.json();
    const category = url.searchParams.get('category') || '';
    const buyer = url.searchParams.get('buyer') || '';
    const opportunity = url.searchParams.get('opportunity_type') || '';
    const q = (url.searchParams.get('q') || '').toLowerCase();
    const minImpact = Number(url.searchParams.get('min_importance') || 0);
    const minCommercial = Number(url.searchParams.get('min_commercial') || 0);
    const limit = Math.min(100, Math.max(1, Number(url.searchParams.get('limit') || 30)));
    const type = url.searchParams.get('change_type') || '';

    const items = (data.items || []).filter(x =>
      (!category || x.category === category) &&
      (!buyer || (x.buyer_segments || []).includes(buyer)) &&
      (!opportunity || x.opportunity_type === opportunity) &&
      (!type || x.change_type === type) &&
      Number(x.importance || 0) >= minImpact &&
      Number(x.commercial_score || 0) >= minCommercial &&
      (!q || `${x.title || ''} ${x.description || ''} ${x.source_name || ''} ${(x.buyer_segments||[]).join(' ')}`.toLowerCase().includes(q))
    ).sort((a,b) => Number(b.commercial_score||0)-Number(a.commercial_score||0)).slice(0, limit);

    return Response.json({
      generated_at: data.generated_at,
      count: items.length,
      items,
      disclaimer: data.disclaimer
    }, {headers});
  }
};
