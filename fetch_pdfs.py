import os
import re
import asyncio
from playwright.async_api import async_playwright
import requests
from datetime import datetime

async def convert_to_pdf(url, output_dir="pdfs"):
    """Convert PIB page to PDF using headless browser"""
    os.makedirs(output_dir, exist_ok=True)
    prid = re.search(r'PRID=(\d+)', url).group(1)
    filename = f"{output_dir}/pib_{prid}.pdf"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                java_script_enabled=True,
                viewport={'width': 1280, 'height': 1080}
            )
            page = await context.new_page()
            
            # Set longer timeout and wait for full load
            await page.goto(url, timeout=90000, wait_until='networkidle')
            
            # Clean up page before PDF generation
            await page.evaluate('''() => {
                // Remove unnecessary elements
                const elements = document.querySelectorAll(
                    'iframe, script, noscript, header, footer, nav, .social-share'
                );
                elements.forEach(el => el.remove());
                
                // Improve PDF readability
                document.body.style.padding = '20px';
                document.body.style.fontSize = '12pt';
            }''')
            
            await page.pdf(
                path=filename,
                format='A4',
                print_background=True,
                margin={'top': '20mm', 'right': '20mm', 'bottom': '20mm', 'left': '20mm'}
            )
            return filename
            
    except Exception as e:
        print(f"⚠️ Browser conversion failed for {url}, trying direct download... Error: {str(e)[:200]}")
        return await direct_download_pdf(url, prid, filename)

async def direct_download_pdf(url, prid, filename):
    """Fallback to direct PDF download"""
    try:
        pdf_url = f"https://pib.gov.in/Utilities/GeneratePdf.aspx?ID={prid}"
        response = requests.get(pdf_url, timeout=30)
        
        if 'application/pdf' in response.headers.get('content-type', ''):
            with open(filename, 'wb') as f:
                f.write(response.content)
            return filename
        return None
    except Exception as e:
        print(f"✗ Direct download failed for {url}: {str(e)[:200]}")
        return None

async def process_urls(urls):
    """Process URLs with progress tracking"""
    results = []
    for i, url in enumerate(urls, 1):
        print(f"\n🔍 Processing URL {i}/{len(urls)}: {url}")
        result = await convert_to_pdf(url)
        if result:
            print(f"✓ Generated: {result}")
            results.append({
                "url": url,
                "pdf_path": result,
                "timestamp": datetime.now().isoformat()
            })
    return results

if __name__ == "__main__":
    import sys
    urls = sys.argv[1:] if len(sys.argv) > 1 else [
        "https://pib.gov.in/PressReleaseIframePage.aspx?PRID=2138491"  # Default test URL
    ]
    
    print("🚀 Starting PDF conversion for", len(urls), "URLs")
    successful = asyncio.run(process_urls(urls))
    print(f"\n🎉 Successfully converted {len(successful)}/{len(urls)} URLs")
