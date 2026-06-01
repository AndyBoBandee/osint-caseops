from dataclasses import dataclass
import re


CLASSIFICATION_VERSION = "fraud-taxonomy-v1"

FRAUD_CATEGORIES = {
    "identity_theft",
    "account_takeover",
    "synthetic_identity",
    "imposter_scam",
    "business_email_compromise",
    "authorized_push_payment",
    "ach_fraud",
    "wire_fraud",
    "check_fraud",
    "mail_theft",
    "elder_fraud",
    "romance_scam",
    "crypto_investment_fraud",
    "securities_fraud",
    "tax_refund_fraud",
    "benefits_fraud",
    "healthcare_fraud",
    "money_mule",
    "cyber_enabled_fraud",
    "ransomware",
    "phishing",
    "smishing",
    "unknown",
}

PAYMENT_RAILS = {
    "ach",
    "wire",
    "check",
    "card",
    "cash",
    "crypto",
    "gift_card",
    "p2p",
    "zelle",
    "rtp",
    "unknown",
}

VICTIM_SEGMENTS = {
    "consumer",
    "elder",
    "business",
    "financial_institution",
    "government",
    "healthcare",
    "unknown",
}


@dataclass(frozen=True)
class Rule:
    label: str
    terms: tuple[str, ...]


@dataclass(frozen=True)
class TaxonomyClassification:
    fraud_category: str
    fraud_subcategory: str
    payment_rail: str
    victim_segment: str
    keywords_detected: list[str]
    classification_version: str
    classification_confidence: str


FRAUD_CATEGORY_RULES = (
    Rule("identity_theft", ("identity theft", "stolen identity", "stolen identities", "id theft")),
    Rule("account_takeover", ("account takeover", "account take over", "account hijack")),
    Rule("synthetic_identity", ("synthetic identity", "synthetic identities")),
    Rule("business_email_compromise", ("business email compromise", "bec scam", "email compromise")),
    Rule("authorized_push_payment", ("authorized push payment", "app fraud", "push payment")),
    Rule("ach_fraud", ("ach fraud", "automated clearing house")),
    Rule("wire_fraud", ("wire fraud", "wire transfer fraud")),
    Rule("check_fraud", ("check fraud", "cheque fraud", "fake check", "check washing", "washed check")),
    Rule("mail_theft", ("mail theft", "stolen mail")),
    Rule("elder_fraud", ("elder fraud", "elderly victim", "senior scam", "older adult")),
    Rule("romance_scam", ("romance scam", "romance fraud")),
    Rule("crypto_investment_fraud", ("crypto investment", "cryptocurrency investment", "virtual asset investment", "bitcoin investment")),
    Rule("securities_fraud", ("securities fraud", "investment fraud", "ponzi")),
    Rule("tax_refund_fraud", ("tax refund fraud", "tax fraud", "irs scam")),
    Rule("benefits_fraud", ("benefits fraud", "unemployment fraud", "child nutrition program")),
    Rule("healthcare_fraud", ("healthcare fraud", "health care fraud", "medicare fraud", "medicaid fraud")),
    Rule("money_mule", ("money mule", "money mules")),
    Rule("ransomware", ("ransomware",)),
    Rule("smishing", ("smishing", "sms phishing", "text message scam")),
    Rule("phishing", ("phishing", "spoofing")),
    Rule("cyber_enabled_fraud", ("cyber enabled", "cyber-enabled", "deepfake", "online fraud")),
    Rule("imposter_scam", ("imposter scam", "impersonation scam", "government impersonator", "romance impersonator", "scammer impersonating")),
)

PAYMENT_RAIL_RULES = (
    Rule("zelle", ("zelle",)),
    Rule("ach", ("ach", "automated clearing house")),
    Rule("wire", ("wire transfer", "wire fraud", "bank wire")),
    Rule("check", ("check washing", "check fraud", "fake check", "cheque")),
    Rule("card", ("credit card", "debit card", "card fraud")),
    Rule("crypto", ("crypto", "cryptocurrency", "bitcoin", "virtual asset", "digital asset")),
    Rule("gift_card", ("gift card", "gift cards")),
    Rule("p2p", ("peer-to-peer", "p2p", "payment app", "cash app", "venmo", "paypal")),
    Rule("rtp", ("real-time payment", "rtp")),
    Rule("cash", ("cash payment", "bulk cash", "cash smuggling")),
)

VICTIM_SEGMENT_RULES = (
    Rule("elder", ("elder", "elderly", "senior", "older adult")),
    Rule("business", ("business", "company", "corporate", "vendor", "employer")),
    Rule("financial_institution", ("financial institution", "bank", "credit union", "lender")),
    Rule("government", ("government", "federal", "state agency", "municipal")),
    Rule("healthcare", ("healthcare", "health care", "medicare", "medicaid", "hospital")),
    Rule("consumer", ("consumer", "customer", "victim", "borrower")),
)


def normalize_text(*values: str) -> str:
    return " ".join(" ".join(values).lower().split())


def term_matches(text: str, term: str) -> bool:
    escaped = re.escape(term.lower()).replace(r"\ ", r"[\s/-]+")
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None


def match_rules(text: str, rules: tuple[Rule, ...], fallback: str) -> tuple[str, list[str]]:
    for rule in rules:
        matched = [term for term in rule.terms if term_matches(text, term)]
        if matched:
            return rule.label, matched
    return fallback, []


def classify_fraud_taxonomy(title: str, snippet: str, publisher: str = "", source_url: str = "") -> TaxonomyClassification:
    text = normalize_text(title, snippet, publisher, source_url)
    fraud_category, fraud_terms = match_rules(text, FRAUD_CATEGORY_RULES, "unknown")
    payment_rail, rail_terms = match_rules(text, PAYMENT_RAIL_RULES, "unknown")
    victim_segment, victim_terms = match_rules(text, VICTIM_SEGMENT_RULES, "unknown")
    all_terms = []
    for term in [*fraud_terms, *rail_terms, *victim_terms]:
        if term not in all_terms:
            all_terms.append(term)

    if fraud_category != "unknown" and (payment_rail != "unknown" or victim_segment != "unknown"):
        confidence = "high"
    elif fraud_category != "unknown" or all_terms:
        confidence = "medium"
    else:
        confidence = "low"

    return TaxonomyClassification(
        fraud_category=fraud_category,
        fraud_subcategory=fraud_terms[0] if fraud_terms else "",
        payment_rail=payment_rail,
        victim_segment=victim_segment,
        keywords_detected=all_terms,
        classification_version=CLASSIFICATION_VERSION,
        classification_confidence=confidence,
    )
