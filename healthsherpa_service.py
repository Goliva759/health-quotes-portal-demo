"""
HealthSherpa One API Integration Service
Nexxel Corporation Quotes Portal

Provides client methods for:
- County resolution (GET /v1/reference/counties)
- Plan quoting (POST /v1/quotes)
- Document URLs extraction (SBC, Brochure, Formulary, Provider Directory)
- Resilient fallback handling
"""

import os
import requests
from datetime import date, datetime
from typing import List, Dict, Any, Optional

HEALTHSHERPA_BASE_URL = os.environ.get(
    "HEALTHSHERPA_BASE_URL", "https://api.one.healthsherpa.com"
).rstrip("/")

DEFAULT_TIMEOUT = 12


def get_default_effective_date() -> str:
    """
    Computes runtime default effective date as the first day
    of the next calendar month (YYYY-MM-01).
    """
    today = date.today()
    if today.month == 12:
        next_month = 1
        year = today.year + 1
    else:
        next_month = today.month + 1
        year = today.year
    return f"{year:04d}-{next_month:02d}-01"


def get_headers(api_key: str) -> Dict[str, str]:
    """
    Builds required standard headers for HealthSherpa One API.
    """
    key_clean = (api_key or "").strip()
    return {
        "x-api-key": key_clean,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Nexxel-Quotes-Portal/2.0"
    }


def lookup_counties(zip_code: str, api_key: str, base_url: str = HEALTHSHERPA_BASE_URL) -> List[Dict[str, Any]]:
    """
    Queries HealthSherpa for counties matching a 5-digit ZIP code.
    Endpoint: GET /v1/reference/counties?zip_code={zip_code}
    """
    zip_clean = str(zip_code or "").strip()
    if len(zip_clean) != 5 or not zip_clean.isdigit():
        return []

    url = f"{base_url}/v1/reference/counties"
    headers = get_headers(api_key)
    params = {"zip_code": zip_clean}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("counties", []) or data.get("data", [])
        return []
    except Exception:
        return []


def quote_plans(
    zip_code: str,
    fips_code: str,
    state: str,
    age: int,
    api_key: str,
    pregnant: bool = False,
    annual_income: float = 0.0,
    effective_date: Optional[str] = None,
    provider_npis: Optional[List[str]] = None,
    base_url: str = HEALTHSHERPA_BASE_URL
) -> Dict[str, Any]:
    """
    Submits an ACA Quote request to HealthSherpa One API.
    Endpoint: POST /v1/quotes
    
    Returns standard dictionary with:
    - success: bool
    - plans: List[Dict[str, Any]]
    - error: Optional[str]
    - total_count: int
    """
    eff_date = effective_date or get_default_effective_date()
    url = f"{base_url}/v1/quotes"
    headers = get_headers(api_key)

    applicant = {
        "member_id": "applicant-1",
        "age": int(age),
        "relationship": "primary",
        "uses_tobacco": False,  # Hardcoded false for surrogacy eligibility
        "pregnant": bool(pregnant)
    }

    payload: Dict[str, Any] = {
        "context": {
            "product": "aca",
            "exchange": "on_exchange",
            "coverage_family": "medical",
            "coverage_type": "medical"
        },
        "location": {
            "zip_code": str(zip_code).strip(),
            "fips_code": str(fips_code).strip(),
            "state": str(state).strip().upper()
        },
        "household": {
            "household_size": 1,
            "annual_income": float(annual_income),
            "effective_date": eff_date,
            "applicants": [applicant]
        },
        "sort": {
            "field": "premium",
            "direction": "asc"
        },
        "page": {
            "number": 1,
            "size": 50
        }
    }

    if provider_npis:
        payload["providers"] = [str(npi).strip() for npi in provider_npis if str(npi).strip()]

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            raw_plans = data.get("plans", [])
            normalized_plans = [_normalize_plan(p) for p in raw_plans]
            return {
                "success": True,
                "plans": normalized_plans,
                "total_count": len(normalized_plans),
                "error": None
            }
        else:
            err_msg = f"HealthSherpa API error {resp.status_code}: {resp.text[:200]}"
            return {
                "success": False,
                "plans": [],
                "total_count": 0,
                "error": err_msg
            }
    except Exception as exc:
        return {
            "success": False,
            "plans": [],
            "total_count": 0,
            "error": str(exc)
        }


def _normalize_plan(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standardizes HealthSherpa plan dictionary for the Nexxel UI and PDF generation.
    Safely handles nested structures, missing keys, and casing variations.
    """
    details = raw.get("details", {}) or {}
    pricing = raw.get("pricing", {}) or {}
    issuer = raw.get("issuer", {}) or {}
    urls = raw.get("urls", {}) or {}
    cost_sharing = raw.get("cost_sharing", {}) or {}

    gross_prem = pricing.get("gross_premium")
    net_prem = pricing.get("net_premium")
    if net_prem is None and gross_prem is not None:
        net_prem = gross_prem
    elif net_prem is None:
        net_prem = raw.get("premium", 0.0)

    metal = details.get("metal_level") or raw.get("metal_level") or "Standard"
    clean_metal = str(metal).replace("_", " ").title()

    plan_type = details.get("plan_type") or raw.get("plan_type") or raw.get("network_type") or "PPO"

    # Deductible and MOOP extraction
    med_ded = (
        cost_sharing.get("medical_ded_ind")
        or raw.get("deductible")
        or "$0"
    )
    med_moop = (
        cost_sharing.get("medical_moop_ind")
        or raw.get("moop")
        or "$0"
    )

    return {
        "id": str(raw.get("hios_id") or raw.get("id") or ""),
        "hios_id": str(raw.get("hios_id") or raw.get("id") or ""),
        "name": str(raw.get("name") or details.get("name") or "Medical Plan"),
        "issuer": str(issuer.get("name") or raw.get("issuer_name") or "Insurance Carrier"),
        "logo_url": issuer.get("logo_url") or "",
        "metal_level": clean_metal,
        "plan_type": str(plan_type).upper(),
        "gross_premium": float(gross_prem or net_prem or 0.0),
        "net_premium": float(net_prem or 0.0),
        "subsidy_applied": float(pricing.get("subsidy_applied") or 0.0),
        "max_aptc": float(pricing.get("max_aptc") or 0.0),
        "deductible": med_ded,
        "moop": med_moop,
        "urls": {
            "summary_of_benefits": urls.get("summary_of_benefits") or urls.get("benefits") or "",
            "brochure": urls.get("brochure") or "",
            "formulary": urls.get("formulary") or "",
            "provider_directory": urls.get("provider_directory") or urls.get("network") or ""
        },
        "providers": raw.get("providers", {}),
        "deeplink_enrollment": bool(raw.get("deeplink_enrollment", False)),
        "api_enrollment": bool(raw.get("api_enrollment", False)),
        "off_ex": bool(raw.get("off_ex", False))
    }
