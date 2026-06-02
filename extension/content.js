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

function extractLeadsFromPage() {
  const cardSelectors = [
    '[data-view-name="search-results-lead-result-item"]',
    ".search-results__result-item",
    "li.artdeco-list__item",
  ];
  let cards = [];
  for (const sel of cardSelectors) {
    cards = [...document.querySelectorAll(sel)];
    if (cards.length > 0) break;
  }

  return cards
    .map((card) => {
      const nameEl =
        card.querySelector('[data-anonymize="person-name"]') ||
        card.querySelector(".result-lockup__name a");
      const titleEl =
        card.querySelector('[data-anonymize="title"]') ||
        card.querySelector(".result-lockup__highlight-keyword");
      const companyEl =
        card.querySelector('[data-anonymize="company-name"]') ||
        card.querySelector(".result-lockup__position-company a");
      const locEl =
        card.querySelector('[data-anonymize="location"]') ||
        card.querySelector(".result-lockup__misc-item");
      const linkEl =
        card.querySelector('a[href*="/sales/lead/"]') ||
        card.querySelector('a[href*="/in/"]');

      // Company link from the card — the company name usually links to the
      // company's Sales Nav / LinkedIn page (used later to find their website).
      const companyLinkEl =
        card.querySelector('a[href*="/sales/company/"]') ||
        card.querySelector('a[href*="/company/"]') ||
        (companyEl && companyEl.tagName === "A" ? companyEl : null);

      return {
        name: nameEl ? nameEl.textContent.trim() : null,
        title: titleEl ? titleEl.textContent.trim() : null,
        company: companyEl ? companyEl.textContent.trim() : null,
        location: locEl ? locEl.textContent.trim() : null,
        profile_url: linkEl ? linkEl.href : null,
        company_url: companyLinkEl ? companyLinkEl.href : null,
      };
    })
    .filter((l) => l.name);
}

async function scrollToBottom() {
  // Sales Nav lazy-loads result cards as you scroll; nudge the list to render all.
  for (let i = 0; i < 6; i++) {
    window.scrollBy(0, document.body.scrollHeight / 6);
    await SLEEP(rand(400, 800));
  }
  window.scrollTo(0, 0);
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

// The popup/background drives the scrape one page at a time so it can stream
// each batch to the API and update progress.
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "PING") {
    sendResponse({ ok: true, ready: true });
    return true;
  }

  if (msg.type === "SCRAPE_CURRENT_PAGE") {
    (async () => {
      await scrollToBottom();
      const leads = extractLeadsFromPage();
      sendResponse({ ok: true, leads });
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
