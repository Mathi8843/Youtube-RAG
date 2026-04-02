const BASE_URL = 'https://youtube-rag-production.up.railway.app';

// ── State ──────────────────────────────────────────────────────────────────
const knowledgeBase = [];    // [{ video_id, video_title, video_url }]
let activeVideoIds = [];    // [] = all videos, else filtered list

// ── DOM ────────────────────────────────────────────────────────────────────
const viewLanding = document.getElementById('view-landing');
const viewInput = document.getElementById('view-input');
const viewChat = document.getElementById('view-chat');

const navCta = document.getElementById('nav-cta');
const heroCta = document.getElementById('hero-cta-btn');
const backToLanding = document.getElementById('back-to-landing');
const backToInput = document.getElementById('back-to-input');

const urlForm = document.getElementById('url-form');
const youtubeUrl = document.getElementById('youtube-url');
const setupError = document.getElementById('setup-error');
const addBtn = document.getElementById('add-btn');

const loader = document.getElementById('loader');
const loaderMsg = document.getElementById('loader-message');

const videoList = document.getElementById('video-list');
const videoCount = document.getElementById('video-count');
const startChatBtn = document.getElementById('start-chat-btn');

const chatHistory = document.getElementById('chat-history');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatError = document.getElementById('chat-error');
const sendBtn = document.getElementById('send-btn');
const videoFilters = document.getElementById('video-filters');

const notesBtn = document.getElementById('notes-btn');
const momentsBtn = document.getElementById('moments-btn');
const toolsHint = document.getElementById('tools-hint');

// ── View Switching ─────────────────────────────────────────────────────────
function showView(view) {
  [viewLanding, viewInput, viewChat].forEach(v => v.classList.remove('view--active'));
  view.classList.add('view--active');
  window.scrollTo(0, 0);
}

navCta.addEventListener('click', (e) => { e.preventDefault(); showView(viewInput); });
heroCta.addEventListener('click', () => showView(viewInput));
backToLanding.addEventListener('click', () => showView(viewLanding));
backToInput.addEventListener('click', () => showView(viewInput));

// ── Example Pills ──────────────────────────────────────────────────────────
document.querySelectorAll('.pill').forEach(p => {
  p.addEventListener('click', () => { youtubeUrl.value = p.dataset.url; youtubeUrl.focus(); });
});

