import { useEffect, useRef, useState } from "react";

import "./App.css";
import InteractiveBackground from "./components/InteractiveBackground";

import NetworkVisualization from "./components/NetworkVisualisation";

import {

  startInvestigation,

  getInvestigationStatus,

  getInvestigationResult,

} from "./services/investigationService";

/* =========================================================

   APP

========================================================= */

function App() {

  const [target, setTarget] = useState("");

  const [investigationId, setInvestigationId] = useState(null);

  const [status, setStatus] = useState("idle");

  const [stage, setStage] = useState(null);

  const [result, setResult] = useState(null);

  const [selectedHop, setSelectedHop] = useState(null);

  const handleInvestigate = () => {

    if (!target.trim()) return;

    setResult(null);

    setSelectedHop(null);

    setStage("starting");

    setStatus("running");

    const id = startInvestigation(target.trim());

    setInvestigationId(id);

  };

  const handleRetest = () => {

    if (!target.trim()) return;

    setResult(null);

    setSelectedHop(null);

    setStage("starting");

    setStatus("running");

    const id = startInvestigation(target.trim());

    setInvestigationId(id);

  };

  useEffect(() => {
if (!investigationId) return;

const interval = setInterval(() => {
try {
const currentStatus =
getInvestigationStatus(investigationId);


  setStage(currentStatus.stage);

  if (currentStatus.status === "complete") {
    try {
      const investigationResult =
        getInvestigationResult(investigationId);

      setResult(investigationResult);
      setStatus("complete");

      clearInterval(interval);
    } catch (resultError) {
      console.log(
        "Backend complete, waiting for result...",
        resultError
      );
    }
  }
} catch (error) {
  console.error("Investigation status error:", error);
  clearInterval(interval);
}


}, 500);

return () => clearInterval(interval);
}, [investigationId]);


  if (status === "idle") {

    return (

      <LaunchScreen

        target={target}

        setTarget={setTarget}

        onInvestigate={handleInvestigate}

      />

    );

  }

  return (

    <InvestigationConsole

      target={target}

      stage={stage}

      result={result}

      selectedHop={selectedHop}

      setSelectedHop={setSelectedHop}

      onRetest={handleRetest}

      onNewInvestigation={() => {

        setStatus("idle");

        setInvestigationId(null);

        setResult(null);

        setStage(null);

        setSelectedHop(null);

        setTarget("");

      }}

    />

  );

}

/* =========================================================

   LIVE INTERACTIVE BACKGROUND

========================================================= */

function LiveNetworkBackground() {

  const canvasRef = useRef(null);

  const mouseRef = useRef({

    x: null,

    y: null,

  });

  useEffect(() => {

    const canvas = canvasRef.current;

    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    let width = 0;

    let height = 0;

    let animationFrame;

    const particles = [];

    const particleCount = 110;

    const resize = () => {

      width = window.innerWidth;

      height = window.innerHeight;

      const dpr = Math.min(window.devicePixelRatio || 1, 2);

      canvas.width = width * dpr;

      canvas.height = height * dpr;

      canvas.style.width = `${width}px`;

      canvas.style.height = `${height}px`;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    };

    const createParticle = () => ({

      x: Math.random() * width,

      y: Math.random() * height,

      vx: (Math.random() - 0.5) * 0.25,

      vy: (Math.random() - 0.5) * 0.25,

      radius: Math.random() * 1.8 + 0.5,

      alpha: Math.random() * 0.7 + 0.2,

      pulse: Math.random() * Math.PI * 2,

    });

    const initialize = () => {

      particles.length = 0;

      for (let i = 0; i < particleCount; i++) {

        particles.push(createParticle());

      }

    };

    const drawGlow = () => {

      const centerX = width * 0.5;

      const centerY = height * 0.42;

      const gradient = ctx.createRadialGradient(

        centerX,

        centerY,

        20,

        centerX,

        centerY,

        Math.min(width, height) * 0.52

      );

      gradient.addColorStop(0, "rgba(255, 65, 180, 0.12)");

      gradient.addColorStop(0.45, "rgba(180, 30, 130, 0.055)");

      gradient.addColorStop(1, "rgba(0, 0, 0, 0)");

      ctx.fillStyle = gradient;

      ctx.fillRect(0, 0, width, height);

    };

    const drawGlobe = (time) => {

      const cx = width * 0.5;

      const cy = height * 0.40;

      const radius =

        Math.min(width, height) * 0.29;

      ctx.save();

      ctx.translate(cx, cy);

      /*

        Outer globe glow

      */

      const globeGlow = ctx.createRadialGradient(

        0,

        0,

        radius * 0.2,

        0,

        0,

        radius

      );

      globeGlow.addColorStop(

        0,

        "rgba(255, 70, 190, 0.035)"

      );

      globeGlow.addColorStop(

        0.7,

        "rgba(255, 20, 150, 0.025)"

      );

      globeGlow.addColorStop(

        1,

        "rgba(255, 20, 150, 0)"

      );

      ctx.fillStyle = globeGlow;

      ctx.beginPath();

      ctx.arc(0, 0, radius, 0, Math.PI * 2);

      ctx.fill();

      /*

        Globe wireframe

      */

      ctx.strokeStyle =

        "rgba(255, 65, 180, 0.12)";

      ctx.lineWidth = 0.7;

      for (let i = 0; i < 7; i++) {

        const offset =

          Math.sin(time * 0.00025 + i) *

          radius *

          0.08;

        ctx.beginPath();

        ctx.ellipse(

          offset,

          0,

          Math.abs(

            radius *

              Math.sin(

                (i / 7) * Math.PI

              )

          ),

          radius,

          0,

          0,

          Math.PI * 2

        );

        ctx.stroke();

      }

      for (let i = -4; i <= 4; i++) {

        const y =

          (i / 4) * radius * 0.82;

        const curve =

          Math.sqrt(

            Math.max(

              0,

              radius * radius - y * y

            )

          );

        ctx.beginPath();

        ctx.ellipse(

          0,

          y,

          curve,

          radius * 0.13,

          0,

          0,

          Math.PI * 2

        );

        ctx.stroke();

      }

      /*

        Rotating network nodes

      */

      const nodeCount = 38;

      for (let i = 0; i < nodeCount; i++) {

        const angle =

          (i / nodeCount) *

            Math.PI *

            2 +

          time * 0.00008;

        const depth =

          Math.sin(

            angle * 2.7 + i

          );

        const x =

          Math.cos(angle) *

          radius *

          (0.45 + Math.abs(depth) * 0.45);

        const y =

          Math.sin(angle) *

          radius *

          0.75;

        ctx.beginPath();

        ctx.arc(

          x,

          y,

          depth > 0 ? 2 : 1.2,

          0,

          Math.PI * 2

        );

        ctx.fillStyle =

          depth > 0

            ? "rgba(255, 95, 200, 0.75)"

            : "rgba(255, 95, 200, 0.3)";

        ctx.fill();

      }

      ctx.restore();

    };

    const drawParticles = (time) => {

      for (const particle of particles) {

        particle.x += particle.vx;

        particle.y += particle.vy;

        particle.pulse += 0.025;

        if (

          particle.x < -20 ||

          particle.x > width + 20

        ) {

          particle.x =

            Math.random() * width;

        }

        if (

          particle.y < -20 ||

          particle.y > height + 20

        ) {

          particle.y =

            Math.random() * height;

        }

        /*

          Cursor interaction

        */

        if (

          mouseRef.current.x !== null

        ) {

          const dx =

            particle.x -

            mouseRef.current.x;

          const dy =

            particle.y -

            mouseRef.current.y;

          const distance =

            Math.sqrt(dx * dx + dy * dy);

          if (distance < 150) {

            const force =

              (150 - distance) / 150;

            particle.x +=

              (dx / Math.max(distance, 1)) *

              force *

              1.8;

            particle.y +=

              (dy / Math.max(distance, 1)) *

              force *

              1.8;

          }

        }

        const pulse =

          Math.sin(

            particle.pulse + time * 0.001

          ) *

          0.25;

        ctx.beginPath();

        ctx.arc(

          particle.x,

          particle.y,

          particle.radius + pulse,

          0,

          Math.PI * 2

        );

        ctx.fillStyle = `rgba(255, 90, 190, ${

          particle.alpha

        })`;

        ctx.fill();

      }

    };

    const drawConnections = () => {

      const connectionDistance = 125;

      for (

        let i = 0;

        i < particles.length;

        i++

      ) {

        for (

          let j = i + 1;

          j < particles.length;

          j++

        ) {

          const a = particles[i];

          const b = particles[j];

          const dx = a.x - b.x;

          const dy = a.y - b.y;

          const distance =

            Math.sqrt(dx * dx + dy * dy);

          if (

            distance <

            connectionDistance

          ) {

            const opacity =

              (1 -

                distance /

                  connectionDistance) *

              0.18;

            ctx.beginPath();

            ctx.moveTo(

              a.x,

              a.y

            );

            ctx.lineTo(

              b.x,

              b.y

            );

            ctx.strokeStyle = `rgba(

              255,

              75,

              185,

              ${opacity}

            )`;

            ctx.lineWidth = 0.6;

            ctx.stroke();

          }

        }

      }

    };

    const animate = (time) => {

      ctx.clearRect(

        0,

        0,

        width,

        height

      );

      drawGlow();

      drawGlobe(time);

      drawConnections();

      drawParticles(time);

      animationFrame =

        requestAnimationFrame(

          animate

        );

    };

    const handleMouseMove = (event) => {

      mouseRef.current.x =

        event.clientX;

      mouseRef.current.y =

        event.clientY;

    };

    const handleMouseLeave = () => {

      mouseRef.current.x = null;

      mouseRef.current.y = null;

    };

    resize();

    initialize();

    window.addEventListener(

      "resize",

      resize

    );

    window.addEventListener(

      "mousemove",

      handleMouseMove

    );

    window.addEventListener(

      "mouseleave",

      handleMouseLeave

    );

    animationFrame =

      requestAnimationFrame(

        animate

      );

    return () => {

      cancelAnimationFrame(

        animationFrame

      );

      window.removeEventListener(

        "resize",

        resize

      );

      window.removeEventListener(

        "mousemove",

        handleMouseMove

      );

      window.removeEventListener(

        "mouseleave",

        handleMouseLeave

      );

    };

  }, []);

  return (

    <canvas

      ref={canvasRef}

      className="network-background-canvas"

    />

  );

}

