import { Canvas } from "@react-three/fiber";
import { OrbitControls, Html, Grid } from "@react-three/drei";
import { useMemo, useState } from "react";
import "./NetworkVisualisation.css";

function NetworkNode({
  hop,
  index,
  selected,
  onSelect,
  isDestination,
}) {
  const [hovered, setHovered] = useState(false);

  const isAnomalous =
    hop?.status === "anomalous" ||
    hop?.anomaly ||
    hop?.packetLoss > 5;

  const nodeColor = isDestination
    ? "#ffffff"
    : isAnomalous
    ? "#ff4f9a"
    : selected
    ? "#ffffff"
    : "#e9e3d8";

  const emissiveColor = isAnomalous
    ? "#ff2f8a"
    : selected
    ? "#ffffff"
    : "#777777";

  return (
    <group
      position={[
        index * 3.2 - 7.5,
        Math.sin(index * 0.8) * 0.35,
        Math.cos(index * 0.6) * 0.5,
      ]}
    >
      {/* Outer selection ring */}
      {selected && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.55, 0.045, 12, 48]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      )}

      {/* Anomaly ring */}
      {isAnomalous && !selected && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.58, 0.035, 12, 48]} />
          <meshBasicMaterial color="#ff4f9a" />
        </mesh>
      )}

      {/* Main node */}
      <mesh
        scale={hovered || selected ? 1.15 : 1}
        onClick={(event) => {
          event.stopPropagation();
          onSelect(hop);
        }}
        onPointerOver={(event) => {
          event.stopPropagation();
          setHovered(true);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHovered(false);
          document.body.style.cursor = "default";
        }}
      >
        <sphereGeometry
          args={[
            isDestination ? 0.48 : 0.4,
            32,
            32,
          ]}
        />

        <meshStandardMaterial
          color={nodeColor}
          emissive={emissiveColor}
          emissiveIntensity={
            selected || hovered || isAnomalous ? 0.35 : 0.08
          }
          roughness={0.35}
          metalness={0.2}
        />
      </mesh>

      {/* Node label */}
      <Html
        position={[0, -0.72, 0]}
        center
        distanceFactor={9}
        style={{
          pointerEvents: "none",
          userSelect: "none",
        }}
      >
        <div
          className={`network-node-label ${
            selected ? "selected" : ""
          } ${isAnomalous ? "anomalous" : ""}`}
        >
          <div className="network-node-hop">
            {isDestination ? "DESTINATION" : `HOP ${hop?.hop ?? index + 1}`}
          </div>

          {!isDestination && (
            <>
              <div className="network-node-ip">
                {hop?.ip ?? "UNKNOWN"}
              </div>

              <div className="network-node-meta">
                {hop?.rtt ?? "—"} ms · {hop?.packetLoss ?? 0}% LOSS
              </div>
            </>
          )}
        </div>
      </Html>

      {/* Anomaly badge */}
      {isAnomalous && (
        <Html
          position={[0, 0.8, 0]}
          center
          distanceFactor={9}
          style={{
            pointerEvents: "none",
            userSelect: "none",
          }}
        >
          <div className="network-anomaly-badge">
            ANOMALY
          </div>
        </Html>
      )}
    </group>
  );
}

function NetworkConnection({
  start,
  end,
  highlighted,
  anomalous,
}) {
  const points = useMemo(() => {
    return [
      start,
      [
        (start[0] + end[0]) / 2,
        (start[1] + end[1]) / 2 + 0.15,
        (start[2] + end[2]) / 2,
      ],
      end,
    ];
  }, [start, end]);

  return (
    <line>
      <bufferGeometry
        attach="geometry"
        onUpdate={(geometry) => {
          geometry.setFromPoints(
            points.map(
              (point) =>
                ({
                  x: point[0],
                  y: point[1],
                  z: point[2],
                })
            )
          );
        }}
      />

      <lineBasicMaterial
        color={
          anomalous
            ? "#ff4f9a"
            : highlighted
            ? "#ffffff"
            : "#8a8290"
        }
        transparent
        opacity={
          anomalous
            ? 0.9
            : highlighted
            ? 0.95
            : 0.45
        }
        linewidth={2}
      />
    </line>
  );
}

