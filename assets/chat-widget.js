/*!
 * Floating chat widget for aespinola-bot/dashboards
 *
 * Injects a floating bubble (bottom-right) that opens a real-time chat panel
 * embedding kiwiirc.com (IRC web client). Anyone visiting any dashboard joins
 * the same channel #aespinola-dashboards on the libera.chat IRC network.
 *
 * - No signup required (just pick a nickname on first connect)
 * - Real-time, free, lightweight (only loads the iframe when opened)
 * - Hidden when printing
 */
(function () {
  if (window.__chatWidgetLoaded) return;
  window.__chatWidgetLoaded = true;

  // --- Config ---
  var CHAT_NETWORK = 'irc.libera.chat';
  var CHAT_CHANNEL = 'aespinola-dashboards';
  var CHAT_URL = 'https://kiwiirc.com/client/' + CHAT_NETWORK + '/#' + CHAT_CHANNEL;
  var STORAGE_OPEN = 'chat-widget-open';
  var STORAGE_BADGE = 'chat-widget-last-seen';

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
    '@keyframes cwPulse{0%{transform:scale(1);opacity:.8}70%{transform:scale(1.45);opacity:0}100%{transform:scale(1.45);opacity:0}}',
    '@keyframes cwIn{from{transform:scale(0) rotate(-180deg);opacity:0}to{transform:scale(1) rotate(0);opacity:1}}',
    '.cw-panel{position:fixed;bottom:90px;right:20px;z-index:2147483645;width:min(380px,calc(100vw - 40px));height:min(540px,calc(100vh - 120px));background:#0f1424;border:1px solid #2a3556;border-radius:16px;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 18px 50px rgba(0,0,0,.55),0 0 0 1px rgba(139,92,246,.15);transform:translateY(20px) scale(.96);opacity:0;pointer-events:none;transition:transform .25s cubic-bezier(.34,1.56,.64,1),opacity .2s ease}',
    '.cw-panel.is-open{transform:translateY(0) scale(1);opacity:1;pointer-events:auto}',
    '.cw-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:linear-gradient(135deg,rgba(139,92,246,.18) 0%,rgba(6,182,212,.14) 100%);border-bottom:1px solid #2a3556}',
    '.cw-head-title{display:flex;align-items:center;gap:9px;color:#e8ecf5;font:600 13px/1.2 Inter,system-ui,-apple-system,sans-serif}',
    '.cw-head-dot{width:8px;height:8px;border-radius:50%;background:#10b981;box-shadow:0 0 8px #10b981;animation:cwPulse2 2s ease-in-out infinite}',
    '@keyframes cwPulse2{0%,100%{opacity:1}50%{opacity:.5}}',
    '.cw-head-sub{color:#94a3b8;font-size:10px;font-family:"JetBrains Mono",ui-monospace,monospace;text-transform:uppercase;letter-spacing:.7px;margin-top:1px}',
    '.cw-head-actions{display:flex;gap:4px}',
    '.cw-head-btn{background:transparent;border:none;color:#94a3b8;padding:6px;border-radius:6px;cursor:pointer;font-size:13px;line-height:1;transition:all .15s ease}',
    '.cw-head-btn:hover{background:rgba(255,255,255,.08);color:#fff}',
    '.cw-body{flex:1;background:#0a0e1a;position:relative;overflow:hidden}',
    '.cw-body iframe{width:100%;height:100%;border:0;display:block}',
    '.cw-loading{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;color:#94a3b8;font:500 12px/1.4 Inter,system-ui,sans-serif;text-align:center;padding:20px}',
    '.cw-spin{width:32px;height:32px;border:3px solid #2a3556;border-top-color:#8b5cf6;border-radius:50%;animation:cwSpin .9s linear infinite}',
    '@keyframes cwSpin{to{transform:rotate(360deg)}}',
    '.cw-foot{padding:8px 12px;background:#0a0e1a;border-top:1px solid #2a3556;color:#64748b;font:500 10px/1.4 "JetBrains Mono",ui-monospace,monospace;text-align:center}',
    '.cw-foot a{color:#94a3b8;text-decoration:none}.cw-foot a:hover{color:#06b6d4}',
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
    '</svg>';

  var panel = document.createElement('div');
  panel.className = 'cw-panel';
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'Community chat');
  panel.innerHTML =
    '<div class="cw-head">' +
      '<div>' +
        '<div class="cw-head-title"><span class="cw-head-dot"></span> Community Chat</div>' +
        '<div class="cw-head-sub">#' + CHAT_CHANNEL + '</div>' +
      '</div>' +
      '<div class="cw-head-actions">' +
        '<button class="cw-head-btn" data-cw-action="popout" title="Open in new tab" aria-label="Open in new tab">↗</button>' +
        '<button class="cw-head-btn" data-cw-action="close" title="Close" aria-label="Close">✕</button>' +
      '</div>' +
    '</div>' +
    '<div class="cw-body" data-cw-body>' +
      '<div class="cw-loading"><div class="cw-spin"></div><div>Connecting&hellip;<br><span style="font-size:11px;opacity:.7">Pick any nickname when prompted</span></div></div>' +
    '</div>' +
    '<div class="cw-foot">Powered by <a href="https://kiwiirc.com" target="_blank" rel="noopener">kiwiirc</a> · libera.chat IRC · 100% anonymous</div>';

  document.body.appendChild(bubble);
  document.body.appendChild(panel);

  // --- Behaviour ---
  var iframeLoaded = false;
  function loadIframe() {
    if (iframeLoaded) return;
    iframeLoaded = true;
    var body = panel.querySelector('[data-cw-body]');
    var iframe = document.createElement('iframe');
    iframe.src = CHAT_URL;
    iframe.title = 'Community chat';
    iframe.allow = 'clipboard-write; clipboard-read';
    iframe.referrerPolicy = 'no-referrer';
    iframe.addEventListener('load', function () {
      var loader = body.querySelector('.cw-loading');
      if (loader) loader.style.display = 'none';
    });
    body.appendChild(iframe);
  }

  function openPanel() {
    panel.classList.add('is-open');
    bubble.classList.add('is-open');
    bubble.querySelector('svg').innerHTML = '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>';
    bubble.setAttribute('aria-label', 'Close community chat');
    try { sessionStorage.setItem(STORAGE_OPEN, '1'); } catch (e) {}
    loadIframe();
  }
  function closePanel() {
    panel.classList.remove('is-open');
    bubble.classList.remove('is-open');
    bubble.querySelector('svg').innerHTML = '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>';
    bubble.setAttribute('aria-label', 'Open community chat');
    try { sessionStorage.removeItem(STORAGE_OPEN); } catch (e) {}
  }
  function togglePanel() {
    if (panel.classList.contains('is-open')) closePanel(); else openPanel();
  }

  bubble.addEventListener('click', togglePanel);
  panel.addEventListener('click', function (e) {
    var t = e.target.closest('[data-cw-action]');
    if (!t) return;
    if (t.dataset.cwAction === 'close') closePanel();
    else if (t.dataset.cwAction === 'popout') {
      window.open(CHAT_URL, '_blank', 'noopener,width=900,height=700');
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && panel.classList.contains('is-open')) closePanel();
  });

  // Persist open-state across same-session navigation between dashboards
  try {
    if (sessionStorage.getItem(STORAGE_OPEN) === '1') {
      // Slight delay so the entrance animation is visible
      setTimeout(openPanel, 200);
    }
  } catch (e) {}
})();