// ── Add Video to Knowledge Base ────────────────────────────────────────────
urlForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const url = youtubeUrl.value.trim();
  if (!url) return;

  setupError.textContent = '';
  loaderMsg.textContent = 'Extracting transcript & indexing with timestamps…';
  loader.classList.add('active');
  addBtn.disabled = true;

  try {
    const res = await fetch(`${BASE_URL}/api/process-video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to process video.');
    }

    const data = await res.json();

    // Avoid duplicates in local KB
    if (!knowledgeBase.find(v => v.video_id === data.video_id)) {
      knowledgeBase.push({
        video_id: data.video_id,
        video_title: data.video_title,
        video_url: data.video_url
      });
      renderVideoList();
    }

    youtubeUrl.value = '';

  } catch (err) {
    setupError.textContent = err.message;
  } finally {
    loader.classList.remove('active');
    addBtn.disabled = false;
  }
});

// ── Render Knowledge Base List ─────────────────────────────────────────────
function renderVideoList() {
  videoCount.textContent = `${knowledgeBase.length} video${knowledgeBase.length !== 1 ? 's' : ''}`;
  startChatBtn.disabled = knowledgeBase.length === 0;

  if (knowledgeBase.length === 0) {
    videoList.innerHTML = `
      <div class="video-list__empty">
        <div style="font-size:2.5rem;margin-bottom:12px;">🎬</div>
        <div>No videos added yet.</div>
        <div style="font-size:0.8rem;color:var(--muted);margin-top:6px;">Add a YouTube URL to get started.</div>
      </div>`;
    return;
  }

  videoList.innerHTML = knowledgeBase.map(v => `
    <div class="video-card">
      <div class="video-card__thumb">▶</div>
      <div class="video-card__info">
        <div class="video-card__title" title="${escHtml(v.video_title)}">${escHtml(v.video_title)}</div>
        <div class="video-card__url">${escHtml(v.video_url)}</div>
      </div>
      <div class="video-card__check">✓</div>
    </div>`).join('');
}

// ── Start Chat ─────────────────────────────────────────────────────────────
startChatBtn.addEventListener('click', () => {
  activeVideoIds = []; // search ALL by default
  renderFilterChips();

  // Reset chat to welcome
  chatHistory.innerHTML = `
    <div class="message ai-msg">
      <div class="msg-avatar">AI</div>
      <div class="msg-content">
        <div class="msg-bubble">
          Hello! I've indexed <strong>${knowledgeBase.length} video${knowledgeBase.length !== 1 ? 's' : ''}</strong> in your knowledge base.
          Ask anything — I'll search across all videos and show you the <strong>exact timestamps</strong> where each answer comes from.
        </div>
      </div>
    </div>`;
  chatError.textContent = '';
  showView(viewChat);
  setTimeout(() => chatInput.focus(), 300);
});

// ── Filter Chips ───────────────────────────────────────────────────────────
function renderFilterChips() {
  videoFilters.innerHTML = '';

  // "All videos" chip
  const allChip = makeChip('All Videos', activeVideoIds.length === 0);
  allChip.addEventListener('click', () => {
    activeVideoIds = [];
    renderFilterChips();
  });
  videoFilters.appendChild(allChip);

  // Per-video chips
  knowledgeBase.forEach(v => {
    const isActive = activeVideoIds.includes(v.video_id);
    const chip = makeChip('▶ ' + truncate(v.video_title, 24), isActive);
    chip.addEventListener('click', () => {
      if (activeVideoIds.includes(v.video_id)) {
        activeVideoIds = activeVideoIds.filter(id => id !== v.video_id);
      } else {
        activeVideoIds.push(v.video_id);
      }
      // If nothing selected => go to All
      if (activeVideoIds.length === 0) activeVideoIds = [];
      renderFilterChips();
    });
    videoFilters.appendChild(chip);
  });
}

function makeChip(label, active) {
  const el = document.createElement('button');
  el.className = 'filter-chip' + (active ? ' active' : '');
  el.type = 'button';
  el.textContent = label;
  return el;
}

// ── Send Chat Message ──────────────────────────────────────────────────────
chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;

  chatError.textContent = '';
  appendUserMessage(question);
  chatInput.value = '';
  sendBtn.disabled = true;

  const thinkingId = appendTyping();

  try {
    const payload = { question };
    // Only send video_ids if user is filtering (not "All")
    if (activeVideoIds.length > 0) payload.video_ids = activeVideoIds;

    const res = await fetch(`${BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to get response.');
    }

    const data = await res.json();
    replaceTypingWithAnswer(thinkingId, data.answer, data.sources || []);

  } catch (err) {
    replaceTypingWithAnswer(thinkingId, '⚠️ ' + err.message, []);
    chatError.textContent = err.message;
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
});

// ── Message Helpers ────────────────────────────────────────────────────────
function appendUserMessage(text) {
  const div = document.createElement('div');
  div.className = 'message user-msg';
  div.innerHTML = `
    <div class="msg-avatar">You</div>
    <div class="msg-content">
      <div class="msg-bubble">${escHtml(text)}</div>
    </div>`;
  chatHistory.appendChild(div);
  scrollChat();
}

function appendTyping() {
  const id = 'msg-' + Date.now();
  const div = document.createElement('div');
  div.id = id;
  div.className = 'message ai-msg';
  div.innerHTML = `
    <div class="msg-avatar">AI</div>
    <div class="msg-content">
      <div class="msg-bubble">
        <div class="typing-dots"><span></span><span></span><span></span></div>
      </div>
    </div>`;
  chatHistory.appendChild(div);
  scrollChat();
  return id;
}

function replaceTypingWithAnswer(id, answer, sources) {
  const el = document.getElementById(id);
  if (!el) return;

  const sourcesHtml = buildSourcesHtml(sources);

  el.querySelector('.msg-content').innerHTML = `
    <div class="msg-bubble">${escHtml(answer)}</div>
    ${sourcesHtml}`;
  scrollChat();
}

function buildSourcesHtml(sources) {
  if (!sources || sources.length === 0) return '';

  const items = sources.map(s => `
    <a class="source-item" href="${escHtml(s.timestamp_url)}" target="_blank" rel="noopener" title="Jump to ${s.timestamp} in: ${escHtml(s.video_title)}">
      <span class="source-item__ts">⏱ ${escHtml(s.timestamp)}</span>
      <span class="source-item__title">${escHtml(s.video_title)}</span>
      <span class="source-item__arrow">↗</span>
    </a>`).join('');

  return `
    <div class="msg-sources">
      <div class="sources-label">📍 Sources</div>
      ${items}
    </div>`;
}

