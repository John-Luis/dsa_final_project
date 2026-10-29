/* Queue polling never replaces the media player: videos keep playing during updates. */
(() => {
  const initial = JSON.parse(document.getElementById('monitor-state').textContent);
  const screen = document.getElementById('media-screen');
  let playlist = initial.playlist, index = 0, timer, paused = false;
  let offset = Date.parse(initial.server_time) - Date.now();
  const clock = new Intl.DateTimeFormat('en-PH', { timeZone: 'Asia/Manila', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
  const date = new Intl.DateTimeFormat('en-PH', { timeZone: 'Asia/Manila', weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
  function tick() {
    const now = new Date(Date.now() + offset);
    document.getElementById('tv-time').textContent = clock.format(now);
    document.getElementById('tv-date').textContent = date.format(now);
  }
  function schedule() {
    clearTimeout(timer);
    if (!paused) timer = setTimeout(() => show(index + 1), playlist[index].seconds * 1000);
  }
  function show(next) {
    clearTimeout(timer);
    screen.querySelector('video')?.pause();
    index = (next + playlist.length) % playlist.length;
    const item = playlist[index];
    const player = document.createElement(item.kind === 'video' ? 'video' : 'img');
    if (item.kind === 'video') {
      player.muted = true; player.autoplay = !paused; player.playsInline = true;
      player.onended = () => { if (!paused) show(index + 1); };
    } else player.alt = item.title;
    player.onerror = () => {
      const message = document.createElement('p');
      message.textContent = 'This announcement cannot be played. The next announcement will follow.';
      screen.replaceChildren(message);
    };
    player.src = item.url;
    screen.replaceChildren(player);
    document.getElementById('media-title').textContent = item.title;
    schedule();
  }
  document.getElementById('media-prev').onclick = () => show(index - 1);
  document.getElementById('media-next').onclick = () => show(index + 1);
  document.getElementById('media-pause').onclick = (event) => {
    paused = !paused;
    event.currentTarget.textContent = paused ? 'Resume slideshow' : 'Pause slideshow';
    const video = screen.querySelector('video');
    if (paused) { clearTimeout(timer); video?.pause(); }
    else { video?.play().catch(() => { video.controls = true; }); schedule(); }
  };
  async function refresh() {
    try {
      const response = await fetch('/api/monitor', { cache: 'no-store' });
      if (!response.ok) throw new Error('Queue unavailable');
      const state = await response.json();
      offset = Date.parse(state.server_time) - Date.now();
      for (const counter of state.counters) {
        const block = document.getElementById(`tv-counter-${counter.id}`);
        block.querySelector('[data-current]').textContent = counter.ticket || '—';
        block.querySelector('[data-next]').textContent = counter.up_next || '—';
        block.querySelector('[data-status]').textContent = counter.status || 'Ready to assist';
      }
      document.getElementById('tv-announcement').textContent = state.announcement;
      document.getElementById('tv-total').textContent = `${state.total} waiting`;
      const upcoming = document.getElementById('tv-upcoming');
      upcoming.replaceChildren();
      for (const row of state.upcoming) {
        const entry = document.createElement('span'), ticket = document.createElement('strong'), counter = document.createElement('small');
        ticket.textContent = row.ticket; counter.textContent = `Counter ${row.counter}`;
        entry.append(ticket, counter); upcoming.append(entry);
      }
      if (!state.upcoming.length) upcoming.textContent = 'The waiting queue is clear.';
      if (JSON.stringify(state.playlist) !== JSON.stringify(playlist)) {
        playlist = state.playlist; show(0);
      }
      document.getElementById('monitor-health').textContent = 'Live · updated ' + clock.format(new Date());
    } catch {
      document.getElementById('monitor-health').textContent = 'Connection interrupted · showing last received queue. Reconnecting…';
    } finally { setTimeout(refresh, 5000); }
  }
  tick(); setInterval(tick, 1000); show(0); setTimeout(refresh, 5000);
})();