function NetworkScene({
  path,
  selectedHop,
  onSelectHop,
}) {
  const positions = useMemo(() => {
    return path.map((_, index) => [
      index * 3.2 - 7.5,
      Math.sin(index * 0.8) * 0.35,
      Math.cos(index * 0.6) * 0.5,
    ]);
  }, [path]);

  return (
    <>
      <ambientLight intensity={1.4} />

      <directionalLight
        position={[5, 8, 5]}
        intensity={2}
      />

      <pointLight
        position={[-5, 3, 4]}
        intensity={1.2}
      />

      <Grid
        position={[0, -1.1, 0]}
        args={[30, 30]}
        cellSize={1}
        cellThickness={0.45}
        cellColor="#34303a"
        sectionSize={5}
        sectionThickness={0.8}
        sectionColor="#4b4652"
        fadeDistance={22}
        fadeStrength={1}
      />

      {/* Connections */}
      {path.map((hop, index) => {
        if (index >= path.length - 1) {
          return null;
        }

        const nextHop = path[index + 1];

        const currentSelected =
          selectedHop?.ip === hop?.ip;

        const nextSelected =
          selectedHop?.ip === nextHop?.ip;

        const anomalous =
          hop?.status === "anomalous" ||
          hop?.anomaly ||
          hop?.packetLoss > 5 ||
          nextHop?.status === "anomalous" ||
          nextHop?.anomaly ||
          nextHop?.packetLoss > 5;

        return (
          <NetworkConnection
            key={`connection-${index}`}
            start={positions[index]}
            end={positions[index + 1]}
            highlighted={
              currentSelected || nextSelected
            }
            anomalous={anomalous}
          />
        );
      })}

      {/* Nodes */}
      {path.map((hop, index) => (
        <NetworkNode
          key={`${hop?.ip ?? "hop"}-${index}`}
          hop={hop}
          index={index}
          selected={
            selectedHop?.ip === hop?.ip
          }
          onSelect={onSelectHop}
          isDestination={index === path.length - 1}
        />
      ))}

      <OrbitControls
        enablePan={false}
        minDistance={5}
        maxDistance={20}
        minPolarAngle={Math.PI / 4}
        maxPolarAngle={Math.PI / 1.8}
        dampingFactor={0.08}
        enableDamping
      />
    </>
  );
}

export default function NetworkVisualisation({
  path = [],
  selectedHop,
  onSelectHop,
}) {
  if (!path || path.length === 0) {
    return (
      <div className="network-visualisation-empty">
        <div className="network-empty-title">
          NETWORK PATH UNAVAILABLE
        </div>

        <div className="network-empty-description">
          No network path data was returned for this investigation.
        </div>
      </div>
    );
  }

  return (
    <div className="network-visualisation">
      <div className="network-visualisation-header">
        <div>
          <div className="network-eyebrow">
            BLACK BOX / LIVE TOPOLOGY
          </div>

          <h3>LIVE NETWORK PATH</h3>

          <p>
            CLICK A NODE TO INSPECT THE NETWORK HOP
          </p>
        </div>

        <div className="network-legend">
          <div className="legend-item">
            <span className="legend-dot normal" />
            NETWORK NODE
          </div>

          <div className="legend-item">
            <span className="legend-dot anomaly" />
            ANOMALY
          </div>

          <div className="legend-item">
            <span className="legend-dot traffic" />
            TRAFFIC
          </div>
        </div>
      </div>

      <div className="network-canvas">
        <Canvas
          camera={{
            position: [0, 4.5, 14],
            fov: 45,
          }}
          dpr={[1, 2]}
        >
          <color
            attach="background"
            args={["#09080c"]}
          />

          <NetworkScene
            path={path}
            selectedHop={selectedHop}
            onSelectHop={onSelectHop}
          />
        </Canvas>

        <div className="network-controls">
          <span>DRAG TO ROTATE</span>
          <span>SCROLL TO ZOOM</span>
          <span>CLICK A NODE TO INSPECT</span>
        </div>
      </div>
    </div>
  );
}