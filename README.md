# E-Faktur API Validation Service

A robust microservice that automates the validation of e-Faktur PDF documents against official data from the Directorate General of Taxes (DJP) in Indonesia.

## Overview

This service addresses a critical pain point in Indonesia's B2B ecosystem where businesses need to validate electronic tax invoices (e-Faktur) against official DJP records. It helps companies quickly identify discrepancies, improving data integrity and financial compliance.

## Features

- **PDF Text Extraction**: Parses e-Faktur PDF documents to extract critical fields
- **Image OCR**: Extracts text from JPG/PNG e-Faktur images using Tesseract OCR
- **QR Code Detection**: Extracts and decodes QR codes from PDF images and image files to get DJP validation URLs
- **DJP API Integration**: Fetches official data from DJP services
- **Field Comparison**: Compares PDF data with official DJP records
- **Deviation Analysis**: Identifies mismatches, missing fields, and data inconsistencies
- **RESTful API**: Clean, documented API endpoints

## Technical Stack

- **[FastAPI](https://pypi.org/project/fastapi/)**: Modern, fast web framework for building APIs
- **[pdfplumber](https://pypi.org/project/pdfplumber/)**: PDF text and image extraction
- **[pyzbar](https://pypi.org/project/pyzbar/)**: QR code decoding from images
- **[Pillow](https://pypi.org/project/Pillow/)**: Image processing for QR code extraction
- **[requests](https://pypi.org/project/requests/)**: HTTP client for DJP API calls
- **[xml.etree.ElementTree](https://docs.python.org/3/library/xml.etree.elementtree.html)**: XML parsing for DJP responses (built-in Python library)
- **[pytesseract](https://pypi.org/project/pytesseract/)**: OCR text extraction from images

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd online-pajak
```

2. Install system dependencies (required for QR code processing and OCR):
```bash
# macOS
brew install zbar tesseract tesseract-lang

# Ubuntu/Debian
sudo apt-get install libzbar0 tesseract-ocr tesseract-ocr-ind

# CentOS/RHEL
sudo yum install zbar tesseract tesseract-langpack-ind

# Windows
# Download and install from: https://github.com/NaturalHistoryMuseum/pyzbar#windows
# For Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Run the service:
```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Documentation

### Base URL
```
http://localhost:8000
```

### Endpoints

#### POST /validate-efaktur
Validates an e-Faktur PDF against DJP data.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: File upload (PDF or JPG)

**Response:**
```json
{
  "status": "validated_with_deviations" | "validated_successfully" | "error",
  "message": "string",
  "validation_results": {
    "deviations": [
      {
        "field": "string",
        "pdf_value": "any",
        "djp_api_value": "any",
        "deviation_type": "mismatch" | "missing_in_pdf" | "missing_in_api"
      }
    ],
    "validated_data": {
      "npwpPenjual": "value",
      "namaPenjual": "value",
      "npwpPembeli": "value",
      "namaPembeli": "value",
      "nomorFaktur": "value",
      "tanggalFaktur": "value",
      "jumlahDpp": "value",
      "jumlahPpn": "value"
    }
  }
}
```

#### GET /
Health check endpoint.

**Response:**
```json
{
  "message": "E-Faktur Validation Service is running"
}
```

## Usage Examples

### Using curl
```bash
curl -X POST "http://localhost:8000/validate-efaktur" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@path/to/your/efaktur.pdf"
```

### Using Python requests
```python
import requests

url = "http://localhost:8000/validate-efaktur"
files = {"file": open("efaktur.pdf", "rb")}

response = requests.post(url, files=files)
result = response.json()
print(result)
```

## Extracted Fields

The service extracts and validates the following fields from e-Faktur documents:

| Field | Description | Format |
|-------|-------------|---------|
| NPWP Penjual | Seller's Tax ID | XX.XXX.XXX.X-XXX.XXX |
| Nama Penjual | Seller Name | Text |
| NPWP Pembeli | Buyer's Tax ID | XX.XXX.XXX.X-XXX.XXX |
| Nama Pembeli | Buyer Name | Text |
| Nomor Faktur | E-Faktur Number | 16 digits |
| Tanggal Faktur | E-Faktur Date | DD/MM/YYYY |
| Jumlah DPP | Total Tax Base Value | Numeric |
| Jumlah PPN | Total VAT Amount | Numeric |

## Deviation Types

The service identifies three types of deviations:

1. **mismatch**: Values exist in both PDF and DJP but don't match
2. **missing_in_pdf**: Field exists in DJP but not found in PDF
3. **missing_in_api**: Field exists in PDF but not found in DJP response

## Error Handling

The service includes comprehensive error handling for:

- Invalid file formats
- Corrupted PDF files
- Network failures when calling DJP API
- Malformed XML responses
- Missing or invalid QR codes
- Parsing errors

## Development

### Project Structure
```
online-pajak/
├── main.py              # Main FastAPI application
├── requirements.txt     # Python dependencies
├── README.md           # This file
└── files/              # Sample files for testing
    └── mock-faktur-pajak.jpg
```

### Testing

The service includes a mock DJP API URL for testing purposes. In production, this would be replaced with the actual QR code URL extracted from the PDF.

### Logging

The service includes comprehensive logging for debugging and monitoring:
- PDF processing errors
- QR code extraction issues
- DJP API call failures
- Field parsing problems

## Production Considerations

For production deployment, consider:

1. **Environment Variables**: Configure DJP API endpoints and timeouts
2. **Rate Limiting**: Implement rate limiting for DJP API calls
3. **Caching**: Cache DJP responses to reduce API calls
4. **Monitoring**: Add metrics and health checks
5. **Security**: Implement authentication and authorization
6. **Error Recovery**: Add retry logic for transient failures

## Support

For questions or issues, please refer to the API documentation at `http://localhost:8000/docs` when the service is running.
