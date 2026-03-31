// eslint.config.cjs - Flat config that loads existing .eslintrc via FlatCompat
const { FlatCompat } = require('@eslint/eslintrc');
const js = require('@eslint/js');
const path = require('path');

const compat = new FlatCompat({
  baseDirectory: __dirname,
  resolvePluginsRelativeTo: __dirname,
  recommendedConfig: js.configs.recommended,
});

module.exports = [
  // Translate our existing .eslintrc.cjs extensions/plugins/rules into flat format
  ...compat.extends('plugin:react/recommended', 'plugin:@typescript-eslint/recommended', 'eslint:recommended'),
  ...compat.plugins('react', '@typescript-eslint', 'react-hooks', 'jsx-a11y', 'import'),
  ...compat.config({
    env: { browser: true, node: true, es2024: true },
    parser: '@typescript-eslint/parser',
    parserOptions: { ecmaVersion: 2024, sourceType: 'module', ecmaFeatures: { jsx: true } },
    settings: { react: { version: 'detect' } },
    rules: {
      // Prefer TS-aware unused var checks and allow underscore-prefixed placeholders.
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
      // Legacy codebase currently uses many explicit anys; keep visible as warnings for cleanup.
      '@typescript-eslint/no-explicit-any': 'warn',
      // Keep signal without blocking for common JSX text and placeholder blocks.
      'react/no-unescaped-entities': 'warn',
      'no-empty': 'warn',
      '@typescript-eslint/explicit-module-boundary-types': 'off',
      'react/react-in-jsx-scope': 'off',
      'import/order': ['warn', { 'newlines-between': 'never' }],
    },
  }),
];

