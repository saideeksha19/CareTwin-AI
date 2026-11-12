"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import {
  Maximize2,
  Minus,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { cn } from "@caretwin/shared";

type TwinStatus = "on_track" | "needs_attention" | "urgent_review";

export type SystemKey = "overview" | "skeleton" | "organs" | "vascular";

const SYSTEMS: Array<{ key: SystemKey; label: string }> = [
  { key: "overview", label: "Overview" },
  { key: "skeleton", label: "Skeleton" },
  { key: "organs", label: "Organs" },
  { key: "vascular", label: "Circulation" },
];

const STATUS_TINT: Record<TwinStatus, number> = {
  on_track: 0x4ee0f2,
  needs_attention: 0xfbbf24,
  urgent_review: 0xfb7185,
};

/* ------------------------------------------------------------------ helpers */

function capsuleBetween(
  a: THREE.Vector3,
  b: THREE.Vector3,
  radius: number,
  material: THREE.Material,
) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const length = Math.max(dir.length() - radius * 1.2, 0.05);
  const geometry = new THREE.CapsuleGeometry(radius, length, 4, 14);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.copy(a).add(b).multiplyScalar(0.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
  return mesh;
}

function softDotTexture() {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    gradient.addColorStop(0, "rgba(180,245,255,1)");
    gradient.addColorStop(0.35, "rgba(90,220,255,0.65)");
    gradient.addColorStop(1, "rgba(40,160,220,0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/* ---------------------------------------------------------------- the scene */

type TwinHandles = {
  dispose: () => void;
  setPlaying: (playing: boolean) => void;
  reset: () => void;
  zoom: (delta: number) => void;
  setSystem: (system: SystemKey) => void;
  isPlaying: () => boolean;
};

function buildScene(
  container: HTMLDivElement,
  options: { status: TwinStatus; reducedMotion: boolean; onReady?: () => void },
): TwinHandles {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.appendChild(renderer.domElement);
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.height = "100%";
  renderer.domElement.style.display = "block";
  renderer.domElement.style.cursor = "grab";
  renderer.domElement.style.touchAction = "none";

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x030b18, 0.035);

  const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 100);
  const HOME = new THREE.Vector3(0, 0.35, 11.2);
  camera.position.copy(HOME);

  const disposables: Array<{ dispose: () => void }> = [];
  const track = <T extends { dispose: () => void }>(item: T) => {
    disposables.push(item);
    return item;
  };

  /* ------------------------------------------------------------- lighting */
  const ambient = new THREE.AmbientLight(0x4a6b93, 1.1);
  scene.add(ambient);

  const keyLight = new THREE.DirectionalLight(0xbfe9ff, 1.9);
  keyLight.position.set(4, 6, 6);
  scene.add(keyLight);

  const rimLight = new THREE.DirectionalLight(0x8b5cf6, 1.3);
  rimLight.position.set(-6, 2, -4);
  scene.add(rimLight);

  const underLight = new THREE.PointLight(0x22d3ee, 14, 12, 2);
  underLight.position.set(0, -2.6, 1.2);
  scene.add(underLight);

  const tint = STATUS_TINT[options.status];
  const accentLight = new THREE.PointLight(tint, 6, 9, 2);
  accentLight.position.set(0, 1.2, 3);
  scene.add(accentLight);

  /* ---------------------------------------------------------------- stage */
  const root = new THREE.Group();
  scene.add(root);

  const platform = new THREE.Group();
  platform.position.y = -3.05;
  root.add(platform);

  const glowTexture = track(softDotTexture());

  const core = new THREE.Mesh(
    track(new THREE.CircleGeometry(1.55, 64)),
    track(
      new THREE.MeshBasicMaterial({
        color: 0x2ad4f0,
        transparent: true,
        opacity: 0.12,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    ),
  );
  core.rotation.x = -Math.PI / 2;
  platform.add(core);

  const innerRing = new THREE.Mesh(
    track(new THREE.RingGeometry(0.62, 0.72, 96)),
    track(
      new THREE.MeshBasicMaterial({
        color: 0x67e8f9,
        transparent: true,
        opacity: 0.5,
        side: THREE.DoubleSide,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    ),
  );
  innerRing.rotation.x = -Math.PI / 2;
  platform.add(innerRing);

  const outerRings: THREE.Mesh[] = [];
  [
    [1.5, 1.56, 0.38],
    [1.86, 1.9, 0.22],
    [2.22, 2.25, 0.12],
  ].forEach(([inner, outer, opacity], index) => {
    const ring = new THREE.Mesh(
      track(new THREE.RingGeometry(inner, outer, 128)),
      track(
        new THREE.MeshBasicMaterial({
          color: index === 2 ? 0x8b5cf6 : 0x4ee0f2,
          transparent: true,
          opacity,
          side: THREE.DoubleSide,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
        }),
      ),
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.002 * index;
    platform.add(ring);
    outerRings.push(ring);
  });

  // tick marks
  const ticks = new THREE.Group();
  const tickGeo = track(new THREE.PlaneGeometry(0.02, 0.16));
  for (let i = 0; i < 72; i += 1) {
    const angle = (i / 72) * Math.PI * 2;
    const tick = new THREE.Mesh(
      tickGeo,
      track(
        new THREE.MeshBasicMaterial({
          color: i % 6 === 0 ? 0x9df3ff : 0x2e7f9c,
          transparent: true,
          opacity: i % 6 === 0 ? 0.65 : 0.28,
          depthWrite: false,
          blending: THREE.AdditiveBlending,
        }),
      ),
    );
    tick.position.set(Math.cos(angle) * 1.7, 0, Math.sin(angle) * 1.7);
    tick.rotation.x = -Math.PI / 2;
    tick.rotation.z = -angle;
    ticks.add(tick);
  }
  platform.add(ticks);

  const halo = new THREE.Sprite(
    track(
      new THREE.SpriteMaterial({
        map: glowTexture,
        color: 0x2ad4f0,
        transparent: true,
        opacity: 0.5,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    ),
  );
  halo.scale.set(4.6, 4.6, 1);
  halo.position.y = -3.05;
  root.add(halo);

  /* ------------------------------------------------------------ body group */
  const body = new THREE.Group();
  root.add(body);

  const skin = track(
    new THREE.MeshPhysicalMaterial({
      color: 0x8fe9ff,
      transparent: true,
      opacity: 0.15,
      roughness: 0.18,
      metalness: 0.05,
      clearcoat: 1,
      clearcoatRoughness: 0.15,
      side: THREE.DoubleSide,
      depthWrite: false,
    }),
  );

  const skinWire = track(
    new THREE.MeshBasicMaterial({
      color: 0x7fe6ff,
      wireframe: true,
      transparent: true,
      opacity: 0.055,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );

  const boneMaterial = track(
    new THREE.MeshBasicMaterial({
      color: 0x9befff,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );

  const skinGroup = new THREE.Group();
  const boneGroup = new THREE.Group();
  const organGroup = new THREE.Group();
  const vesselGroup = new THREE.Group();
  body.add(skinGroup, boneGroup, organGroup, vesselGroup);

  function part(geometry: THREE.BufferGeometry, material: THREE.Material, group: THREE.Group) {
    const mesh = new THREE.Mesh(track(geometry), material);
    group.add(mesh);
    // faint wireframe shell for the holographic gridding
    if (group === skinGroup) {
      const wire = new THREE.Mesh(geometry, skinWire);
      mesh.add(wire);
    }
    return mesh;
  }

  // torso from a lathe silhouette
  const torsoProfile = [
    [0.34, -1.02],
    [0.46, -0.86],
    [0.5, -0.62],
    [0.45, -0.28],
    [0.47, 0.06],
    [0.55, 0.5],
    [0.62, 0.95],
    [0.63, 1.24],
    [0.52, 1.5],
    [0.3, 1.6],
  ].map(([radius, y]) => new THREE.Vector2(radius, y));
  part(new THREE.LatheGeometry(torsoProfile, 48), skin, skinGroup);

  // hips
  const hips = part(
    new THREE.SphereGeometry(0.44, 28, 20),
    skin,
    skinGroup,
  );
  hips.position.set(0, -0.95, 0);
  hips.scale.set(1.12, 0.8, 0.86);

  // neck + head
  const neck = part(new THREE.CylinderGeometry(0.14, 0.18, 0.26, 20), skin, skinGroup);
  neck.position.set(0, 1.72, 0);
  const head = part(new THREE.SphereGeometry(0.38, 32, 24), skin, skinGroup);
  head.position.set(0, 2.16, 0.01);
  head.scale.set(0.86, 1.08, 0.94);
  const jaw = part(new THREE.SphereGeometry(0.26, 24, 18), skin, skinGroup);
  jaw.position.set(0, 1.98, 0.06);
  jaw.scale.set(0.82, 0.66, 0.82);

  // shoulders + arms
  const shoulderY = 1.42;
  [-1, 1].forEach((side) => {
    const shoulder = part(new THREE.SphereGeometry(0.21, 20, 16), skin, skinGroup);
    shoulder.position.set(side * 0.6, shoulderY, 0);
    shoulder.scale.set(1.1, 0.9, 0.95);

    skinGroup.add(
      capsuleBetween(
        new THREE.Vector3(side * 0.62, shoulderY - 0.12, 0),
        new THREE.Vector3(side * 0.82, 0.28, 0.04),
        0.115,
        skin,
      ),
    );
    skinGroup.add(
      capsuleBetween(
        new THREE.Vector3(side * 0.82, 0.28, 0.04),
        new THREE.Vector3(side * 0.94, -0.72, 0.12),
        0.09,
        skin,
      ),
    );
    const hand = part(new THREE.SphereGeometry(0.11, 16, 12), skin, skinGroup);
    hand.position.set(side * 0.97, -0.86, 0.13);
    hand.scale.set(0.8, 1.3, 0.6);

    // legs
    skinGroup.add(
      capsuleBetween(
        new THREE.Vector3(side * 0.23, -1.0, 0),
        new THREE.Vector3(side * 0.3, -2.0, 0.02),
        0.16,
        skin,
      ),
    );
    skinGroup.add(
      capsuleBetween(
        new THREE.Vector3(side * 0.3, -2.0, 0.02),
        new THREE.Vector3(side * 0.31, -2.87, 0.02),
        0.115,
        skin,
      ),
    );
    const foot = part(new THREE.SphereGeometry(0.13, 16, 12), skin, skinGroup);
    foot.position.set(side * 0.31, -2.94, 0.12);
    foot.scale.set(0.85, 0.42, 1.6);

    // clavicle
    boneGroup.add(
      capsuleBetween(
        new THREE.Vector3(side * 0.04, 1.5, 0.16),
        new THREE.Vector3(side * 0.56, 1.44, 0.05),
        0.018,
        boneMaterial,
      ),
    );
    // arm bones
    boneGroup.add(
      capsuleBetween(
        new THREE.Vector3(side * 0.6, shoulderY - 0.06, 0),
        new THREE.Vector3(side * 0.8, 0.3, 0.04),
        0.022,
        boneMaterial,
      ),
    );
    boneGroup.add(
      capsuleBetween(
        new THREE.Vector3(side * 0.8, 0.3, 0.04),
        new THREE.Vector3(side * 0.92, -0.7, 0.12),
        0.019,
        boneMaterial,
      ),
    );
    // leg bones
    boneGroup.add(
      capsuleBetween(
        new THREE.Vector3(side * 0.22, -1.02, 0),
        new THREE.Vector3(side * 0.29, -1.98, 0.02),
        0.028,
        boneMaterial,
      ),
    );
    boneGroup.add(
      capsuleBetween(
        new THREE.Vector3(side * 0.29, -2.0, 0.02),
        new THREE.Vector3(side * 0.31, -2.88, 0.04),
        0.022,
        boneMaterial,
      ),
    );
  });

  // spine
  for (let i = 0; i < 9; i += 1) {
    const y = -0.9 + i * 0.24;
    const disc = new THREE.Mesh(track(new THREE.CylinderGeometry(0.055, 0.055, 0.12, 10)), boneMaterial);
    disc.position.set(0, y, -0.06 + Math.sin(i / 8) * 0.02);
    boneGroup.add(disc);
  }

  // ribs
  for (let i = 0; i < 7; i += 1) {
    const y = 1.32 - i * 0.18;
    const width = 0.3 + Math.sin((i / 6) * Math.PI) * 0.12;
    [-1, 1].forEach((side) => {
      const curve = new THREE.CatmullRomCurve3([
        new THREE.Vector3(side * 0.02, y, -0.08),
        new THREE.Vector3(side * width * 0.85, y - 0.03, 0.02),
        new THREE.Vector3(side * width, y - 0.1, 0.2),
        new THREE.Vector3(side * 0.05, y - 0.16, 0.3),
      ]);
      const rib = new THREE.Mesh(
        track(new THREE.TubeGeometry(curve, 16, 0.012, 4, false)),
        boneMaterial,
      );
      boneGroup.add(rib);
    });
  }
  const sternum = new THREE.Mesh(track(new THREE.BoxGeometry(0.05, 0.6, 0.02)), boneMaterial);
  sternum.position.set(0, 1.05, 0.3);
  boneGroup.add(sternum);

  // pelvis ring
  const pelvisRing = new THREE.Mesh(track(new THREE.TorusGeometry(0.3, 0.022, 6, 40)), boneMaterial);
  pelvisRing.position.set(0, -1.0, 0);
  pelvisRing.rotation.x = Math.PI / 2;
  pelvisRing.scale.set(1.2, 0.9, 1);
  boneGroup.add(pelvisRing);

  // skull shell
  const skull = new THREE.Mesh(
    track(new THREE.SphereGeometry(0.37, 20, 14)),
    track(
      new THREE.MeshBasicMaterial({
        color: 0x9befff,
        wireframe: true,
        transparent: true,
        opacity: 0.22,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    ),
  );
  skull.position.set(0, 2.16, 0);
  skull.scale.set(0.86, 1.06, 0.92);
  boneGroup.add(skull);

  /* --------------------------------------------------------------- organs */
  const organ = (
    geometry: THREE.BufferGeometry,
    color: number,
    opacity: number,
    position: [number, number, number],
    scale: [number, number, number] = [1, 1, 1],
  ) => {
    const material = track(
      new THREE.MeshStandardMaterial({
        color,
        emissive: new THREE.Color(color).multiplyScalar(0.55),
        emissiveIntensity: 0.85,
        transparent: true,
        opacity,
        roughness: 0.42,
        metalness: 0.05,
        depthWrite: false,
      }),
    );
    const mesh = new THREE.Mesh(track(geometry), material);
    mesh.position.set(...position);
    mesh.scale.set(...scale);
    organGroup.add(mesh);
    return mesh;
  };

  // brain
  const brain = organ(new THREE.SphereGeometry(0.26, 24, 18), 0xc4b5fd, 0.5, [0, 2.26, 0.0], [1, 0.92, 1.06]);
  // lungs
  organ(new THREE.SphereGeometry(0.2, 20, 16), 0x5ad2ea, 0.34, [-0.22, 1.02, 0.02], [0.78, 1.5, 0.72]);
  organ(new THREE.SphereGeometry(0.2, 20, 16), 0x5ad2ea, 0.34, [0.22, 1.02, 0.02], [0.78, 1.5, 0.72]);
  // heart
  const heart = organ(new THREE.SphereGeometry(0.15, 20, 16), 0xff6b81, 0.65, [-0.03, 1.0, 0.13], [0.95, 1.1, 0.9]);
  const heartCone = new THREE.Mesh(
    track(new THREE.ConeGeometry(0.13, 0.24, 16)),
    heart.material as THREE.Material,
  );
  heartCone.position.set(-0.03, 0.84, 0.13);
  heartCone.rotation.z = Math.PI;
  organGroup.add(heartCone);
  // liver
  organ(new THREE.SphereGeometry(0.18, 18, 14), 0xf0a868, 0.42, [0.12, 0.44, 0.08], [1.5, 0.66, 0.9]);
  // stomach
  organ(new THREE.SphereGeometry(0.14, 18, 14), 0xa78bfa, 0.42, [-0.16, 0.42, 0.06], [0.95, 1.2, 0.8]);
  // kidneys
  organ(new THREE.SphereGeometry(0.1, 16, 12), 0xf472b6, 0.4, [-0.22, 0.1, -0.16], [0.85, 1.3, 0.7]);
  organ(new THREE.SphereGeometry(0.1, 16, 12), 0xf472b6, 0.4, [0.22, 0.1, -0.16], [0.85, 1.3, 0.7]);
  // intestines
  const intestines = organ(new THREE.TorusKnotGeometry(0.16, 0.05, 60, 6, 2, 3), 0x7dd3fc, 0.34, [0, -0.14, 0.06], [1.25, 0.85, 0.7]);
  intestines.rotation.x = Math.PI / 2;

  /* ------------------------------------------------------------ circulation */
  const vesselMaterial = track(
    new THREE.MeshBasicMaterial({
      color: 0xff5d7a,
      transparent: true,
      opacity: 0.34,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  const veinMaterial = track(
    new THREE.MeshBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.34,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  const vesselCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 1.0, 0.14),
    new THREE.Vector3(0.16, 0.9, 0.2),
    new THREE.Vector3(0.2, 0.3, 0.12),
    new THREE.Vector3(0.28, -0.6, 0.06),
    new THREE.Vector3(0.31, -1.6, 0.04),
    new THREE.Vector3(0.31, -2.7, 0.04),
  ]);
  vesselGroup.add(new THREE.Mesh(track(new THREE.TubeGeometry(vesselCurve, 60, 0.014, 5, false)), vesselMaterial));
  const veinCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 0.94, 0.04),
    new THREE.Vector3(-0.16, 0.86, 0.02),
    new THREE.Vector3(-0.22, 0.26, 0.08),
    new THREE.Vector3(-0.28, -0.6, 0.1),
    new THREE.Vector3(-0.31, -1.6, 0.08),
    new THREE.Vector3(-0.31, -2.7, 0.08),
  ]);
  vesselGroup.add(new THREE.Mesh(track(new THREE.TubeGeometry(veinCurve, 60, 0.014, 5, false)), veinMaterial));
  vesselGroup.add(
    capsuleBetween(new THREE.Vector3(0.02, 1.0, 0.18), new THREE.Vector3(0.5, 1.36, 0.12), 0.012, vesselMaterial),
  );
  vesselGroup.add(
    capsuleBetween(new THREE.Vector3(-0.02, 1.0, 0.14), new THREE.Vector3(-0.5, 1.32, 0.1), 0.012, veinMaterial),
  );
  vesselGroup.visible = false;

  /* ---------------------------------------------------------- data particles */
  const particleCount = 320;
  const positions = new Float32Array(particleCount * 3);
  const seeds = new Float32Array(particleCount);
  for (let i = 0; i < particleCount; i += 1) {
    const angle = Math.random() * Math.PI * 2;
    const radius = 1.2 + Math.random() * 2.4;
    positions[i * 3] = Math.cos(angle) * radius;
    positions[i * 3 + 1] = -3 + Math.random() * 6.4;
    positions[i * 3 + 2] = Math.sin(angle) * radius;
    seeds[i] = Math.random() * Math.PI * 2;
  }
  const particleGeometry = track(new THREE.BufferGeometry());
  particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const particleMaterial = track(
    new THREE.PointsMaterial({
      map: glowTexture,
      color: 0x7fe6ff,
      size: 0.07,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    }),
  );
  const particles = new THREE.Points(particleGeometry, particleMaterial);
  root.add(particles);

  /* ------------------------------------------------------------- scan ring */
  const scanRing = new THREE.Mesh(
    track(new THREE.TorusGeometry(0.62, 0.006, 6, 64)),
    track(
      new THREE.MeshBasicMaterial({
        color: 0xbaf7ff,
        transparent: true,
        opacity: 0.5,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      }),
    ),
  );
  scanRing.rotation.x = Math.PI / 2;
  root.add(scanRing);

  /* -------------------------------------------------------------- controls */
  let rotY = 0;
  let targetRotY = 0;
  let tilt = 0;
  let targetTilt = 0;
  let zoomTarget = HOME.z;
  let playing = !options.reducedMotion;
  let dragging = false;
  let pointerId: number | null = null;
  let lastX = 0;
  let lastY = 0;
  let lastInteraction = 0;
  let autoAngle = 0;
  let visible = true;
  let raf = 0;
  let elapsed = 0;
  let lastFrame = performance.now();

  const setSystem = (system: SystemKey) => {
    skinGroup.visible = true;
    boneGroup.visible = system !== "organs";
    organGroup.visible = system !== "skeleton";
    vesselGroup.visible = system === "vascular";
    skin.opacity = system === "organs" ? 0.07 : 0.15;
  };

  const onPointerDown = (event: PointerEvent) => {
    dragging = true;
    pointerId = event.pointerId;
    lastX = event.clientX;
    lastY = event.clientY;
    renderer.domElement.style.cursor = "grabbing";
    renderer.domElement.setPointerCapture?.(event.pointerId);
    lastInteraction = elapsed;
  };
  const onPointerMove = (event: PointerEvent) => {
    if (!dragging) return;
    const dx = event.clientX - lastX;
    const dy = event.clientY - lastY;
    lastX = event.clientX;
    lastY = event.clientY;
    targetRotY += dx * 0.008;
    targetTilt = THREE.MathUtils.clamp(targetTilt + dy * 0.004, -0.35, 0.35);
    lastInteraction = elapsed;
  };
  const onPointerUp = (event: PointerEvent) => {
    dragging = false;
    renderer.domElement.style.cursor = "grab";
    if (pointerId !== null) {
      try {
        renderer.domElement.releasePointerCapture?.(pointerId);
      } catch {
        /* pointer already released */
      }
    }
    pointerId = null;
    lastInteraction = elapsed;
  };
  const onWheel = (event: WheelEvent) => {
    event.preventDefault();
    zoomTarget = THREE.MathUtils.clamp(zoomTarget + event.deltaY * 0.006, 6.8, 15.5);
  };
  const onDoubleClick = () => {
    targetRotY = 0;
    targetTilt = 0;
    zoomTarget = HOME.z;
  };

  renderer.domElement.addEventListener("pointerdown", onPointerDown);
  renderer.domElement.addEventListener("pointermove", onPointerMove);
  renderer.domElement.addEventListener("pointerup", onPointerUp);
  renderer.domElement.addEventListener("pointercancel", onPointerUp);
  renderer.domElement.addEventListener("wheel", onWheel, { passive: false });
  renderer.domElement.addEventListener("dblclick", onDoubleClick);

  /* ---------------------------------------------------------------- resize */
  const resize = () => {
    const width = container.clientWidth || 1;
    const height = container.clientHeight || 1;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };
  const observer = new ResizeObserver(resize);
  observer.observe(container);
  resize();

  const onVisibility = () => {
    lastFrame = performance.now();
    if (!document.hidden) resize();
  };
  document.addEventListener("visibilitychange", onVisibility);

  const intersection = new IntersectionObserver(
    (entries) => {
      visible = entries.some((entry) => entry.isIntersecting);
      lastFrame = performance.now();
    },
    { threshold: 0.05 },
  );
  intersection.observe(container);

  /* ------------------------------------------------------------------ loop */
  const render = () => {
    const now = performance.now();
    const dt = Math.min((now - lastFrame) / 1000, 0.05);
    lastFrame = now;
    if (document.hidden || !visible) {
      raf = requestAnimationFrame(render);
      return;
    }

    elapsed += dt;

    if (playing && !dragging && elapsed - lastInteraction > 0.4) {
      autoAngle += dt * 0.22;
    }

    rotY += (targetRotY - rotY) * Math.min(1, dt * 6);
    tilt += (targetTilt - tilt) * Math.min(1, dt * 6);
    body.rotation.y = rotY + autoAngle;
    body.rotation.x = tilt * 0.4;
    body.position.y = Math.sin(elapsed * 0.55) * 0.035;

    particles.rotation.y = -elapsed * 0.045;
    const positionAttr = particleGeometry.getAttribute("position") as THREE.BufferAttribute;
    for (let i = 0; i < particleCount; i += 1) {
      positionAttr.setY(
        i,
        positions[i * 3 + 1] + Math.sin(elapsed * 0.5 + seeds[i]) * 0.18,
      );
    }
    positionAttr.needsUpdate = true;

    ticks.rotation.y = elapsed * 0.16;
    outerRings[0].rotation.z = elapsed * 0.35;
    outerRings[1].rotation.z = -elapsed * 0.22;
    innerRing.rotation.z = -elapsed * 0.6;
    halo.material.opacity = 0.42 + Math.sin(elapsed * 1.6) * 0.08;

    heart.scale.setScalar(1 + Math.sin(elapsed * 3.4) * 0.055);
    heartCone.scale.setScalar(1 + Math.sin(elapsed * 3.4) * 0.055);
    brain.rotation.y = elapsed * 0.08;

    scanRing.position.y = -2.8 + ((elapsed * 0.55) % 5.6);
    (scanRing.material as THREE.MeshBasicMaterial).opacity =
      0.42 * Math.sin((((elapsed * 0.55) % 5.6) / 5.6) * Math.PI);

    if (playing || dragging) {
      underLight.intensity = 12 + Math.sin(elapsed * 2) * 2;
    }

    camera.position.z += (zoomTarget - camera.position.z) * Math.min(1, dt * 4);
    camera.position.y = HOME.y + Math.sin(elapsed * 0.22) * 0.12;
    camera.lookAt(0, 0.05, 0);

    renderer.render(scene, camera);
    raf = requestAnimationFrame(render);
  };

  raf = requestAnimationFrame(render);
  options.onReady?.();

  /* --------------------------------------------------------------- teardown */
  const dispose = () => {
    cancelAnimationFrame(raf);
    observer.disconnect();
    intersection.disconnect();
    document.removeEventListener("visibilitychange", onVisibility);
    renderer.domElement.removeEventListener("pointerdown", onPointerDown);
    renderer.domElement.removeEventListener("pointermove", onPointerMove);
    renderer.domElement.removeEventListener("pointerup", onPointerUp);
    renderer.domElement.removeEventListener("pointercancel", onPointerUp);
    renderer.domElement.removeEventListener("wheel", onWheel);
    renderer.domElement.removeEventListener("dblclick", onDoubleClick);
    disposables.forEach((item) => item.dispose());
    scene.traverse((object) => {
      if (object instanceof THREE.Mesh || object instanceof THREE.Points) {
        object.geometry?.dispose?.();
      }
    });
    renderer.dispose();
    renderer.forceContextLoss();
    if (renderer.domElement.parentNode === container) {
      container.removeChild(renderer.domElement);
    }
  };

  return {
    dispose,
    setPlaying: (value: boolean) => {
      playing = value;
    },
    isPlaying: () => playing,
    reset: () => {
      targetRotY = 0;
      targetTilt = 0;
      zoomTarget = HOME.z;
    },
    zoom: (delta: number) => {
      zoomTarget = THREE.MathUtils.clamp(zoomTarget + delta, 6.8, 15.5);
    },
    setSystem,
  };
}

/* ------------------------------------------------------------- fallback SVG */

function FallbackTwin({ className }: { className?: string }) {
  return (
    <div className={cn("relative flex h-full w-full items-center justify-center", className)}>
      <svg viewBox="0 0 220 420" className="h-full max-h-[420px] animate-float" aria-hidden="true">
        <defs>
          <linearGradient id="twin-fallback" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#9df3ff" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.35" />
          </linearGradient>
        </defs>
        <g stroke="url(#twin-fallback)" fill="none" strokeWidth="2" strokeLinecap="round">
          <circle cx="110" cy="46" r="24" />
          <path d="M110 70v18M110 88c-26 0-40 18-40 52v46c0 18 10 26 24 26h32c14 0 24-8 24-26v-46c0-34-14-52-40-52Z" />
          <path d="M70 96 46 132l-12 88M150 96l24 36 12 88" />
          <path d="M96 212v52l-12 96M124 212v52l12 96" />
          <path d="M72 110h76M82 130h56M88 150h44M96 170h28" strokeOpacity="0.5" />
          <circle cx="110" cy="112" r="7" stroke="#ff8fa3" />
        </g>
      </svg>
      <p className="absolute bottom-2 text-[0.6rem] uppercase tracking-[0.2em] text-slate-500">
        3D unavailable · schematic view
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- component */

export function DigitalTwin3D({
  status = "on_track",
  className,
  compact = false,
  showSystems = true,
  fallbackLabel,
}: {
  status?: TwinStatus;
  className?: string;
  compact?: boolean;
  showSystems?: boolean;
  fallbackLabel?: string;
}) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const handles = useRef<TwinHandles | null>(null);
  const [playing, setPlaying] = useState(true);
  const [system, setSystem] = useState<SystemKey>("overview");
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);

  const reducedMotion = useMemo(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    [],
  );

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    // Respect devices that cannot render WebGL at all.
    const probe = document.createElement("canvas");
    const context =
      probe.getContext("webgl2") ??
      probe.getContext("webgl") ??
      probe.getContext("experimental-webgl");
    if (!context) {
      setFailed(true);
      return;
    }

    let instance: TwinHandles | null = null;
    try {
      instance = buildScene(mount, {
        status,
        reducedMotion,
        onReady: () => setReady(true),
      });
      handles.current = instance;
      if (reducedMotion) {
        instance.setPlaying(false);
        setPlaying(false);
      }
    } catch (error) {
      console.warn("Digital twin 3D stage could not start", error);
      setFailed(true);
    }

    return () => {
      instance?.dispose();
      handles.current = null;
    };
  }, [status, reducedMotion]);

  useEffect(() => {
    handles.current?.setSystem(system);
  }, [system]);

  const togglePlay = useCallback(() => {
    const next = !playing;
    setPlaying(next);
    handles.current?.setPlaying(next);
  }, [playing]);

  return (
    <div className={cn("relative isolate", className)}>
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-1/2 h-[78%] w-[78%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-care-400/10 blur-3xl" />
        <div className="absolute left-1/2 top-1/2 h-[46%] w-[46%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-500/10 blur-3xl" />
      </div>

      <div
        ref={mountRef}
        className="h-full w-full [&>canvas]:rounded-[1.6rem]"
        role="img"
        aria-label="Rotating three-dimensional anatomical digital twin of the patient on a holographic platform. Drag to rotate, scroll to zoom."
      />

      {failed && (
        <div className="absolute inset-0 flex flex-col">
          <FallbackTwin />
          <p className="text-center text-[0.62rem] text-slate-500">
            {fallbackLabel ?? "This device does not expose WebGL. Showing a schematic twin instead."}
          </p>
        </div>
      )}

      {!failed && !ready && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-center">
            <span className="h-10 w-10 animate-spin rounded-full border-2 border-care-300/30 border-t-care-300" />
            <p className="text-[0.65rem] uppercase tracking-[0.2em] text-slate-400">
              Initialising twin projection
            </p>
          </div>
        </div>
      )}

      {!failed && (
        <>
          <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-1.5 rounded-full border border-care-300/20 bg-black/30 px-2.5 py-1 text-[0.58rem] font-semibold uppercase tracking-[0.16em] text-care-200 backdrop-blur">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-care-300 opacity-70" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-care-300" />
            </span>
            Live projection
          </div>

          <div className="absolute right-3 top-3 flex flex-col gap-1.5">
            <button
              type="button"
              onClick={togglePlay}
              aria-label={playing ? "Pause twin rotation" : "Resume twin rotation"}
              title={playing ? "Pause rotation" : "Resume rotation"}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/12 bg-black/35 text-slate-200 backdrop-blur transition-colors hover:border-care-300/40 hover:text-care-200"
            >
              {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
            </button>
            <button
              type="button"
              onClick={() => handles.current?.zoom(-1)}
              aria-label="Zoom in"
              title="Zoom in"
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/12 bg-black/35 text-slate-200 backdrop-blur transition-colors hover:border-care-300/40 hover:text-care-200"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => handles.current?.zoom(1)}
              aria-label="Zoom out"
              title="Zoom out"
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/12 bg-black/35 text-slate-200 backdrop-blur transition-colors hover:border-care-300/40 hover:text-care-200"
            >
              <Minus className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => handles.current?.reset()}
              aria-label="Reset view"
              title="Reset view"
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/12 bg-black/35 text-slate-200 backdrop-blur transition-colors hover:border-care-300/40 hover:text-care-200"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>
          </div>

          {showSystems && !compact && (
            <div className="absolute bottom-3 left-1/2 flex w-max max-w-[calc(100%-1.25rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-1 rounded-xl border border-white/10 bg-black/35 p-1 backdrop-blur">
              {SYSTEMS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setSystem(item.key)}
                  aria-pressed={system === item.key}
                  className={cn(
                    "rounded-lg px-1.5 py-1 text-[0.6rem] font-semibold uppercase tracking-[0.04em] transition-colors sm:px-2.5 sm:text-[0.62rem] sm:tracking-[0.1em]",
                    system === item.key
                      ? "bg-care-300/20 text-care-100 ring-1 ring-care-300/30"
                      : "text-slate-400 hover:text-white",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}

          <div className="pointer-events-none absolute bottom-3 right-3 hidden items-center gap-1.5 text-[0.55rem] uppercase tracking-[0.16em] text-slate-500 sm:flex">
            <Maximize2 className="h-2.5 w-2.5" /> Drag · scroll
          </div>

          <div className="pointer-events-none absolute left-3 bottom-3 hidden items-center gap-1.5 text-[0.55rem] uppercase tracking-[0.14em] text-slate-500 sm:flex">
            <Sparkles className="h-2.5 w-2.5 text-care-300/60" /> Synthetic anatomical model
          </div>
        </>
      )}
    </div>
  );
}

export default DigitalTwin3D;
