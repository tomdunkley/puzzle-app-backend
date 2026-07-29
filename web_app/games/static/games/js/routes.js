'use strict';

(() => {
  // ── Java Random port (matches Kotlin/JVM kotlin.random.Random exactly) ────

  class JavaRandom {
    constructor(seed) {
      const MULTIPLIER = 0x5DEECE66Dn;
      const MASK48 = (1n << 48n) - 1n;
      // seed is a BigInt representing a Java long
      this._seed = (BigInt.asIntN(64, seed) ^ MULTIPLIER) & MASK48;
    }

    _next(bits) {
      const MULTIPLIER = 0x5DEECE66Dn;
      const ADDEND = 0xBn;
      const MASK48 = (1n << 48n) - 1n;
      this._seed = (this._seed * MULTIPLIER + ADDEND) & MASK48;
      return Number(this._seed >> BigInt(48 - bits));
    }

    nextInt(n) {
      if (n <= 0) throw new Error('n must be positive');
      const nbig = BigInt(n);
      if ((nbig & (nbig - 1n)) === 0n) {
        return Number((nbig * BigInt(this._next(31))) >> 31n);
      }
      let bits, val;
      do {
        bits = this._next(31);
        val = bits % n;
      } while (bits - val + n - 1 < 0);
      return val;
    }
  }

  // Matches Kotlin: puzzleId.fold(0L) { acc, c -> acc * 31 + c.code }
  function seedFromPuzzleId(puzzleId) {
    let acc = 0n;
    for (const c of puzzleId) {
      acc = BigInt.asIntN(64, acc * 31n + BigInt(c.charCodeAt(0)));
    }
    return acc;
  }

  // Matches Kotlin gridSizeForDate / RootsViewModel.gridSizeForDate
  // Mon (weekday 1 in JS, dayOfWeek.MONDAY) → 4
  // Sat (6) / Sun (0) → 6, else → 5
  function gridSizeForDate(dateStr) {
    const d = new Date(dateStr + 'T12:00:00Z');
    const dow = d.getUTCDay(); // 0=Sun,1=Mon,...,6=Sat
    if (dow === 1) return 4;
    if (dow === 0 || dow === 6) return 6;
    return 5;
  }

  // ── Puzzle generator (exact port of RootsPuzzleGenerator.kt) ────────────

  const DIRS = [{dr:-1,dc:0},{dr:1,dc:0},{dr:0,dc:-1},{dr:0,dc:1}];

  function shuffled(arr, rng) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = rng.nextInt(i + 1);
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function manhattan(r1, c1, r2, c2) { return Math.abs(r1 - r2) + Math.abs(c1 - c2); }

  function randomPath(rng, n, sr, sc, er, ec) {
    const visited = Array.from({length: n}, () => new Array(n).fill(false));
    const path = [];
    function dfs(r, c) {
      visited[r][c] = true;
      path.push([r, c]);
      if (r === er && c === ec) return true;
      for (const {dr, dc} of shuffled(DIRS, rng)) {
        const nr = r + dr, nc = c + dc;
        if (nr < 0 || nr >= n || nc < 0 || nc >= n || visited[nr][nc]) continue;
        if (dfs(nr, nc)) return true;
      }
      visited[r][c] = false;
      path.pop();
      return false;
    }
    return dfs(sr, sc) ? path : null;
  }

  function countTurns(path) {
    if (path.length < 3) return 0;
    let turns = 0;
    let [pr, pc] = path[0], [r1, c1] = path[1];
    let prevDr = r1 - pr, prevDc = c1 - pc;
    for (let i = 2; i < path.length; i++) {
      const dr = path[i][0] - path[i-1][0];
      const dc = path[i][1] - path[i-1][1];
      if (dr !== prevDr || dc !== prevDc) turns++;
      prevDr = dr; prevDc = dc;
    }
    return turns;
  }

  function isUnique(n, sr, sc, er, ec, rowClues, colClues) {
    let count = 0;
    const rowUsed = new Array(n).fill(0);
    const colUsed = new Array(n).fill(0);
    const visited = Array.from({length: n}, () => new Array(n).fill(false));
    let nodes = 0;
    function dfs(r, c) {
      if (count >= 2 || nodes > 100000) return;
      nodes++;
      rowUsed[r]++; colUsed[c]++; visited[r][c] = true;
      if (r === er && c === ec) {
        let ok = true;
        for (let i = 0; i < n && ok; i++) {
          if (rowUsed[i] !== rowClues[i] || colUsed[i] !== colClues[i]) ok = false;
        }
        if (ok) count++;
      } else {
        let feasible = true;
        for (let i = 0; i < n && feasible; i++) {
          const rrem = rowClues[i] - rowUsed[i];
          if (rrem < 0) { feasible = false; break; }
          if (rrem > 0) {
            let avail = 0;
            for (let j = 0; j < n; j++) if (!visited[i][j]) avail++;
            if (avail < rrem) feasible = false;
          }
        }
        for (let i = 0; i < n && feasible; i++) {
          const crem = colClues[i] - colUsed[i];
          if (crem < 0) { feasible = false; break; }
          if (crem > 0) {
            let avail = 0;
            for (let j = 0; j < n; j++) if (!visited[j][i]) avail++;
            if (avail < crem) feasible = false;
          }
        }
        if (feasible) {
          for (const {dr, dc} of DIRS) {
            if (count >= 2) break;
            const nr = r + dr, nc = c + dc;
            if (nr < 0 || nr >= n || nc < 0 || nc >= n || visited[nr][nc]) continue;
            if (rowUsed[nr] >= rowClues[nr] || colUsed[nc] >= colClues[nc]) continue;
            dfs(nr, nc);
          }
        }
      }
      rowUsed[r]--; colUsed[c]--; visited[r][c] = false;
    }
    dfs(sr, sc);
    return count === 1;
  }

  function tryGenerate(rng, n) {
    const sr = rng.nextInt(n), sc = rng.nextInt(n);
    let er, ec, attempts = 0;
    do {
      er = rng.nextInt(n); ec = rng.nextInt(n);
      if (++attempts > 50) return null;
    } while ((er === sr && ec === sc) || manhattan(sr, sc, er, ec) < Math.floor((n + 1) / 2));

    const path = randomPath(rng, n, sr, sc, er, ec);
    if (!path) return null;

    const minLen = Math.max(Math.floor(n * n * 0.35), n + 2);
    if (path.length < minLen || countTurns(path) < n - 1) return null;

    const rowClues = Array.from({length: n}, (_, r) => path.filter(([pr]) => pr === r).length);
    const colClues = Array.from({length: n}, (_, c) => path.filter(([, pc]) => pc === c).length);

    if (!isUnique(n, sr, sc, er, ec, rowClues, colClues)) return null;

    return {gridSize: n, startRow: sr, startCol: sc, endRow: er, endCol: ec, rowClues, colClues, solution: path};
  }

  function generateFallback(n) {
    const path = [];
    for (let r = 0; r < n; r++) {
      if (r % 2 === 0) { for (let c = 0; c < n; c++) path.push([r, c]); }
      else { for (let c = n-1; c >= 0; c--) path.push([r, c]); }
    }
    return {
      gridSize: n, startRow: 0, startCol: 0, endRow: n-1, endCol: n-1,
      rowClues: Array(n).fill(n), colClues: Array(n).fill(n), solution: path,
    };
  }

  function generatePuzzle(puzzleId) {
    const seed = seedFromPuzzleId(puzzleId);
    const n = gridSizeForDate(puzzleId.replace('routes_', ''));
    const rng = new JavaRandom(seed);
    for (let i = 0; i < 500; i++) {
      const p = tryGenerate(rng, n);
      if (p) return p;
    }
    return generateFallback(n);
  }

  function checkSolved(path, rowClues, colClues, startRow, startCol, endRow, endCol) {
    if (!path.length) return false;
    const [fr, fc] = path[0], [lr, lc] = path[path.length - 1];
    const validEnds = (fr === startRow && fc === startCol && lr === endRow && lc === endCol) ||
                      (fr === endRow && fc === endCol && lr === startRow && lc === startCol);
    if (!validEnds) return false;
    const n = rowClues.length;
    const rowCount = new Array(n).fill(0);
    const colCount = new Array(n).fill(0);
    for (const [r, c] of path) { rowCount[r]++; colCount[c]++; }
    return rowCount.every((v, i) => v === rowClues[i]) && colCount.every((v, i) => v === colClues[i]);
  }

  // ── State ──────────────────────────────────────────────────────────────

  const STORAGE_KEY_PREFIX = 'td_routes_progress_';

  let puzzle = null;       // {gridSize, startRow, startCol, endRow, endCol, rowClues, colClues, solution}
  let puzzleId = null;
  let path = [];           // [[row, col], ...]
  let crossMarkers = new Set();  // "r,c" strings
  let tickMarkers = new Set();
  let elapsedSeconds = 0;
  let timerInterval = null;
  let dragMode = null;     // 'path' | 'cross' | 'tick' | 'clear' | null
  let myUserId = null;

  function storageKey() { return puzzle ? STORAGE_KEY_PREFIX + puzzleId : null; }

  function saveProgress() {
    const k = storageKey();
    if (!k) return;
    localStorage.setItem(k, JSON.stringify({
      path, crossMarkers: [...crossMarkers], tickMarkers: [...tickMarkers], elapsedSeconds,
    }));
  }

  function loadProgress() {
    const k = storageKey();
    if (!k) return null;
    try { return JSON.parse(localStorage.getItem(k)); } catch { return null; }
  }

  function clearProgress() {
    const k = storageKey();
    if (k) localStorage.removeItem(k);
  }

  // ── Canvas rendering ───────────────────────────────────────────────────

  const ROUTES_COLOR   = '#2E7D32';
  const CLUE_FONT_RATIO = 0.38;   // relative to cellPx
  const CLUE_AREA_RATIO = 0.70;   // clue area width relative to cellPx

  function drawGrid(canvas, puz, path, crossMarkers, tickMarkers, interactive) {
    if (!puz) return;
    const {gridSize: n, startRow, startCol, endRow, endCol, rowClues, colClues} = puz;

    const dpr = window.devicePixelRatio || 1;
    const w = canvas.offsetWidth;
    const clueArea = Math.round(w * CLUE_AREA_RATIO / (n + CLUE_AREA_RATIO));
    const cellPx = Math.round((w - clueArea) / n);
    const totalW = clueArea + n * cellPx;
    const totalH = clueArea + n * cellPx;
    canvas.width = totalW * dpr;
    canvas.height = totalH * dpr;
    canvas.style.height = totalH + 'px';

    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, totalW, totalH);

    const isDark = document.documentElement.dataset.theme === 'dark' ||
      (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches &&
       document.documentElement.dataset.theme !== 'light');
    const inkColor     = isDark ? '#E0D5C5' : '#1C1008';
    const borderColor  = isDark ? '#444' : '#ccc';
    const bgColor      = isDark ? '#222' : '#fff';
    const pathColor    = ROUTES_COLOR;
    const pathBgAlpha  = isDark ? 'rgba(46,125,50,0.22)' : 'rgba(46,125,50,0.12)';
    const clueHighlight = ROUTES_COLOR;

    // Background
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, totalW, totalH);

    // Build path cell set
    const pathSet = new Set(path.map(([r, c]) => `${r},${c}`));
    const isStart = (r, c) => r === startRow && c === startCol;
    const isEnd   = (r, c) => r === endRow   && c === endCol;

    // Draw cell backgrounds + markers
    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n; c++) {
        const x = clueArea + c * cellPx;
        const y = clueArea + r * cellPx;
        const key = `${r},${c}`;
        const inPath = pathSet.has(key);

        if (inPath && !isStart(r, c) && !isEnd(r, c)) {
          ctx.fillStyle = pathBgAlpha;
          ctx.fillRect(x, y, cellPx, cellPx);
        }

        if (crossMarkers.has(key)) {
          ctx.strokeStyle = isDark ? '#777' : '#bbb';
          ctx.lineWidth = 1.5;
          const pad = cellPx * 0.25;
          ctx.beginPath();
          ctx.moveTo(x + pad, y + pad); ctx.lineTo(x + cellPx - pad, y + cellPx - pad);
          ctx.moveTo(x + cellPx - pad, y + pad); ctx.lineTo(x + pad, y + cellPx - pad);
          ctx.stroke();
        }

        if (tickMarkers.has(key)) {
          ctx.strokeStyle = isDark ? '#66BB6A' : '#4CAF50';
          ctx.lineWidth = 2;
          const pad = cellPx * 0.2;
          ctx.beginPath();
          ctx.moveTo(x + pad, y + cellPx * 0.55);
          ctx.lineTo(x + cellPx * 0.42, y + cellPx - pad);
          ctx.lineTo(x + cellPx - pad, y + pad);
          ctx.stroke();
        }
      }
    }

    // Draw grid lines
    ctx.strokeStyle = borderColor;
    ctx.lineWidth = 1;
    for (let r = 0; r <= n; r++) {
      const y = clueArea + r * cellPx;
      ctx.beginPath(); ctx.moveTo(clueArea, y); ctx.lineTo(clueArea + n * cellPx, y); ctx.stroke();
    }
    for (let c = 0; c <= n; c++) {
      const x = clueArea + c * cellPx;
      ctx.beginPath(); ctx.moveTo(x, clueArea); ctx.lineTo(x, clueArea + n * cellPx); ctx.stroke();
    }

    // Draw path line
    if (path.length >= 2) {
      ctx.strokeStyle = pathColor;
      ctx.lineWidth = cellPx * 0.22;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.beginPath();
      const [r0, c0] = path[0];
      ctx.moveTo(clueArea + c0 * cellPx + cellPx / 2, clueArea + r0 * cellPx + cellPx / 2);
      for (let i = 1; i < path.length; i++) {
        const [ri, ci] = path[i];
        ctx.lineTo(clueArea + ci * cellPx + cellPx / 2, clueArea + ri * cellPx + cellPx / 2);
      }
      ctx.stroke();
    }

    // Draw start/end circles
    for (const [row, col] of [[startRow, startCol], [endRow, endCol]]) {
      const cx = clueArea + col * cellPx + cellPx / 2;
      const cy = clueArea + row * cellPx + cellPx / 2;
      const r = cellPx * 0.3;
      ctx.fillStyle = ROUTES_COLOR;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
    }

    // Clue numbers — columns (top)
    const fontSize = Math.max(11, Math.round(cellPx * CLUE_FONT_RATIO));
    ctx.font = `600 ${fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (let c = 0; c < n; c++) {
      const colHasPath = path.some(([, pc]) => pc === c);
      ctx.fillStyle = colHasPath ? clueHighlight : inkColor;
      ctx.fillText(String(colClues[c]), clueArea + c * cellPx + cellPx / 2, clueArea / 2);
    }
    // Clue numbers — rows (left)
    for (let r = 0; r < n; r++) {
      const rowHasPath = path.some(([pr]) => pr === r);
      ctx.fillStyle = rowHasPath ? clueHighlight : inkColor;
      ctx.fillText(String(rowClues[r]), clueArea / 2, clueArea + r * cellPx + cellPx / 2);
    }
  }

  function cellAtPoint(canvas, clientX, clientY, puz) {
    if (!puz) return null;
    const rect = canvas.getBoundingClientRect();
    const px = clientX - rect.left;
    const py = clientY - rect.top;
    const {gridSize: n} = puz;
    const clueArea = rect.width * CLUE_AREA_RATIO / (n + CLUE_AREA_RATIO);
    const cellPx = (rect.width - clueArea) / n;
    const col = Math.floor((px - clueArea) / cellPx);
    const row = Math.floor((py - clueArea) / cellPx);
    if (row < 0 || row >= n || col < 0 || col >= n) return null;
    return [row, col];
  }

  function isAdjacent(a, b) {
    return Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) === 1;
  }

  // ── Timer ──────────────────────────────────────────────────────────────

  function fmtTime(s) {
    if (s == null || s < 0) return '';
    const m = Math.floor(s / 60);
    return m > 0 ? `${m}m ${String(s % 60).padStart(2, '0')}s` : `${s}s`;
  }

  function startTimer() {
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      elapsedSeconds++;
      document.getElementById('timer').textContent = fmtTime(elapsedSeconds);
      saveProgress();
    }, 1000);
  }

  function stopTimer() { clearInterval(timerInterval); timerInterval = null; }

  // ── Show/hide states ──────────────────────────────────────────────────

  function show(id) {
    ['state-loading','state-already-played','state-playing','state-results','state-error']
      .forEach(s => {
        const el = document.getElementById(s);
        if (el) el.style.display = s === id ? '' : 'none';
      });
    const timerEl = document.getElementById('timer');
    if (timerEl) timerEl.style.display = id === 'state-playing' ? '' : 'none';
  }

  // ── Playing canvas & interaction ────────────────────────────────────

  let playCanvas = null;

  function renderPlay() {
    if (!playCanvas || !puzzle) return;
    drawGrid(playCanvas, puzzle, path, crossMarkers, tickMarkers, true);
  }

  function handleSolve() {
    stopTimer();
    clearProgress();
    submitScore(elapsedSeconds).then(() => {});
  }

  function onPointerDown(e) {
    if (!puzzle) return;
    e.preventDefault();
    const cell = cellAtPoint(playCanvas, e.clientX, e.clientY, puzzle);
    if (!cell) return;

    const [r, c] = cell;
    const {startRow, startCol, endRow, endCol} = puzzle;
    const key = `${r},${c}`;

    // Check if cell is in path
    const pathIdx = path.findIndex(([pr, pc]) => pr === r && pc === c);

    if (pathIdx >= 0) {
      path = path.slice(0, pathIdx + 1);
      dragMode = 'path';
    } else if ((r === startRow && c === startCol) || (r === endRow && c === endCol)) {
      path = [[r, c]];
      dragMode = 'path';
    } else if (crossMarkers.has(key)) {
      dragMode = 'tick';
      crossMarkers.delete(key);
      tickMarkers.add(key);
    } else if (tickMarkers.has(key)) {
      dragMode = 'clear';
      tickMarkers.delete(key);
    } else {
      dragMode = 'cross';
      crossMarkers.add(key);
      tickMarkers.delete(key);
    }
    renderPlay();
  }

  function onPointerMove(e) {
    if (!puzzle || !dragMode) return;
    e.preventDefault();
    const cell = cellAtPoint(playCanvas, e.clientX, e.clientY, puzzle);
    if (!cell) return;
    const [r, c] = cell;
    const {startRow, startCol, endRow, endCol} = puzzle;
    const key = `${r},${c}`;

    if (dragMode === 'path') {
      const existingIdx = path.findIndex(([pr, pc]) => pr === r && pc === c);
      if (existingIdx >= 0) {
        path = path.slice(0, existingIdx + 1);
      } else if (path.length > 0 && isAdjacent(path[path.length - 1], cell)) {
        path = [...path, cell];
        crossMarkers.delete(key);
        tickMarkers.delete(key);
        if (checkSolved(path, puzzle.rowClues, puzzle.colClues, startRow, startCol, endRow, endCol)) {
          renderPlay();
          handleSolve();
          return;
        }
      }
    } else if (dragMode === 'cross') {
      if ((r === startRow && c === startCol) || (r === endRow && c === endCol)) return;
      if (path.some(([pr, pc]) => pr === r && pc === c)) return;
      crossMarkers.add(key);
      tickMarkers.delete(key);
    } else if (dragMode === 'tick') {
      if ((r === startRow && c === startCol) || (r === endRow && c === endCol)) return;
      if (path.some(([pr, pc]) => pr === r && pc === c)) return;
      crossMarkers.delete(key);
      tickMarkers.add(key);
    } else if (dragMode === 'clear') {
      if ((r === startRow && c === startCol) || (r === endRow && c === endCol)) return;
      if (path.some(([pr, pc]) => pr === r && pc === c)) return;
      crossMarkers.delete(key);
      tickMarkers.delete(key);
    }
    renderPlay();
  }

  function onPointerUp(e) {
    if (!dragMode) return;
    e.preventDefault();
    // Tap: if drag mode but no movement, cycle marker (handled in onPointerDown for path
    // and markers; nothing extra needed here)
    dragMode = null;
    saveProgress();
  }

  // ── API ────────────────────────────────────────────────────────────────

  async function submitScore(durationSeconds) {
    try {
      const result = await API.post('v1/scores', {
        puzzle_id: puzzleId,
        duration_seconds: durationSeconds,
      });
      const rank = result.rank_today;
      const streak = result.current_streak;
      showResults(durationSeconds, rank, streak, result.newly_unlocked || []);
    } catch (e) {
      showResults(durationSeconds, null, null, []);
    }
  }

  // ── Results rendering ──────────────────────────────────────────────────

  function showResults(durationSeconds, rank, streak, newlyUnlocked) {
    show('state-results');

    let headline = `Solved in ${fmtTime(durationSeconds)}!`;
    document.getElementById('results-headline').textContent = headline;

    const parts = [];
    if (rank) parts.push(`#${rank} today`);
    if (streak) parts.push(`🔥 ${streak}-day streak`);
    if (newlyUnlocked && newlyUnlocked.length) parts.push(`🏆 New trophy!`);
    document.getElementById('results-sub').textContent = parts.join(' · ');

    const canvas = document.getElementById('results-canvas');
    requestAnimationFrame(() => {
      drawGrid(canvas, puzzle, puzzle.solution, new Set(), new Set(), false);
    });

    const lbEl = document.getElementById('results-leaderboard');
    Leaderboard.render(lbEl, puzzleId, e => fmtTime(e.duration_seconds), myUserId);
  }

  // ── Init ───────────────────────────────────────────────────────────────

  async function init() {
    playCanvas = document.getElementById('play-canvas');

    await API.ensureSession();

    if (API.isLoggedIn()) {
      try {
        const me = await API.get('v1/users/me');
        myUserId = me.user_id;
      } catch (_) {}
    }

    let todayPuzzle;
    try {
      todayPuzzle = await API.get('v1/puzzles/today?game=routes');
    } catch (e) {
      show('state-error');
      document.getElementById('error-msg').textContent = e.message || 'Failed to load puzzle.';
      return;
    }

    puzzleId = todayPuzzle.puzzle_id;
    puzzle = generatePuzzle(puzzleId);

    if (todayPuzzle.already_played) {
      show('state-already-played');

      let durationSeconds = null;
      try {
        const scoreDetail = await API.get(`v1/scores/${puzzleId}/${myUserId}`);
        durationSeconds = scoreDetail.duration_seconds;
      } catch (_) {}

      const headline = durationSeconds != null
        ? `Already played — solved in ${fmtTime(durationSeconds)}`
        : 'Already played today!';
      document.getElementById('already-headline').textContent = headline;

      const streak = todayPuzzle.streak;
      const sub = streak ? `🔥 ${streak.current}-day streak` : '';
      document.getElementById('already-sub').textContent = sub;

      const canvas = document.getElementById('already-canvas');
      requestAnimationFrame(() => {
        drawGrid(canvas, puzzle, puzzle.solution, new Set(), new Set(), false);
      });

      const lbEl = document.getElementById('already-leaderboard');
      Leaderboard.render(lbEl, puzzleId, e => fmtTime(e.duration_seconds), myUserId);
      return;
    }

    // Restore saved progress
    const saved = loadProgress();
    if (saved) {
      path = saved.path || [];
      crossMarkers = new Set(saved.crossMarkers || []);
      tickMarkers = new Set(saved.tickMarkers || []);
      elapsedSeconds = saved.elapsedSeconds || 0;
    }

    show('state-playing');
    document.getElementById('timer').textContent = fmtTime(elapsedSeconds);

    // Wire canvas
    requestAnimationFrame(() => {
      renderPlay();
      playCanvas.addEventListener('pointerdown', onPointerDown);
      playCanvas.addEventListener('pointermove', onPointerMove);
      playCanvas.addEventListener('pointerup', onPointerUp);
      playCanvas.addEventListener('pointercancel', onPointerUp);
    });

    document.getElementById('clear-path-btn').addEventListener('click', () => {
      path = [];
      renderPlay();
      saveProgress();
    });

    startTimer();

    // Redraw on resize
    window.addEventListener('resize', () => { renderPlay(); });
  }

  document.addEventListener('DOMContentLoaded', init);
})();
