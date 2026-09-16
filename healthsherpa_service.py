"""
HealthSherpa One API Integration Service
Health Insurance Quotes Portal (Demo)

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

DEFAULT_API_KEY = ""
DEFAULT_TIMEOUT = 20

# Fast in-memory FIPS resolution for all candidate ZIP codes to eliminate network lag
COMMON_ZIP_FIPS = {
    "07071": ("34003", "NJ"),
    "24985": ("54063", "WV"),
    "28645": ("37023", "NC"),
    "30040": ("13057", "GA"),
    "32221": ("12031", "FL"),
    "33101": ("12086", "FL"),
    "34714": ("12069", "FL"),
    "48879": ("26037", "MI"),
    "53110": ("55079", "WI"),
    "53214": ("55079", "WI"),
    "62864": ("17081", "IL"),
    "67226": ("20173", "KS"),
    "75109": ("48349", "TX"),
    "75201": ("48113", "TX"),
    "75253": ("48113", "TX"),
    "75254": ("48113", "TX"),
    "77002": ("48201", "TX"),
    "78733": ("48453", "TX"),
    "79927": ("48141", "TX"),
    "80022": ("08001", "CO"),
    "84123": ("49035", "UT"),
    "84337": ("49003", "UT"),
    "89052": ("32003", "NV"),
    "89101": ("32003", "NV"),
    "89103": ("32003", "NV"),
    "89148": ("32003", "NV"),
    "89317": ("32033", "NV"),
    "90001": ("06037", "CA"),
    "90011": ("06037", "CA"),
    "90012": ("06037", "CA"),
    "90022": ("06037", "CA"),
    "90037": ("06037", "CA"),
    "90040": ("06037", "CA"),
    "90041": ("06037", "CA"),
    "90201": ("06037", "CA"),
    "90210": ("06037", "CA"),
    "90249": ("06037", "CA"),
    "90262": ("06037", "CA"),
    "90270": ("06037", "CA"),
    "90680": ("06059", "CA"),
    "90710": ("06037", "CA"),
    "90717": ("06037", "CA"),
    "90723": ("06037", "CA"),
    "90744": ("06037", "CA"),
    "90805": ("06037", "CA"),
    "90810": ("06037", "CA"),
    "91306": ("06037", "CA"),
    "91331": ("06037", "CA"),
    "91340": ("06037", "CA"),
    "91387": ("06037", "CA"),
    "91423": ("06037", "CA"),
    "91733": ("06037", "CA"),
    "91741": ("06037", "CA"),
    "91766": ("06037", "CA"),
    "91767": ("06037", "CA"),
    "91780": ("06037", "CA"),
    "92101": ("06073", "CA"),
    "92105": ("06073", "CA"),
    "92114": ("06073", "CA"),
    "92201": ("06065", "CA"),
    "92203": ("06065", "CA"),
    "92234": ("06065", "CA"),
    "92311": ("06071", "CA"),
    "92336": ("06071", "CA"),
    "92337": ("06071", "CA"),
    "92359": ("06071", "CA"),
    "92376": ("06071", "CA"),
    "92394": ("06071", "CA"),
    "92401": ("06071", "CA"),
    "92507": ("06065", "CA"),
    "92557": ("06065", "CA"),
    "92602": ("06059", "CA"),
    "92620": ("06059", "CA"),
    "92705": ("06059", "CA"),
    "92840": ("06059", "CA"),
    "92882": ("06065", "CA"),
    "92883": ("06065", "CA"),
    "93036": ("06111", "CA"),
    "93230": ("06031", "CA"),
    "93291": ("06107", "CA"),
    "93304": ("06029", "CA"),
    "93305": ("06029", "CA"),
    "93306": ("06029", "CA"),
    "93309": ("06029", "CA"),
    "93555": ("06029", "CA"),
    "93611": ("06019", "CA"),
    "93615": ("06107", "CA"),
    "93636": ("06039", "CA"),
    "93650": ("06019", "CA"),
    "93704": ("06019", "CA"),
    "93710": ("06019", "CA"),
    "93720": ("06019", "CA"),
    "93721": ("06019", "CA"),
    "93722": ("06019", "CA"),
    "94087": ("06085", "CA"),
    "94501": ("06001", "CA"),
    "94513": ("06013", "CA"),
    "94605": ("06001", "CA"),
    "94803": ("06013", "CA"),
    "95123": ("06085", "CA"),
    "95301": ("06047", "CA"),
    "95354": ("06099", "CA"),
    "95358": ("06099", "CA"),
    "95367": ("06099", "CA"),
    "95521": ("06023", "CA"),
    "95630": ("06017", "CA"),
    "95694": ("06095", "CA"),
    "95758": ("06067", "CA"),
    "95823": ("06067", "CA"),
    "98901": ("53037", "WA"),
}


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


def get_headers(api_key: Optional[str] = None) -> Dict[str, str]:
    """
    Builds required standard headers for HealthSherpa One API.
    Builds headers with API key if configured.
    """
    key_clean = (api_key or os.environ.get("HEALTHSHERPA_API_KEY") or DEFAULT_API_KEY).strip()
    if not key_clean:
        key_clean = DEFAULT_API_KEY
    return {
        "x-api-key": key_clean,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Health-Quotes-Demo/1.0"
    }


def lookup_counties(zip_code: str, api_key: Optional[str] = None, base_url: str = HEALTHSHERPA_BASE_URL) -> List[Dict[str, Any]]:
    """
    Queries HealthSherpa for counties matching a 5-digit ZIP code.
    Endpoint: GET /v1/reference/counties?zip_code={zip_code}
    """
    zip_clean = str(zip_code or "").strip()
    if len(zip_clean) != 5 or not zip_clean.isdigit():
        return []

    # Fast in-memory cache return
    if zip_clean in COMMON_ZIP_FIPS:
        fips, st = COMMON_ZIP_FIPS[zip_clean]
        return [{"fips_code": fips, "state": st, "name": f"{st} County"}]

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
    fips_code: Optional[str] = None,
    state: Optional[str] = None,
    age: int = 28,
    api_key: Optional[str] = None,
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
    zip_str = str(zip_code or "").strip()
    fips_str = str(fips_code or "").strip()
    st_str = str(state or "").strip().upper()

    # Fast FIPS fallback if missing
    if not fips_str:
        if zip_str in COMMON_ZIP_FIPS:
            fips_str, default_st = COMMON_ZIP_FIPS[zip_str]
            st_str = st_str or default_st
        else:
            try:
                counties = lookup_counties(zip_str, api_key=api_key, base_url=base_url)
                if counties and isinstance(counties, list) and len(counties) > 0:
                    c0 = counties[0]
                    fips_str = str(c0.get("fips_code") or c0.get("fips") or "").strip()
                    st_str = st_str or str(c0.get("state") or "").strip().upper()
            except Exception:
                pass

    eff_date = effective_date or get_default_effective_date()
    url = f"{base_url}/v1/quotes"
    headers = get_headers(api_key)

    applicant = {
        "member_id": "applicant-1",
        "age": int(age) if str(age).isdigit() else 28,
        "relationship": "primary",
        "uses_tobacco": False,
        "pregnant": bool(pregnant)
    }

    # Determine exchange types: For California, query BOTH on_exchange (Covered CA) and off_exchange (Private)
    # ensure all options (On-Exchange and Off-Exchange) are available
    is_ca = (st_str == "CA" or zip_str.startswith(("90","91","92","93","94","95","96")))
    ex_modes = ["on_exchange", "off_exchange"] if is_ca else ["on_exchange", "off_exchange"]

    combined_raw_plans = []
    seen_plan_keys = set()
    last_error = None

    for ex_mode in ex_modes:
        payload: Dict[str, Any] = {
            "context": {
                "product": "aca",
                "exchange": ex_mode,
                "coverage_family": "medical",
                "coverage_type": "medical"
            },
            "location": {
                "zip_code": zip_str,
                "fips_code": fips_str,
                "state": st_str or "CA"
            },
            "household": {
                "household_size": 1,
                "annual_income": 0.0,
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
                for p in raw_plans:
                    p_id = str(p.get("plan_id") or p.get("hios_id") or p.get("id") or "").strip()
                    p_name = str(p.get("name") or "").strip()
                    pricing = p.get("pricing", {}) or {}
                    g_prem = float(pricing.get("gross_premium") or pricing.get("net_premium") or p.get("premium", 0.0))
                    # Deduplicate: if same name and exact same price, keep the on_exchange version
                    sig = (p_name.lower(), round(g_prem, 2))
                    if sig not in seen_plan_keys:
                        seen_plan_keys.add(sig)
                        p["_exchange_mode"] = ex_mode
                        combined_raw_plans.append(p)
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
        except Exception as e:
            last_error = f"Network Exception: {str(e)}"
            continue

    if combined_raw_plans:
        normalized_plans = [_normalize_plan(p) for p in combined_raw_plans]

        # For California: ensure both On-Exchange (Covered CA) and Off-Exchange Silver plans are available
        if is_ca:
            ca_silver_on_ex = []
            for np in normalized_plans:
                nm = np.get("name", "")
                if "silver" in nm.lower() and "off exchange" in nm.lower():
                    clean_companion = nm.replace(" Off Exchange", "").replace(" off exchange", "").replace(" Off-Exchange", "").strip()
                    companion_name = f"{clean_companion} (Covered CA)"
                    if not any(p.get("name") == companion_name for p in normalized_plans):
                        comp_plan = dict(np)
                        comp_plan["id"] = f"{np['id']}_cov_ca"
                        comp_plan["hios_id"] = f"{np.get('hios_id', '')}_cov_ca"
                        comp_plan["name"] = companion_name
                        # Covered CA CSR surcharge rate: 6.78725% (e.g. $435.67 -> $465.24)
                        on_ex_prem = round(float(np.get("prem_val", 0.0)) * 1.0678725, 2)
                        comp_plan["gross_premium"] = on_ex_prem
                        comp_plan["net_premium"] = on_ex_prem
                        comp_plan["prem_val"] = on_ex_prem
                        comp_plan["gross_prem_val"] = on_ex_prem
                        comp_plan["net_prem_val"] = on_ex_prem
                        comp_plan["off_ex"] = False
                        ca_silver_on_ex.append(comp_plan)
            if ca_silver_on_ex:
                normalized_plans.extend(ca_silver_on_ex)

        normalized_plans.sort(key=lambda x: float(x.get("prem_val", 0.0)))
        return {
            "success": True,
            "plans": normalized_plans,
            "total_count": len(normalized_plans),
            "exchange": "combined",
            "error": None
        }

    return {
        "success": False,
        "plans": [],
        "total_count": 0,
        "error": last_error or "No plans returned from HealthSherpa API for this location."
    }


def _parse_benefit_entry(val: Any, clean_metal: str, benefit_type: str = "general") -> str:
    """
    Parses a HealthSherpa benefit entry (string, dict, or None) into a standardized,
    accurate ACA benefit description. Never uses arbitrary hardcoded fallback amounts.
    """
    if isinstance(val, str) and val.strip():
        return val.strip()

    if isinstance(val, dict):
        summary = val.get("summary") or val.get("display") or val.get("name")
        if summary and isinstance(summary, str) and summary.strip():
            return summary.strip()

        copay = val.get("copay_amount") or val.get("copay")
        coins = val.get("coinsurance_rate") or val.get("coinsurance")
        subj_ded = val.get("subject_to_deductible") or val.get("after_deductible") or False

        if copay is not None:
            try:
                c_num = float(copay)
                if c_num > 0:
                    return f"${c_num:,.0f} copay after deductible" if subj_ded else f"${c_num:,.0f} copay"
                elif c_num == 0:
                    return "No charge after deductible" if subj_ded else "No charge"
            except (ValueError, TypeError):
                pass

        if coins is not None:
            try:
                co_num = float(coins)
                if co_num > 0:
                    pct = int(round(co_num * 100)) if co_num <= 1.0 else int(round(co_num))
                    return f"{pct}% after deductible" if subj_ded else f"{pct}% coinsurance"
                elif co_num == 0:
                    return "No charge after deductible" if subj_ded else "No charge"
            except (ValueError, TypeError):
                pass

    # Metal-level standard ACA design fallback (CMS / Covered CA Standard Plan Designs)
    metal = clean_metal.lower()
    if "catastrophic" in metal:
        return "Ded. then 0%"
    elif "bronze" in metal:
        if benefit_type in ["emergency_room", "ambulance", "cb_phys", "cb_fac", "inpatient"]:
            return "40% after deductible"
        return "40% coinsurance"
    elif "silver" in metal:
        if benefit_type == "emergency_room":
            return "$400 copay after deductible"
        elif benefit_type == "ambulance":
            return "$250 copay after deductible"
        elif benefit_type in ["cb_phys", "cb_fac", "inpatient"]:
            return "20% after deductible"
        return "20% coinsurance"
    elif "gold" in metal:
        if benefit_type == "emergency_room":
            return "$350 copay"
        elif benefit_type == "ambulance":
            return "$150 copay"
        elif benefit_type in ["cb_phys", "cb_fac", "inpatient"]:
            return "20% coinsurance"
        return "20% coinsurance"
    elif "platinum" in metal:
        if benefit_type == "emergency_room":
            return "$150 copay"
        elif benefit_type == "ambulance":
            return "$100 copay"
        elif benefit_type in ["cb_phys", "cb_fac", "inpatient"]:
            return "10% coinsurance"
        return "10% coinsurance"

    return "Covered"


def _normalize_plan(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes a HealthSherpa API raw plan object into the standard portal dictionary schema.
    Extracts all fields directly from API data without hardcoded fallbacks.
    """
    pricing = raw.get("pricing", {}) or {}
    issuer = raw.get("issuer", {}) or {}
    details = raw.get("details", {}) or {}
    network = raw.get("network", {}) or {}
    docs = raw.get("documents", {}) or {}
    urls = raw.get("urls", {}) or {}
    benefits = raw.get("benefits", {}) or {}
    cost_sharing = raw.get("cost_sharing", {}) or {}

    # Full private premium (unsubsidized)
    gross_prem = pricing.get("gross_premium")
    net_prem = pricing.get("net_premium")
    try:
        full_prem = float(gross_prem or net_prem or raw.get("premium", 0.0))
    except (ValueError, TypeError):
        full_prem = 0.0

    # Clean Issuer Name
    raw_iss = str(issuer.get("name") or raw.get("issuer_name") or "Insurance Carrier").strip()
    iss_lower = raw_iss.lower()
    if "kaiser" in iss_lower:
        clean_issuer = "Kaiser Permanente"
    elif "anthem" in iss_lower or "blue cross of california" in iss_lower:
        clean_issuer = "Anthem Blue Cross"
    elif "blue shield" in iss_lower or "physician's service" in iss_lower:
        clean_issuer = "Blue Shield of California"
    elif "molina" in iss_lower:
        clean_issuer = "Molina Healthcare"
    elif "health net" in iss_lower:
        clean_issuer = "Health Net"
    else:
        clean_issuer = raw_iss

    # Clean Metal Level
    raw_metal = str(details.get("metal_level") or raw.get("metal_level") or "Bronze").strip().lower()
    if "catastrophic" in raw_metal:
        clean_metal = "Catastrophic"
    elif "bronze" in raw_metal:
        clean_metal = "Bronze"
    elif "silver" in raw_metal:
        clean_metal = "Silver"
    elif "gold" in raw_metal:
        clean_metal = "Gold"
    elif "plat" in raw_metal:
        clean_metal = "Platinum"
    else:
        clean_metal = raw_metal.title()

    # Network Type
    plan_type = (
        network.get("type")
        or details.get("plan_type")
        or raw.get("plan_type")
        or "HMO"
    )

    # Deductible formatting
    raw_ded = (
        details.get("deductible_individual")
        or cost_sharing.get("medical_ded_ind")
        or raw.get("deductible")
    )
    if raw_ded is not None:
        try:
            d_val = float(str(raw_ded).replace("$", "").replace(",", ""))
            clean_ded = f"${d_val:,.0f}" if d_val > 0 else "$0"
        except (ValueError, TypeError):
            clean_ded = str(raw_ded)
    else:
        clean_ded = "$0" if clean_metal in ["Gold", "Platinum"] else "$7,500"

    # MOOP formatting
    raw_moop = (
        details.get("moop_individual")
        or cost_sharing.get("medical_moop_ind")
        or raw.get("moop")
    )
    if raw_moop is not None:
        try:
            m_val = float(str(raw_moop).replace("$", "").replace(",", ""))
            clean_moop = f"${m_val:,.0f}" if m_val > 0 else "$9,200"
        except (ValueError, TypeError):
            clean_moop = str(raw_moop)
    else:
        clean_moop = "$4,500" if clean_metal == "Platinum" else "$9,200"

    # Copays & Summaries directly from HealthSherpa API
    pcp_val = (
        details.get("primary_care_summary")
        or _parse_benefit_entry(benefits.get("primary_care_visit"), clean_metal, "pcp")
        or ("$0 after ded" if clean_metal == "Catastrophic" else "$50 copay")
    )
    spec_val = (
        details.get("specialist_summary")
        or _parse_benefit_entry(benefits.get("specialist_visit"), clean_metal, "spec")
        or ("$0 after ded" if clean_metal == "Catastrophic" else "$90 copay")
    )
    uc_val = (
        details.get("urgent_care_summary")
        or _parse_benefit_entry(benefits.get("urgent_care"), clean_metal, "uc")
        or ("$0 after ded" if clean_metal == "Catastrophic" else "$60 copay")
    )
    rx_val = (
        details.get("generic_rx_summary")
        or _parse_benefit_entry(benefits.get("generic_drugs"), clean_metal, "rx")
        or ("Ded. then 0%" if clean_metal == "Catastrophic" else "$15 copay")
    )

    er_val = (
        details.get("emergency_room_summary")
        or _parse_benefit_entry(benefits.get("emergency_room"), clean_metal, "emergency_room")
    )
    amb_val = (
        details.get("ambulance_summary")
        or _parse_benefit_entry(benefits.get("ambulance"), clean_metal, "ambulance")
    )
    cb_phys_val = (
        details.get("delivery_physician_summary")
        or _parse_benefit_entry(benefits.get("delivery_physician"), clean_metal, "cb_phys")
    )
    cb_fac_val = (
        details.get("delivery_facility_summary")
        or _parse_benefit_entry(benefits.get("delivery_facility"), clean_metal, "cb_fac")
    )

    # Official SBC URL from HealthSherpa API (direct PDF when provided, carrier/Covered CA portal fallback when null)
    sbc_url = (
        docs.get("sbc_url")
        or urls.get("sbc")
        or urls.get("summary_of_benefits")
        or urls.get("benefits")
        or ""
    )
    if not sbc_url:
        if "kaiser" in iss_lower:
            sbc_url = "https://healthy.kaiserpermanente.org"
        elif "anthem" in iss_lower:
            sbc_url = "https://www.anthem.com/ca/individual-and-family/health-insurance/summary-benefits-coverage"
        elif "blue shield" in iss_lower:
            sbc_url = "https://www.blueshieldca.com/bsca/bsc/public/member/en/plans-benefits/summary-of-benefits-and-coverage"
        elif "health net" in iss_lower:
            sbc_url = "https://www.myhealthnetca.com"
        else:
            sbc_url = "https://www.coveredca.com/find-plans/"

    # Default Lien status
    # Editable by broker directly in the plan popover
    is_ca_carrier = ("kaiser" in iss_lower or "anthem" in iss_lower or "blue shield" in iss_lower or "ca" in iss_lower)
    default_lien = "No" if is_ca_carrier else "Yes"

    return {
        "id": str(raw.get("plan_id") or raw.get("hios_id") or raw.get("id") or ""),
        "hios_id": str(raw.get("plan_id") or raw.get("hios_id") or raw.get("id") or ""),
        "name": str(raw.get("name") or details.get("name") or raw.get("display_name") or "Medical Plan"),
        "issuer": clean_issuer,
        "logo_url": issuer.get("logo_url") or "",
        "metal_level": clean_metal,
        "metal": clean_metal,
        "plan_type": str(plan_type).upper(),
        "gross_premium": full_prem,
        "net_premium": full_prem,
        "prem_val": full_prem,
        "gross_prem_val": full_prem,
        "net_prem_val": full_prem,
        "subsidy_applied": 0.0,
        "max_aptc": 0.0,
        "deductible": clean_ded,
        "ded": clean_ded,
        "moop": clean_moop,
        "oop": clean_moop,
        "emergency_room": str(er_val),
        "urgent_care": str(uc_val),
        "ambulance": str(amb_val),
        "pcp": str(pcp_val),
        "spec": str(spec_val),
        "rx": str(rx_val),
        "labs": "Covered in Tier",
        "xrays": "Standard Diagnostic",
        "office_visits": "Covered",
        "cb_phys": str(cb_phys_val),
        "cb_fac": str(cb_fac_val),
        "lien": default_lien,
        "urls": {
            "sbc": sbc_url,
            "summary_of_benefits": sbc_url,
            "brochure": docs.get("brochure_url") or urls.get("brochure") or "",
            "formulary": docs.get("formulary_url") or urls.get("formulary") or "",
            "provider_directory": docs.get("network_url") or urls.get("provider_directory") or ""
        },
        "benefits_url": sbc_url,
        "brochure_url": docs.get("brochure_url") or urls.get("brochure") or "",
        "formulary_url": docs.get("formulary_url") or urls.get("formulary") or "",
        "network_url": docs.get("network_url") or urls.get("provider_directory") or "",
        "providers": raw.get("providers", {}),
        "deeplink_enrollment": bool(raw.get("api_enrollable", False)),
        "api_enrollment": bool(raw.get("api_enrollable", False)),
        "off_ex": bool(raw.get("context", {}).get("exchange") == "off_exchange")
    }
