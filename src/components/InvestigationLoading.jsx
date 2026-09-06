import { useEffect, useRef, useState } from "react";
import "./InvestigationLoading.css";

function InvestigationLoading({
  target,
  stage,
}) {
  const sceneRef = useRef(null);

  const [mouse, setMouse] = useState({
    x: 0,
    y: 0,
  });

  useEffect(() => {
    const handleMouseMove = (event) => {
      const x =
        (event.clientX / window.innerWidth - 0.5) * 2;

      const y =
        (event.clientY / window.innerHeight - 0.5) * 2;

      setMouse({
        x,
        y,
      });
    };

    window.addEventListener(
      "mousemove",
      handleMouseMove
    );

    return () => {
      window.removeEventListener(
        "mousemove",
        handleMouseMove
      );
    };
  }, []);

  const currentStage =
    stage
      ? stage
          .replaceAll("_", " ")
          .toUpperCase()
      : "INITIALIZING";

  const stageIndex = [
    "starting",
    "dns",
    "http",
    "path_discovery",
    "path_analysis",
    "complete",
  ].indexOf(stage);

  const stages = [
    "STARTING",
    "DNS",
    "HTTP",
    "PATH DISCOVERY",
    "PATH ANALYSIS",
    "COMPLETE",
  ];

  return (
    <main
      className="investigation-loading"
      ref={sceneRef}
    >

      {/* =================================================
          BACKGROUND
      ================================================= */}

      <div className="loading-background">

        <div
          className="background-glow glow-one"
          style={{
            transform: `
              translate(
                ${mouse.x * 25}px,
                ${mouse.y * 20}px
              )
            `,
          }}
        />

        <div
          className="background-glow glow-two"
          style={{
            transform: `
              translate(
                ${mouse.x * -35}px,
                ${mouse.y * -25}px
              )
            `,
          }}
        />

        <div
          className="background-grid"
          style={{
            transform: `
              perspective(700px)
              rotateX(58deg)
              translate(
                ${mouse.x * 8}px,
                ${mouse.y * 5}px
              )
            `,
          }}
        />

        <div className="floral-pattern">
          {Array.from({
            length: 28,
          }).map((_, index) => (
            <span
              key={index}
              className="floral-swirl"
              style={{
                "--i": index,
              }}
            />
          ))}
        </div>

        <div className="floating-particles">
          {Array.from({
            length: 42,
          }).map((_, index) => (
            <span
              key={index}
              className="particle"
              style={{
                "--i": index,
              }}
            />
          ))}
        </div>

        <div className="moving-light" />

        <div className="background-vignette" />

      </div>

      {/* =================================================
          HEADER
      ================================================= */}

      <header className="loading-header">

        <div>

          <div className="loading-system-label">
            BLACK BOX / INVESTIGATION
          </div>

          <div className="loading-target">
            {target}
          </div>

        </div>

        <div className="loading-status">

          <span className="status-dot" />

          INVESTIGATION RUNNING

        </div>

      </header>

      {/* =================================================
          CENTRAL SCENE
      ================================================= */}

      <section className="dance-scene">

        <div
          className="scene-title"
          style={{
            transform: `
              translate(
                ${mouse.x * 5}px,
                ${mouse.y * 3}px
              )
            `,
          }}
        >

          <div className="scene-eyebrow">
            NETWORK INVESTIGATION
          </div>

          <h1>
            WHAT WENT WRONG,
            <br />
            BRO?
          </h1>

          <p>
            LET'S FIND OUT.
          </p>

        </div>

        {/* =================================================
            HERO CHARACTERS
        ================================================= */}

        <div
          className="mascot-stage"
          style={{
            transform: `
              translate(
                ${mouse.x * 12}px,
                ${mouse.y * 8}px
              )
            `,
          }}
        >

          {/* HERO */}

          <div className="mascot hero-mascot">

            <div className="shadow hero-shadow" />

            <div className="character-body">

              <div className="cape" />

              <div className="head">

                <div className="ears">
                  <span />
                  <span />
                </div>

                <div className="mask">

                  <div className="eye left-eye" />
                  <div className="eye right-eye" />

                </div>

                <div className="face" />

              </div>

              <div className="neck" />

              <div className="torso">

                <div className="emblem">
                  B
                </div>

              </div>

              <div className="arm left-arm" />
              <div className="arm right-arm" />

              <div className="leg left-leg" />
              <div className="leg right-leg" />

            </div>

          </div>

          {/* CAT-LIKE PARTNER */}

          <div className="mascot cat-mascot">

            <div className="shadow cat-shadow" />

            <div className="character-body">

              <div className="cat-cape" />

              <div className="head">

                <div className="cat-ears">
                  <span />
                  <span />
                </div>

                <div className="cat-mask">

                  <div className="eye left-eye" />
                  <div className="eye right-eye" />

                </div>

                <div className="face" />

              </div>

              <div className="neck" />

              <div className="torso">

                <div className="cat-emblem">
                  ♡
                </div>

              </div>

              <div className="arm left-arm" />
              <div className="arm right-arm" />

              <div className="leg left-leg" />
              <div className="leg right-leg" />

              <div className="tail" />

            </div>

          </div>

          {/* HEART / SPARKLE EFFECTS */}

          <div className="dance-spark spark-one">
            ✦
          </div>

          <div className="dance-spark spark-two">
            ✧
          </div>

          <div className="dance-spark spark-three">
            ♡
          </div>

        </div>

        {/* =================================================
            CURRENT OPERATION
        ================================================= */}

        <div className="operation-panel">

          <div className="operation-label">
            CURRENT OPERATION
          </div>

          <div className="operation-main">
            {currentStage}
          </div>

          <div className="operation-sub">
            ANALYZING {target}
          </div>

          <div className="operation-loader">
            <span />
            <span />
            <span />
          </div>

        </div>

      </section>

      {/* =================================================
          INVESTIGATION PIPELINE
      ================================================= */}

      <section className="loading-pipeline">

        <div className="pipeline-heading">

          <span>01</span>

          <strong>
            INVESTIGATION PIPELINE
          </strong>

        </div>

        <div className="pipeline-track">

          {stages.map((item, index) => {

            let className =
              "loading-pipeline-stage";

            if (
              stageIndex >= 0 &&
              index < stageIndex
            ) {
              className += " completed";
            }

            if (index === stageIndex) {
              className += " active";
            }

            return (
              <div
                className={className}
                key={item}
              >

                <div className="loading-pipeline-dot" />

                <div className="loading-pipeline-name">
                  {item}
                </div>

              </div>
            );
          })}

        </div>

      </section>

      <div className="loading-footer">
        BLACK BOX SYSTEM // INVESTIGATION IN PROGRESS
      </div>

    </main>
  );
}

export default InvestigationLoading;