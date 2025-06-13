const fs = require('fs');
const https = require('https');
const path = require('path');

// Read the reports data
const reports = JSON.parse(fs.readFileSync('reports.json', 'utf8'));

// Create pdfs directory
if (!fs.existsSync('pdfs')) {
  fs.mkdirSync('pdfs');
}

// Function to download PDF
function downloadPDF(url, filename) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(path.join('pdfs', filename));
    
    https.get(url, (response) => {
      response.pipe(file);
      file.on('finish', () => {
        file.close();
        resolve();
      });
    }).on('error', (err) => {
      reject(err);
    });
  });
}

// Download all PDFs
async function fetchAllPDFs() {
  for (let i = 0; i < reports.length; i++) {
    const report = reports[i];
    const filename = `report_${i + 1}.pdf`;
    
    try {
      await downloadPDF(report.pdfUrl, filename);
      console.log(`Downloaded: ${report.title}`);
    } catch (error) {
      console.error(`Failed to download: ${report.title}`, error);
    }
  }
}

fetchAllPDFs();
