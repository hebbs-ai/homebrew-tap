import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts'],
    exclude: ['tests/e2e/**', 'tests/integration/**', 'node_modules/**'],
    testTimeout: 30_000,
  },
});
