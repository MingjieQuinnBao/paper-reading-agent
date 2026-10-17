(() => {
  const mathOptions = {
    delimiters: [
      {left: '$$', right: '$$', display: true},
      {left: '\\[', right: '\\]', display: true},
      {left: '\\(', right: '\\)', display: false},
      {left: '$', right: '$', display: false},
    ],
    throwOnError: false,
    trust: false,
    maxSize: 10,
    maxExpand: 1000,
  };

  function typeset(root) {
    if (typeof window.renderMathInElement !== 'function') return;
    window.renderMathInElement(root, mathOptions);
  }

  function createLiveRenderer(element, scroller, shouldScroll = () => true) {
    let source = '';
    let renderedLength = 0;
    let tail = null;
    let timer = null;
    let inFlight = false;
    let generation = 0;
    let disposed = false;
    let failed = false;

    function showTail() {
      if (!renderedLength) {
        element.textContent = source;
      } else {
        if (!tail) {
          tail = document.createElement('span');
          tail.className = 'stream-tail';
          element.append(tail);
        }
        tail.textContent = source.slice(renderedLength);
      }
      if (shouldScroll()) scroller.scrollTop = scroller.scrollHeight;
    }

    function schedule() {
      if (disposed || failed || timer || inFlight || !source) return;
      timer = setTimeout(() => {
        timer = null;
        renderLatest();
      }, 100);
    }

    async function renderLatest() {
      if (disposed || failed || inFlight || !source) return;
      const snapshot = source;
      const version = generation;
      inFlight = true;
      try {
        const response = await fetch('/api/render-markdown', {
          method: 'POST', headers: {'Content-Type': 'text/plain; charset=utf-8'},
          body: snapshot, credentials: 'same-origin',
        });
        if (!response.ok) throw new Error(`Markdown render ${response.status}`);
        const result = await response.json();
        if (disposed || version !== generation) return;
        element.innerHTML = result.html;
        element.classList.remove('streaming-raw');
        typeset(element);
        renderedLength = snapshot.length;
        tail = null;
        if (source.length > renderedLength) showTail();
        else if (shouldScroll()) scroller.scrollTop = scroller.scrollHeight;
      } catch (_) {
        if (version === generation && !disposed) {
          failed = true;
          renderedLength = 0;
          tail = null;
          element.textContent = source;
        }
      } finally {
        inFlight = false;
        if (source !== snapshot) schedule();
      }
    }

    return {
      push(delta) {
        if (disposed) return;
        source += delta;
        element.classList.add('streaming');
        if (!renderedLength) element.classList.add('streaming-raw');
        showTail();
        schedule();
      },
      reset() {
        generation += 1;
        clearTimeout(timer);
        timer = null;
        source = '';
        renderedLength = 0;
        tail = null;
        element.textContent = '';
        element.classList.remove('streaming-raw');
      },
      dispose() {
        disposed = true;
        generation += 1;
        clearTimeout(timer);
      },
    };
  }

  window.chatMarkdown = {typeset, createLiveRenderer};
  typeset(document.querySelector('#chat-content'));
})();
