import { useEffect, useRef } from "react";
import "./InteractiveBackground.css";

/* =========================================================
   COLOR PALETTE — restrained slate + single blue accent
========================================================= */

const ACCENT = "91, 141, 239";
const ACCENT_DIM = "60, 90, 150";

function InteractiveBackground() {
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: 0, y: 0 }); // raw target from cursor
  const smoothRef = useRef({ x: 0, y: 0 }); // eased value actually used for drawing

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    let animationFrame;

    const handleMouseMove = (event) => {
      mouseRef.current.x = (event.clientX / window.innerWidth - 0.5) * 2;
      mouseRef.current.y = (event.clientY / window.innerHeight - 0.5) * 2;
    };

    const handleMouseLeave = () => {
      mouseRef.current.x = 0;
      mouseRef.current.y = 0;
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseleave", handleMouseLeave);

    // =========================================================
    // NETWORK NODES (a quiet, slowly drifting constellation)
    // =========================================================

    const nodes = [];

    const buildNodes = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const count = Math.round((width * height) / 42000);

      nodes.length = 0;
      for (let i = 0; i < count; i++) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.08,
          vy: (Math.random() - 0.5) * 0.08,
          radius: Math.random() * 1.1 + 0.6,
        });
      }
    };

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      buildNodes();
    };

    const LINK_DISTANCE = 140;

    const drawNodes = (parallaxX, parallaxY) => {
      const width = canvas.width;
      const height = canvas.height;

      nodes.forEach((node) => {
        node.x += node.vx;
        node.y += node.vy;

        if (node.x < 0 || node.x > width) node.vx *= -1;
        if (node.y < 0 || node.y > height) node.vy *= -1;
        node.x = Math.min(Math.max(node.x, 0), width);
        node.y = Math.min(Math.max(node.y, 0), height);
      });

      const offsetX = parallaxX * 6;
      const offsetY = parallaxY * 4;

      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const distance = Math.hypot(dx, dy);

          if (distance < LINK_DISTANCE) {
            ctx.beginPath();
            ctx.moveTo(a.x + offsetX, a.y + offsetY);
            ctx.lineTo(b.x + offsetX, b.y + offsetY);
            ctx.strokeStyle = `rgba(${ACCENT_DIM}, ${0.12 * (1 - distance / LINK_DISTANCE)})`;
            ctx.lineWidth = 0.6;
            ctx.stroke();
          }
        }
      }

      nodes.forEach((node) => {
        ctx.beginPath();
        ctx.arc(node.x + offsetX, node.y + offsetY, node.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${ACCENT}, 0.45)`;
        ctx.fill();
      });
    };

    // =========================================================
    // MAIN LOOP
    // =========================================================

    const animate = () => {
      const width = canvas.width;
      const height = canvas.height;

      smoothRef.current.x += (mouseRef.current.x - smoothRef.current.x) * 0.05;
      smoothRef.current.y += (mouseRef.current.y - smoothRef.current.y) * 0.05;

      ctx.fillStyle = "#0b0e14";
      ctx.fillRect(0, 0, width, height);

      const glow = ctx.createRadialGradient(
        width * 0.5,
        height * 0.32,
        20,
        width * 0.5,
        height * 0.32,
        height * 0.75
      );
      glow.addColorStop(0, `rgba(${ACCENT_DIM}, 0.1)`);
      glow.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, width, height);

      drawNodes(smoothRef.current.x, smoothRef.current.y);

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