/* =========================================================

   LAUNCH SCREEN

========================================================= */

function LaunchScreen({

  target,

  setTarget,

  onInvestigate,

}) {

  const [focused, setFocused] =

    useState(false);

  return (

    <main className="launch-screen">

      <InteractiveBackground />

      <div className="launch-vignette" />

      <div className="scanlines" />

      {/* =================================================

          TOP NAVIGATION

      ================================================= */}

      <header className="launch-header">

        <div className="brand">

          <div className="brand-symbol">

            ◈

          </div>

          <div>

            <div className="brand-name">

              BLACK BOX

            </div>

            <div className="brand-subtitle">

              NETWORK INVESTIGATION SYSTEM

            </div>

          </div>

        </div>

        <nav className="launch-nav">

          <span>ABOUT</span>

          <span>DOCS</span>

          <span>STATUS</span>

          <div className="online-indicator">

            <span />

            ONLINE

          </div>

        </nav>

      </header>

      {/* =================================================

          CORNER MARKERS

      ================================================= */}

      <div className="corner-marker top-left" />

      <div className="corner-marker top-right" />

      <div className="corner-marker bottom-left" />

      <div className="corner-marker bottom-right" />

      {/* =================================================

          LEFT SIDE INFORMATION

      ================================================= */}

      <div className="side-info side-info-left">

        <span>TRACE</span>

        <span>ANALYZE</span>

        <span>DETECT</span>

        <span>SOLVE</span>

      </div>

      {/* =================================================

          RIGHT SIDE QUOTE

      ================================================= */}

      <div className="side-info side-info-right">

        <span>SOMEWHERE</span>

        <span>IN THE INTERNET</span>

        <span>THE ANSWER</span>

        <span>IS ALWAYS THERE</span>

      </div>

      {/* =================================================

          MAIN HERO

      ================================================= */}

      <section className="launch-content">

        <div className="system-label hero-label">

          [ NETWORK INVESTIGATION SYSTEM ]

        </div>

        <h1 className="black-box-title">

          BLACK BOX

        </h1>

        <div className="title-line">

          <span />

          <span />

          <span />

        </div>

        <p className="launch-description">

          Investigate network paths. Detect anomalies. Find the cause.

        </p>

        {/* =================================================

            TARGET FORM

        ================================================= */}

        <div

          className={`target-form ${

            focused

              ? "target-form-focused"

              : ""

          }`}

        >

          <div className="input-icon">

            ⌕

          </div>

          <input

            type="text"

            value={target}

            onChange={(event) =>

              setTarget(

                event.target.value

              )

            }

            onFocus={() =>

              setFocused(true)

            }

            onBlur={() =>

              setFocused(false)

            }

            onKeyDown={(event) => {

              if (

                event.key ===

                "Enter"

              ) {

                onInvestigate();

              }

            }}

            placeholder="github.com"

          />

          <button

            onClick={onInvestigate}

            className="investigate-button"

          >

            INVESTIGATE

            <span>→</span>

          </button>

        </div>

        <div className="launch-hint">

          ENTER A DOMAIN OR IP ADDRESS TO BEGIN INVESTIGATION

        </div>

      </section>

      {/* =================================================

          CUTE MASCOTS

      ================================================= */}

      <div className="mascots">

        <CuteMascot

          type="blackbox"

          label="BLACK BOX"

        />

        <CuteMascot

          type="pink"

          label="ANALYST"

        />

      </div>

      {/* =================================================

          LEFT LIVE SYSTEM PANEL

      ================================================= */}

      <LiveSystemPanel />

      {/* =================================================

          RIGHT PIPELINE PANEL

      ================================================= */}

      <PipelinePanel />

      {/* =================================================

          DECORATIVE PETALS

      ================================================= */}

      <div className="floating-petals">

        <span>✦</span>

        <span>◆</span>

        <span>✧</span>

        <span>✦</span>

        <span>◇</span>

        <span>✧</span>

        <span>◆</span>

      </div>

      <div className="launch-footer">

        // A CLEARER INTERNET FOR EVERYONE //

      </div>

    </main>

  );

}

