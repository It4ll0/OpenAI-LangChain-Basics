"""
Chile Auto Price Scraper — MercadoLibre Chile public API
"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time

BASE_URL       = "https://api.mercadolibre.com"
SITE_ID        = "MLC"
CATEGORY_AUTOS = "MLC1744"   # Autos y Camionetas — Chile

MARCAS_DEFAULT = [
    "Toyota", "Chevrolet", "Hyundai", "Kia", "Suzuki",
    "Nissan", "Ford", "Volkswagen", "Honda", "Mazda",
    "Mitsubishi", "Subaru", "Peugeot", "Renault", "Citroën",
]


# ─── API helpers ─────────────────────────────────────────────────────────────

def _get(url: str, params: dict = None, timeout: int = 12):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def get_usd_clp() -> float:
    data = _get(f"{BASE_URL}/currency_conversions/search", {"from": "USD", "to": "CLP"})
    return float(data.get("ratio", 950))


def _get_attr(attributes: list, attr_id: str):
    for a in attributes:
        if a.get("id") == attr_id:
            return a.get("value_name")
    return None


def _parse_item(item: dict) -> dict:
    attrs = item.get("attributes", [])
    return {
        "id":          item.get("id"),
        "titulo":      item.get("title"),
        "precio":      item.get("price"),
        "moneda":      item.get("currency_id"),
        "condicion":   item.get("condition"),
        "marca":       _get_attr(attrs, "BRAND"),
        "modelo":      _get_attr(attrs, "MODEL"),
        "anio":        _get_attr(attrs, "VEHICLE_YEAR"),
        "kilometraje": _get_attr(attrs, "VEHICLE_MILEAGE"),
        "combustible": _get_attr(attrs, "FUEL_TYPE"),
        "transmision": _get_attr(attrs, "TRANSMISSION"),
        "url":         item.get("permalink"),
        "thumbnail":   item.get("thumbnail"),
    }


def fetch_brand(brand: str, max_items: int = 100, delay: float = 0.3) -> list:
    items, offset = [], 0
    while len(items) < max_items:
        data = _get(
            f"{BASE_URL}/sites/{SITE_ID}/search",
            {"category": CATEGORY_AUTOS, "q": brand, "limit": 50, "offset": offset},
        )
        batch = data.get("results", [])
        if not batch:
            break
        items.extend(batch)
        offset += 50
        if len(batch) < 50:
            break
        time.sleep(delay)
    return items[:max_items]


# ─── Data collection ─────────────────────────────────────────────────────────

def fetch_all(
    marcas: list = None,
    max_per_brand: int = 100,
    progress_cb=None,
) -> pd.DataFrame:
    """
    Fetch listings for all brands and return a clean DataFrame.
    progress_cb(brand, current, total) is called after each brand if provided.
    """
    marcas = marcas or MARCAS_DEFAULT
    usd_clp = get_usd_clp()
    raw = []

    for i, marca in enumerate(marcas):
        if progress_cb:
            progress_cb(marca, i, len(marcas))
        items = fetch_brand(marca, max_items=max_per_brand)
        raw.extend([_parse_item(it) for it in items])

    if progress_cb:
        progress_cb("", len(marcas), len(marcas))

    return clean(pd.DataFrame(raw), usd_clp)


# ─── Cleaning ────────────────────────────────────────────────────────────────

def _parse_km(val) -> float:
    if pd.isna(val):
        return np.nan
    s = str(val).replace(" km", "").replace("km", "").replace(".", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return np.nan


def clean(df: pd.DataFrame, usd_clp: float = 950) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.drop_duplicates(subset="id").copy()

    df["precio_clp"] = df.apply(
        lambda r: r["precio"] * usd_clp if r["moneda"] == "USD" else r["precio"], axis=1
    )
    df["precio_m"]   = df["precio_clp"] / 1_000_000
    df["precio_usd"] = df["precio_clp"] / usd_clp

    df["km"]         = df["kilometraje"].apply(_parse_km)
    df["anio_num"]   = pd.to_numeric(df["anio"], errors="coerce")
    df["antiguedad"] = datetime.now().year - df["anio_num"]

    df["condicion_es"] = df["condicion"].map(
        {"new": "Nuevo", "used": "Usado", "not_specified": "No especificado"}
    ).fillna("No especificado")

    df = df[
        df["precio_m"].between(1, 600) &
        df["marca"].notna() &
        (df["anio_num"].isna() | (df["anio_num"] >= 1990))
    ]
    return df.reset_index(drop=True)
