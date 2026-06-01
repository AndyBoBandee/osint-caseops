# Fraud Taxonomy

Fraud Monitor uses deterministic rule matching for `fraud-intel-source-pack-v1`. It does not use AI or LLM classification.

## Stored Tags

Each stored result keeps:

- `fraud_category`
- `fraud_subcategory`
- `payment_rail`
- `victim_segment`
- `keywords_detected`
- `classification_version`
- `classification_confidence`

The current classifier version is `fraud-taxonomy-v1`.

## Fraud Categories

Supported categories are:

`identity_theft`, `account_takeover`, `synthetic_identity`, `imposter_scam`, `business_email_compromise`, `authorized_push_payment`, `ach_fraud`, `wire_fraud`, `check_fraud`, `mail_theft`, `elder_fraud`, `romance_scam`, `crypto_investment_fraud`, `securities_fraud`, `tax_refund_fraud`, `benefits_fraud`, `healthcare_fraud`, `money_mule`, `cyber_enabled_fraud`, `ransomware`, `phishing`, `smishing`, and `unknown`.

## Payment Rails

Supported payment rail tags are:

`ach`, `wire`, `check`, `card`, `cash`, `crypto`, `gift_card`, `p2p`, `zelle`, `rtp`, and `unknown`.

## Victim Segments

Supported victim segment tags are:

`consumer`, `elder`, `business`, `financial_institution`, `government`, `healthcare`, and `unknown`.

## Confidence

Classification confidence is rule-derived:

- `high`: category plus payment rail or victim segment matched.
- `medium`: category or other taxonomy evidence matched.
- `low`: no deterministic taxonomy evidence matched.

These tags are triage aids. They are not fraud verdicts and require analyst review.
