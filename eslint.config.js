const js = require('@eslint/js');
const globals = require('globals');

module.exports = [
  {
    ignores: ['interface/uploads/**', 'output/**'],
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
