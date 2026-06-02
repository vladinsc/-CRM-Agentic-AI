const badge = document.getElementById("pageBadge");
const hint = document.getElementById("hint");
const scrapeBtn = document.getElementById("scrapeBtn");
const pagesInput = document.getElementById("pages");
const statusEl = document.getElementById("status");
const autoUrl = document.getElementById("autoUrl");
const autoBtn = document.getElementById("autoBtn");

const SALES_SEARCH_RE = /^https:\/\/www\.linkedin\.com\/sales\/search\//;

let activeTab = null;

async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  activeTab = tab;

  if (tab && SALES_SEARCH_RE.test(tab.url || "")) {
    badge.textContent = "ready";
    badge.className = "badge ok";
    hint.textContent = "You're on a Sales Navigator search. Ready to scrape.";
    scrapeBtn.disabled = false;
  } else {
    badge.textContent = "not on search";
    badge.className = "badge warn";
    hint.textContent =
      "Navigate to a LinkedIn Sales Navigator people-search page, then reopen this.";
    scrapeBtn.disabled = true;
  }
}

// Both buttons kick off a scrape that runs entirely in the SERVICE WORKER using
// a dedicated background tab. The popup does NOT need to stay open — closing it
// (or switching tabs) does not stop or reset the scrape. Live progress + final
// results are visible in the CRM's "Scraping jobs" panel.
function startScrape(url, maxPages, btn) {
  if (!SALES_SEARCH_RE.test(url)) {
    statusEl.innerHTML =
      '<div class="err">Open or paste a valid Sales Navigator search URL (linkedin.com/sales/search/…).</div>';
    return;
  }
  btn.disabled = true;
  statusEl.innerHTML =
    '<div class="muted">Scrape started in the background. You can close this popup or switch tabs — ' +
    "it keeps running. Watch progress in the CRM under <strong>Scraping jobs</strong>.</div>";

  // Fire-and-forget: we do NOT rely on the response callback (it dies when the
  // popup closes). The service worker owns the whole job from here.
  chrome.runtime.sendMessage({ type: "START_AUTO_SCRAPE", payload: { url, maxPages } });

  // Re-enable shortly so the user can queue another if they want.
  setTimeout(() => { btn.disabled = false; }, 2500);
}

scrapeBtn.addEventListener("click", () => {
  const maxPages = Math.min(10, Math.max(1, parseInt(pagesInput.value) || 1));
  startScrape(activeTab && activeTab.url, maxPages, scrapeBtn);
});

autoBtn.addEventListener("click", () => {
  const maxPages = Math.min(10, Math.max(1, parseInt(pagesInput.value) || 1));
  startScrape(autoUrl.value.trim(), maxPages, autoBtn);
});

init();
