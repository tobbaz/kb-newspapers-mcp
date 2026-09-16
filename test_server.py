"""
Testskript för KB Gamla Tidningar MCP-server.
Testar verktygen direkt för att verifiera anrop, datastrukturer och felhantering.
"""

import asyncio
from kb_tidningar_mcp.server import (
    search_newspapers,
    get_newspaper_timeline,
    search_in_issue,
    get_newspaper_page_image,
    lookup_newspaper_id,
)


async def run_tests():
    print("=== Test 1: Sökning i gamla tidningar (search_newspapers) ===")
    res1 = await search_newspapers(
        query="ångbåt",
        from_date="1860",
        to_date="1865",
        newspaper="Aftonbladet",
        limit=2,
    )
    print(f"Totalt antal träffar: {res1['total_hits']}")
    print(f"Meddelande: {res1['message']}")
    assert res1["total_hits"] > 0, "Förväntade träffar på ångbåt"
    hit = res1["hits"][0]
    print(f"Första träff: {hit['title']} ({hit['date']}), sida {hit['page']}")
    print(f"Snippets: {hit['snippets']}")
    print(f"Bilder: {hit['images']}")
    package_id = hit["package_id"]
    print(f"Paket-ID: {package_id}")

    print("\n=== Test 2: Tidslinje och statistik (get_newspaper_timeline) ===")
    res2 = await get_newspaper_timeline(query="kolera", field="datePublished")
    print(f"Kolera totalt: {res2['total_hits']}")
    print(f"Årtalsfördelning (första 5): {res2['distribution'][:5]}")
    assert len(res2["distribution"]) > 0, "Förväntade årtalsfördelning"

    res2_paper = await get_newspaper_timeline(query="kolera", field="isPartOf")
    print(f"Tidningsfördelning (topp 3): {res2_paper['distribution'][:3]}")

    print("\n=== Test 3: ID-lookup (lookup_newspaper_id) ===")
    res3 = await lookup_newspaper_id(id_or_url=package_id)
    print(f"Input: {res3['input']}")
    print(f"Webb-URL på tidningar.kb.se: {res3['resolved_url']}")
    assert res3["resolved_url"] is not None, "Kunde inte slå upp webb-URL"

    print("\n=== Test 4: Hämta sidbild och IIIF (get_newspaper_page_image) ===")
    res4 = await get_newspaper_page_image(package_id=package_id, page_number=hit["page"] or 1)
    print(f"Tidningar.kb.se: {res4.get('tidningar_kb_se_url')}")
    print(f"Bildlänkar: {res4.get('images')}")
    assert "preview_width" in res4.get("images", {}), "Förväntade IIIF bild-URL"

    print("\n=== Test 5: Innehållssökning inom tidningsnummer (search_in_issue) ===")
    res5 = await search_in_issue(package_id=package_id, query="ångbåt")
    print(f"Träffar inom numret: {res5['total_matches']}")
    if res5["matches"]:
        print(f"Exempelcitat: {res5['matches'][0]['quote']}")

    print("\nALLA TESTER GICK IGENOM FRAMGÅNGSRIKT!")


if __name__ == "__main__":
    asyncio.run(run_tests())
