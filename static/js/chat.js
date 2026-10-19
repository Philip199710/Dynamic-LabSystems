(function () {
  "use strict";
  var root = document.getElementById("chat");
  if (!root) return;
  var list = document.getElementById("chat-list");
  var stream = document.getElementById("chat-stream");
  var empty = document.getElementById("chat-empty");
  var olderBtn = document.getElementById("chat-older");
  var form = document.getElementById("chat-compose");
  var input = document.getElementById("chat-input");
  var live = document.getElementById("chat-live");
  var messagesUrl = root.dataset.messagesUrl;
  var sendUrl = root.dataset.sendUrl;
  var channelId = root.dataset.channel;
  var lastId = 0, firstId = null, lastAuthor = null, lastIso = null, lastDate = null;
  var seen = {};
  var failures = 0, timer = null, busy = false;

  function csrf() {
    var el = document.querySelector("#chat-compose [name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }
  function nearBottom() { return stream.scrollHeight - stream.scrollTop - stream.clientHeight < 120; }
  function toBottom() { stream.scrollTop = stream.scrollHeight; }
  function escapeText(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

  function build(m, prev) {
    var frag = document.createDocumentFragment();
    if (!prev || prev.date !== m.date) {
      var day = document.createElement("div");
      day.className = "chat-day"; day.textContent = m.date;
      frag.appendChild(day);
    }
    var cont = prev && prev.date === m.date && prev.author_id === m.author_id &&
      (new Date(m.iso) - new Date(prev.iso)) < 5 * 60 * 1000;
    var row = document.createElement("div");
    row.className = "chat-msg" + (m.mine ? " mine" : "") + (cont ? " cont" : "");
    row.dataset.id = m.id;
    row.innerHTML =
      '<div class="chat-avatar">' + escapeText(m.initials) + '</div>' +
      '<div><div class="chat-meta"><strong>' + escapeText(m.author) + '</strong><time datetime="' + m.iso + '">' + m.time + '</time></div>' +
      '<div class="chat-text">' + m.html + '</div></div>';
    if (cont) row.title = m.time;
    frag.appendChild(row);
    return frag;
  }

  function append(msgs) {
    var stick = nearBottom();
    msgs.forEach(function (m) {
      if (seen[m.id]) return;
      seen[m.id] = true;
      var prev = lastIso ? { date: lastDate, author_id: lastAuthor, iso: lastIso } : null;
      list.appendChild(build(m, prev));
      lastId = Math.max(lastId, m.id); lastAuthor = m.author_id; lastIso = m.iso; lastDate = m.date;
      if (firstId === null) firstId = m.id;
    });
    empty.hidden = list.children.length > 0;
    if (stick) toBottom();
  }

  function prepend(msgs) {
    if (!msgs.length) return;
    var before = stream.scrollHeight;
    // Re-render everything so date dividers and grouping stay correct.
    var existing = Array.prototype.slice.call(list.querySelectorAll(".chat-msg")).length;
    var all = msgs.concat(cache);
    cache = all;
    list.innerHTML = ""; seen = {}; lastId = 0; lastIso = null; firstId = null;
    append(all);
    stream.scrollTop = stream.scrollHeight - before;
    return existing;
  }

  var cache = JSON.parse(document.getElementById("chat-initial").textContent);
  append(cache);
  toBottom();
  if (root.dataset.hasOlder === "1") olderBtn.hidden = false;

  olderBtn.addEventListener("click", function () {
    if (firstId === null) return;
    olderBtn.disabled = true;
    fetch(messagesUrl + "?before=" + firstId, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) { prepend(d.messages); olderBtn.hidden = !d.has_older; })
      .finally(function () { olderBtn.disabled = false; });
  });

  function setUnread(map) {
    document.querySelectorAll("[data-channel-link]").forEach(function (a) {
      var id = a.getAttribute("data-channel-link");
      if (id === channelId) return;
      var n = map[id] || 0, pill = a.querySelector(".chat-unread");
      pill.textContent = n; pill.hidden = !n;
      a.classList.toggle("has-unread", n > 0);
    });
    var total = Object.keys(map).reduce(function (s, k) { return s + (map[k] || 0); }, 0);
    var badge = document.getElementById("nav-chat-badge");
    if (badge) { badge.textContent = total; badge.hidden = !total; }
  }

  function poll() {
    if (busy) return schedule();
    busy = true;
    fetch(messagesUrl + "?after=" + lastId, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        failures = 0; live.classList.remove("off"); live.lastChild.nodeValue = "Live";
        if (d.messages.length) { cache = cache.concat(d.messages); append(d.messages); }
        setUnread(d.unread || {});
      })
      .catch(function () {
        failures += 1; live.classList.add("off"); live.lastChild.nodeValue = "Reconnecting…";
      })
      .finally(function () { busy = false; schedule(); });
  }
  function schedule() {
    clearTimeout(timer);
    var base = document.hidden ? 15000 : 3000;
    timer = setTimeout(poll, Math.min(base * Math.pow(2, failures), 60000));
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) poll(); });
  schedule();

  if (!form) return;
  function autosize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 160) + "px"; }
  input.addEventListener("input", autosize);
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
  });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var body = input.value.trim();
    if (!body) return;
    var data = new FormData(); data.append("body", body);
    input.value = ""; autosize();
    var btn = document.getElementById("chat-send"); btn.disabled = true;
    fetch(sendUrl, { method: "POST", body: data, credentials: "same-origin", headers: { "X-CSRFToken": csrf() } })
      .then(function (r) { return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || "Send failed"); return d; }); })
      .then(function (d) { cache.push(d.message); append([d.message]); toBottom(); })
      .catch(function (err) { input.value = body; autosize(); var hint = document.querySelector(".chat-hint"); if (hint) { hint.textContent = (err.message || "Message not sent") + " — check your connection and press Enter to retry."; hint.style.color = "var(--red-dark)"; } })
      .finally(function () { btn.disabled = false; input.focus(); });
  });
  input.focus();
})();
