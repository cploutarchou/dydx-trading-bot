#!/usr/bin/env node

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';

const ROUTES = [
  { key: 'ico-briefing', path: '/ico', variant: 'ico' },
  { key: 'ico-whitepaper', path: '/ico/whitepaper', variant: 'whitepaper' },
  { key: 'ico-tokenomics', path: '/ico/tokenomics', variant: 'tokenomics' },
  { key: 'login', path: '/login', variant: 'login' },
];

const VIEWPORTS = [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function parseArgs(argv) {
  const options = {
    baseUrl: 'http://localhost:5173',
    outputDir: 'docs/screenshots/crypto-background-final',
    browserPath: '',
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--base-url') options.baseUrl = argv[++index] ?? options.baseUrl;
    else if (arg === '--output-dir') options.outputDir = argv[++index] ?? options.outputDir;
    else if (arg === '--browser-path') options.browserPath = argv[++index] ?? '';
    else throw new Error(`Unknown argument: ${arg}`);
  }

  return options;
}

function commandExists(command) {
  const result = spawn('which', [command], { stdio: ['ignore', 'pipe', 'ignore'] });
  return new Promise((resolve) => {
    let output = '';
    result.stdout.on('data', (chunk) => {
      output += chunk.toString();
    });
    result.on('close', (code) => resolve(code === 0 ? output.trim() : ''));
  });
}

async function detectBrowser(explicitPath) {
  if (explicitPath) return path.resolve(explicitPath);
  for (const command of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']) {
    const resolved = await commandExists(command);
    if (resolved) return resolved;
  }
  throw new Error('Could not find Chrome/Chromium. Pass --browser-path.');
}

async function waitForDevToolsPort(userDataDir) {
  const portFile = path.join(userDataDir, 'DevToolsActivePort');
  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (fs.existsSync(portFile)) {
      const [port] = fs.readFileSync(portFile, 'utf-8').trim().split('\n');
      if (port) return port;
    }
    await sleep(100);
  }
  throw new Error('Chrome did not expose a DevTools port.');
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async connect() {
    this.socket = new WebSocket(this.wsUrl);
    this.socket.addEventListener('message', (event) => this.handleMessage(event.data));
    await new Promise((resolve, reject) => {
      this.socket.addEventListener('open', resolve, { once: true });
      this.socket.addEventListener('error', reject, { once: true });
    });
  }

  handleMessage(raw) {
    const message = JSON.parse(raw);
    if (message.id && this.pending.has(message.id)) {
      const { resolve, reject } = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
      return;
    }
    if (message.method && this.listeners.has(message.method)) {
      this.listeners.get(message.method).forEach((listener) => listener(message.params));
    }
  }

  on(method, listener) {
    if (!this.listeners.has(method)) this.listeners.set(method, []);
    this.listeners.get(method).push(listener);
  }

  send(method, params = {}) {
    const id = this.nextId;
    this.nextId += 1;
    this.socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
  }

  close() {
    this.socket?.close();
  }
}

async function createPageClient(port) {
  const response = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, {
    method: 'PUT',
  });
  const target = await response.json();
  const client = new CdpClient(target.webSocketDebuggerUrl);
  await client.connect();
  await client.send('Page.enable');
  await client.send('Runtime.enable');
  await client.send('Log.enable');
  return client;
}

async function navigate(client, baseUrl, routePath, viewport, media = 'screen', features = []) {
  await client.send('Emulation.setDeviceMetricsOverride', {
    width: viewport.width,
    height: viewport.height,
    deviceScaleFactor: 1,
    mobile: viewport.width < 768,
  });
  await client.send('Emulation.setEmulatedMedia', { media, features });
  const loadPromise = new Promise((resolve) => client.on('Page.loadEventFired', resolve));
  await client.send('Page.navigate', { url: `${baseUrl.replace(/\/$/, '')}${routePath}` });
  await loadPromise;
  await sleep(900);
}

async function evaluate(client, expression, awaitPromise = false) {
  const result = await client.send('Runtime.evaluate', {
    expression,
    awaitPromise,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || 'Runtime evaluation failed');
  }
  return result.result.value;
}

async function capture(client, outputPath) {
  const result = await client.send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false,
  });
  fs.writeFileSync(outputPath, Buffer.from(result.data, 'base64'));
}

