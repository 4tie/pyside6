// Feature: web-ui-redesign, Property 1: Design Token Parity Across Themes
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const cssContent = fs.readFileSync(
  path.resolve(__dirname, '../styles/theme.css'),
  'utf-8'
);

/**
 * Extract the content of a CSS block matching a given selector.
 * Returns the text between the first `{` and its matching `}`.
 */
function extractBlock(css: string, selector: string): string {
  const idx = css.indexOf(selector);
  if (idx === -1) return '';
  const start = css.indexOf('{', idx);
  if (start === -1) return '';
  let depth = 0;
  let end = start;
  for (let i = start; i < css.length; i++) {
    if (css[i] === '{') depth++;
    else if (css[i] === '}') {
      depth--;
      if (depth === 0) { end = i; break; }
    }
  }
  return css.slice(start + 1, end);
}

const rootBlock = extractBlock(cssContent, ':root {');
// Use the more specific selector to avoid matching :root { itself
const lightBlock = extractBlock(cssContent, ":root[data-theme='light']");

const newTokenNames = [
  '--text-xs',
  '--text-sm',
  '--text-base',
  '--text-lg',
  '--text-xl',
  '--text-2xl',
  '--space-1',
  '--space-2',
  '--space-3',
  '--space-4',
  '--space-5',
  '--space-6',
  '--shadow-sm',
  '--shadow-md',
];

/**
 * Validates: Requirements 1.1, 1.2, 1.3, 1.4
 *
 * Property 1: Design Token Parity Across Themes
 * For any token name in the new token set, theme.css must define it in
 * both :root and :root[data-theme='light'].
 */
describe('Property 1: Design Token Parity Across Themes', () => {
  it('every new token is defined in both :root and :root[data-theme="light"]', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...newTokenNames),
        (token) => {
          const inRoot = rootBlock.includes(token + ':') || rootBlock.includes(token + ' :');
          const inLight = lightBlock.includes(token + ':') || lightBlock.includes(token + ' :');
          expect(inRoot, `Token "${token}" missing from :root block`).toBe(true);
          expect(inLight, `Token "${token}" missing from :root[data-theme='light'] block`).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });
});

// Feature: web-ui-redesign, Property 2: Existing Token Preservation
const existingTokenNames = [
  '--bg',
  '--surface',
  '--surface-2',
  '--surface-3',
  '--text',
  '--muted',
  '--border',
  '--accent',
  '--accent-strong',
  '--amber',
  '--red',
  '--green',
  '--blue',
  '--shadow',
  '--radius',
  '--font',
];

/**
 * Validates: Requirements 1.5
 *
 * Property 2: Existing Token Preservation
 * For any token name in the existing token set, the updated theme.css
 * must still define it in :root.
 */
describe('Property 2: Existing Token Preservation', () => {
  it('every existing token is still defined in :root', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...existingTokenNames),
        (token) => {
          const inRoot = rootBlock.includes(token + ':') || rootBlock.includes(token + ' :');
          expect(inRoot, `Existing token "${token}" is missing from :root block`).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });
});
