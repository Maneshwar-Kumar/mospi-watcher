import os
import requests
from bs4 import BeautifulSoup
import base64
import json
from urllib.parse import urljoin, urlparse
import time

def extract_pdfs_from_press_release(url):
    """Extract PDF links from a press release page"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        pdf_links = []
        # Find all links ending in .pdf
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.lower().endswith('.pdf'):
                # Convert relative URLs to absolute
                if href.startswith('http'):
                    pdf_links.append(href)
                else:
                    pdf_links.append(urljoin(url, href))
        
        return pdf_links
    except Exception as e:
        print(f"Error extracting PDFs from {url}: {e}")
        return []

def download_pdf(url):
    """Download PDF and return base64 encoded content"""
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        # Get filename from URL
        filename = url.split('/')[-1]
        if not filename.endswith('.pdf'):
            filename += '.pdf'
            
        return {
            'filename': filename,
            'content': base64.b64encode(response.content).decode('utf-8'),
            'url': url,
            'size': len(response.content)
        }
    except Exception as e:
        print(f"Error downloading PDF {url}: {e}")
        return None

def send_to_n8n(webhook_url, pdfs_data, press_release_urls):
    """Send PDF data to N8N webhook"""
    try:
        payload = {
            'pdfs': pdfs_data,
            'source_urls': press_release_urls,
            'timestamp': time.time()
        }
        
        response = requests.post(webhook_url, json=payload, timeout=120)
        response.raise_for_status()
        print(f"Successfully sent {len(pdfs_data)} PDFs to N8N")
        
    except Exception as e:
        print(f"Error sending to N8N: {e}")

def main():
    # Get environment variables
    pdf_urls_str = os.environ.get('PDF_URLS', '')
    n8n_webhook = os.environ.get('N8N_WEBHOOK', '')
    
    if not pdf_urls_str or not n8n_webhook:
        print("Missing required environment variables")
        return
    
    # Parse comma-separated URLs
    press_release_urls = [url.strip() for url in pdf_urls_str.split(',') if url.strip()]
    
    print(f"Processing {len(press_release_urls)} press release URLs")
    
    all_pdfs_data = []
    processed_urls = []
    
    for pr_url in press_release_urls:
        print(f"Processing: {pr_url}")
        
        # Extract PDF links from press release page
        pdf_links = extract_pdfs_from_press_release(pr_url)
        print(f"Found {len(pdf_links)} PDF links")
        
        # Download each PDF
        for pdf_url in pdf_links:
            print(f"Downloading: {pdf_url}")
            pdf_data = download_pdf(pdf_url)
            
            if pdf_data:
                pdf_data['source_url'] = pr_url
                all_pdfs_data.append(pdf_data)
                print(f"Downloaded: {pdf_data['filename']} ({pdf_data['size']} bytes)")
            
            # Add small delay to be respectful
            time.sleep(1)
        
        processed_urls.append(pr_url)
        time.sleep(2)  # Delay between press releases
    
    print(f"Total PDFs downloaded: {len(all_pdfs_data)}")
    
    # Send to N8N if we have PDFs
    if all_pdfs_data:
        send_to_n8n(n8n_webhook, all_pdfs_data, processed_urls)
    else:
        print("No PDFs found to send")

if __name__ == '__main__':
    main()
