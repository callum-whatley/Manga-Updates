/**
 * Mocha setup file (CommonJS).
 *
 * Runs before any test files are loaded. It:
 *   1. Registers tsx/cjs for TypeScript support
 *   2. Resolves the `@/` path alias to `src/`
 *   3. Pre-registers a stub for `@/composables/useApi` so that the manga store
 *      can be imported in a pure Node.js context (no bundler / no import.meta).
 *
 * The stub's methods (get, post, patch, delete) are replaced per-test inside
 * the spec files to control API responses.
 */

'use strict';

require('tsx/cjs');

const path = require('path');
const Module = require('module');
const ROOT = path.join(__dirname, '..');

// ── 1. Resolve @/ alias ───────────────────────────────────────────────────────

const origResolve = Module._resolveFilename;
Module._resolveFilename = function (request, parent, isMain, options) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    request = path.join(ROOT, 'src', request.slice(2));
  }
  return origResolve.call(this, request, parent, isMain, options);
};

// ── 2. Stub out useApi ────────────────────────────────────────────────────────

// Resolve the real path so the cache key matches what the store will request.
const apiPath = path.join(ROOT, 'src', 'composables', 'useApi.ts');

// Create a reusable stub object whose methods tests can replace freely.
const apiStub = {
  get: async () => { throw new Error('api.get not stubbed'); },
  post: async () => { throw new Error('api.post not stubbed'); },
  patch: async () => { throw new Error('api.patch not stubbed'); },
  delete: async () => { throw new Error('api.delete not stubbed'); },
};

// Place it in the require cache so any `require('@/composables/useApi')` (after
// alias resolution) returns this stub instead of loading the real file.
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { default: apiStub, __esModule: true },
  children: [],
  parent: null,
  paths: [],
};

// Expose the stub globally so spec files can reach it without re-importing.
global.__apiStub = apiStub;
