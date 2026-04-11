import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { createDecipheriv } from 'node:crypto';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

type JsonValue = string | number | boolean | null | JsonObject | JsonValue[];
type JsonObject = { [key: string]: JsonValue };

const normalizeEnvironmentName = (
  value: string | undefined,
  fallback: 'development' | 'production'
) => {
  const normalized = String(value ?? '')
    .trim()
    .toLowerCase();
  if (normalized === 'prod' || normalized === 'production') return 'production';
  if (normalized === 'dev' || normalized === 'development') return 'development';
  return fallback;
};

const isStructuredConfigRoot = (candidate: string) =>
  existsSync(resolve(candidate, 'config', 'profiles')) ||
  existsSync(resolve(candidate, 'run.json'));

const findRepoRoot = (start: string) => {
  let current = resolve(start);

  while (true) {
    if (
      existsSync(resolve(current, '.github')) &&
      existsSync(resolve(current, 'AGENTS.md')) &&
      isStructuredConfigRoot(current)
    ) {
      return current;
    }

    const parent = dirname(current);
    if (parent === current) {
      throw new Error(
        `Unable to locate monorepo root from ${start}. Expected a parent with .github, AGENTS.md, and config/profiles or run.json.`
      );
    }
    current = parent;
  }
};

const resolveProfilePath = (repoRoot: string, environment: 'development' | 'production') => {
  const explicitRun = String(process.env.APP_RUN_CONFIG_FILE ?? '').trim();
  if (explicitRun.length > 0) {
    return explicitRun;
  }

  const runJson = resolve(repoRoot, 'run.json');
  if (existsSync(runJson)) {
    return runJson;
  }

  const explicit = String(process.env.APP_CONFIG_FILE ?? '').trim();
  if (explicit.length > 0) {
    return explicit;
  }

  const candidates = [
    resolve(repoRoot, 'config', 'profiles', `${environment}.config.enc.json`),
    resolve(repoRoot, 'config', 'profiles', `${environment}.config.json`),
  ];

  const match = candidates.find((candidate) => existsSync(candidate));
  if (!match) {
    throw new Error(`Missing structured config profile. Expected ${candidates.join(' or ')}`);
  }
  return match;
};

const resolveConfigKeyFile = (repoRoot: string) => {
  const explicit = String(process.env.APP_CONFIG_KEY_FILE ?? '').trim();
  return explicit.length > 0 ? explicit : resolve(repoRoot, '.configkey.bin');
};

const decryptPayload = (parsed: JsonObject, repoRoot: string): JsonObject => {
  const keyPath = resolveConfigKeyFile(repoRoot);
  if (!existsSync(keyPath)) {
    throw new Error(
      `Missing config key file. Expected ${keyPath}. Run 'make config-keygen' or install the shared key.`
    );
  }

  const key = readFileSync(keyPath);
  if (key.length !== 32) {
    throw new Error(`Invalid config key length in ${keyPath}. Expected 32 bytes.`);
  }

  const nonce = Buffer.from(String(parsed.nonce ?? ''), 'base64');
  const ciphertext = Buffer.from(String(parsed.ciphertext ?? ''), 'base64');
  const tag = Buffer.from(String(parsed.tag ?? ''), 'base64');
  const decipher = createDecipheriv('aes-256-gcm', key, nonce);
  decipher.setAuthTag(tag);
  const plaintext = Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString(
    'utf-8'
  );
  return JSON.parse(plaintext) as JsonObject;
};

const loadJsonConfig = (path: string, repoRoot: string): JsonObject => {
  const raw = readFileSync(path, 'utf-8');
  const parsed = JSON.parse(raw) as JsonObject;
  const isEncrypted =
    path.endsWith('.config.enc.json') ||
    (typeof parsed === 'object' &&
      parsed !== null &&
      'cipher' in parsed &&
      'nonce' in parsed &&
      'ciphertext' in parsed &&
      'tag' in parsed);
  return isEncrypted ? decryptPayload(parsed, repoRoot) : parsed;
};

const flattenConfig = (tree: JsonObject): Record<string, string> => {
  const flattened: Record<string, string> = {};
  const walk = (node: JsonValue) => {
    if (!node || typeof node !== 'object' || Array.isArray(node)) {
      return;
    }
    Object.entries(node as JsonObject).forEach(([key, value]) => {
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        walk(value);
        return;
      }
      if (typeof value === 'string') flattened[key] = value;
      else if (typeof value === 'number' || typeof value === 'boolean')
        flattened[key] = String(value);
      else if (value == null) flattened[key] = '';
      else flattened[key] = JSON.stringify(value);
    });
  };

  Object.entries(tree).forEach(([section, value]) => {
    if (section === 'metadata') return;
    walk(value);
  });

  return flattened;
};

const loadStructuredEnvironment = (repoRoot: string, mode: string) => {
  const environment = normalizeEnvironmentName(
    process.env.APP_CONFIG_ENV ||
      process.env.CONFIG_ENV ||
      process.env.ENVIRONMENT ||
      process.env.APP_ENV,
    mode === 'production' ? 'production' : 'development'
  );
  const profilePath = resolveProfilePath(repoRoot, environment);
  return flattenConfig(loadJsonConfig(profilePath, repoRoot));
};

export default defineConfig(({ mode }) => {
  const repoRoot = findRepoRoot(__dirname);
  const env = loadStructuredEnvironment(repoRoot, mode);
  const viteDefine = Object.fromEntries(
    Object.entries(env)
      .filter(([key]) => key.startsWith('VITE_'))
      .map(([key, value]) => [`import.meta.env.${key}`, JSON.stringify(value)])
  );

  return {
    plugins: [react()],
    define: viteDefine,
    server: {
      host: '0.0.0.0',
      port: 5173,
      allowedHosts: ['.localhost'],
      proxy: {
        '/api': {
          target: env.VITE_API_URL || 'http://localhost:8888',
          changeOrigin: true,
        },
      },
    },
    build: {
      chunkSizeWarningLimit: 700,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.indexOf('node_modules') === -1) return;

            const modulePath = id.split('node_modules/')[1] || '';
            const pathParts = modulePath.split('/');
            const firstPart = pathParts[0] || '';
            const packageName =
              firstPart.charAt(0) === '@' ? `${pathParts[0]}-${pathParts[1]}` : pathParts[0];

            if (id.indexOf('react-router') !== -1 || id.indexOf('@remix-run') !== -1) {
              return 'router-vendor';
            }

            if (id.indexOf('react-dom') !== -1 || id.indexOf('/react/') !== -1) {
              return 'react-core';
            }

            if (id.indexOf('echarts') !== -1 || id.indexOf('d3') !== -1) {
              return 'charts-vendor';
            }

            if (
              id.indexOf('@mui') !== -1 ||
              id.indexOf('@emotion') !== -1 ||
              id.indexOf('lucide-react') !== -1
            ) {
              return 'ui-vendor';
            }

            if (
              id.indexOf('axios') !== -1 ||
              id.indexOf('dayjs') !== -1 ||
              id.indexOf('lodash') !== -1
            ) {
              return 'utils-vendor';
            }

            if (id.indexOf('cookie') !== -1 || id.indexOf('set-cookie-parser') !== -1) {
              return 'utils-vendor';
            }

            const safePackage = (packageName || 'misc')
              .replace(/^@/, '')
              .replace(/[^a-zA-Z0-9_-]/g, '-');

            return `vendor-${safePackage}`;
          },
        },
      },
    },
  };
});
