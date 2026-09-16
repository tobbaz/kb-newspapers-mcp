"""
Test suite for KB Historical Newspapers MCP Server.
Verifies API requests, data structures, and tool outputs directly.
"""

import asyncio
from kb_newspapers_mcp.server import (
    search_newspapers,
    get_newspaper_timeline,
    search_in_issue,
    get_newspaper_page_image,
    lookup_newspaper_id,
)


async def run_tests():
    print("=== Test 1: Search Historical Newspapers (search_newspapers) ===")
    res1 = await search_newspapers(
        query="ångbåt",
        from_date="1860",
        to_date="1865",
        newspaper="Aftonbladet",
        limit=2,
    )
    print(f"Total hits: {res1['total_hits']}")
    print(f"Message: {res1['message']}")
    assert res1["total_hits"] > 0, "Expected hits for query 'ångbåt'"
    hit = res1["hits"][0]
    print(f"First hit: {hit['title']} ({hit['date']}), page {hit['page']}")
    print(f"Snippets: {hit['snippets']}")
    print(f"Images: {hit['images']}")
    package_id = hit["package_id"]
    print(f"Package ID: {package_id}")

    print("\n=== Test 2: Timeline & Distribution (get_newspaper_timeline) ===")
    res2 = await get_newspaper_timeline(query="kolera", field="datePublished")
    print(f"Cholera total hits: {res2['total_hits']}")
    print(f"Year distribution (first 5): {res2['distribution'][:5]}")
    assert len(res2["distribution"]) > 0, "Expected year distribution data"

    res2_paper = await get_newspaper_timeline(query="kolera", field="isPartOf")
    print(f"Newspaper distribution (top 3): {res2_paper['distribution'][:3]}")

    print("\n=== Test 3: ID Lookup (lookup_newspaper_id) ===")
    res3 = await lookup_newspaper_id(id_or_url=package_id)
    print(f"Input: {res3['input']}")
    print(f"Resolved URL on tidningar.kb.se: {res3['resolved_url']}")
    assert res3["resolved_url"] is not None, "Could not resolve web URL"

    print("\n=== Test 4: Retrieve Page Image & IIIF (get_newspaper_page_image) ===")
    res4 = await get_newspaper_page_image(package_id=package_id, page_number=hit["page"] or 1)
    print(f"Tidningar.kb.se: {res4.get('tidningar_kb_se_url')}")
    print(f"Image links: {res4.get('images')}")
    assert "preview_width" in res4.get("images", {}), "Expected IIIF preview image URL"

    print("\n=== Test 5: Search Within Issue (search_in_issue) ===")
    res5 = await search_in_issue(package_id=package_id, query="ångbåt")
    print(f"Matches in issue: {res5['total_matches']}")
    if res5["matches"]:
        print(f"Sample quote: {res5['matches'][0]['quote']}")

    print("\nALL INTEGRATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
