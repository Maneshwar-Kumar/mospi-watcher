import os
import re
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def convert_to_pdf(url, output_dir="pdfs"):
    """Convert PIB page to PDF using headless browser"""
    os.makedirs(output_dir, exist_ok=True)
    prid = re.search(r'PRID=(\d+)', url).group(1)
    filename = f"{output_dir}/pib_{prid}.pdf"
    
    async with async_playwright() as p:
        # Launch browser with JS enabled
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            java_script_enabled=True,
            viewport={'width': 1280, 'height': 1080}
        )
        page = await context.new_page()
        
        try:
            # Load page with extended timeout
            await page.goto(url, timeout=60000, wait_until='networkidle')
            
            # Remove problematic elements
            await page.evaluate('''() => {
                document.querySelectorAll(
                    'iframe, script, noscript, .header, .footer, .navbar'
                ).forEach(el => el.remove());
            }''')
            
            # Generate PDF with print styles
            await page.pdf(
                path=filename,
                format='A4',
                print_background=True,
                margin={'top': '20mm', 'right': '20mm', 'bottom': '20mm', 'left': '20mm'}
            )
            return filename
            
        except Exception as e:
            print(f"✗ Failed to convert {url}: {str(e)}")
            return None
        finally:
            await browser.close()

async def process_urls(urls):
    """Process multiple URLs concurrently"""
    return await asyncio.gather(*[convert_to_pdf(url) for url in urls])

if __name__ == "__main__":
    urls = [
        "https://pib.gov.in/PressReleaseIframePage.aspx?PRID=2138823",
        # Add other URLs here
    ]
    
    print("🔄 Converting PIB pages to PDFs...")
    results = asyncio.run(process_urls(urls))
    successful = [r for r in results if r]
    print(f"✅ Generated {len(successful)} PDFs")
