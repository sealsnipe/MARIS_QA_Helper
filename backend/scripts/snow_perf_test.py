#!/usr/bin/env python3
"""End-zu-End-Performancetest für das Schneefall-Easter-Egg.

Misst den CPU-Verbrauch des kompletten Chromium-Prozessbaums (headless,
--disable-gpu => Software-Rendering wie in schwachen VMs), beschränkt per
taskset auf 2 Kerne. Verglichen werden:

  1. baseline  — leere dunkle Seite
  2. snow      — das echte /static/snow.js (compositor-only Kacheltechnik)
  3. naive     — klassischer 200-Flocken-Canvas-Schnee mit requestAnimationFrame
                 (so wurde es "früher" gebaut — die Referenz für hohe CPU-Last)

Aufruf:  python3 scripts/snow_perf_test.py [Messdauer Sekunden, default 10]
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SNOW_JS = ROOT / "app" / "static" / "snow.js"
PORT = 8911

PAGE_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  body {{ margin: 0; min-height: 100vh; background: #0d1117; color: #e6e8ee;
         font: 16px system-ui; }}
  main {{ padding: 3rem; }}
</style></head>
<body><main><h1>Schnee-Performancetest</h1><p>{label}</p></main>{extra}</body></html>
"""

NAIVE_SNIPPET = """
<canvas id="c" style="position:fixed;inset:0;pointer-events:none"></canvas>
<script>
  // Klassische Implementierung: 200 Flocken, Canvas-Redraw pro Frame.
  const canvas = document.getElementById("c");
  const ctx = canvas.getContext("2d");
  function resize() { canvas.width = innerWidth; canvas.height = innerHeight; }
  resize(); addEventListener("resize", resize);
  const flakes = Array.from({ length: 200 }, () => ({
    x: Math.random() * innerWidth, y: Math.random() * innerHeight,
    r: 1 + Math.random() * 2.5, s: 0.5 + Math.random() * 1.5, p: Math.random() * 6.28,
  }));
  function tick(t) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "rgba(255,255,255,0.8)";
    for (const f of flakes) {
      f.y += f.s; f.x += Math.sin(t / 900 + f.p) * 0.4;
      if (f.y > canvas.height) { f.y = -4; f.x = Math.random() * canvas.width; }
      ctx.beginPath(); ctx.arc(f.x, f.y, f.r, 0, 6.28); ctx.fill();
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
</script>
"""

SNOW_SNIPPET = """
<script src="/snow.js"></script>
<script>window.MarisSnow.enable();</script>
"""


def build_pages(directory: Path) -> None:
    shutil.copyfile(SNOW_JS, directory / "snow.js")
    (directory / "baseline.html").write_text(PAGE_TEMPLATE.format(label="Baseline ohne Schnee", extra=""))
    (directory / "snow.html").write_text(PAGE_TEMPLATE.format(label="Compositor-Schnee (snow.js)", extra=SNOW_SNIPPET))
    (directory / "naive.html").write_text(PAGE_TEMPLATE.format(label="Naiver Canvas-Schnee", extra=NAIVE_SNIPPET))


def proc_tree_cpu_seconds(root_pid: int) -> float:
    """Summe utime+stime (Sekunden) über den gesamten Prozessbaum unter root_pid."""
    hertz = 100.0
    children: dict[int, list[int]] = {}
    stats: dict[int, float] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "stat").read_text()
        except OSError:
            continue
        # Feld 2 (comm) kann Leerzeichen/Klammern enthalten -> hinter ')' parsen
        after = raw.rsplit(")", 1)[1].split()
        pid = int(entry.name)
        ppid = int(after[1])
        utime = float(after[11])
        stime = float(after[12])
        children.setdefault(ppid, []).append(pid)
        stats[pid] = (utime + stime) / hertz

    total = 0.0
    stack = [root_pid]
    seen = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        total += stats.get(pid, 0.0)
        stack.extend(children.get(pid, []))
    return total


def make_taskset_wrapper(directory: Path, real_executable: str) -> Path:
    wrapper = directory / "chrome-2cores.sh"
    wrapper.write_text(
        "#!/bin/sh\n"
        'export LD_LIBRARY_PATH="/tmp/chrome-libs/extracted/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"\n'
        f'exec taskset -c 0,1 "{real_executable}" "$@"\n'
    )
    wrapper.chmod(0o755)
    return wrapper


