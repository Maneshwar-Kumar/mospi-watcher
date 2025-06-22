import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import datetime
import shutil

def log_message(message):
    """Consistent logging format"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def is_valid_pdf_link(href):
    """Check if link is a relevant PDF"""
    if not href or not isinstance(href, str):
        return False
    href = href.lower()
    return (href.endswith('.pdf') and 
            not href.startswith(('javascript:', 'mailto:')) and
            ('specificdocs' in href or 
             'generatepdf.aspx' in href or
             '/pdf/' in href or
             '/document/' in href))

def find_pdf_links(url):
    """Find all relevant PDF links from a PIB page"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        pdf_links = set()
        prid_match = re.search(r'PRID=(\d+)', url)
        prid = prid_match.group(1) if prid_match else None
        
        # Standard PIB PDF generation link
        if prid:
            primary_pdf = f"https://pib.gov.in/Utilities/GeneratePdf.aspx?ID={prid}"
            pdf_links.add(primary_pdf)
        
        # Specificdocs PDFs and other direct links
        main_content = soup.find('div', {'id': 'ContentPlaceHolder1_Content'}) or soup
        for a in main_content.find_all('a', href=True):
            href = a['href']
            if is_valid_pdf_link(href):
                absolute_url = urljoin(url, href)
                pdf_links.add(absolute_url)
        
        return list(pdf_links)
    except Exception as e:
        log_message(f"⚠️ PDF detection failed for {url}: {str(e)[:100]}...")
        return []

def download_pdf(pdf_url, filename):
    """Download PDF with proper error handling"""
    try:
        response = requests.get(pdf_url, stream=True, timeout=30)
        response.raise_for_status()
        
        if 'pdf' in response.headers.get('content-type', '').lower():
            with open(filename, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            file_size = os.path.getsize(filename)
            return {
                "status": "success",
                "filename": filename,
                "size": file_size,
                "url": pdf_url
            }
        else:
            log_message(f"✗ Not a PDF: {pdf_url}")
            return {
                "status": "failed",
                "error": "Not a PDF file",
                "url": pdf_url
            }
    except Exception as e:
        log_message(f"✗ Download failed {pdf_url}: {str(e)[:100]}...")
        return {
            "status": "failed",
            "error": str(e),
            "url": pdf_url
        }

def process_urls(urls):
    """Process all URLs sequentially"""
    results = []
    for i, url in enumerate(urls, 1):
        url = url.strip()
        if not url:
            continue
            
        log_message(f"\n🔍 Processing URL {i}/{len(urls)}: {url}")
        try:
            prid_match = re.search(r'PRID=(\d+)', url)
            prid = prid_match.group(1) if prid_match else "unknown"
            
            pdf_links = find_pdf_links(url)
            if not pdf_links:
                log_message("⚠️ No PDF links found")
                results.append({
                    "url": url,
                    "status": "failed",
                    "error": "No PDF links found"
                })
                continue
                
            downloaded_files = []
            for j, pdf_url in enumerate(pdf_links):
                suffix = f"_{j}" if len(pdf_links) > 1 else ""
                filename = f"pib_{prid}{suffix}.pdf"
                result = download_pdf(pdf_url, filename)
                if result['status'] == 'success':
                    downloaded_files.append(result)
            
            if downloaded_files:
                results.append({
                    "url": url,
                    "prid": prid,
                    "status": "success",
                    "files": downloaded_files
                })
            else:
                results.append({
                    "url": url,
                    "status": "failed",
                    "error": "All downloads failed"
                })
                
        except Exception as e:
            log_message(f"⚠️ Error processing URL: {str(e)[:100]}...")
            results.append({
                "url": url,
                "status": "error",
                "error": str(e)
            })
    
    return results

def send_to_n8n(webhook_url, results):
    """Send results to n8n webhook"""
    if not webhook_url:
        log_message("⚠️ No webhook URL configured")
        return
        
    try:
        successful = sum(1 for r in results if r.get('status') == 'success')
        payload = {
            "metadata": {
                "timestamp": datetime.datetime.now().isoformat(),
                "processed_urls": len(results),
                "successful": successful,
                "failed": len(results) - successful,
                "total_pdfs": sum(len(r.get('files', [])) for r in results)
            },
            "details": results
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=15,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        log_message("✅ Results sent to n8n successfully")
    except Exception as e:
        log_message(f"⚠️ Failed to send to n8n: {str(e)[:100]}...")

if __name__ == "__main__":
    # Get inputs from environment
    urls_str = os.environ.get('PDF_URLS', '')
    webhook_url = os.environ.get('N8N_WEBHOOK', '')
    
    if not urls_str:
        log_message("⛔ No URLs provided in PDF_URLS environment variable")
        exit(1)
    
    urls = [url.strip() for url in urls_str.split(',') if url.strip()]
    log_message(f"📥 Starting processing for {len(urls)} URLs")
    
    results = process_urls(urls)
    send_to_n8n(webhook_url, results)
    
    # Determine exit code
    success_count = sum(1 for r in results if r.get('status') == 'success')
    exit(0 if success_count > 0 else 1)
