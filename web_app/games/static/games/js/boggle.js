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

  function show(id) {
    ['state-loading','state-already-played','state-playing','state-paused','state-results','state-error']
      .forEach(s => { const el = document.getElementById(s); if (el) el.style.display = s === id ? '' : 'none'; });
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

    // Use pointermove + elementFromPoint so diagonals work on touch
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
      addToSelect(+el.dataset.idx);
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

  function addToSelect(i) {
    if (selectedIndices.has(i)) {
      const pos = selectedCells.indexOf(i);
      if (pos >= 0 && pos < selectedCells.length - 1) {
        selectedCells.slice(pos + 1).forEach(j => selectedIndices.delete(j));
        selectedCells = selectedCells.slice(0, pos + 1);
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

  function endSelect() {
    if (!isSelecting) return;
    isSelecting = false;
    const word = selectedCells.map(i => board[i]).join('').toLowerCase();
    if (word.length >= 3 && !foundWords.has(word)) {
      foundWords.add(word);
      renderFoundWords();
      updateWordCount();
      saveProgress();
    }
    selectedCells = [];
    selectedIndices = new Set();
    renderSelection();
    document.getElementById('current-word').textContent = '';
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
    let validWords = null;

    try {
      const result = await API.post('v1/scores', {
        puzzle_id: puzzle.puzzle_id,
        duration_seconds: durationUsed,
        words: allWords,
      });
      validWords = result.valid_words || null;
    } catch (e) {
      // non-fatal — show results with attempted words
    }

    showResults(allWords, validWords);
  }

  function showResults(allWords, validWords) {
    show('state-results');
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
  }

  function setupShareBtn() {
    document.getElementById('share-btn').addEventListener('click', () => {
      const score = calcScore([...foundWords]);
      const text = `td Puzzles — Words\nScore: ${score} (${foundWords.size} words)`;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          const msg = document.getElementById('share-msg');
          msg.style.display = '';
          setTimeout(() => { msg.style.display = 'none'; }, 2000);
        });
      }
    });
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

  async function init() {
    try {
      await API.ensureSession();
      const data = await API.get('v1/puzzles/today?game=boggle');
      puzzle = data;
      board = Array.isArray(data.board[0]) ? data.board.flat() : data.board;

      if (data.already_played) {
        show('state-already-played');
        document.getElementById('already-score').textContent =
          `Score: ${data.your_score || 0} points`;
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
      setupShareBtn();
      startTimer();
    } catch (e) {
      show('state-error');
      document.getElementById('error-msg').textContent = e.message || 'Failed to load puzzle.';
    }
  }

  document.addEventListener('DOMContentLoaded', init);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && !gameOver) saveProgress();
  });
})();
