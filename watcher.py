import os
import requests
from bs4 import BeautifulSoup
from email.message import EmailMessage
import smtplib

# Constants
BASE_URL = 'https://mospi.gov.in'
TARGET_PAGE = BASE_URL + '/documents/213904/0/SDD_Publications.html'
LINK_RECORD_FILE = 'pdf_links.txt'

# Email credentials
EMAIL_FROM = os.environ['EMAIL_FROM']
EMAIL_TO = os.environ['EMAIL_TO']
EMAIL_PASSWORD = os.environ['EMAIL_PASSWORD']
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587


def load_sent_links():
    if not os.path.exists(LINK_RECORD_FILE):
        return set()
    with open(LINK_RECORD_FILE, 'r') as f:
        return set(line.strip() for line in f)


def save_sent_links(links_set):
    with open(LINK_RECORD_FILE, 'w') as f:
        f.writelines(link + '\n' for link in sorted(links_set))


def get_pdf_links():
    try:
        response = requests.get(TARGET_PAGE)
        soup = BeautifulSoup(response.content, 'html.parser')
        return {
            BASE_URL + a['href']
            for a in soup.find_all('a', href=True)
            if a['href'].endswith('.pdf')
        }
    except Exception as e:
        print(f"Error fetching page: {e}")
        return set()


def download_pdf(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        filename = url.split('/')[-1]
        with open(filename, 'wb') as f:
            f.write(response.content)
        return filename
    except Exception as e:
        print(f"Download error: {e}")
        return None


def send_email_with_attachment(subject, body, pdf_path):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    msg.set_content(body)

    try:
        with open(pdf_path, 'rb') as f:
            data = f.read()
            msg.add_attachment(data, maintype='application', subtype='pdf', filename=os.path.basename(pdf_path))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_FROM, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"Email sent for {pdf_path}")
    except Exception as e:
        print(f"Email send error: {e}")


def main():
    current_links = get_pdf_links()
    if not current_links:
        print("No PDFs found on page.")
        return

    already_sent = load_sent_links()

    # First run detection
    if not already_sent:
        print("First run detected. Saving current links, sending nothing.")
        save_sent_links(current_links)
        return

    new_links = current_links - already_sent
    if not new_links:
        print("No new PDFs found.")
        return

    for url in new_links:
        filename = download_pdf(url)
        if filename:
            send_email_with_attachment(
                subject="New MoSPI PDF Available",
                body=f"A new PDF has been uploaded:\n{url}",
                pdf_path=filename
            )
            os.remove(filename)

    # Save updated list of sent links
    save_sent_links(already_sent.union(new_links))


if __name__ == '__main__':
    main()
