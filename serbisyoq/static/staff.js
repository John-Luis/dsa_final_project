/* Update only read-only queue regions; keep filters and announcement drafts intact. */
(() => {
  const health = document.getElementById('staff-live-status');
  let lastResponse;
  async function refresh() {
    try {
      const response = await fetch('/api/staff/queue' + window.location.search, { cache: 'no-store' });
      if (response.redirected || !response.ok || !response.headers.get('content-type')?.includes('application/json')) {
        throw new Error('Sign in again if your session expired.');
      }
      const data = await response.json();
      if (!document.activeElement?.closest('[data-live]')) {
        // Fragments are produced by autoescaped Jinja templates on our authenticated endpoint.
        for (const [id, key] of [['staff-stats','stats_html'],['staff-counters','counters_html'],['staff-rows','rows_html']]) {
          if (!lastResponse || data[key] !== lastResponse[key]) document.getElementById(id).innerHTML = data[key];
        }
        document.getElementById('record-count').textContent = `${data.record_count} records`;
        lastResponse = data;
      }
      health.textContent = 'Live · updated ' + new Intl.DateTimeFormat('en-PH', {timeZone:'Asia/Manila',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date());
    } catch {
      health.textContent = 'Updates paused · reconnecting. Sign in again if your session expired.';
    } finally { setTimeout(refresh, 5000); }
  }
  setTimeout(refresh, 5000);
})();