/* =========================================================

   CUTE MASCOT

========================================================= */

function CuteMascot({

  type,

  label,

}) {

  return (

    <div className={`mascot ${type}`}>

      <div className="mascot-cape" />

      <div className="mascot-body">

        <div className="cat-ear left" />

        <div className="cat-ear right" />

        <div className="cat-face">

          <div className="cat-eye left" />

          <div className="cat-eye right" />

          <div className="cat-nose" />

        </div>

        <div className="mascot-symbol">

          {type === "blackbox"

            ? "B"

            : "♥"}

        </div>

      </div>

      <div className="mascot-tail" />

      {type === "pink" && (

        <div className="mascot-bow">

          ♥

        </div>

      )}

      <div className="mascot-label">

        {label}

      </div>

    </div>

  );

}

/* =========================================================

   LIVE SYSTEM PANEL

========================================================= */

function LiveSystemPanel() {

  return (

    <div className="live-system-panel">

      <div className="panel-title">

        LIVE SYSTEM

      </div>

      <div className="signal-graph">

        <span />

        <span />

        <span />

        <span />

        <span />

        <span />

        <span />

        <span />

        <span />

        <span />

      </div>

      <div className="panel-status">

        SCANNING THE INTERNET

      </div>

      <div className="progress-track">

        <div />

      </div>

    </div>

  );

}

/* =========================================================

   PIPELINE PANEL

========================================================= */

function PipelinePanel() {

  const stages = [

    "MONITORING",

    "DNS",

    "HTTP",

    "TRACEROUTE",

    "ANOMALY DETECTION",

    "PATH ANALYSIS",

    "DIAGNOSIS",

  ];

  return (

    <div className="pipeline-panel">

      {stages.map(

        (stage, index) => (

          <div

            className="pipeline-row"

            key={stage}

          >

            <div

              className={`pipeline-status-dot ${

                index === 0

                  ? "active"

                  : ""

              }`}

            />

            <span>

              {stage}

            </span>

          </div>

        )

      )}

    </div>

  );

}

/* =========================================================

   INVESTIGATION CONSOLE

========================================================= */

function InvestigationConsole({

  target,

  stage,

  result,

  selectedHop,

  setSelectedHop,

  onRetest,

  onNewInvestigation,

}) {

  const stages = [

    "starting",

    "dns",

    "http",

    "path_discovery",

    "path_analysis",

    "complete",

  ];

  const currentStageIndex =

    stages.indexOf(stage);

  return (

    <main className="investigation-screen">

      <header className="target-bar">

        <div>

          <div className="system-label">

            BLACK BOX / INVESTIGATION

          </div>

          <div className="target-name">

            {target}

          </div>

        </div>

        <div className="target-status">

          {result

            ? "INVESTIGATION COMPLETE"

            : "INVESTIGATION RUNNING"}

        </div>

      </header>

      {/* =================================================

          01 PIPELINE

      ================================================= */}

      <section className="progress-section">

        <div className="section-heading">

          <span>01</span>

          <h2>

            INVESTIGATION PIPELINE

          </h2>

        </div>

        <div className="pipeline">

          {stages.map(

            (item, index) => {

              let className =

                "pipeline-stage";

              if (

                index <

                currentStageIndex

              ) {

                className +=

                  " completed";

              }

              if (

                index ===

                currentStageIndex

              ) {

                className +=

                  " active";

              }

              return (

                <div

                  className={className}

                  key={item}

                >

                  <div className="pipeline-dot" />

                  <div className="pipeline-name">

                    {item

                      .replaceAll(

                        "_",

                        " "

                      )

                      .toUpperCase()}

                  </div>

                </div>

              );

            }

          )}

        </div>

      </section>

      {/*=================================================

          02 STATUS

      ================================================= */}

      <section className="result-preview">

        <div className="section-heading">

          <span>02</span>

          <h2>

            INVESTIGATION STATUS

          </h2>

        </div>

        {!result ? (

          <div className="running-panel">

            <div className="running-indicator">

              <span />

              INVESTIGATION IN PROGRESS

            </div>

            <div className="running-stage">

              {stage

                ? stage

                    .replaceAll(

                      "_",

                      " "

                    )

                    .toUpperCase()

                : "INITIALIZING"}

            </div>

            <p>

              Collecting network information

              and analyzing the discovered path.

            </p>

          </div>

        ) : (

          <div className="completed-panel">

            <div className="completed-status">

              INVESTIGATION COMPLETE

            </div>

            <div className="completed-summary">

              <div>

                <span>TARGET</span>

                <strong>

                  {result.target}

                </strong>

              </div>

              <div>

                <span>HTTP STATUS</span>

                <strong>

                  {result.http?.statusCode ??

                    "—"}

                </strong>

              </div>

              <div>

                <span>RESPONSE TIME</span>

                <strong>

                  {result.http?.responseTime ??

                    "—"}{" "}

                  ms

                </strong>

              </div>

              <div>

                <span>DIAGNOSIS</span>

                <strong>

                  {result.diagnosis

                    ?.probableCause ??

                    "—"}

                </strong>

              </div>

            </div>

          </div>

        )}

      </section>

      {/* =================================================

          03 VISUALIZATION

      ================================================= */}

      {result && (

        <section className="visualization-section">

          <div className="section-heading">

            <span>03</span>

            <h2>

              NETWORK VISUALIZATION

            </h2>

          </div>

          <p className="section-description">

            Interactive three-dimensional

            representation of the discovered

            network path.

          </p>

          <div className="network-visualization-wrapper">

            <NetworkVisualization

              path={

                result.currentPath ||

                []

              }

              selectedHop={

                selectedHop

              }

              onSelectHop={

                setSelectedHop

              }

            />

          </div>

        </section>

      )}

      {/* =================================================

          04 PREVIOUS

      ================================================= */}

      {result && (

        <PreviousNetworkPath

          path={

            result.previousPath ||

            result.baselinePath ||

            result.previous?.path ||

            result.pathComparison

              ?.previousPath ||

            []

          }

          currentPath={

            result.currentPath ||

            []

          }

        />

      )}

      {/* =================================================

          05 CURRENT

      ================================================= */}

      {result && (

        <>

          <NetworkPath

            path={

              result.currentPath

            }

            selectedHop={

              selectedHop

            }

            onSelectHop={

              setSelectedHop

            }

          />

          {selectedHop && (

            <HopDetails

              hop={selectedHop}

            />

          )}

          <PathComparison

            result={result}

          />

          <PerformanceAnalysis

            result={result}

          />

          <EvidenceAnalysis

            result={result}

          />

          <DiagnosisAnalysis

            result={result}

          />

          <InvestigationTimeline

            result={result}

          />

          <FinalResult

            result={result}

            target={target}

            onRetest={onRetest}

            onNewInvestigation={

              onNewInvestigation

            }

          />

        </>

      )}

    </main>

  );

}

