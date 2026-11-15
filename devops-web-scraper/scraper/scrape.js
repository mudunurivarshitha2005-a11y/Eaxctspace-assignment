const puppeteer = require("puppeteer-core");
const dns = require("dns").promises;
const net = require("net");

function isPrivateAddress(address) {
  // Reject loopback, private, link-local, multicast and unspecified addresses.
  if (net.isIP(address) === 4) {
    const p = address.split(".").map(Number);
    return p[0] === 10 ||
      p[0] === 127 ||
      (p[0] === 169 && p[1] === 254) ||
      (p[0] === 172 && p[1] >= 16 && p[1] <= 31) ||
      (p[0] === 192 && p[1] === 168) ||
      p[0] === 0 ||
      p[0] >= 224;
  }
  if (net.isIP(address) === 6) {
    const normalized = address.toLowerCase();
    return normalized === "::" ||
      normalized === "::1" ||
      normalized.startsWith("fc") ||
      normalized.startsWith("fd") ||
      normalized.startsWith("fe80:") ||
      normalized.startsWith("ff");
  }
  return true;
}

async function assertPublicHttpUrl(rawUrl) {
  let parsed;
  try {
    parsed = new URL(rawUrl);
  } catch {
    throw new Error("Invalid URL.");
  }

  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Only HTTP and HTTPS URLs are supported.");
  }
  if (!parsed.hostname || parsed.username || parsed.password) {
    throw new Error("The URL must contain a valid public hostname.");
  }

  const hostname = parsed.hostname.toLowerCase();
  if (hostname === "localhost" || hostname.endsWith(".localhost") ||
      hostname.endsWith(".local") || hostname.endsWith(".internal")) {
    throw new Error("Local and internal hostnames are not allowed.");
  }

  if (net.isIP(hostname)) {
    if (isPrivateAddress(hostname)) throw new Error("Private network addresses are not allowed.");
    return;
  }

  let records;
  try {
    records = await dns.lookup(hostname, { all: true });
  } catch {
    throw new Error("The hostname could not be resolved.");
  }
  if (!records.length || records.some(record => isPrivateAddress(record.address))) {
    throw new Error("Private or non-public network destinations are not allowed.");
  }
}

async function main() {
  const targetUrl = process.argv[2];
  if (!targetUrl) throw new Error("Usage: node scraper/scrape.js <URL>");

  await assertPublicHttpUrl(targetUrl);

  const browser = await puppeteer.launch({
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || "/usr/bin/chromium",
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu"
    ]
  });

  try {
    const page = await browser.newPage();
    page.setDefaultNavigationTimeout(45000);

    // Validate every browser navigation/request to reduce SSRF exposure,
    // including requests caused by page redirects or embedded resources.
    await page.setRequestInterception(true);
    page.on("request", async request => {
      try {
        const requestUrl = request.url();
        if (requestUrl.startsWith("data:") || requestUrl.startsWith("blob:")) {
          return request.continue();
        }
        await assertPublicHttpUrl(requestUrl);
        return request.continue();
      } catch {
        return request.abort();
      }
    });

    await page.goto(targetUrl, { waitUntil: "domcontentloaded", timeout: 45000 });

    const result = await page.evaluate(() => {
      const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6"))
        .map(element => (element.innerText || element.textContent || "").trim())
        .filter(Boolean)
        .slice(0, 100);

      const metaDescription =
        document.querySelector('meta[name="description"]')?.content ||
        document.querySelector('meta[property="og:description"]')?.content ||
        "";

      const bodyText = document.body?.innerText || "";

      return {
        title: document.title || "",
        url: window.location.href,
        first_heading: headings[0] || "",
        headings,
        meta_description: metaDescription.trim(),
        scraped_at: new Date().toISOString(),
        text_excerpt: bodyText.replace(/\s+/g, " ").trim().slice(0, 3000)
      };
    });

    // stdout contains only JSON so Flask can parse it reliably.
    process.stdout.write(JSON.stringify(result));
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(`Scraping failed: ${error.message}`);
  process.exit(1);
});
