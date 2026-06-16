import { createTimer, type Timer } from 'animejs/timer';
import React, { useEffect, useMemo, useRef, useState } from 'react';

export type CryptoBackgroundVariant = 'launch' | 'ico' | 'login' | 'whitepaper' | 'tokenomics';

export type CryptoBackgroundRuntimeMode = 'animated' | 'static';

export interface CryptoBackgroundPreset {
  variant: CryptoBackgroundVariant;
  intensity: 'minimal' | 'low' | 'medium-low' | 'medium';
  density: number;
  mobileDensity: number;
  speed: number;
  opacity: number;
  gridOpacity: number;
  nodeRadius: number;
  structure: 'workflow' | 'sale' | 'access' | 'protocol' | 'distribution';
  edgeBias: number;
  centerQuietRadius: number;
  colorA: string;
  colorB: string;
  colorC: string;
  markers: string[];
}

export interface CryptoBackgroundEnvironment {
  reducedMotion?: boolean;
  saveData?: boolean;
  unsuitableDevice?: boolean;
  contextFailed?: boolean;
  hidden?: boolean;
}

const FALLBACK_VARIANT: CryptoBackgroundVariant = 'launch';

export const cryptoBackgroundPresets: Record<CryptoBackgroundVariant, CryptoBackgroundPreset> = {
  launch: {
    variant: 'launch',
    intensity: 'medium',
    density: 54,
    mobileDensity: 30,
    speed: 0.24,
    opacity: 0.34,
    gridOpacity: 0.09,
    nodeRadius: 1.65,
    structure: 'workflow',
    edgeBias: 0.5,
    centerQuietRadius: 0.24,
    colorA: '#22d3ee',
    colorB: '#14b8a6',
    colorC: '#8b5cf6',
    markers: ['research', 'validate', 'execute', 'monitor'],
  },
  ico: {
    variant: 'ico',
    intensity: 'medium-low',
    density: 44,
    mobileDensity: 24,
    speed: 0.18,
    opacity: 0.27,
    gridOpacity: 0.075,
    nodeRadius: 1.5,
    structure: 'sale',
    edgeBias: 0.58,
    centerQuietRadius: 0.3,
    colorA: '#22d3ee',
    colorB: '#f59e0b',
    colorC: '#7dd3fc',
    markers: ['EXL', 'KYC', 'TGE'],
  },
  login: {
    variant: 'login',
    intensity: 'minimal',
    density: 18,
    mobileDensity: 12,
    speed: 0.08,
    opacity: 0.16,
    gridOpacity: 0.035,
    nodeRadius: 1.25,
    structure: 'access',
    edgeBias: 0.68,
    centerQuietRadius: 0.42,
    colorA: '#22d3ee',
    colorB: '#64748b',
    colorC: '#14b8a6',
    markers: ['auth', 'mfa', 'session'],
  },
  whitepaper: {
    variant: 'whitepaper',
    intensity: 'low',
    density: 28,
    mobileDensity: 16,
    speed: 0.1,
    opacity: 0.18,
    gridOpacity: 0.055,
    nodeRadius: 1.25,
    structure: 'protocol',
    edgeBias: 0.82,
    centerQuietRadius: 0.46,
    colorA: '#67e8f9',
    colorB: '#94a3b8',
    colorC: '#a78bfa',
    markers: ['hash', 'proof', 'flow'],
  },
  tokenomics: {
    variant: 'tokenomics',
    intensity: 'medium-low',
    density: 34,
    mobileDensity: 18,
    speed: 0.13,
    opacity: 0.2,
    gridOpacity: 0.06,
    nodeRadius: 1.35,
    structure: 'distribution',
    edgeBias: 0.76,
    centerQuietRadius: 0.4,
    colorA: '#2dd4bf',
    colorB: '#fbbf24',
    colorC: '#60a5fa',
    markers: ['vesting', 'unlock', 'treasury'],
  },
};

export const cryptoBackgroundIntensityOrder: CryptoBackgroundVariant[] = [
  'login',
  'whitepaper',
  'tokenomics',
  'ico',
  'launch',
];

export const resolveCryptoBackgroundVariant = (
  variant: CryptoBackgroundVariant | string | null | undefined
): CryptoBackgroundVariant =>
  variant && variant in cryptoBackgroundPresets
    ? (variant as CryptoBackgroundVariant)
    : FALLBACK_VARIANT;

