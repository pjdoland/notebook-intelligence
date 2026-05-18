// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { HTML_FRAME_CSP, injectHtmlFrameCsp } from '../../src/html-frame-csp';

describe('HTML_FRAME_CSP', () => {
  it('disables network egress by default', () => {
    expect(HTML_FRAME_CSP).toContain("default-src 'none'");
    expect(HTML_FRAME_CSP).toContain("connect-src 'none'");
    expect(HTML_FRAME_CSP).toContain("frame-src 'none'");
    expect(HTML_FRAME_CSP).toContain("object-src 'none'");
  });

  it('allows inline scripts and styles so self-contained tool HTML renders', () => {
    expect(HTML_FRAME_CSP).toContain("script-src 'unsafe-inline'");
    expect(HTML_FRAME_CSP).toContain("style-src 'unsafe-inline'");
  });

  it('only permits data: images and fonts', () => {
    expect(HTML_FRAME_CSP).toContain('img-src data:');
    expect(HTML_FRAME_CSP).toContain('font-src data:');
  });

  it('blocks base-uri and form-action escape hatches', () => {
    expect(HTML_FRAME_CSP).toContain("base-uri 'none'");
    expect(HTML_FRAME_CSP).toContain("form-action 'none'");
  });

  it('explicitly blocks worker / child / manifest / media sinks', () => {
    expect(HTML_FRAME_CSP).toContain("worker-src 'none'");
    expect(HTML_FRAME_CSP).toContain("child-src 'none'");
    expect(HTML_FRAME_CSP).toContain("manifest-src 'none'");
    expect(HTML_FRAME_CSP).toContain("media-src 'none'");
  });
});

describe('injectHtmlFrameCsp', () => {
  const META_RE =
    /^<meta http-equiv="Content-Security-Policy" content="[^"]+">/;

  it('always prepends the CSP meta so it sees the document first', () => {
    expect(injectHtmlFrameCsp('<p>hi</p>')).toMatch(META_RE);
    expect(injectHtmlFrameCsp('<p>hi</p>')).toContain('<p>hi</p>');
  });

  it('prepends even when the source opens its own <head>', () => {
    // Author-supplied <head> must not get the meta inserted "inside" it
    // by a regex that could be fooled by <head> in a comment or
    // <noscript>. Prepending puts the meta before any author-controlled
    // bytes; the browser tokenizer wraps it in a synthetic <head> ahead
    // of the author's opening <head>.
    const src = '<html><head><title>x</title></head><body>y</body></html>';
    expect(injectHtmlFrameCsp(src)).toMatch(META_RE);
  });

  it('prepends before a DOCTYPE-prefixed document', () => {
    const src = '<!DOCTYPE html><html><head></head><body>y</body></html>';
    const out = injectHtmlFrameCsp(src);
    expect(out).toMatch(META_RE);
    expect(out.indexOf('<meta')).toBeLessThan(out.indexOf('<!DOCTYPE'));
  });

  it('is unaffected by <head> hiding in a comment', () => {
    // The pre-fix regex strategy could be confused by this construction.
    // Pin the always-prepend behavior so a future refactor cannot
    // re-introduce that gap.
    const src = '<!--<head>--><head><script>x</script></head>';
    const out = injectHtmlFrameCsp(src);
    expect(out).toMatch(META_RE);
    expect(out.indexOf('<meta')).toBeLessThan(out.indexOf('<!--'));
  });

  it('places the meta before any <script> in the document', () => {
    const src = '<html><body><script>alert(1)</script></body></html>';
    const out = injectHtmlFrameCsp(src);
    const metaIdx = out.indexOf('<meta');
    const scriptIdx = out.indexOf('<script');
    expect(metaIdx).toBeGreaterThanOrEqual(0);
    expect(scriptIdx).toBeGreaterThan(metaIdx);
  });

  it('does not deduplicate when called twice (idempotency caveat)', () => {
    // Two metas are harmless: per CSP spec the strictest policy wins.
    // Pin this so a future caller does not quietly accumulate metas in
    // an unexpected configuration.
    const first = injectHtmlFrameCsp('<p>x</p>');
    const second = injectHtmlFrameCsp(first);
    const count = (second.match(/Content-Security-Policy/g) || []).length;
    expect(count).toBe(2);
  });

  it('returns the bare meta when source is empty or nullish', () => {
    expect(injectHtmlFrameCsp('')).toMatch(META_RE);
    expect(injectHtmlFrameCsp(null)).toMatch(META_RE);
    expect(injectHtmlFrameCsp(undefined)).toMatch(META_RE);
  });
});
