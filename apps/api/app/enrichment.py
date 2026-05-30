from datetime import UTC, datetime
from html.parser import HTMLParser
import json
import socket
import sqlite3
import ssl
from typing import Any, Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.cases import connect, get_case_or_404, get_entity_or_404, normalize_domain


RunStatus = Literal["success", "partial", "failed"]
ModuleStatus = Literal["success", "failed", "skipped"]

HTTP_TIMEOUT_SECONDS = 8
MAX_BODY_BYTES = 128_000

router = APIRouter()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class ModuleResult(BaseModel):
    module_name: str
    status: ModuleStatus
    started_at: str
    completed_at: str
    result: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""


class EnrichmentRunRecord(BaseModel):
    id: str
    case_id: str
    entity_id: str
    module_name: str
    status: RunStatus
    started_at: str
    completed_at: str
    results: list[ModuleResult]
    error_message: str = ""
    created_at: str


class EnrichmentTarget(BaseModel):
    entity_type: str
    entity_value: str
    domain: str
    url: str
    hostname: str
    scheme: str
    port: int | None = None


class TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._inside_title = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._inside_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._parts.append(data)

    @property
    def title(self) -> str:
        return " ".join(" ".join(self._parts).split())


class RecordingRedirectHandler(HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.chain: list[dict[str, Any]] = []

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        self.chain.append(
            {
                "status_code": code,
                "from_url": req.full_url,
                "to_url": newurl,
            }
        )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def request_headers() -> dict[str, str]:
    return {
        "User-Agent": "OSINT-CaseOps/0.1 passive-enrichment",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def row_to_enrichment_run(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    result = json.loads(payload.pop("result_json"))
    payload["results"] = result.get("results", [])
    return payload


def derive_target(entity: dict[str, Any]) -> EnrichmentTarget:
    entity_type = entity["type"]
    entity_value = entity["value"]

    if entity_type == "domain":
        domain = normalize_domain(entity_value)
        url = f"https://{domain}/"
        return EnrichmentTarget(
            entity_type=entity_type,
            entity_value=entity_value,
            domain=domain,
            url=url,
            hostname=domain,
            scheme="https",
            port=None,
        )

    if entity_type == "url":
        parsed = urlsplit(entity_value)
        if parsed.hostname is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="URL entity must include a valid host before enrichment.",
            )
        host = parsed.hostname
        try:
            domain = normalize_domain(host)
        except ValueError:
            domain = host.strip().lower()
        port = parsed.port
        url = urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path or "/",
                parsed.query,
                "",
            )
        )
        return EnrichmentTarget(
            entity_type=entity_type,
            entity_value=entity_value,
            domain=domain,
            url=url,
            hostname=host,
            scheme=parsed.scheme,
            port=port,
        )

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Passive enrichment is available for domain and URL entities.",
    )


def fetch_url(url: str, max_body_bytes: int = MAX_BODY_BYTES) -> dict[str, Any]:
    redirect_handler = RecordingRedirectHandler()
    opener = build_opener(redirect_handler)
    request = Request(url, headers=request_headers(), method="GET")

    try:
        with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read(max_body_bytes)
            headers = dict(response.headers.items())
            return {
                "url": response.geturl(),
                "status_code": response.status,
                "headers": headers,
                "body": body,
                "redirect_chain": redirect_handler.chain,
            }
    except HTTPError as exc:
        body = exc.read(max_body_bytes)
        return {
            "url": exc.geturl(),
            "status_code": exc.code,
            "headers": dict(exc.headers.items()),
            "body": body,
            "redirect_chain": redirect_handler.chain,
        }
    except URLError as exc:
        raise RuntimeError(f"HTTP request failed: {exc.reason}") from exc


def fetch_status_only(url: str) -> dict[str, Any]:
    try:
        metadata = fetch_url(url, max_body_bytes=512)
    except RuntimeError as exc:
        raise exc

    return {
        "url": metadata["url"],
        "status_code": metadata["status_code"],
        "available": 200 <= int(metadata["status_code"]) < 400,
        "content_type": metadata["headers"].get("Content-Type", ""),
    }


def resolve_dns(target: EnrichmentTarget) -> dict[str, Any]:
    records = socket.getaddrinfo(target.domain, None, proto=socket.IPPROTO_TCP)
    addresses: list[str] = []
    for record in records:
        address = record[4][0]
        if address not in addresses:
            addresses.append(address)

    return {
        "domain": target.domain,
        "addresses": addresses,
        "record_count": len(addresses),
    }


