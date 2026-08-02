import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st

from core.job_sources import load_job_sources, source_key


INTERVIEW_PROCESS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "interview_processes.json"
)

PUBLIC_TICKERS = {
    "Adyen": "ADYEN.AS",
    "Amplitude": "AMPL",
    "Bill.com": "BILL",
    "Braze": "BRZE",
    "C3.ai": "AI",
    "Cloudflare": "NET",
    "Coinbase": "COIN",
    "Confluent": "CFLT",
    "Datadog": "DDOG",
    "DigitalOcean": "DOCN",
    "Elastic": "ESTC",
    "Fastly": "FSLY",
    "Freshworks": "FRSH",
    "GitLab": "GTLB",
    "HubSpot": "HUBS",
    "IDT": "IDT",
    "Instacart": "CART",
    "Klaviyo": "KVYO",
    "MongoDB": "MDB",
    "NielsenIQ": None,
    "PagerDuty": "PD",
    "Paytm": "PAYTM.NS",
    "Rubrik": "RBRK",
    "Reddit": "RDDT",
    "Robinhood": "HOOD",
    "Samsara": "IOT",
    "ServiceNow": "NOW",
    "SIXT": "SIX2.DE",
    "Snowflake": "SNOW",
    "Twilio": "TWLO",
    "Veeva Systems": "VEEV",
    "Visa": "V",
    "Western Digital": "WDC",
    "Experian": "EXPN.L",
}

_PAY_RANGE_PATTERN = re.compile(
    r"(?P<currency>USD|INR|EUR|GBP|\$|₹|€|£)\s*"
    r"(?P<minimum>\d[\d,]*(?:\.\d+)?\s*(?:k|m|lakh|lakhs|crore)?)"
    r"\s*(?:-|–|—|to)\s*"
    r"(?:(?:USD|INR|EUR|GBP|\$|₹|€|£)\s*)?"
    r"(?P<maximum>\d[\d,]*(?:\.\d+)?\s*(?:k|m|lakh|lakhs|crore)?)"
    r"(?:\s*(?:per year|annually|annual|per annum|per hour|hourly))?",
    re.I,
)

_SINGLE_PAY_PATTERN = re.compile(
    r"(?P<currency>USD|INR|EUR|GBP|\$|₹|€|£)\s*"
    r"(?P<amount>\d[\d,]*(?:\.\d+)?\s*(?:k|m|lakh|lakhs|crore))"
    r"(?:\s*(?:per year|annually|annual|per annum|per hour|hourly))",
    re.I,
)


def get_company_metadata(source, company):
    if source == "microsoft_careers":
        return {
            "company": "Microsoft",
            "category": "Product and cloud infrastructure",
            "platform": "Eightfold",
            "careers_url": "https://apply.careers.microsoft.com/careers",
            "ticker": "MSFT",
        }

    for configured in load_job_sources():
        if source_key(configured) != source:
            continue
        platform = configured["platform"]
        slug = configured["slug"]
        careers_urls = {
            "greenhouse": f"https://boards.greenhouse.io/{slug}",
            "lever": f"https://jobs.lever.co/{slug}",
            "ashby": f"https://jobs.ashbyhq.com/{slug}",
            "smartrecruiters": f"https://jobs.smartrecruiters.com/{slug}",
        }
        return {
            "company": configured["company"],
            "category": configured.get("category", "product").replace("-", " ").title(),
            "platform": platform.title(),
            "careers_url": careers_urls.get(platform),
            "ticker": PUBLIC_TICKERS.get(configured["company"]),
        }

    return {
        "company": company,
        "category": "Product company",
        "platform": "Official careers site",
        "careers_url": None,
        "ticker": PUBLIC_TICKERS.get(company),
    }


def extract_compensation(description):
    text = " ".join((description or "").split())
    ranges = []
    for pattern in (_PAY_RANGE_PATTERN, _SINGLE_PAY_PATTERN):
        for match in pattern.finditer(text):
            value = match.group(0).strip(" ,.;")
            if value not in ranges:
                ranges.append(value)
            if len(ranges) >= 3:
                break
        if ranges:
            break

    lowered = text.lower()
    equity_terms = ("equity", "stock option", "restricted stock", "rsu")
    bonus_terms = ("annual bonus", "performance bonus", "target bonus", "variable pay")
    benefit_terms = {
        "Health insurance": ("health insurance", "medical insurance", "healthcare coverage"),
        "Retirement": ("401(k)", "retirement plan", "provident fund"),
        "Paid leave": ("paid time off", "paid leave", "vacation"),
        "Learning support": ("learning budget", "education reimbursement", "tuition"),
    }
    return {
        "published_ranges": ranges,
        "equity_mentioned": any(term in lowered for term in equity_terms),
        "bonus_mentioned": any(term in lowered for term in bonus_terms),
        "benefits": [
            label
            for label, terms in benefit_terms.items()
            if any(term in lowered for term in terms)
        ],
    }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_quote(ticker):
    if not ticker:
        return None
    params = urlencode({"interval": "1d", "range": "5d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?{params}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload["chart"]["result"][0]
        metadata = result["meta"]
        price = metadata.get("regularMarketPrice")
        previous_close = metadata.get("chartPreviousClose")
        change_percent = None
        if price is not None and previous_close:
            change_percent = ((price - previous_close) / previous_close) * 100
        return {
            "ticker": ticker,
            "price": price,
            "currency": metadata.get("currency"),
            "exchange": metadata.get("exchangeName"),
            "change_percent": change_percent,
            "as_of": datetime.now(timezone.utc),
        }
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def _load_interview_processes():
    try:
        return json.loads(INTERVIEW_PROCESS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def get_interview_process(company, role_title):
    verified = _load_interview_processes().get(company)
    if verified:
        sources = verified.get("sources") or []
        return {
            "is_company_verified": True,
            "confidence": verified.get("confidence", "medium"),
            "sources": sources,
            "source_url": sources[0].get("url") if sources else None,
            "note": verified.get("note") or "Reported process; rounds may vary.",
            "steps": verified.get("steps") or [],
            "question_categories": verified.get("question_categories") or [],
            "role": role_title,
        }

    return {
        "is_company_verified": False,
        "confidence": "unverified",
        "sources": [],
        "source_url": None,
        "note": (
            f"No sourced {company}-specific sequence is stored yet. "
            "The following is a typical data-engineering process, not a guarantee."
        ),
        "steps": [
            "Recruiter or talent-acquisition screening",
            "SQL and Python coding or take-home assessment",
            "Data engineering technical discussion",
            "Data platform or system-design round",
            "Hiring-manager and behavioural discussion",
        ],
        "question_categories": [
            "SQL and Python",
            "ETL and data modelling",
            "Data platform system design",
            "Project and behavioural discussion",
        ],
        "role": role_title,
    }