export const getCryptoBackgroundPreset = (
  variant: CryptoBackgroundVariant | string | null | undefined
): CryptoBackgroundPreset => cryptoBackgroundPresets[resolveCryptoBackgroundVariant(variant)];

export const getCryptoBackgroundVariantForIcoDocument = (
  slug: string | undefined
): CryptoBackgroundVariant => {
  if (slug === 'whitepaper') return 'whitepaper';
  if (slug === 'tokenomics') return 'tokenomics';
  return 'ico';
};

export const getCryptoBackgroundStaticReason = (
  environment: CryptoBackgroundEnvironment
): string | null => {
  if (environment.reducedMotion) return 'reduced-motion';
  if (environment.saveData) return 'save-data';
  if (environment.contextFailed) return 'context-failed';
  if (environment.unsuitableDevice) return 'device';
  if (environment.hidden) return 'hidden';
  return null;
};

export const getCryptoBackgroundRuntimeMode = (
  environment: CryptoBackgroundEnvironment
): CryptoBackgroundRuntimeMode =>
  getCryptoBackgroundStaticReason(environment) ? 'static' : 'animated';

interface SceneNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  phase: number;
  marker: string;
  role: number;
}

interface InteractionState {
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  energy: number;
  bursts: Array<{
    x: number;
    y: number;
    age: number;
    duration: number;
  }>;
}

interface CryptoBackgroundProps {
  variant?: CryptoBackgroundVariant | string;
  className?: string;
}

const getNavigatorConnection = () => {
  const nav = navigator as Navigator & {
    connection?: { saveData?: boolean; effectiveType?: string };
  };
  return nav.connection;
};

const isUnsuitableDevice = () => {
  const nav = navigator as Navigator & {
    deviceMemory?: number;
  };
  const connection = getNavigatorConnection();
  const memory = nav.deviceMemory ?? 4;
  const cores = navigator.hardwareConcurrency ?? 4;
  const effectiveType = connection?.effectiveType ?? '';
  return memory <= 1 || cores <= 2 || effectiveType === 'slow-2g' || effectiveType === '2g';
};

const readEnvironment = (): CryptoBackgroundEnvironment => {
  if (typeof window === 'undefined') {
    return { reducedMotion: true };
  }

  return {
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    saveData: Boolean(getNavigatorConnection()?.saveData),
    unsuitableDevice: isUnsuitableDevice(),
    hidden: document.visibilityState === 'hidden',
  };
};

