import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const themeCss = fs.readFileSync(
  path.resolve(__dirname, '../styles/theme.css'),
  'utf-8'
);

const appCss = fs.readFileSync(
  path.resolve(__dirname, '../styles/app.css'),
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

// ── theme.css token assertions ────────────────────────────────────────────────

const rootBlock = extractBlock(themeCss, ':root {');
const lightBlock = extractBlock(themeCss, ":root[data-theme='light']");

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

describe('theme.css — new design tokens', () => {
  for (const token of newTokenNames) {
    it(`"${token}" is defined in :root`, () => {
      expect(rootBlock).toMatch(new RegExp(token + '\\s*:'));
    });

    it(`"${token}" is defined in :root[data-theme='light']`, () => {
      expect(lightBlock).toMatch(new RegExp(token + '\\s*:'));
    });
  }
});

// ── app.css rule assertions ───────────────────────────────────────────────────

describe('app.css — panel shadow', () => {
  it('.panel rule contains box-shadow: var(--shadow-sm)', () => {
    const panelBlock = extractBlock(appCss, '.panel {');
    expect(panelBlock).toContain('box-shadow: var(--shadow-sm)');
  });
});

describe('app.css — disabled button opacity', () => {
  it('.button:disabled or .icon-button:disabled rule contains opacity: 0.45', () => {
    // The rule may span both selectors; search the full CSS for the declaration
    // near the disabled selector
    const disabledIdx = appCss.indexOf('.button:disabled');
    expect(disabledIdx, '.button:disabled selector not found').toBeGreaterThan(-1);
    const blockStart = appCss.indexOf('{', disabledIdx);
    const blockEnd = appCss.indexOf('}', blockStart);
    const disabledBlock = appCss.slice(blockStart + 1, blockEnd);
    expect(disabledBlock).toContain('opacity: 0.45');
  });
});

describe('app.css — alert error left border', () => {
  it('.alert.error rule contains border-left-color: var(--red)', () => {
    const alertErrorBlock = extractBlock(appCss, '.alert.error');
    expect(alertErrorBlock).toContain('border-left-color: var(--red)');
  });
});

describe('app.css — active nav link accent bar', () => {
  it('.nav-link.active::before rule contains background: var(--accent)', () => {
    const beforeBlock = extractBlock(appCss, '.nav-link.active::before');
    expect(beforeBlock).toContain('background: var(--accent)');
  });
});

describe('app.css — workflow step classes', () => {
  it('.workflow-step rule is present', () => {
    expect(appCss).toContain('.workflow-step');
  });

  it('.step-badge rule is present', () => {
    expect(appCss).toContain('.step-badge');
  });
});
