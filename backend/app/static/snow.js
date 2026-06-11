/* MARIS Schneefall-Easter-Egg — compositor-only, null Arbeit pro Frame.
 *
 * Design-Prinzip (Ergebnis der Performance-Recherche):
 * - KEIN JavaScript pro Frame (kein requestAnimationFrame im Dauerbetrieb).
 * - KEIN Layout, KEIN Paint pro Frame: Flocken werden EINMAL als nahtlos
 *   kachelnde Textur (Offscreen-Canvas -> Data-URL) gerendert; drei
 *   Parallax-Ebenen sind fixe Divs mit background-repeat.
 * - Animiert wird ausschließlich `transform: translate3d(...)` über
 *   @keyframes mit konkreten Pixelwerten -> läuft komplett auf dem
 *   Compositor-Thread des Browsers (auch ohne GPU nur Layer-Blending).
 * - Nahtlose Schleife: Ebene ist um eine Kachelhöhe größer als der
 *   Viewport und wandert exakt eine Kachelhöhe pro Loop; seitliches
 *   Pendeln (Sinus) ist in die Keyframes eingebacken und endet bei 0.
 * - Adaptive Sonde: Beim Einschalten werden einmalig ~30 Frames gemessen.
 *   Ruckelt es (z. B. schwache VM), wird auf eine ruhige Einzel-Ebene
 *   reduziert. Danach läuft wieder null JS.
 * - `prefers-reduced-motion` stoppt die Animation (statische Flocken).
 * - Versteckte Tabs kosten nichts: Browser pausieren Compositor-Animationen
 *   unsichtbarer Seiten von selbst.
 */
