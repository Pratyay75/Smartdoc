import os
import fitz  # PyMuPDF – used for reading PDF
import requests
import uuid
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# Load environment variables
load_dotenv()

# Configurations from .env
BLOB_CONN_STR = f"DefaultEndpointsProtocol=https;AccountName={os.getenv('AZURE_STORAGE_ACCOUNT')};AccountKey={os.getenv('AZURE_STORAGE_KEY')};EndpointSuffix=core.windows.net"
BLOB_CONTAINER = os.getenv('AZURE_STORAGE_CONTAINER')

EMBEDDING_URL = f"{os.getenv('AZURE_OPENAI_ENDPOINT')}openai/deployments/{os.getenv('AZURE_EMBEDDING_DEPLOYMENT')}/embeddings?api-version={os.getenv('AZURE_API_VERSION')}"
EMBEDDING_HEADERS = {
    "api-key": os.getenv("AZURE_OPENAI_API_KEY"),
    "Content-Type": "application/json"
}

SEARCH_URL = f"{os.getenv('AZURE_SEARCH_ENDPOINT')}/indexes/{os.getenv('AZURE_SEARCH_INDEX')}/docs/index?api-version=2023-07-01-Preview"
SEARCH_HEADERS = {
    "Content-Type": "application/json",
    "api-key": os.getenv("AZURE_SEARCH_API_KEY")
}



# 📄 Extract Text Page-by-Page
def extract_chunks(pdf_path):
    doc = fitz.open(pdf_path)
    chunks = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            chunks.append(text)
    return chunks

# 🧠 Get Embedding Vector for Each Chunk
def get_embedding(text):
    data = {
        "input": text,
        "model": os.getenv("AZURE_EMBEDDING_DEPLOYMENT")
    }
    res = requests.post(EMBEDDING_URL, headers=EMBEDDING_HEADERS, json=data)
    if res.status_code == 200:
        return res.json()['data'][0]['embedding']
    else:
        print("❌ Embedding failed:", res.text)
        return []

# 🔍 Push Chunk + Embedding to Azure Cognitive Search
def push_chunks_to_search(chunks, source_name):
    documents = []
    for i, chunk in enumerate(chunks):
        print(f"🔄 Processing chunk {i+1}/{len(chunks)}")
        vector = get_embedding(chunk)
        if not vector:
            print("❌ Skipping chunk due to missing embedding")
            continue
        documents.append({
            "@search.action": "upload",
            "id": str(uuid.uuid4()),
            "content": chunk,
            "embedding": vector,
            "metadata": f"source:{source_name}"
        })

    if not documents:
        print("❌ No documents to upload to Azure Search.")
        return

    payload = {"value": documents}
    res = requests.post(SEARCH_URL, headers=SEARCH_HEADERS, json=payload)

    print("🔍 Azure Search Response:")
    print("Status Code:", res.status_code)
    print("Response Body:", res.text)

    if res.status_code == 200:
        print("✅ Chunks uploaded to Azure Cognitive Search successfully.")
    else:
        print("❌ Failed to upload to Azure Cognitive Search.")

# 🚀 Run Everything Together
def process_pdf(pdf_path):
    chunks = extract_chunks(pdf_path)
    print(f"✅ Extracted {len(chunks)} chunks from PDF")
    push_chunks_to_search(chunks, source_name=os.path.basename(pdf_path))

#testing ke liye sample uthao 
if __name__ == "__main__":
    # You can still run this for manual testing
    test_path = r"D:\TRAIL\pdf-extractor\pdf-backend\Sample.pdf.pdf"
    process_pdf(test_path)


