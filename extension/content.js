// Runs inside the LinkedIn Sales Navigator search page (the user's own logged-in
// tab). Extracts leads from the visible results and paginates. Selectors are the
// ones already validated server-side in scraper-service/scraper/linkedin.py.

// Guard against double-injection (manifest match + programmatic executeScript),
// which would otherwise register duplicate message listeners.
if (window.__crmScraperInjected) {
  // Already loaded — do nothing on re-injection.
} else {
  window.__crmScraperInjected = true;

const SLEEP = (ms) => new Promise((r) => setTimeout(r, ms));
const rand = (min, max) => Math.floor(Math.random() * (max - min) + min);

function getCards() {
  const cardSelectors = [
    '[data-view-name="search-results-lead-result-item"]',
    ".search-results__result-item",
    "li.artdeco-list__item",
  ];
  for (const sel of cardSelectors) {
    const found = [...document.querySelectorAll(sel)];
    if (found.length > 0) return found;
  }

  // Structural fallback (resilient to LinkedIn class/attr changes): every result
  // row contains a link to /sales/lead/. Walk up to the row container.
  const leadLinks = [...document.querySelectorAll('a[href*="/sales/lead/"]')];
  const rows = new Set();
  for (const a of leadLinks) {
    let el = a;
    for (let i = 0; i < 6 && el && el !== document.body; i++) {
      if (el.tagName === "LI" || el.getAttribute("role") === "listitem") break;
      el = el.parentElement;
    }
    if (el && el !== document.body) rows.add(el);
  }
  return [...rows];
}

function extractLeadsFromPage() {
  const cards = getCards();

  return cards
    .map((card) => {
      const leadLink =
        card.querySelector('a[href*="/sales/lead/"]') ||
        card.querySelector('a[href*="/in/"]');

      const nameEl =
        card.querySelector('[data-anonymize="person-name"]') ||
        card.querySelector(".result-lockup__name a") ||
        leadLink;   // the lead link's text is the person's name

      const titleEl =
        card.querySelector('[data-anonymize="title"]') ||
        card.querySelector(".result-lockup__highlight-keyword");
      const companyEl =
        card.querySelector('[data-anonymize="company-name"]') ||
        card.querySelector(".result-lockup__position-company a");
      const locEl =
        card.querySelector('[data-anonymize="location"]') ||
        card.querySelector(".result-lockup__misc-item");

      const companyLinkEl =
        card.querySelector('a[href*="/sales/company/"]') ||
        card.querySelector('a[href*="/company/"]') ||
        (companyEl && companyEl.tagName === "A" ? companyEl : null);

      const clean = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : null);

      return {
        name: clean(nameEl),
        title: clean(titleEl),
        company: clean(companyEl),
        location: clean(locEl),
        profile_url: leadLink ? leadLink.href : null,
        company_url: companyLinkEl ? companyLinkEl.href : null,
      };
    })
    .filter((l) => l.name);
}

function countCards() {
  return getCards().length;
}

// Find the actual scrollable results container. Sales Nav renders results in an
// INNER scroll region, not the window — scrolling window alone loads nothing.
function findScrollContainer() {
  const firstCard =
    document.querySelector('[data-view-name="search-results-lead-result-item"]') ||
    document.querySelector(".search-results__result-item") ||
    document.querySelector("li.artdeco-list__item");
  let el = firstCard ? firstCard.parentElement : null;
  while (el && el !== document.body) {
    const style = getComputedStyle(el);
    if (
      (style.overflowY === "auto" || style.overflowY === "scroll") &&
      el.scrollHeight > el.clientHeight + 50
    ) {
      return el;
    }
    el = el.parentElement;
  }
  return null;
}

// Sales Nav lazy-loads/virtualizes cards as the inner list scrolls. Scroll it
// step by step until the card count stops growing (all ~25 rendered).
async function scrollToBottom() {
  const container = findScrollContainer();
  const scrollEl = container || document.scrollingElement || document.documentElement;

  let lastCount = -1;
  let stable = 0;
  for (let i = 0; i < 30 && stable < 3; i++) {
    scrollEl.scrollBy(0, Math.max(600, scrollEl.clientHeight * 0.8));
    await SLEEP(rand(500, 900));
    const count = countCards();
    if (count === lastCount) {
      stable++;
    } else {
      stable = 0;
      lastCount = count;
    }
  }
  // Back to top so pagination/Next is reachable and the page looks normal.
  scrollEl.scrollTo({ top: 0 });
  await SLEEP(rand(500, 900));
}

function findNextButton() {
  const selectors = [
    'button[aria-label="Next"]',
    "button.artdeco-pagination__button--next",
    '[data-test-pagination-page-btn="next"]',
  ];
  for (const sel of selectors) {
    const btn = document.querySelector(sel);
    if (btn && !btn.disabled) return btn;
  }
  return null;
}

// On a Sales Nav company page, find the real company website behind the
// "Visit website" link. Returns the external URL (not a linkedin.com link).
function findCompanyWebsite() {
  // 1. Anchors whose visible text is "Visit website".
  const anchors = [...document.querySelectorAll("a[href]")];
  const byText = anchors.find((a) =>
    /visit website/i.test((a.textContent || "").trim())
  );
  if (byText && byText.href) return byText.href;

  // 2. Any external (non-linkedin) link in the company top-card / about area.
  const external = anchors.find((a) => {
    try {
      const u = new URL(a.href);
      return (
        !u.hostname.endsWith("linkedin.com") &&
        (u.protocol === "http:" || u.protocol === "https:")
      );
    } catch {
      return false;
    }
  });
  return external ? external.href : null;
}

// Sales Nav is a heavy SPA: the page reports "loaded" long before the result
// cards render. Poll until cards actually appear (or we give up) so we never
// scrape an empty, still-rendering page.
async function waitForCards(maxMs = 20000) {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    if (countCards() > 0) return true;
    // a checkpoint/login page will never have cards — bail early if detected
    if (/\/(login|checkpoint|authwall)/.test(location.pathname)) return false;
    await SLEEP(600);
  }
  return countCards() > 0;
}

// The popup/background drives the scrape one page at a time so it can stream
// each batch to the API and update progress.
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "PING") {
    sendResponse({ ok: true, ready: true });
    return true;
  }

  if (msg.type === "SCRAPE_CURRENT_PAGE") {
    (async () => {
      const appeared = await waitForCards();
      if (!appeared) {
        sendResponse({ ok: true, leads: [], reason: "no-cards", url: location.href });
        return;
      }
      await scrollToBottom();
      const leads = extractLeadsFromPage();
      sendResponse({ ok: true, leads, cardCount: countCards() });
    })();
    return true; // async response
  }

  if (msg.type === "GET_COMPANY_WEBSITE") {
    (async () => {
      // give the company page a moment to render its top-card
      await SLEEP(rand(1200, 2200));
      sendResponse({ ok: true, website: findCompanyWebsite() });
    })();
    return true;
  }

  if (msg.type === "GO_NEXT_PAGE") {
    (async () => {
      const btn = findNextButton();
      if (!btn) {
        sendResponse({ ok: true, hasNext: false });
        return;
      }
      btn.click();
      await SLEEP(rand(2500, 4500)); // let the next page render
      sendResponse({ ok: true, hasNext: true });
    })();
    return true;
  }
});

} // end double-injection guard