/* =========================================================

   PREVIOUS NETWORK PATH

========================================================= */

function PreviousNetworkPath({

  path,

}) {

  if (

    !path ||

    path.length === 0

  ) {

    return (

      <section className="network-section previous-network-section">

        <div className="section-heading">

          <span>04</span>

          <h2>

            PREVIOUS NETWORK PATH

          </h2>

        </div>

        <p className="section-description">

          No previous network route is

          available for comparison.

        </p>

        <div className="empty-panel">

          NO BASELINE NETWORK PATH AVAILABLE

        </div>

      </section>

    );

  }

  return (

    <section className="network-section previous-network-section">

      <div className="section-heading">

        <span>04</span>

        <h2>

          PREVIOUS NETWORK PATH

        </h2>

      </div>

      <p className="section-description">

        Baseline route captured before the

        current investigation.

      </p>

      <div className="path-label previous-path-label">

        BASELINE / PREVIOUS ROUTE

      </div>

      <div className="path-container previous-path-container">

        {path.map(

          (hop, index) => {

            const hopIp =

              hop?.ip ||

              hop?.address ||

              hop?.host ||

              "UNKNOWN";

            const hopNumber =

              hop?.hop ??

              hop?.number ??

              index + 1;

            const rtt =

              hop?.rtt ??

              hop?.latency ??

              "—";

            const packetLoss =

              hop?.packetLoss ??

              hop?.loss ??

              0;

            return (

              <div

                className="path-node-wrapper"

                key={`previous-${hopIp}-${index}`}

              >

                <div className="hop-card previous-hop">

                  <div className="hop-number">

                    HOP {hopNumber}

                  </div>

                  <div className="hop-ip">

                    {hopIp}

                  </div>

                  <div className="hop-meta">

                    <span>

                      {rtt} ms

                    </span>

                    <span>

                      {packetLoss}% LOSS

                    </span>

                  </div>

                  {hop.network && (

                    <div className="hop-network">

                      {hop.network}

                    </div>

                  )}

                </div>

                {index <

                  path.length - 1 && (

                  <div className="path-connector">

                    <span />

                  </div>

                )}

              </div>

            );

          }

        )}

      </div>

    </section>

  );

}

/* =========================================================

   CURRENT NETWORK PATH

========================================================= */

function NetworkPath({

  path,

  selectedHop,

  onSelectHop,

}) {

  if (

    !path ||

    path.length === 0

  ) {

    return (

      <section className="network-section">

        <div className="section-heading">

          <span>05</span>

          <h2>

            NETWORK PATH

          </h2>

        </div>

        <div className="empty-panel">

          NO NETWORK PATH DATA AVAILABLE

        </div>

      </section>

    );

  }

  return (

    <section className="network-section">

      <div className="section-heading">

        <span>05</span>

        <h2>

          DISCOVERED NETWORK PATH

        </h2>

      </div>

      <p className="section-description">

        Select a hop to inspect the network

        information collected during the investigation.

      </p>

      <div className="path-label current-path-label">

        CURRENT / DISCOVERED ROUTE

      </div>

      <div className="path-container">

        {path.map(

          (hop, index) => {

            const isSelected =

              selectedHop?.ip ===

              hop.ip;

            return (

              <div

                className="path-node-wrapper"

                key={`${hop.ip}-${index}`}

              >

                <button

                  className={`hop-card ${

                    isSelected

                      ? "selected"

                      : ""

                  } ${

                    hop.status ===

                    "anomalous"

                      ? "anomalous"

                      : ""

                  }`}

                  onClick={() =>

                    onSelectHop(

                      hop

                    )

                  }

                >

                  <div className="hop-number">

                    HOP {hop.hop}

                  </div>

                  <div className="hop-ip">

                    {hop.ip}

                  </div>

                  <div className="hop-meta">

                    <span>

                      {hop.rtt} ms

                    </span>

                    <span>

                      {hop.packetLoss}%

                      LOSS

                    </span>

                  </div>

                  {hop.network && (

                    <div className="hop-network">

                      {hop.network}

                    </div>

                  )}

                  {hop.status ===

                    "anomalous" && (

                    <div className="hop-warning">

                      ANOMALY DETECTED

                    </div>

                  )}

                </button>

                {index <

                  path.length - 1 && (

                  <div className="path-connector">

                    <span />

                  </div>

                )}

              </div>

            );

          }

        )}

      </div>

    </section>

  );

}

/* =========================================================

   HOP DETAILS

========================================================= */

