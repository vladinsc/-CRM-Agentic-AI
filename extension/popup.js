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

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "SCRAPE_PROGRESS") {
    const { page, totalMatched, totalRejected, lastBatch } = msg.progress;
    statusEl.innerHTML =
      `<div>Page ${page}: +${lastBatch} found · ` +
      `<strong>${totalMatched ?? 0}</strong> matched · ${totalRejected ?? 0} skipped</div>`;
  }
});

function renderResult(resp, ...btns) {
  btns.forEach((b) => (b.disabled = false));
  if (chrome.runtime.lastError) {
    statusEl.innerHTML = `<div class="err">${chrome.runtime.lastError.message}</div>`;
    return;
  }
  if (resp && resp.ok) {
    const r = resp.result || {};
    statusEl.innerHTML =
      `<div class="ok" style="color:#16a34a"><strong>Done.</strong> ` +
      `${r.totalMatched ?? r.totalAccepted ?? 0} matched your ICP and were added; ` +
      `${r.totalRejected ?? 0} didn't match. AI research is running on the matches.</div>`;
  } else {
    statusEl.innerHTML = `<div class="err">${(resp && resp.error) || "Scrape failed"}</div>`;
  }
}

scrapeBtn.addEventListener("click", () => {
  const maxPages = Math.min(10, Math.max(1, parseInt(pagesInput.value) || 1));
  scrapeBtn.disabled = true;
  statusEl.innerHTML = '<div class="muted">Starting…</div>';

  chrome.runtime.sendMessage(
    {
      type: "START_SCRAPE",
      payload: { tabId: activeTab.id, query: activeTab.url, maxPages },
    },
    (resp) => renderResult(resp, scrapeBtn)
  );
});

autoBtn.addEventListener("click", () => {
  const url = autoUrl.value.trim();
  if (!SALES_SEARCH_RE.test(url)) {
    statusEl.innerHTML =
      '<div class="err">Paste a valid Sales Navigator search URL (linkedin.com/sales/search/…).</div>';
    return;
  }
  const maxPages = Math.min(10, Math.max(1, parseInt(pagesInput.value) || 1));
  autoBtn.disabled = true;
  statusEl.innerHTML = '<div class="muted">Opening background tab and scraping…</div>';

  chrome.runtime.sendMessage(
    { type: "START_AUTO_SCRAPE", payload: { url, maxPages } },
    (resp) => renderResult(resp, autoBtn)
  );
});

init();