const pageCheckExpression = (expectedVariant) => `(() => {
  const bg = [...document.querySelectorAll('[data-crypto-background="true"]')];
  const canvas = [...document.querySelectorAll('.crypto-background__canvas')];
  const firstBg = bg[0];
  const tocLink = document.querySelector('.ico-document-index a');
  const table = document.querySelector('.ico-document-article table');
  const h1 = document.querySelector('h1');
  const beforeHash = location.hash;
  let anchorNavigationWorks = true;
  if (tocLink) {
    tocLink.click();
    anchorNavigationWorks = location.hash !== beforeHash && location.hash.length > 1;
  }
  let selectionWorks = false;
  if (h1 && window.getSelection) {
    const range = document.createRange();
    range.selectNodeContents(h1);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    selectionWorks = selection.toString().trim().length > 0;
    selection.removeAllRanges();
  }
  const pointerTarget = tocLink || document.querySelector('a, button, input');
  const rect = pointerTarget?.getBoundingClientRect();
  const topElement = rect
    ? document.elementFromPoint(Math.min(rect.left + 8, window.innerWidth - 2), Math.min(rect.top + 8, window.innerHeight - 2))
    : null;
  return {
    backgroundCount: bg.length,
    canvasCount: canvas.length,
    variant: firstBg?.getAttribute('data-variant') || '',
    mode: firstBg?.getAttribute('data-mode') || '',
    staticReason: firstBg?.getAttribute('data-static-reason') || '',
    ariaHidden: firstBg?.getAttribute('aria-hidden') === 'true',
    pointerEvents: firstBg ? getComputedStyle(firstBg).pointerEvents : '',
    expectedVariant: '${expectedVariant}',
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    anchorNavigationWorks,
    selectionWorks,
    topElementIsBackground: Boolean(topElement?.closest?.('[data-crypto-background="true"]')),
    firstTableText: table?.textContent?.replace(/\\s+/g, ' ').trim().slice(0, 80) || '',
    chartCount: document.querySelectorAll('[role="img"], .recharts-wrapper, canvas[data-chart]').length,
    tableCount: document.querySelectorAll('.ico-document-article table').length,
  };
})()`;