(() => {
  "use strict";

  const STORAGE_KEY = "maris-ui-snow";
  // Schwelle bewusst unter 30-fps-Niveau (33ms): RDP-Sitzungen sind oft auf
  // 30 fps gedeckelt, ohne dass die Maschine überlastet wäre — erst echtes
  // Ruckeln (<25 fps) reduziert auf die Spar-Ebene.
  const PROBE_THRESHOLD_MS = 40;

  // Drei Tiefen-Ebenen: fern (klein, langsam, blass) bis nah (groß, schnell).
  // phase: negative animation-delay, damit die Ebenen nie synchron pendeln.
  // twinkle: sanftes Opacity-Pulsieren (auch compositor-only) für Lebendigkeit.
  const LAYERS = [
    { tile: 256, flakes: 54, minR: 0.6, maxR: 1.3, alpha: 0.4, duration: 36, sway: 18, phase: 0.0, twinkle: 9 },
    { tile: 288, flakes: 34, minR: 1.2, maxR: 2.2, alpha: 0.6, duration: 24, sway: 30, phase: 0.37, twinkle: 7 },
    { tile: 320, flakes: 20, minR: 2.0, maxR: 3.4, alpha: 0.85, duration: 15, sway: 44, phase: 0.71, twinkle: 0 },
  ];
  const LOW_QUALITY_LAYERS = [LAYERS[1]];

  let overlay = null;
  let styleEl = null;
  let probed = false;

  // Einmalige Texturerzeugung: weiche, runde Flocken mit Radial-Verlauf.
  function buildTile({ tile, flakes, minR, maxR, alpha }) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = tile;
    const ctx = canvas.getContext("2d");
    for (let i = 0; i < flakes; i += 1) {
      const x = Math.random() * tile;
      const y = Math.random() * tile;
      const r = minR + Math.random() * (maxR - minR);
      const a = alpha * (0.55 + Math.random() * 0.45);
      const gradient = ctx.createRadialGradient(x, y, 0, x, y, r);
      gradient.addColorStop(0, `rgba(255,255,255,${a.toFixed(3)})`);
      gradient.addColorStop(0.55, `rgba(255,255,255,${(a * 0.8).toFixed(3)})`);
      gradient.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    }
    return canvas.toDataURL("image/png");
  }

  // Keyframes mit festen Pixelwerten (kein var()/calc() -> garantiert
  // compositor-fähig). Sinus-Pendeln, vertikal linear, Start = Ende.
  function keyframesFor(name, tile, sway) {
    const steps = [];
    const segments = 12;
    for (let i = 0; i <= segments; i += 1) {
      const p = i / segments;
      const x = Math.round(Math.sin(p * Math.PI * 2) * sway);
      const y = Math.round(p * tile);
      steps.push(`${((p * 100).toFixed(1))}% { transform: translate3d(${x}px, ${y}px, 0); }`);
    }
    return `@keyframes ${name} { ${steps.join(" ")} }`;
  }

  function enable(layerConfigs) {
    if (overlay) return;
    const configs = layerConfigs || LAYERS;
    overlay = document.createElement("div");
    overlay.className = "snow-overlay";
    overlay.setAttribute("aria-hidden", "true");
    const css = [];
    configs.forEach((cfg, index) => {
      const layer = document.createElement("div");
      layer.className = "snow-layer";
      layer.style.backgroundImage = `url(${buildTile(cfg)})`;
      layer.style.backgroundSize = `${cfg.tile}px ${cfg.tile}px`;
      layer.style.top = `${-cfg.tile}px`;
      layer.style.bottom = `${-cfg.tile}px`;
      layer.style.left = `${-2 * cfg.sway}px`;
      layer.style.right = `${-2 * cfg.sway}px`;
      const animations = [`maris-snow-${index} ${cfg.duration}s linear infinite`];
      if (cfg.twinkle) {
        animations.push(`maris-snow-twinkle ${cfg.twinkle}s ease-in-out infinite alternate`);
      }
      layer.style.animation = animations.join(", ");
      layer.style.animationDelay = `-${(cfg.duration * (cfg.phase || 0)).toFixed(1)}s`;
      css.push(keyframesFor(`maris-snow-${index}`, cfg.tile, cfg.sway));
      overlay.appendChild(layer);
    });
    css.push("@keyframes maris-snow-twinkle { from { opacity: 0.72; } to { opacity: 1; } }");
    styleEl = document.createElement("style");
    styleEl.textContent = css.join("\n");
    document.head.appendChild(styleEl);
    document.body.appendChild(overlay);
  }

  function disable() {
    overlay?.remove();
    styleEl?.remove();
    overlay = null;
    styleEl = null;
  }

  // Einmalige Mess-Sonde direkt nach dem Einschalten: ~30 Frames.
  // Läuft die Maschine am Limit, fällt der Schnee auf eine Ebene zurück.
  function probeAndAdapt() {
    if (probed) return;
    probed = true;
    let frames = 0;
    let start = 0;
    const measure = (timestamp) => {
      if (!overlay) return; // inzwischen ausgeschaltet
      if (frames === 0) start = timestamp;
      frames += 1;
      if (frames < 30) {
        requestAnimationFrame(measure);
        return;
      }
      const avg = (timestamp - start) / (frames - 1);
      if (avg > PROBE_THRESHOLD_MS) {
        disable();
        enable(LOW_QUALITY_LAYERS);
      }
    };
    requestAnimationFrame(measure);
  }

  function init() {
    const btn = document.getElementById("snow-toggle");
    if (!btn) return;

    let on = false;
    try {
      on = window.localStorage.getItem(STORAGE_KEY) === "1";
    } catch (_error) {
      on = false;
    }

    const render = () => {
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.title = on ? "Schneefall ausschalten" : "Schneefall einschalten";
    };

    const sync = () => {
      if (on) {
        enable();
        probeAndAdapt();
      } else {
        disable();
      }
      render();
    };

    btn.addEventListener("click", () => {
      on = !on;
      try {
        window.localStorage.setItem(STORAGE_KEY, on ? "1" : "0");
      } catch (_error) {
        /* localStorage gesperrt — gilt dann nur für diese Seite */
      }
      sync();
    });

    render();
    if (on) sync();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  // Für Tests und Konsole.
  window.MarisSnow = { enable, disable };
})();
