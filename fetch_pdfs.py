import os
import re
import requests
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import datetime

async def convert_to_pdf(url, prid):
    """Convert webpage to PDF using headless browser"""
    filename = f"pib_{prid}.pdf"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            # Set longer timeout and wait for page to load
            await page.goto(url, timeout=60000, wait_until='networkidle')
            
            # Remove potentially problematic elements
            await page.evaluate('''() => {
                const elements = document.querySelectorAll('iframe, script, noscript');
                elements.forEach(el => el.remove());
            }''')
            
            # Generate PDF
            await page.pdf(path=filename, format='A4', print_background=True)
            await browser.close()
            
            file_size = os.path.getsize(filename)
            print(f"✓ Generated PDF: {filename} ({file_size//1024} KB)")
            return {
                "status": "success",
                "filename": filename,
                "size": file_size,
                "url": url
            }
            
    except Exception as e:
        print(f"✗ Failed to convert {url}: {str(e)[:100]}...")
        return {
            "status": "failed",
            "error": str(e),
            "url": url
        }

async def process_url(url):
    """Process a single PIB URL"""
    url = url.strip()
    if not url:
        return None
        
    print(f"\n🔍 Processing: {url}")
    try:
        prid = re.search(r'PRID=(\d+)', url).group(1)
        
        # First try direct PDF generation
        pdf_result = await convert_to_pdf(url, prid)
        
        if pdf_result['status'] == 'success':
            return {
                "url": url,
                "prid": prid,
                "status": "success",
                "files": [pdf_result]
            }
        
        # Fallback to traditional PDF detection
        print("⚠️ Falling back to PDF detection")
        pdf_links = find_pdf_links(url)
        if pdf_links:
            downloaded = download_pdfs(pdf_links, prid)
            if downloaded:
                return {
                    "url": url,
                    "prid": prid,
                    "status": "success",
                    "files": downloaded
                }
        
        return {
            "url": url,
            "prid": prid,
            "status": "failed",
            "error": "No PDF generated or found"
        }
        
    except Exception as e:
        print(f"⚠️ Error processing URL: {str(e)[:100]}...")
        return {
            "url": url,
            "status": "error",
            "error": str(e)
        }

def find_pdf_links(url):
    """Fallback PDF link detection"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        pdf_links = set()
        prid = re.search(r'PRID=(\d+)', url).group(1)
        
        # Standard PIB PDF pattern
        primary_pdf = f"https://pib.gov.in/Utilities/GeneratePdf.aspx?ID={prid}"
        pdf_links.add(primary_pdf)
        
        # All PDF links on page
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if href.endswith('.pdf'):
                absolute_url = urljoin(url, a['href'])
                pdf_links.add(absolute_url)
        
        return list(pdf_links)
    except Exception as e:
        print(f"⚠️ PDF detection failed: {str(e)[:100]}...")
        return []

def download_pdfs(pdf_links, prid):
    """Fallback PDF downloader"""
    downloaded = []
    for i, pdf_url in enumerate(pdf_links):
        try:
            suffix = f"_{i}" if len(pdf_links) > 1 else ""
            filename = f"pib_{prid}{suffix}.pdf"
            
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
            
            if 'pdf' in response.headers.get('content-type', '').lower():
                with open(filename, 'wb') as f:
                    f.write(response.content)
                downloaded.append({
                    "filename": filename,
                    "size": len(response.content),
                    "url": pdf_url,
                    "method": "direct_download"
                })
                print(f"✓ Downloaded {filename} ({len(response.content)//1024} KB)")
            else:
                print(f"✗ Skipping non-PDF: {pdf_url}")
        except Exception as e:
            print(f"✗ Download failed {pdf_url}: {str(e)[:100]}...")
    
    return downloaded

async def process_all_urls(urls):
    """Process all URLs concurrently"""
    return await asyncio.gather(*[process_url(url) for url in urls])

def send_to_n8n(webhook_url, results):
    """Send results to n8n webhook"""
    if not webhook_url or webhook_url == "YOUR_N8N_WEBHOOK_URL":
        return
        
    try:
        payload = {
            "timestamp": datetime.datetime.now().isoformat(),
            "processed_urls": len(results),
            "successful": sum(1 for r in results if r and r.get('status') == 'success'),
            "failed": sum(1 for r in results if not r or r.get('status') != 'success'),
            "total_pdfs": sum(len(r.get('files', [])) for r in results if r),
            "details": [r for r in results if r]
        }
        response = requests.post(webhook_url, json=payload, timeout=15)
        response.raise_for_status()
        print("✅ Results sent to n8n successfully")
    except Exception as e:
        print(f"⚠️ Failed to send to n8n: {str(e)[:100]}...")

if __name__ == "__main__":
    urls_str = os.environ.get('PDF_URLS', '')
    webhook_url = os.environ.get('N8N_WEBHOOK', '')
    
    if not urls_str:
        print("⛔ No URLs provided in PDF_URLS environment variable")
        exit(1)
    
    urls = [url.strip() for url in urls_str.split(',') if url.strip()]
    print(f"📥 Processing {len(urls)} PIB URLs")
    
    # Run async processing
    results = asyncio.run(process_all_urls(urls))
    
    # Filter out None results and send to n8n
    valid_results = [r for r in results if r]
    send_to_n8n(webhook_url, valid_results)
    
    # Determine exit code
    success_rate = sum(1 for r in valid_results if r.get('status') == 'success') / len(valid_results)
    exit(0 if success_rate > 0.5 else 1)
