(function () {
  var form = document.getElementById('composer');
  if (!form) return;
  var input = document.getElementById('input');
  var sendBtn = document.getElementById('send');
  var messages = document.getElementById('messages');
  var csrf = document.querySelector('meta[name=csrf-token]').content;

  function scrollDown() { messages.scrollTop = messages.scrollHeight; }

  function addMessage(role, html, isText) {
    var empty = messages.querySelector('.empty-chat');
    if (empty) empty.remove();
    var wrap = document.createElement('div');
    wrap.className = 'msg msg-' + role;
    var bubble = document.createElement('div');
    bubble.className = 'bubble';
    if (isText) {
      var p = document.createElement('div');
      p.className = 'plain';
      p.textContent = html;
      bubble.appendChild(p);
    } else {
      bubble.innerHTML = html; // server-sanitized HTML
      if (role === 'assistant') bubble.appendChild(copyButton());
    }
    wrap.appendChild(bubble);
    messages.appendChild(wrap);
    scrollDown();
    return wrap;
  }

  function copyButton() {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'copy'; b.textContent = 'Copy';
    return b;
  }

  messages.addEventListener('click', function (e) {
    if (e.target.classList.contains('copy')) {
      var bubble = e.target.parentElement.cloneNode(true);
      bubble.querySelector('.copy').remove();
      navigator.clipboard.writeText(bubble.innerText.trim()).then(function () {
        e.target.textContent = 'Copied'; setTimeout(function () { e.target.textContent = 'Copy'; }, 1500);
      });
    }
    if (e.target.dataset.suggest) {
      input.value = e.target.dataset.suggest;
      input.focus();
    }
  });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    addMessage('user', text, true);
    input.value = '';
    sendBtn.disabled = true;
    var thinking = addMessage('assistant', '<div class="typing"><span></span><span></span><span></span></div>');

    fetch(form.dataset.sendUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify({ message: text, conversation_id: form.dataset.conversation || null })
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        thinking.remove();
        if (res.data.conversation_id && !form.dataset.conversation) {
          form.dataset.conversation = res.data.conversation_id;
          if (res.data.url) history.replaceState(null, '', res.data.url);
        }
        if (!res.ok) { addMessage('error', res.data.error || 'Something went wrong.', true); return; }
        addMessage('assistant', res.data.reply_html);
      })
      .catch(function () {
        thinking.remove();
        addMessage('error', 'Network error — please try again.', true);
      })
      .finally(function () { sendBtn.disabled = false; input.focus(); });
  });

  scrollDown();
})();
