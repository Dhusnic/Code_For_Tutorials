Playwright is a powerful end-to-end testing framework for web applications. When using it with TypeScript, you can create efficient, maintainable, and scalable test scripts. Below is the "20%" of key concepts that will help you understand the "80%" of Playwright with TypeScript:

### 1. **Installation & Setup**
   - Install Playwright and TypeScript:
     ```bash
     npm init playwright@latest
     npm install typescript
     ```
   - Configure `tsconfig.json`:
     ```json
     {
       "compilerOptions": {
         "target": "ESNext",
         "module": "CommonJS",
         "outDir": "./dist",
         "strict": true,
         "esModuleInterop": true
       }
     }
     ```
   This ensures TypeScript compiles to modern JavaScript while supporting Playwright.

### 2. **Basic Playwright Syntax**
   - **Launching a browser:**
     ```typescript
     import { chromium } from 'playwright';

     (async () => {
       const browser = await chromium.launch();
       const page = await browser.newPage();
       await page.goto('https://example.com');
       await browser.close();
     })();
     ```
   - **Key browsers** supported: `chromium`, `firefox`, `webkit`.

### 3. **Selectors**
   - Playwright uses CSS selectors by default:
     ```typescript
     await page.click('button#submit');
     await page.fill('input[name="username"]', 'user123');
     ```
   - **Best practices**: Use `data-test-id` or other custom attributes to make selectors robust and less prone to change.

### 4. **Assertions**
   Playwright integrates with `@playwright/test` for built-in assertions.
   ```typescript
   import { test, expect } from '@playwright/test';

   test('basic test', async ({ page }) => {
     await page.goto('https://example.com');
     const title = await page.title();
     expect(title).toBe('Example Domain');
   });
   ```

### 5. **Waits and Timings**
   - **Automatic waiting**: Playwright waits for elements to be actionable (e.g., visible, clickable).
   - Explicit waits can be used if necessary:
     ```typescript
     await page.waitForSelector('text=Success');
     ```

### 6. **Parallel and Sequential Testing**
   Playwright allows running tests in parallel by default.
   - To run tests sequentially, add this to `playwright.config.ts`:
     ```typescript
     use: {
       workers: 1
     }
     ```

### 7. **Headless and Headed Mode**
   By default, Playwright runs in headless mode (without GUI). You can enable the browser GUI with:
   ```typescript
   const browser = await chromium.launch({ headless: false });
   ```

### 8. **Handling Forms and Inputs**
   Playwright provides utilities for handling forms easily:
   ```typescript
   await page.fill('input[name="email"]', 'test@example.com');
   await page.click('button[type="submit"]');
   ```

### 9. **Screenshots and Videos**
   Useful for debugging tests:
   ```typescript
   await page.screenshot({ path: 'screenshot.png' });
   await page.video.saveAs('video.mp4');
   ```

### 10. **Handling Dialogs & Alerts**
   To interact with dialogs (alerts, confirms):
   ```typescript
   page.on('dialog', async dialog => {
     console.log(dialog.message());
     await dialog.accept();
   });
   ```

### 11. **Keyboard and Mouse Simulation**
   - **Keyboard:** `await page.keyboard.press('Enter');`
   - **Mouse:** `await page.mouse.click(100, 200);`

### 12. **Fixtures and Hooks**
   Use `beforeAll`, `afterAll`, `beforeEach`, and `afterEach` to manage test setup and teardown.
   ```typescript
   test.beforeAll(async () => { /* setup */ });
   test.afterAll(async () => { /* teardown */ });
   ```

### 13. **Network Interception**
   Playwright allows mocking and intercepting network requests:
   ```typescript
   await page.route('**/api/**', route => route.fulfill({ body: '{"success": true}' }));
   ```

### 14. **Custom Test Fixtures**
   Create reusable code patterns across tests:
   ```typescript
   test.use({ baseURL: 'https://example.com' });
   ```

### 15. **Continuous Integration (CI)**
   Integrate Playwright tests with CI tools like GitHub Actions:
   ```yaml
   jobs:
     tests:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v2
         - name: Run tests
           run: npm run test
   ```

### 16. **Cross-browser Testing**
   Playwright allows you to test on multiple browsers:
   ```typescript
   for (const browserType of [chromium, firefox, webkit]) {
     const browser = await browserType.launch();
     // Run tests...
     await browser.close();
   }
   ```

### 17. **Emulating Devices and Geolocation**
   Playwright supports emulation for devices and geo-locations:
   ```typescript
   const iPhone = playwright.devices['iPhone 12'];
   const page = await browser.newPage({ ...iPhone });
   ```

### 18. **Handling Frames and IFrames**
   To interact with iframes:
   ```typescript
   const frame = page.frame({ url: /.*iframe-url.*/ });
   await frame.click('button');
   ```

### 19. **API Testing**
   Playwright can be used for API testing:
   ```typescript
   const response = await page.request.get('/api/data');
   expect(response.ok()).toBeTruthy();
   ```

### 20. **Error Handling & Debugging**
   - Use Playwright's built-in tracing:
     ```typescript
     test('test with trace', async ({ page }) => {
       await page.tracing.start({ screenshots: true, snapshots: true });
       await page.goto('https://example.com');
       await page.tracing.stop({ path: 'trace.zip' });
     });
     ```

By focusing on these core aspects, you’ll cover most of the commonly used Playwright TypeScript features needed for end-to-end testing.