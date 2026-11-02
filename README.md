# MoSPI / PIB Watcher

**Status: early automation scaffold.** It converts Indian government press releases (PIB, the Press Information Bureau) into PDFs on GitHub Actions and reports the result to an external workflow tool.

## How it works

1. An external scheduler (an n8n workflow) finds new MoSPI press-release links and sends a `repository_dispatch` event of type `fetch-pdfs` carrying the links and a webhook URL.
2. [`fetch-pdfs.yml`](.github/workflows/fetch-pdfs.yml) installs Playwright and runs [`fetch_pdfs.py`](fetch_pdfs.py).
3. `fetch_pdfs.py` renders each page in headless Chromium and saves it as `pdfs/pib_<PRID>.pdf`. If rendering fails it falls back to PIB's direct PDF endpoint.
4. The PDFs are uploaded as a workflow artifact and a summary is posted to the webhook.

## Files

| File | Purpose |
| --- | --- |
| `fetch_pdfs.py` | Page to PDF conversion with a fallback |
| `.github/workflows/fetch-pdfs.yml` | The dispatch-triggered job |
| `processed_links.json`, `pdf_links.txt` | Empty placeholders for de-duplication state; not yet wired in |

## Run locally

```bash
pip install playwright beautifulsoup4 requests && playwright install chromium
python fetch_pdfs.py "https://pib.gov.in/PressReleaseIframePage.aspx?PRID=2138491"
```

## Known limitations

- De-duplication state is not implemented; the n8n side is assumed to do it.
- Dispatch payload values reach the job only through `env:` variables (no inline `${{ }}` in scripts), and the webhook post has a timeout and fails the job on an HTTP error. The workflow itself has not been run end to end since this change.
- There are no tests.
