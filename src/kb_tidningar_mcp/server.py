"""
KB Gamla Tidningar MCP Server
Ger AI-modeller tillgång till Kungliga bibliotekets (KB) digitaliserade
historiska svenska dagstidningar (1600-talet fram till ca 1908-1910).
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
import httpx
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP  # type: ignore

# Konfigurera loggning
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("kb-tidningar-mcp")

# Skapa MCP-instans
mcp = FastMCP(
    name="kb-tidningar",
    instructions="Sök i Kungliga bibliotekets (KB) historiska digitaliserade dagstidningar (1600-tal till ca 1908/1910)",
)

BASE_SEARCH_URL = "https://data.kb.se/search/"
BASE_DATA_URL = "https://data.kb.se/"
USER_AGENT = "KB-Tidningar-MCP/1.0 (+https://github.com/tobbaz/kb-tidningar-mcp; Slaktforskning och Historisk forskning)"

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
    """Utför asynkront HTTP-anrop med fair-usage exponential backoff för rate limits."""
    # Rensa None-värden från params
    cleaned_params = {k: v for k, v in (params or {}).items() if v is not None}

    async with httpx.AsyncClient(timeout=timeout, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
        backoff = 1.0
        for attempt in range(max_retries):
            try:
                resp = await client.get(url, params=cleaned_params)

                # Hantera rate limit / throttling (429 Too Many Requests eller 503)
                if resp.status_code in (429, 503):
                    retry_after = resp.headers.get("Retry-After")
                    sleep_time = float(retry_after) if retry_after else backoff
                    logger.warning(
                        "Fick HTTP %s från KB. Väntar %.1f sekunder (försök %d/%d)...",
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
                logger.error("HTTP-fel vid anrop till %s: %s", url, e)
                raise
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    logger.error("Nätverksfel efter %d försök: %s", max_retries, e)
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2.0

        raise RuntimeError(f"Kunde inte slutföra anrop till {url} efter {max_retries} försök.")


def _clean_date(date_str: Optional[str], is_end_date: bool = False) -> Optional[str]:
    """Konverterar årtal YYYY till fullständigt datum YYYY-MM-DD om det behövs."""
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
    Sök i Kungliga bibliotekets digitaliserade historiska tidningar (1600-tal till ca 1908).
    Söker i OCR-fulltexten och returnerar träffar på sidnivå med textutdrag/snippets.

    Args:
        query: Sökord eller fras (t.ex. 'ångfartyg', 'Carl von Linné', 'brand i Karlskrona').
        from_date: Startdatum i formatet 'YYYY-MM-DD' eller bara årtal 'YYYY' (t.ex. '1850').
        to_date: Slutdatum i formatet 'YYYY-MM-DD' eller bara årtal 'YYYY' (t.ex. '1899').
        newspaper: Begränsa till specifik tidning (t.ex. 'Aftonbladet', 'Dagens Nyheter', 'Post- och inrikes tidningar', 'Göteborgsposten').
        sort_by: Sorteringsordning: 'relevance' (mest relevant), 'date_asc' (äldst först) eller 'date_desc' (nyast först).
        limit: Antal träffar per anrop (1-100, standard 20).
        offset: Startindex för paginering (standard 0).
        max_snippets: Max antal textutdrag som visas per tidningssida (standard 5).
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
        "message": f"Visar träff {offset + 1}–{offset + len(hits)} av totalt {total}." if total > 0 else "Inga träffar hittades.",
        "hits": hits,
    }


@mcp.tool()
async def get_newspaper_timeline(
    query: str,
    field: str = "datePublished",
) -> Dict[str, Any]:
    """
    Hämta fördelning över tid eller tidningar för ett sökord.
    Perfekt för att se när en händelse omskrevs mest eller vilka tidningar som skrev om den.

    Args:
        query: Sökord (t.ex. 'kolera', 'ångbåt', 'Sveriges riksdag').
        field: Vad statistiken ska grupperas på: 'datePublished' (årtal) eller 'isPartOf' (tidningstitlar).
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
    Sök inom ett specifikt tidningsnummer för att hitta alla förekomster av ett ord
    med exakta textrader och koordinater för bildmarkering (IIIF Content Search).

    Args:
        package_id: Tidningsnumrets paket-ID (t.ex. 'dark-37858').
        query: Sökord att hitta i tidningsnumret.
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
    Generera direktlänkar och IIIF-bild-URL:er för en specifik tidningssida.

    Args:
        image_service_id: IIIF-tjänst-ID som returnerades från search_newspapers (t.ex. 'https://data.kb.se/iiif/3/dark-30466%2Fbib4345612_18620716_0_s_0003.jp2').
        package_id: Tidningsnumrets paket-ID (t.ex. 'dark-30466' eller 'dark-37858').
        page_number: Sidnummer (t.ex. 1, 3, 4).
        part_number: Delnummer (standard 1).
        width: Önskad bredd i pixlar på den genererade bilden (t.ex. 1200 för läsbar storlek, eller 300 för tumnagel).
    """
    image_urls: Dict[str, str] = {}
    pkg_id = package_id

    # Alternativ A: Om vi fick image_service_id direkt
    if image_service_id:
        image_urls = {
            "thumbnail": f"{image_service_id}/full/300,/0/default.jpg",
            "preview_width": f"{image_service_id}/full/{width},/0/default.jpg",
            "max_resolution": f"{image_service_id}/full/max/0/default.jpg",
            "info_json": f"{image_service_id}/info.json",
        }
        # Försök härleda package_id ur image_service_id om den saknas
        if not pkg_id and "dark-" in image_service_id:
            try:
                parts = image_service_id.split("dark-")
                pkg_id = "dark-" + parts[1].split("%2F")[0].split("/")[0]
            except Exception:
                pass

    # Alternativ B: Slå upp via package_id .jsonld om image_service_id inte angavs
    elif pkg_id:
        pkg_url = f"{BASE_DATA_URL}{pkg_id}.jsonld"
        try:
            pkg_data = await _make_request(pkg_url)
            files = pkg_data.get("includes", [])
            # Hitta filer som matchar sidnumret (t.ex. 0003.jp2 eller part-fil)
            padded_page = f"_{page_number:04d}."
            matched_file = None
            for f in files:
                fname = f.get("fileName", "")
                if fname.endswith(".jp2"):
                    if padded_page in fname or f"_{page_number}." in fname:
                        matched_file = fname
                        break
            # Fallback: om ingen specifik träffades, ta index (page_number - 1)
            if not matched_file:
                jp2_files = [f.get("fileName") for f in files if f.get("fileName", "").endswith(".jp2")]
                if 0 <= page_number - 1 < len(jp2_files):
                    matched_file = jp2_files[page_number - 1]

            if matched_file:
                img_srv = f"https://data.kb.se/iiif/3/{pkg_id}%2FJP2000%2F{matched_file}"
                image_urls = {
                    "thumbnail": f"{img_srv}/full/300,/0/default.jpg",
                    "preview_width": f"{img_srv}/full/{width},/0/default.jpg",
                    "max_resolution": f"{img_srv}/full/max/0/default.jpg",
                    "info_json": f"{img_srv}/info.json",
                }
        except Exception as e:
            logger.warning("Kunde inte hämta paketdata för %s: %s", pkg_id, e)

    # Slå upp URL:er på tidningar.kb.se och digitalt.kb.se
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
    Konvertera mellan Kungliga bibliotekets interna paket-ID (t.ex. 'dark-37858')
    och webblänk på tidningar.kb.se (t.ex. 'https://tidningar.kb.se/dxqth86q2n2zwg9').

    Args:
        id_or_url: Ett data.kb.se-ID, eller en länk/ID från tidningar.kb.se.
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
    """Starta MCP-servern via stdio."""
    logger.info("Startar KB Tidningar MCP-server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
