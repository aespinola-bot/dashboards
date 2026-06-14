/*!
 * Floating community chat for aespinola-bot/dashboards
 *
 * Real-time, anonymous, no signup. Speaks MQTT over WebSockets to a free
 * public broker (broker.emqx.io). Messages are not persisted on the broker —
 * users only see chatter while they're online.
 *
 * Topic: aespinola/dashboards/chat-v1
 * Wire format: JSON { id, nick, text, ts }
 */
(function () {
  if (window.__chatWidgetLoaded) return;
  window.__chatWidgetLoaded = true;

  // --- Config ---
  var BROKER  = 'wss://broker.emqx.io:8084/mqtt';
  var TOPIC   = 'aespinola/dashboards/chat-v1';
  var MQTT_SRC = 'https://unpkg.com/mqtt@5.10.1/dist/mqtt.min.js';
  var MAX_MESSAGES = 200;
  var STORAGE_OPEN = 'cw-open';
  var STORAGE_NICK = 'cw-nick';
  var STORAGE_LOG  = 'cw-log-v1';

  // --- Styles ---
  var css = document.createElement('style');
  css.textContent = [
    '.cw-bubble{position:fixed;bottom:20px;right:20px;z-index:2147483645;width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,#8b5cf6 0%,#06b6d4 100%);border:none;cursor:pointer;box-shadow:0 8px 24px rgba(139,92,246,.45),0 4px 10px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;color:#fff;transition:transform .2s ease,box-shadow .2s ease;animation:cwIn .35s cubic-bezier(.34,1.56,.64,1)}',
    '.cw-bubble:hover{transform:scale(1.08);box-shadow:0 12px 30px rgba(139,92,246,.6),0 6px 14px rgba(0,0,0,.35)}',
    '.cw-bubble:active{transform:scale(.95)}',
    '.cw-bubble svg{width:28px;height:28px;filter:drop-shadow(0 2px 4px rgba(0,0,0,.3))}',
    '.cw-bubble.is-open{background:linear-gradient(135deg,#475569 0%,#1e293b 100%);box-shadow:0 4px 14px rgba(0,0,0,.35)}',
    '.cw-bubble .cw-pulse{position:absolute;inset:-4px;border-radius:50%;border:2px solid rgba(139,92,246,.6);animation:cwPulse 2.4s ease-in-out infinite;pointer-events:none}',
    '.cw-bubble.is-open .cw-pulse{display:none}',
    '.cw-bubble .cw-badge{position:absolute;top:-2px;right:-2px;min-width:18px;height:18px;padding:0 5px;border-radius:9px;background:#ef4444;color:#fff;font:700 10px/18px Inter,sans-serif;text-align:center;box-shadow:0 2px 6px rgba(239,68,68,.5);display:none}',
    '.cw-bubble .cw-badge.is-on{display:block}',
    '@keyframes cwPulse{0%{transform:scale(1);opacity:.8}70%{transform:scale(1.45);opacity:0}100%{transform:scale(1.45);opacity:0}}',
    '@keyframes cwIn{from{transform:scale(0) rotate(-180deg);opacity:0}to{transform:scale(1) rotate(0);opacity:1}}',
    '.cw-panel{position:fixed;bottom:90px;right:20px;z-index:2147483645;width:min(380px,calc(100vw - 40px));height:min(560px,calc(100vh - 120px));background:#0f1424;border:1px solid #2a3556;border-radius:16px;display:flex;flex-direction:column;box-shadow:0 18px 50px rgba(0,0,0,.55),0 0 0 1px rgba(139,92,246,.15);transform:translateY(20px) scale(.96);opacity:0;pointer-events:none;transition:transform .25s cubic-bezier(.34,1.56,.64,1),opacity .2s ease;overflow:hidden;color:#e8ecf5;font-family:Inter,system-ui,-apple-system,sans-serif}',
    '.cw-panel.is-open{transform:translateY(0) scale(1);opacity:1;pointer-events:auto}',
    '.cw-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:linear-gradient(135deg,rgba(139,92,246,.18) 0%,rgba(6,182,212,.14) 100%);border-bottom:1px solid #2a3556;flex:0 0 auto}',
    '.cw-head-title{display:flex;align-items:center;gap:9px;font:600 13px/1.2 Inter}',
    '.cw-head-dot{width:8px;height:8px;border-radius:50%;background:#64748b;transition:background .2s ease,box-shadow .2s ease}',
    '.cw-head-dot.is-on{background:#10b981;box-shadow:0 0 8px #10b981;animation:cwPulse2 2s ease-in-out infinite}',
    '@keyframes cwPulse2{0%,100%{opacity:1}50%{opacity:.55}}',
    '.cw-head-sub{color:#94a3b8;font-size:10px;font-family:"JetBrains Mono",ui-monospace,monospace;text-transform:uppercase;letter-spacing:.7px;margin-top:1px}',
    '.cw-head-btn{background:transparent;border:none;color:#94a3b8;padding:6px 8px;border-radius:6px;cursor:pointer;font-size:14px;line-height:1;transition:all .15s ease}',
    '.cw-head-btn:hover{background:rgba(255,255,255,.08);color:#fff}',
    '.cw-nickbar{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid #1e2742;background:#0a0e1a;flex:0 0 auto}',
    '.cw-nickbar label{font-size:11px;color:#94a3b8;font-family:"JetBrains Mono",ui-monospace,monospace;text-transform:uppercase;letter-spacing:.6px}',
    '.cw-nick-input{flex:1;background:#161c30;border:1px solid #2a3556;color:#e8ecf5;padding:6px 10px;border-radius:6px;font:600 12px Inter;outline:none;transition:border-color .15s ease}',
    '.cw-nick-input:focus{border-color:#8b5cf6}',
    '.cw-msgs{flex:1 1 auto;overflow-y:auto;padding:12px 14px;display:flex;flex-direction:column;gap:8px;background:#0a0e1a;scrollbar-width:thin;scrollbar-color:#2a3556 transparent}',
    '.cw-msgs::-webkit-scrollbar{width:6px}.cw-msgs::-webkit-scrollbar-thumb{background:#2a3556;border-radius:3px}',
    '.cw-msg{padding:7px 10px;border-radius:10px;background:#161c30;border:1px solid #1e2742;font-size:13px;line-height:1.4;word-wrap:break-word;animation:cwMsgIn .25s ease}',
    '.cw-msg.is-mine{background:linear-gradient(135deg,rgba(139,92,246,.18),rgba(6,182,212,.12));border-color:rgba(139,92,246,.35);align-self:flex-end;max-width:85%}',
    '.cw-msg-meta{display:flex;justify-content:space-between;gap:8px;margin-bottom:3px;font:600 10px/1.2 "JetBrains Mono",ui-monospace,monospace;text-transform:uppercase;letter-spacing:.5px}',
    '.cw-msg-nick{color:#a78bfa}.cw-msg.is-mine .cw-msg-nick{color:#67e8f9}',
    '.cw-msg-time{color:#64748b}',
    '.cw-msg-text{color:#e8ecf5;white-space:pre-wrap}',
    '.cw-sys{align-self:center;color:#64748b;font:500 11px "JetBrains Mono",ui-monospace,monospace;padding:4px 10px;background:rgba(100,116,139,.08);border-radius:999px}',
    '@keyframes cwMsgIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}',
    '.cw-form{display:flex;gap:8px;padding:10px 12px;border-top:1px solid #2a3556;background:#0f1424;flex:0 0 auto}',
    '.cw-input{flex:1;background:#161c30;border:1px solid #2a3556;color:#e8ecf5;padding:9px 12px;border-radius:8px;font:500 13px Inter;outline:none;resize:none;max-height:80px;line-height:1.4;transition:border-color .15s ease}',
    '.cw-input:focus{border-color:#8b5cf6}',
    '.cw-input:disabled{opacity:.5;cursor:not-allowed}',
    '.cw-send{background:linear-gradient(135deg,#8b5cf6 0%,#06b6d4 100%);color:#fff;border:none;padding:0 14px;border-radius:8px;font:700 13px Inter;cursor:pointer;transition:transform .12s ease,opacity .15s ease;display:flex;align-items:center;justify-content:center}',
    '.cw-send:hover:not(:disabled){transform:translateY(-1px)}',
    '.cw-send:disabled{opacity:.4;cursor:not-allowed}',
    '.cw-send svg{width:16px;height:16px}',
    '@media print{.cw-bubble,.cw-panel{display:none!important}}',
    '@media (max-width:480px){.cw-panel{right:10px;left:10px;width:auto;bottom:80px;height:calc(100vh - 140px)}.cw-bubble{bottom:14px;right:14px;width:54px;height:54px}}'
  ].join('');
  document.head.appendChild(css);

  // --- DOM ---
  var bubble = document.createElement('button');
  bubble.className = 'cw-bubble';
  bubble.setAttribute('aria-label', 'Open community chat');
  bubble.setAttribute('title', 'Community chat');
  bubble.innerHTML =
    '<span class="cw-pulse" aria-hidden="true"></span>' +
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>' +
    '</svg>' +
    '<span class="cw-badge" data-cw-badge>0</span>';

  var panel = document.createElement('div');
  panel.className = 'cw-panel';
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'Community chat');
  panel.innerHTML =
    '<div class="cw-head">' +
      '<div>' +
        '<div class="cw-head-title"><span class="cw-head-dot" data-cw-dot></span> Community Chat</div>' +
        '<div class="cw-head-sub" data-cw-status>Connecting…</div>' +
      '</div>' +
      '<button class="cw-head-btn" data-cw-action="close" title="Close" aria-label="Close">✕</button>' +
    '</div>' +
    '<div class="cw-nickbar">' +
      '<label for="cw-nick">You:</label>' +
      '<input class="cw-nick-input" id="cw-nick" maxlength="20" placeholder="Pick a nickname" data-cw-nick />' +
    '</div>' +
    '<div class="cw-msgs" data-cw-msgs></div>' +
    '<form class="cw-form" data-cw-form>' +
      '<textarea class="cw-input" rows="1" maxlength="500" placeholder="Type a message…" data-cw-input disabled></textarea>' +
      '<button class="cw-send" type="submit" data-cw-send disabled aria-label="Send">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>' +
      '</button>' +
    '</form>';

  document.body.appendChild(bubble);
  document.body.appendChild(panel);

  // Avoid overlapping the World Cup "Standings" toggle which also lives in the
  // bottom-right corner. If detected, raise the bubble and panel accordingly.
  function adjustForStandingsToggle() {
    var st = document.querySelector('.standings-toggle');
    if (!st) return;
    var h = st.getBoundingClientRect().height || 46;
    var lift = Math.round(h + 14); // toggle height + gap
    bubble.style.bottom = (20 + lift) + 'px';
    panel.style.bottom  = (90 + lift) + 'px';
    // Hide chat while the standings panel is open (same pattern as home pill)
    var obs = new MutationObserver(function () {
      var open = document.body.classList.contains('standings-open');
      bubble.style.opacity = open ? '0' : '';
      bubble.style.pointerEvents = open ? 'none' : '';
      bubble.style.transform = open ? 'translateX(20px)' : '';
    });
    obs.observe(document.body, { attributes: true, attributeFilter: ['class'] });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', adjustForStandingsToggle);
  } else {
    adjustForStandingsToggle();
  }

  // --- Refs ---
  var dot      = panel.querySelector('[data-cw-dot]');
  var statusEl = panel.querySelector('[data-cw-status]');
  var msgsEl   = panel.querySelector('[data-cw-msgs]');
  var nickEl   = panel.querySelector('[data-cw-nick]');
  var inputEl  = panel.querySelector('[data-cw-input]');
  var sendBtn  = panel.querySelector('[data-cw-send]');
  var formEl   = panel.querySelector('[data-cw-form]');
  var badgeEl  = bubble.querySelector('[data-cw-badge]');

  // --- State ---
  var unread = 0;
  var seenIds = new Set();
  var client = null;
  var connected = false;

  function genNick() {
    var animals = ['Falcon','Otter','Panda','Lynx','Heron','Tapir','Koala','Marlin','Bison','Quokka','Wombat','Vixen'];
    return animals[Math.floor(Math.random() * animals.length)] + '-' +
           Math.floor(1000 + Math.random() * 8999);
  }
  var nick = '';
  try { nick = localStorage.getItem(STORAGE_NICK) || ''; } catch (e) {}
  if (!nick) nick = genNick();
  nickEl.value = nick;

  function persistNick() {
    var v = (nickEl.value || '').trim().slice(0, 20);
    if (!v) v = genNick();
    nick = v;
    try { localStorage.setItem(STORAGE_NICK, v); } catch (e) {}
  }
  nickEl.addEventListener('change', persistNick);
  nickEl.addEventListener('blur', persistNick);

  function fmtTime(ts) {
    var d = new Date(ts);
    var hh = String(d.getHours()).padStart(2, '0');
    var mm = String(d.getMinutes()).padStart(2, '0');
    return hh + ':' + mm;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function appendMessage(m, opts) {
    if (!m || !m.id || seenIds.has(m.id)) return;
    seenIds.add(m.id);
    var mine = m.nick === nick && (Date.now() - m.ts < 60000); // best-effort own-message detection
    var div = document.createElement('div');
    div.className = 'cw-msg' + (mine ? ' is-mine' : '');
    div.innerHTML =
      '<div class="cw-msg-meta">' +
        '<span class="cw-msg-nick">' + escapeHtml(m.nick) + '</span>' +
        '<span class="cw-msg-time">' + fmtTime(m.ts) + '</span>' +
      '</div>' +
      '<div class="cw-msg-text">' + escapeHtml(m.text) + '</div>';
    msgsEl.appendChild(div);
    while (msgsEl.children.length > MAX_MESSAGES) msgsEl.removeChild(msgsEl.firstChild);
    msgsEl.scrollTop = msgsEl.scrollHeight;
    if (!mine && !panel.classList.contains('is-open') && !(opts && opts.silent)) {
      unread++;
      badgeEl.textContent = unread > 99 ? '99+' : String(unread);
      badgeEl.classList.add('is-on');
    }
  }
  function appendSystem(text) {
    var div = document.createElement('div');
    div.className = 'cw-sys';
    div.textContent = text;
    msgsEl.appendChild(div);
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  // Replay last messages from local cache so the panel never opens empty
  try {
    var log = JSON.parse(localStorage.getItem(STORAGE_LOG) || '[]');
    log.slice(-50).forEach(function (m) { appendMessage(m, { silent: true }); });
  } catch (e) {}
  function persistLog() {
    try {
      var arr = [];
      msgsEl.querySelectorAll('.cw-msg').forEach(function (el) {
        // We don't bother — just persist the canonical store
      });
      // Persist via a simple in-memory store updated on each new message
      localStorage.setItem(STORAGE_LOG, JSON.stringify(logBuf.slice(-MAX_MESSAGES)));
    } catch (e) {}
  }
  var logBuf = [];
  try { logBuf = JSON.parse(localStorage.getItem(STORAGE_LOG) || '[]'); } catch (e) {}

  // --- MQTT ---
  function setStatus(text, on) {
    statusEl.textContent = text;
    if (on) dot.classList.add('is-on'); else dot.classList.remove('is-on');
    inputEl.disabled = !on;
    sendBtn.disabled = !on;
  }

  function loadMqtt() {
    return new Promise(function (resolve, reject) {
      if (window.mqtt) return resolve(window.mqtt);
      var s = document.createElement('script');
      s.src = MQTT_SRC;
      s.onload = function () { window.mqtt ? resolve(window.mqtt) : reject(new Error('mqtt missing')); };
      s.onerror = function () { reject(new Error('mqtt load failed')); };
      document.head.appendChild(s);
    });
  }

  function connect() {
    setStatus('Connecting…', false);
    loadMqtt().then(function (mqtt) {
      var clientId = 'cw_' + Math.random().toString(36).slice(2, 10);
      client = mqtt.connect(BROKER, {
        clientId: clientId,
        clean: true,
        keepalive: 30,
        connectTimeout: 8000,
        reconnectPeriod: 4000
      });
      client.on('connect', function () {
        connected = true;
        setStatus('Connected · ' + TOPIC.split('/').pop(), true);
        client.subscribe(TOPIC, { qos: 0 });
      });
      client.on('reconnect', function () { setStatus('Reconnecting…', false); });
      client.on('close',     function () { connected = false; setStatus('Disconnected', false); });
      client.on('offline',   function () { connected = false; setStatus('Offline', false); });
      client.on('error',     function (err) { setStatus('Error: ' + (err && err.message || 'unknown'), false); });
      client.on('message', function (topic, payload) {
        if (topic !== TOPIC) return;
        var m;
        try { m = JSON.parse(payload.toString()); } catch (e) { return; }
        if (!m || typeof m.text !== 'string') return;
        m.nick = String(m.nick || 'anon').slice(0, 20);
        m.text = String(m.text).slice(0, 500);
        m.ts   = Number(m.ts) || Date.now();
        m.id   = String(m.id  || (m.ts + '_' + Math.random()));
        appendMessage(m);
        logBuf.push(m); persistLog();
      });
    }).catch(function (e) {
      setStatus('Failed to load chat library', false);
      appendSystem('Could not load chat. Check your network.');
    });
  }

  function send() {
    var text = (inputEl.value || '').trim();
    if (!text || !connected || !client) return;
    persistNick();
    var msg = {
      id: Date.now() + '_' + Math.random().toString(36).slice(2, 8),
      nick: nick,
      text: text.slice(0, 500),
      ts: Date.now()
    };
    try {
      client.publish(TOPIC, JSON.stringify(msg), { qos: 0 });
    } catch (e) { return; }
    inputEl.value = '';
    inputEl.style.height = '';
  }

  formEl.addEventListener('submit', function (e) { e.preventDefault(); send(); });
  inputEl.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  inputEl.addEventListener('input', function () {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 80) + 'px';
  });

  // --- Open / close ---
  function openPanel() {
    panel.classList.add('is-open');
    bubble.classList.add('is-open');
    bubble.querySelector('svg').innerHTML = '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>';
    bubble.setAttribute('aria-label', 'Close community chat');
    unread = 0; badgeEl.classList.remove('is-on'); badgeEl.textContent = '0';
    msgsEl.scrollTop = msgsEl.scrollHeight;
    setTimeout(function () { inputEl.focus(); }, 180);
    try { sessionStorage.setItem(STORAGE_OPEN, '1'); } catch (e) {}
    if (!client) connect();
  }
  function closePanel() {
    panel.classList.remove('is-open');
    bubble.classList.remove('is-open');
    bubble.querySelector('svg').innerHTML = '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>';
    bubble.setAttribute('aria-label', 'Open community chat');
    try { sessionStorage.removeItem(STORAGE_OPEN); } catch (e) {}
  }
  bubble.addEventListener('click', function () {
    panel.classList.contains('is-open') ? closePanel() : openPanel();
  });
  panel.addEventListener('click', function (e) {
    var t = e.target.closest('[data-cw-action]');
    if (t && t.dataset.cwAction === 'close') closePanel();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && panel.classList.contains('is-open')) closePanel();
  });

  // Eagerly connect in the background so the first open is instant
  connect();

  // Restore open state on cross-page navigation within the same session
  try {
    if (sessionStorage.getItem(STORAGE_OPEN) === '1') setTimeout(openPanel, 200);
  } catch (e) {}
})();
