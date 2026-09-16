# KB Historical Newspapers (Gamla Tidningar) MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that provides AI assistants (such as Claude Desktop, Antigravity, Cursor, and other MCP-compliant clients) with direct programmatic access to the National Library of Sweden's (Kungliga biblioteket / KB) digitized historical newspapers from the 17th century up to circa 1908–1910.

Built in Python using **FastMCP** and **uv**.

---

## Key Features

- 🔍 **Full-Text Search (OCR):** Search across more than 2.2 million historical newspaper pages with highlighted text snippets (`<em>...</em>`) indicating matches.
- 📅 **Filtering & Sorting:** Filter by year or date range (e.g. `1850` to `1880` or `1862-07-01`), restrict searches to specific newspaper titles (e.g. *Aftonbladet*, *Dagens Nyheter*, *Post- och Inrikes Tidningar*, *Göteborgsposten*), and sort by relevance or publication date.
- 📈 **Timeline & Distribution:** Aggregate occurrences of a word, name, or event over time (by year) or across different publications.
- 🖼️ **High-Resolution Images (IIIF):** Construct direct image URLs for page previews and full-resolution scans using KB's IIIF Image API.
- 🔗 **Web Link Resolution:** Bidirectional lookup between internal dataset package IDs and public article pages on [tidningar.kb.se](https://tidningar.kb.se) and [digitalt.kb.se](https://digitalt.kb.se).
- 🕊️ **Fair-Usage & Resilience:** Automated exponential backoff for HTTP 429/503 responses, friendly User-Agent headers, and sane pagination defaults.

---

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)

To install `uv` on any platform, refer to the [official uv installation guide](https://docs.astral.sh/uv/getting-started/installation/), or run:

- **Linux / macOS:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Windows (PowerShell):**
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **Via Pip:**
  ```bash
  pip install uv
  ```

---

## Installation & Quickstart

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tobbaz/kb-tidningar-mcp.git
   cd kb-tidningar-mcp
   ```

2. **Run the server locally:**
   ```bash
   uv run kb-tidningar-mcp
   ```

3. **Execute integration tests:**
   ```bash
   uv run python test_server.py
   ```

---

## Client Configuration

### Claude Desktop
Add the server to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kb-tidningar": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "<path-to-repo>/kb-tidningar-mcp",
        "kb-tidningar-mcp"
      ]
    }
  }
}
```

### Antigravity / Gemini CLI (`mcp_config.json`)
```json
{
  "mcpServers": {
    "kb-tidningar": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "<path-to-repo>/kb-tidningar-mcp",
        "kb-tidningar-mcp"
      ]
    }
  }
}
```

*(Replace `<path-to-repo>` with the absolute path to where you cloned this repository.)*

---

## Available Tools

### 1. `search_newspapers`
Searches OCR full text across digitized historical Swedish newspapers.
- `query` *(string, required)*: Keyword or phrase (e.g. `"ångfartyg"`, `"Carl von Linné"`, `"August Strindberg"`).
- `from_date` *(optional)*: Start date (`'YYYY-MM-DD'` or year `'YYYY'`).
- `to_date` *(optional)*: End date (`'YYYY-MM-DD'` or year `'YYYY'`).
- `newspaper` *(optional)*: Filter by newspaper title (e.g. `'Aftonbladet'`, `'Dagens Nyheter'`).
- `sort_by` *(optional)*: `'relevance'` (default), `'date_asc'` (oldest first), or `'date_desc'` (newest first).
- `limit` *(int, default 20, max 100)*: Number of hits to return.
- `offset` *(int, default 0)*: Pagination starting index.
- `max_snippets` *(int, default 5)*: Maximum text snippets to return per page.

### 2. `get_newspaper_timeline`
Retrieves aggregation statistics for a search term over time or across publications.
- `query` *(string, required)*: Search term (e.g. `'kolera'`).
- `field` *(optional)*: Aggregation target: `'datePublished'` (by year) or `'isPartOf'` (by publication title).

### 3. `search_in_issue`
Searches within an individual newspaper issue using IIIF Content Search to return exact quotes and bounding-box coordinates.
- `package_id` *(string, required)*: Issue package identifier (e.g. `'dark-37858'`).
- `query` *(string, required)*: Word or phrase to locate.

### 4. `get_newspaper_page_image`
Generates IIIF image URLs and web links for a given newspaper page.
- `image_service_id` *(optional)*: IIIF service URL returned from `search_newspapers`.
- `package_id` *(optional)*: Issue package identifier (e.g. `'dark-30466'`).
- `page_number` *(int, default 1)*: Page number within the issue.
- `width` *(int, default 1200)*: Desired pixel width for preview images.

### 5. `lookup_newspaper_id`
Converts bidirectionally between `data.kb.se` package IDs and public web URLs on `tidningar.kb.se`.
- `id_or_url` *(string, required)*: E.g. `'dark-37858'` or `'https://tidningar.kb.se/dxqth86q2n2zwg9'`.

---

## Research Strategies & Best Practices for Historical OCR

Searching digitized newspapers from the 17th to early 20th century presents distinct challenges due to typography and historical spelling. Follow these general strategies for optimal results:

### 1. Gothic / Fraktur Script & OCR Glitches
Most Swedish newspapers before the late 19th century were printed in Fraktur (blackletter). OCR systems frequently misidentify character shapes:
- **Long 's' (ſ):** Often transcribed as `f`, `S`, or `l` (e.g. *Hilpershausen* scanned as *HilperShauftn*).
- **Vowel mutations & Ligatures:** Characters with umlauts or ligatures (`ä`, `ö`, `æ`, `oe`) may be parsed phonetically or stripped.
- **Similar letterforms:** `c` vs `e`, `rn` vs `m`, `v` vs `u`.

### 2. Wildcards and Alternative Orthography
Swedish spelling was only standardized in the early 20th century. When searching names, places, or terms:
- **Wildcard search (`*`):** Use stems (e.g. `Hilp*` or `Söder*`) to capture truncated OCR or spelling variants.
- **Boolean OR:** Combine historical variations (e.g. `Carlscrona OR Karlskrona`, `Gustaf OR Gustav`, `Capitain OR Kapten`).

### 3. The Recommended Two-Stage Workflow
1. **Stage 1 (Discovery):** Run `search_newspapers` with your query and date limits. Note the `package_id`, issue date, and page number of promising hits.
2. **Stage 2 (Deep Context):** If the snippets returned in Stage 1 are truncated or lack key context (e.g. destination of a traveller, cause of death, or family connections), call `search_in_issue(package_id="...", query="...")` on the relevant issue to extract full verbatim sentences and surrounding text quotes.
3. **Stage 3 (Visual Verification):** Open the direct image link (`images.preview_width` or `images.max`) to examine the original scanned page if the OCR text is degraded.

---

## Copyright & Fair Usage

- **Historical Scope:** Digitized newspapers published before circa 1908–1910 are in the public domain and made available as open data via [data.kb.se](https://data.kb.se). Modern newspapers are protected by copyright and are not included in this open API.
- **Fair Use:** The National Library implements rate throttling to ensure service availability. This server includes an identifying `User-Agent` and automated exponential backoff when encountering rate limits.

---

## License

MIT License. Metadata and digitized content are provided by the [National Library of Sweden (Kungliga biblioteket)](https://www.kb.se).
