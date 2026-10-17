(() => {
  const STORAGE_KEY = 'paper-agent-settings-v1';
  const defaults = {language: 'zh-CN', theme: 'system', fontSize: 'normal', streamSpeed: 'slow', sendMode: 'enter', autoScroll: true, reasoningExpanded: true, reduceMotion: false};
  const translations = {
    'zh-CN': {
      brand: '论文阅读 Agent', searchChats: '搜索对话', hideSidebar: '隐藏侧栏', showSidebar: '显示侧栏',
      searchPlaceholder: '搜索问题、回答或轮次', search: '搜索', showAll: '显示全部', newChat: '新对话',
      chatHistory: '对话记录', noChats: '暂无对话', loadChatFile: '加载对话文件', loadAndContinue: '加载并续聊',
      settings: '设置', closeSettings: '关闭设置', settingsCategories: '设置分类', settingsGeneral: '一般', settingsAppearance: '外观', settingsResponses: '回答', interfaceLanguage: '界面语言',
      theme: '外观主题', themeSystem: '跟随系统', themeLight: '浅色', themeDark: '深色',
      fontSize: '文字大小', fontSmall: '较小', fontNormal: '标准', fontLarge: '较大',
      streamSpeed: '回答显示速度', streamSlow: '慢速', streamNormal: '标准', streamInstant: '即时',
      sendMode: '发送方式', sendWithEnter: 'Enter 发送', sendWithCtrlEnter: 'Ctrl+Enter 发送', autoScroll: '回答时自动滚动', reasoningExpanded: '展开思考过程', reduceMotion: '减少动画效果',
      turns: '轮对话', exportChat: '导出对话', imported: '已导入', noPaper: '未导入论文',
      addToChat: '添加到对话', importPaper: '导入论文', replacePaper: '更换论文', importFile: '导入 PDF、Markdown 或文本',
      orPaste: '或粘贴正文', pastePaper: '粘贴论文正文', modelSettings: '模型与参数设置', model: '模型',
      evidenceCount: '证据数', addPaperOrSettings: '添加论文或调整参数', questionPlaceholder: '问这篇论文的任何问题…',
      questionInput: '输入问题', sendQuestion: '发送问题',
      modeLabel: '搜索模式', modePaper: '论文阅读', modeQuick: '快速搜索', modeDeep: '深度研究', modePaperShort: '论文', modeQuickShort: '快搜', modeDeepShort: '深研',
      modePaperDescription: '依据已导入论文回答', modeQuickDescription: '检索一次，直接展示来源与摘要', modeDeepDescription: '多源搜索、筛选、重排并提取内容块',
      webQuestionPlaceholder: '搜索网络上的任何问题…', emptyWebTitle: '开始搜索', emptyWebHint: '选择快速搜索或深度研究，然后输入问题。',
      emptyTitle: '开始阅读', emptyHint: '导入或粘贴论文，然后提出问题。', noResults: '没有找到对应轮次',
      noResultsHint: '试试问题关键词或轮次编号。', rename: '重命名', save: '保存', delete: '删除',
      conversationActions: '对话操作', conversationName: '对话名称', autoModel: '自动',
      sentNow: '刚刚发送', thinking: '正在生成回答…', askFirst: '请先输入问题。', answering: '正在回答…',
      reasoningTitle: '思考过程', processPaperPages: '读取论文，共 {pages} 页', processPaperSections: '读取论文，共 {pages} 节', processEvidence: '检索相关内容：{pages}', processRoute: '选择模型：{model}', processReading: '阅读论文并分析问题', processPart: '阅读论文片段 {position}', processCombine: '整理各段阅读笔记', processDraft: '整合证据并撰写回答', processOffline: '根据检索结果整理回答', processFallback: '切换至本地阅读流程', processDone: '回答完成',
      readingPaper: '正在阅读论文并生成回答…', retrievingPart: '正在检索论文第 {position} 段…', organizingEvidence: '正在整理证据并生成回答…',
      researchSearching: '正在搜索资料…', researchFiltering: '正在筛选来源…', researchReranking: '正在重排结果…', researchExtracting: '正在提取内容块…', researchWriting: '正在整理研究回答…',
      processSearch: '搜索来源：{position}', processFilter: '筛选来源：{position}', processRerank: '重排结果：{position}', processExtract: '提取内容块：{position}', processResearchDraft: '根据来源撰写回答',
      unrecognizedPage: '服务器返回了无法识别的页面。', serverReturned: '服务器返回 {status}',
      requestFailed: '请求未完成，请查看上方错误信息。', sendFailed: '发送失败：{message}', connectionFailed: '连接失败，请重试。',
      confirmDelete: '确定删除这个对话吗？原始调用日志会保留。', turnPrefix: '第', turnSuffix: '轮',
    },
    'zh-TW': {
      brand: '論文閱讀 Agent', searchChats: '搜尋對話', hideSidebar: '隱藏側欄', showSidebar: '顯示側欄',
      searchPlaceholder: '搜尋問題、回答或回合', search: '搜尋', showAll: '顯示全部', newChat: '新對話',
      chatHistory: '對話紀錄', noChats: '暫無對話', loadChatFile: '載入對話檔案', loadAndContinue: '載入並續聊',
      settings: '設定', closeSettings: '關閉設定', settingsCategories: '設定分類', settingsGeneral: '一般', settingsAppearance: '外觀', settingsResponses: '回答', interfaceLanguage: '介面語言',
      theme: '外觀主題', themeSystem: '跟隨系統', themeLight: '淺色', themeDark: '深色',
      fontSize: '文字大小', fontSmall: '較小', fontNormal: '標準', fontLarge: '較大',
      streamSpeed: '回答顯示速度', streamSlow: '慢速', streamNormal: '標準', streamInstant: '即時',
      sendMode: '傳送方式', sendWithEnter: 'Enter 傳送', sendWithCtrlEnter: 'Ctrl+Enter 傳送', autoScroll: '回答時自動捲動', reasoningExpanded: '展開思考過程', reduceMotion: '減少動畫效果',
      turns: '回合對話', exportChat: '匯出對話', imported: '已匯入', noPaper: '尚未匯入論文',
      addToChat: '加入對話', importPaper: '匯入論文', replacePaper: '更換論文', importFile: '匯入 PDF、Markdown 或文字',
      orPaste: '或貼上正文', pastePaper: '貼上論文正文', modelSettings: '模型與參數設定', model: '模型',
      evidenceCount: '證據數', addPaperOrSettings: '加入論文或調整參數', questionPlaceholder: '詢問這篇論文的任何問題…',
      questionInput: '輸入問題', sendQuestion: '傳送問題',
      modeLabel: '搜尋模式', modePaper: '論文閱讀', modeQuick: '快速搜尋', modeDeep: '深度研究', modePaperShort: '論文', modeQuickShort: '快搜', modeDeepShort: '深研',
      modePaperDescription: '依據已匯入論文回答', modeQuickDescription: '檢索一次，直接展示來源與摘要', modeDeepDescription: '多源搜尋、篩選、重排並提取內容塊',
      webQuestionPlaceholder: '搜尋網路上的任何問題…', emptyWebTitle: '開始搜尋', emptyWebHint: '選擇快速搜尋或深度研究，然後輸入問題。',
      emptyTitle: '開始閱讀', emptyHint: '匯入或貼上論文，然後提出問題。', noResults: '找不到對應回合',
      noResultsHint: '試試問題關鍵詞或回合編號。', rename: '重新命名', save: '儲存', delete: '刪除',
      conversationActions: '對話操作', conversationName: '對話名稱', autoModel: '自動',
      sentNow: '剛剛傳送', thinking: '正在產生回答…', askFirst: '請先輸入問題。', answering: '正在回答…',
      reasoningTitle: '思考過程', processPaperPages: '讀取論文，共 {pages} 頁', processPaperSections: '讀取論文，共 {pages} 節', processEvidence: '檢索相關內容：{pages}', processRoute: '選擇模型：{model}', processReading: '閱讀論文並分析問題', processPart: '閱讀論文片段 {position}', processCombine: '整理各段閱讀筆記', processDraft: '整合證據並撰寫回答', processOffline: '根據檢索結果整理回答', processFallback: '切換至本地閱讀流程', processDone: '回答完成',
      readingPaper: '正在閱讀論文並產生回答…', retrievingPart: '正在檢索論文第 {position} 段…', organizingEvidence: '正在整理證據並產生回答…',
      researchSearching: '正在搜尋資料…', researchFiltering: '正在篩選來源…', researchReranking: '正在重排結果…', researchExtracting: '正在提取內容塊…', researchWriting: '正在整理研究回答…',
      processSearch: '搜尋來源：{position}', processFilter: '篩選來源：{position}', processRerank: '重排結果：{position}', processExtract: '提取內容塊：{position}', processResearchDraft: '根據來源撰寫回答',
      unrecognizedPage: '伺服器傳回無法辨識的頁面。', serverReturned: '伺服器傳回 {status}',
      requestFailed: '請求未完成，請查看上方錯誤訊息。', sendFailed: '傳送失敗：{message}', connectionFailed: '連線失敗，請重試。',
      confirmDelete: '確定刪除這個對話嗎？原始呼叫日誌會保留。', turnPrefix: '第', turnSuffix: '回合',
    },
    en: {
      brand: 'Paper Reading Agent', searchChats: 'Search chats', hideSidebar: 'Hide sidebar', showSidebar: 'Show sidebar',
      searchPlaceholder: 'Search questions, answers, or turns', search: 'Search', showAll: 'Show all', newChat: 'New chat',
      chatHistory: 'Chat history', noChats: 'No chats yet', loadChatFile: 'Load a chat file', loadAndContinue: 'Load and continue',
      settings: 'Settings', closeSettings: 'Close settings', settingsCategories: 'Settings categories', settingsGeneral: 'General', settingsAppearance: 'Appearance', settingsResponses: 'Responses', interfaceLanguage: 'Interface language',
      theme: 'Appearance', themeSystem: 'Use system setting', themeLight: 'Light', themeDark: 'Dark',
      fontSize: 'Text size', fontSmall: 'Small', fontNormal: 'Standard', fontLarge: 'Large',
      streamSpeed: 'Answer display speed', streamSlow: 'Slow', streamNormal: 'Standard', streamInstant: 'Instant',
      sendMode: 'Send message with', sendWithEnter: 'Enter', sendWithCtrlEnter: 'Ctrl+Enter', autoScroll: 'Auto-scroll responses', reasoningExpanded: 'Expand thought process', reduceMotion: 'Reduce motion',
      turns: 'turns', exportChat: 'Export chat', imported: 'Imported', noPaper: 'No paper imported',
      addToChat: 'Add to chat', importPaper: 'Import paper', replacePaper: 'Replace paper', importFile: 'Import PDF, Markdown, or text',
      orPaste: 'Or paste the paper', pastePaper: 'Paste paper text', modelSettings: 'Model and parameters', model: 'Model',
      evidenceCount: 'Evidence count', addPaperOrSettings: 'Add paper or adjust settings', questionPlaceholder: 'Ask anything about this paper…',
      questionInput: 'Enter a question', sendQuestion: 'Send question',
      modeLabel: 'Search mode', modePaper: 'Paper reading', modeQuick: 'Quick search', modeDeep: 'Deep research', modePaperShort: 'Paper', modeQuickShort: 'Quick', modeDeepShort: 'Deep',
      modePaperDescription: 'Answer from the imported paper', modeQuickDescription: 'Search once and show sources directly', modeDeepDescription: 'Search, filter, rerank, and extract source passages',
      webQuestionPlaceholder: 'Search or ask anything on the web…', emptyWebTitle: 'Start searching', emptyWebHint: 'Choose Quick search or Deep research, then enter a question.',
      emptyTitle: 'Start reading', emptyHint: 'Import or paste a paper, then ask a question.', noResults: 'No matching turns',
      noResultsHint: 'Try a keyword or turn number.', rename: 'Rename', save: 'Save', delete: 'Delete',
      conversationActions: 'Chat actions', conversationName: 'Chat title', autoModel: 'Auto',
      sentNow: 'Just sent', thinking: 'Generating an answer…', askFirst: 'Enter a question first.', answering: 'Generating an answer…',
      reasoningTitle: 'Thought process', processPaperPages: 'Read paper: {pages} pages', processPaperSections: 'Read paper: {pages} sections', processEvidence: 'Found relevant sections: {pages}', processRoute: 'Selected model: {model}', processReading: 'Reading the paper and analyzing the question', processPart: 'Reading section {position}', processCombine: 'Combining section notes', processDraft: 'Combining evidence and drafting the answer', processOffline: 'Preparing an answer from search results', processFallback: 'Switching to local reading', processDone: 'Answer complete',
      readingPaper: 'Reading the paper and generating an answer…', retrievingPart: 'Searching paper section {position}…', organizingEvidence: 'Organizing evidence and generating an answer…',
      researchSearching: 'Searching sources…', researchFiltering: 'Filtering sources…', researchReranking: 'Reranking results…', researchExtracting: 'Extracting content blocks…', researchWriting: 'Preparing the research answer…',
      processSearch: 'Searched: {position}', processFilter: 'Filtered sources: {position}', processRerank: 'Reranked results: {position}', processExtract: 'Extracted content blocks: {position}', processResearchDraft: 'Writing an answer from sources',
      unrecognizedPage: 'The server returned an unrecognized page.', serverReturned: 'Server returned {status}',
      requestFailed: 'The request did not finish. Check the error above.', sendFailed: 'Send failed: {message}', connectionFailed: 'Connection failed. Try again.',
      confirmDelete: 'Delete this chat? Original call logs will remain.', turnPrefix: 'Turn', turnSuffix: '',
    },
  };

  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return {
        language: ['zh-CN', 'zh-TW', 'en'].includes(saved.language) ? saved.language : defaults.language,
        theme: ['system', 'light', 'dark'].includes(saved.theme) ? saved.theme : defaults.theme,
        fontSize: ['small', 'normal', 'large'].includes(saved.fontSize) ? saved.fontSize : defaults.fontSize,
        streamSpeed: ['slow', 'normal', 'instant'].includes(saved.streamSpeed) ? saved.streamSpeed : defaults.streamSpeed,
        sendMode: ['enter', 'ctrl-enter'].includes(saved.sendMode) ? saved.sendMode :
          saved.enterToSend === false ? 'ctrl-enter' : defaults.sendMode,
        autoScroll: typeof saved.autoScroll === 'boolean' ? saved.autoScroll : defaults.autoScroll,
        reasoningExpanded: typeof saved.reasoningExpanded === 'boolean' ? saved.reasoningExpanded : defaults.reasoningExpanded,
        reduceMotion: typeof saved.reduceMotion === 'boolean' ? saved.reduceMotion : defaults.reduceMotion,
      };
    } catch (_) { return {...defaults}; }
  }

  let settings = load();
  const overlay = document.querySelector('#settings-overlay');
  const panel = document.querySelector('#settings-panel');
  const trigger = document.querySelector('#settings-trigger');
  const tabs = [...document.querySelectorAll('[data-settings-tab]')];
  const pages = [...document.querySelectorAll('[data-settings-page]')];
  const themeQuery = matchMedia('(prefers-color-scheme: dark)');

  function t(key, values = {}) {
    const template = translations[settings.language][key] || translations['zh-CN'][key] || key;
    return template.replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ''));
  }

  function applyI18n(root = document) {
    root.querySelectorAll('[data-i18n]').forEach(node => {
      node.textContent = t(node.dataset.i18n, {
        pages: node.dataset.pages, position: node.dataset.position, model: node.dataset.model,
      });
    });
    root.querySelectorAll('[data-i18n-placeholder]').forEach(node => { node.placeholder = t(node.dataset.i18nPlaceholder); });
    root.querySelectorAll('[data-i18n-aria]').forEach(node => { node.setAttribute('aria-label', t(node.dataset.i18nAria)); });
    root.querySelectorAll('[data-i18n-title]').forEach(node => { node.title = t(node.dataset.i18nTitle); });
  }

  function applyProcessPreference(root = document) {
    root.querySelectorAll('.reasoning-process').forEach(node => {
      node.open = settings.reasoningExpanded;
    });
  }

  function apply() {
    document.documentElement.lang = settings.language;
    document.title = t('brand');
    document.documentElement.dataset.theme = settings.theme === 'system' ? (themeQuery.matches ? 'dark' : 'light') : settings.theme;
    document.documentElement.dataset.fontSize = settings.fontSize;
    document.documentElement.dataset.reduceMotion = String(settings.reduceMotion);
    applyI18n();
  }

  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)); } catch (_) {}
    apply();
  }

  function selectTab(name, focus = false) {
    tabs.forEach(tab => {
      const active = tab.dataset.settingsTab === name;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && focus) tab.focus();
    });
    pages.forEach(page => { page.hidden = page.dataset.settingsPage !== name; });
  }

  function setPanel(open) {
    overlay.hidden = !open;
    trigger.setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('modal-open', open);
    if (open) selectTab('general', true);
    else if (document.activeElement && panel.contains(document.activeElement)) trigger.focus();
  }

  const controls = {
    language: document.querySelector('#setting-language'),
    theme: document.querySelector('#setting-theme'),
    fontSize: document.querySelector('#setting-font-size'),
    streamSpeed: document.querySelector('#setting-stream-speed'),
    sendMode: document.querySelector('#setting-send-mode'),
    autoScroll: document.querySelector('#setting-auto-scroll'),
    reasoningExpanded: document.querySelector('#setting-reasoning-expanded'),
    reduceMotion: document.querySelector('#setting-reduce-motion'),
  };
  for (const [key, control] of Object.entries(controls)) {
    if (!control) continue;
    if (control.type === 'checkbox') control.checked = settings[key];
    else control.value = settings[key];
    control.addEventListener('change', () => {
      settings = {...settings, [key]: control.type === 'checkbox' ? control.checked : control.value};
      save();
      if (key === 'reasoningExpanded') applyProcessPreference();
    });
  }
  tabs.forEach(tab => tab.addEventListener('click', () => selectTab(tab.dataset.settingsTab)));
  document.querySelector('.settings-nav').addEventListener('keydown', event => {
    if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const index = tabs.indexOf(document.activeElement);
    const direction = ['ArrowDown', 'ArrowRight'].includes(event.key) ? 1 : -1;
    selectTab(tabs[(index + direction + tabs.length) % tabs.length].dataset.settingsTab, true);
  });
  trigger.addEventListener('click', () => setPanel(overlay.hidden));
  document.querySelector('#settings-close').addEventListener('click', () => setPanel(false));
  overlay.addEventListener('click', event => { if (event.target === overlay) setPanel(false); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !overlay.hidden) setPanel(false);
    if (event.key !== 'Tab' || overlay.hidden) return;
    const focusable = [...panel.querySelectorAll('button, select, input')].filter(node => !node.closest('[hidden]'));
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  themeQuery.addEventListener('change', () => { if (settings.theme === 'system') apply(); });

  window.appSettings = {get: () => ({...settings}), t, applyI18n, applyProcessPreference, closePanel: () => setPanel(false)};
  apply();
  applyProcessPreference();
})();
