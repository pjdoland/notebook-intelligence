import { expect, test } from '@jupyterlab/galata';

test.describe('notebook-intelligence extension', () => {
  test('lab loads with the labextension installed', async ({ page }) => {
    // Galata waits for lab's main shell to render before resolving the page
    // fixture, so by the time the test body runs the extension's
    // ``activate()`` hook should already have fired.
    const installed = await page.evaluate(() => {
      // The extension registers itself on window.jupyterapp via JupyterLab's
      // standard plugin system; presence of either the plugin id or the
      // labextension manifest entry is enough to confirm it loaded.
      const app = (window as any).jupyterapp;
      if (!app) return false;
      const ids: string[] = app.listPlugins();
      return ids.some(id => id.startsWith('@notebook-intelligence/'));
    });
    expect(installed).toBe(true);
  });

  test('chat sidebar can be opened from the side panel', async ({ page }) => {
    // The sidebar tab is registered with a stable id; clicking it should
    // toggle the panel into view. Once visible, the sidebar root element
    // (``.sidebar``) lives in the lab DOM.
    const sidebarTab = page
      .locator('[data-id^="@notebook-intelligence"]')
      .first();
    await expect(sidebarTab).toBeVisible({ timeout: 30_000 });
    await sidebarTab.click();
    await expect(page.locator('.sidebar').first()).toBeVisible();
  });
});
