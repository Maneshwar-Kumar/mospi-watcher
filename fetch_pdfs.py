import requests
import os
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

def extract_prid_and_download_pdf(url):
    """Extract PRID from URL and download PDF directly"""
    try:
        # Extract PRID from URL
        prid_match = re.search(r'PRID=(\d+)', url)
        if not prid_match:
            print(f"Could not extract PRID from {url}")
            return []
        
        prid = prid_match.group(1)
        
        # Direct PDF download URL pattern
        pdf_url = f"https://pib.gov.in/Utilities/GeneratePdf.aspx?ID={prid}"
        
        print(f"Attempting to download PDF from: {pdf_url}")
        
        # Download PDF
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        
        # Check if response is actually a PDF
        content_type = response.headers.get('content-type', '')
        if 'pdf' not in content_type.lower():
            print(f"Response is not a PDF for PRID {prid}")
            return []
        
        # Save PDF
        filename = f"pib_{prid}.pdf"
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        print(f"Downloaded: {filename} ({len(response.content)} bytes)")
        return [pdf_url]
        
    except Exception as e:
        print(f"Error downloading PDF for {url}: {e}")
        return []

def process_urls(urls):
    """Process multiple URLs and download PDFs"""
    total_pdfs = 0
    all_pdf_links = []
    
    for url in urls:
        print(f"Processing: {url}")
        pdf_links = extract_prid_and_download_pdf(url.strip())
        all_pdf_links.extend(pdf_links)
        total_pdfs += len(pdf_links)
        print(f"Found {len(pdf_links)} PDF links")
    
    print(f"Total PDFs downloaded: {total_pdfs}")
    return all_pdf_links

def send_to_n8n(webhook_url, pdf_links):
    """Send results to N8N webhook"""
    if webhook_url and webhook_url != "YOUR_N8N_WEBHOOK_URL":
        try:
            payload = {
                "pdf_count": len(pdf_links),
                "pdf_links": pdf_links,
                "status": "completed"
            }
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            print("Successfully sent results to N8N")
        except Exception as e:
            print(f"Error sending to N8N: {e}")

if __name__ == "__main__":
    # Get URLs from environment variable
    urls_str = os.environ.get('PDF_URLS', '')
    webhook_url = os.environ.get('N8N_WEBHOOK', '')
    
    if not urls_str:
        print("No URLs provided")
        exit(1)
    
    urls = [url.strip() for url in urls_str.split(',') if url.strip()]
    print(f"Processing {len(urls)} press release URLs")
    
    # Process URLs and download PDFs
    pdf_links = process_urls(urls)
    
    # Send results to N8N
    send_to_n8n(webhook_url, pdf_links)
