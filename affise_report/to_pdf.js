// Render the HTML report to an A4 PDF: node to_pdf.js <in.html> <out.pdf>
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + require('path').resolve(process.argv[2]));
  await page.pdf({
    path: process.argv[3], format: 'A4', printBackground: true,
    margin: { top: '12mm', bottom: '12mm', left: '10mm', right: '10mm' },
  });
  await browser.close();
})();