const metricExpression = `(() => new Promise((resolve) => {
  const metrics = { longTasks: 0, cls: 0, lcp: 0, fps: 0 };
  try {
    const longTaskObserver = new PerformanceObserver((list) => {
      metrics.longTasks += list.getEntries().length;
    });
    longTaskObserver.observe({ entryTypes: ['longtask'] });
    const clsObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) metrics.cls += entry.value || 0;
      }
    });
    clsObserver.observe({ type: 'layout-shift', buffered: true });
    const lcpObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const last = entries[entries.length - 1];
      if (last) metrics.lcp = last.startTime || 0;
    });
    lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true });
    setTimeout(() => {
      longTaskObserver.disconnect();
      clsObserver.disconnect();
      lcpObserver.disconnect();
    }, 1600);
  } catch {
    metrics.observerUnavailable = true;
  }
  let frames = 0;
  const start = performance.now();
  const step = (now) => {
    frames += 1;
    if (now - start >= 1000) {
      metrics.fps = Math.round((frames * 1000) / Math.max(1, now - start));
      resolve(metrics);
      return;
    }
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}))()`;

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const projectRoot = path.resolve(import.meta.dirname, '..');
  const outputDir = path.resolve(projectRoot, options.outputDir);
  fs.mkdirSync(outputDir, { recursive: true });

  const browserPath = await detectBrowser(options.browserPath);
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'crypto-background-browser-'));
  const chrome = spawn(browserPath, [
    '--headless=new',
    '--disable-gpu',
    '--disable-extensions',
    '--no-first-run',
    '--no-default-browser-check',
    '--remote-debugging-port=0',
    `--user-data-dir=${userDataDir}`,
    'about:blank',
  ]);

  const errors = [];
  const measurements = [];

  try {
    const port = await waitForDevToolsPort(userDataDir);
    const client = await createPageClient(port);
    client.on('Runtime.exceptionThrown', (params) => {
      errors.push(params.exceptionDetails?.text || 'Runtime exception');
    });
    client.on('Log.entryAdded', (params) => {
      if (params.entry?.level === 'error') errors.push(params.entry.text);
    });

    for (const route of ROUTES) {
      for (const viewport of VIEWPORTS) {
        await navigate(client, options.baseUrl, route.path, viewport);
        const checks = await evaluate(client, pageCheckExpression(route.variant));
        if (checks.backgroundCount !== 1) {
          throw new Error(`${route.key}: expected one background, got ${checks.backgroundCount}`);
        }
        if (checks.canvasCount !== 1) {
          throw new Error(`${route.key}: expected one canvas, got ${checks.canvasCount}`);
        }
        if (checks.variant !== route.variant)
          throw new Error(`${route.key}: expected ${route.variant}, got ${checks.variant}`);
        if (checks.pointerEvents !== 'none')
          throw new Error(`${route.key}: background captures pointer events`);
        if (!checks.ariaHidden) throw new Error(`${route.key}: background is not aria-hidden`);
        if (checks.overflowX > 1)
          throw new Error(`${route.key}: horizontal overflow ${checks.overflowX}px`);
        if (checks.topElementIsBackground)
          throw new Error(`${route.key}: background intercepts pointer target`);
        if (
          (route.key === 'ico-whitepaper' || route.key === 'ico-tokenomics') &&
          !checks.anchorNavigationWorks
        ) {
          throw new Error(`${route.key}: anchor navigation failed`);
        }
        if (
          (route.key === 'ico-whitepaper' || route.key === 'ico-tokenomics') &&
          !checks.selectionWorks
        ) {
          throw new Error(`${route.key}: text selection failed`);
        }
        await capture(client, path.join(outputDir, `${route.key}-${viewport.width}.png`));
      }
    }

    for (const route of ROUTES.filter(
      (item) => item.key === 'ico-whitepaper' || item.key === 'ico-tokenomics'
    )) {
      await navigate(client, options.baseUrl, route.path, { width: 1440, height: 900 }, 'screen', [
        { name: 'prefers-reduced-motion', value: 'reduce' },
      ]);
      const checks = await evaluate(client, pageCheckExpression(route.variant));
      if (checks.mode !== 'static' || checks.staticReason !== 'reduced-motion') {
        throw new Error(`${route.key}: reduced-motion static fallback failed`);
      }
      await capture(client, path.join(outputDir, `${route.key}-reduced-motion-1440.png`));

      await navigate(client, options.baseUrl, route.path, { width: 1440, height: 900 }, 'print');
      const printCheck = await evaluate(
        client,
        `(() => {
          const bg = document.querySelector('[data-crypto-background="true"]');
          return {
            backgroundDisplay: bg ? getComputedStyle(bg).display : '',
            articleText: document.querySelector('.ico-document-article')?.textContent?.trim().length || 0,
            tableCount: document.querySelectorAll('table').length,
          };
        })()`
      );
      if (printCheck.backgroundDisplay !== 'none')
        throw new Error(`${route.key}: print background visible`);
      if (printCheck.articleText < 200) throw new Error(`${route.key}: print content missing`);
      await capture(client, path.join(outputDir, `${route.key}-print-1440.png`));
    }

    await navigate(client, options.baseUrl, '/ico', { width: 1440, height: 900 });
    await evaluate(
      client,
      `(() => new Promise(async (resolve) => {
        const routes = ${JSON.stringify(ROUTES.map((route) => route.path))};
        for (const route of routes.concat(routes)) {
          history.pushState({}, '', route);
          dispatchEvent(new PopStateEvent('popstate'));
          await new Promise((done) => setTimeout(done, 250));
          const bg = document.querySelectorAll('[data-crypto-background="true"]').length;
          const canvas = document.querySelectorAll('.crypto-background__canvas').length;
          if (bg !== 1 || canvas !== 1) {
            resolve(JSON.stringify({ ok: false, route, bg, canvas }));
            return;
          }
        }
        resolve(JSON.stringify({ ok: true, bg: document.querySelectorAll('[data-crypto-background="true"]').length, canvas: document.querySelectorAll('.crypto-background__canvas').length }));
      }))()`,
      true
    ).then((serializedResult) => {
      const result = JSON.parse(serializedResult);
      if (!result.ok) {
        throw new Error(`navigation lifecycle duplicate renderer: ${JSON.stringify(result)}`);
      }
    });

    await navigate(client, options.baseUrl, '/ico/tokenomics', { width: 1440, height: 900 });
    measurements.push({
      route: '/ico/tokenomics',
      ...(await evaluate(client, metricExpression, true)),
      ...(await client.send('Runtime.getHeapUsage').catch(() => ({}))),
    });
    await navigate(client, options.baseUrl, '/ico/whitepaper', { width: 1440, height: 900 });
    measurements.push({
      route: '/ico/whitepaper',
      ...(await evaluate(client, metricExpression, true)),
      ...(await client.send('Runtime.getHeapUsage').catch(() => ({}))),
    });

    client.close();
  } finally {
    await new Promise((resolve) => {
      chrome.once('close', resolve);
      chrome.kill('SIGTERM');
      setTimeout(resolve, 1500);
    });
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }

  if (errors.length > 0) {
    throw new Error(`Browser console errors found:\n${errors.join('\n')}`);
  }

  fs.writeFileSync(
    path.join(outputDir, 'crypto-background-browser-results.json'),
    JSON.stringify({ measurements, routes: ROUTES, viewports: VIEWPORTS }, null, 2)
  );

  console.log(JSON.stringify({ ok: true, measurements, outputDir }, null, 2));
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
