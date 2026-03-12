import js from '@eslint/js';
import globals from 'globals';

export default [
  {
    ignores: [
      'interface/uploads/**',
      'output/**',
      'node_modules/**',
      'bkp_limpeza/**',
      '.venv/**',
    ],
  },
  js.configs.recommended,
  {
    files: ['static/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      'no-empty': 'off',
      'no-undef': 'off',
      'no-useless-assignment': 'off',
      'no-unused-vars': 'off',
      'no-var': 'off',
      'prefer-const': 'off',
    },
  },
];
