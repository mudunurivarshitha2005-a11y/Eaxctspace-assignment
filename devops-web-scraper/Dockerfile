# Stage 1: Node.js scraper build and optional build-time scraping
FROM node:18-bookworm-slim AS scraper-build

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

COPY package.json ./
RUN npm install --omit=dev

COPY scraper ./scraper

# Optional build-time URL support (required by the assignment).
ARG SCRAPE_URL=""
RUN if [ -n "$SCRAPE_URL" ]; then \
      node scraper/scrape.js "$SCRAPE_URL" > /app/scraped_data.json; \
    else \
      printf '%s\n' '{"title":"","url":"","first_heading":"","headings":[],"meta_description":"","scraped_at":"","text_excerpt":""}' > /app/scraped_data.json; \
    fi

# Stage 2: Small Python runtime hosting the scraper and Flask application
FROM python:3.10-slim-bookworm AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    PORT=5000

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only the Node runtime dependencies and scraper needed at runtime.
COPY --from=scraper-build /usr/local/bin/node /usr/local/bin/node
COPY --from=scraper-build /app/node_modules ./node_modules
COPY --from=scraper-build /app/package.json ./package.json
COPY --from=scraper-build /app/scraper ./scraper
COPY --from=scraper-build /app/scraped_data.json ./scraped_data.json

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py ./
COPY templates ./templates

EXPOSE 5000

CMD ["python", "server.py"]
