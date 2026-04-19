"""Google Drive 讀取（用 Service Account，不需要 OAuth 互動）。"""
from __future__ import annotations

import io
import warnings

from docx import Document
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .config import (
    DOC_MIME, DOCX_MIME, DRIVE_SCOPES, FOLDER_MIME, GDOC_MIME, PDF_MIME,
    get_service_account_info,
)


def get_drive_service():
    info = get_service_account_info()
    creds = Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)
    return build('drive', 'v3', credentials=creds, cache_discovery=False)


PARSEABLE_MIMES = {DOCX_MIME, DOC_MIME, GDOC_MIME, PDF_MIME}


def list_doc_files(service, folder_id: str) -> list[dict]:
    """遞迴列出資料夾底下所有可解析文件（.doc/.docx/Google Doc/PDF）。"""
    out: list[dict] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields='nextPageToken, files(id, name, mimeType, createdTime)',
            orderBy='createdTime desc',
            pageToken=page_token,
            pageSize=200,
        ).execute()
        for item in resp.get('files', []):
            mime = item['mimeType']
            if mime in PARSEABLE_MIMES:
                out.append(item)
            elif mime == FOLDER_MIME:
                out.extend(list_doc_files(service, item['id']))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return out


def _download_bytes(service, file_id: str) -> io.BytesIO:
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return fh


def _export_text(service, file_id: str) -> str:
    request = service.files().export_media(fileId=file_id, mimeType='text/plain')
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return fh.read().decode('utf-8', errors='ignore')


def extract_text(service, file_id: str, mime_type: str, filename: str) -> str:
    """根據檔案類型抽出純文字內容。

    .docx        → 用 python-docx 讀
    Google Doc   → export 成純文字
    .doc (舊版)  → 先複製成 Google Doc 再 export，最後刪除暫存
    """
    if mime_type == DOCX_MIME:
        fh = _download_bytes(service, file_id)
        doc = Document(fh)
        return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())

    if mime_type == GDOC_MIME:
        return _export_text(service, file_id)

    if mime_type == DOC_MIME:
        copied = service.files().copy(
            fileId=file_id,
            body={'mimeType': GDOC_MIME, 'name': f'__tmp__{filename}'},
        ).execute()
        gdoc_id = copied['id']
        try:
            return _export_text(service, gdoc_id)
        finally:
            try:
                service.files().delete(fileId=gdoc_id).execute()
            except Exception:
                pass

    if mime_type == PDF_MIME:
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError('缺少 pdfplumber 套件，請執行 pip install pdfplumber')
        fh = _download_bytes(service, file_id)
        text_parts: list[str] = []
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')  # 抑制 pdfplumber 的 FontBBox 警告
            with pdfplumber.open(fh) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
        return '\n'.join(text_parts)

    raise ValueError(f'不支援的檔案類型：{mime_type}')
