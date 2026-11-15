import ipaddress
import json
import os
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "scraped_data.json"
SCRAPER_FILE = BASE_DIR / "scraper" / "scrape.js"
SCRAPE_TIMEOUT_SECONDS = 60


def validate_public_url(raw_url):
    """Allow public HTTP(S) URLs only; reject obvious SSRF targets."""
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise ValueError("Please provide a URL.")

    raw_url = raw_url.strip()
    try:
        parsed = urlsplit(raw_url)
        hostname = parsed.hostname
        port = parsed.port  # Accessing this also validates malformed ports.
    except ValueError:
        raise ValueError("The URL is malformed.")

    if parsed.scheme not in ("http", "https") or not hostname:
        raise ValueError("Enter a complete URL beginning with http:// or https://.")

    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not allowed.")

    if port and port not in (80, 443):
        raise ValueError("Only standard HTTP and HTTPS ports (80 and 443) are allowed.")

    hostname = hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Local and internal hostnames are not allowed.")

    try:
        ip = ipaddress.ip_address(hostname)
        if not ip.is_global:
            raise ValueError("Private or non-public IP addresses are not allowed.")
    except ValueError as exc:
        # A valid IP that is not global raises our message; non-IP hostnames
        # are resolved below.
        if "not allowed" in str(exc):
            raise
        try:
            addresses = socket.getaddrinfo(hostname, port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror:
            raise ValueError("The hostname could not be resolved.")

        resolved = {item[4][0] for item in addresses}
        if not resolved:
            raise ValueError("The hostname could not be resolved.")
        for address in resolved:
            if not ipaddress.ip_address(address).is_global:
                raise ValueError("The hostname resolves to a private or non-public address.")

    return raw_url


def load_scraped_data():
    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {
            "title": "",
            "url": "",
            "first_heading": "",
            "headings": [],
            "meta_description": "",
            "scraped_at": "",
            "text_excerpt": ""
        }


def scrape_url(url):
    completed = subprocess.run(
        ["node", str(SCRAPER_FILE), url],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=SCRAPE_TIMEOUT_SECONDS,
        check=False
    )

    if completed.returncode != 0:
        message = completed.stderr.strip() or "The scraper process failed."
        raise RuntimeError(message[-1500:])

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("The scraper returned invalid JSON.")

    temporary_file = DATA_FILE.with_suffix(".tmp")
    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
    temporary_file.replace(DATA_FILE)
    return result


@app.get("/")
def index():
    # Preserve the assignment's JSON endpoint at the root URL.
    return jsonify(load_scraped_data())


@app.get("/data")
def data():
    return jsonify(load_scraped_data())


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/ui")
def dashboard():
    return render_template("index.html")


@app.post("/scrape")
def scrape():
    payload = request.get_json(silent=True) or {}
    try:
        url = validate_public_url(payload.get("url"))
        result = scrape_url(url)
        return jsonify(result), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Scraping timed out. Try a faster or simpler website."}), 504
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 502
    except Exception:
        app.logger.exception("Unexpected scraping error")
        return jsonify({"error": "An unexpected server error occurred."}), 500


if __name__ == "__main__":
    # Preserve runtime environment-variable URL support from the assignment.
    runtime_url = os.environ.get("SCRAPE_URL", "").strip()
    if runtime_url:
        try:
            validated_url = validate_public_url(runtime_url)
            result = scrape_url(validated_url)
            print(f"Runtime scrape completed for {result.get('url', validated_url)}.", flush=True)
        except Exception as error:
            print(f"Runtime scrape failed: {error}", flush=True)

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
