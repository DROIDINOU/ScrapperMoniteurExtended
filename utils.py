# utils.py
import hashlib

def generate_doc_hash_from_html(html, date_str):
    text = f"{html.strip()}|{date_str.strip()}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()