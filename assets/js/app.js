/* Book Factory — client-side behaviour.
   Two jobs: keep the spec readout in sync while the person fills the form,
   and poll the build status until the book is done. */

(function () {
  'use strict';

  /* --- Order form: live imposition readout -------------------------------- */

  var sheet = document.getElementById('spec-sheet');
  var chapterInput = document.getElementById('chapters');

  if (sheet && chapterInput) {
    var perPage = parseInt(sheet.dataset.qpp, 10) || 3;
    var perChapter = parseInt(sheet.dataset.ppc, 10) || 10;

    var out = {
      chapters:  document.getElementById('spec-chapters'),
      questions: document.getElementById('spec-questions'),
      content:   document.getElementById('spec-content'),
      answers:   document.getElementById('spec-answers'),
      total:     document.getElementById('spec-total')
    };

    function clamp(n) {
      var min = parseInt(chapterInput.min, 10);
      var max = parseInt(chapterInput.max, 10);
      if (isNaN(n)) return min;
      return Math.min(max, Math.max(min, n));
    }

    function recalc() {
      var chapters = clamp(parseInt(chapterInput.value, 10));
      var questions = chapters * perChapter * perPage;
      var contentPages = chapters * perChapter;
      var answerPages = Math.max(1, Math.ceil(questions / 60));

      out.chapters.textContent  = chapters;
      out.questions.textContent = questions;
      out.content.textContent   = contentPages;
      out.answers.textContent   = answerPages;
      out.total.textContent     = 2 + contentPages + answerPages;
    }

    chapterInput.addEventListener('input', recalc);
    recalc();
  }

  /* --- Theme picker: show/hide custom theme input ----------------------- */

  var themeSelect = document.getElementById('theme');
  var customGroup = document.getElementById('custom-theme-group');

  if (themeSelect && customGroup) {
    function toggleCustom() {
      if (themeSelect.value === '__custom__') {
        customGroup.classList.remove('hidden');
        document.getElementById('custom_theme').focus();
      } else {
        customGroup.classList.add('hidden');
      }
    }

    themeSelect.addEventListener('change', toggleCustom);
    toggleCustom();
  }

  /* --- Book page: live progress polling ----------------------------------- */

  var buildPanel = document.getElementById('build-panel');
  if (!buildPanel || buildPanel.dataset.active !== '1') return;

  var bookId = buildPanel.dataset.bookId;
  var endpoint = buildPanel.dataset.poll;
  var statusLabel = document.getElementById('status-label');
  var statusNote = document.getElementById('status-note');
  var progressBar = document.getElementById('progress-bar');
  var logList = document.getElementById('log-list');

  var lastEventId = 0;
  var misses = 0;
  var POLL_MS = 2500;

  function appendEvents(events) {
    events.forEach(function (event) {
      var li = document.createElement('li');
      li.setAttribute('data-level', event.level);

      var time = document.createElement('time');
      time.className = 'log-time';
      time.textContent = event.time;

      var span = document.createElement('span');
      span.textContent = event.message;

      li.appendChild(time);
      li.appendChild(span);
      logList.appendChild(li);
      lastEventId = Math.max(lastEventId, event.id);
    });

    if (events.length) {
      logList.scrollTop = logList.scrollHeight;
    }
  }

  function poll() {
    var url = endpoint + '?id=' + encodeURIComponent(bookId) + '&after=' + lastEventId;

    fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        misses = 0;

        statusLabel.textContent = data.label;
        statusNote.textContent = data.note || '';
        progressBar.style.width = data.progress + '%';
        progressBar.setAttribute('aria-valuenow', data.progress);

        appendEvents(data.events || []);

        if (data.done || data.failed) {
          setTimeout(function () { window.location.reload(); }, 1500);
          return;
        }

        setTimeout(poll, POLL_MS);
      })
      .catch(function () {
        misses += 1;
        if (misses < 8) {
          setTimeout(poll, POLL_MS + 1500);
        } else {
          statusNote.textContent = 'Lost contact with the server. Reload to check again.';
        }
      });
  }

  setTimeout(poll, 1200);
})();
