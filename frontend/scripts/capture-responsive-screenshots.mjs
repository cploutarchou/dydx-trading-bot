#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

const VIEWPORTS = [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
];

function parseArgs(argv) {
  const options = {
    baseUrl: 'http://localhost:5173',
    manifestPath: 'scripts/responsive-screenshot-routes.json',
    outputDir: 'docs/screenshots/responsive',
    browserPath: '',
    userDataDir: '',
    profileDirectory: '',
    dryRun: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    switch (arg) {
      case '--base-url':
        options.baseUrl = argv[++index] ?? options.baseUrl;
        break;
      case '--manifest-path':
        options.manifestPath = argv[++index] ?? options.manifestPath;
        break;
      case '--output-dir':
        options.outputDir = argv[++index] ?? options.outputDir;
        break;
      case '--browser-path':
        options.browserPath = argv[++index] ?? options.browserPath;
        break;
      case '--user-data-dir':
        options.userDataDir = argv[++index] ?? options.userDataDir;
        break;
      case '--profile-directory':
        options.profileDirectory = argv[++index] ?? options.profileDirectory;
        break;
      case '--dry-run':
        options.dryRun = true;
        break;
      case '--help':
        printHelp();
        process.exit(0);
      case '-h':
        printHelp();
        process.exit(0);
      default:
        throw new Error(`Unknown argument: ${arg}`);
    }
  }

  return options;
}

function printHelp() {
  console.log(
    `Usage: node scripts/capture-responsive-screenshots.mjs [options]\n\nOptions:\n  --base-url URL              Frontend base URL (default: http://localhost:5173)\n  --manifest-path PATH        Route manifest path relative to frontend/\n  --output-dir PATH           Output directory relative to frontend/\n  --browser-path PATH         Explicit browser executable path\n  --user-data-dir PATH        Existing Chromium/Chrome/Edge user data directory\n  --profile-directory NAME    Profile directory inside the user data directory\n  --dry-run                   Print planned captures without launching browser\n  --help                      Show this help message`
  );
}

function commandExists(command) {
  const result = spawnSync('which', [command], { encoding: 'utf-8' });
  return result.status === 0 ? result.stdout.trim() : '';
}

function detectBrowser(explicitPath) {
  const macCandidates = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ];
  const linuxCommands = [
    'google-chrome',
    'google-chrome-stable',
    'chromium',
    'chromium-browser',
    'microsoft-edge',
    'microsoft-edge-stable',
  ];

  if (explicitPath) {
    const resolved = path.resolve(explicitPath);
    if (fs.existsSync(resolved)) {
      return resolved;
    }
    throw new Error(`Browser executable not found: ${resolved}`);
  }

  for (const candidate of macCandidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  for (const command of linuxCommands) {
    const resolved = commandExists(command);
    if (resolved) {
      return resolved;
    }
  }

  throw new Error('Could not find Chrome/Chromium/Edge. Pass --browser-path explicitly.');
}

function ensureDirectory(targetPath) {
  fs.mkdirSync(targetPath, { recursive: true });
}

function createCaptureProfile(userDataDir, profileDirectory) {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'dydx-responsive-capture-'));

  if (!userDataDir) {
    return tempRoot;
  }

  const resolvedUserDataDir = path.resolve(userDataDir);
  if (!fs.existsSync(resolvedUserDataDir)) {
    throw new Error(`User data directory not found: ${resolvedUserDataDir}`);
  }

  const localStateSource = path.join(resolvedUserDataDir, 'Local State');
  if (fs.existsSync(localStateSource)) {
    fs.copyFileSync(localStateSource, path.join(tempRoot, 'Local State'));
  }

  if (profileDirectory) {
    const profileSource = path.join(resolvedUserDataDir, profileDirectory);
    if (!fs.existsSync(profileSource)) {
      throw new Error(`Profile directory not found: ${profileSource}`);
    }
    fs.cpSync(profileSource, path.join(tempRoot, profileDirectory), { recursive: true });
  }

  return tempRoot;
}

function runCapture(browserPath, args, dryRun) {
  if (dryRun) {
    console.log(`DRY RUN  -> ${args.at(-1)}`);
    console.log(`           ${args.join(' ')}`);
    return;
  }

  const result = spawnSync(browserPath, args, { stdio: 'inherit' });
  if (result.status !== 0) {
    throw new Error(`Screenshot capture failed with exit code ${result.status}`);
  }
}

function buildCaptureUrl(baseUrl, routePath) {
  const base = baseUrl.replace(/\/$/, '');
  const url = new URL(`${base}${routePath}`);
  url.searchParams.set('qa_screenshots', '1');
  return url.toString();
}

function main() {
  if (process.platform === 'win32') {
    throw new Error('This script supports macOS and Linux only.');
  }

  const options = parseArgs(process.argv.slice(2));
  const browserPath = detectBrowser(options.browserPath);
  const manifestFullPath = path.resolve(projectRoot, options.manifestPath);
  const outputFullPath = path.resolve(projectRoot, options.outputDir);

  if (!fs.existsSync(manifestFullPath)) {
    throw new Error(`Manifest file not found: ${manifestFullPath}`);
  }

  ensureDirectory(outputFullPath);

  const routes = JSON.parse(fs.readFileSync(manifestFullPath, 'utf-8'));
  let captureUserDataDir = '';

  try {
    captureUserDataDir = createCaptureProfile(options.userDataDir, options.profileDirectory);

    console.log(`Using browser: ${browserPath}`);
    console.log(`Manifest: ${manifestFullPath}`);
    console.log(`Output:   ${outputFullPath}`);
    if (captureUserDataDir) {
      console.log(`Profile clone: ${captureUserDataDir}`);
    }

    for (const route of routes) {
      for (const viewport of VIEWPORTS) {
        const fileName = `${route.routeKey}-${viewport.width}.png`;
        const targetUrl = buildCaptureUrl(options.baseUrl, route.path);
        const targetOutput = path.join(outputFullPath, fileName);
        const args = [
          '--headless=new',
          '--disable-gpu',
          '--disable-extensions',
          '--disable-component-extensions-with-background-pages',
          '--no-first-run',
          '--no-default-browser-check',
          '--hide-scrollbars',
          '--run-all-compositor-stages-before-draw',
          '--virtual-time-budget=10000',
          `--window-size=${viewport.width},${viewport.height}`,
          `--screenshot=${targetOutput}`,
        ];

        args.unshift(`--user-data-dir=${captureUserDataDir}`);

        if (options.profileDirectory) {
          args.unshift(`--profile-directory=${options.profileDirectory}`);
        }

        args.push(targetUrl);

        console.log(`CAPTURE  -> ${targetUrl} [${viewport.width}x${viewport.height}]`);
        runCapture(browserPath, args, options.dryRun);
      }
    }

    console.log('Responsive screenshot capture plan complete.');
  } finally {
    if (captureUserDataDir && fs.existsSync(captureUserDataDir)) {
      fs.rmSync(captureUserDataDir, { recursive: true, force: true });
    }
  }
}

try {
  main();
} catch (error) {
  console.error(`Error: ${error.message}`);
  process.exit(1);
}
