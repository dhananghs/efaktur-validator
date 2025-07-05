import re
import io
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber
from pyzbar.pyzbar import decode
from PIL import Image, ImageFilter, ImageEnhance
import pytesseract
import logging
import cv2
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="E-Faktur Validation Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def is_image_file(filename: str) -> bool:
    return filename.lower().endswith((".jpg", ".jpeg", ".png"))

def is_pdf_file(filename: str) -> bool:
    return filename.lower().endswith(".pdf")

MOCK_DJP_XML = '''<resValidateFakturPm>
<kdJenisTransaksi>07</kdJenisTransaksi>
<fgPengganti>0</fgPengganti>
<nomorFaktur>0700002212345678</nomorFaktur>
<tanggalFaktur>01/04/2022</tanggalFaktur>
<npwpPenjual>012345678012000</npwpPenjual>
<namaPenjual>PT ABC</namaPenjual>
<alamatPenjual>Jalan Gatot Subroto No. 40A, Senayan, Kebayoran Baru, Jakarta Selatan 12910</alamatPenjual>
<npwpLawanTransaksi>023456789217000</npwpLawanTransaksi>
<namaLawanTransaksi>PT XYZ</namaLawanTransaksi>
<alamatLawanTransaksi>Jalan Kuda Laut No. 1, Sungai Jodoh, Batu Ampar, Batam 29444</alamatLawanTransaksi>
<jumlahDpp>15000000</jumlahDpp>
<jumlahPpn>1650000</jumlahPpn>
<jumlahPpnBm>0</jumlahPpnBm>
<statusApproval>Faktur Valid, Sudah Diapprove oleh DJP</statusApproval>
<statusFaktur>Faktur Pajak Normal</statusFaktur>
<referensi>123/ABC/IV/2022</referensi>
<detailTransaksi>
<nama>KOMPUTER MERK ABC, HS Code 84714110</nama>
<hargaSatuan>5000000</hargaSatuan>
<jumlahBarang>3</jumlahBarang>
<hargaTotal>15000000</hargaTotal>
<diskon>0</diskon>
<dpp>15000000</dpp>
<ppn>1650000</ppn>
<tarifPpnbm>0</tarifPpnbm>
<ppnbm>0</ppnbm>
</detailTransaksi>
</resValidateFakturPm>'''