function HopDetails({

  hop,

}) {

  return (

    <section className="hop-details-section">

      <div className="section-heading">

        <span>06</span>

        <h2>

          HOP INSPECTION

        </h2>

      </div>

      <div className="hop-details-panel">

        <div className="hop-details-header">

          <div>

            <span>HOP</span>

            <strong>

              {hop.hop}

            </strong>

          </div>

          <div>

            <span>STATUS</span>

            <strong>

              {hop.status?.toUpperCase() ??

                "UNKNOWN"}

            </strong>

          </div>

        </div>

        <div className="hop-details-grid">

          <div>

            <span>IP ADDRESS</span>

            <strong>

              {hop.ip}

            </strong>

          </div>

          <div>

            <span>ROUND TRIP TIME</span>

            <strong>

              {hop.rtt} ms

            </strong>

          </div>

          <div>

            <span>PACKET LOSS</span>

            <strong>

              {hop.packetLoss}%

            </strong>

          </div>

          <div>

            <span>ASN</span>

            <strong>

              {hop.asn ?? "—"}

            </strong>

          </div>

          <div>

            <span>NETWORK</span>

            <strong>

              {hop.network ?? "—"}

            </strong>

          </div>

        </div>

        {hop.anomaly && (

          <div className="hop-anomaly">

            <div className="hop-anomaly-title">

              {hop.anomaly.type}

            </div>

            {hop.anomaly.severity && (

              <div className="hop-anomaly-severity">

                SEVERITY:{" "}

                {hop.anomaly.severity.toUpperCase()}

              </div>

            )}

          </div>

        )}

        {hop.evidence &&

          hop.evidence.length > 0 && (

            <div className="hop-evidence">

              <div className="hop-evidence-title">

                EVIDENCE

              </div>

              {hop.evidence.map(

                (item, index) => (

                  <div

                    className="hop-evidence-item"

                    key={index}

                  >

                    <span>✓</span>

                    {item}

                  </div>

                )

              )}

            </div>

          )}

      </div>

    </section>

  );

}

/* =========================================================

   PATH COMPARISON

========================================================= */

function PathComparison({

  result,

}) {

  const comparison =

    result.pathComparison;

  return (

    <section className="analysis-section">

      <div className="analysis-header">

        <div>

          <div className="section-heading">

            <span>07</span>

            <h2>

              PATH COMPARISON

            </h2>

          </div>

          <p className="section-description">

            Comparing the discovered route

            against the available baseline.

          </p>

        </div>

        <div className="analysis-status">

          {comparison?.status ===

          "no_baseline"

            ? "NO BASELINE"

            : comparison?.status ===

              "path_change_with_performance_impact"

            ? "PATH CHANGED"

            : "ANALYZED"}

        </div>

      </div>

      {!comparison ||

      comparison.status ===

        "no_baseline" ? (

        <div className="analysis-empty">

          <h3>

            NO BASELINE AVAILABLE

          </h3>

          <p>

            A previous route is not available

            for this investigation, so path-change

            analysis cannot be performed.

          </p>

        </div>

      ) : (

        <div className="comparison-panel">

          <div className="comparison-message">

            {comparison.message}

          </div>

          <div className="comparison-grid">

            <div>

              <span>DIVERGENCE POINT</span>

              <strong>

                HOP{" "}

                {comparison.divergencePoint}

              </strong>

            </div>

            <div>

              <span>ADDED HOPS</span>

              <strong>

                {comparison.addedHops

                  ?.length ?? 0}

              </strong>

            </div>

            <div>

              <span>REMOVED HOPS</span>

              <strong>

                {comparison.removedHops

                  ?.length ?? 0}

              </strong>

            </div>

            <div>

              <span>COMMON HOPS</span>

              <strong>

                {comparison.commonHops

                  ?.length ?? 0}

              </strong>

            </div>

          </div>

          <div className="route-changes">

            <div className="route-column">

              <div className="route-column-title">

                REMOVED

              </div>

              {comparison.removedHops?.map(

                (hop, index) => (

                  <div

                    className="route-hop removed"

                    key={index}

                  >

                    {hop}

                  </div>

                )

              )}

            </div>

            <div className="route-column">

              <div className="route-column-title">

                ADDED

              </div>

              {comparison.addedHops?.map(

                (hop, index) => (

                  <div

                    className="route-hop added"

                    key={index}

                  >

                    {hop}

                  </div>

                )

              )}

            </div>

          </div>

        </div>

      )}

    </section>

  );

}

/* =========================================================

   PERFORMANCE ANALYSIS

========================================================= */

function PerformanceAnalysis({

  result,

}) {

  const comparison =

    result.performanceComparison;

  return (

    <section className="analysis-section">

      <div className="analysis-header">

        <div>

          <div className="section-heading">

            <span>08</span>

            <h2>

              PERFORMANCE ANALYSIS

            </h2>

          </div>

          <p className="section-description">

            Comparing current network performance

            against the available baseline.

          </p>

        </div>

        {comparison && (

          <div className="analysis-status">

            {comparison.status

              ?.replaceAll(

                "_",

                " "

              )

              .toUpperCase()}

          </div>

        )}

      </div>

      {!comparison ? (

        <div className="analysis-empty">

          <h3>

            NO PERFORMANCE BASELINE AVAILABLE

          </h3>

          <p>

            This investigation does not contain

            a previous performance measurement.

          </p>

        </div>

      ) : (

        <div className="performance-panel">

          <div className="performance-grid">

            <PerformanceMetric

              label="ROUND TRIP TIME"

              previous={

                comparison.previous.rtt

              }

              current={

                comparison.current.rtt

              }

              difference={

                comparison.difference.rtt

              }

              unit="ms"

            />

            <PerformanceMetric

              label="PACKET LOSS"

              previous={

                comparison.previous

                  .packetLoss

              }

              current={

                comparison.current

                  .packetLoss

              }

              difference={

                comparison.difference

                  .packetLoss

              }

              unit="%"

            />

            <PerformanceMetric

              label="HTTP RESPONSE TIME"

              previous={

                comparison.previous

                  .httpResponseTime

              }

              current={

                comparison.current

                  .httpResponseTime

              }

              difference={

                comparison.difference

                  .httpResponseTime

              }

              unit="ms"

            />

            <div className="performance-metric">

              <span>

                HTTP STATUS

              </span>

              <div className="metric-values">

                <strong>

                  {

                    comparison.previous

                      .httpStatusCode

                  }

                </strong>

                <span>→</span>

                <strong>

                  {

                    comparison.current

                      .httpStatusCode

                  }

                </strong>

              </div>

            </div>

          </div>

          <div className="performance-finding">

            <span>

              INVESTIGATION FINDING

            </span>

            <strong>

              {comparison.status ===

              "degraded"

                ? "NETWORK PERFORMANCE DEGRADATION DETECTED"

                : "NO SIGNIFICANT PERFORMANCE DEGRADATION"}

            </strong>

          </div>

        </div>

      )}

    </section>

  );

}

