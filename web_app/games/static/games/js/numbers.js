(() => {
  let puzzle = null;
  let target = 0;
  let tiles = [];       // { value, id, used }
  let selectedTile = null;   // index into tiles[]
  let pendingOp = null;
  let steps = [];
  let timerInterval = null;
  let secondsLeft = 0;
  let gameOver = false;

  const OP_MAP = { '+': '+', '−': '-', '×': '*', '÷': '/' };
  const OP_DISPLAY = { '+': '+', '-': '−', '*': '×', '/': '÷' };

  function show(id) {
    ['state-loading','state-already-played','state-playing','state-results','state-error']
      .forEach(s => { const el = document.getElementById(s); if (el) el.style.display = s === id ? '' : 'none'; });
  }

  function fmtTime(s) {
    const m = Math.floor(s / 60);
    return `${m}:${String(s % 60).padStart(2,'0')}`;
  }

  function startTimer() {
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      secondsLeft--;
      document.getElementById('timer').textContent = fmtTime(secondsLeft);
      if (secondsLeft <= 30) document.getElementById('timer').classList.add('timer-urgent');
      if (secondsLeft <= 0) finish(false);
    }, 1000);
  }

  function renderTiles() {
    const el = document.getElementById('tiles');
    el.innerHTML = '';
    tiles.forEach((tile, i) => {
      if (tile.used) return;  // disappear used tiles
      const btn = document.createElement('button');
      btn.className = 'number-tile' + (selectedTile === i ? ' selected' : '');
      btn.textContent = tile.value;
      btn.addEventListener('click', () => onTileClick(i));
      el.appendChild(btn);
    });
  }

  function renderCalcDisplay() {
    const el = document.getElementById('calc-display');
    if (selectedTile === null) { el.textContent = ''; return; }
    const val = tiles[selectedTile].value;
    el.textContent = pendingOp ? `${val} ${pendingOp}` : String(val);
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

  function onTileClick(i) {
    if (tiles[i].used) return;

    if (selectedTile === null) {
      selectedTile = i;
      pendingOp = null;
      renderTiles();
      renderCalcDisplay();
      setOpsEnabled(true);
      return;
    }

    if (selectedTile === i) {
      // deselect
      selectedTile = null;
      pendingOp = null;
      renderTiles();
      renderCalcDisplay();
      setOpsEnabled(false);
      return;
    }

    if (pendingOp === null) {
      // swap selection to this tile
      selectedTile = i;
      renderTiles();
      renderCalcDisplay();
      return;
    }

    applyOp(selectedTile, pendingOp, i);
  }

  function applyOp(leftIdx, op, rightIdx) {
    const a = tiles[leftIdx].value;
    const b = tiles[rightIdx].value;
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

    steps.push({ a, op: apiOp, b, result });
    tiles[leftIdx].used = true;
    tiles[rightIdx].used = true;
    tiles.push({ value: result, id: Date.now(), used: false });

    selectedTile = null;
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
      if (selectedTile === null) return;
      pendingOp = btn.dataset.op;
      document.querySelectorAll('.op-btn').forEach(b =>
        b.classList.toggle('selected', b.dataset.op === pendingOp));
      renderCalcDisplay();
    });
  });

  document.getElementById('undo-btn').addEventListener('click', () => {
    if (steps.length === 0) return;
    steps.pop();
    tiles.pop();  // remove result tile
    // un-use the last two used tiles
    let count = 0;
    for (let i = tiles.length - 1; i >= 0 && count < 2; i--) {
      if (tiles[i].used) { tiles[i].used = false; count++; }
    }
    selectedTile = null;
    pendingOp = null;
    renderTiles();
    renderCalcDisplay();
    setOpsEnabled(false);
    updateSubmitBtn();
    renderLastStep();
  });

  document.getElementById('reset-btn').addEventListener('click', () => {
    tiles = puzzle.numbers.map((v, i) => ({ value: v, id: i, used: false }));
    steps = [];
    selectedTile = null;
    pendingOp = null;
    renderTiles();
    document.getElementById('calc-display').textContent = '';
    setOpsEnabled(false);
    updateSubmitBtn();
  });

  document.getElementById('submit-btn').addEventListener('click', () => finish(true));

  async function finish(playerSolved) {
    clearInterval(timerInterval);
    gameOver = true;

    const durationUsed = (puzzle.duration_seconds || 180) - Math.max(0, secondsLeft);
    const available = tiles.filter(t => !t.used).map(t => t.value);
    const closest = available.reduce((best, v) =>
      Math.abs(v - target) < Math.abs(best - target) ? v : best, available[0] || target);

    try {
      await API.post('v1/scores', {
        puzzle_id: puzzle.puzzle_id,
        duration_seconds: durationUsed,
        steps: playerSolved ? steps : [],
        result_value: playerSolved ? target : closest,
      });
    } catch (e) {
      // non-fatal
    }
    showResults(playerSolved, closest);
  }

  function showResults(playerSolved, closest) {
    show('state-results');

    if (playerSolved) {
      document.getElementById('results-headline').textContent = 'Solved!';
      document.getElementById('results-sub').textContent =
        `Reached ${target} in ${steps.length} step${steps.length !== 1 ? 's' : ''}`;
    } else {
      document.getElementById('results-headline').textContent = 'Time up!';
      document.getElementById('results-sub').textContent =
        closest ? `Closest: ${closest} (${Math.abs(closest - target)} away from ${target})` : `Target was ${target}`;
    }

    if (steps.length > 0) {
      document.getElementById('results-steps').innerHTML = steps.map(s =>
        `<div class="solution-step">${s.a} ${OP_DISPLAY[s.op] || s.op} ${s.b} = <strong>${s.result}</strong></div>`
      ).join('');
    }

    if (puzzle.solution && puzzle.solution.length > 0) {
      document.getElementById('solution-wrap').style.display = '';
      document.getElementById('solution-steps').innerHTML = puzzle.solution.map(s =>
        `<div class="solution-step">${s.a} ${OP_DISPLAY[s.op] || s.op} ${s.b} = <strong>${s.result}</strong></div>`
      ).join('');
    }
  }

  async function init() {
    try {
      await API.ensureSession();
      const data = await API.get('v1/puzzles/today?game=numbers');
      puzzle = data;
      target = data.target;
      tiles = data.numbers.map((v, i) => ({ value: v, id: i, used: false }));

      if (data.already_played) {
        show('state-already-played');
        const rv = data.your_result_value;
        document.getElementById('already-result').textContent =
          rv === target ? `You reached ${target}!` :
          rv != null ? `Closest: ${rv} (${Math.abs(rv - target)} away)` : '';
        return;
      }

      secondsLeft = data.duration_seconds || 180;
      document.getElementById('timer').textContent = fmtTime(secondsLeft);
      document.getElementById('target').textContent = target;

      show('state-playing');
      renderTiles();
      setOpsEnabled(false);
      updateSubmitBtn();
      startTimer();
    } catch (e) {
      show('state-error');
      document.getElementById('error-msg').textContent = e.message || 'Failed to load puzzle.';
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
