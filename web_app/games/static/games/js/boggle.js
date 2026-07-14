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
    localStorage.setItem(key, JSON.stringify({
      secondsLeft,
      foundWords: [...foundWords],
      paused,
    }));
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

  function updateTimer() {
    document.getElementById('timer').textContent = fmtTime(secondsLeft);
  }

  function startTimer() {
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      if (paused) return;
      secondsLeft--;
      updateTimer();
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

      cell.addEventListener('pointerdown', e => { e.preventDefault(); startSelect(i); });
      cell.addEventListener('pointerenter', e => { if (isSelecting) addToSelect(i); });
      boardEl.appendChild(cell);
    });
    document.addEventListener('pointerup', endSelect);
  }

  function cellEl(i) { return document.querySelector(`.board-cell[data-idx="${i}"]`); }

  function startSelect(i) {
    isSelecting = true;
    selectedCells = [i];
    selectedIndices = new Set([i]);
    renderSelection();
  }

  function addToSelect(i) {
    if (selectedIndices.has(i)) {
      // backtrack
      const pos = selectedCells.indexOf(i);
      if (pos >= 0 && pos < selectedCells.length - 1) {
        selectedCells.slice(pos + 1).forEach(j => selectedIndices.delete(j));
        selectedCells = selectedCells.slice(0, pos + 1);
      }
      renderSelection();
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
      submitWord(word);
    }
    selectedCells = [];
    selectedIndices = new Set();
    renderSelection();
    document.getElementById('current-word').textContent = '';
  }

  async function submitWord(word) {
    try {
      const res = await API.post(`v1/puzzles/${puzzle.puzzle_id}/words`, { word });
      if (res.valid) {
        foundWords.add(word);
        renderFoundWords();
        updateWordCount();
        saveProgress();
      } else {
        flashCurrentWord('Not a word');
      }
    } catch (e) {
      flashCurrentWord('Error');
    }
  }

  function flashCurrentWord(msg) {
    const el = document.getElementById('current-word');
    el.textContent = msg;
    el.classList.add('flash-error');
    setTimeout(() => { el.classList.remove('flash-error'); el.textContent = ''; }, 1000);
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
    const words = [...foundWords];
    try {
      await API.post(`v1/scores`, {
        puzzle_id: puzzle.puzzle_id,
        words,
      });
    } catch (e) {
      // score submission failure is non-fatal — still show results
    }
    showResults(words);
  }

  function showResults(words) {
    show('state-results');
    const score = calcScore(words);
    document.getElementById('results-score').textContent = `${score} points`;
    document.getElementById('results-words-label').textContent =
      `${words.length} word${words.length !== 1 ? 's' : ''} found`;
    const sorted = [...words].sort((a, b) => b.length - a.length || a.localeCompare(b));
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

  document.getElementById('finish-early-btn').addEventListener('click', () => {
    finish();
  });

  async function init() {
    try {
      await API.ensureSession();
      const data = await API.get('v1/puzzles/today?game=boggle');
      puzzle = data;
      board = data.board.flat ? data.board.flat() : data.board;

      // board may come as flat array or 2D — normalise to flat
      if (Array.isArray(board[0])) board = board.flat();

      const savedProgress = loadProgress();

      if (data.already_played) {
        show('state-already-played');
        const score = data.my_score || 0;
        const words = data.my_words || [];
        document.getElementById('already-score').textContent = `Score: ${score} points`;
        document.getElementById('already-words').textContent = `${words.length} word${words.length !== 1 ? 's' : ''} found`;
        return;
      }

      if (savedProgress) {
        foundWords = new Set(savedProgress.foundWords || []);
        secondsLeft = savedProgress.secondsLeft ?? (data.duration_seconds || 180);
        paused = savedProgress.paused || false;
      } else {
        secondsLeft = data.duration_seconds || 180;
      }

      updateTimer();
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
