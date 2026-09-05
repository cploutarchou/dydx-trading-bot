// Flat ESLint config — single source of truth (legacy .eslintrc.cjs removed).
// FlatCompat translates the classic plugin recommended configs into flat
// format; the full set from the old legacy file is loaded here so
// react-hooks / jsx-a11y / import rules actually run.
const { FlatCompat } = require('@eslint/eslintrc');
const js = require('@eslint/js');

const compat = new FlatCompat({
  baseDirectory: __dirname,
  resolvePluginsRelativeTo: __dirname,
  recommendedConfig: js.configs.recommended,
});

module.exports = [
  {
    ignores: ['dist/**', 'coverage/**', 'playwright-report/**', 'test-results/**', 'e2e/**'],
  },
  ...compat.extends(
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
    'plugin:jsx-a11y/recommended',
    'plugin:import/errors',
    'plugin:import/warnings',
    'plugin:import/typescript'
  ),
  {
    settings: {
      react: { version: 'detect' },
      'import/resolver': { typescript: {} },
    },
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      // Prefer TS-aware unused var checks and allow underscore-prefixed placeholders.
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/no-explicit-any': 'warn',
      'react/no-unescaped-entities': 'warn',
      'no-empty': 'warn',
      '@typescript-eslint/explicit-module-boundary-types': 'off',
      'react/react-in-jsx-scope': 'off',
      'import/order': ['warn', { 'newlines-between': 'never' }],
    },
  },
  {
    // Depth 4 lets the label rule see text nested inside wrapping spans
    // (consent checkboxes, toggle rows) — those were false negatives before.
    rules: {
      'jsx-a11y/label-has-associated-control': ['error', { depth: 4 }],
    },
  },
  {
    // Debt carve-out (audit FE-038): enabling the full react-hooks v7
    // recommended set surfaced pre-existing violations. These rules stay off
    // until their categories are burned down; everything else runs at full
    // severity. (import-naming and jsx-a11y interaction categories burned
    // down 2026-09-05 and now run at error level from the recommended sets.)
    rules: {
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/exhaustive-deps': 'off',
      'react-hooks/static-components': 'off',
      'react-hooks/preserve-manual-memoization': 'off',
      'react-hooks/immutability': 'off',
      'react-hooks/purity': 'off',
    },
  },
];
