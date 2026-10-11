const form = document.querySelector('#chat-form');
const question = document.querySelector('#question');
const send = document.querySelector('#send');
const messages = document.querySelector('#messages');
const intro = document.querySelector('#intro');
const statusLabel = document.querySelector('#status-text');
const statusIndicator = document.querySelector('#status');
let ready = false;
let busy = false;

function message(label, text, kind = 'assistant') {
  const article = document.createElement('article');
  article.className = `message ${kind}`;
  const heading = document.createElement('p');
  heading.className = 'label';
  heading.textContent = label;
  const content = document.createElement('p');
  content.textContent = text;
  article.append(heading, content);
  messages.append(article);
  return article;
}

async function checkStatus() {
  try {
    const response = await fetch('/api/status');
    if (!response.ok) throw new Error('Server unavailable');
    const data = await response.json();
    ready = data.status === 'ready';
    statusIndicator.dataset.state = ready ? 'ready' : data.status;
    statusLabel.textContent = ready ? `${data.passages} passages · Ready` : data.status === 'error' ? 'Model setup failed. Check the terminal.' : 'Loading local models…';
  } catch {
    ready = false;
    statusLabel.textContent = 'Cannot reach the server.';
  }
  send.disabled = !ready || busy;
  if (!ready) setTimeout(checkStatus, 3000);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = question.value.trim();
  if (!text || !ready || busy) return;
  busy = true;
  send.disabled = true;
  document.querySelector('#clear').disabled = true;
  intro.hidden = true;
  message('YOU', text, 'user');
  question.value = '';
  const pending = message('BOOK COMPANION', 'Finding passages and reading the evidence…');
  pending.scrollIntoView({ behavior: 'smooth', block: 'center' });
  try {
    const response = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: text })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Please enter a question of up to 1,000 characters.');
    pending.querySelector('p:last-child').textContent = result.answer;
    if (result.sources.length) {
      const sources = document.createElement('div');
      sources.className = 'sources';
      const label = document.createElement('p');
      label.textContent = 'Retrieved chapter passages — check the evidence';
      sources.append(label);
      result.sources.forEach((source, index) => {
        const detail = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = `[${index + 1}] ${source.chapter} · ${source.title}`;
        const passage = document.createElement('p');
        passage.textContent = source.text;
        detail.append(summary, passage);
        sources.append(detail);
      });
      pending.append(sources);
    }
  } catch (error) {
    pending.querySelector('p:last-child').textContent = error.message;
    pending.classList.add('error');
  } finally {
    busy = false;
    send.disabled = !ready;
    document.querySelector('#clear').disabled = false;
    question.focus();
  }
});

question.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
document.querySelectorAll('[data-question]').forEach(button => button.addEventListener('click', () => {
  question.value = button.dataset.question;
  question.focus();
  if (ready && !busy) form.requestSubmit();
}));
document.querySelector('#clear').addEventListener('click', () => {
  if (busy) return;
  messages.replaceChildren();
  intro.hidden = false;
  question.value = '';
  question.focus();
});
checkStatus();
