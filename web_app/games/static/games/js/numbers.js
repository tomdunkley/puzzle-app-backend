(() => {
  let puzzle = null;
  let target = 0;
  let tiles = [];
  let selectedTileId = null;
  let pendingOp = null;
  let steps = [];
  let nextStepId = 0;
  let bestValue = null;
  let bestSteps = [];
  let allComputedValues = [];
  let timerInterval = null;
  let secondsLeft = 0;
  let gameOver = false;
  let paused = false;
  let myUserId = null;

  const OP_MAP = { '+': '+', '−': '-', '×': '*', '÷': '/' };
  const OP_DISPLAY = { '+': '+', '-': '−', '*': '×', '/': '÷' };

  const STORAGE_KEY_PREFIX = 'td_numbers_progress_';
  function storageKey() { return puzzle ? STORAGE_KEY_PREFIX + puzzle.puzzle_id : null; }

  function saveProgress() {
    const key = storageKey();
    if (!key || gameOver) return;
    localStorage.setItem(key, JSON.stringify({
      tiles, steps, nextStepId,
      bestValue, bestSteps, allComputedValues, secondsLeft, paused,
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
      if (secondsLeft <= 0) finish(false);
    }, 1000);
  }

  function renderTiles() {
    const el = document.getElementById('tiles');
    el.innerHTML = '';
    tiles.forEach(tile => {
      if (tile.used) return;
      const wrap = document.createElement('div');
      wrap.className = 'number-tile-wrap';

      const btn = document.createElement('button');
      btn.className = 'number-tile' + (tile.id === selectedTileId ? ' selected' : '');
      btn.textContent = tile.value;
      btn.addEventListener('click', () => onTileClick(tile.id));
      wrap.appendChild(btn);

      if (tile.sourceIds) {
        const undoBtn = document.createElement('button');
        undoBtn.className = 'number-tile-undo';
        undoBtn.title = 'Undo';
        undoBtn.textContent = '↩';
        undoBtn.addEventListener('click', e => { e.stopPropagation(); undoTile(tile.id); });
        wrap.appendChild(undoBtn);
      }

      el.appendChild(wrap);
    });
  }

  function renderCalcDisplay() {
    const el = document.getElementById('calc-display');
    if (selectedTileId === null) { el.textContent = ''; return; }
    const tile = tiles.find(t => t.id === selectedTileId);
    if (!tile) { el.textContent = ''; return; }
    el.textContent = pendingOp ? `${tile.value} ${pendingOp}` : String(tile.value);
  }

  function renderClosestDisplay() {
    const el = document.getElementById('closest-display');
    if (!el) return;
    if (bestValue === null) { el.textContent = ''; return; }
    if (bestValue === target) {
      el.textContent = `You've got it: ${target}`;
      el.className = 'closest-display closest-display--solved';
    } else {
      el.textContent = `Closest: ${bestValue} (${Math.abs(bestValue - target)} away)`;
      el.className = 'closest-display';
    }
  }

  function setOpsEnabled(enabled) {
    document.querySelectorAll('.op-btn').forEach(b => {
      b.disabled = !enabled;
      b.classList.toggle('selected', enabled && b.dataset.op === pendingOp);
    });
  }

  function updateSubmitBtn() {
    const available = tiles.filter(t => !t.used).map(t => t.value);
    document.getElementById('submit-btn').disabled = !available.includes(target);
  }

  function onTileClick(tileId) {
    const tile = tiles.find(t => t.id === tileId && !t.used);
    if (!tile) return;

    if (selectedTileId === null) {
      selectedTileId = tileId;
      pendingOp = null;
      renderTiles();
      renderCalcDisplay();
      setOpsEnabled(true);
      return;
    }

    if (selectedTileId === tileId) {
      selectedTileId = null;
      pendingOp = null;
      renderTiles();
      renderCalcDisplay();
      setOpsEnabled(false);
      return;
    }

    if (pendingOp === null) {
      selectedTileId = tileId;
      renderTiles();
      renderCalcDisplay();
      return;
    }

    applyOp(selectedTileId, pendingOp, tileId);
  }

  function applyOp(leftId, op, rightId) {
    const leftTile = tiles.find(t => t.id === leftId);
    const rightTile = tiles.find(t => t.id === rightId);
    if (!leftTile || !rightTile) return;

    const a = leftTile.value;
    const b = rightTile.value;
    const apiOp = OP_MAP[op];
    let result;
    if (apiOp === '+') result = a + b;
    else if (apiOp === '-') result = a - b;
    else if (apiOp === '*') result = a * b;
    else if (apiOp === '/') result = a / b;

    if (!Number.isInteger(result) || result <= 0) {
      flashCalc('Not valid');
      return;
    }

    const stepId = nextStepId++;
    steps.push({ id: stepId, a, op: apiOp, b, result });
    allComputedValues.push(result);

    if (bestValue === null || Math.abs(result - target) < Math.abs(bestValue - target)) {
      bestValue = result;
      bestSteps = [...steps];
    }

    leftTile.used = true;
    rightTile.used = true;
    tiles.push({ value: result, id: Date.now(), used: false, sourceIds: [leftId, rightId], stepId });

    selectedTileId = null;
    pendingOp = null;
    renderTiles();
    renderCalcDisplay();
    setOpsEnabled(false);
    updateSubmitBtn();
    renderLastStep();
    renderClosestDisplay();

    if (result === target) {
      finish(true);
    }
  }

  function undoTile(tileId) {
    const tile = tiles.find(t => t.id === tileId);
    if (!tile || !tile.sourceIds) return;

    tile.sourceIds.forEach(srcId => {
      const src = tiles.find(t => t.id === srcId);
      if (src) src.used = false;
    });

    const idx = tiles.findIndex(t => t.id === tileId);
    if (idx >= 0) tiles.splice(idx, 1);

    const stepIdx = steps.findIndex(s => s.id === tile.stepId);
    if (stepIdx >= 0) steps.splice(stepIdx, 1);

    selectedTileId = null;
    pendingOp = null;
    renderTiles();
    renderCalcDisplay();
    setOpsEnabled(false);
    updateSubmitBtn();
    renderLastStep();
  }

  function renderLastStep() {
    const el = document.getElementById('calc-display');
    if (steps.length === 0) { el.textContent = ''; return; }
    const s = steps[steps.length - 1];
    el.textContent = `${s.a} ${OP_DISPLAY[s.op] || s.op} ${s.b} = ${s.result}`;
  }

  function flashCalc(msg) {
    const el = document.getElementById('calc-display');
    el.textContent = msg;
    el.classList.add('flash-error');
    setTimeout(() => { el.classList.remove('flash-error'); renderLastStep(); }, 1000);
  }

  document.querySelectorAll('.op-btn').forEach(btn => {
    btn.disabled = true;
    btn.addEventListener('click', () => {
      if (selectedTileId === null) return;
      pendingOp = btn.dataset.op;
      document.querySelectorAll('.op-btn').forEach(b =>
        b.classList.toggle('selected', b.dataset.op === pendingOp));
      renderCalcDisplay();
    });
  });

  document.getElementById('reset-btn').addEventListener('click', () => {
    tiles = puzzle.numbers.map((v, i) => ({ value: v, id: i, used: false }));
    steps = [];
    selectedTileId = null;
    pendingOp = null;
    renderTiles();
    document.getElementById('calc-display').textContent = '';
    setOpsEnabled(false);
    updateSubmitBtn();
  });

  document.getElementById('submit-btn').addEventListener('click', () => finish(true));

  document.getElementById('pause-btn').addEventListener('click', () => {
    paused = true;
    saveProgress();
    const closest = bestValue !== null ? bestValue : '';
    document.getElementById('pause-closest').textContent =
      closest !== '' ? (closest === target ? `You've got it: ${target}` : `Closest so far: ${closest} (${Math.abs(closest - target)} away)`) : '';
    show('state-paused');
  });

  document.getElementById('resume-btn').addEventListener('click', () => {
    paused = false;
    show('state-playing');
  });

  document.getElementById('finish-early-btn').addEventListener('click', () => finish(false));

  async function finish(playerSolved) {
    if (gameOver) return;
    clearInterval(timerInterval);
    gameOver = true;
    clearProgress();

    const durationUsed = (puzzle.duration_seconds || 180) - Math.max(0, secondsLeft);

    const startingValues = puzzle.numbers || [];
    const fallbackBest = startingValues.length
      ? startingValues.reduce((best, v) => Math.abs(v - target) < Math.abs(best - target) ? v : best, startingValues[0])
      : target;
    const resultValue = playerSolved ? target : (bestValue !== null ? bestValue : fallbackBest);
    const resultSteps = playerSolved ? steps : bestSteps;

    try {
      await API.post('v1/scores', {
        puzzle_id: puzzle.puzzle_id,
        duration_seconds: durationUsed,
        steps: resultSteps,
        result_value: resultValue,
        all_computed_values: allComputedValues,
      });
    } catch (_) { /* non-fatal */ }

    showResults(playerSolved, resultValue, puzzle.puzzle_id);
  }

  async function showResults(playerSolved, resultValue, puzzleId) {
    show('state-results');

    if (playerSolved) {
      document.getElementById('results-headline').textContent = 'Solved!';
      document.getElementById('results-sub').textContent =
        `Reached ${target} in ${bestSteps.length} step${bestSteps.length !== 1 ? 's' : ''}`;
    } else {
      document.getElementById('results-headline').textContent = 'Time up!';
      document.getElementById('results-sub').textContent =
        resultValue != null
          ? `Closest: ${resultValue} (${Math.abs(resultValue - target)} away from ${target})`
          : `Target was ${target}`;
    }

    if (bestSteps.length > 0) {
      document.getElementById('results-steps').innerHTML = bestSteps.map(s =>
        `<div class="solution-step">${s.a} ${OP_DISPLAY[s.op] || s.op} ${s.b} = <strong>${s.result}</strong></div>`
      ).join('');
    }

    if (puzzle.solution && puzzle.solution.length > 0) {
      document.getElementById('solution-wrap').style.display = '';
      document.getElementById('solution-steps').innerHTML = puzzle.solution.map(s =>
        `<div class="solution-step">${s.a} ${OP_DISPLAY[s.op] || s.op} ${s.b} = <strong>${s.result}</strong></div>`
      ).join('');
    }

    // Leaderboards
    if (puzzleId) {
      await Leaderboard.render(
        document.getElementById('results-leaderboard'),
        puzzleId,
        e => {
          const rv = e.result_value;
          const tgt = e.target;
          if (rv == null) return '—';
          return rv === tgt ? `${rv} ✓` : `${rv} (${Math.abs(rv - tgt)} away)`;
        },
        myUserId,
      );
    }
  }

  async function showAlreadyPlayed(data) {
    show('state-already-played');
    const rv = data.your_result_value;
    const tgt = data.target;

    document.getElementById('already-headline').textContent =
      rv === tgt ? 'Solved!' : 'Already played';
    document.getElementById('already-result').textContent =
      rv === tgt ? `Reached ${tgt}!` :
      rv != null ? `Closest: ${rv} (${Math.abs(rv - tgt)} away from ${tgt})` : '';

    // Leaderboards
    if (data.puzzle_id) {
      await Leaderboard.render(
        document.getElementById('already-leaderboard'),
        data.puzzle_id,
        e => {
          const rv2 = e.result_value;
          const tgt2 = e.target;
          if (rv2 == null) return '—';
          return rv2 === tgt2 ? `${rv2} ✓` : `${rv2} (${Math.abs(rv2 - tgt2)} away)`;
        },
        myUserId,
      );
    }
  }

  async function loadPuzzleAndStart() {
    if (API.isLoggedIn()) {
      try {
        const me = await API.get('v1/users/me');
        myUserId = me.user_id;
      } catch (_) { /* guest */ }
    }

    const data = await API.get('v1/puzzles/today?game=numbers');
    puzzle = data;
    target = data.target;

    if (data.already_played) {
      await showAlreadyPlayed(data);
      return;
    }

    const saved = loadProgress();
    if (saved) {
      tiles = saved.tiles;
      steps = saved.steps;
      nextStepId = saved.nextStepId || 0;
      bestValue = saved.bestValue;
      bestSteps = saved.bestSteps || [];
      allComputedValues = saved.allComputedValues || [];
      secondsLeft = saved.secondsLeft ?? (data.duration_seconds || 180);
      paused = saved.paused || false;
    } else {
      tiles = data.numbers.map((v, i) => ({ value: v, id: i, used: false }));
      steps = [];
      nextStepId = data.numbers.length;
      bestValue = data.numbers.reduce((best, v) =>
        Math.abs(v - target) < Math.abs(best - target) ? v : best, data.numbers[0]);
      bestSteps = [];
      allComputedValues = [];
      secondsLeft = data.duration_seconds || 180;
    }

    document.getElementById('timer').textContent = fmtTime(secondsLeft);
    document.getElementById('target').textContent = target;

    show('state-playing');
    renderTiles();
    setOpsEnabled(false);
    updateSubmitBtn();
    renderClosestDisplay();
    startTimer();

    if (paused) {
      const closest = bestValue !== null ? bestValue : '';
      document.getElementById('pause-closest').textContent =
        closest !== '' ? (closest === target ? `You've got it: ${target}` : `Closest so far: ${closest} (${Math.abs(closest - target)} away)`) : '';
      show('state-paused');
    }
  }

  async function init() {
    if (!localStorage.getItem('td_access_token')) {
      // No session yet — show a start gate so we only create a guest account if they actually play
      const loadingEl = document.getElementById('state-loading');
      loadingEl.innerHTML = `
        <div style="text-align:center;padding:40px 0">
          <p style="color:var(--ink-mid);margin-bottom:20px">Ready to play today's Numbers puzzle?</p>
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
