import { useRef, useEffect } from 'react';

interface Cell {
  brightness: number; // 0 = default grey, 1 = full green
}

export default function TerrainCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const parent = canvas.parentElement;
    if (!parent) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const cellSize = 14;
    const gap = 7;
    const step = cellSize + gap;

    // Colors
    const bgR = 10, bgG = 10, bgB = 10;       // #0a0a0a
    const defaultR = 30, defaultG = 30, defaultB = 30; // slightly lighter grey
    const greenR = 1, greenG = 255, greenB = 94;       // #01ff5e

    const fadeSpeed = 0.4; // how fast cells fade back per second
    const flashChance = 0.00005; // probability per cell per frame to flash

    let cols = 0;
    let rows = 0;
    let cells: Cell[] = [];

    function initGrid() {
      const w = parent!.clientWidth;
      const h = parent!.clientHeight;
      const dpr = Math.min(window.devicePixelRatio, 2);
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);

      cols = Math.ceil(w / step) + 1;
      rows = Math.ceil(h / step) + 1;

      const newCells: Cell[] = new Array(cols * rows);
      for (let i = 0; i < newCells.length; i++) {
        newCells[i] = { brightness: 0 };
      }
      // Preserve existing brightness values where possible
      if (cells.length > 0) {
        const oldCols = cols;
        for (let i = 0; i < Math.min(cells.length, newCells.length); i++) {
          newCells[i].brightness = cells[i].brightness;
        }
      }
      cells = newCells;
    }

    function lerpColor(
      r1: number, g1: number, b1: number,
      r2: number, g2: number, b2: number,
      t: number
    ): string {
      const r = Math.round(r1 + (r2 - r1) * t);
      const g = Math.round(g1 + (g2 - g1) * t);
      const b = Math.round(b1 + (b2 - b1) * t);
      return `rgb(${r},${g},${b})`;
    }

    let animId: number;
    let lastTime = performance.now();

    function animate() {
      animId = requestAnimationFrame(animate);
      const now = performance.now();
      const dt = Math.min((now - lastTime) / 1000, 0.05);
      lastTime = now;

      // Update cells
      for (let i = 0; i < cells.length; i++) {
        const cell = cells[i];

        // Random chance to flash green
        if (cell.brightness < 0.1 && Math.random() < flashChance) {
          cell.brightness = 0.7 + Math.random() * 0.3; // flash to 0.7–1.0
        }

        // Fade back toward 0
        if (cell.brightness > 0) {
          cell.brightness = Math.max(0, cell.brightness - fadeSpeed * dt);
        }
      }

      // Draw
      const w = canvas.width / (Math.min(window.devicePixelRatio, 2));
      const h = canvas.height / (Math.min(window.devicePixelRatio, 2));

      ctx!.fillStyle = `rgb(${bgR},${bgG},${bgB})`;
      ctx!.fillRect(0, 0, w, h);

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const cell = cells[r * cols + c];
          const x = c * step;
          const y = r * step;

          if (cell.brightness > 0.01) {
            ctx!.fillStyle = lerpColor(
              defaultR, defaultG, defaultB,
              greenR, greenG, greenB,
              cell.brightness
            );
          } else {
            ctx!.fillStyle = `rgb(${defaultR},${defaultG},${defaultB})`;
          }

          ctx!.fillRect(x, y, cellSize, cellSize);
        }
      }
    }

    initGrid();
    animate();

    const observer = new ResizeObserver(initGrid);
    observer.observe(parent);

    return () => {
      cancelAnimationFrame(animId);
      observer.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '100%', display: 'block' }}
    />
  );
}
