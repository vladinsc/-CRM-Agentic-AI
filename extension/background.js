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

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Try to message a tab once, resolving null instead of rejecting on "no receiver".
function tryPing(tabId) {
  return new Promise((resolve) => {
    try {
      chrome.tabs.sendMessage(tabId, { type: "PING" }, (resp) => {
        if (chrome.runtime.lastError) resolve(null);
        else resolve(resp);
      });
    } catch {
      resolve(null);
    }
  });
}

// Inject content.js and wait until it actually responds to a PING, so we never
// send a real message before its onMessage listener is registered. content.js
// is injected ONLY here (no manifest content_scripts), avoiding any race.
async function ensureContentScript(tabId) {
  for (let attempt = 0; attempt < 8; attempt++) {
    try {
      await chrome.scripting.executeScript({ target: { tabId }, files: ["content.js"] });
    } catch (e) {
      console.warn("ensureContentScript inject:", e.message);
    }
    const pong = await tryPing(tabId);
    if (pong && pong.ready) return;
    await sleep(600);
  }
  throw new Error("Content script did not become ready in the tab.");
}

// Visit a Sales Nav company page in a background tab and read its real
// "Visit website" URL. Returns null on any failure (best-effort enrichment).
async function resolveCompanyWebsite(companyPageUrl) {
  if (!companyPageUrl || !companyPageUrl.includes("/sales/company/")) return null;
  let tab;
  try {
    tab = await chrome.tabs.create({ url: companyPageUrl, active: false });
    await waitForTabComplete(tab.id);
    await ensureContentScript(tab.id);
    const resp = await sendToTab(tab.id, { type: "GET_COMPANY_WEBSITE" });
    return (resp && resp.website) || null;
  } catch (e) {
    console.warn("resolveCompanyWebsite failed:", e.message);
    return null;
  } finally {
    if (tab) { try { await chrome.tabs.remove(tab.id); } catch {} }
  }
}

// Enrich a batch of leads with their real company website, deduped + cached by
// the company page URL so each company is visited at most once per job.
async function enrichWebsites(leads, cache) {
  for (const lead of leads) {
    const key = lead.company_url;
    if (!key || !key.includes("/sales/company/")) continue;
    if (!(key in cache)) {
      cache[key] = await resolveCompanyWebsite(key);
    }
    // Replace the LinkedIn company-page URL with the real website (if found),
    // so the server-side research fetch hits a real, fetchable domain.
    if (cache[key]) lead.company_url = cache[key];
  }
  return leads;
}

// Drives the page-by-page scrape of an already-prepared tab into an existing job.
async function scrapeTabIntoJob({ tabId, jobId, maxPages, token }, onProgress) {
  let totalMatched = 0;
  let totalRejected = 0;
  const websiteCache = {};   // company page URL -> real website (or null)
  for (let page = 1; page <= maxPages; page++) {
    const pageResp = await sendToTab(tabId, { type: "SCRAPE_CURRENT_PAGE" });
    let leads = (pageResp && pageResp.leads) || [];

    if (leads.length > 0) {
      leads = await enrichWebsites(leads, websiteCache);
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
