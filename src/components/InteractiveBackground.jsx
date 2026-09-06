import { useEffect, useRef } from "react";

/* =========================================================
   COLOR PALETTE — "ROYAL" PINK/MAGENTA
========================================================= */

const MAGENTA = "255, 0, 150";
const MAGENTA_DEEP = "185, 0, 125";
const ROYAL_PURPLE = "120, 0, 150";
const ROSE_HIGHLIGHT = "255, 130, 205";

function InteractiveBackground() {
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: 0, y: 0 }); // raw target from cursor
  const smoothRef = useRef({ x: 0, y: 0 }); // eased value actually used for drawing

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    let animationFrame;

    let farLayer = [];
    let midLayer = [];
    let nearLayer = [];
    let spireX = 0;
    let cliffPoints = [];

    function buildCityLayers() {
      const width = window.innerWidth;

      farLayer = [];
      midLayer = [];
      nearLayer = [];

      for (let x = 0; x < width + 26; x += 13) {
        farLayer.push({ x, height: Math.random() * 55 + 15, seed: Math.random() });
      }
      for (let x = 0; x < width + 34; x += 17) {
        midLayer.push({ x, height: Math.random() * 85 + 25, seed: Math.random() });
      }
      for (let x = 0; x < width + 44; x += 22) {
        nearLayer.push({ x, height: Math.random() * 120 + 30, seed: Math.random() });
      }

      spireX = width * (0.62 + Math.random() * 0.08);

      cliffPoints = [];
      const segments = 14;
      for (let i = 0; i <= segments; i++) {
        cliffPoints.push({
          xFrac: i / segments,
          peak: Math.random() * 0.55 + 0.25,
        });
      }
    }

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      buildCityLayers();
    };

    const handleMouseMove = (event) => {
      mouseRef.current.x = (event.clientX / window.innerWidth - 0.5) * 2;
      mouseRef.current.y = (event.clientY / window.innerHeight - 0.5) * 2;
    };

    const handleMouseLeave = () => {
      // drift back to center instead of freezing at the last position
      mouseRef.current.x = 0;
      mouseRef.current.y = 0;
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseleave", handleMouseLeave);

    // =========================================================
    // PARTICLES (rising ambient dust / stars)
    // =========================================================

    const particles = [];
    for (let i = 0; i < 160; i++) {
      particles.push({
        x: Math.random(),
        y: Math.random(),
        size: Math.random() * 2 + 0.4,
        speed: Math.random() * 0.00025 + 0.00005,
        alpha: Math.random() * 0.7 + 0.2,
        pulse: Math.random() * Math.PI * 2,
      });
    }

    // =========================================================
    // FLOATING PETALS (denser + wider size range)
    // =========================================================

    const petals = [];
    for (let i = 0; i < 46; i++) {
      petals.push({
        x: Math.random(),
        y: Math.random(),
        size: Math.random() * 8 + 3,
        speed: Math.random() * 0.0006 + 0.00012,
        drift: Math.random() * 0.0012 - 0.0006,
        rotation: Math.random() * Math.PI,
        rotationSpeed: Math.random() * 0.02 - 0.01,
        depth: Math.random() * 0.6 + 0.4, // parallax weight: closer petals drift more with mouse
      });
    }

    // =========================================================
    // NETWORK CONSTELLATION (upper sky)
    // =========================================================

    const nodes = [];
    for (let i = 0; i < 70; i++) {
      nodes.push({
        x: Math.random(),
        y: Math.random() * 0.55,
        radius: Math.random() * 1.4 + 0.5,
      });
    }

    // =========================================================
    // SHOOTING STARS / COMET STREAKS
    // =========================================================

    const comets = [];
    let nextCometAt = performance.now() + 2000 + Math.random() * 4000;

    function spawnComet(width, height) {
      const fromLeft = Math.random() > 0.5;
      const startX = fromLeft ? Math.random() * width * 0.3 : width - Math.random() * width * 0.3;
      const startY = Math.random() * height * 0.35;
      const angle = fromLeft ? Math.PI * 0.15 : Math.PI * 0.85;
      const speed = 6 + Math.random() * 5;

      comets.push({
        x: startX,
        y: startY,
        vx: Math.cos(angle) * speed * (fromLeft ? 1 : -1),
        vy: Math.sin(angle) * speed,
        life: 1,
        length: 90 + Math.random() * 70,
      });
    }

    const drawComets = (time) => {
      const width = canvas.width;
      const height = canvas.height;

      if (time > nextCometAt) {
        spawnComet(width, height);
        nextCometAt = time + 3500 + Math.random() * 5500;
      }

      for (let i = comets.length - 1; i >= 0; i--) {
        const comet = comets[i];
        comet.x += comet.vx;
        comet.y += comet.vy;
        comet.life -= 0.012;

        if (comet.life <= 0) {
          comets.splice(i, 1);
          continue;
        }

        const dirLen = Math.hypot(comet.vx, comet.vy) || 1;
        const tailX = comet.x - (comet.vx / dirLen) * comet.length;
        const tailY = comet.y - (comet.vy / dirLen) * comet.length;

        const gradient = ctx.createLinearGradient(comet.x, comet.y, tailX, tailY);
        gradient.addColorStop(0, `rgba(${ROSE_HIGHLIGHT}, ${0.9 * comet.life})`);
        gradient.addColorStop(1, "rgba(255, 130, 205, 0)");

        ctx.save();
        ctx.strokeStyle = gradient;
        ctx.lineWidth = 1.4;
        ctx.lineCap = "round";
        ctx.shadowBlur = 10;
        ctx.shadowColor = `rgba(${MAGENTA}, ${0.6 * comet.life})`;
        ctx.beginPath();
        ctx.moveTo(comet.x, comet.y);
        ctx.lineTo(tailX, tailY);
        ctx.stroke();
        ctx.restore();

        ctx.beginPath();
        ctx.arc(comet.x, comet.y, 1.6, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${comet.life})`;
        ctx.fill();
      }
    };

    // =========================================================
    // CORNER CHERRY BLOSSOM BRANCHES (denser, layered)
    // =========================================================

    function buildBranch(dirX, dirY, seed, reach) {
      const segments = [];
      let x = 0;
      let y = 0;
      let angle = Math.atan2(dirY, dirX);
      const segmentCount = 6 + (seed % 3);

      for (let i = 0; i < segmentCount; i++) {
        const length = reach * (0.55 + ((seed * (i + 1)) % 40) / 60);
        const wobble = Math.sin(seed + i * 1.7) * 0.4;

        const nextX = x + Math.cos(angle + wobble) * length;
        const nextY = y + Math.sin(angle + wobble) * length;

        segments.push({
          x1: x,
          y1: y,
          x2: nextX,
          y2: nextY,
          width: Math.max(1, 3.4 - i * 0.5),
        });

        const blossomCount = i > 0 ? 4 + (seed % 3) : 2;
        for (let b = 0; b < blossomCount; b++) {
          const t = (b + 1) / (blossomCount + 1);
          segments.push({
            blossom: true,
            x: x + (nextX - x) * t + Math.cos(seed + b * 2) * 12,
            y: y + (nextY - y) * t + Math.sin(seed + b * 2) * 12,
            size: 3 + ((seed + b * 7) % 6),
            deep: b % 2 === 0,
          });
        }

        x = nextX;
        y = nextY;
        angle += wobble * 0.4;
      }

      return segments;
    }

    function remap(segments, corner) {
      const flipX = corner === "tr" || corner === "br";
      const flipY = corner === "bl" || corner === "br";

      return segments.map((segment) => {
        const mapped = { ...segment, corner };
        if (segment.blossom) {
          mapped.x = flipX ? -segment.x : segment.x;
          mapped.y = flipY ? -segment.y : segment.y;
        } else {
          mapped.x1 = flipX ? -segment.x1 : segment.x1;
          mapped.y1 = flipY ? -segment.y1 : segment.y1;
          mapped.x2 = flipX ? -segment.x2 : segment.x2;
          mapped.y2 = flipY ? -segment.y2 : segment.y2;
        }
        return mapped;
      });
    }

    // extra branch per corner vs. the original for a lusher, curtain-like cluster
    const branches = [
      ...remap(buildBranch(1, 0.55, 11, 150), "tl"),
      ...remap(buildBranch(0.85, 0.25, 27, 115), "tl"),
      ...remap(buildBranch(0.95, 0.75, 19, 90), "tl"),
      ...remap(buildBranch(-1, 0.55, 41, 150), "tr"),
      ...remap(buildBranch(-0.85, 0.25, 59, 115), "tr"),
      ...remap(buildBranch(-0.95, 0.75, 47, 90), "tr"),
      ...remap(buildBranch(1, -0.45, 73, 125), "bl"),
      ...remap(buildBranch(0.8, -0.2, 83, 95), "bl"),
      ...remap(buildBranch(-1, -0.45, 97, 125), "br"),
      ...remap(buildBranch(-0.8, -0.2, 61, 95), "br"),
    ];

    function cornerOrigin(corner, width, height) {
      switch (corner) {
        case "tr":
          return [width, 0];
        case "bl":
          return [0, height];
        case "br":
          return [width, height];
        default:
          return [0, 0];
      }
    }

    const drawBranches = (time, parallaxX, parallaxY) => {
      const width = canvas.width;
      const height = canvas.height;
      const sway = Math.sin(time * 0.0003) * 4;

      branches.forEach((segment) => {
        const [originX, originY] = cornerOrigin(segment.corner, width, height);

        ctx.save();
        ctx.translate(
          originX + parallaxX * 3,
          originY + sway * 0.2 + parallaxY * 2
        );

        if (segment.blossom) {
          ctx.beginPath();
          ctx.arc(segment.x, segment.y + sway, segment.size, 0, Math.PI * 2);
          ctx.fillStyle = segment.deep
            ? `rgba(${MAGENTA_DEEP}, 0.6)`
            : `rgba(${ROSE_HIGHLIGHT}, 0.6)`;
          ctx.shadowBlur = 11;
          ctx.shadowColor = `rgba(${MAGENTA}, 0.7)`;
          ctx.fill();
          ctx.shadowBlur = 0;
        } else {
          ctx.beginPath();
          ctx.moveTo(segment.x1, segment.y1 + sway);
          ctx.lineTo(segment.x2, segment.y2 + sway);
          ctx.strokeStyle = "rgba(70, 15, 45, 0.75)";
          ctx.lineWidth = segment.width;
          ctx.lineCap = "round";
          ctx.stroke();
        }

        ctx.restore();
      });
    };

    // =========================================================
    // GLOBE
    // =========================================================

    const drawGlobe = (time, parallaxX, parallaxY) => {
      const width = canvas.width;
      const height = canvas.height;

      const cx = width * 0.5 + parallaxX * 14;
      const cy = height * 0.36 + parallaxY * 8;
      const radius = Math.min(width, height) * 0.42;

      ctx.save();

      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${MAGENTA}, 0.09)`;
      ctx.lineWidth = 5;
      ctx.shadowBlur = 38;
      ctx.shadowColor = `rgba(${ROYAL_PURPLE}, 0.5)`;
      ctx.stroke();
      ctx.shadowBlur = 0;

      for (let i = -4; i <= 4; i++) {
        const y = cy + (i / 5) * radius;
        const widthFactor = Math.sqrt(Math.max(0, 1 - Math.pow((y - cy) / radius, 2)));

        ctx.beginPath();
        ctx.ellipse(cx, y, radius * widthFactor, radius * 0.18, 0, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${MAGENTA}, 0.13)`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      for (let i = -6; i <= 6; i++) {
        const rotation = (i / 6) * Math.PI + time * 0.00004;

        ctx.beginPath();
        ctx.ellipse(cx, cy, Math.abs(radius * Math.cos(rotation)), radius, 0, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${MAGENTA}, 0.13)`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      for (let i = 0; i < 5; i++) {
        const offset = time * 0.00015 + i;

        ctx.beginPath();
        ctx.arc(cx, cy, radius * (0.65 + i * 0.05), offset, offset + Math.PI * 0.8);
        ctx.strokeStyle = `rgba(${ROSE_HIGHLIGHT}, 0.15)`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      const nodeCount = 28;
      for (let i = 0; i < nodeCount; i++) {
        const angle = (i / nodeCount) * Math.PI * 2 + time * 0.00012;
        const depth = Math.sin(angle * 2.3 + i);

        const nx = cx + Math.cos(angle) * radius * (0.4 + Math.abs(depth) * 0.5);
        const ny = cy + Math.sin(angle) * radius * 0.7;

        ctx.beginPath();
        ctx.arc(nx, ny, depth > 0 ? 2 : 1.1, 0, Math.PI * 2);
        ctx.fillStyle = depth > 0 ? `rgba(${MAGENTA}, 0.85)` : `rgba(${MAGENTA}, 0.3)`;
        ctx.fill();
      }

      ctx.restore();
    };

    // =========================================================
    // CITY LAYERS
    // =========================================================

    const drawCityLayer = (buildings, horizon, opacity, windowAlpha, tint) => {
      buildings.forEach((building) => {
        const y = horizon - building.height;

        ctx.fillStyle = `rgba(${tint}, ${opacity})`;
        ctx.fillRect(building.x, y, 11, building.height);

        for (let wy = y + 8; wy < horizon - 4; wy += 11) {
          if (Math.sin(building.seed * 999 + wy) > 0.4) {
            ctx.fillStyle = `rgba(${MAGENTA}, ${windowAlpha})`;
            ctx.fillRect(building.x + 3, wy, 2, 2);
          }
        }
      });
    };

    const drawSpireTower = (horizon, parallaxX) => {
      const baseX = spireX + parallaxX * 4;
      const towerHeight = 210;
      const baseWidth = 10;

      ctx.save();

      ctx.beginPath();
      ctx.moveTo(baseX - baseWidth, horizon);
      ctx.lineTo(baseX - baseWidth * 0.35, horizon - towerHeight * 0.55);
      ctx.lineTo(baseX - 2, horizon - towerHeight * 0.9);
      ctx.lineTo(baseX, horizon - towerHeight);
      ctx.lineTo(baseX + 2, horizon - towerHeight * 0.9);
      ctx.lineTo(baseX + baseWidth * 0.35, horizon - towerHeight * 0.55);
      ctx.lineTo(baseX + baseWidth, horizon);
      ctx.closePath();

      ctx.fillStyle = "rgba(6, 2, 8, 0.98)";
      ctx.fill();

      ctx.beginPath();
      ctx.arc(baseX, horizon - towerHeight - 2, 2.4, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${MAGENTA}, 0.9)`;
      ctx.shadowBlur = 16;
      ctx.shadowColor = `rgba(${MAGENTA}, 0.9)`;
      ctx.fill();
      ctx.shadowBlur = 0;

      for (let i = 1; i < 5; i++) {
        const ringY = horizon - (towerHeight / 5) * i;
        ctx.beginPath();
        ctx.arc(baseX, ringY, 1.4, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${ROSE_HIGHLIGHT}, 0.7)`;
        ctx.shadowBlur = 6;
        ctx.shadowColor = `rgba(${MAGENTA}, 0.6)`;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      ctx.restore();
    };

    const drawCity = (parallaxX) => {
      const width = canvas.width;
      const height = canvas.height;
      const horizon = height * 0.74;

      ctx.save();

      const glow = ctx.createRadialGradient(
        width * 0.5,
        horizon,
        10,
        width * 0.5,
        horizon,
        width * 0.62
      );
      glow.addColorStop(0, `rgba(${MAGENTA}, 0.34)`);
      glow.addColorStop(0.45, `rgba(${ROYAL_PURPLE}, 0.16)`);
      glow.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(0, horizon - 140, width, 300);

      ctx.save();
      ctx.translate(parallaxX * 2, 0);
      ctx.globalAlpha = 0.55;
      drawCityLayer(farLayer, horizon - 6, 0.85, 0.28, "20, 8, 22");
      ctx.restore();

      ctx.save();
      ctx.translate(parallaxX * 4, 0);
      drawCityLayer(midLayer, horizon - 2, 0.92, 0.42, "13, 4, 15");
      ctx.restore();

      ctx.save();
      ctx.translate(parallaxX * 5, 0);
      drawSpireTower(horizon, parallaxX);
      ctx.restore();

      ctx.save();
      ctx.translate(parallaxX * 7, 0);
      drawCityLayer(nearLayer, horizon, 0.97, 0.6, "8, 2, 10");
      ctx.restore();

      ctx.beginPath();
      ctx.moveTo(0, horizon);
      ctx.lineTo(width, horizon);
      ctx.strokeStyle = `rgba(${MAGENTA}, 0.32)`;
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.restore();
    };

    // =========================================================
    // GLOWING RIVER-ROADS THROUGH THE CITY
    // =========================================================

    const roads = [];
    {
      const roadCount = 5;
      for (let i = 0; i < roadCount; i++) {
        roads.push({
          seed: i * 137.5,
          startFrac: 0.22 + (i / roadCount) * 0.56,
          amplitude: 45 + (i % 3) * 20,
          width: i === Math.floor(roadCount / 2) ? 4.5 : 2.4,
        });
      }
    }

    const drawRoads = (time) => {
      const width = canvas.width;
      const height = canvas.height;
      const horizon = height * 0.74;
      const bottom = height;

      ctx.save();
      ctx.globalCompositeOperation = "lighter";

      roads.forEach((road) => {
        const startX = width * road.startFrac;
        const endX = width * 0.5 + Math.sin(road.seed) * width * 0.1;

        const cp1x = startX + Math.sin(time * 0.00018 + road.seed) * road.amplitude;
        const cp1y = bottom - (bottom - horizon) * 0.4;
        const cp2x = endX + Math.cos(time * 0.00013 + road.seed) * road.amplitude * 0.5;
        const cp2y = horizon + (bottom - horizon) * 0.15;

        ctx.beginPath();
        ctx.moveTo(startX, bottom);
        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, endX, horizon - 6);

        const gradient = ctx.createLinearGradient(startX, bottom, endX, horizon);
        gradient.addColorStop(0, `rgba(${MAGENTA}, 0.7)`);
        gradient.addColorStop(0.55, `rgba(${MAGENTA_DEEP}, 0.4)`);
        gradient.addColorStop(1, `rgba(${ROYAL_PURPLE}, 0.0)`);

        ctx.strokeStyle = gradient;
        ctx.lineWidth = road.width;
        ctx.shadowBlur = 18;
        ctx.shadowColor = `rgba(${MAGENTA}, 0.65)`;
        ctx.stroke();
      });

      ctx.shadowBlur = 0;
      ctx.restore();
    };

    // =========================================================
    // FOREGROUND CLIFF SILHOUETTE
    // =========================================================

    const drawCliffs = (parallaxX) => {
      const width = canvas.width;
      const height = canvas.height;
      const baseY = height;
      const bandHeight = height * 0.16;

      ctx.save();
      ctx.translate(parallaxX * 9, 0);

      ctx.beginPath();
      ctx.moveTo(0, baseY);

      cliffPoints.forEach((point) => {
        const x = point.xFrac * width;
        const y = baseY - bandHeight * point.peak;
        ctx.lineTo(x, y);
      });

      ctx.lineTo(width, baseY);
      ctx.closePath();

      ctx.fillStyle = "rgba(3, 1, 4, 0.98)";
      ctx.fill();

      ctx.beginPath();
      cliffPoints.forEach((point, i) => {
        const x = point.xFrac * width;
        const y = baseY - bandHeight * point.peak;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = `rgba(${MAGENTA}, 0.35)`;
      ctx.lineWidth = 1.4;
      ctx.shadowBlur = 12;
      ctx.shadowColor = `rgba(${MAGENTA}, 0.5)`;
      ctx.stroke();
      ctx.shadowBlur = 0;

      ctx.restore();
    };

    // =========================================================
    // PARTICLES / NETWORK / PETALS
    // =========================================================

    const drawParticles = () => {
      const width = canvas.width;
      const height = canvas.height;

      particles.forEach((particle) => {
        particle.y -= particle.speed;
        if (particle.y < 0) {
          particle.y = 1;
          particle.x = Math.random();
        }

        const pulse = Math.sin(particle.pulse + performance.now() * 0.001);
        const alpha = particle.alpha + pulse * 0.15;

        ctx.beginPath();
        ctx.arc(particle.x * width, particle.y * height, particle.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${MAGENTA}, ${Math.max(0.1, alpha)})`;
        ctx.shadowBlur = 8;
        ctx.shadowColor = `rgba(${ROYAL_PURPLE}, 0.8)`;
        ctx.fill();
        ctx.shadowBlur = 0;
      });
    };

    const drawNetwork = () => {
      const width = canvas.width;
      const height = canvas.height;

      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const other = nodes[j];
          const dx = node.x - other.x;
          const dy = node.y - other.y;
          const distance = Math.sqrt(dx * dx + dy * dy);

          if (distance < 0.13) {
            ctx.beginPath();
            ctx.moveTo(node.x * width, node.y * height);
            ctx.lineTo(other.x * width, other.y * height);
            ctx.strokeStyle = `rgba(${MAGENTA}, ${0.12 * (1 - distance / 0.13)})`;
            ctx.lineWidth = 0.7;
            ctx.stroke();
          }
        }
      }

      nodes.forEach((node) => {
        ctx.beginPath();
        ctx.arc(node.x * width, node.y * height, node.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${MAGENTA}, 0.7)`;
        ctx.shadowBlur = 8;
        ctx.shadowColor = `rgba(${ROYAL_PURPLE}, 0.8)`;
        ctx.fill();
        ctx.shadowBlur = 0;
      });
    };

    const drawPetals = (parallaxX, parallaxY) => {
      const width = canvas.width;
      const height = canvas.height;

      petals.forEach((petal) => {
        petal.y += petal.speed;
        petal.x += petal.drift;
        petal.rotation += petal.rotationSpeed;

        if (petal.y > 1.05) {
          petal.y = -0.05;
          petal.x = Math.random();
        }
        if (petal.x > 1.05) petal.x = -0.05;
        if (petal.x < -0.05) petal.x = 1.05;

        const x = petal.x * width + parallaxX * 18 * petal.depth;
        const y = petal.y * height + parallaxY * 10 * petal.depth;

        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(petal.rotation);

        ctx.beginPath();
        ctx.moveTo(0, -petal.size);
        ctx.bezierCurveTo(petal.size, -petal.size * 0.5, petal.size, petal.size, 0, petal.size);
        ctx.bezierCurveTo(-petal.size, petal.size * 0.5, -petal.size, -petal.size * 0.5, 0, -petal.size);

        ctx.fillStyle = `rgba(${MAGENTA}, 0.55)`;
        ctx.shadowBlur = 12;
        ctx.shadowColor = `rgba(${ROYAL_PURPLE}, 0.8)`;
        ctx.fill();

        ctx.restore();
      });
    };

    // =========================================================
    // MAIN LOOP
    // =========================================================

    const animate = (time) => {
      const width = canvas.width;
      const height = canvas.height;

      // ease the parallax toward the real cursor position instead of snapping
      smoothRef.current.x += (mouseRef.current.x - smoothRef.current.x) * 0.06;
      smoothRef.current.y += (mouseRef.current.y - smoothRef.current.y) * 0.06;

      const parallaxX = smoothRef.current.x;
      const parallaxY = smoothRef.current.y;

      const background = ctx.createLinearGradient(0, 0, 0, height);
      background.addColorStop(0, "#04020a");
      background.addColorStop(0.45, "#0d0512");
      background.addColorStop(0.72, "#170819");
      background.addColorStop(1, "#020103");
      ctx.fillStyle = background;
      ctx.fillRect(0, 0, width, height);

      const atmosphere = ctx.createRadialGradient(
        width * 0.5,
        height * 0.42,
        30,
        width * 0.5,
        height * 0.42,
        height * 0.68
      );
      atmosphere.addColorStop(0, `rgba(${MAGENTA_DEEP}, 0.2)`);
      atmosphere.addColorStop(0.4, `rgba(${ROYAL_PURPLE}, 0.14)`);
      atmosphere.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = atmosphere;
      ctx.fillRect(0, 0, width, height);

      drawGlobe(time, parallaxX, parallaxY);
      drawNetwork();
      drawComets(time);
      drawParticles();
      drawCity(parallaxX);
      drawRoads(time);
      drawCliffs(parallaxX);
      drawBranches(time, parallaxX, parallaxY);
      drawPetals(parallaxX, parallaxY);

      animationFrame = requestAnimationFrame(animate);
    };

    resize();
    window.addEventListener("resize", resize);

    animationFrame = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, []);

  return (
    <>
      <canvas ref={canvasRef} className="interactive-background" />
      <div className="background-vignette" />
      <div className="background-noise" />
    </>
  );
}

export default InteractiveBackground;
