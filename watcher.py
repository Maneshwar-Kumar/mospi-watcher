import requests
from bs4 import BeautifulSoup
import os
import smtplib
from email.message import EmailMessage

URL = 'https://www.mospi.gov.in/press-release'
LOG = 'pdf_links.txt'

def get_pdf_links():
    r = requests.get(URL)
    soup = BeautifulSoup(r.text, 'html.parser')
    links = []
    for a in soup.select('a[href$=".pdf"]'):
        href = a['href']
        full_url = href if href.startswith('http') else f'https://www.mospi.gov.in{href}'
        links.append(full_url)
    return links

def load():
    return set(open(LOG).read().splitlines()) if os.path.exists(LOG) else set()

def save(links):
    with open(LOG, 'w') as f:
        f.write('\n'.join(links))

def send_email(pdf_url):
    msg = EmailMessage()
    msg['Subject'] = 'New MoSPI Announcement'
    msg['From'] = os.environ['EMAIL_FROM']
    msg['To'] = os.environ['EMAIL_TO']
    msg.set_content(f"New press release: {pdf_url}")

    r = requests.get(pdf_url, stream=True)
    filename = pdf_url.split('/')[-1]
    msg.add_attachment(r.content, maintype='application', subtype='pdf', filename=filename)

    s = smtplib.SMTP(os.environ['SMTP_SERVER'], int(os.environ['SMTP_PORT']))
    s.starttls()
    s.login(os.environ['EMAIL_FROM'], os.environ['SMTP_PASSWORD'])
    s.send_message(msg)
    s.quit()

def main():
    previous = load()
    current = set(get_pdf_links())
    new = current - previous
    for pdf in new:
        send_email(pdf)
    if new:
        save(current)

if __name__ == '__main__':
    main()