def lookup_rdap(target: EnrichmentTarget) -> dict[str, Any]:
    url = f"https://rdap.org/domain/{quote(target.domain)}"
    request = Request(url, headers=request_headers(), method="GET")

    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read(MAX_BODY_BYTES).decode("utf-8", errors="replace"))
    except HTTPError as exc:
        raise RuntimeError(f"RDAP lookup returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"RDAP lookup failed: {exc}") from exc

    registrar = ""
    for entity in payload.get("entities", []):
        if "registrar" not in entity.get("roles", []):
            continue
        vcard = entity.get("vcardArray", [])
        if len(vcard) < 2:
            continue
        for item in vcard[1]:
            if item[0] == "fn" and len(item) >= 4:
                registrar = str(item[3])
                break
        if registrar:
            break

    return {
        "domain": payload.get("ldhName") or payload.get("name") or target.domain,
        "handle": payload.get("handle", ""),
        "status": payload.get("status", []),
        "registrar": registrar,
    }


def fetch_http_metadata(target: EnrichmentTarget) -> dict[str, Any]:
    metadata = fetch_url(target.url)
    body = metadata.pop("body")
    metadata["body_text"] = body.decode("utf-8", errors="replace")
    return metadata


def get_http_metadata(target: EnrichmentTarget, context: dict[str, Any]) -> dict[str, Any]:
    if "http_error" in context:
        raise RuntimeError(str(context["http_error"]))

    if "http" not in context:
        try:
            context["http"] = fetch_http_metadata(target)
        except RuntimeError as exc:
            context["http_error"] = str(exc)
            raise
    return context["http"]


def summarize_http_status(target: EnrichmentTarget, context: dict[str, Any]) -> dict[str, Any]:
    metadata = get_http_metadata(target, context)
    return {
        "requested_url": target.url,
        "final_url": metadata["url"],
        "status_code": metadata["status_code"],
    }


def summarize_redirect_chain(target: EnrichmentTarget, context: dict[str, Any]) -> dict[str, Any]:
    metadata = get_http_metadata(target, context)
    return {
        "requested_url": target.url,
        "final_url": metadata["url"],
        "redirect_count": len(metadata["redirect_chain"]),
        "redirect_chain": metadata["redirect_chain"],
    }


def summarize_tls_certificate(target: EnrichmentTarget) -> dict[str, Any]:
    port = target.port if target.scheme == "https" and target.port else 443
    context = ssl.create_default_context()

    try:
        with socket.create_connection((target.hostname, port), timeout=HTTP_TIMEOUT_SECONDS) as sock:
            with context.wrap_socket(sock, server_hostname=target.hostname) as tls_sock:
                certificate = tls_sock.getpeercert()
    except OSError as exc:
        raise RuntimeError(f"TLS connection failed: {exc}") from exc
    except ssl.SSLError as exc:
        raise RuntimeError(f"TLS certificate check failed: {exc}") from exc

    def get_name(parts: Any) -> str:
        for group in parts or []:
            for key, value in group:
                if key == "commonName":
                    return str(value)
        return ""

    sans = [
        value
        for key, value in certificate.get("subjectAltName", [])
        if key.lower() == "dns"
    ]

    return {
        "hostname": target.hostname,
        "port": port,
        "subject_common_name": get_name(certificate.get("subject")),
        "issuer_common_name": get_name(certificate.get("issuer")),
        "not_before": certificate.get("notBefore", ""),
        "not_after": certificate.get("notAfter", ""),
        "serial_number": certificate.get("serialNumber", ""),
        "subject_alt_names": sans[:20],
    }


SECURITY_HEADERS = [
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
]


def summarize_security_headers(target: EnrichmentTarget, context: dict[str, Any]) -> dict[str, Any]:
    metadata = get_http_metadata(target, context)
    headers = metadata["headers"]
    lower_headers = {key.lower(): value for key, value in headers.items()}
    present = {
        header: lower_headers[header.lower()]
        for header in SECURITY_HEADERS
        if header.lower() in lower_headers
    }

    return {
        "present": present,
        "missing": [header for header in SECURITY_HEADERS if header not in present],
    }


def extract_page_title(target: EnrichmentTarget, context: dict[str, Any]) -> dict[str, Any]:
    metadata = get_http_metadata(target, context)
    parser = TitleParser()
    parser.feed(metadata["body_text"])
    return {
        "url": metadata["url"],
        "title": parser.title,
    }


def check_robots_txt(target: EnrichmentTarget) -> dict[str, Any]:
    return fetch_status_only(urljoin(target.url, "/robots.txt"))


def check_sitemap(target: EnrichmentTarget) -> dict[str, Any]:
    return fetch_status_only(urljoin(target.url, "/sitemap.xml"))


ModuleRunner = Callable[[EnrichmentTarget, dict[str, Any]], dict[str, Any]]


def with_contextless_runner(
    runner: Callable[[EnrichmentTarget], dict[str, Any]],
) -> ModuleRunner:
    def wrapped(target: EnrichmentTarget, _: dict[str, Any]) -> dict[str, Any]:
        return runner(target)

    return wrapped


ENRICHMENT_MODULES: list[tuple[str, ModuleRunner]] = [
    ("dns_lookup", with_contextless_runner(resolve_dns)),
    ("rdap_lookup", with_contextless_runner(lookup_rdap)),
    ("http_status", summarize_http_status),
    ("redirect_chain", summarize_redirect_chain),
    ("tls_certificate", with_contextless_runner(summarize_tls_certificate)),
    ("security_headers", summarize_security_headers),
    ("page_title", extract_page_title),
    ("robots_txt", with_contextless_runner(check_robots_txt)),
    ("sitemap", with_contextless_runner(check_sitemap)),
]


def run_module(
    module_name: str,
    runner: ModuleRunner,
    target: EnrichmentTarget,
    context: dict[str, Any],
) -> dict[str, Any]:
    started_at = utc_now()
    try:
        result = runner(target, context)
        return ModuleResult(
            module_name=module_name,
            status="success",
            started_at=started_at,
            completed_at=utc_now(),
            result=result,
        ).model_dump()
    except Exception as exc:
        return ModuleResult(
            module_name=module_name,
            status="failed",
            started_at=started_at,
            completed_at=utc_now(),
            error_message=str(exc),
        ).model_dump()


def summarize_run_status(results: list[dict[str, Any]]) -> tuple[RunStatus, str]:
    failures = [result for result in results if result["status"] == "failed"]
    if not failures:
        return "success", ""
    if len(failures) == len(results):
        return "failed", "All enrichment modules failed."
    return (
        "partial",
        f"{len(failures)} enrichment module{'s' if len(failures) != 1 else ''} failed.",
    )


def store_enrichment_run(
    connection: sqlite3.Connection,
    entity: dict[str, Any],
    started_at: str,
    completed_at: str,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    run_id = str(uuid4())
    run_status, error_message = summarize_run_status(results)
    created_at = completed_at

    connection.execute(
        """
        INSERT INTO enrichment_runs (
            id,
            case_id,
            entity_id,
            module_name,
            status,
            started_at,
            completed_at,
            result_json,
            error_message,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            entity["case_id"],
            entity["id"],
            "passive_enrichment",
            run_status,
            started_at,
            completed_at,
            json.dumps({"results": results}),
            error_message,
            created_at,
        ),
    )
    connection.execute(
        "UPDATE cases SET updated_at = ? WHERE id = ?",
        (created_at, entity["case_id"]),
    )

    row = connection.execute("SELECT * FROM enrichment_runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise RuntimeError("Enrichment run was not stored.")

    return row_to_enrichment_run(row)


@router.get("/cases/{case_id}/enrichment-runs", response_model=list[EnrichmentRunRecord])
def list_case_enrichment_runs(case_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        get_case_or_404(case_id, connection)
        rows = connection.execute(
            """
            SELECT *
            FROM enrichment_runs
            WHERE case_id = ?
            ORDER BY created_at DESC
            """,
            (case_id,),
        ).fetchall()

    return [row_to_enrichment_run(row) for row in rows]


@router.get("/entities/{entity_id}/enrichment-runs", response_model=list[EnrichmentRunRecord])
def list_entity_enrichment_runs(entity_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        get_entity_or_404(entity_id, connection)
        rows = connection.execute(
            """
            SELECT *
            FROM enrichment_runs
            WHERE entity_id = ?
            ORDER BY created_at DESC
            """,
            (entity_id,),
        ).fetchall()

    return [row_to_enrichment_run(row) for row in rows]


@router.get("/enrichment-runs/{run_id}", response_model=EnrichmentRunRecord)
def get_enrichment_run(run_id: str) -> dict[str, Any]:
    with connect() as connection:
        row = connection.execute("SELECT * FROM enrichment_runs WHERE id = ?", (run_id,)).fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrichment run not found.")

    return row_to_enrichment_run(row)


@router.post(
    "/entities/{entity_id}/enrichment-runs",
    response_model=EnrichmentRunRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_enrichment_run(entity_id: str) -> dict[str, Any]:
    started_at = utc_now()

    with connect() as connection:
        entity = get_entity_or_404(entity_id, connection)
        target = derive_target(entity)
        context: dict[str, Any] = {}
        results = [
            run_module(module_name, runner, target, context)
            for module_name, runner in ENRICHMENT_MODULES
        ]

        return store_enrichment_run(connection, entity, started_at, utc_now(), results)
