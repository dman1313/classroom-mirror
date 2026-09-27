"use strict";
const $ = (id) => document.getElementById(id);
let state = { status: "idle", tracks: [] },
  view = "session",
  recaps = [],
  currentRecap = null;
let polling = false,
  previewBusy = false,
  cameraImage = null,
  lastFrameAt = 0,
  failures = 0;
let deleteAction = null,
  transitionHandled = null;
let localCover = false;
let connectionError = false;
const active = () => ["starting", "running", "stopping"].includes(state.status);
const fmt = (seconds) => {
  const n = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`;
};
const capitalize = (x) =>
  (x || "").charAt(0).toUpperCase() + (x || "").slice(1);
const date = (value) =>
  new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
const ctx = $("room").getContext("2d"),
  chart = $("timeline").getContext("2d");

async function api(path, method = "GET", body) {
  const response = await fetch(path, {
    method,
    cache: "no-store",
    headers: { "Content-Type": "application/json", "X-Classroom-Mirror": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error ||
        (data.detail
          ? "Check the session settings and try again."
          : "The app could not complete that request."),
    );
  return data;
}
function error(message) {
  $("error").textContent = message || "";
  $("error").hidden = !message;
}
function clearFrame() {
  if (cameraImage) cameraImage.close();
  cameraImage = null;
  lastFrameAt = 0;
  ctx.clearRect(0, 0, 960, 540);
}
function privacy(hidden) {
  $("privacy").hidden = !hidden;
  $("app-shell").hidden = hidden;
  state.hidden = hidden;
  if (hidden) {
    clearFrame();
    $("restore").focus();
  }
}
async function setPrivacy(hidden) {
  if (hidden) {
    localCover = true;
    privacy(true);
  }
  try {
    await api("/api/hide", "POST", { hidden });
    localCover = hidden;
    privacy(hidden);
    await tick();
  } catch (e) {
    if (!hidden) $("restore").textContent = "Cannot reconnect — try again";
    else $("private-stop").textContent = "Stop session";
    error(e.message);
  }
}
function chooseSource() {
  const demo = document.querySelector("[name=source]:checked").value === "demo";
  $("camera-options").hidden = demo;
  $("adult-row").hidden = demo;
  $("demo-note").hidden = !demo;
}
async function showView(next) {
  view = next;
  for (const name of ["session", "history", "recap", "help"])
    $(name + "-view").hidden = name !== next;
  document.querySelectorAll("[data-view]").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === next);
    if (b.dataset.view === next) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  $("breadcrumb").textContent =
    `Workspace / ${{ session: "Live session", history: "Session recaps", recap: "Session recap", help: "Getting started" }[next]}`;
  if (next === "history") await loadHistory();
  if (next === "session") drawRoom();
}
document
  .querySelectorAll("[data-view]")
  .forEach(
    (b) =>
      (b.onclick = () =>
        showView(b.dataset.view).catch((e) => error(e.message))),
  );
document.querySelector(".brand").onclick = (e) => {
  e.preventDefault();
  showView("session");
};
document
  .querySelectorAll("[name=source]")
  .forEach((r) => (r.onchange = chooseSource));
$("hide").onclick = () => setPrivacy(true);
$("restore").onclick = () => setPrivacy(false);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("confirm-dialog").open) {
    e.preventDefault();
    setPrivacy(true);
  }
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden && active()) setPrivacy(true);
});
$("scan").onclick = async () => {
  error("");
  $("scan").disabled = true;
  $("scan").textContent = "Checking…";
  try {
    const data = await api("/api/cameras", "POST");
    $("camera").replaceChildren(new Option("Select a camera", ""));
    for (const c of data.cameras)
      $("camera").add(new Option(`Camera ${c.index} · ${c.backend}`, c.index));
    $("camera-help").textContent = data.cameras.length
      ? "Select the camera you want. The first view appears after Start."
      : "No cameras found. Check camera permissions in Getting started, then try again.";
    if (data.cameras.length === 1)
      $("camera").value = String(data.cameras[0].index);
  } catch (e) {
    error(e.message);
  } finally {
    $("scan").disabled = false;
    $("scan").textContent = "Find cameras ↻";
  }
};
async function startSession(sourceOverride) {
  error("");
  const source =
    sourceOverride || document.querySelector("[name=source]:checked").value;
  if (source === "camera" && $("camera").value === "") {
    error("Choose Find cameras, then select the camera you want to use.");
    return;
  }
  if (source === "camera" && !$("adult").checked) {
    error(
      "Confirm the consenting-adults-only trial before starting the camera.",
    );
    $("adult").focus();
    return;
  }
  $("start").disabled = true;
  $("try-demo").disabled = true;
  try {
    await api("/api/start", "POST", {
      source,
      camera_index: source === "camera" ? Number($("camera").value) : 0,
      sensitivity: document.querySelector("[name=sensitivity]:checked").value,
      duration_minutes: Number($("duration").value),
      adult_confirmed: $("adult").checked,
    });
    clearFrame();
    transitionHandled = null;
    await showView("session");
    await tick();
  } catch (e) {
    error(e.message);
  } finally {
    $("start").disabled = false;
    $("try-demo").disabled = false;
  }
}
$("start-form").onsubmit = (e) => {
  e.preventDefault();
  startSession();
};
$("try-demo").onclick = () => {
  document.querySelector("[name=source][value=demo]").checked = true;
  chooseSource();
  startSession("demo");
};
async function stopSession() {
  $("stop").disabled = true;
  $("private-stop").disabled = true;
  try {
    await api("/api/stop", "POST");
    if (state.hidden) await setPrivacy(false);
    await tick();
  } catch (e) {
    error(e.message);
  } finally {
    $("stop").disabled = false;
    $("private-stop").disabled = false;
  }
}
$("stop").onclick = stopSession;
$("private-stop").onclick = stopSession;

function drawRoom() {
  ctx.fillStyle = "#203b36";
  ctx.fillRect(0, 0, 960, 540);
  if (state.hidden) return;
  const demo = state.source === "demo" && active();
  if (
    cameraImage &&
    state.source === "camera" &&
    state.status === "running" &&
    performance.now() - lastFrameAt < 3000
  ) {
    // Match the camera's aspect ratio without stretching its coordinates.
    const scale = Math.min(960 / cameraImage.width, 540 / cameraImage.height);
    const w = cameraImage.width * scale,
      h = cameraImage.height * scale;
    ctx.drawImage(cameraImage, (960 - w) / 2, (540 - h) / 2, w, h);
  } else {
    ctx.strokeStyle = "#ffffff07";
    ctx.lineWidth = 1;
    for (let x = 30; x < 960; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, 540);
      ctx.stroke();
    }
    for (let y = 20; y < 540; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(960, y);
      ctx.stroke();
    }
    if (demo) {
      ctx.fillStyle = "#b8c7a450";
      ctx.font = "11px system-ui";
      ctx.fillText("PRACTICE SESSION · MADE-UP FIGURES", 30, 30);
    }
  }
  if (!active()) return;
  if (!demo && (!cameraImage || performance.now() - lastFrameAt >= 3000))
    return;
  let w = 960,
    h = 540,
    ox = 0,
    oy = 0;
  if (!demo && cameraImage) {
    const scale = Math.min(960 / cameraImage.width, 540 / cameraImage.height);
    w = cameraImage.width * scale;
    h = cameraImage.height * scale;
    ox = (960 - w) / 2;
    oy = (540 - h) / 2;
  }
  for (const tr of state.tracks || []) {
    const [x, y, bw, bh] = tr.bbox,
      c =
        tr.band === "red"
          ? "#e29b84"
          : tr.band === "yellow"
            ? "#e0bf70"
            : "#97c3a5";
    const px = ox + x * w,
      py = oy + y * h,
      pw = bw * w,
      ph = bh * h;
    if (demo) {
      const kp = tr.keypoints || {},
        bones = [
          ["left_shoulder", "right_shoulder"],
          ["left_shoulder", "left_hip"],
          ["right_shoulder", "right_hip"],
          ["left_hip", "right_hip"],
          ["left_shoulder", "left_elbow"],
          ["left_elbow", "left_wrist"],
          ["right_shoulder", "right_elbow"],
          ["right_elbow", "right_wrist"],
          ["left_hip", "left_knee"],
          ["left_knee", "left_ankle"],
          ["right_hip", "right_knee"],
          ["right_knee", "right_ankle"],
        ];
      ctx.strokeStyle = "#a6bba6";
      ctx.lineWidth = 9;
      ctx.lineCap = "round";
      for (const [a, b] of bones) {
        if (!kp[a] || !kp[b]) continue;
        ctx.beginPath();
        ctx.moveTo(kp[a][0] * w, kp[a][1] * h);
        ctx.lineTo(kp[b][0] * w, kp[b][1] * h);
        ctx.stroke();
      }
      const head = kp.nose;
      if (head) {
        ctx.fillStyle = "#b1c2ae";
        ctx.beginPath();
        ctx.arc(head[0] * w, head[1] * h, 12, 0, 2 * Math.PI);
        ctx.fill();
      }
    }
    ctx.strokeStyle = c;
    ctx.lineWidth = 2;
    ctx.lineCap = "butt";
    ctx.strokeRect(px, py, pw, ph);
    ctx.fillStyle = c;
    ctx.fillRect(px, Math.max(0, py - 25), 62, 25);
    ctx.fillStyle = "#203b36";
    ctx.font = "600 13px system-ui";
    ctx.fillText(
      `#${String(tr.number).padStart(2, "0")}`,
      px + 10,
      Math.max(0, py - 25) + 17,
    );
    if (tr.moving) {
      ctx.fillStyle = c;
      ctx.beginPath();
      ctx.arc(px + pw - 9, py + 9, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}
function drawChart(context, rows, width, height) {
  context.clearRect(0, 0, width, height);
  context.strokeStyle = "#e8ece3";
  context.lineWidth = 1;
  for (let y = 8; y < height; y += 26) {
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(width, y);
    context.stroke();
  }
  if (!rows || !rows.length) {
    context.fillStyle = "#a8b19f";
    context.font = "12px system-ui";
    context.textAlign = "center";
    context.fillText(
      "Your session timeline will appear here",
      width / 2,
      height / 2 + 3,
    );
    context.textAlign = "left";
    return;
  }
  const max = Math.max(1, ...rows.map((r) => r.people)),
    step = width / Math.max(20, rows.length);
  for (let i = 0; i < rows.length; i++) {
    const v = (rows[i].moving / max) * (height - 12);
    context.fillStyle = "#89ac8d";
    context.fillRect(
      i * step + 2,
      height - Math.max(2, v),
      Math.max(2, step - 5),
      Math.max(2, v),
    );
  }
}
function renderState() {
  const running = active(),
    demo = state.source === "demo";
  $("setup-card").hidden = running;
  $("live-card").hidden = !running;
  $("nav-live").hidden = !running;
  $("page-title").textContent = running
    ? demo
      ? "A space to practise."
      : "Your classroom, in the moment."
    : "A little perspective. A clearer classroom.";
  $("page-subtitle").textContent = running
    ? demo
      ? "Made-up figures. Real controls. Explore what a session can show."
      : "A private view of movement and raised hands as they happen."
    : "Notice movement, follow raised hands, and reflect on the session.";
  $("session-badge").textContent = running
    ? demo
      ? "● Practice session"
      : "● Live session"
    : "● Ready when you are";
  $("session-badge").className =
    "session-badge" + (running ? (demo ? " practice" : " running") : "");
  for (const key of ["people", "moving", "raises"])
    $(key).textContent = running ? (state[key] ?? "—") : "—";
  $("timer").textContent = running
    ? fmt(state.duration - state.elapsed)
    : "—:—";
  $("timer-caption").textContent = running
    ? `${fmt(state.elapsed)} elapsed · stops automatically`
    : "Choose a session length";
  $("source-label").textContent = running
    ? demo
      ? "PRACTICE · SYNTHETIC"
      : "LIVE CAMERA"
    : "CAMERA OFF";
  $("stage-empty").hidden = running;
  const waiting =
    state.status === "starting" ||
    state.status === "stopping" ||
    (state.status === "running" &&
      !demo &&
      performance.now() - lastFrameAt > 3000);
  $("stage-status").hidden = !waiting;
  $("stage-status").querySelector("h3").textContent =
    state.status === "stopping"
      ? "Finishing your session…"
      : state.status === "starting"
        ? "Getting things ready…"
        : "Waiting for a live image…";
  $("stage-message").textContent =
    state.status === "stopping"
      ? "Releasing the camera and saving the recap."
      : state.status === "starting"
        ? demo
          ? "Preparing your practice figures."
          : "Loading the local pose model and selected camera. This may take a moment."
        : "If this continues, stop and check your camera connection.";
  $("live-sensitivity").textContent = capitalize(state.sensitivity);
  $("live-source").textContent = demo ? "Practice" : "Camera";
  $("live-intro").textContent = demo
    ? "This session uses made-up figures."
    : "Your view, in the moment.";
  const list = $("track-list");
  list.replaceChildren();
  if (!(state.tracks || []).length) {
    const p = document.createElement("p");
    p.className = "field-note";
    p.textContent =
      state.status === "starting"
        ? "Preparing the session…"
        : "No people detected. Check the camera angle and lighting.";
    list.append(p);
  }
  for (const tr of state.tracks || []) {
    const row = document.createElement("div");
    row.className = "track-row " + tr.band;
    const number = document.createElement("span");
    number.className = "track-number";
    number.textContent = String(tr.number).padStart(2, "0");
    const copy = document.createElement("span");
    copy.className = "track-copy";
    copy.textContent =
      tr.band === "red"
        ? "Sustained movement"
        : tr.band === "yellow"
          ? "Movement continues"
          : tr.moving
            ? "Moving"
            : "In view";
    const note = document.createElement("small");
    note.textContent = "Session position";
    copy.append(note);
    const raises = document.createElement("span");
    raises.className = "track-raises";
    raises.textContent = `☝ ${tr.raises}`;
    row.append(number, copy, raises);
    list.append(row);
  }
  drawRoom();
  drawChart(chart, state.timeline, 900, 105);
}
async function pollPreview() {
  if (
    previewBusy ||
    state.status !== "running" ||
    state.source !== "camera" ||
    state.hidden ||
    view !== "session" ||
    document.hidden
  )
    return;
  previewBusy = true;
  try {
    const r = await fetch("/api/preview.jpg", { cache: "no-store" });
    if (r.status !== 200) return;
    const blob = await r.blob();
    const img = await createImageBitmap(blob);
    if (state.status === "running" && !state.hidden) {
      if (cameraImage) cameraImage.close();
      cameraImage = img;
      lastFrameAt = performance.now();
      drawRoom();
    } else img.close();
  } catch (e) {
    /* State and stale-frame status communicate capture errors. */
  } finally {
    previewBusy = false;
  }
}
async function tick() {
  if (polling) return;
  polling = true;
  try {
    const next = await api("/api/state");
    failures = 0;
    state = next;
    if (connectionError) {
      error("");
      connectionError = false;
    }
    if (state.hidden || localCover) {
      privacy(true);
      return;
    }
    if (!$("privacy").hidden) privacy(false);
    if (state.error) error(state.error);
    renderState();
    if (
      ["finished", "error"].includes(state.status) &&
      state.last_recap &&
      transitionHandled !== state.last_recap
    ) {
      transitionHandled = state.last_recap;
      await loadRecaps();
      await openRecap(state.last_recap);
    }
  } catch (e) {
    failures++;
    if (failures >= 3) {
      clearFrame();
      connectionError = true;
      error(
        "The app is not responding. Check that the Classroom Mirror launcher is still open.",
      );
    }
  } finally {
    polling = false;
  }
}

async function loadRecaps() {
  recaps = (await api("/api/recaps")).recaps;
}
async function loadHistory() {
  await loadRecaps();
  const list = $("history-list");
  list.replaceChildren();
  $("delete-all").hidden = !recaps.length;
  if (!recaps.length) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.innerHTML =
      '<h2>A fresh start.</h2><p>Your session recaps will appear here after you press Stop.</p><button class="primary">Start a session →</button>';
    empty.querySelector("button").onclick = () => showView("session");
    list.append(empty);
    return;
  }
  for (const r of recaps) {
    const row = document.createElement("article");
    row.className = "history-row";
    const copy = document.createElement("div");
    const tag = document.createElement("span");
    tag.className = "history-type " + (r.source === "demo" ? "demo" : "");
    tag.textContent =
      r.source === "demo" ? "Practice · made-up data" : "Camera session";
    const title = document.createElement("h2");
    title.textContent = date(r.started_at);
    const p = document.createElement("p");
    p.textContent = `${fmt(r.duration_seconds)} · ${capitalize(r.sensitivity)} sensitivity · ${r.raises} hand raises`;
    copy.append(tag, title, p);
    const stats = document.createElement("span");
    stats.className = "recap-label";
    stats.textContent = `${r.peak_people} PEAK IN VIEW`;
    const button = document.createElement("button");
    button.className = "quiet";
    button.textContent = "View recap →";
    button.onclick = () => openRecap(r.id);
    row.append(copy, stats, button);
    list.append(row);
  }
}
async function openRecap(id) {
  const r = recaps.find((x) => x.id === id);
  if (!r) {
    await showView("history");
    return;
  }
  currentRecap = r;
  await showView("recap");
  const panel = $("recap-content");
  panel.replaceChildren();
  const heading = document.createElement("div");
  heading.className = "page-heading compact";
  const title = document.createElement("div");
  const eyebrow = document.createElement("div");
  eyebrow.className = "eyebrow";
  eyebrow.textContent =
    r.source === "demo" ? "PRACTICE RECAP · MADE-UP DATA" : "SESSION COMPLETE";
  const h = document.createElement("h1");
  h.textContent = "A moment to look back.";
  const sub = document.createElement("p");
  sub.textContent = `${date(r.started_at)} · ${fmt(r.duration_seconds)} · ${capitalize(r.sensitivity)} sensitivity`;
  title.append(eyebrow, h, sub);
  heading.append(title);
  panel.append(heading);
  const metrics = document.createElement("div");
  metrics.className = "metrics";
  for (const [label, value, note] of [
    ["Peak in view", r.peak_people, "Most people detected at once"],
    ["Hand raises", r.raises, "Total counted this session"],
    ["Yellow cues", r.yellow_events, "Episodes of continuing movement"],
    ["Red cues", r.red_events, "Episodes of sustained movement"],
  ]) {
    const card = document.createElement("article");
    card.className = "metric";
    const l = document.createElement("span");
    l.textContent = label;
    const v = document.createElement("strong");
    v.textContent = value;
    const n = document.createElement("small");
    n.textContent = note;
    card.append(l, v, n);
    metrics.append(card);
  }
  panel.append(metrics);
  const detail = document.createElement("div");
  detail.className = "recap-panel";
  const dh = document.createElement("h2");
  dh.textContent = "Movement through the session";
  const canvas = document.createElement("canvas");
  canvas.width = 1000;
  canvas.height = 120;
  canvas.className = "recap-chart";
  canvas.setAttribute("aria-label", "Saved room-level movement timeline");
  const p = document.createElement("p");
  p.textContent =
    "These counts describe visible movement and raised hands. Ordinary classroom activity, camera angle, and missed detections can change the numbers. Use your own observation to interpret them.";
  const end = document.createElement("p");
  end.textContent =
    r.end_reason === "timer"
      ? "The session ended when its timer finished."
      : r.end_reason === "dashboard_closed"
        ? "The app stopped after the dashboard disconnected."
        : r.end_reason === "error"
          ? "The session ended early because of a camera or processing error."
          : "The session was stopped using the dashboard.";
  detail.append(dh, canvas, p, end);
  if (r.error) {
    const ep = document.createElement("p");
    ep.textContent = r.error;
    detail.append(ep);
  }
  panel.append(detail);
  drawChart(canvas.getContext("2d"), r.timeline, 1000, 120);
  const actions = document.createElement("div");
  actions.className = "recap-actions";
  for (const [label, fn, cls] of [
    ["New session →", () => showView("session"), "primary"],
    ["Download totals", () => download(r), "quiet"],
    ["Print recap", () => window.print(), "quiet"],
    [
      "Delete recap",
      () =>
        confirmDelete("Delete this recap?", async () => {
          await api(`/api/recaps/${r.id}`, "DELETE");
          await showView("history");
        }),
      "quiet danger",
    ],
  ]) {
    const b = document.createElement("button");
    b.textContent = label;
    b.className = cls;
    b.onclick = fn;
    actions.append(b);
  }
  panel.append(actions);
}
function download(r) {
  const rows = [
    ["measure", "value"],
    ["source", r.source === "demo" ? "practice (synthetic)" : "camera"],
    ["started_at", r.started_at],
    ["duration_seconds", r.duration_seconds],
    ["sensitivity", r.sensitivity],
    ["peak_people_in_view", r.peak_people],
    ["hand_raises", r.raises],
    ["yellow_episodes", r.yellow_events],
    ["red_episodes", r.red_events],
    ["end_reason", r.end_reason],
  ];
  const blob = new Blob(
    [
      rows
        .map((row) =>
          row.map((v) => '"' + String(v).replaceAll('"', '""') + '"').join(","),
        )
        .join("\r\n"),
    ],
    { type: "text/csv;charset=utf-8" },
  );
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `classroom-mirror-${r.source}-${r.id}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function confirmDelete(title, action) {
  deleteAction = action;
  $("confirm-title").textContent = title;
  $("confirm-dialog").showModal();
  $("cancel-delete").focus();
}
$("cancel-delete").onclick = () => $("confirm-dialog").close();
$("confirm-delete").onclick = async () => {
  try {
    $("confirm-delete").disabled = true;
    await deleteAction();
    $("confirm-dialog").close();
  } catch (e) {
    error(e.message);
  } finally {
    $("confirm-delete").disabled = false;
  }
};
$("delete-all").onclick = () =>
  confirmDelete("Delete all saved recaps?", async () => {
    await api("/api/recaps", "DELETE");
    await loadHistory();
  });
$("back-history").onclick = () =>
  showView("history").catch((e) => error(e.message));
chooseSource();
drawRoom();
drawChart(chart, [], 900, 105);
tick();
setInterval(tick, 800);
setInterval(pollPreview, 180);
