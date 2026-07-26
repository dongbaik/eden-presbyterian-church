// Collect every Google Photos album link from https://photos.google.com/albums
//
// Run this with the run_playwright_code tool against a SHARED, LOGGED-IN
// Google Photos tab. It returns a JSON string ready to pipe into
// ../scripts/merge_albums.py.
//
// The album grid is virtualised, so tiles unmount as they scroll out of view.
// This walks top -> bottom (which fixes the order) and then bottom -> top to
// fill in any titles that were missing on the first pass.

const albums = await page.evaluate(async () => {
  const order = [];
  const labels = new Map();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const collect = () => {
    for (const a of document.querySelectorAll('a[href*="/share/"]')) {
      const href = a.href;
      if (!labels.has(href)) {
        order.push(href);
        labels.set(href, '');
      }
      const label = (a.getAttribute('aria-label') || a.innerText || '').trim();
      if (label && !labels.get(href)) labels.set(href, label);
    }
  };

  const scroller = document.scrollingElement;
  scroller.scrollTop = 0;
  await sleep(1200);
  collect();

  for (let i = 0; i < 80; i++) {
    scroller.scrollTop += window.innerHeight * 0.5;
    await sleep(600);
    collect();
    if (scroller.scrollTop + window.innerHeight >= scroller.scrollHeight - 5) break;
  }
  for (let i = 0; i < 80; i++) {
    scroller.scrollTop -= window.innerHeight * 0.5;
    await sleep(600);
    collect();
    if (scroller.scrollTop <= 5) break;
  }
  await sleep(600);
  collect();

  return order.map((href) => {
    const raw = labels.get(href) || '';
    const lines = raw.split('\n').map((s) => s.trim()).filter(Boolean);
    const first = lines[0] || '';
    return {
      url: href,
      title: first && !/items/.test(first) ? first : '',
    };
  });
});

return JSON.stringify(albums, null, 2);
