(() => {
  const SCORE_TABLE = { 4: 1, 5: 2, 6: 3, 7: 5 };
  function wordScore(w) { return w.length >= 8 ? 11 : (SCORE_TABLE[w.length] || 0); }
  function calcScore(words) { return words.reduce((s, w) => s + wordScore(w), 0); }

  let puzzle = null;
  let board = [];
  let foundWords = new Set();
  let selectedCells = [];
  let selectedIndices = new Set();
  let isSelecting = false;
  let timerInterval = null;
  let secondsLeft = 0;
  let gameOver = false;
  let paused = false;
  let wordSet = null;       // null = not loaded yet; Set once loaded
  let myUserId = null;

  const STORAGE_KEY_PREFIX = 'td_boggle_progress_';

  function storageKey() { return puzzle ? STORAGE_KEY_PREFIX + puzzle.puzzle_id : null; }

  function saveProgress() {
    const key = storageKey();
    if (!key) return;
    localStorage.setItem(key, JSON.stringify({ secondsLeft, foundWords: [...foundWords], paused }));
  }

  function loadProgress() {
    const key = storageKey();
    if (!key) return null;
    try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
  }

  function clearProgress() {
    const key = storageKey();
    if (key) localStorage.removeItem(key);
  }

  async function loadDictionary() {
    try {
      const resp = await fetch(window.TD_DICT_URL);
      const text = await resp.text();
      wordSet = new Set(text.split('\n').map(w => w.trim().toLowerCase()).filter(Boolean));
    } catch {
      wordSet = null;
    }
  }

  function show(id) {
    ['state-loading','state-already-played','state-playing','state-paused','state-results','state-error']
      .forEach(s => { const el = document.getElementById(s); if (el) el.style.display = s === id ? '' : 'none'; });
    // Show timer only during play
    const timerEl = document.getElementById('timer');
    if (timerEl) timerEl.style.display = id === 'state-playing' ? '' : 'none';
  }

  function fmtTime(s) {
    const m = Math.floor(s / 60);
    return `${m}:${String(s % 60).padStart(2,'0')}`;
  }

  function startTimer() {
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      if (paused) return;
      secondsLeft--;
      document.getElementById('timer').textContent = fmtTime(secondsLeft);
      if (secondsLeft <= 30) document.getElementById('timer').classList.add('timer-urgent');
      saveProgress();
      if (secondsLeft <= 0) finish();
    }, 1000);
  }

  function renderReadOnlyBoard(letters, containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = letters.map(l =>
      `<div class="board-cell" style="cursor:default;pointer-events:none">${l.toUpperCase()}</div>`
    ).join('');
  }

  function renderBoard() {
    const boardEl = document.getElementById('board');
    boardEl.innerHTML = '';
    board.forEach((letter, i) => {
      const cell = document.createElement('div');
      cell.className = 'board-cell';
      cell.textContent = letter.toUpperCase();
      cell.dataset.idx = i;
      boardEl.appendChild(cell);
    });

    boardEl.addEventListener('pointerdown', e => {
      const cell = e.target.closest('.board-cell');
      if (!cell) return;
      e.preventDefault();
      boardEl.setPointerCapture(e.pointerId);
      startSelect(+cell.dataset.idx);
    });

    boardEl.addEventListener('pointermove', e => {
      if (!isSelecting) return;
      e.preventDefault();
      const el = document.elementFromPoint(e.clientX, e.clientY);
      if (!el || !el.classList.contains('board-cell')) return;
      addToSelect(+el.dataset.idx, e.clientX, e.clientY);
    });

    boardEl.addEventListener('pointerup', e => {
      e.preventDefault();
      endSelect();
    });

    boardEl.addEventListener('pointercancel', () => {
      isSelecting = false;
      selectedCells = [];
      selectedIndices = new Set();
      renderSelection();
    });
  }

  function startSelect(i) {
    isSelecting = true;
    selectedCells = [i];
    selectedIndices = new Set([i]);
    renderSelection();
  }

  function addToSelect(i, clientX, clientY) {
    const cellEl = document.querySelector(`.board-cell[data-idx="${i}"]`);
    if (cellEl) {
      const rect = cellEl.getBoundingClientRect();
      const dx = clientX - (rect.left + rect.width / 2);
      const dy = clientY - (rect.top + rect.height / 2);
      if (Math.sqrt(dx * dx + dy * dy) > rect.width * 0.4) return;
    }

    if (selectedIndices.has(i)) {
      const prev = selectedCells[selectedCells.length - 2];
      if (i === prev) {
        const last = selectedCells[selectedCells.length - 1];
        selectedIndices.delete(last);
        selectedCells.pop();
        renderSelection();
      }
      return;
    }
    const last = selectedCells[selectedCells.length - 1];
    if (!adjacent(last, i)) return;
    selectedCells.push(i);
    selectedIndices.add(i);
    renderSelection();
  }

  function adjacent(a, b) {
    const ar = Math.floor(a / 5), ac = a % 5;
    const br = Math.floor(b / 5), bc = b % 5;
    return Math.abs(ar - br) <= 1 && Math.abs(ac - bc) <= 1 && a !== b;
  }

  function renderSelection() {
    document.querySelectorAll('.board-cell').forEach(el => {
      const i = +el.dataset.idx;
      el.classList.toggle('selected', selectedIndices.has(i));
      el.classList.toggle('path-end', i === selectedCells[selectedCells.length - 1] && selectedCells.length > 1);
    });
    const word = selectedCells.map(i => board[i]).join('').toUpperCase();
    document.getElementById('current-word').textContent = word;
  }

  function flashWord(msg) {
    const el = document.getElementById('current-word');
    el.textContent = msg;
    el.classList.add('flash-error');
    setTimeout(() => { el.classList.remove('flash-error'); el.textContent = ''; }, 900);
  }

  function endSelect() {
    if (!isSelecting) return;
    isSelecting = false;
    const word = selectedCells.map(i => board[i]).join('').toLowerCase();

    if (word.length < 4) {
      if (word.length >= 2) flashWord('Too short');
    } else if (foundWords.has(word)) {
      flashWord('Already found');
    } else if (wordSet !== null && !wordSet.has(word)) {
      flashWord('Not a word');
    } else {
      foundWords.add(word);
      renderFoundWords();
      updateWordCount();
      saveProgress();
    }

    selectedCells = [];
    selectedIndices = new Set();
    renderSelection();
  }

  function renderFoundWords() {
    const el = document.getElementById('found-words');
    const sorted = [...foundWords].sort((a, b) => b.length - a.length || a.localeCompare(b));
    el.innerHTML = sorted.map(w =>
      `<span class="word-chip">${API.escHtml(w.toUpperCase())} <span class="chip-score">+${wordScore(w)}</span></span>`
    ).join('');
  }

  function updateWordCount() {
    const score = calcScore([...foundWords]);
    document.getElementById('word-count').textContent = `${foundWords.size} words · ${score} pts`;
  }

  async function finish() {
    clearInterval(timerInterval);
    gameOver = true;
    clearProgress();

    const durationUsed = (puzzle.duration_seconds || 180) - Math.max(0, secondsLeft);
    const allWords = [...foundWords];
    let result = null;

    try {
      result = await API.post('v1/scores', {
        puzzle_id: puzzle.puzzle_id,
        duration_seconds: durationUsed,
        words: allWords,
      });
    } catch (_) { /* non-fatal */ }

    showResults(allWords, result ? result.valid_words : null, puzzle.puzzle_id);
  }

  async function showResults(allWords, validWords, puzzleId) {
    show('state-results');
    renderReadOnlyBoard(board, 'results-board');
    const displayWords = validWords || allWords;
    const score = calcScore(displayWords);
    const invalid = validWords ? allWords.length - validWords.length : 0;

    document.getElementById('results-score').textContent = `${score} points`;
    let label = `${displayWords.length} word${displayWords.length !== 1 ? 's' : ''}`;
    if (invalid > 0) label += ` · ${invalid} invalid`;
    document.getElementById('results-words-label').textContent = label;

    const sorted = [...displayWords].sort((a, b) => b.length - a.length || a.localeCompare(b));
    document.getElementById('results-words').innerHTML = sorted.map(w =>
      `<span class="word-chip">${API.escHtml(w.toUpperCase())} <span class="chip-score">+${wordScore(w)}</span></span>`
    ).join('');

    // Share button
    document.getElementById('share-btn').addEventListener('click', () => {
      const text = `td Puzzles — Words\nScore: ${score} (${displayWords.length} words)`;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          const msg = document.getElementById('share-msg');
          msg.style.display = '';
          setTimeout(() => { msg.style.display = 'none'; }, 2000);
        });
      }
    });

    // Leaderboards
    if (puzzleId) {
      await Leaderboard.render(
        document.getElementById('results-leaderboard'),
        puzzleId,
        e => e.word_count != null ? `${e.score} pts (${e.word_count} words)` : `${e.score} pts`,
        myUserId,
      );
    }
  }

  async function showAlreadyPlayed(data) {
    show('state-already-played');
    const score = data.your_score || 0;
    document.getElementById('already-score').textContent = `${score} points`;
    const boardLetters = Array.isArray(data.board?.[0]) ? data.board.flat() : (data.board || []);
    renderReadOnlyBoard(boardLetters, 'already-board');

    // Try to load the valid_words from score detail
    let validWords = null;
    if (myUserId && data.puzzle_id) {
      try {
        const detail = await API.get(`v1/scores/${data.puzzle_id}/${myUserId}`);
        validWords = detail.valid_words || null;
        const wc = validWords ? validWords.length : 0;
        document.getElementById('already-words-label').textContent = `${wc} word${wc !== 1 ? 's' : ''}`;
        if (validWords) {
          const sorted = [...validWords].sort((a, b) => b.length - a.length || a.localeCompare(b));
          document.getElementById('already-words').innerHTML = sorted.map(w =>
            `<span class="word-chip">${API.escHtml(w.toUpperCase())} <span class="chip-score">+${wordScore(w)}</span></span>`
          ).join('');
        }
      } catch (_) { /* fallback: no words shown */ }
    }

    // Leaderboards
    if (data.puzzle_id) {
      await Leaderboard.render(
        document.getElementById('already-leaderboard'),
        data.puzzle_id,
        e => e.word_count != null ? `${e.score} pts (${e.word_count} words)` : `${e.score} pts`,
        myUserId,
      );
    }
  }

  document.getElementById('pause-btn').addEventListener('click', () => {
    paused = true;
    saveProgress();
    const score = calcScore([...foundWords]);
    document.getElementById('pause-score').textContent = `${score} pts · ${foundWords.size} words`;
    show('state-paused');
  });

  document.getElementById('resume-btn').addEventListener('click', () => {
    paused = false;
    show('state-playing');
  });

  document.getElementById('finish-early-btn').addEventListener('click', finish);

  async function loadPuzzleAndStart() {
    if (API.isLoggedIn()) {
      try {
        const me = await API.get('v1/users/me');
        myUserId = me.user_id;
      } catch (_) { /* guest */ }
    }

    const data = await API.get('v1/puzzles/today?game=boggle');
    puzzle = data;
    board = Array.isArray(data.board[0]) ? data.board.flat() : data.board;

    if (data.already_played) {
      await showAlreadyPlayed(data);
      return;
    }

    const saved = loadProgress();
    if (saved) {
      foundWords = new Set(saved.foundWords || []);
      secondsLeft = saved.secondsLeft ?? (data.duration_seconds || 180);
      paused = saved.paused || false;
    } else {
      secondsLeft = data.duration_seconds || 180;
    }

    document.getElementById('timer').textContent = fmtTime(secondsLeft);
    show('state-playing');
    renderBoard();
    renderFoundWords();
    updateWordCount();
    startTimer();

    if (paused) {
      const score = calcScore([...foundWords]);
      document.getElementById('pause-score').textContent = `${score} pts · ${foundWords.size} words`;
      show('state-paused');
    }
  }

  async function init() {
    loadDictionary();

    if (!localStorage.getItem('td_access_token')) {
      // No session yet — show a start gate so we only create a guest account if they actually play
      const loadingEl = document.getElementById('state-loading');
      loadingEl.innerHTML = `
        <div style="text-align:center;padding:40px 0">
          <p style="color:var(--ink-mid);margin-bottom:20px">Ready to play today's Words puzzle?</p>
          <button class="btn btn-primary" id="start-gate-btn">Start today's puzzle</button>
        </div>`;
      document.getElementById('start-gate-btn').addEventListener('click', async () => {
        loadingEl.innerHTML = '<p style="color:var(--ink-mid)">Loading today\'s puzzle…</p>';
        try {
          await API.ensureSession();
          await loadPuzzleAndStart();
        } catch (e) {
          show('state-error');
          document.getElementById('error-msg').textContent = e.message || 'Failed to load puzzle.';
        }
      });
      return;
    }

    try {
      await loadPuzzleAndStart();
    } catch (e) {
      show('state-error');
      document.getElementById('error-msg').textContent = e.message || 'Failed to load puzzle.';
    }
  }

  document.addEventListener('DOMContentLoaded', init);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && !gameOver) {
      paused = true;
      saveProgress();
    }
  });
})();
