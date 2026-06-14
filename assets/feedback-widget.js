/*!
 * Feedback / Bug report pill for aespinola-bot/dashboards
 *
 * Floating pill (bottom-left) that opens a small modal. The user picks a type
 * (Bug / Idea / Question), writes a short description, and clicks Submit —
 * which opens a prefilled GitHub Issues "new issue" URL in a new tab. No
 * backend, no auth flow on our side; user signs in to GitHub once if needed.
 */
(function () {
  if (window.__feedbackWidgetLoaded) return;
  window.__feedbackWidgetLoaded = true;

  var REPO = 'aespinola-bot/dashboards';
  var STORAGE_NAME = 'fw-name';

  var css = document.createElement('style');
  css.textContent = [
    '.fw-pill{position:fixed;bottom:calc(20px + env(safe-area-inset-bottom));left:20px;z-index:2147483645;display:inline-flex;align-items:center;gap:8px;padding:9px 14px;border-radius:999px;background:rgba(15,20,36,.86);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border:1px solid rgba(139,92,246,.35);color:#e8ecf5;font:600 12px Inter,system-ui,-apple-system,sans-serif;cursor:pointer;box-shadow:0 6px 18px rgba(0,0,0,.35);transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease;animation:fwIn .35s cubic-bezier(.34,1.56,.64,1)}',
    '.fw-pill:hover{transform:translateY(-1px);border-color:rgba(139,92,246,.7);box-shadow:0 10px 24px rgba(139,92,246,.35)}',
    '.fw-pill svg{width:14px;height:14px}',
    '@keyframes fwIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}',
    '.fw-overlay{position:fixed;inset:0;z-index:2147483646;background:rgba(5,8,16,.72);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:20px;opacity:0;pointer-events:none;transition:opacity .2s ease}',
    '.fw-overlay.is-open{opacity:1;pointer-events:auto}',
    '.fw-modal{width:min(480px,100%);max-height:calc(100vh - 40px);background:#0f1424;border:1px solid #2a3556;border-radius:16px;box-shadow:0 24px 60px rgba(0,0,0,.6),0 0 0 1px rgba(139,92,246,.18);display:flex;flex-direction:column;overflow:hidden;color:#e8ecf5;font-family:Inter,system-ui,-apple-system,sans-serif;transform:scale(.96) translateY(10px);opacity:0;transition:transform .25s cubic-bezier(.34,1.56,.64,1),opacity .2s ease}',
    '.fw-overlay.is-open .fw-modal{transform:scale(1) translateY(0);opacity:1}',
    '.fw-head{padding:16px 18px;display:flex;align-items:center;justify-content:space-between;background:linear-gradient(135deg,rgba(139,92,246,.18) 0%,rgba(6,182,212,.14) 100%);border-bottom:1px solid #2a3556}',
    '.fw-title{font:700 15px Inter;color:#f1f5f9}',
    '.fw-sub{font:500 10px/1.4 "JetBrains Mono",ui-monospace,monospace;text-transform:uppercase;letter-spacing:.7px;color:#94a3b8;margin-top:2px}',
    '.fw-close{background:transparent;border:none;color:#94a3b8;font-size:18px;line-height:1;cursor:pointer;padding:6px;border-radius:6px}',
    '.fw-close:hover{background:rgba(255,255,255,.08);color:#fff}',
    '.fw-body{padding:18px;display:flex;flex-direction:column;gap:14px;overflow-y:auto}',
    '.fw-row{display:flex;flex-direction:column;gap:6px}',
    '.fw-label{font:600 11px "JetBrains Mono",ui-monospace,monospace;text-transform:uppercase;letter-spacing:.6px;color:#94a3b8}',
    '.fw-types{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}',
    '.fw-type{display:flex;flex-direction:column;align-items:center;gap:4px;padding:10px 8px;border:1px solid #2a3556;border-radius:10px;background:#161c30;cursor:pointer;transition:all .15s ease;font:600 12px Inter;color:#cbd5e1}',
    '.fw-type:hover{border-color:#475569;color:#e8ecf5}',
    '.fw-type.is-on{border-color:#8b5cf6;background:linear-gradient(135deg,rgba(139,92,246,.2),rgba(6,182,212,.14));color:#f1f5f9;box-shadow:0 0 0 1px rgba(139,92,246,.4)}',
    '.fw-type-emoji{font-size:20px}',
    '.fw-input,.fw-textarea{width:100%;background:#0a0e1a;border:1px solid #2a3556;color:#e8ecf5;padding:9px 12px;border-radius:8px;font:500 13px Inter;outline:none;transition:border-color .15s ease;box-sizing:border-box}',
    '.fw-input:focus,.fw-textarea:focus{border-color:#8b5cf6}',
    '.fw-textarea{min-height:110px;resize:vertical;font-family:Inter;line-height:1.5}',
    '.fw-help{font-size:11px;color:#64748b;line-height:1.5}',
    '.fw-help a{color:#a78bfa;text-decoration:none}.fw-help a:hover{text-decoration:underline}',
    '.fw-foot{padding:14px 18px;display:flex;justify-content:flex-end;gap:8px;border-top:1px solid #2a3556;background:#0a0e1a}',
    '.fw-btn{padding:9px 16px;border-radius:8px;border:1px solid #2a3556;background:#161c30;color:#e8ecf5;font:600 12px Inter;cursor:pointer;transition:all .15s ease}',
    '.fw-btn:hover{border-color:#475569}',
    '.fw-btn.is-primary{border-color:transparent;background:linear-gradient(135deg,#8b5cf6 0%,#06b6d4 100%);box-shadow:0 4px 14px rgba(139,92,246,.35)}',
    '.fw-btn.is-primary:hover{transform:translateY(-1px);box-shadow:0 6px 18px rgba(139,92,246,.5)}',
    '.fw-btn:disabled{opacity:.4;cursor:not-allowed;transform:none}',
    '@media print{.fw-pill,.fw-overlay{display:none!important}}',
    '@media (max-width:480px){.fw-pill{bottom:calc(14px + env(safe-area-inset-bottom));left:14px;padding:0;width:46px;height:46px;border-radius:50%;justify-content:center;gap:0}.fw-pill span{display:none}.fw-pill svg{width:18px;height:18px}.fw-types{grid-template-columns:1fr 1fr 1fr}}'
  ].join('');
  document.head.appendChild(css);

  var pill = document.createElement('button');
  pill.className = 'fw-pill';
  pill.setAttribute('aria-label', 'Send feedback or report a bug');
  pill.setAttribute('title', 'Send feedback or report a bug');
  pill.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>' +
    '</svg>' +
    '<span>Feedback</span>';

  var overlay = document.createElement('div');
  overlay.className = 'fw-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', 'Feedback');
  overlay.innerHTML =
    '<div class="fw-modal">' +
      '<div class="fw-head">' +
        '<div>' +
          '<div class="fw-title">Send feedback</div>' +
          '<div class="fw-sub">we read every message</div>' +
        '</div>' +
        '<button class="fw-close" data-fw-action="close" aria-label="Close">✕</button>' +
      '</div>' +
      '<div class="fw-body">' +
        '<div class="fw-row">' +
          '<div class="fw-label">Type</div>' +
          '<div class="fw-types" data-fw-types>' +
            '<button class="fw-type is-on"  data-fw-type="bug"      type="button"><span class="fw-type-emoji">🐛</span>Bug</button>' +
            '<button class="fw-type"        data-fw-type="idea"     type="button"><span class="fw-type-emoji">💡</span>Idea</button>' +
            '<button class="fw-type"        data-fw-type="question" type="button"><span class="fw-type-emoji">❓</span>Question</button>' +
          '</div>' +
        '</div>' +
        '<div class="fw-row">' +
          '<div class="fw-label">Title</div>' +
          '<input class="fw-input" data-fw-title placeholder="Short summary" maxlength="120" />' +
        '</div>' +
        '<div class="fw-row">' +
          '<div class="fw-label">Description</div>' +
          '<textarea class="fw-textarea" data-fw-desc placeholder="What happened? What did you expect? Steps to reproduce…" maxlength="2000"></textarea>' +
        '</div>' +
        '<div class="fw-row">' +
          '<div class="fw-label">Your name (optional)</div>' +
          '<input class="fw-input" data-fw-name placeholder="So I know who to thank" maxlength="40" />' +
        '</div>' +
        '<div class="fw-help">' +
          'A new tab will open to confirm and send your message. If it\'s your first time, you may be asked to sign in.' +
        '</div>' +
      '</div>' +
      '<div class="fw-foot">' +
        '<button class="fw-btn"            data-fw-action="close"  type="button">Cancel</button>' +
        '<button class="fw-btn is-primary" data-fw-action="submit" type="button" data-fw-submit>Submit</button>' +
      '</div>' +
    '</div>';

  document.body.appendChild(pill);
  document.body.appendChild(overlay);

  var typeBtns = overlay.querySelectorAll('[data-fw-type]');
  var titleEl  = overlay.querySelector('[data-fw-title]');
  var descEl   = overlay.querySelector('[data-fw-desc]');
  var nameEl   = overlay.querySelector('[data-fw-name]');
  var submitEl = overlay.querySelector('[data-fw-submit]');

  try { nameEl.value = localStorage.getItem(STORAGE_NAME) || ''; } catch (e) {}

  typeBtns.forEach(function (b) {
    b.addEventListener('click', function () {
      typeBtns.forEach(function (x) { x.classList.remove('is-on'); });
      b.classList.add('is-on');
    });
  });

  function getType() {
    var on = overlay.querySelector('.fw-type.is-on');
    return on ? on.dataset.fwType : 'bug';
  }
  function pageInfo() {
    return [
      '',
      '---',
      '**Page:** `' + (location.pathname || '/') + '`',
      '**URL:** ' + location.href,
      '**User-Agent:** ' + navigator.userAgent,
      '**Submitted:** ' + new Date().toISOString()
    ].join('\n');
  }
  function emojiFor(t) { return t === 'idea' ? '💡' : t === 'question' ? '❓' : '🐛'; }
  function labelFor(t) { return t === 'idea' ? 'enhancement' : t === 'question' ? 'question' : 'bug'; }

  function submit() {
    var t = getType();
    var titleRaw = (titleEl.value || '').trim();
    var desc     = (descEl.value  || '').trim();
    if (!titleRaw && !desc) {
      titleEl.focus();
      return;
    }
    var title = '[' + emojiFor(t) + ' ' + t + '] ' + (titleRaw || desc.split('\n')[0].slice(0, 80));
    var name  = (nameEl.value || '').trim();
    if (name) { try { localStorage.setItem(STORAGE_NAME, name); } catch (e) {} }
    var body  = (desc || '_(no description)_') + (name ? '\n\n— ' + name : '') + pageInfo();
    var url   = 'https://github.com/' + REPO + '/issues/new' +
                '?labels=' + encodeURIComponent('feedback,' + labelFor(t)) +
                '&title='  + encodeURIComponent(title) +
                '&body='   + encodeURIComponent(body);
    window.open(url, '_blank', 'noopener');
    closeModal();
    titleEl.value = '';
    descEl.value  = '';
  }

  function openModal() {
    overlay.classList.add('is-open');
    setTimeout(function () { titleEl.focus(); }, 180);
  }
  function closeModal() { overlay.classList.remove('is-open'); }

  pill.addEventListener('click', openModal);
  overlay.addEventListener('click', function (e) {
    var act = e.target.closest('[data-fw-action]');
    if (act) {
      if (act.dataset.fwAction === 'close')  closeModal();
      if (act.dataset.fwAction === 'submit') submit();
      return;
    }
    if (e.target === overlay) closeModal();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && overlay.classList.contains('is-open')) closeModal();
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && overlay.classList.contains('is-open')) submit();
  });
})();