def find_browser_pid(marker: str) -> int:
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().decode(errors="replace")
        except OSError:
            continue
        if marker in cmdline and "--type=" not in cmdline:
            return int(entry.name)
    raise RuntimeError(f"Browser-Prozess mit Marker {marker} nicht gefunden")


def measure(browser_type, wrapper: Path, url: str, seconds: float, marker: str, screencast: bool = False):
    browser = browser_type.launch(
        executable_path=str(wrapper),
        args=[
            "--disable-gpu",
            "--window-size=1600,900",
            "--force-device-scale-factor=1",
            f"--snow-perf-marker={marker}",
        ],
    )
    try:
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        frames = {"count": 0}
        cdp = None
        if screencast:
            # Zwingt den Compositor, jeden Frame wirklich zu produzieren —
            # Worst-Case-Szenario und zugleich FPS-Nachweis, dass animiert wird.
            cdp = page.context.new_cdp_session(page)

            def on_frame(params):
                frames["count"] += 1
                try:
                    cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
                except Exception:
                    pass  # Browser bereits geschlossen

            cdp.on("Page.screencastFrame", on_frame)
        page.goto(url)
        if screencast:
            cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 40, "everyNthFrame": 1})
        page.wait_for_timeout(2500)  # Warmup: Texturen, Layer-Promotion, Sonde
        frames["count"] = 0
        pid = find_browser_pid(marker)
        before = proc_tree_cpu_seconds(pid)
        t0 = time.monotonic()
        if screencast == "screenshots":
            # Compositing aktiv erzwingen: jeder Screenshot zwingt den Compositor,
            # einen frischen Frame zu erzeugen (inkl. Blending aller Schnee-Ebenen).
            deadline = t0 + seconds
            while time.monotonic() < deadline:
                page.screenshot(type="jpeg", quality=40)
                frames["count"] += 1
        else:
            page.wait_for_timeout(seconds * 1000)
        elapsed = time.monotonic() - t0
        after = proc_tree_cpu_seconds(pid)
        cores = (after - before) / elapsed  # durchschnittlich genutzte Kerne
        fps = frames["count"] / elapsed
        return cores, fps
    finally:
        browser.close()


def main() -> None:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    tmp = Path(tempfile.mkdtemp(prefix="snow-perf-"))
    build_pages(tmp)

    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp))
    server = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    results: dict[str, dict[str, float]] = {}
    with sync_playwright() as p:
        wrapper = make_taskset_wrapper(tmp, p.chromium.executable_path)
        for mode_label, use_screencast in (
            ("idle-compositing", False),
            ("forced-rendering", True),
            ("screenshot-loop", "screenshots"),
        ):
            print(f"\n--- Modus: {mode_label} ---")
            for name in ("baseline", "snow", "naive"):
                url = f"http://127.0.0.1:{PORT}/{name}.html"
                cores, fps = measure(
                    p.chromium, wrapper, url, seconds, marker=f"perf-{name}-{mode_label}", screencast=use_screencast
                )
                results[f"{name}/{mode_label}"] = {"cores": cores, "fps": fps}
                fps_note = f"  {fps:5.1f} fps" if use_screencast else ""
                print(f"{name:9s}  {cores:6.3f} Kerne  ({cores * 100:6.1f}% eines Kerns){fps_note}")

    server.shutdown()
    print()
    for mode_label in ("idle-compositing", "forced-rendering", "screenshot-loop"):
        base = results[f"baseline/{mode_label}"]["cores"]
        snow_cost = results[f"snow/{mode_label}"]["cores"] - base
        naive_cost = results[f"naive/{mode_label}"]["cores"] - base
        factor = f"{naive_cost / snow_cost:.1f}x" if snow_cost > 0.005 else "n/a (Schnee im Messrauschen)"
        print(
            f"{mode_label}: Schnee +{snow_cost * 100:.1f}% | naiv +{naive_cost * 100:.1f}% "
            f"| Faktor {factor}"
        )


if __name__ == "__main__":
    main()
