import requests
from bs4 import BeautifulSoup
import os, smtplib, hashlib
from email.message import EmailMessage
import logging

URL = 'https://www.mospi.gov.in/press-release'
LOG = 'pdf_links.txt'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_pdf_links():
    try:
        r = requests.get(URL)
        r.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to fetch MoSPI page: {e}")
        return []

    soup = BeautifulSoup(r.text, 'html.parser')
    links = [a['href'] for a in soup.select('a[href$=".pdf"]')]
    full_links = [l if l.startswith('http') else f'https://www.mospi.gov.in{l}' for l in links]
    logging.info(f"Found {len(full_links)} PDF links")
    return full_links

def load():
    if not os.path.exists(LOG):
        return set()
    with open(LOG, 'r') as f:
        return set(f.read().splitlines())

def save(links):
    with open(LOG, 'w') as f:
        f.write('\n'.join(links))

def send_email(pdf_url):
    try:
        msg = EmailMessage()
        msg['Subject'] = 'New MoSPI Announcement'
        msg['From'] = os.environ.get('EMAIL_FROM', 'no-reply@example.com')
        msg['To'] = os.environ.get('EMAIL_TO', 'receiver@example.com')
        msg.set_content(f"New press release: {pdf_url}")

        r = requests.get(pdf_url, stream=True)
        r.raise_for_status()
        filename = pdf_url.split('/')[-1]
        msg.add_attachment(r.content, maintype='application', subtype='pdf', filename=filename)

        with smtplib.SMTP(os.environ['SMTP_SERVER'], int(os.environ['SMTP_PORT'])) as s:
            s.starttls()
            s.login(os.environ['EMAIL_FROM'], os.environ['SMTP_PASSWORD'])
            s.send_message(msg)
        logging.info(f"Email sent for: {pdf_url}")
    except Exception as e:
        logging.error(f"Failed to send email for {pdf_url}: {e}")

def main():
    previous = load()
    current = set(get_pdf_links())
    new = current - previous
    logging.info(f"{len(new)} new PDFs detected")
    for pdf in new:
        send_email(pdf)
    if new:
        save(current)

if __name__ == '__main__':
    main()
