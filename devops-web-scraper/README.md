# Dockerized Web Scraper Dashboard

A multi-stage Docker application that uses Node.js 18, Puppeteer and Chromium to scrape a user-supplied public URL. Python 3.10 and Flask host the JSON output and a professional browser dashboard.

## Features

- Build-time scraping with Docker build argument `SCRAPE_URL`.
- Runtime startup scraping with Docker environment variable `SCRAPE_URL`.
- Dynamic scraping from the dashboard without rebuilding the image.
- JSON endpoints at `/` and `/data`.
- Health endpoint at `/health`.
- Dashboard at `/ui`.
- Browser-local scraping history and JSON download.

## Build

From the directory containing the Dockerfile:

```powershell
docker build --build-arg SCRAPE_URL="https://www.python.org" -t devops-web-scraper .
```

The build stage runs the scraper and saves its output as `/app/scraped_data.json`.

## Run with a runtime URL

```powershell
docker rm -f web-scraper 2>$null
docker run -d --name web-scraper -p 5000:5000 -e SCRAPE_URL="https://example.com" devops-web-scraper
```

The container performs a startup scrape for the runtime URL and starts Flask.

## Open the application

- Dashboard: http://localhost:5000/ui
- JSON root endpoint: http://localhost:5000/
- JSON data endpoint: http://localhost:5000/data
- Health check: http://localhost:5000/health

Enter another public HTTP or HTTPS URL in the dashboard and select **Scrape website**. This invokes Puppeteer at runtime; no image rebuild is needed.

## API

```powershell
$body = @{ url = "https://www.python.org" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/scrape" -Method Post -ContentType "application/json" -Body $body
```

## Verify

```powershell
docker ps
docker logs web-scraper
docker exec web-scraper ls -l /app/scraped_data.json
Invoke-RestMethod http://localhost:5000/health
Invoke-RestMethod http://localhost:5000/data
```

## Project structure

```text
devops-web-scraper/
├── Dockerfile
├── .dockerignore
├── package.json
├── requirements.txt
├── server.py
├── README.md
├── scraper/
│   └── scrape.js
└── templates/
    └── index.html
```

## Notes

- Use only public websites that you are authorized to access.
- The application rejects obvious private/internal network targets and non-HTTP(S) URLs.
- Scraping behavior depends on the target site's availability, robots policies, access controls and content.
- Flask's built-in server is suitable for this assignment demonstration, not production deployment.
