import "./InvestigationDance.css";

function InvestigationDance({
  target,
  stage,
}) {
  const stages = [
    "starting",
    "dns",
    "http",
    "path_discovery",
    "path_analysis",
    "complete",
  ];

  const currentStageIndex = stages.indexOf(stage);

  const getStageLabel = () => {
    if (!stage) {
      return "INITIALIZING";
    }

    return stage
      .replaceAll("_", " ")
      .toUpperCase();
  };

  return (
    <main className="dance-investigation-screen">

      {/* =====================================================
          ROYAL PINK FLORAL ATMOSPHERE
      ====================================================== */}

      <div className="dance-floral-background" />
      <div className="dance-vignette" />

      {/* =====================================================
          TOP BLACK BOX HEADER
      ====================================================== */}

      <header className="dance-header">

        <div className="dance-brand">

          <div className="dance-system-label">
            BLACK BOX / INVESTIGATION
          </div>

          <div className="dance-target">
            {target}
          </div>

        </div>

        <div className="dance-running-status">

          <span className="dance-status-dot" />

          INVESTIGATION RUNNING

        </div>

      </header>

      {/* =====================================================
          MAIN MESSAGE
      ====================================================== */}

      <section className="dance-main">

        <div className="dance-message">

          <div className="dance-eyebrow">
            NETWORK DIAGNOSTIC SYSTEM
          </div>

          <h1>
            WHAT WENT WRONG,
            <br />
            BRO?
          </h1>

          <p>
            Don't worry.
            <br />
            We're investigating it.
          </p>

        </div>

        {/* =================================================
            DANCING CHARACTERS
        ================================================= */}

        <div className="dance-stage">

          <div className="dance-spotlight spotlight-left" />
          <div className="dance-spotlight spotlight-right" />

          {/* BATMAN */}
          <div className="dancer dancer-batman">

            <div className="batman-shadow" />

            <div className="batman-character">

              {/* Cape */}
              <div className="batman-cape" />

              {/* Head */}
              <div className="hero-head">

                <div className="hero-ears">
                  <span />
                  <span />
                </div>

                <div className="hero-mask">

                  <span className="hero-eye left" />
                  <span className="hero-eye right" />

                </div>

              </div>

              {/* Body */}
              <div className="hero-body">

                <div className="hero-chest-symbol">
                  B
                </div>

              </div>

              {/* Arms */}
              <div className="hero-arm hero-arm-left" />
              <div className="hero-arm hero-arm-right" />

              {/* Legs */}
              <div className="hero-leg hero-leg-left" />
              <div className="hero-leg hero-leg-right" />

            </div>

            <div className="dancer-name">
              BATMAN
            </div>

          </div>

          {/* CATWOMAN */}
          <div className="dancer dancer-catwoman">

            <div className="catwoman-shadow" />

            <div className="catwoman-character">

              {/* Head */}
              <div className="cat-head">

                <div className="cat-ears">
                  <span />
                  <span />
                </div>

                <div className="cat-mask">

                  <span className="cat-eye left" />
                  <span className="cat-eye right" />

                </div>

              </div>

              {/* Hair */}
              <div className="cat-hair" />

              {/* Body */}
              <div className="cat-body">

                <div className="cat-chest-symbol">
                  ♡
                </div>

              </div>

              {/* Arms */}
              <div className="cat-arm cat-arm-left" />
              <div className="cat-arm cat-arm-right" />

              {/* Legs */}
              <div className="cat-leg cat-leg-left" />
              <div className="cat-leg cat-leg-right" />

            </div>

            <div className="dancer-name">
              CATWOMAN
            </div>

          </div>

          {/* Little floor glow */}
          <div className="dance-floor" />

        </div>

        {/* =================================================
            DIALOGUE
        ================================================= */}

        <div className="dance-dialogue">

          <div className="speech-bubble batman-speech">
            <span>...</span>
            <strong>I've got this.</strong>
          </div>

          <div className="speech-bubble catwoman-speech">
            <span>♥</span>
            <strong>Let's dance.</strong>
          </div>

        </div>

      </section>

      {/* =====================================================
          CURRENT INVESTIGATION STATUS
      ====================================================== */}

      <section className="dance-status-panel">

        <div className="dance-status-heading">

          <span>01</span>

          <div>
            <h2>INVESTIGATION PIPELINE</h2>

            <p>
              The network is being investigated while
              the diagnostic engine works.
            </p>
          </div>

        </div>

        <div className="dance-current-stage">

          <div className="dance-current-stage-label">
            CURRENT STAGE
          </div>

          <div className="dance-current-stage-value">
            {getStageLabel()}
          </div>

        </div>

        {/* =================================================
            PIPELINE
        ================================================== */}

        <div className="dance-pipeline">

          {stages.map((item, index) => {

            let className =
              "dance-pipeline-stage";

            if (index < currentStageIndex) {
              className += " completed";
            }

            if (index === currentStageIndex) {
              className += " active";
            }

            if (
              stage === "complete" &&
              index === stages.length - 1
            ) {
              className += " active";
            }

            return (
              <div
                className={className}
                key={item}
              >

                <div className="dance-pipeline-node">

                  <div className="dance-pipeline-dot" />

                </div>

                <div className="dance-pipeline-name">
                  {item
                    .replaceAll("_", " ")
                    .toUpperCase()}
                </div>

              </div>
            );
          })}

        </div>

      </section>

    </main>
  );
}

export default InvestigationDance;