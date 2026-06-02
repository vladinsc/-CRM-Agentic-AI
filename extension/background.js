// Service worker: owns auth + all core-api calls. Centralizing fetch here (rather
// than in the content script) keeps the JWT out of the page context and avoids
// page-origin CORS issues.

import { API_BASE, AUTH_COOKIE_NAME } from "./config.js";

async function getAuthToken() {
  // chrome.cookies CAN read httpOnly cookies (page JS cannot).
  const cookie = await chrome.cookies.get({
    url: API_BASE,
    name: AUTH_COOKIE_NAME,
  });
  return cookie ? cookie.value : null;
}

async function apiFetch(path, { method = "GET", body, token } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

function sendToTab(tabId, message) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, (resp) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(resp);
      }
    });
  });
}

// Guarantees the content script is present in the tab before we message it.
// (Manifest injection only happens on page loads AFTER the extension is
// installed, so an already-open Sales Nav tab would have no receiver.)
async function ensureContentScript(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content.js"],
    });
  } catch (e) {
    // If it's already injected, a duplicate injection may throw — that's fine.
    console.warn("ensureContentScript:", e.message);
  }
}

// Drives the page-by-page scrape of an already-prepared tab into an existing job.
async function scrapeTabIntoJob({ tabId, jobId, maxPages, token }, onProgress) {
  let totalMatched = 0;
  let totalRejected = 0;
  for (let page = 1; page <= maxPages; page++) {
    const pageResp = await sendToTab(tabId, { type: "SCRAPE_CURRENT_PAGE" });
    const leads = (pageResp && pageResp.leads) || [];

    if (leads.length > 0) {
      const result = await apiFetch(`/scraper/ext/jobs/${jobId}/leads`, {
        method: "POST",
        body: { leads },
        token,
      });
      totalMatched += result.matched ?? result.accepted ?? 0;
      totalRejected += result.rejected ?? 0;
    }

    onProgress({ page, totalMatched, totalRejected, lastBatch: leads.length });

    if (page < maxPages) {
      const nav = await sendToTab(tabId, { type: "GO_NEXT_PAGE" });
      if (!nav || !nav.hasNext) break;
    }
  }

  await apiFetch(`/scraper/ext/jobs/${jobId}`, {
    method: "PATCH",
    body: { status: "completed" },
    token,
  });

  return { jobId, totalMatched, totalRejected };
}

// Phase 1: scrape the tab the user is already viewing.
async function runScrape({ tabId, query, maxPages }, onProgress) {
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Not logged in. Open the CRM web app and log in first.");
  }
  // Create the job first so an ICP block (400) surfaces before we touch the page.
  const job = await apiFetch("/scraper/ext/jobs", {
    method: "POST",
    body: { query },
    token,
  });
  await ensureContentScript(tabId);
  return scrapeTabIntoJob({ tabId, jobId: job.id, maxPages, token }, onProgress);
}

// Phase 2: open a pasted Sales Nav URL in a background tab, scrape it, close it.
async function runAutoScrape({ url, maxPages }, onProgress) {
  const token = await getAuthToken();
  if (!token) {
    throw new Error("Not logged in. Open the CRM web app and log in first.");
  }
  // Create the job first — if no active ICP, this 400s before opening any tab.
  const job = await apiFetch("/scraper/ext/jobs", {
    method: "POST",
    body: { query: url },
    token,
  });

  const tab = await chrome.tabs.create({ url, active: false });
  try {
    await waitForTabComplete(tab.id);
    await ensureContentScript(tab.id);
    return await scrapeTabIntoJob({ tabId: tab.id, jobId: job.id, maxPages, token }, onProgress);
  } finally {
    try { await chrome.tabs.remove(tab.id); } catch {}
  }
}

function waitForTabComplete(tabId, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      reject(new Error("Sales Navigator page took too long to load."));
    }, timeoutMs);
    function listener(updatedTabId, info) {
      if (updatedTabId === tabId && info.status === "complete") {
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        // small settle delay for SPA content
        setTimeout(resolve, 2500);
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  const progress = (p) => chrome.runtime.sendMessage({ type: "SCRAPE_PROGRESS", progress: p });

  if (msg.type === "START_SCRAPE") {
    (async () => {
      try {
        sendResponse({ ok: true, result: await runScrape(msg.payload, progress) });
      } catch (err) {
        sendResponse({ ok: false, error: err.message });
      }
    })();
    return true;
  }

  if (msg.type === "START_AUTO_SCRAPE") {
    (async () => {
      try {
        sendResponse({ ok: true, result: await runAutoScrape(msg.payload, progress) });
      } catch (err) {
        sendResponse({ ok: false, error: err.message });
      }
    })();
    return true;
  }
});
