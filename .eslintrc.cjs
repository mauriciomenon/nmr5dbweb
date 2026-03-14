module.exports = {
  root: true,
  env: {
    browser: true,
    node: true,
    es2022: true,
  },
  extends: ['eslint:recommended'],
  ignorePatterns: [
    'interface/uploads/**',
    'output/**',
    'node_modules/**',
    'bkp_limpeza/**',
    '.venv/**',
  ],
  overrides: [
    {
      files: ['static/**/*.js'],
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: 'script',
      },
      rules: {
        'no-empty': 'off',
        'no-undef': 'warn',
        'no-unused-vars': 'off',
        'no-var': 'off',
        'prefer-const': 'off',
      },
    },
  ],
};
