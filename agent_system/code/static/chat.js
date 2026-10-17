(() => {
  const app = document.querySelector('#app');
  const form = document.querySelector('#composer');
  const content = document.querySelector('#chat-content');
  const toolsMenu = document.querySelector('#tools-menu');
  const toolsToggle = document.querySelector('#tools-toggle');
  const search = document.querySelector('#sidebar-search');
  const searchToggle = document.querySelector('#search-toggle');
  const status = document.querySelector('#submit_status');
  const settings = window.appSettings;
  const modeField = document.querySelector('#research-mode');
  const modeSlider = document.querySelector('#mode-slider');
  const modePanel = document.querySelector('#mode-panel');
  const modeToggle = document.querySelector('#mode-toggle');
  let paperStatusMarkup = document.querySelector('.chat-head .sub').innerHTML;
  let busy = false;
  let activeSessionMenu = null;
  let floatingSessionPanel = null;

  function closeSessionMenu() {
    if (!activeSessionMenu) return;
    const menu = activeSessionMenu;
    if (floatingSessionPanel) {
      floatingSessionPanel.classList.remove('floating');
      floatingSessionPanel.style.left = '';
      floatingSessionPanel.style.top = '';
      menu.appendChild(floatingSessionPanel);
    }
    activeSessionMenu = null;
    floatingSessionPanel = null;
    menu.open = false;
  }

  function openSessionMenu(menu) {
    closeSessionMenu();
    const panel = menu.querySelector('.menu-panel');
    if (!panel) return;
    activeSessionMenu = menu;
    floatingSessionPanel = panel;
    document.body.appendChild(panel);
    panel.classList.add('floating');
    const anchor = menu.querySelector('summary').getBoundingClientRect();
    const margin = 8;
    const left = Math.max(margin, Math.min(anchor.right - panel.offsetWidth, innerWidth - panel.offsetWidth - margin));
    const below = anchor.bottom + 3;
    const top = below + panel.offsetHeight + margin <= innerHeight
      ? below
      : Math.max(margin, anchor.top - panel.offsetHeight - 3);
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
  }

  function scrollToLatest() {
    if (settings.get().autoScroll) content.scrollTop = content.scrollHeight;
  }

  function setSidebar(collapsed) {
    app.classList.toggle('sidebar-collapsed', collapsed);
    if (collapsed) settings.closePanel();
    document.querySelector('#sidebar-hide').setAttribute('aria-expanded', String(!collapsed));
    document.querySelector('#sidebar-show').setAttribute('aria-expanded', String(!collapsed));
    try { localStorage.setItem('paper-agent-sidebar-collapsed', String(collapsed)); } catch (_) {}
  }

  let savedSidebar = null;
  try { savedSidebar = localStorage.getItem('paper-agent-sidebar-collapsed'); } catch (_) {}
  setSidebar(savedSidebar === null ? matchMedia('(max-width: 760px)').matches : savedSidebar === 'true');
  document.querySelector('#sidebar-hide').addEventListener('click', () => setSidebar(true));
  document.querySelector('#sidebar-show').addEventListener('click', () => setSidebar(false));

  function setSearch(open) {
    search.hidden = !open;
    searchToggle.setAttribute('aria-expanded', String(open));
    if (open) search.querySelector('input[name="search"]').focus();
  }
  if (search.querySelector('input[name="search"]').value) setSearch(true);
  searchToggle.addEventListener('click', () => setSearch(search.hidden));

  function setTools(open) {
    toolsMenu.hidden = !open;
    toolsToggle.setAttribute('aria-expanded', String(open));
  }
  toolsToggle.addEventListener('click', () => setTools(toolsMenu.hidden));
  const modes = [
    {value: 'paper', label: 'modePaper', description: 'modePaperDescription'},
    {value: 'quick', label: 'modeQuick', description: 'modeQuickDescription'},
    {value: 'deep', label: 'modeDeep', description: 'modeDeepDescription'},
  ];
  function refreshModePresentation() {
    const selected = modes.find(mode => mode.value === modeField.value) || modes[0];
    const paperMode = selected.value === 'paper';
    const subtitle = document.querySelector('.chat-head .sub');
    if (paperMode) {
      delete subtitle.dataset.i18n;
      subtitle.innerHTML = paperStatusMarkup;
      settings.applyI18n(subtitle);
    } else {
      subtitle.dataset.i18n = selected.label;
      subtitle.textContent = settings.t(selected.label);
    }
    const question = form.querySelector('.question');
    question.dataset.i18nPlaceholder = paperMode ? 'questionPlaceholder' : 'webQuestionPlaceholder';
    question.placeholder = settings.t(question.dataset.i18nPlaceholder);
    const empty = content.querySelector('.empty');
    if (empty) {
      const heading = empty.querySelector('b');
      const hint = empty.querySelector('span');
      heading.dataset.i18n = paperMode ? 'emptyTitle' : 'emptyWebTitle';
      hint.dataset.i18n = paperMode ? 'emptyHint' : 'emptyWebHint';
      heading.textContent = settings.t(heading.dataset.i18n);
      hint.textContent = settings.t(hint.dataset.i18n);
    }
  }
  function setResearchMode(index) {
    const selected = modes[Math.max(0, Math.min(2, Number(index) || 0))];
    modeSlider.value = String(modes.indexOf(selected));
    modeSlider.setAttribute('aria-valuetext', settings.t(selected.label));
    modeSlider.style.setProperty('--mode-progress', `${modes.indexOf(selected) * 50}%`);
    modeField.value = selected.value;
    for (const [selector, key] of [['#mode-current', selected.label], ['#mode-heading', selected.label], ['#mode-description', selected.description]]) {
      const element = document.querySelector(selector);
      element.dataset.i18n = key;
      element.textContent = settings.t(key);
    }
    refreshModePresentation();
    try { localStorage.setItem('paper-agent-research-mode', selected.value); } catch (_) {}
  }
  function setModePanel(open) {
    modePanel.hidden = !open;
    modeToggle.setAttribute('aria-expanded', String(open));
  }
  let savedMode = 'paper';
  try { savedMode = localStorage.getItem('paper-agent-research-mode') || 'paper'; } catch (_) {}
  setResearchMode(Math.max(0, modes.findIndex(mode => mode.value === savedMode)));
  modeSlider.addEventListener('input', () => setResearchMode(modeSlider.value));
  modeToggle.addEventListener('click', () => setModePanel(modePanel.hidden));
  document.querySelectorAll('[data-tool]').forEach(button => button.addEventListener('click', () => {
    const panel = document.querySelector(`[data-tool-section="${button.dataset.tool}"]`);
    panel.hidden = !panel.hidden;
    button.setAttribute('aria-expanded', String(!panel.hidden));
  }));

  document.querySelector('.question').addEventListener('keydown', event => {
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
    const enterToSend = settings.get().sendMode === 'enter';
    if ((enterToSend && !event.ctrlKey && !event.metaKey) || (!enterToSend && (event.ctrlKey || event.metaKey))) {
      event.preventDefault();
      form.requestSubmit(form.querySelector('.send-button'));
    }
  });

  function appendPending(question) {
    const messages = content.querySelector('#messages');
    messages.querySelector('.empty')?.remove();
    const turn = document.createElement('article');
    turn.className = 'turn pending';
    const label = document.createElement('p');
    label.className = 'turn-title';
    label.textContent = settings.t('sentNow');
    const user = document.createElement('div');
    user.className = 'bubble user-bubble';
    user.textContent = question;
    const answer = document.createElement('div');
    answer.className = 'bubble assistant-bubble';
    const process = document.createElement('details');
    process.className = 'reasoning-process';
    process.open = settings.get().reasoningExpanded;
    const processTitle = document.createElement('summary');
    processTitle.dataset.i18n = 'reasoningTitle';
    processTitle.textContent = settings.t('reasoningTitle');
    const processSteps = document.createElement('ol');
    process.append(processTitle, processSteps);
    const thinking = document.createElement('span');
    thinking.className = 'thinking';
    thinking.textContent = settings.t('thinking');
    answer.append(thinking);
    turn.append(label, user, process, answer);
    messages.append(turn);
    scrollToLatest();
    return {answer, thinking, processSteps};
  }

  function appendProcessStep(list, step) {
    if (!step || typeof step.key !== 'string') return;
    const item = document.createElement('li');
    const label = document.createElement('span');
    label.dataset.i18n = step.key;
    for (const field of ['pages', 'position', 'model']) {
      if (step[field] !== undefined) label.dataset[field] = String(step[field]);
    }
    label.textContent = settings.t(step.key, step);
    item.append(label);
    list.append(item);
    scrollToLatest();
  }

  async function readStream(response, pending) {
    if (!response.body) throw new Error(settings.t('unrecognizedPage'));
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finished = null;
    let started = false;
    const renderer = window.chatMarkdown?.createLiveRenderer
      ? window.chatMarkdown.createLiveRenderer(pending.answer, content, () => settings.get().autoScroll)
      : createPlainTextRenderer(pending.answer);
    const live = createPacedRenderer(renderer);
    function eventLine(line) {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      if (event.type === 'status') {
        const [key, position] = event.message.split(':', 2);
        const message = settings.t(key, {position});
        status.textContent = message;
        if (!started) pending.thinking.textContent = message;
      } else if (event.type === 'process') {
        appendProcessStep(pending.processSteps, event.step);
      } else if (event.type === 'reset') {
        started = false;
        live.reset();
        pending.answer.replaceChildren(pending.thinking);
        pending.thinking.textContent = settings.t('thinking');
      } else if (event.type === 'delta') {
        if (!started) {
          started = true;
        }
        live.push(event.text);
      } else if (event.type === 'done') {
        finished = event;
      }
    }
    try {
      while (true) {
        const {value, done} = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
        let breakAt;
        while ((breakAt = buffer.indexOf('\n')) !== -1) {
          eventLine(buffer.slice(0, breakAt));
          buffer = buffer.slice(breakAt + 1);
        }
        if (done) break;
      }
      if (buffer.trim()) eventLine(buffer);
      if (!finished?.session_id) throw new Error(settings.t('unrecognizedPage'));
      await live.finish();
      return finished;
    } finally {
      live.dispose();
    }
  }

  function createPacedRenderer(renderer) {
    const queued = [];
    let timer = null;
    let finishDeadline = 0;
    let resolveFinish = null;

    function stopTimer() {
      if (timer !== null) clearInterval(timer);
      timer = null;
    }

    function tick() {
      const speed = settings.get().streamSpeed;
      let count = speed === 'instant' ? queued.length : speed === 'normal' ? 3 : 1;
      if (finishDeadline) {
        const ticksLeft = Math.max(1, Math.ceil((finishDeadline - Date.now()) / 40));
        count = Math.max(count, Math.ceil(queued.length / ticksLeft));
      }
      if (queued.length) renderer.push(queued.splice(0, count).join(''));
      if (!queued.length) {
        stopTimer();
        if (resolveFinish) {
          resolveFinish();
          resolveFinish = null;
        }
      }
    }

    function startTimer() {
      if (timer === null) timer = setInterval(tick, 40);
    }

    return {
      push(text) {
        if (settings.get().streamSpeed === 'instant' && !queued.length) {
          renderer.push(text);
          return;
        }
        for (const character of text) queued.push(character);
        startTimer();
      },
      reset() {
        queued.length = 0;
        finishDeadline = 0;
        stopTimer();
        renderer.reset();
      },
      finish() {
        if (!queued.length) return Promise.resolve();
        finishDeadline = Date.now() + 10000;
        startTimer();
        return new Promise(resolve => { resolveFinish = resolve; });
      },
      dispose() {
        stopTimer();
        if (resolveFinish) resolveFinish();
        renderer.dispose();
      },
    };
  }

  function createPlainTextRenderer(element) {
    let source = '';
    return {
      push(delta) {
        source += delta;
        element.textContent = source;
        scrollToLatest();
      },
      reset() {
        source = '';
        element.textContent = '';
      },
      dispose() {},
    };
  }

  function applyServerPage(markup) {
    const page = new DOMParser().parseFromString(markup, 'text/html');
    const nextContent = page.querySelector('#chat-content');
    const nextForm = page.querySelector('#composer');
    if (!nextContent || !nextForm) throw new Error(settings.t('unrecognizedPage'));
    closeSessionMenu();
    content.innerHTML = nextContent.innerHTML;
    document.querySelector('.session-list').innerHTML = page.querySelector('.session-list').innerHTML;
    document.querySelector('.chat-head h1').innerHTML = page.querySelector('.chat-head h1').innerHTML;
    document.querySelector('.chat-head .sub').innerHTML = page.querySelector('.chat-head .sub').innerHTML;
    paperStatusMarkup = document.querySelector('.chat-head .sub').innerHTML;
    const sessionId = nextForm.querySelector('[name="session_id"]').value;
    form.querySelector('[name="session_id"]').value = sessionId;
    search.querySelector('[name="session"]').value = sessionId;
    document.querySelector('.export-link').href = `/export?session=${encodeURIComponent(sessionId)}`;
    const paperButtonLabel = form.querySelector('[data-tool="paper"] span');
    const nextPaperButtonLabel = nextForm.querySelector('[data-tool="paper"] span');
    paperButtonLabel.dataset.i18n = nextPaperButtonLabel.dataset.i18n;
    paperButtonLabel.textContent = nextPaperButtonLabel.textContent;
    settings.applyI18n();
    refreshModePresentation();
    settings.applyProcessPreference(content);
    window.chatMarkdown?.typeset?.(content);
    history.replaceState(null, '', `/?session=${encodeURIComponent(sessionId)}`);
    scrollToLatest();
    return Boolean(nextContent.querySelector('.error'));
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    const questionField = form.querySelector('.question');
    const question = questionField.value.trim();
    if (!question) {
      status.textContent = settings.t('askFirst');
      questionField.focus();
      return;
    }
    const payload = new FormData(form);
    payload.set('action', 'ask');
    questionField.value = '';
    busy = true;
    form.querySelectorAll('button[type="submit"]').forEach(button => { button.disabled = true; });
    setTools(false);
    status.textContent = settings.t('answering');
    const pending = appendPending(question);
    try {
      const target = form.getAttribute('action');
      let response = await fetch(`${target}/stream`, {method: 'POST', body: payload, credentials: 'same-origin'});
      let hasError;
      let errorMessage = '';
      if (response.status === 404 || response.status === 405) {
        response = await fetch(target, {method: 'POST', body: payload, credentials: 'same-origin'});
        if (!response.ok) throw new Error(settings.t('serverReturned', {status: response.status}));
        hasError = applyServerPage(await response.text());
      } else {
        if (!response.ok) throw new Error(settings.t('serverReturned', {status: response.status}));
        const finished = await readStream(response, pending);
        const page = await fetch(`/?session=${encodeURIComponent(finished.session_id)}`, {credentials: 'same-origin'});
        if (!page.ok) throw new Error(settings.t('serverReturned', {status: page.status}));
        hasError = applyServerPage(await page.text()) || finished.error;
        errorMessage = finished.message || '';
      }
      if (hasError) {
        if (!questionField.value) questionField.value = question;
        status.textContent = errorMessage || settings.t('requestFailed');
      } else {
        form.querySelector('#paper_file').value = '';
        form.querySelector('#paper_text').value = '';
        status.textContent = '';
      }
    } catch (error) {
      if (!questionField.value) questionField.value = question;
      pending.answer.textContent = settings.t('sendFailed', {message: error.message});
      status.textContent = settings.t('connectionFailed');
    } finally {
      busy = false;
      form.querySelectorAll('button[type="submit"]').forEach(button => { button.disabled = false; });
      questionField.focus();
    }
  });

  document.addEventListener('toggle', event => {
    if (!event.target.matches('.session-menu')) return;
    if (event.target.open) openSessionMenu(event.target);
    else if (event.target === activeSessionMenu) closeSessionMenu();
  }, true);
  document.addEventListener('click', event => {
    if (!event.target.closest('.session-menu') && !event.target.closest('.menu-panel')) closeSessionMenu();
    if (!event.target.closest('#tools-menu') && !event.target.closest('#tools-toggle')) setTools(false);
    if (!event.target.closest('.mode-picker')) setModePanel(false);
    const rename = event.target.closest('[data-rename]');
    if (rename) {
      const renameForm = rename.nextElementSibling;
      renameForm.hidden = false;
      renameForm.querySelector('input[name="title"]').focus();
    }
  });
  document.addEventListener('submit', event => {
    if (event.target.matches('.delete-form') && !window.confirm(settings.t('confirmDelete'))) event.preventDefault();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      setTools(false);
      setModePanel(false);
      closeSessionMenu();
    }
  });
  window.addEventListener('resize', closeSessionMenu);
  document.querySelector('.session-list').addEventListener('scroll', closeSessionMenu);
})();