// ── Tool: Generate Notes ───────────────────────────────────────────────────
notesBtn.addEventListener('click', async () => {
  notesBtn.disabled = true;
  momentsBtn.disabled = true;
  toolsHint.textContent = 'Generating notes…';

  const thinkingId = appendToolThinking('📝 Generating structured study notes…');

  try {
    const payload = {};
    if (activeVideoIds.length > 0) payload.video_ids = activeVideoIds;

    const res = await fetch(`${BASE_URL}/api/generate-notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }

    const { notes } = await res.json();
    replaceToolThinking(thinkingId, buildNotesCard(notes));

  } catch (err) {
    replaceToolThinking(thinkingId, `<div class="msg-bubble">⚠️ ${escHtml(err.message)}</div>`);
  } finally {
    notesBtn.disabled = false;
    momentsBtn.disabled = false;
    toolsHint.textContent = '';
  }
});

// ── Tool: Key Moments ──────────────────────────────────────────────────────
momentsBtn.addEventListener('click', async () => {
  // Key Moments requires a single video
  const candidates = activeVideoIds.length > 0 ? activeVideoIds : knowledgeBase.map(v => v.video_id);
  if (candidates.length === 0) {
    toolsHint.textContent = '⚠ Add a video first.';
    return;
  }
  const videoId = candidates[0];
  const videoTitle = knowledgeBase.find(v => v.video_id === videoId)?.video_title || videoId;

  if (candidates.length > 1) {
    toolsHint.textContent = `Using: "${truncate(videoTitle, 32)}"`;
  }

  notesBtn.disabled = true;
  momentsBtn.disabled = true;

  const thinkingId = appendToolThinking(`🎯 Finding key moments in "${truncate(videoTitle, 36)}"…`);

  try {
    const res = await fetch(`${BASE_URL}/api/key-moments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_id: videoId })
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail); }

    const { moments } = await res.json();
    replaceToolThinking(thinkingId, buildMomentsCard(moments, videoTitle));

  } catch (err) {
    replaceToolThinking(thinkingId, `<div class="msg-bubble">⚠️ ${escHtml(err.message)}</div>`);
  } finally {
    notesBtn.disabled = false;
    momentsBtn.disabled = false;
    toolsHint.textContent = '';
  }
});

// ── Tool Helper: append a "thinking" tool block ────────────────────────────
function appendToolThinking(label) {
  const id = 'tool-' + Date.now();
  const div = document.createElement('div');
  div.id = id;
  div.className = 'message ai-msg';
  div.style.maxWidth = '100%';
  div.innerHTML = `
    <div class="msg-avatar">AI</div>
    <div class="msg-content" style="flex:1;">
      <div class="msg-bubble" style="display:flex;align-items:center;gap:12px;">
        <div class="typing-dots"><span></span><span></span><span></span></div>
        <span style="color:var(--muted);font-size:0.85rem;">${escHtml(label)}</span>
      </div>
    </div>`;
  chatHistory.appendChild(div);
  scrollChat();
  return id;
}

function replaceToolThinking(id, innerHtml) {
  const el = document.getElementById(id);
  if (el) {
    el.querySelector('.msg-content').innerHTML = innerHtml;
    scrollChat();
  }
}

// ── Build Notes Card HTML ──────────────────────────────────────────────────
function buildNotesCard(markdown) {
  const html = simpleMarkdown(markdown);
  return `
    <div class="notes-card">
      <div class="notes-card__header">
        <div class="notes-card__title">📝 Video Study Notes</div>
        <button class="copy-btn" onclick="copyNotes(this)">Copy</button>
      </div>
      <div class="notes-body">${html}</div>
    </div>`;
}

// ── Build Key Moments Card HTML ────────────────────────────────────────────
function buildMomentsCard(moments, videoTitle) {
  const items = moments.map(m => `
    <a class="moment-item" href="${escHtml(m.timestamp_url)}" target="_blank" rel="noopener">
      <span class="moment-ts">▶ ${escHtml(m.timestamp)}</span>
      <div class="moment-info">
        <div class="moment-title">${escHtml(m.title)}</div>
        <div class="moment-desc">${escHtml(m.description)}</div>
      </div>
      <span class="moment-arrow">↗</span>
    </a>`).join('');

  return `
    <div class="moments-card">
      <div class="moments-card__title">🎯 Key Moments — ${escHtml(truncate(videoTitle, 48))}</div>
      ${items}
    </div>`;
}

// ── Copy Notes ─────────────────────────────────────────────────────────────
window.copyNotes = (btn) => {
  const card = btn.closest('.notes-card');
  const text = card.querySelector('.notes-body').innerText;
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
  });
};

// ── Simple Markdown → HTML (for notes output) ─────────────────────────────
function simpleMarkdown(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`)
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/^(?!<[hul])(.+)$/gm, '<p>$1</p>')
    .replace(/<p><\/p>/g, '');
}

function scrollChat() {
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function truncate(str, n) {
  return str.length > n ? str.slice(0, n - 1) + '…' : str;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