function PerformanceMetric({

  label,

  previous,

  current,

  difference,

  unit,

}) {

  const percentage =

    previous !== 0

      ? Math.round(

          (difference /

            previous) *

            100

        )

      : 0;

  return (

    <div className="performance-metric">

      <span>{label}</span>

      <div className="metric-values">

        <strong>

          {previous}

          {unit}

        </strong>

        <span>→</span>

        <strong className="current-value">

          {current}

          {unit}

        </strong>

      </div>

      <div className="metric-difference">

        +{difference}

        {unit}

        {percentage !== 0 && (

          <span>

            {" "}

            (+{percentage}%)

          </span>

        )}

      </div>

    </div>

  );

}

/* =========================================================

   EVIDENCE

========================================================= */

function EvidenceAnalysis({

  result,

}) {

  const anomalies =

    result.anomalies || [];

  const evidence =

    result.evidence || [];

  return (

    <section className="evidence-section">

      <div className="section-heading">

        <span>09</span>

        <h2>

          ANOMALIES & EVIDENCE

        </h2>

      </div>

      <p className="section-description">

        Detected anomalies and the evidence

        collected during the investigation.

      </p>

      <div className="evidence-content">

        <div className="anomalies-block">

          <div className="evidence-subheading">

            <span>

              ANOMALIES DETECTED

            </span>

            <div className="anomaly-count">

              {anomalies.length}

            </div>

          </div>

          {anomalies.length ===

          0 ? (

            <div className="evidence-empty">

              <h3>

                NO ANOMALIES DETECTED

              </h3>

              <p>

                No abnormal network behavior

                was recorded.

              </p>

            </div>

          ) : (

            <div className="anomaly-list">

              {anomalies.map(

                (

                  anomaly,

                  index

                ) => (

                  <AnomalyCard

                    anomaly={

                      anomaly

                    }

                    index={index}

                    key={index}

                  />

                )

              )}

            </div>

          )}

        </div>

        <div className="evidence-block">

          <div className="evidence-subheading">

            <span>

              EVIDENCE

            </span>

            <div className="anomaly-count">

              {evidence.length}

            </div>

          </div>

          {evidence.length ===

          0 ? (

            <div className="evidence-empty">

              <h3>

                NO EVIDENCE RECORDED

              </h3>

              <p>

                This investigation did not

                record supporting evidence.

              </p>

            </div>

          ) : (

            <div className="evidence-list">

              {evidence.map(

                (

                  item,

                  index

                ) => (

                  <div

                    className="evidence-item"

                    key={index}

                  >

                    <div className="evidence-marker">

                      ✓

                    </div>

                    <div className="evidence-text">

                      {item}

                    </div>

                  </div>

                )

              )}

            </div>

          )}

        </div>

      </div>

    </section>

  );

}

/* =========================================================

   ANOMALY CARD

========================================================= */

function AnomalyCard({

  anomaly,

  index,

}) {

  const type =

    anomaly.type ||

    "NETWORK ANOMALY";

  const hop =

    anomaly.hop;

  const severity =

    anomaly.severity;

  const excludedKeys = [

    "type",

    "hop",

    "severity",

  ];

  const details =

    Object.entries(

      anomaly

    ).filter(

      ([key]) =>

        !excludedKeys.includes(

          key

        )

    );

  return (

    <div className="anomaly-card">

      <div className="anomaly-index">

        {String(

          index + 1

        ).padStart(

          2,

          "0"

        )}

      </div>

      <div className="anomaly-main">

        <div className="anomaly-top">

          <div className="anomaly-type">

            {type}

          </div>

          {severity && (

            <div

              className={`anomaly-severity ${severity.toLowerCase()}`}

            >

              {severity.toUpperCase()}

            </div>

          )}

        </div>

        {hop !==

          undefined && (

          <div className="anomaly-hop">

            HOP {hop}

          </div>

        )}

        {details.length >

          0 && (

          <div className="anomaly-details">

            {details.map(

              ([

                key,

                value,

              ]) => (

                <AnomalyDetail

                  key={key}

                  label={key}

                  value={value}

                />

              )

            )}

          </div>

        )}

      </div>

    </div>

  );

}

function AnomalyDetail({

  label,

  value,

}) {

  if (

    value === null ||

    value === undefined ||

    value === ""

  ) {

    return null;

  }

  if (

    Array.isArray(

      value

    )

  ) {

    return (

      <div className="anomaly-detail">

        <span>

          {formatLabel(

            label

          )}

        </span>

        <strong>

          {value.join(

            ", "

          )}

        </strong>

      </div>

    );

  }

  if (

    typeof value ===

    "object"

  ) {

    return (

      <div className="anomaly-detail">

        <span>

          {formatLabel(

            label

          )}

        </span>

        <strong>

          {Object.entries(

            value

          )

            .map(

              ([

                nestedKey,

                nestedValue,

              ]) =>

                `${formatLabel(

                  nestedKey

                )}: ${nestedValue}`

            )

            .join(" • ")}

        </strong>

      </div>

    );

  }

  return (

    <div className="anomaly-detail">

      <span>

        {formatLabel(

          label

        )}

      </span>

      <strong>

        {String(value)}

      </strong>

    </div>

  );

}

/* =========================================================

   DIAGNOSIS

========================================================= */