def preprocess_ocr_text(text: str) -> str:
    # Normalize whitespace
    text = re.sub(r'[\r\n]+', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    # Fix common OCR errors
    text = text.replace('Sen Faktur', 'Seri Faktur')
    text = text.replace('NPWP |', 'NPWP :')
    text = text.replace('NPWP |', 'NPWP :')
    text = text.replace('NPWP :', 'NPWP:')
    text = text.replace('NIKPaspor', 'NIK/Paspor')
    text = text.replace('Palak', 'Pajak')
    # Remove non-ASCII chars (optional, can help with weird quotes)
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    # Remove double spaces
    text = re.sub(r' +', ' ', text)
    return text

class EFakturValidator:
    def __init__(self):
        self.mock_djp_xml = MOCK_DJP_XML

    def preprocess_for_ocr(self, pil_image: Image.Image) -> Image.Image:
        # Convert to grayscale only - no thresholding to avoid making text too thick
        img = pil_image.convert('L')
        # Apply sharp filter
        img = img.filter(ImageFilter.SHARPEN)
        # Save for debugging
        img.save('files/debug_preprocessed.png')
        return img

    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        try:
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                logger.info(f"[PDF OCR] Extracted text:\n{text}")
                return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise HTTPException(status_code=400, detail="Failed to extract text from PDF")

    def extract_text_from_image(self, image_content: bytes) -> str:
        try:
            image = Image.open(io.BytesIO(image_content))
            image = self.preprocess_for_ocr(image)  # Preprocessing disabled for debugging
            text = pytesseract.image_to_string(image, lang="eng+ind")
            logger.info(f"[Image OCR] Extracted text:\n{text}")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from image: {e}")
            raise HTTPException(status_code=400, detail="Failed to extract text from image")

    def extract_qr_code_from_pdf(self, pdf_content: bytes) -> Optional[str]:
        try:
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page in pdf.pages:
                    images = page.images
                    for img in images:
                        try:
                            pil_image = Image.frombytes(
                                img['format'],
                                (img['width'], img['height']),
                                img['stream'].get_data()
                            )
                            pil_image = self.preprocess_for_ocr(pil_image)
                            decoded_objects = decode(pil_image)
                            for obj in decoded_objects:
                                qr_data = obj.data.decode('utf-8')
                                if 'http' in qr_data:
                                    logger.info(f"[QR Extraction] Extracted QR URL from PDF: {qr_data}")
                                    return qr_data
                        except Exception as e:
                            logger.warning(f"Failed to decode image: {e}")
                            continue
            return None
        except Exception as e:
            logger.error(f"Error extracting QR code: {e}")
            return None

    def extract_qr_code_from_image(self, image_content: bytes) -> Optional[str]:
        try:
            image = Image.open(io.BytesIO(image_content))
            image = self.preprocess_for_ocr(image)  # Preprocessing disabled for debugging
            decoded_objects = decode(image)
            for obj in decoded_objects:
                qr_data = obj.data.decode('utf-8')
                if 'http' in qr_data:
                    logger.info(f"[QR Extraction] Extracted QR URL from image: {qr_data}")
                    return qr_data
            return None
        except Exception as e:
            logger.error(f"Error extracting QR code from image: {e}")
            return None

    def parse_pdf_fields(self, text: str) -> Dict[str, Any]:
        # Preprocess text for better matching
        text = preprocess_ocr_text(text)
        fields = {}
        # Improved section splitting
        penjual_section = ''
        pembeli_section = ''
        # Find start and end indices for sections
        penjual_start = re.search(r'Pengusaha Kena Pajak', text, re.IGNORECASE)
        pembeli_start = re.search(r'Pembeli Barang Kena Pajak', text, re.IGNORECASE)
        if penjual_start and pembeli_start:
            penjual_section = text[penjual_start.start():pembeli_start.start()]
            pembeli_section = text[pembeli_start.start():]
        elif penjual_start:
            penjual_section = text[penjual_start.start():]
        elif pembeli_start:
            pembeli_section = text[pembeli_start.start():]
        # Helper to extract NPWP and Nama from a section
        def extract_npwp(section):
            m = re.search(r'NPWP[\s:|\-]*([0-9.\-]+)', section)
            if m:
                return re.sub(r'[^0-9]', '', m.group(1))
            return None
        def extract_nama(section):
            m = re.search(r'Nama[\s:|\-]*([A-Z0-9 .,&-]+)', section)
            if m:
                return m.group(1).strip()
            return None
        # Prefer section-based extraction, fallback to global if not found
        npwp_penjual = extract_npwp(penjual_section) if penjual_section else None
        if not npwp_penjual:
            npwp_penjual = extract_npwp(text)
        fields['npwpPenjual'] = npwp_penjual
        nama_penjual = extract_nama(penjual_section) if penjual_section else None
        if not nama_penjual:
            nama_penjual = extract_nama(text)
        fields['namaPenjual'] = nama_penjual
        npwp_pembeli = extract_npwp(pembeli_section) if pembeli_section else None
        if not npwp_pembeli:
            # Try to extract the second NPWP in the text (after penjual's NPWP)
            all_npwp = list(re.finditer(r'NPWP[\s:|\-]*([0-9.\-]+)', text))
            if len(all_npwp) > 1:
                npwp_pembeli = re.sub(r'[^0-9]', '', all_npwp[1].group(1))
            else:
                npwp_pembeli = None
        fields['npwpPembeli'] = npwp_pembeli
        nama_pembeli = extract_nama(pembeli_section) if pembeli_section else None
        if not nama_pembeli:
            # Try to extract the second Nama in the text (after penjual's Nama)
            all_nama = list(re.finditer(r'Nama[\s:|\-]*([A-Z0-9 .,&-]+)', text))
            if len(all_nama) > 1:
                nama_pembeli = all_nama[1].group(1).strip()
            else:
                nama_pembeli = None
        fields['namaPembeli'] = nama_pembeli
        # More robust regex patterns for other fields
        patterns = {
            'nomorFaktur': r'(?:Kode dan Nomor Seri Faktur Pajak|Nomor[\s:|\-]*Faktur)[\s:|\-]*([0-9.\-]+[ ]*[0-9]+)',
            'tanggalFaktur': r'(?:Tanggal[\s:|\-]*Faktur|,\s*)(\d{1,2}/\d{1,2}/\d{4})',
            'jumlahDpp': r'Dasar Pengenaan Pajak[\s:|\-]*([0-9.,]+)',
            'jumlahPpn': r'Total PPN[\s:|\-]*([0-9.,]+)'
        }
        indo_months = {
            'JANUARI': '01', 'FEBRUARI': '02', 'MARET': '03', 'APRIL': '04', 'MEI': '05', 'JUNI': '06',
            'JULI': '07', 'AGUSTUS': '08', 'SEPTEMBER': '09', 'OKTOBER': '10', 'NOVEMBER': '11', 'DESEMBER': '12'
        }
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if field == 'nomorFaktur':
                    value = re.sub(r'[^0-9]', '', value)
                if field in ['jumlahDpp', 'jumlahPpn']:
                    # Remove spaces, dots, and commas to get the full number
                    value = re.sub(r'[\s.,]', '', value)
                fields[field] = value
            else:
                # Fallback for tanggalFaktur: look for 'PLACE, DD MONTH YYYY'
                if field == 'tanggalFaktur':
                    match3 = re.search(r',\s*(\d{1,2})\s+([A-Z]+)\s+(\d{4})', text, re.IGNORECASE)
                    if match3:
                        day = match3.group(1)
                        month_str = match3.group(2).upper()
                        year = match3.group(3)
                        month = indo_months.get(month_str, None)
                        if month:
                            value = f"{day.zfill(2)}/{month}/{year}"
                            fields[field] = value
                            continue
                fields[field] = fields.get(field, None)
        logger.info(f"[Field Parsing] Parsed fields: {fields}")
        return fields

    def fetch_djp_data(self, qr_url: str = None) -> Dict[str, Any]:
        try:
            root = ET.fromstring(self.mock_djp_xml)
            djp_data = {}
            field_mapping = {
                'npwpPenjual': 'npwpPenjual',
                'namaPenjual': 'namaPenjual',
                'npwpPembeli': 'npwpLawanTransaksi',
                'namaPembeli': 'namaLawanTransaksi',
                'nomorFaktur': 'nomorFaktur',
                'tanggalFaktur': 'tanggalFaktur',
                'jumlahDpp': 'jumlahDpp',
                'jumlahPpn': 'jumlahPpn'
            }
            for pdf_field, xml_field in field_mapping.items():
                element = root.find(xml_field)
                if element is not None:
                    djp_data[pdf_field] = element.text
                else:
                    djp_data[pdf_field] = None
            return djp_data
        except ET.ParseError as e:
            logger.error(f"Error parsing DJP XML: {e}")
            raise HTTPException(status_code=500, detail="Failed to parse DJP response")

    def compare_fields(self, pdf_data: Dict[str, Any], djp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        deviations = []
        for field in ['npwpPenjual', 'namaPenjual', 'npwpPembeli', 'namaPembeli',
                     'nomorFaktur', 'tanggalFaktur', 'jumlahDpp', 'jumlahPpn']:
            pdf_value = pdf_data.get(field)
            djp_value = djp_data.get(field)
            if pdf_value is None and djp_value is not None:
                deviation_type = "missing_in_pdf"
            elif pdf_value is not None and djp_value is None:
                deviation_type = "missing_in_api"
            elif pdf_value != djp_value:
                deviation_type = "mismatch"
            else:
                continue
            deviations.append({
                "field": field,
                "pdf_value": pdf_value,
                "djp_api_value": djp_value,
                "deviation_type": deviation_type
            })
        return deviations

    def validate_efaktur(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        try:
            if is_pdf_file(filename):
                pdf_text = self.extract_text_from_pdf(file_content)
                if not pdf_text:
                    raise HTTPException(status_code=400, detail="No text found in PDF")
                pdf_data = self.parse_pdf_fields(pdf_text)
                qr_url = self.extract_qr_code_from_pdf(file_content)
                extracted_text = pdf_text
            elif is_image_file(filename):
                image_text = self.extract_text_from_image(file_content)
                if not image_text:
                    raise HTTPException(status_code=400, detail="No text found in image")
                pdf_data = self.parse_pdf_fields(image_text)
                qr_url = self.extract_qr_code_from_image(file_content)
                extracted_text = image_text
            else:
                raise HTTPException(status_code=400, detail="Only PDF and JPG/PNG files are supported")
            djp_data = self.fetch_djp_data(qr_url)
            deviations = self.compare_fields(pdf_data, djp_data)
            if deviations:
                status = "validated_with_deviations"
                message = f"Found {len(deviations)} deviation(s) in e-Faktur data"
            else:
                status = "validated_successfully"
                message = "E-Faktur data matches DJP records"
            return {
                "status": status,
                "message": message,
                "validation_results": {
                    "deviations": deviations,
                    "validated_data": djp_data,
                    "extracted_data": pdf_data,
                    "raw_ocr_text": extracted_text,
                    "qr_url": qr_url
                }
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during validation: {e}")
            raise HTTPException(status_code=500, detail="Internal server error during validation")

validator = EFakturValidator()

@app.post("/validate-efaktur")
async def validate_efaktur(file: UploadFile = File(..., media_type=["application/pdf", "image/jpeg"])):
    if not (is_pdf_file(file.filename) or is_image_file(file.filename)):
        raise HTTPException(status_code=400, detail="Only PDF and JPG/PNG files are supported")
    try:
        file_content = await file.read()
        result = validator.validate_efaktur(file_content, file.filename)
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        raise HTTPException(status_code=500, detail="Failed to process uploaded file")

@app.get("/")
async def root():
    return {"message": "E-Faktur Validation Service is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 