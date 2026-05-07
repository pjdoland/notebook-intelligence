// Localized config so the root eslint command can lint ui-tests through
// this folder's own tsconfig instead of being told to skip it. Inherits
// the project root's rules, then opts into Playwright/Node globals.
module.exports = {
  parserOptions: {
    project: './tsconfig.json',
    tsconfigRootDir: __dirname
  },
  env: {
    node: true
  }
};
