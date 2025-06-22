import os
import re
import requests
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import datetime

def is_valid_pdf_link(href):
    """Check if link is a relevant PDF"""
    if not href or not isinstance(href, str):
        return False
    href = href.lower()
    if not href.endswith('.pdf'):
        return False
    if href.startswith('javascript:'):
        return False
    # Include specificdocs and other direct PDF links
    return ('specificdocs' in href or 
            'generatepdf.aspx' in href or
            '/pdf/' in href or
            '/document/' in href)

def find_pdf_links(url):
    """Find all relevant PDF links from a PIB page"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        pdf_links = set()
        prid_match = re.search(r'PRID=(\d+)', url)
        prid = prid_match.group(1) if prid_match else None
        
        # 1. Standard PIB PDF generation link
        if prid:
            primary_pdf = f"https://pib.gov.in/Utilities/GeneratePdf.aspx?ID={prid}"
            pdf_links.add(primary_pdf)
        
        # 2. Specificdocs PDFs (high priority attachments)
        for a in soup.find_all('a', href=True):
            href = a['href']
            if is_valid_pdf_link(href):
                if href.startswith('https://static.pib.gov.in/WriteReadData/specificdocs/'):
                    pdf_links.add(href)
                else:
                    absolute_url = urljoin(url, href)
                    pdf_links.add(absolute_url)
        
        # 3. PDFs in main content area only
        main_content = soup.find('div', {'id': 'ContentPlaceHolder1_Content'}) or soup
        for a in main_content.find_all('a', href=True):
            href = a['href']
            if is_valid_pdf_link(href) and not href.startswith('javascript:'):
                absolute_url = urljoin(url, href)
                pdf_links.add(absolute_url)
        
        return list(pdf_links)
    except Exception as e:
        print(f"⚠️ PDF detection failed for {url}: {str(e)[:100]}...")
        return []

async def convert_to_pdf(url, prid):
    """Convert webpage to PDF using headless browser"""
    filename = f"pib_{prid}.pdf"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            await page.goto(url, timeout=60000, wait_until='networkidle')
            
            # Clean up page before PDF generation
            await page.evaluate('''() => {
                // Remove unnecessary elements
                const selectors = [
                    'iframe', 'script', 'noscript',
                    '.header', '.footer', 
                    '.social-share', '.navigation'
                ];
                selectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => el.remove());
                });
                
                // Make content more PDF-friendly
                document.body.style.padding = '20px';
                document.body.style.fontSize = '12pt';
            }''')
            
            # Generate PDF with proper margins
            await page.pdf(
                path=filename,
                format='A4',
                print_background=True,
                margin={'top': '20mm', 'right': '20mm', 'bottom': '20mm', 'left': '20mm'}
            )
            await browser.close()
            
            file_size = os.path.getsize(filename)
            print(f"✓ Generated PDF: {filename} ({file_size//1024} KB)")
            return {
                "status": "success",
                "filename": filename,
                "size": file_size,
                "url": url,
                "method": "browser_generated"
            }
    except Exception as e:
        print(f"✗ Failed to convert {url}: {str(e)[:100]}...")
        return {
            "status": "failed",
            "error": str(e),
            "url": url
        }

def download_pdf(pdf_url, filename):
    """Direct PDF download helper"""
    try:
        response = requests.get(pdf_url, stream=True, timeout=30)
        response.raise_for_status()
        
        if 'pdf' in response.headers.get('content-type', '').lower():
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            file_size = os.path.getsize(filename)
            return {
                "status": "success",
                "filename": filename,
                "size": file_size,
                "url": pdf_url,
                "method": "direct_download"
            }
        else:
            print(f"✗ Not a PDF: {pdf_url}")
            return {
                "status": "failed",
                "error": "Not a PDF file",
                "url": pdf_url
            }
    except Exception as e:
        print(f"✗ Download failed {pdf_url}: {str(e)[:100]}...")
        return {
            "status": "failed",
            "error": str(e),
            "url": pdf_url
        }

async def process_single_url(url):
    """Process a single PIB URL with all fallback methods"""
    url = url.strip()
    if not url:
        return None
        
    print(f"\n🔍 Processing: {url}")
    try:
        prid_match = re.search(r'PRID=(\d+)', url)
        prid = prid_match.group(1) if prid_match else "unknown"
        
        # First try browser-based PDF generation
        pdf_result = await convert_to_pdf(url, prid)
        if pdf_result['status'] == 'success':
            return {
                "url": url,
                "prid": prid,
                "status": "success",
                "files": [pdf_result]
            }
        
        # If browser fails, try finding direct PDF links
        print("⚠️ Falling back to PDF link detection")
        pdf_links = find_pdf_links(url)
        downloaded_files = []
        
        for i, pdf_url in enumerate(pdf_links):
            suffix = f"_{i}" if len(pdf_links) > 1 else ""
            filename = f"pib_{prid}{suffix}.pdf"
            result = download_pdf(pdf_url, filename)
            if result['status'] == 'success':
                downloaded_files.append(result)
        
        if downloaded_files:
            return {
                "url": url,
                "prid": prid,
                "status": "success",
                "files": downloaded_files
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

async def process_all_urls(urls):
    """Process all URLs concurrently with progress tracking"""
    results = []
    total = len(urls)
    
    for i, url in enumerate(urls, 1):
        print(f"\n📄 Processing URL {i}/{total}")
        result = await process_single_url(url)
        if result:
            results.append(result)
    
    return results

def send_to_n8n(webhook_url, results):
    """Send comprehensive results to n8n webhook"""
    if not webhook_url or webhook_url == "YOUR_N8N_WEBHOOK_URL":
        return
        
    try:
        successful = sum(1 for r in results if r and r.get('status') == 'success')
        total_pdfs = sum(len(r.get('files', [])) for r in results if r)
        
        payload = {
            "metadata": {
                "timestamp": datetime.datetime.now().isoformat(),
                "processed_urls": len(results),
                "successful": successful,
                "failed": len(results) - successful,
                "total_pdfs": total_pdfs,
                "success_rate": f"{(successful/len(results))*100:.1f}%" if results else "0%"
            },
            "details": [r for r in results if r]
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=15,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        print("✅ Results sent to n8n successfully")
    except Exception as e:
        print(f"⚠️ Failed to send to n8n: {str(e)[:100]}...")

def cleanup_pdfs():
    """Remove any PDF files from previous runs"""
    for f in os.listdir('.'):
        if f.startswith('pib_') and f.endswith('.pdf'):
            try:
                os.remove(f)
                print(f"♻️ Cleaned up: {f}")
            except Exception as e:
                print(f"⚠️ Failed to clean up {f}: {str(e)[:100]}...")

if __name__ == "__main__":
    # Clean up previous runs
    cleanup_pdfs()
    
    # Get inputs from environment
    urls_str = os.environ.get('PDF_URLS', '')
    webhook_url = os.environ.get('N8N_WEBHOOK', '')
    
    if not urls_str:
        print("⛔ No URLs provided in PDF_URLS environment variable")
        exit(1)
    
    urls = [url.strip() for url in urls_str.split(',') if url.strip()]
    print(f"📥 Starting processing for {len(urls)} URLs")
    
    # Run async processing
    results = asyncio.run(process_all_urls(urls))
    
    # Filter out None results and send to n8n
    valid_results = [r for r in results if r]
    send_to_n8n(webhook_url, valid_results)
    
    # Determine exit code based on success rate
    success_count = sum(1 for r in valid_results if r.get('status') == 'success')
    success_rate = success_count / len(valid_results) if valid_results else 0
    print(f"\n📊 Final results: {success_count} succeeded, {len(valid_results)-success_count} failed")
    
    exit(0 if success_rate >= 0.5 else 1)
