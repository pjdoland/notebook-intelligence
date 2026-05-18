// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

/**
 * Content-Security-Policy injected into every HTMLFrame blob document.
 *
 * The iframe already runs with sandbox="allow-scripts" (no allow-same-origin),
 * so cookies and parent DOM are unreachable. But scripts in a null-origin
 * context can still fetch() to any URL the user's browser can reach:
 * cluster intranet, 169.254.169.254 cloud metadata, the Jupyter server
 * itself. Inline scripts/styles stay enabled because most LLM/tool HTML
 * output (matplotlib, plotly, custom dashboards) is self-contained inline;
 * external CDN loads and any network egress are blocked. img/font are
 * allowed only as data: URIs so inline visualizations still render.
 */
export const HTML_FRAME_CSP = [
  "default-src 'none'",
  "script-src 'unsafe-inline'",
  "style-src 'unsafe-inline'",
  'img-src data:',
  'font-src data:',
  "connect-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "frame-src 'none'",
  "child-src 'none'",
  "worker-src 'none'",
  "manifest-src 'none'",
  "media-src 'none'",
  "object-src 'none'"
].join('; ');

const CSP_META_TAG = `<meta http-equiv="Content-Security-Policy" content="${HTML_FRAME_CSP}">`;

/**
 * Prepend the CSP `<meta>` tag to untrusted HTML so the resulting blob
 * document boots under policy.
 *
 * Always prepend rather than trying to locate `<head>`: an HTML-naive
 * regex can be fooled by `<head>` inside a comment, `<noscript>`,
 * `<textarea>`, or a `<![CDATA[ ]]>` block, which would let the actual
 * `<head>` parsed by the browser run unguarded. Prepending puts the
 * meta before everything; the browser's tokenizer folds a leading meta
 * into the synthetic `<head>` it builds, ahead of any author-supplied
 * `<head>` opening tag.
 */
export function injectHtmlFrameCsp(source: string | null | undefined): string {
  if (!source) {
    return CSP_META_TAG;
  }
  return CSP_META_TAG + source;
}
