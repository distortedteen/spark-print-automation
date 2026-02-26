# SPARK – Self-Service Print Automation & Record-Keeping

SPARK is a campus printing automation system designed to digitize and streamline printing workflows using Flask, SQLite, and CUPS.

## Features

- PDF upload with automatic page detection (PDF.js)
- Token-based queue system (First-Come, First-Serve)
- UPI payment integration
- Secure admin login (hashed password)
- Real-time job tracking
- CSV export for auditing
- Canon imageRUNNER 2925 integration via CUPS

## Tech Stack

Frontend: HTML, CSS, JavaScript  
Backend: Flask (Python)  
Database: SQLite  
Printing: CUPS (Linux)

## Setup Instructions

1. Install dependencies:
   pip install -r requirements.txt

2. Run the application:
   python app.py

3. Open in browser:
   http://localhost:5000

## Deployment

Designed for deployment within campus infrastructure using existing printers.
