const jdFile = document.getElementById("jdFile");
const jdText = document.getElementById("jdText");
const resumeFiles = document.getElementById("resumeFiles");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusEl = document.getElementById("status");
const results = document.getElementById("results");

function drawGrid() {
  const canvas = document.getElementById("grid");
  const ctx = canvas.getContext("2d");
  const resize = () => {
    canvas.width = innerWidth;
    canvas.height = innerHeight;
  };
  resize();
  addEventListener("resize", resize);
  let t = 0;
  const loop = () => {
    t += 0.004;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(59,130,246,0.12)";
    ctx.lineWidth = 1;
    const gap = 42;
    const offset = (t * 20) % gap;
    for (let x = -gap; x < canvas.width + gap; x += gap) {
      ctx.beginPath();
      ctx.moveTo(x + offset, 0);
      ctx.lineTo(x + offset, canvas.height);
      ctx.stroke();
    }
    for (let y = -gap; y < canvas.height + gap; y += gap) {
      ctx.beginPath();
      ctx.moveTo(0, y + offset);
      ctx.lineTo(canvas.width, y + offset);
      ctx.stroke();
    }
    requestAnimationFrame(loop);
  };
  loop();
}
drawGrid();

function chips(items, cls) {
  if (!items || !items.length) return "<span class='chip'>None</span>";
  return items.map((s) => `<span class="chip ${cls || ""}">${s}</span>`).join("");
}

function bars(c) {
  const rows = [
    ["Skills", c.skill_match],
    ["Experience", c.experience_match],
    ["Education", c.education_match],
    ["Projects", c.project_match],
    ["Requirements", c.requirement_coverage],
  ];
  return rows
    .map(
      ([n, v]) =>
        `<div class="bar-row"><span>${n}</span><div class="bar"><span style="width:${v}%"></span></div><span>${v}</span></div>`
    )
    .join("");
}

function renderOne(r) {
  const evidence = (r.evidence || [])
    .map((e) => `<li>${e.claim} — <b>${e.confidence}</b>: ${e.reason}</li>`)
    .join("");
  const courses = (r.course_recommendations || [])
    .map((c) => `<li><a href="${c.url}" target="_blank" rel="noreferrer">${c.title}</a> (${c.platform})</li>`)
    .join("");
  return `
    <article class="card">
      <h3>${r.resume_name}</h3>
      <div class="grid">
        <div class="score-wrap">
          <div class="gauge" style="--p:${r.final_score}%"><div class="gauge-inner">${r.final_score}%</div></div>
          <div>Compatibility</div>
        </div>
        <div>
          <h3>Why this score</h3>
          <div class="bars">${bars(r.component_scores)}</div>
        </div>
      </div>
      <h3>Matched skills</h3>
      <div class="chips">${chips(r.matched_skills)}</div>
      <h3>Missing skills</h3>
      <div class="chips">${chips(r.missing_skills, "miss")}</div>
      <h3>Partial skills</h3>
      <div class="chips">${chips(r.partial_skills, "partial")}</div>
      <h3>Experience alignment</h3>
      <p>${r.experience_alignment || "—"}</p>
      <h3>Evidence confidence</h3>
      <ul>${evidence || "<li>No claims extracted</li>"}</ul>
      <h3>Suggestion</h3>
      <p>${r.suggestion || "—"}</p>
      <h3>Learn next</h3>
      <ul>${courses || "<li>None</li>"}</ul>
    </article>`;
}

analyzeBtn.addEventListener("click", async () => {
  const files = [...(resumeFiles.files || [])];
  if (!files.length) {
    statusEl.textContent = "Add at least one resume.";
    return;
  }
  analyzeBtn.disabled = true;
  statusEl.textContent = "Analyzing…";
  results.classList.add("hidden");
  try {
    let payload;
    if (files.length === 1) {
      const form = new FormData();
      if (jdFile.files[0]) form.append("jd", jdFile.files[0]);
      form.append("jd_text", jdText.value);
      form.append("resume", files[0]);
      const res = await fetch("/api/analyze", { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      payload = { results: [await res.json()] };
    } else {
      const form = new FormData();
      if (jdFile.files[0]) form.append("jd", jdFile.files[0]);
      form.append("jd_text", jdText.value);
      files.forEach((f) => form.append("resumes", f));
      const res = await fetch("/api/analyze-multiple", { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      payload = await res.json();
    }
    results.innerHTML =
      (payload.best_fit ? `<p class="card">Best alignment: <b>${payload.best_fit}</b> — not a hiring decision.</p>` : "") +
      payload.results.map(renderOne).join("");
    results.classList.remove("hidden");
    statusEl.textContent = "Done.";
  } catch (err) {
    statusEl.textContent = err.message || "Analysis failed.";
  } finally {
    analyzeBtn.disabled = false;
  }
});