const colorToRgba = (hex: string, alpha: number) => {
  const normalized = hex.replace('#', '');
  const value = Number.parseInt(normalized, 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

const seeded = (seed: number) => {
  const next = Math.sin(seed * 12.9898) * 43758.5453;
  return next - Math.floor(next);
};

const edgeWeightedPosition = (index: number, preset: CryptoBackgroundPreset, width: number) => {
  const side =
    seeded(index + 11) < 0.5
      ? seeded(index + 23) * preset.edgeBias
      : 1 - seeded(index + 37) * preset.edgeBias;
  const quiet = 0.5 + (seeded(index + 43) - 0.5) * preset.centerQuietRadius;
  return seeded(index + 3) < preset.edgeBias ? side * width : quiet * width;
};

const createNodes = (
  preset: CryptoBackgroundPreset,
  width: number,
  height: number
): SceneNode[] => {
  const count = width < 768 ? preset.mobileDensity : preset.density;
  return Array.from({ length: count }, (_, index) => {
    const x = edgeWeightedPosition(index, preset, width);
    const y = seeded(index + 101) * height;
    const drift = preset.speed * (0.35 + seeded(index + 17) * 0.65);
    return {
      x,
      y,
      vx: (seeded(index + 29) - 0.5) * drift,
      vy: (seeded(index + 31) - 0.5) * drift,
      radius: preset.nodeRadius + seeded(index + 41) * preset.nodeRadius,
      phase: seeded(index + 53) * Math.PI * 2,
      marker: preset.markers[index % preset.markers.length] ?? '',
      role: index % 7,
    };
  });
};

const drawGrid = (
  context: CanvasRenderingContext2D,
  preset: CryptoBackgroundPreset,
  width: number,
  height: number
) => {
  const spacing = preset.variant === 'whitepaper' ? 72 : preset.variant === 'tokenomics' ? 84 : 64;
  context.save();
  context.strokeStyle = colorToRgba(preset.colorB, preset.gridOpacity);
  context.lineWidth = 1;
  for (let x = spacing; x < width; x += spacing) {
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, height);
    context.stroke();
  }
  for (let y = spacing; y < height; y += spacing) {
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(width, y);
    context.stroke();
  }
  context.restore();
};

const drawProtocolLayers = (
  context: CanvasRenderingContext2D,
  preset: CryptoBackgroundPreset,
  width: number,
  height: number,
  time: number
) => {
  context.save();
  context.lineWidth = 1;
  context.strokeStyle = colorToRgba(preset.colorA, preset.opacity * 0.32);
  context.fillStyle = colorToRgba(preset.colorC, preset.opacity * 0.055);

  const layerCount = preset.structure === 'distribution' ? 4 : 3;
  for (let index = 0; index < layerCount; index += 1) {
    const inset = 52 + index * 38;
    const widthScale = preset.structure === 'protocol' ? 0.34 : 0.26;
    const x = index % 2 === 0 ? inset : width - inset - width * widthScale;
    const y = height * (0.18 + index * 0.18) + Math.sin(time * 0.00035 + index) * 3;
    const rectWidth = width * widthScale;
    const rectHeight = preset.structure === 'protocol' ? 52 : 44;
    context.beginPath();
    context.roundRect(x, y, rectWidth, rectHeight, 8);
    context.fill();
    context.stroke();
  }

  if (preset.structure === 'distribution') {
    const cx = width * 0.5;
    const cy = height * 0.42;
    for (let ring = 0; ring < 3; ring += 1) {
      context.beginPath();
      context.ellipse(cx, cy, 96 + ring * 58, 42 + ring * 30, 0, 0, Math.PI * 2);
      context.strokeStyle = colorToRgba(
        ring === 1 ? preset.colorB : preset.colorA,
        preset.opacity * (0.22 - ring * 0.035)
      );
      context.stroke();
    }
  }

  context.restore();
};

const drawHexagon = (
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  rotation = 0
) => {
  context.beginPath();
  for (let side = 0; side < 6; side += 1) {
    const angle = rotation + Math.PI / 6 + side * (Math.PI / 3);
    const px = x + Math.cos(angle) * radius;
    const py = y + Math.sin(angle) * radius;
    if (side === 0) context.moveTo(px, py);
    else context.lineTo(px, py);
  }
  context.closePath();
};

const drawEthereumDiamond = (
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  size: number,
  alpha: number
) => {
  context.save();
  context.strokeStyle = `rgba(125, 211, 252, ${alpha})`;
  context.fillStyle = `rgba(125, 211, 252, ${alpha * 0.16})`;
  context.lineWidth = 1;
  context.beginPath();
  context.moveTo(x, y - size);
  context.lineTo(x + size * 0.62, y);
  context.lineTo(x, y + size);
  context.lineTo(x - size * 0.62, y);
  context.closePath();
  context.fill();
  context.stroke();
  context.beginPath();
  context.moveTo(x, y - size * 0.45);
  context.lineTo(x + size * 0.62, y);
  context.lineTo(x, y + size * 0.22);
  context.lineTo(x - size * 0.62, y);
  context.closePath();
  context.stroke();
  context.restore();
};

const drawDeFiMotifs = (
  context: CanvasRenderingContext2D,
  preset: CryptoBackgroundPreset,
  width: number,
  height: number,
  time: number
) => {
  const alpha = preset.opacity;
  const drift = Math.sin(time * 0.00045) * 6;
  context.save();
  context.font = '10px "JetBrains Mono", ui-monospace, monospace';
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  context.lineWidth = 1;

  const labels =
    preset.variant === 'tokenomics'
      ? ['SUPPLY', 'VEST', 'UNLOCK', 'TREASURY', 'FLOW']
      : preset.variant === 'whitepaper'
        ? ['0xHASH', 'PROOF', 'L2', 'FLOW', 'AUDIT']
        : preset.variant === 'login'
          ? ['AUTH', 'MFA', 'SESSION']
          : ['L1', 'L2', 'DEX', 'AMM', 'VAULT', 'ORACLE'];

  const motifCount = width < 768 ? 4 : 7;
  for (let index = 0; index < motifCount; index += 1) {
    const edge = index % 2 === 0 ? 0.08 : 0.92;
    const x = width * edge + (seeded(index + 301) - 0.5) * width * 0.1;
    const y = height * (0.16 + seeded(index + 311) * 0.72) + drift * (index % 2 === 0 ? 1 : -1);
    const radius = 20 + seeded(index + 331) * 14;
    const label = labels[index % labels.length] ?? 'NODE';
    context.strokeStyle = colorToRgba(
      index % 2 === 0 ? preset.colorA : preset.colorC,
      alpha * 0.28
    );
    context.fillStyle = colorToRgba(index % 2 === 0 ? preset.colorA : preset.colorC, alpha * 0.05);
    drawHexagon(context, x, y, radius, time * 0.00008 + index);
    context.fill();
    context.stroke();
    context.fillStyle = colorToRgba(preset.colorB, alpha * 0.46);
    context.fillText(label, x, y);
  }

  if (preset.variant === 'ico' || preset.variant === 'whitepaper') {
    drawEthereumDiamond(context, width * 0.86, height * 0.34 + drift, 26, alpha * 0.36);
    drawEthereumDiamond(context, width * 0.12, height * 0.66 - drift, 18, alpha * 0.24);
  }

  if (preset.variant === 'launch' || preset.variant === 'ico') {
    const chainY = height * 0.82;
    context.strokeStyle = colorToRgba(preset.colorA, alpha * 0.24);
    context.fillStyle = colorToRgba(preset.colorA, alpha * 0.045);
    for (let block = 0; block < 6; block += 1) {
      const x = width * 0.12 + block * Math.min(92, width * 0.09);
      const y = chainY + Math.sin(time * 0.0005 + block) * 4;
      context.beginPath();
      context.roundRect(x, y, 54, 28, 5);
      context.fill();
      context.stroke();
      if (block > 0) {
        context.beginPath();
        context.moveTo(x - 26, y + 14);
        context.lineTo(x, y + 14);
        context.stroke();
      }
    }
  }

  if (preset.variant === 'tokenomics') {
    const cx = width * 0.78;
    const cy = height * 0.58;
    for (let arc = 0; arc < 4; arc += 1) {
      context.strokeStyle = colorToRgba(
        arc % 2 === 0 ? preset.colorA : preset.colorB,
        alpha * (0.26 - arc * 0.035)
      );
      context.beginPath();
      context.arc(
        cx,
        cy,
        38 + arc * 24,
        time * 0.00018 + arc,
        Math.PI * 1.3 + time * 0.00018 + arc
      );
      context.stroke();
    }
    context.fillStyle = colorToRgba(preset.colorA, alpha * 0.16);
    context.beginPath();
    context.arc(cx, cy, 8, 0, Math.PI * 2);
    context.fill();
  }

  if (preset.variant === 'login') {
    context.strokeStyle = colorToRgba(preset.colorA, alpha * 0.22);
    context.beginPath();
    context.roundRect(width * 0.78, height * 0.22, 72, 36, 7);
    context.stroke();
    context.beginPath();
    context.arc(width * 0.78 + 36, height * 0.22, 13, Math.PI, Math.PI * 2);
    context.stroke();
  }

  context.restore();
};

const drawConnections = (
  context: CanvasRenderingContext2D,
  nodes: SceneNode[],
  preset: CryptoBackgroundPreset,
  time: number
) => {
  const maxDistance =
    preset.variant === 'login' ? 140 : preset.variant === 'whitepaper' ? 165 : 190;
  context.save();
  for (let index = 0; index < nodes.length; index += 1) {
    const source = nodes[index];
    if (!source) continue;
    for (
      let targetIndex = index + 1;
      targetIndex < Math.min(nodes.length, index + 5);
      targetIndex += 1
    ) {
      const target = nodes[targetIndex];
      if (!target) continue;
      const distance = Math.hypot(source.x - target.x, source.y - target.y);
      if (distance > maxDistance) continue;
      const pulse = 0.55 + Math.sin(time * 0.00055 + source.phase + target.phase) * 0.25;
      const alpha = (1 - distance / maxDistance) * preset.opacity * 0.38 * pulse;
      context.strokeStyle = colorToRgba(
        source.role % 3 === 0 ? preset.colorC : preset.colorA,
        alpha
      );
      context.lineWidth = source.role % 4 === 0 ? 1.15 : 0.85;
      context.beginPath();
      context.moveTo(source.x, source.y);
      context.lineTo(target.x, target.y);
      context.stroke();

      if (source.role % 3 === 0) {
        const progress = (Math.sin(time * 0.001 + source.phase) + 1) / 2;
        const pulseX = source.x + (target.x - source.x) * progress;
        const pulseY = source.y + (target.y - source.y) * progress;
        context.fillStyle = colorToRgba(preset.colorA, alpha * 1.8);
        context.beginPath();
        context.arc(pulseX, pulseY, 1.2 + source.role * 0.08, 0, Math.PI * 2);
        context.fill();
      }
    }
  }
  context.restore();
};

const drawNodes = (
  context: CanvasRenderingContext2D,
  nodes: SceneNode[],
  preset: CryptoBackgroundPreset,
  time: number
) => {
  context.save();
  context.font = '10px "JetBrains Mono", ui-monospace, monospace';
  context.textAlign = 'center';
  nodes.forEach((node, index) => {
    const pulse = 0.76 + Math.sin(time * 0.0007 + node.phase) * 0.2;
    const color = index % 5 === 0 ? preset.colorC : index % 3 === 0 ? preset.colorB : preset.colorA;
    context.beginPath();
    context.fillStyle = colorToRgba(color, preset.opacity * (0.38 + pulse * 0.2));
    context.arc(node.x, node.y, node.radius * pulse, 0, Math.PI * 2);
    context.fill();

    if (index % 13 === 0 && preset.variant !== 'login') {
      context.fillStyle = colorToRgba(color, preset.opacity * 0.34);
      context.fillText(node.marker, node.x, node.y - 8);
    }
  });
  context.restore();
};

const updateNodes = (
  nodes: SceneNode[],
  preset: CryptoBackgroundPreset,
  width: number,
  height: number,
  interaction?: InteractionState
) => {
  nodes.forEach((node) => {
    node.x += node.vx;
    node.y += node.vy;
    if (node.x < -24) node.x = width + 24;
    if (node.x > width + 24) node.x = -24;
    if (node.y < -24) node.y = height + 24;
    if (node.y > height + 24) node.y = -24;

    const centerDistance = Math.abs(node.x / width - 0.5);
    if (centerDistance < preset.centerQuietRadius * 0.45) {
      node.x += node.x < width * 0.5 ? -0.08 : 0.08;
    }

    if (interaction && interaction.energy > 0.02) {
      const distance = Math.hypot(node.x - interaction.x, node.y - interaction.y);
      const influenceRadius = preset.variant === 'login' ? 180 : 240;
      if (distance > 0 && distance < influenceRadius) {
        const force = (1 - distance / influenceRadius) * interaction.energy * preset.speed * 0.82;
        node.x += ((node.x - interaction.x) / distance) * force;
        node.y += ((node.y - interaction.y) / distance) * force;
      }
    }
  });
};

const updateInteraction = (interaction: InteractionState) => {
  interaction.x += (interaction.targetX - interaction.x) * 0.08;
  interaction.y += (interaction.targetY - interaction.y) * 0.08;
  interaction.energy *= 0.985;
  interaction.bursts = interaction.bursts
    .map((burst) => ({ ...burst, age: burst.age + 1 }))
    .filter((burst) => burst.age < burst.duration);
};

const drawInteractionField = (
  context: CanvasRenderingContext2D,
  preset: CryptoBackgroundPreset,
  nodes: SceneNode[],
  interaction: InteractionState
) => {
  if (interaction.energy < 0.02 && interaction.bursts.length === 0) return;

  context.save();
  const radius = preset.variant === 'login' ? 112 : preset.variant === 'whitepaper' ? 132 : 172;
  const gradient = context.createRadialGradient(
    interaction.x,
    interaction.y,
    0,
    interaction.x,
    interaction.y,
    radius
  );
  gradient.addColorStop(0, colorToRgba(preset.colorA, preset.opacity * 0.22 * interaction.energy));
  gradient.addColorStop(1, colorToRgba(preset.colorA, 0));
  context.fillStyle = gradient;
  context.beginPath();
  context.arc(interaction.x, interaction.y, radius, 0, Math.PI * 2);
  context.fill();

  context.strokeStyle = colorToRgba(preset.colorA, preset.opacity * 0.42 * interaction.energy);
  context.lineWidth = 0.9;
  nodes.slice(0, 18).forEach((node) => {
    const distance = Math.hypot(node.x - interaction.x, node.y - interaction.y);
    if (distance > radius * 1.2) return;
    context.beginPath();
    context.moveTo(interaction.x, interaction.y);
    context.lineTo(node.x, node.y);
    context.stroke();
  });

  interaction.bursts.forEach((burst, index) => {
    const progress = burst.age / burst.duration;
    const burstRadius = 28 + progress * (preset.variant === 'login' ? 92 : 178);
    const burstAlpha =
      (1 - progress) *
      preset.opacity *
      (preset.variant === 'whitepaper' ? 0.34 : preset.variant === 'tokenomics' ? 0.42 : 0.62);
    context.strokeStyle = colorToRgba(index % 2 === 0 ? preset.colorA : preset.colorC, burstAlpha);
    context.lineWidth = 1 + (1 - progress) * 1.4;
    context.beginPath();
    context.arc(burst.x, burst.y, burstRadius, 0, Math.PI * 2);
    context.stroke();

    context.strokeStyle = colorToRgba(preset.colorB, burstAlpha * 0.8);
    drawHexagon(context, burst.x, burst.y, burstRadius * 0.42, progress * Math.PI);
    context.stroke();
  });
  context.restore();
};

export const drawCryptoBackgroundFrame = (
  context: CanvasRenderingContext2D,
  preset: CryptoBackgroundPreset,
  nodes: SceneNode[],
  width: number,
  height: number,
  time = 0,
  interaction?: InteractionState
) => {
  context.clearRect(0, 0, width, height);
  drawGrid(context, preset, width, height);
  drawDeFiMotifs(context, preset, width, height, time);
  if (preset.structure === 'protocol' || preset.structure === 'distribution') {
    drawProtocolLayers(context, preset, width, height, time);
  }
  drawConnections(context, nodes, preset, time);
  if (interaction) drawInteractionField(context, preset, nodes, interaction);
  drawNodes(context, nodes, preset, time);
};

export const CryptoBackground: React.FC<CryptoBackgroundProps> = ({
  variant = FALLBACK_VARIANT,
  className = '',
}) => {
  const resolvedVariant = resolveCryptoBackgroundVariant(variant);
  const preset = useMemo(() => getCryptoBackgroundPreset(resolvedVariant), [resolvedVariant]);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const timerRef = useRef<Timer | null>(null);
  const nodesRef = useRef<SceneNode[]>([]);
  const interactionRef = useRef<InteractionState>({
    x: 0,
    y: 0,
    targetX: 0,
    targetY: 0,
    energy: 0,
    bursts: [],
  });
  const modeRef = useRef<CryptoBackgroundRuntimeMode>('static');
  const [mode, setMode] = useState<CryptoBackgroundRuntimeMode>('static');
  const [staticReason, setStaticReason] = useState<string>('ssr');

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    let disposed = false;
    let contextFailed = false;
    let visibleInViewport = true;
    let resizeTimeout: number | null = null;
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const context = canvas.getContext('2d', { alpha: true });

    if (!context) {
      contextFailed = true;
    }

    const stop = () => {
      timerRef.current?.pause();
    };

    const syncCanvas = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, width < 768 ? 1.25 : 1.6);
      canvas.width = Math.max(1, Math.floor(width * dpr));
      canvas.height = Math.max(1, Math.floor(height * dpr));
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context?.setTransform(dpr, 0, 0, dpr, 0, 0);
      nodesRef.current = createNodes(preset, width, height);
      interactionRef.current.x = width * 0.5;
      interactionRef.current.y = height * 0.5;
      interactionRef.current.targetX = width * 0.5;
      interactionRef.current.targetY = height * 0.5;
      interactionRef.current.bursts = [];
    };

    const drawStatic = () => {
      if (!context) return;
      drawCryptoBackgroundFrame(
        context,
        preset,
        nodesRef.current,
        window.innerWidth,
        window.innerHeight,
        0
      );
    };

    const renderAnimatedFrame = (time: number) => {
      if (disposed || modeRef.current !== 'animated' || !context) return;
      const width = window.innerWidth;
      const height = window.innerHeight;
      updateInteraction(interactionRef.current);
      updateNodes(nodesRef.current, preset, width, height, interactionRef.current);
      drawCryptoBackgroundFrame(
        context,
        preset,
        nodesRef.current,
        width,
        height,
        time,
        interactionRef.current
      );
    };

    const refreshMode = () => {
      const environment = {
        ...readEnvironment(),
        contextFailed,
        hidden: document.visibilityState === 'hidden' || !visibleInViewport,
      };
      const nextMode = getCryptoBackgroundRuntimeMode(environment);
      const nextReason = getCryptoBackgroundStaticReason(environment);
      modeRef.current = nextMode;
      setMode(nextMode);
      setStaticReason(nextReason ?? 'none');
      stop();
      if (nextMode === 'static') {
        drawStatic();
        return;
      }
      timerRef.current?.resume();
    };

    const handleResize = () => {
      if (resizeTimeout) window.clearTimeout(resizeTimeout);
      resizeTimeout = window.setTimeout(() => {
        syncCanvas();
        refreshMode();
      }, 160);
    };

    const handleVisibility = () => refreshMode();
    const handleContextLost = (event: Event) => {
      event.preventDefault();
      contextFailed = true;
      refreshMode();
    };
    const handlePointerMove = (event: PointerEvent) => {
      if (modeRef.current !== 'animated') return;
      interactionRef.current.targetX = event.clientX;
      interactionRef.current.targetY = event.clientY;
      interactionRef.current.energy = Math.min(1, interactionRef.current.energy + 0.18);
    };
    const handlePointerDown = (event: PointerEvent) => {
      if (modeRef.current !== 'animated') return;
      interactionRef.current.targetX = event.clientX;
      interactionRef.current.targetY = event.clientY;
      interactionRef.current.energy = 1;
      interactionRef.current.bursts = [
        ...interactionRef.current.bursts.slice(-3),
        {
          x: event.clientX,
          y: event.clientY,
          age: 0,
          duration: preset.variant === 'login' ? 70 : 92,
        },
      ];
    };
    const handlePointerLeave = () => {
      interactionRef.current.energy *= 0.35;
    };

    const observer = new IntersectionObserver(
      (entries) => {
        visibleInViewport = entries.some((entry) => entry.isIntersecting);
        refreshMode();
      },
      { threshold: 0.01 }
    );

    syncCanvas();
    timerRef.current = createTimer({
      autoplay: false,
      duration: 60_000,
      loop: true,
      frameRate: window.innerWidth < 768 ? 30 : 48,
      onUpdate: (timer) => renderAnimatedFrame(timer.currentTime),
    });
    observer.observe(canvas);
    refreshMode();

    window.addEventListener('resize', handleResize, { passive: true });
    window.addEventListener('pointermove', handlePointerMove, { passive: true });
    window.addEventListener('pointerdown', handlePointerDown, { passive: true });
    window.addEventListener('pointerleave', handlePointerLeave, { passive: true });
    document.addEventListener('visibilitychange', handleVisibility);
    canvas.addEventListener('contextlost', handleContextLost);
    mediaQuery.addEventListener('change', handleVisibility);

    return () => {
      disposed = true;
      stop();
      timerRef.current?.revert();
      timerRef.current = null;
      if (resizeTimeout) window.clearTimeout(resizeTimeout);
      observer.disconnect();
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerdown', handlePointerDown);
      window.removeEventListener('pointerleave', handlePointerLeave);
      document.removeEventListener('visibilitychange', handleVisibility);
      canvas.removeEventListener('contextlost', handleContextLost);
      mediaQuery.removeEventListener('change', handleVisibility);
      context?.clearRect(0, 0, canvas.width, canvas.height);
      nodesRef.current = [];
    };
  }, [preset]);

  return (
    <div
      className={`crypto-background crypto-background--${resolvedVariant} ${className}`}
      data-crypto-background="true"
      data-variant={resolvedVariant}
      data-mode={mode}
      data-static-reason={staticReason}
      aria-hidden="true"
    >
      <div className="crypto-background__static" />
      <canvas ref={canvasRef} className="crypto-background__canvas" />
    </div>
  );
};

export default CryptoBackground;
