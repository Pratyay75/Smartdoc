import os
import fitz
import requests
import uuid
import re
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
import logging

# Optional: configure logging format and level
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

load_dotenv()

BLOB_CONN_STR = (
    f"DefaultEndpointsProtocol=https;AccountName={os.getenv('AZURE_STORAGE_ACCOUNT')};"
    f"AccountKey={os.getenv('AZURE_STORAGE_KEY')};EndpointSuffix=core.windows.net"
)
BLOB_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")

EMBEDDING_URL = (
    f"{os.getenv('AZURE_OPENAI_ENDPOINT')}openai/deployments/"
    f"{os.getenv('AZURE_EMBEDDING_DEPLOYMENT')}/embeddings?api-version={os.getenv('AZURE_API_VERSION')}"
)
EMBEDDING_HEADERS = {
    "api-key": os.getenv("AZURE_OPENAI_API_KEY"),
    "Content-Type": "application/json"
}

SEARCH_URL = (
    f"{os.getenv('AZURE_SEARCH_ENDPOINT')}/indexes/{os.getenv('AZURE_MULTI_DOC_INDEX')}"
    f"/docs/index?api-version=2023-07-01-Preview"
)
SEARCH_HEADERS = {
    "Content-Type": "application/json",
    "api-key": os.getenv("AZURE_SEARCH_API_KEY")
}


# ------------------ Normalization ------------------
def normalize_text(text: str) -> str:
    """
    Normalize extracted text so tables, paragraphs, and key-value pairs
    are all treated consistently.
    """
    # Collapse multiple whitespaces into single space
    text = re.sub(r'\s+', ' ', text)
    # Normalize key-value formatting (keep colon spacing clean)
    text = re.sub(r'\s*:\s*', ': ', text)
    return text.strip()


# ------------------ Chunk Extraction ------------------
def extract_chunks(pdf_bytes):
    """
    Extract text from PDF.
    - Each page = 1 chunk.
    - Normalize text for consistent embeddings.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    chunks = []

    for page in doc:
        raw_text = page.get_text("text").strip()
        if not raw_text:
            continue
        norm_text = normalize_text(raw_text)
        chunks.append(norm_text)

    return chunks


# ------------------ Embedding ------------------
def get_embedding(text):
    data = {"input": text, "model": os.getenv("AZURE_EMBEDDING_DEPLOYMENT")}
    res = requests.post(EMBEDDING_URL, headers=EMBEDDING_HEADERS, json=data)
    if res.status_code == 200:
        return res.json()["data"][0]["embedding"]

    print("❌ Embedding failed:", res.text)
    return []


def push_chunks(chunks, blob_name, filename):
    if not os.getenv("AZURE_MULTI_DOC_INDEX"):
        raise ValueError("❌ Missing AZURE_MULTI_DOC_INDEX in .env")

    documents = []
    for i, chunk in enumerate(chunks):
        logging.info(f"🔄 Chunk {i + 1}/{len(chunks)} for {blob_name}")
        vector = get_embedding(chunk)
        if not vector:
            continue
        documents.append({
            "@search.action": "upload",
            "id": str(uuid.uuid4()),
            "content": chunk,
            "embedding": vector,
            "metadata": f"source:{blob_name}",
            "filename": filename
        })

    if documents:
        payload = {"value": documents}
        res = requests.post(SEARCH_URL, headers=SEARCH_HEADERS, json=payload)
        logging.info(f"Azure Search upload response: {res.status_code} - {res.text}")
    else:
        logging.warning(f"⚠ No chunks to upload for {blob_name}")


def process_blob(blob_name, filename):
    blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
    blob_client = blob_service.get_blob_client(BLOB_CONTAINER, blob_name)
    pdf_bytes = blob_client.download_blob().readall()
    chunks = extract_chunks(pdf_bytes)
    logging.info(f"✅ Extracted {len(chunks)} chunks from {filename}")
    push_chunks(chunks, blob_name, filename)


if __name__ == "__main__":
    # test with a blob in your container
    process_blob("sample.pdf", "sample.pdf")


