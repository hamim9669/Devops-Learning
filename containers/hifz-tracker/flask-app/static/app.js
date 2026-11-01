const CIRCUMFERENCE = 326.7;

async function api(path, options) {
  const res = await fetch(path, options);
  return res.json();
}

function countUp(el, to) {
  const start = performance.now();
  const duration = 1200;
  function tick(now) {
    const p = Math.min((now - start) / duration, 1);
    el.textContent = Math.round(to * p);
    if (p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

async function load() {
  const [summary, surahs] = await Promise.all([
    api("/api/summary"),
    api("/api/surahs"),
  ]);

  document.getElementById("bar").style.strokeDashoffset =
    CIRCUMFERENCE * (1 - summary.percent / 100);
  countUp(document.getElementById("pct"), Math.round(summary.percent));
  countUp(document.getElementById("ayahs"), summary.memorised_ayahs);
  document.getElementById("streak").textContent = summary.streak;
  document.getElementById("due").textContent = summary.due_count;

  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  surahs.forEach((s, i) => {
    const tile = document.createElement("div");
    tile.className = `tile ${s.status}`;
    tile.textContent = s.number;
    tile.title = `${s.name}: ${s.ayahs}/${s.total} (${s.status})`;
    tile.style.animationDelay = `${i * 10}ms`;
    tile.onclick = () => openSurah(s);
    grid.appendChild(tile);
  });
}

async function openSurah(s) {
  const input = prompt(
    `${s.name} (${s.total} ayahs). Ayahs memorised? Clear the box to log a revision.`,
    s.ayahs
  );
  if (input === null) return;

  let result;
  if (input.trim() === "") {
    result = await api(`/api/surah/${s.number}/revise`, { method: "POST" });
  } else {
    result = await api(`/api/surah/${s.number}/progress`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ayahs: Number(input) }),
    });
  }
  if (result.error) alert(result.error);
  load();
}

load();
