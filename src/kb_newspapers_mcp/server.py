"""
KB Historical Newspapers MCP Server.

Provides AI assistants with access to the National Library of Sweden's (Kungliga biblioteket / KB)
digitized historical newspapers (from the 17th century up to circa 1908–1910).
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
import httpx

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP  # type: ignore

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("kb-newspapers-mcp")

# Initialize MCP instance
mcp = FastMCP(
    name="kb-newspapers",
    instructions=(
        "Search and retrieve digitized Swedish historical newspapers (17th century to circa 1908–1910) "
        "from the National Library of Sweden (Kungliga biblioteket / KB) open collections.\n\n"
        "RECOMMENDED HISTORICAL RESEARCH WORKFLOW & BEST PRACTICES:\n"
        "1. Orthography & Gothic/Fraktur OCR:\n"
        "   - Historical Swedish newspapers (especially before the late 19th century) were printed in Fraktur/blackletter.\n"
        "   - OCR engines frequently misrecognize letters (e.g. long 's' (ſ) as 'f' or 'S'; 'c' for 'e'; 'rn' for 'm').\n"
        "   - Spellings varied historically (e.g. 'c' vs 'k', 'fv' vs 'v', 'ph' vs 'p', 'dt' vs 't').\n"
        "   - If an initial search returns 0 or fewer hits than expected, ALWAYS try wildcards ('*') "
        "or Boolean OR (e.g. 'Carlscrona OR Karlskrona', 'Gustaf OR Gustav', or stem wildcards like 'Söder*').\n"
        "2. Two-Stage Search Workflow:\n"
        "   - Stage 1 (Discovery): Use 'search_newspapers' to locate issues, dates, pages, and snippet matches.\n"
        "   - Stage 2 (Deep Context): When snippets are truncated or lack surrounding sentences (e.g. to determine "
        "full names, causes of death, destinations, or accompanying persons), invoke 'search_in_issue(package_id, query)' "
        "on the relevant package_id to extract complete verbatim quotes and surrounding text.\n"
        "3. Verification via Images:\n"
        "   - Because historical OCR can be imperfect, always provide the direct image preview link from "
        "'images.preview_width' (or 'get_newspaper_page_image') so the user can visually verify the original printed text."
    ),
)

BASE_SEARCH_URL = "https://data.kb.se/search/"
BASE_DATA_URL = "https://data.kb.se/"
USER_AGENT = "KB-Newspapers-MCP/1.0 (+https://github.com/tobbaz/kb-newspapers-mcp; Historical Newspaper Research)"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": USER_AGENT,
}


async def _make_request(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    """Execute an asynchronous HTTP GET request with fair-usage exponential backoff for rate limits."""
    # Filter out None values from query parameters
    cleaned_params = {k: v for k, v in (params or {}).items() if v is not None}

    async with httpx.AsyncClient(timeout=timeout, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        backoff = 1.0
        for attempt in range(max_retries):
            try:
                resp = await client.get(url, params=cleaned_params)

                # Handle rate limiting / throttling (HTTP 429 Too Many Requests or 503)
                if resp.status_code in (429, 503):
                    retry_after = resp.headers.get("Retry-After")
                    sleep_time = float(retry_after) if retry_after else backoff
                    logger.warning(
                        "Received HTTP %s from KB. Backing off for %.1f seconds (attempt %d/%d)...",
                        resp.status_code,
                        sleep_time,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(sleep_time)
                    backoff *= 2.0
                    continue

                resp.raise_for_status()
                return resp.json()

            except httpx.HTTPStatusError as e:
                logger.error("HTTP error during request to %s: %s", url, e)
                raise
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    logger.error("Network error after %d attempts: %s", max_retries, e)
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2.0

        raise RuntimeError(f"Could not complete request to {url} after {max_retries} attempts.")


def _clean_date(date_str: Optional[str], is_end_date: bool = False) -> Optional[str]:
    """Convert a year string 'YYYY' into full ISO date format 'YYYY-MM-DD' if needed."""
    if not date_str:
        return None
    s = date_str.strip()
    if len(s) == 4 and s.isdigit():
        return f"{s}-12-31" if is_end_date else f"{s}-01-01"
    return s


@mcp.tool()
async def search_newspapers(
    query: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    newspaper: Optional[str] = None,
    sort_by: str = "relevance",
    limit: int = 20,
    offset: int = 0,
    max_snippets: int = 5,
) -> Dict[str, Any]:
    """
    Search digitized Swedish historical newspapers (17th century to circa 1908–1910).
    Performs OCR full-text search and returns page-level hits with highlighted snippets and image links.

    Historical Search & OCR Strategies:
    - Fraktur / Gothic Print: 17th to late 19th-century newspapers were mostly printed in Fraktur/blackletter.
      OCR engines frequently confuse similar glyphs (e.g. long 's' [ſ] misread as 'f', 'S', or 'l'; 'c' for 'e'; 'rn' for 'm').
    - Historical Spelling & Wildcards: Use wildcard '*' or Boolean 'OR' to catch spelling variations
      (e.g. 'Carlscrona OR Karlskrona', 'Gustaf OR Gustav', 'Linné OR Linnaeus', or stem wildcards like 'Söder*').
    - Two-Stage Workflow:
        1. Use this tool ('search_newspapers') for initial discovery of dates, issues, and page numbers.
        2. If snippets are cut off or you need surrounding sentences (e.g. destinations, causes of death, full names),
           call 'search_in_issue(package_id=..., query=...)' on the matched issue to retrieve complete verbatim quotes.
        3. Always present the 'images.preview_width' link so users can visually verify the scanned page if OCR is unclear.

    Args:
        query: Search term or phrase in Swedish/English (e.g. 'ångfartyg', 'Carl von Linné', 'brand i Karlskrona').
        from_date: Start date in 'YYYY-MM-DD' format or simply year 'YYYY' (e.g. '1850').
        to_date: End date in 'YYYY-MM-DD' format or simply year 'YYYY' (e.g. '1899').
        newspaper: Filter by specific newspaper title (e.g. 'Aftonbladet', 'Dagens Nyheter', 'Post- och inrikes tidningar', 'Göteborgsposten').
        sort_by: Sort order: 'relevance' (most relevant), 'date_asc' (oldest first), or 'date_desc' (newest first).
        limit: Number of results to return per page (1-100, default 20).
        offset: Zero-based starting index for pagination (default 0).
        max_snippets: Maximum number of text snippets to include per newspaper page (default 5).
    """
    limit = max(1, min(100, limit))
    offset = max(0, offset)

    sort_map = {
        "relevance": "relevance",
        "date_asc": "datePublished",
        "date_desc": "-datePublished",
    }
    kb_sort = sort_map.get(sort_by, "relevance")

    params = {
        "q": query,
        "searchGranularity": "part",
        "genreForm": "Dagstidningar",
        "_sort": kb_sort,
        "from": _clean_date(from_date, is_end_date=False),
        "to": _clean_date(to_date, is_end_date=True),
        "isPartOf": newspaper,
        "limit": limit,
        "offset": offset,
    }

    raw_data = await _make_request(BASE_SEARCH_URL, params=params)
    total = raw_data.get("total", 0)
    raw_hits = raw_data.get("hits", [])

    hits = []
    for h in raw_hits:
        file_package = h.get("hasFilePackage", {}).get("@id", "")
        package_id = file_package.rstrip("/").split("/")[-1] if file_package else None

        img_service = h.get("imageServiceId")
        img_urls = None
        if img_service:
            img_urls = {
                "thumbnail": f"{img_service}/full/300,/0/default.jpg",
                "medium": f"{img_service}/full/1200,/0/default.jpg",
                "max": f"{img_service}/full/max/0/default.jpg",
            }

        newspaper_title = h.get("isPartOf", {}).get("title") if h.get("isPartOf") else None
        snippets = h.get("snippets") or []
        if max_snippets and len(snippets) > max_snippets:
            snippets = snippets[:max_snippets]

        hits.append({
            "title": h.get("title"),
            "date": h.get("datePublished"),
            "newspaper": newspaper_title,
            "page": h.get("page"),
            "part": h.get("part"),
            "package_id": package_id,
            "page_id": h.get("@id"),
            "snippets": snippets,
            "images": img_urls,
        })

    next_offset = offset + limit if (offset + limit) < total else None

    return {
        "query": query,
        "total_hits": total,
        "returned_hits": len(hits),
        "offset": offset,
        "limit": limit,
        "next_offset": next_offset,
        "has_more": next_offset is not None,
        "message": f"Showing hits {offset + 1}–{offset + len(hits)} of {total} total." if total > 0 else "No hits found.",
        "hits": hits,
    }


@mcp.tool()
async def get_newspaper_timeline(
    query: str,
    field: str = "datePublished",
) -> Dict[str, Any]:
    """
    Get the temporal or newspaper distribution statistics for a search term.
    Useful to discover when an event was reported most frequently or which newspapers covered it.

    Args:
        query: Search term (e.g. 'kolera', 'ångbåt', 'Sveriges riksdag').
        field: Aggregation target: 'datePublished' (distribution by year) or 'isPartOf' (distribution by newspaper title).
    """
    params = {
        "q": query,
        "searchGranularity": "part",
        "genreForm": "Dagstidningar",
        "limit": 1,
    }

    raw_data = await _make_request(BASE_SEARCH_URL, params=params)
    total = raw_data.get("total", 0)
    aggs = raw_data.get("aggs", {})

    items = []
    if field in aggs and aggs[field]:
        values = aggs[field].get("values", [])
        for v in values:
            if v.get("count", 0) > 0:
                items.append({
                    "name": v.get("value"),
                    "count": v.get("count"),
                })

    return {
        "query": query,
        "total_hits": total,
        "grouped_by": field,
        "distribution": items,
    }


@mcp.tool()
async def search_in_issue(
    package_id: str,
    query: str,
) -> Dict[str, Any]:
    """
    Search inside a specific newspaper issue to locate all occurrences of a word or phrase
    with exact text lines and coordinates for image highlighting (IIIF Content Search).

    Two-Stage Workflow Usage:
    Use this tool as Stage 2 after 'search_newspapers' whenever a snippet is cut off or you need
    the complete surrounding sentence (e.g. to uncover full names, occupations, causes of death,
    travel origins/destinations, or accompanying persons).

    Args:
        package_id: The package ID of the newspaper issue (e.g. 'dark-37858').
        query: Search word or phrase to locate within the issue.
    """
    url = f"{BASE_SEARCH_URL}content/{package_id}"
    params = {"q": query}

    raw_data = await _make_request(url, params=params)

    annotations = []
    for page in raw_data.get("annotations", []):
        for item in page.get("items", []):
            target = item.get("target", {})
            selectors = target.get("selector", [])
            for s in selectors:
                if s.get("type") == "TextQuoteSelector":
                    prefix = s.get("prefix", "")
                    exact = s.get("exact", "")
                    suffix = s.get("suffix", "")
                    annotations.append({
                        "quote": f"{prefix}[{exact}]{suffix}".strip(),
                        "exact": exact,
                        "source": target.get("source"),
                    })

    return {
        "package_id": package_id,
        "query": query,
        "total_matches": len(annotations),
        "matches": annotations,
    }


@mcp.tool()
async def get_newspaper_page_image(
    image_service_id: Optional[str] = None,
    package_id: Optional[str] = None,
    page_number: int = 1,
    part_number: int = 1,
    width: int = 1200,
) -> Dict[str, Any]:
    """
    Generate direct image URLs and IIIF links for a specific newspaper page.

    Args:
        image_service_id: IIIF image service URL returned from search_newspapers (e.g. 'https://data.kb.se/iiif/3/dark-30466%2Fbib4345612_18620716_0_s_0003.jp2').
        package_id: Package ID of the newspaper issue (e.g. 'dark-30466' or 'dark-37858').
        page_number: Page number within the issue (e.g. 1, 3, 4).
        part_number: Part/section number (default 1).
        width: Desired pixel width for the preview image (e.g. 1200 for readable size, 300 for thumbnail).
    """
    image_urls: Dict[str, str] = {}
    pkg_id = package_id

    # Option A: If image_service_id was provided directly
    if image_service_id:
        image_urls = {
            "thumbnail": f"{image_service_id}/full/300,/0/default.jpg",
            "preview_width": f"{image_service_id}/full/{width},/0/default.jpg",
            "max_resolution": f"{image_service_id}/full/max/0/default.jpg",
            "info_json": f"{image_service_id}/info.json",
        }
        if not pkg_id and "dark-" in image_service_id:
            try:
                parts = image_service_id.split("dark-")
                pkg_id = "dark-" + parts[1].split("%2F")[0].split("/")[0]
            except Exception:
                pass

    # Option B: Look up via package_id .jsonld metadata
    elif pkg_id:
        pkg_url = f"{BASE_DATA_URL}{pkg_id}.jsonld"
        try:
            pkg_data = await _make_request(pkg_url)
            files = pkg_data.get("includes", [])
            padded_page = f"_{page_number:04d}."
            matched_file = None
            for f in files:
                fname = f.get("fileName", "")
                if fname.endswith(".jp2"):
                    if padded_page in fname or f"_{page_number}." in fname:
                        matched_file = fname
                        break
            if not matched_file:
                jp2_files = [f.get("fileName") for f in files if f.get("fileName", "").endswith(".jp2")]
                if 0 <= page_number - 1 < len(jp2_files):
                    matched_file = jp2_files[page_number - 1]

            if matched_file:
                clean_file = matched_file.lstrip("/")
                img_srv = f"https://data.kb.se/iiif/3/{pkg_id}%2F{clean_file}"
                image_urls = {
                    "thumbnail": f"{img_srv}/full/300,/0/default.jpg",
                    "preview_width": f"{img_srv}/full/{width},/0/default.jpg",
                    "max_resolution": f"{img_srv}/full/max/0/default.jpg",
                    "info_json": f"{img_srv}/info.json",
                }
        except Exception as e:
            logger.warning("Could not fetch package metadata for %s: %s", pkg_id, e)

    # Look up corresponding URLs on tidningar.kb.se and digitalt.kb.se
    tidningar_url = None
    digitalt_url = None
    if pkg_id:
        digitalt_url = f"https://digitalt.kb.se/{pkg_id}/part/{part_number}/page/{page_number}"
        lookup_url = f"{BASE_DATA_URL}lookup/"
        try:
            lookup_data = await _make_request(lookup_url, params={"id": pkg_id})
            tidningar_url = lookup_data.get("uri")
        except Exception:
            pass

    return {
        "package_id": pkg_id,
        "part": part_number,
        "page": page_number,
        "tidningar_kb_se_url": tidningar_url,
        "digitalt_kb_se_url": digitalt_url,
        "images": image_urls,
    }


@mcp.tool()
async def lookup_newspaper_id(
    id_or_url: str,
) -> Dict[str, Any]:
    """
    Convert bidirectionally between the National Library's internal package ID (e.g. 'dark-37858')
    and the public web URL on tidningar.kb.se (e.g. 'https://tidningar.kb.se/dxqth86q2n2zwg9').

    Args:
        id_or_url: A data.kb.se package ID, or a URL/ID from tidningar.kb.se.
    """
    clean_id = id_or_url.strip().rstrip("/").split("/")[-1]
    url = f"{BASE_DATA_URL}lookup/"
    data = await _make_request(url, params={"id": clean_id})
    return {
        "input": id_or_url,
        "resolved_id": data.get("id"),
        "resolved_url": data.get("uri"),
    }


def main():
    """Start the MCP server using stdio transport."""
    logger.info("Starting KB Historical Newspapers MCP Server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