function DiagnosisAnalysis({

  result,

}) {

  const diagnosis =

    result.diagnosis;

  const hypotheses =

    result.hypotheses || [];

  if (!diagnosis) {

    return (

      <section className="diagnosis-section">

        <div className="section-heading">

          <span>10</span>

          <h2>

            DIAGNOSIS & HYPOTHESES

          </h2>

        </div>

        <div className="analysis-empty">

          <h3>

            NO DIAGNOSIS AVAILABLE

          </h3>

          <p>

            The investigation did not

            return a diagnostic conclusion.

          </p>

        </div>

      </section>

    );

  }

  const supportingEvidence =

    diagnosis.supportingEvidence ||

    [];

  const alternativeHypotheses =

    diagnosis.alternativeHypotheses ||

    [];

  return (

    <section className="diagnosis-section">

      <div className="section-heading">

        <span>10</span>

        <h2>

          DIAGNOSIS & HYPOTHESES

        </h2>

      </div>

      <p className="section-description">

        Converting the collected evidence

        and network anomalies into an

        engineering diagnosis.

      </p>

      <div className="diagnosis-panel">

        <div className="diagnosis-main">

          <div className="diagnosis-label">

            PROBABLE CAUSE

          </div>

          <div className="diagnosis-cause">

            {diagnosis.probableCause ||

              "UNDETERMINED"}

          </div>

          <div className="diagnosis-confidence">

            <span>

              CONFIDENCE

            </span>

            <strong>

              {diagnosis.confidence

                ? String(

                    diagnosis.confidence

                  ).toUpperCase()

                : "UNKNOWN"}

            </strong>

          </div>

        </div>

        <div className="diagnosis-evidence">

          <div className="diagnosis-subheading">

            SUPPORTING EVIDENCE

          </div>

          {supportingEvidence.length ===

          0 ? (

            <div className="diagnosis-no-evidence">

              NO SUPPORTING EVIDENCE PROVIDED

            </div>

          ) : (

            <div className="diagnosis-evidence-list">

              {supportingEvidence.map(

                (

                  item,

                  index

                ) => (

                  <div

                    className="diagnosis-evidence-item"

                    key={index}

                  >

                    <span>✓</span>

                    <div>

                      {item}

                    </div>

                  </div>

                )

              )}

            </div>

          )}

        </div>

      </div>

      {(hypotheses.length >

        0 ||

        alternativeHypotheses.length >

          0) && (

        <div className="hypotheses-panel">

          <div className="hypotheses-header">

            <div>

              <div className="diagnosis-subheading">

                HYPOTHESES

              </div>

              <p>

                Possible explanations considered

                during the investigation.

              </p>

            </div>

            <div className="anomaly-count">

              {hypotheses.length >

              0

                ? hypotheses.length

                : alternativeHypotheses.length}

            </div>

          </div>

          {hypotheses.length >

          0 ? (

            <div className="hypotheses-list">

              {hypotheses.map(

                (

                  hypothesis,

                  index

                ) => (

                  <HypothesisCard

                    hypothesis={

                      hypothesis

                    }

                    index={

                      index

                    }

                    key={

                      index

                    }

                  />

                )

              )}

            </div>

          ) : (

            <div className="hypotheses-list">

              {alternativeHypotheses.map(

                (

                  hypothesis,

                  index

                ) => (

                  <HypothesisCard

                    hypothesis={

                      hypothesis

                    }

                    index={

                      index

                    }

                    key={

                      index

                    }

                  />

                )

              )}

            </div>

          )}

        </div>

      )}

    </section>

  );

}

/* =========================================================

   HYPOTHESIS

========================================================= */

function HypothesisCard({

  hypothesis,

  index,

}) {

  if (

    typeof hypothesis ===

    "string"

  ) {

    return (

      <div className="hypothesis-card">

        <div className="hypothesis-index">

          {String(

            index + 1

          ).padStart(

            2,

            "0"

          )}

        </div>

        <div className="hypothesis-main">

          <div className="hypothesis-title">

            {hypothesis}

          </div>

        </div>

      </div>

    );

  }

  if (

    !hypothesis ||

    typeof hypothesis !==

      "object"

  ) {

    return null;

  }

  const excludedKeys = [

    "hypothesis",

    "name",

    "title",

    "confidence",

  ];

  const title =

    hypothesis.hypothesis ||

    hypothesis.name ||

    hypothesis.title ||

    "ALTERNATIVE HYPOTHESIS";

  const details =

    Object.entries(

      hypothesis

    ).filter(

      ([key]) =>

        !excludedKeys.includes(

          key

        )

    );

  return (

    <div className="hypothesis-card">

      <div className="hypothesis-index">

        {String(

          index + 1

        ).padStart(

          2,

          "0"

        )}

      </div>

      <div className="hypothesis-main">

        <div className="hypothesis-top">

          <div className="hypothesis-title">

            {title}

          </div>

          {hypothesis.confidence && (

            <div className="hypothesis-confidence">

              {String(

                hypothesis.confidence

              ).toUpperCase()}

            </div>

          )}

        </div>

        {details.length >

          0 && (

          <div className="hypothesis-details">

            {details.map(

              ([

                key,

                value,

              ]) => (

                <HypothesisDetail

                  key={key}

                  label={key}

                  value={value}

                />

              )

            )}

          </div>

        )}

      </div>

    </div>

  );

}

function HypothesisDetail({

  label,

  value,

}) {

  if (

    value === null ||

    value === undefined ||

    value === ""

  ) {

    return null;

  }

  let displayValue =

    value;

  if (

    Array.isArray(

      value

    )

  ) {

    displayValue =

      value.join(", ");

  } else if (

    typeof value ===

    "object"

  ) {

    displayValue =

      Object.entries(

        value

      )

        .map(

          ([

            nestedKey,

            nestedValue,

          ]) =>

            `${formatLabel(

              nestedKey

            )}: ${nestedValue}`

        )

        .join(" • ");

  }

  return (

    <div className="hypothesis-detail">

      <span>

        {formatLabel(

          label

        )}

      </span>

      <strong>

        {String(

          displayValue

        )}

      </strong>

    </div>

  );

}

/* =========================================================

   TIMELINE

========================================================= */

function InvestigationTimeline({

  result,

}) {

  const timeline =

    result.timeline || [];

  return (

    <section className="timeline-section">

      <div className="section-heading">

        <span>11</span>

        <h2>

          INVESTIGATION TIMELINE

        </h2>

      </div>

      <p className="section-description">

        Sequence of events recorded during

        the investigation.

      </p>

      {timeline.length ===

      0 ? (

        <div className="analysis-empty">

          <h3>

            NO TIMELINE AVAILABLE

          </h3>

          <p>

            No investigation events were returned.

          </p>

        </div>

      ) : (

        <div className="timeline-panel">

          <div className="timeline-line" />

          <div className="timeline-list">

            {timeline.map(

              (

                item,

                index

              ) => (

                <TimelineEvent

                  event={item}

                  index={

                    index

                  }

                  key={

                    index

                  }

                />

              )

            )}

          </div>

        </div>

      )}

    </section>

  );

}

function TimelineEvent({

  event,

  index,

}) {

  if (

    !event ||

    typeof event !==

      "object"

  ) {

    return null;

  }

  const eventName =

    event.event ||

    event.type ||

    event.name ||

    "Investigation event";

  const status =

    event.status;

  return (

    <div className="timeline-event">

      <div className="timeline-marker">

        <span />

      </div>

      <div className="timeline-content">

        <div className="timeline-event-header">

          <div className="timeline-event-name">

            {eventName}

          </div>

          {status && (

            <div className="timeline-event-status">

              {String(

                status

              ).toUpperCase()}

            </div>

          )}

        </div>

        <div className="timeline-event-number">

          EVENT{" "}

          {String(

            index + 1

          ).padStart(

            2,

            "0"

          )}

        </div>

        {Object.entries(

          event

        )

          .filter(

            ([key]) =>

              ![

                "event",

                "type",

                "name",

                "status",

              ].includes(

                key

              )

          )

          .map(

            ([

              key,

              value,

            ]) => (

              <TimelineDetail

                key={key}

                label={key}

                value={value}

              />

            )

          )}

      </div>

    </div>

  );

}

