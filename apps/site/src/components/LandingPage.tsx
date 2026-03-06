import Typewriter from './Typewriter';
import TerrainCanvas from './TerrainCanvas';

export default function LandingPage() {
  return (
    <div className="landing">
      <div className="content-panel">
        <div className="content-inner">
          <img src="/forum_logo.svg" alt="Forum" className="nav-logo" />

          <h1 className="headline">
            Web data for
            <br />
            <Typewriter />
          </h1>

          <p className="subtitle">
            Plug in a URL, describe what you need. Our agents build self-healing
            pipelines that deliver structured, validated data on your schedule
            — no engineers required.
          </p>

          <a
            href="https://cal.com/team/forum/intro-call"
            target="_blank"
            rel="noopener noreferrer"
            className="cta-button"
          >
            TALK TO FOUNDERS →
          </a>

          <div className="social-proof">
            <div className="proof-section">
              <span className="proof-label">Backed by</span>
              <div className="proof-logos">
                <img
                  src="/afore_vc.png"
                  alt="Afore Capital"
                  className="proof-logo"
                />
              </div>
            </div>
            <div className="proof-section">
              <span className="proof-label">Team from</span>
              <div className="proof-logos">
                <img
                  src="/point72.png"
                  alt="Point72"
                  className="proof-logo invert"
                />
                <img
                  src="/double_black_capital.png"
                  alt="Double Black Capital"
                  className="proof-logo invert"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="terrain-panel">
        <TerrainCanvas />
      </div>
    </div>
  );
}
