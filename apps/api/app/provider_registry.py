from dataclasses import dataclass

from app.core.config import get_settings


SourceConfidence = str


@dataclass(frozen=True)
class ProviderMetadata:
    provider_id: str
    display_name: str
    source_type: str
    source_confidence: SourceConfidence
    default_enabled: bool
    requires_api_key: bool
    fixture_mode_supported: bool
    fraud_categories: tuple[str, ...]
    request_cap: int
    timeout_seconds: int
    safety_notes: str
    tier: str = "existing"
    enabled: bool = True
    alias_for: str = ""


DEFAULT_FRAUD_CATEGORIES = (
    "identity_theft",
    "imposter_scam",
    "wire_fraud",
    "check_fraud",
    "phishing",
    "unknown",
)


PROVIDER_REGISTRY: dict[str, ProviderMetadata] = {
    "gdelt_doc": ProviderMetadata(
        provider_id="gdelt_doc",
        display_name="GDELT DOC",
        source_type="news_index",
        source_confidence="medium",
        default_enabled=True,
        requires_api_key=False,
        fixture_mode_supported=True,
        fraud_categories=DEFAULT_FRAUD_CATEGORIES,
        request_cap=50,
        timeout_seconds=8,
        safety_notes="Public GDELT DOC metadata only; no article-body scraping.",
    ),
    "gdelt": ProviderMetadata(
        provider_id="gdelt",
        display_name="GDELT",
        source_type="news_index",
        source_confidence="medium",
        default_enabled=True,
        requires_api_key=False,
        fixture_mode_supported=True,
        fraud_categories=DEFAULT_FRAUD_CATEGORIES,
        request_cap=50,
        timeout_seconds=8,
        safety_notes="Legacy alias for GDELT DOC; public metadata only.",
        alias_for="gdelt_doc",
    ),
    "google_news_rss": ProviderMetadata(
        provider_id="google_news_rss",
        display_name="Google News RSS",
        source_type="news_rss",
        source_confidence="medium",
        default_enabled=True,
        requires_api_key=False,
        fixture_mode_supported=True,
        fraud_categories=DEFAULT_FRAUD_CATEGORIES,
        request_cap=50,
        timeout_seconds=8,
        safety_notes="Public RSS search only; store snippets and links as review leads.",
    ),
    "hn_algolia": ProviderMetadata(
        provider_id="hn_algolia",
        display_name="Hacker News Algolia",
        source_type="public_discussion_index",
        source_confidence="low",
        default_enabled=True,
        requires_api_key=False,
        fixture_mode_supported=True,
        fraud_categories=("cyber_enabled_fraud", "phishing", "unknown"),
        request_cap=50,
        timeout_seconds=8,
        safety_notes="Public story index only; not an official source.",
    ),
    "brave": ProviderMetadata(
        provider_id="brave",
        display_name="Brave News Search",
        source_type="news_search",
        source_confidence="medium",
        default_enabled=False,
        requires_api_key=True,
        fixture_mode_supported=False,
        fraud_categories=DEFAULT_FRAUD_CATEGORIES,
        request_cap=20,
        timeout_seconds=8,
        safety_notes="Optional detailed search; API key must stay local.",
    ),
    "fixture": ProviderMetadata(
        provider_id="fixture",
        display_name="Fixture",
        source_type="fixture",
        source_confidence="low",
        default_enabled=False,
        requires_api_key=False,
        fixture_mode_supported=True,
        fraud_categories=("identity_theft", "imposter_scam", "unknown"),
        request_cap=2,
        timeout_seconds=0,
        safety_notes="Deterministic test-only records; never use as real findings.",
    ),
    "doj_news": ProviderMetadata(
        provider_id="doj_news",
        display_name="DOJ News API",
        source_type="official_enforcement",
        source_confidence="high",
        default_enabled=False,
        requires_api_key=False,
        fixture_mode_supported=True,
        fraud_categories=("wire_fraud", "securities_fraud", "healthcare_fraud", "tax_refund_fraud", "elder_fraud", "unknown"),
        request_cap=50,
        timeout_seconds=8,
        safety_notes="Official DOJ press-release API; titles, URLs, dates, and summaries only.",
        tier="tier1",
    ),
    "cfpb_complaints": ProviderMetadata(
        provider_id="cfpb_complaints",
        display_name="CFPB Complaint API",
        source_type="official_complaint_data",
        source_confidence="high",
        default_enabled=False,
        requires_api_key=False,
        fixture_mode_supported=True,
        fraud_categories=("identity_theft", "account_takeover", "ach_fraud", "imposter_scam", "unknown"),
        request_cap=50,
        timeout_seconds=8,
        safety_notes="Public complaint metadata only; consumer narratives and PII are not stored.",
        tier="tier1",
    ),
    "fincen_advisories": ProviderMetadata(
        provider_id="fincen_advisories",
        display_name="FinCEN Advisories",
        source_type="official_advisory",
        source_confidence="high",
        default_enabled=False,
        requires_api_key=False,
        fixture_mode_supported=True,
        fraud_categories=("money_mule", "crypto_investment_fraud", "healthcare_fraud", "cyber_enabled_fraud", "unknown"),
        request_cap=25,
        timeout_seconds=8,
        safety_notes="Public advisory/key-term metadata only; linked PDFs are not scraped.",
        tier="tier1",
    ),
    "ftc_consumer_sentinel_import": ProviderMetadata(
        provider_id="ftc_consumer_sentinel_import",
        display_name="FTC Consumer Sentinel Import",
        source_type="official_annual_data_import",
        source_confidence="high",
        default_enabled=False,
        requires_api_key=False,
        fixture_mode_supported=True,
        fraud_categories=("identity_theft", "imposter_scam", "romance_scam", "crypto_investment_fraud", "unknown"),
        request_cap=100,
        timeout_seconds=0,
        safety_notes="Local analyst-provided annual CSV/zip data only; no live Consumer Sentinel API assumed.",
        tier="tier1",
    ),
    "sec_litigation_releases": ProviderMetadata(
        provider_id="sec_litigation_releases",
        display_name="SEC Litigation Releases",
        source_type="official_enforcement_stub",
        source_confidence="high",
        default_enabled=False,
        requires_api_key=False,
        fixture_mode_supported=False,
        fraud_categories=("securities_fraud", "crypto_investment_fraud", "unknown"),
        request_cap=0,
        timeout_seconds=0,
        safety_notes="Documented Tier 2 planned adapter; disabled until implemented.",
        tier="tier2_stub",
        enabled=False,
    ),
    "irs_ci_press_releases": ProviderMetadata(
        provider_id="irs_ci_press_releases",
        display_name="IRS Criminal Investigation Press Releases",
        source_type="official_enforcement_stub",
        source_confidence="high",
        default_enabled=False,
        requires_api_key=False,
        fixture_mode_supported=False,
        fraud_categories=("tax_refund_fraud", "money_mule", "unknown"),
        request_cap=0,
        timeout_seconds=0,
        safety_notes="Documented Tier 2 planned adapter; disabled until implemented.",
        tier="tier2_stub",
        enabled=False,
    ),
    "uspis_fraud": ProviderMetadata(
        provider_id="uspis_fraud",
        display_name="USPIS/USPS Fraud Source",
        source_type="official_advisory_stub",
        source_confidence="high",
        default_enabled=False,
        requires_api_key=False,
        fixture_mode_supported=False,
        fraud_categories=("check_fraud", "mail_theft", "imposter_scam", "unknown"),
        request_cap=0,
        timeout_seconds=0,
        safety_notes="Documented Tier 2 planned adapter; disabled until implemented.",
        tier="tier2_stub",
        enabled=False,
    ),
}


def provider_metadata(provider_id: str) -> ProviderMetadata | None:
    return PROVIDER_REGISTRY.get(provider_id.strip().lower())


def canonical_provider_id(provider_id: str) -> str:
    metadata = provider_metadata(provider_id)
    if metadata and metadata.alias_for:
        return metadata.alias_for
    return provider_id.strip().lower()


def all_provider_metadata() -> list[ProviderMetadata]:
    return list(PROVIDER_REGISTRY.values())


def is_provider_config_ready(provider_id: str) -> tuple[bool, str]:
    provider = provider_metadata(provider_id)
    settings = get_settings()
    if provider is None:
        return False, "Unsupported provider; remove it from the provider configuration."
    if not provider.enabled:
        return False, "Provider is documented but disabled until its adapter is implemented."
    if provider.provider_id == "fixture" and not settings.enable_fixture_provider:
        return False, "Set OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER=1 before using the fixture provider."
    if provider.requires_api_key and provider.provider_id == "brave" and not settings.brave_search_api_key:
        return False, "Set BRAVE_SEARCH_API_KEY before using Brave News Search."
    return True, "Ready for passive public search."