function TimelineDetail({

  label,

  value,

}) {

  if (

    value === null ||

    value === undefined ||

    value === ""

  ) {

    return null;

  }

  let displayValue =

    value;

  if (

    Array.isArray(

      value

    )

  ) {

    displayValue =

      value.join(", ");

  } else if (

    typeof value ===

    "object"

  ) {

    displayValue =

      Object.entries(

        value

      )

        .map(

          ([

            nestedKey,

            nestedValue,

          ]) =>

            `${formatLabel(

              nestedKey

            )}: ${nestedValue}`

        )

        .join(" • ");

  }

  return (

    <div className="timeline-detail">

      <span>

        {formatLabel(

          label

        )}

      </span>

      <strong>

        {String(

          displayValue

        )}

      </strong>

    </div>

  );

}

/*=========================================================

   FINAL RESULT

========================================================= */

function FinalResult({

  result,

  target,

  onRetest,

  onNewInvestigation,

}) {

  const diagnosis =

    result.diagnosis;

  const comparison =

    result.performanceComparison;

  const pathComparison =

    result.pathComparison;

  const anomalies =

    result.anomalies || [];

  const overallStatus =

    comparison?.status ===

      "degraded" ||

    anomalies.length > 0

      ? "DEGRADED"

      : "NORMAL";

 const pathStatusLabel =
!pathComparison || !pathComparison.status
? "UNKNOWN"
: pathComparison.status === "no_baseline"
? "BASELINE ESTABLISHED"
: pathComparison.status
.replaceAll("_", " ")
.toUpperCase();


  const httpStatusLabel =

    result.http?.statusCode ??

    "—";

  const supportingEvidence =

    diagnosis?.supportingEvidence ||

    [];

  return (

    <section className="final-result-section">

      <div className="section-heading">

        <span>12</span>

        <h2>

          FINAL RESULT

        </h2>

      </div>

      <p className="section-description">

        Conclusion of the investigation,

        combining the diagnosis, measurements,

        and strongest supporting evidence.

      </p>

      <div className="final-result-panel">

        <div className="final-result-header">

          <div>

            <span>TARGET</span>

            <strong>

              {target}

            </strong>

          </div>

          <div>

            <span>STATUS</span>

            <strong

              className={

                overallStatus ===

                "DEGRADED"

                  ? "status-degraded"

                  : "status-normal"

              }

            >

              {overallStatus}

            </strong>

          </div>

        </div>

        <div className="final-result-grid">

          <div>

            <span>DIAGNOSIS</span>

            <strong>

              {diagnosis?.probableCause ??

                "UNDETERMINED"}

            </strong>

          </div>

          <div>

            <span>CONFIDENCE</span>

            <strong>

              {diagnosis?.confidence

                ? String(

                    diagnosis.confidence

                  ).toUpperCase()

                : "UNKNOWN"}

            </strong>

          </div>

          <div>

            <span>PATH STATUS</span>

            <strong>

              {pathStatusLabel}

            </strong>

          </div>

          <div>

            <span>HTTP STATUS</span>

            <strong>

              {httpStatusLabel}

            </strong>

          </div>

        </div>

        {comparison && (

          <div className="final-result-metrics">

            <FinalMetric

              label="RTT"

              previous={

                comparison.previous

                  .rtt

              }

              current={

                comparison.current

                  .rtt

              }

              difference={

                comparison.difference

                  .rtt

              }

              unit=" ms"

            />

            <FinalMetric

              label="PACKET LOSS"

              previous={

                comparison.previous

                  .packetLoss

              }

              current={

                comparison.current

                  .packetLoss

              }

              difference={

                comparison.difference

                  .packetLoss

              }

              unit="%"

            />

            <FinalMetric

              label="HTTP RESPONSE"

              previous={

                comparison.previous

                  .httpResponseTime

              }

              current={

                comparison.current

                  .httpResponseTime

              }

              difference={

                comparison.difference

                  .httpResponseTime

              }

              unit=" ms"

            />

          </div>

        )}

        <div className="final-result-evidence">

          <div className="diagnosis-subheading">

            STRONGEST EVIDENCE

          </div>

          {supportingEvidence.length ===

          0 ? (

            <div className="diagnosis-no-evidence">

              NO SUPPORTING EVIDENCE PROVIDED

            </div>

          ) : (

            <div className="diagnosis-evidence-list">

              {supportingEvidence.map(

                (

                  item,

                  index

                ) => (

                  <div

                    className="diagnosis-evidence-item"

                    key={

                      index

                    }

                  >

                    <span>✓</span>

                    <div>

                      {item}

                    </div>

                  </div>

                )

              )}

            </div>

          )}

        </div>

        <div className="final-result-actions">

          <button

            className="retest-button"

            onClick={

              onRetest

            }

          >

            RETEST TARGET

          </button>

          <button

            onClick={

              onNewInvestigation

            }

          >

            NEW INVESTIGATION

          </button>

        </div>

      </div>

    </section>

  );

}

function FinalMetric({

  label,

  previous,

  current,

  difference,

  unit,

}) {

  const percentage =

    previous !== 0

      ? Math.round(

          (difference /

            previous) *

            100

        )

      : 0;

  return (

    <div className="final-metric">

      <span>{label}</span>

      <div className="metric-values">

        <strong>

          {previous}

          {unit}

        </strong>

        <span>→</span>

        <strong className="current-value">

          {current}

          {unit}

        </strong>

      </div>

      {difference !== 0 && (

        <div className="metric-difference">

          {difference > 0

            ? "+"

            : ""}

          {difference}

          {unit}

          {percentage !==

            0 && (

            <span>

              {" "}

              (

              {percentage >

              0

                ? "+"

                : ""}

              {percentage}%)

            </span>

          )}

        </div>

      )}

    </div>

  );

}

/* =========================================================

   UTILITY

========================================================= */

function formatLabel(value) {

  return value

    .replaceAll(

      "_",

      " "

    )

    .replace(

      /([A-Z])/g,

      " $1"

    )

    .trim()

    .toUpperCase();

}

export default App;