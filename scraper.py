"""
Chile Auto Price Scraper — Autocosmos.cl
Scrapes public listing pages with proper rate-limiting.
"""
import re
import time
import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://www.autocosmos.cl"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "es-CL,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}

# Slug map: display name → URL slug
MARCAS_DEFAULT = [
    "Toyota", "Chevrolet", "Hyundai", "Kia", "Suzuki",
    "Nissan", "Ford", "Volkswagen", "Honda", "Mazda",
    "Mitsubishi", "Subaru", "Peugeot", "Renault", "Citroën",
]

_SLUG = {
    "Citroën": "citroen",
    "Volkswagen": "volkswagen",
    "Mercedes Benz": "mercedes-benz",
    "Mercedes-Benz": "mercedes-benz",
}


def _slug(brand: str) -> str:
    return _SLUG.get(brand, brand.lower().replace(" ", "-"))


# ─── Parsing ─────────────────────────────────────────────────────────────────

def _cond(meta_content: str) -> str:
    if not meta_content:
        return "No especificado"
    if "Used" in meta_content:
        return "Usado"
    if "New" in meta_content:
        return "Nuevo"
    return "No especificado"


def _km(content) -> float:
    if not content or (isinstance(content, float) and np.isnan(content)):
        return np.nan
    cleaned = str(content).replace("KMT", "").replace("km", "").replace(".", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return np.nan


def _price(content) -> float:
    if content is None or (isinstance(content, float) and np.isnan(content)):
        return np.nan
    try:
        return float(str(content).replace(".", "").replace(",", "").replace("$", "").strip())
    except ValueError:
        return np.nan


def _parse_card(card) -> dict | None:
    """Parse a single listing-card article into a dict."""
    try:
        brand_el   = card.find(class_="listing-card__brand")
        model_el   = card.find(class_="listing-card__model")
        version_el = card.find(class_="listing-card__version")
        year_el    = card.find(class_="listing-card__year")
        km_el      = card.find(class_="listing-card__km")
        price_el   = card.find(class_="listing-card__price-value")
        cond_meta  = card.find("meta", {"itemprop": "itemCondition"})
        city_el    = card.find(class_="listing-card__city")
        region_el  = card.find(class_="listing-card__province")
        url_el     = card.find("a", {"itemprop": "url"})
        img_el     = card.find("img", {"itemprop": "image"})

        # Price can be in content attr or in a meta tag inside price div
        price_raw = None
        if price_el:
            price_raw = price_el.get("content") or price_el.get_text(strip=True)
        else:
            price_meta = card.find("meta", {"itemprop": "price"})
            if price_meta:
                price_raw = price_meta.get("content")

        return {
            "marca":     brand_el.get_text(strip=True) if brand_el else None,
            "modelo":    model_el.get_text(strip=True) if model_el else None,
            "version":   version_el.get_text(strip=True) if version_el else None,
            "anio":      year_el.get_text(strip=True) if year_el else None,
            "km_raw":    km_el.get("content") if km_el else None,
            "precio_raw": price_raw,
            "condicion": _cond(cond_meta.get("content") if cond_meta else None),
            "ciudad":    (city_el.get_text(strip=True).replace("|", "").strip()) if city_el else None,
            "region":    region_el.get_text(strip=True) if region_el else None,
            "url":       (BASE_URL + url_el.get("href")) if url_el and url_el.get("href", "").startswith("/") else (url_el.get("href") if url_el else None),
            "thumbnail": img_el.get("src") if img_el else None,
        }
    except Exception:
        return None


def _get_page(url: str, retries: int = 2) -> BeautifulSoup | None:
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=14)
            if r.status_code == 200:
                return BeautifulSoup(r.text, "lxml")
            if r.status_code in (429, 503):
                time.sleep(3 * (attempt + 1))
        except requests.RequestException:
            time.sleep(2)
    return None


# ─── Fetching ─────────────────────────────────────────────────────────────────

def fetch_brand(brand: str, include_new: bool = True, delay: float = 0.5) -> list[dict]:
    """Fetch used (and optionally new) listings for one brand."""
    slug = _slug(brand)
    results = []

    for cond_path in (["usado", "nuevo"] if include_new else ["usado"]):
        url = f"{BASE_URL}/auto/{cond_path}/{slug}/"
        soup = _get_page(url)
        if soup is None:
            continue
        for card in soup.find_all("article", class_="card listing-card"):
            parsed = _parse_card(card)
            if parsed:
                results.append(parsed)
        time.sleep(delay)

    return results


def fetch_general_pages(n_pages: int = 5, delay: float = 0.5) -> list[dict]:
    """Fetch N pages from the general used-cars listing (mixed brands)."""
    results = []
    for pidx in range(1, n_pages + 1):
        url = f"{BASE_URL}/auto/usado?pidx={pidx}"
        soup = _get_page(url)
        if soup is None:
            break
        cards = soup.find_all("article", class_="card listing-card")
        if not cards:
            break
        for card in cards:
            parsed = _parse_card(card)
            if parsed:
                results.append(parsed)
        time.sleep(delay)
    return results


def fetch_all(
    marcas: list[str] = None,
    include_new: bool = True,
    extra_general_pages: int = 3,
    progress_cb=None,
) -> pd.DataFrame:
    """
    Fetch listings for all brands + extra general pages.
    Returns a clean, deduplicated DataFrame.
    """
    marcas = marcas or MARCAS_DEFAULT
    raw: list[dict] = []

    total_steps = len(marcas) + (1 if extra_general_pages else 0)

    for i, marca in enumerate(marcas):
        if progress_cb:
            progress_cb(marca, i, total_steps)
        raw.extend(fetch_brand(marca, include_new=include_new))

    if extra_general_pages:
        if progress_cb:
            progress_cb("Páginas generales…", len(marcas), total_steps)
        raw.extend(fetch_general_pages(n_pages=extra_general_pages))

    if progress_cb:
        progress_cb("", total_steps, total_steps)

    return clean(pd.DataFrame(raw)) if raw else pd.DataFrame()


# ─── Cleaning ─────────────────────────────────────────────────────────────────

def clean(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    # Numeric fields
    df["precio_clp"] = df["precio_raw"].apply(_price)
    df["km"]         = df["km_raw"].apply(_km)
    df["anio_num"]   = pd.to_numeric(df["anio"], errors="coerce")
    df["antiguedad"] = datetime.now().year - df["anio_num"]
    df["precio_m"]   = df["precio_clp"] / 1_000_000

    # Deduplicate by URL, keep first occurrence
    if "url" in df.columns:
        df = df.drop_duplicates(subset="url")

    # Quality filters
    df = df[
        df["precio_clp"].notna() &
        df["precio_m"].between(1, 600) &
        df["marca"].notna() &
        (df["anio_num"].isna() | df["anio_num"].between(1990, datetime.now().year + 1))
    ]

    df = df.reset_index(drop=True)
    df.index.name = None
    return df
