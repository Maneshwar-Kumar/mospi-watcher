import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def find_all_pdf_links(pib_url):
    """Find all PDF links from a PIB page"""
    try:
        response = requests.get(pib_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        pdf_links = set()
        prid = re.search(r'PRID=(\d+)', pib_url).group(1)
        
        # 1. Primary PDF (standard PIB pattern)
        primary_pdf = f"https://pib.gov.in/Utilities/GeneratePdf.aspx?ID={prid}"
        pdf_links.add(primary_pdf)
        
        # 2. All anchor tags with PDFs
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if href.endswith('.pdf'):
                absolute_url = urljoin(pib_url, a['href'])
                pdf_links.add(absolute_url)
        
        # 3. Iframe PDF sources
        for iframe in soup.find_all('iframe', src=True):
            if iframe['src'].lower().endswith('.pdf'):
                absolute_url = urljoin(pib_url, iframe['src'])
                pdf_links.add(absolute_url)
        
        return list(pdf_links)
        
    except Exception as e:
        print(f"Error finding PDFs for {pib_url}: {e}")
        return []

def download_pdfs(pdf_links, prid):
    """Download all PDFs with proper naming"""
    downloaded_files = []
    for i, pdf_url in enumerate(pdf_links):
        try:
            suffix = f"_{i}" if len(pdf_links) > 1 else ""
            filename = f"pib_{prid}{suffix}.pdf"
            
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
            
            if 'pdf' in response.headers.get('content-type', '').lower():
                with open(filename, 'wb') as f:
                    f.write(response.content)
                downloaded_files.append({
                    "url": pdf_url,
                    "filename": filename,
                    "size": len(response.content)
                })
                print(f"✓ Downloaded {filename} ({len(response.content)//1024} KB)")
            else:
                print(f"✗ Skipping non-PDF: {pdf_url}")
                
        except Exception as e:
            print(f"✗ Failed to download {pdf_url}: {str(e)[:100]}...")
    
    return downloaded_files

def process_urls(urls):
    results = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
            
        print(f"\n🔍 Processing: {url}")
        try:
            prid = re.search(r'PRID=(\d+)', url).group(1)
            pdf_links = find_all_pdf_links(url)
            
            if not pdf_links:
                print("⚠️ No PDFs found")
                results.append({"url": url, "status": "no_pdfs"})
                continue
                
            downloaded = download_pdfs(pdf_links, prid)
            results.append({
                "url": url,
                "prid": prid,
                "pdf_count": len(downloaded),
                "files": downloaded,
                "status": "success" if downloaded else "failed"
            })
        except Exception as e:
            print(f"⚠️ Error processing URL: {str(e)[:100]}...")
            results.append({"url": url, "status": "error", "message": str(e)})
    
    return results

def send_to_n8n(webhook_url, results):
    """Send comprehensive results to n8n"""
    if not webhook_url or webhook_url == "YOUR_N8N_WEBHOOK_URL":
        return
        
    try:
        payload = {
            "timestamp": datetime.datetime.now().isoformat(),
            "processed_urls": len(results),
            "successful_downloads": sum(1 for r in results if r.get('status') == 'success'),
            "total_pdfs": sum(r.get('pdf_count', 0) for r in results),
            "details": results
        }
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Results sent to n8n successfully")
    except Exception as e:
        print(f"⚠️ Failed to send to n8n: {str(e)[:100]}...")

if __name__ == "__main__":
    import datetime
    
    # Get inputs from environment
    urls_str = os.environ.get('PDF_URLS', '')
    webhook_url = os.environ.get('N8N_WEBHOOK', '')
    
    if not urls_str:
        print("⛔ No URLs provided in PDF_URLS environment variable")
        exit(1)
    
    urls = [url.strip() for url in urls_str.split(',') if url.strip()]
    print(f"📥 Processing {len(urls)} PIB URLs")
    
    results = process_urls(urls)
    send_to_n8n(webhook_url, results)
    
    # Exit code based on success rate
    success_rate = sum(1 for r in results if r.get('status') == 'success') / len(results)
    exit(0 if success_rate > 0.5 else 1)
