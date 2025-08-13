import os
import json
import uuid
import logging
from datetime import timedelta, datetime
from flask import Flask, request, jsonify
from flask import send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import fitz  # PyMuPDF
from dateutil import parser as dateparser
from openai import AzureOpenAI
import requests
from Analytics import (
    calculate_analytics,
)
from ingest_pdf import push_chunks_to_search, extract_chunks
# ------------------ CONFIG ------------------
load_dotenv()

app = Flask(__name__, static_folder="frontend/build", static_url_path="")

from flask_cors import CORS

CORS(app, supports_credentials=True, resources={r"/*": {
    "origins": [
        "http://localhost:3000",
        "https://smartdoc.azurewebsites.net"
    ],
    "allow_headers": ["Content-Type", "Authorization"],
    "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE"]
}})


logging.basicConfig(level=logging.INFO)

# Azure OpenAI Setup
client_azure = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_API_VERSION")
)
DEPLOYMENT_NAME = os.getenv("AZURE_GPT_DEPLOYMENT")
# MongoDB Setup
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["pdf_data"]
pdf_collection = db["extracted_data"]
users_collection = db["users"]

# Azure Search Setup
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_API_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")


# ------------------ Document classification helper ------------------


# ------------------ SIGNUP ------------------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    if users_collection.find_one({"email": data["email"]}):
        return jsonify({"error": "Email already registered"}), 400

    hashed_pw = generate_password_hash(data["password"])
    users_collection.insert_one({
        "name": data.get("name", data["email"].split("@")[0]),
        "email": data["email"],
        "password": hashed_pw
    })
    return jsonify({"message": "Signup successful"})


# ------------------ LOGIN ------------------
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json(force=True)
        email = data.get("email")
        password = data.get("password")

        user = users_collection.find_one({"email": email})
        if not user or not check_password_hash(user.get("password", ""), password):
            return jsonify({"error": "Invalid credentials"}), 401

        return jsonify({
            "token": str(user["_id"]),
            "name": user.get("name", email.split("@")[0])
        })
    except Exception as e:
        logging.error(f"Login error: {str(e)}")
        return jsonify({"error": "Server error"}), 500


#---------------------------------------------------
def format_ai_data(ai_data):
    try:
        name_conf = ai_data.get("policyholderName_confidence", 0)
        amount_conf = ai_data.get("premiumAmount_confidence", 0)
        date_conf = ai_data.get("issueDate_confidence", 0)

        field_confidences = {
            "name": name_conf,
            "contractAmount": amount_conf,
            "issueDate": date_conf
        }

        total = sum(field_confidences.values())
        count = len(field_confidences)
        accuracy = round(total / count, 2) if count > 0 else 0

        ai_data["field_confidences"] = field_confidences
        ai_data["accuracy"] = accuracy

        return ai_data

    except Exception as e:
        logging.warning(f"⚠️ format_ai_data() failed: {e}")
        return ai_data

#-------------------------image to text -------------------------
def extract_text_with_tesseract(file_path):
    from pdf2image import convert_from_path
    import pytesseract
    from pytesseract import pytesseract as tesseract_cmd

    # ✅ Tell pytesseract where tesseract.exe is
    tesseract_cmd.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    try:
        # ✅ Convert each page of PDF to image
        images = convert_from_path(file_path, dpi=300, poppler_path=r"C:\poppler-24.08.0\Library\bin")
        all_text = []

        for img in images:
            # ✅ OCR each image page
            text = pytesseract.image_to_string(img)
            all_text.append(text)

        return "\n".join(all_text)
    except Exception as e:
        logging.error(f"❌ Tesseract OCR failed: {e}")
        return ""



# ------------------ PDF EXTRACTION ------------------
# ------------------ PDF EXTRACTION ------------------
@app.route("/extract", methods=["POST"])
def extract_data():
    try:
        file = request.files.get("pdf")
        if not file:
            return jsonify({"error": "No PDF file provided"}), 400

        pdf_id = str(uuid.uuid4())
        if not file or file.filename == "":
            logging.error("❌ No PDF file uploaded.")
            return jsonify({"error": "No PDF file uploaded"}), 400

        filename = (file.filename or f"uploaded_{uuid.uuid4()}.pdf").replace(" ", "_")



        from azure.storage.blob import BlobServiceClient
        from io import BytesIO

        BLOB_CONN_STR = os.getenv("AZURE_BLOB_CONNECTION_STRING")
        BLOB_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")
        blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
        container_client = blob_service.get_container_client(BLOB_CONTAINER)

        # Upload to Azure Blob
        blob_name = f"{uuid.uuid4()}_{filename}"
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(file, overwrite=True)

        # Download file into memory
        file_stream = BytesIO()
        blob_client.download_blob().readinto(file_stream)
        file_stream.seek(0)

        text = ""
        word_count = 0
        empty_pages = 0

        pdf_file = fitz.open(stream=file_stream.read(), filetype="pdf")

        # Push chunks to Azure Cognitive Search
        chunks = [page.get_text().strip() for page in pdf_file if page.get_text().strip()]
        push_chunks_to_search(chunks, source_name=filename)

        page_count = len(pdf_file)

        # Count words & detect empty pages
        file_stream.seek(0)
        pdf_file = fitz.open(stream=file_stream.read(), filetype="pdf")
        for page in pdf_file:
            page_text = page.get_text().strip()
            if not page_text:
                empty_pages += 1
            else:
                text += page_text + "\n"
                word_count += len(page_text.split())

        empty_ratio = empty_pages / page_count

        # OCR fallback
        if word_count < 30 or empty_ratio > 0.5:
            logging.warning(
                f"⚠️ Detected scanned PDF (word_count={word_count}, empty_pages={empty_pages}/{page_count}) — using Tesseract OCR fallback."
            )
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_stream.getvalue())
                tmp_path = tmp.name
            text = extract_text_with_tesseract(tmp_path)
            word_count = len(text.split())

        # GPT prompt for structured data extraction
        prompt = f"""
You are a professional document parser AI. Your task is to extract **structured information** from health insurance policy documents, regardless of how messy or inconsistent the text may be.

Use the following schema to return the extracted data as pure JSON only (no extra text):

{{
  "policyholderName": {{ "value": string | null, "confidence": integer }},
  "issueDateRaw": string | null,
  "issueDate": {{ "value": string | null, "confidence": integer }},
  "expirationDateRaw": string | null,
  "expirationDate": {{ "value": string | null, "confidence": integer }},
  "providerName": {{ "value": string | null, "confidence": integer }},
  "policyholderAddress": {{ "value": string | null, "confidence": integer }},
  "policyNumber": {{ "value": string | null, "confidence": integer }},
  "premiumAmount": {{ "value": string | null, "confidence": integer }},
  "deductibles": {{ "value": string | null, "confidence": integer }},
  "termsAndExclusions": list of strings | null
}}

📌 **Instructions for Fields**:
- **policyholderName**: Extract the full name of the insured person (or entity) — avoid nicknames or initials unless that's all that's available.
- **issueDateRaw**: The exact string as shown in the document (e.g., "15th June 2024").
- **issueDate**: Convert issueDateRaw into `"DD-MM-YYYY"` format. Use best guess if ambiguous.
- **expirationDateRaw** and **expirationDate**: Same rules as above.
- **providerName**: Company or organization issuing the policy (e.g., "Star Health", "LIC", "HDFC Ergo").
- **policyholderAddress**: Full address if present, partial if not complete.
- **policyNumber**: Any unique alphanumeric string representing the policy.
- **premiumAmount**:
    - This refers to the **Sum Assured** — the total amount of coverage or the maturity payout.
    - If multiple monetary amounts exist, prefer the largest one explicitly labeled "Sum Assured", "Total Benefit", or similar.
    - Format as-is (e.g., "Rs. 5,00,000", "$50,000").
- **deductibles**:
    - This refers to **recurring premium payments** (weekly, monthly, quarterly, annually).
    - Prioritize values labeled as **"Premium Frequency"**, **"Recurring Premium"**, or similarly.
    - Format as-is (e.g., "Rs. 2,500 monthly", "$100 quarterly").
- **termsAndExclusions**:
    - Extract any bullet points, clauses, or lines indicating what is **excluded from coverage** or under what **conditions claims may be denied**.
    - Return as a **list of individual strings**.

🎯 **Output Format Rules**:
- Return ONLY valid JSON — no extra text, no explanation.
- Every key listed above must be present. Use `null` for values not found.
- For any extracted field, estimate a **confidence score from 0 to 100** based on clarity, keyword match, and certainty.
- Avoid placeholders like "N/A", "Not Found", or "Unavailable" — just use `null`.

🧠 **Extra Context**:
- This document might be scanned or unstructured.
- Be resilient to typos, poor formatting, or OCR noise.
- If a field seems partially matched, still attempt to extract it with lower confidence.

📝 Here is the text to extract from:
{text}
"""



        response = client_azure.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You extract structured data from contracts, even if the format is messy."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        extracted_data = response.choices[0].message.content.strip()

        # Clean JSON
        import re
        cleaned = re.sub(r"^```(?:json)?|```$", "", extracted_data.strip(), flags=re.MULTILINE).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        cleaned = match.group(0) if match else extracted_data

        # Parse and flatten JSON
        try:
            parsed_data = json.loads(cleaned)
            flattened = {
                "policyholderName": parsed_data.get("policyholderName", {}).get("value"),
                "policyholderName_confidence": parsed_data.get("policyholderName", {}).get("confidence", 0),
                "issueDateRaw": parsed_data.get("issueDateRaw"),
                "issueDate": parsed_data.get("issueDate", {}).get("value"),
                "issueDate_confidence": parsed_data.get("issueDate", {}).get("confidence", 0),
                "expirationDateRaw": parsed_data.get("expirationDateRaw"),
                "expirationDate": parsed_data.get("expirationDate", {}).get("value"),
                "expirationDate_confidence": parsed_data.get("expirationDate", {}).get("confidence", 0),
                "providerName": parsed_data.get("providerName", {}).get("value"),
                "providerName_confidence": parsed_data.get("providerName", {}).get("confidence", 0),
                "policyholderAddress": parsed_data.get("policyholderAddress", {}).get("value"),
                "policyholderAddress_confidence": parsed_data.get("policyholderAddress", {}).get("confidence", 0),
                "policyNumber": parsed_data.get("policyNumber", {}).get("value"),
                "policyNumber_confidence": parsed_data.get("policyNumber", {}).get("confidence", 0),
                "premiumAmount": parsed_data.get("premiumAmount", {}).get("value"),
                "premiumAmount_confidence": parsed_data.get("premiumAmount", {}).get("confidence", 0),
                "deductibles": parsed_data.get("deductibles", {}).get("value"),
                "deductibles_confidence": parsed_data.get("deductibles", {}).get("confidence", 0),
                "termsAndExclusions": parsed_data.get("termsAndExclusions"),
            }
            # Always extract Premium from the Policy Schedule line explicitly
            import re

# 👇 Fallback logic if GPT misses the values

# Premium Amount (Total Sum Assured or Maturity)
            if not flattened.get("premiumAmount"):
                match = re.search(
                    r"(sum assured|total benefit|maturity amount)[^\n]*?(Rs\.?\s*[\d,]+)",
                    text,
                    re.IGNORECASE
                )
                if match:
                    flattened["premiumAmount"] = match.group(2).strip()
                    flattened["premiumAmount_confidence"] = 75

# Deductibles (Recurring Premiums)
            if not flattened.get("deductibles"):
                match = re.search(
                    r"(premium(?: per| payable)?(?:.*)?)[^\n]*?(Rs\.?\s*[\d,]+\s*(?:monthly|quarterly|annually|yearly)?)",
                    text,
                    re.IGNORECASE
                )
                if match:
                    flattened["deductibles"] = match.group(2).strip()
                    flattened["deductibles_confidence"] = 70



            # Format extracted dates to DD-MM-YYYY
            for field in ["issueDate", "expirationDate"]:
                if flattened.get(field):
                    try:
                        dt = dateparser.parse(flattened[field], fuzzy=True)
                        flattened[field] = dt.strftime("%d-%m-%Y")
                    except Exception as e:
                        logging.warning(f"⚠️ Could not format {field}: {e}")

            parsed_data = format_ai_data(flattened)

        except json.JSONDecodeError:
            logging.error(f"⚠️ Invalid JSON from model: {cleaned}")
            parsed_data = {"raw_output": extracted_data}

        # Save to MongoDB
        user_id = request.form.get("user_id")
        if not user_id:
            return jsonify({"error": "Missing user_id in form data"}), 400

        user_id = request.form.get("user_id")
        pdf_collection.insert_one({
            "pdf_id": pdf_id,
            "pdfName": filename,
            "ai_data": parsed_data,
            "pageCount": page_count,
            "wordCount": word_count,
            "timestamp": datetime.utcnow(),
            "user_id": user_id
        })

        return jsonify({"pdf_id": pdf_id, **parsed_data})

    except Exception as e:
        logging.error(f"❌ Error during extraction: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ------------------ SAVE EDITED DATA ------------------
@app.route("/save", methods=["POST"])
def save():
    data = request.get_json()
    user_id = data.get("user_id")
    pdf_id = data.get("pdf_id")
    updated_fields = data.get("user_updated_data")

    if not pdf_id or not updated_fields:
        return jsonify({"error": "Missing pdf_id or updated data"}), 400

    # Format issueDate if present
    if "issueDate" in updated_fields:
        try:
            dt = dateparser.parse(updated_fields["issueDate"], fuzzy=True)
            updated_fields["issueDate"] = dt.strftime("%d-%m-%Y")
        except Exception as e:
            logging.warning(f"Could not parse issueDate in save(): {e}")

    # Get the original document to compare
    existing = pdf_collection.find_one({"pdf_id": pdf_id})
    if not existing:
        return jsonify({"error": "PDF not found"}), 404

    ai_data = existing.get("ai_data", {})
    # Compare only changed fields
    changes = {k: v for k, v in updated_fields.items() if ai_data.get(k) != v}

    if not changes:
        return jsonify({"message": "Data Saved"}), 200

    result = pdf_collection.update_one(
    {"pdf_id": pdf_id},
    {
        "$set": {
            "user_updated_data": changes,
            "user_id": user_id,  # ensure update preserves user
            "timestamp": datetime.utcnow()
        }
    }
)


    return jsonify({"message": "User updated data saved successfully"})



# ------------------ Multi-doc upload route ------------------
from werkzeug.utils import secure_filename
import tempfile
import fitz  # PyMuPDF
import docx
import chardet

@app.route("/upload-multi-doc", methods=["POST"])
def upload_multi_doc():
    """
    Accept multiple documents, upload them to Azure Blob Storage,
    process them into chunks, send to Azure Search (with blob_name in metadata)
    using batched embedding requests for speed, and return metadata for frontend.
    """
    try:
        if "files" not in request.files:
            return jsonify({"error": "No files provided"}), 400

        uploaded_files = request.files.getlist("files")
        results = []

        from azure.storage.blob import BlobServiceClient
        BLOB_CONN_STR = os.getenv("AZURE_BLOB_CONNECTION_STRING")
        BLOB_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")
        blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
        container_client = blob_service.get_container_client(BLOB_CONTAINER)

        # --- Helper: batch embeddings ---
        import requests
        def get_embeddings_batch(chunk_list):
            """Get embeddings for multiple chunks in one API call."""
            data = {
                "input": chunk_list,
                "model": os.getenv("AZURE_EMBEDDING_DEPLOYMENT")
            }
            EMBEDDING_URL = f"{os.getenv('AZURE_OPENAI_ENDPOINT')}openai/deployments/{os.getenv('AZURE_EMBEDDING_DEPLOYMENT')}/embeddings?api-version={os.getenv('AZURE_API_VERSION')}"
            EMBEDDING_HEADERS = {
                "api-key": os.getenv("AZURE_OPENAI_API_KEY"),
                "Content-Type": "application/json"
            }
            res = requests.post(EMBEDDING_URL, headers=EMBEDDING_HEADERS, json=data)
            if res.status_code == 200:
                return [item['embedding'] for item in res.json()['data']]
            else:
                print("❌ Embedding batch failed:", res.text)
                return [[] for _ in chunk_list]

        def push_chunks_to_search_batched(chunks, source_name, blob_name=None, batch_size=20):
            """
            Push chunks to Azure Cognitive Search with batched embedding requests.
            """
            if isinstance(chunks, str):
                chunks = [chunks]

            documents = []
            total_chunks = len(chunks)

            SEARCH_URL = f"{os.getenv('AZURE_SEARCH_ENDPOINT')}/indexes/{os.getenv('AZURE_SEARCH_INDEX')}/docs/index?api-version=2023-07-01-Preview"
            SEARCH_HEADERS = {
                "Content-Type": "application/json",
                "api-key": os.getenv("AZURE_SEARCH_API_KEY")
            }

            # Process in batches
            for start in range(0, total_chunks, batch_size):
                batch_chunks = chunks[start:start + batch_size]
                print(f"🔄 Processing batch {start//batch_size + 1} "
                      f"({len(batch_chunks)} chunks) from {source_name}")

                vectors = get_embeddings_batch(batch_chunks)
                for chunk_text, vector in zip(batch_chunks, vectors):
                    if not vector:
                        print("❌ Skipping chunk due to missing embedding")
                        continue

                    metadata_val = f"source:{source_name}"
                    if blob_name:
                        metadata_val += f";blob:{blob_name}"

                    doc = {
                        "@search.action": "upload",
                        "id": str(uuid.uuid4()),
                        "content": chunk_text,
                        "embedding": vector,
                        "metadata": metadata_val
                    }
                    if blob_name:
                        doc["blob_name"] = blob_name

                    documents.append(doc)

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

        # --- Main file loop ---
        for file in uploaded_files:
            filename = secure_filename(file.filename)
            ext = filename.lower().split(".")[-1]

            # save temp file
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                file.save(tmp.name)
                file_path = tmp.name

            # extract text chunks
            if ext == "pdf":
                chunks = extract_chunks(file_path)
            elif ext == "docx":
                import docx
                docx_doc = docx.Document(file_path)
                chunks = [p.text for p in docx_doc.paragraphs if p.text.strip()]
            elif ext == "txt":
                import chardet
                with open(file_path, "rb") as f:
                    raw_data = f.read()
                    detected_encoding = chardet.detect(raw_data)["encoding"] or "utf-8"
                    text_content = raw_data.decode(detected_encoding, errors="ignore")
                chunks = [p.strip() for p in text_content.split("\n\n") if p.strip()]
            else:
                os.unlink(file_path)
                continue

            # upload to blob
            blob_name = f"{uuid.uuid4()}_{filename}"
            with open(file_path, "rb") as data:
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.upload_blob(data, overwrite=True)

            # push to search with blob_name (batched)
            push_chunks_to_search_batched(
                chunks,
                source_name=filename,
                blob_name=blob_name
            )

            # prepare return data
            size_kb = round(os.path.getsize(file_path) / 1024, 1)
            results.append({
                "name": filename,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Uploaded",
                "size": f"{size_kb} KB",
                "blob_name": blob_name
            })

            os.unlink(file_path)

        return jsonify({"documents": results})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def delete_search_docs_by_blob(blob_name):
    """Delete all docs from Azure Search that match blob_name in metadata."""
    try:
        search_url = f"{os.getenv('AZURE_SEARCH_ENDPOINT')}/indexes/{os.getenv('AZURE_SEARCH_INDEX')}/docs/search?api-version=2023-07-01-Preview"
        headers = {"Content-Type": "application/json", "api-key": os.getenv("AZURE_SEARCH_API_KEY")}
        body = {"search": blob_name, "top": 1000}
        res = requests.post(search_url, headers=headers, json=body)
        if res.status_code != 200:
            print("Search query failed for blob deletion:", res.text)
            return False

        hits = res.json().get("value", [])
        ids = [d.get("id") for d in hits if d.get("id")]
        if not ids:
            return True

        delete_payload = {"value": [{"@search.action": "delete", "id": doc_id} for doc_id in ids]}
        update_url = f"{os.getenv('AZURE_SEARCH_ENDPOINT')}/indexes/{os.getenv('AZURE_SEARCH_INDEX')}/docs/index?api-version=2023-07-01-Preview"
        res2 = requests.post(update_url, headers=headers, json=delete_payload)
        return res2.status_code in (200, 201)
    except Exception as e:
        print("Error in delete_search_docs_by_blob:", e)
        return False


@app.route("/delete-blob", methods=["POST"])
def delete_blob_route():
    """Delete a single blob and its related Azure Search docs."""
    try:
        data = request.get_json(force=True)
        blob_name = data.get("blob_name")
        if not blob_name:
            return jsonify({"error": "Missing blob_name"}), 400

        from azure.storage.blob import BlobServiceClient
        BLOB_CONN_STR = os.getenv("AZURE_BLOB_CONNECTION_STRING")
        BLOB_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")
        blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
        container_client = blob_service.get_container_client(BLOB_CONTAINER)
        container_client.delete_blob(blob_name)

        delete_search_docs_by_blob(blob_name)

        return jsonify({"message": f"Blob {blob_name} deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/delete-multiple-blobs", methods=["POST"])
def delete_multiple_blobs_route():
    """Delete multiple blobs and their related Azure Search docs."""
    try:
        data = request.get_json(force=True)
        blob_names = data.get("blob_names", [])
        if not blob_names:
            return jsonify({"error": "Missing blob_names list"}), 400

        from azure.storage.blob import BlobServiceClient
        BLOB_CONN_STR = os.getenv("AZURE_BLOB_CONNECTION_STRING")
        BLOB_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER")
        blob_service = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
        container_client = blob_service.get_container_client(BLOB_CONTAINER)

        for blob_name in blob_names:
            container_client.delete_blob(blob_name)
            delete_search_docs_by_blob(blob_name)

        return jsonify({"message": "All blobs deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ------------------ CHATBOT ------------------
def query_azure_search(question, top_k=5):
    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX}/docs/search?api-version=2023-07-01-Preview"
    headers = {"Content-Type": "application/json", "api-key": AZURE_SEARCH_KEY}
    body = {"search": question, "top": top_k}
    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        results = response.json()
        return [doc["content"] for doc in results.get("value", [])]
    except Exception as e:
        print("❌ Azure Search Query Failed:", e)
        return []


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    pdf_id = data.get("pdf_id")
    question = data.get("question")

    record = pdf_collection.find_one({"pdf_id": pdf_id})
    if not record:
        return jsonify({"error": "PDF data not found"}), 404

    ai_summary = json.dumps(record.get("ai_data", {}), indent=2)
    search_chunks = query_azure_search(question)
    full_text = "\n\n---\n\n".join(search_chunks) if search_chunks else ai_summary

    prompt = f"""
You are  —Chatbot a smart, human-like assistant trained to help users understand complex PDFs such as contracts, insurance policies, business reports, or legal documents.

🎯 Your Goal:
Help the user by answering their question **only using the content of the provided PDF**. Be friendly, clear, and act like a real assistant — not a machine.

---

🧠 Behavior Rules:
- Be professional, conversational, and accurate.
- Use ONLY the content in the PDF to answer.
- If something is not clearly mentioned, say so politely.
- Do not assume or guess beyond what’s written.

📌 Formatting Rules:
- If the user asks for **bullet points, lists, dates, exclusions, or summary points**, format them as:
  - Each item starts with a dash (-).
  - Each item is on a new line.
  - Leave a blank line between items for better readability.
- If the user asks for **steps or instructions**, format them with:
  1. Numbered steps
  2. Clear spacing
  3. Proper punctuation
- If the user asks for a **specific value** (e.g., date, name, amount):
  → Give a short, direct, clear sentence.
- Do NOT return any code, JSON, or technical symbols.

---

📄 PDF Content:
{full_text}

❓ User’s Question:
{question}

---

💬 Your Answer:
(Reply naturally like a helpful assistant would. Avoid sounding robotic.)
"""


    try:
        response = client_azure.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a conversational assistant answering based on PDF content."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        answer = response.choices[0].message.content.strip()
        return jsonify({"answer": answer})
    except Exception as e:
        logging.error(f"❌ Error in chatbot: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/chat-multi-doc", methods=["POST"])
def chat_multi_doc():
    """
    Chatbot for multi-document context using Azure Search RAG.
    Filters search results by blob_names if provided.
    """
    try:
        data = request.json
        question = data.get("question", "").strip()
        blob_names = data.get("blob_names", [])

        if not question:
            return jsonify({"error": "No question provided"}), 400

        # Build Azure Search filter if blob_names provided
        filter_query = None
        if blob_names:
            filter_parts = [f"blob_name eq '{name}'" for name in blob_names]
            filter_query = " or ".join(filter_parts)

        # Search Azure with optional filter
        url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX}/docs/search?api-version=2023-07-01-Preview"
        headers = {"Content-Type": "application/json", "api-key": AZURE_SEARCH_KEY}
        body = {
            "search": question,
            "top": 20
        }
        if filter_query:
            body["filter"] = filter_query

        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        hits = response.json().get("value", [])
        search_chunks = [doc["content"] for doc in hits if "content" in doc]

        if not search_chunks:
            return jsonify({"answer": "I couldn't find any relevant information in the uploaded documents."})

        # Join chunks and send to Azure OpenAI
        full_text = "\n\n---\n\n".join(search_chunks)
        prompt = f"""
You are Chatbot, a helpful assistant answering based only on the provided documents.

📄 Document Content:
{full_text}

❓ Question:
{question}

💬 Answer:
"""

        llm_response = client_azure.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant answering based on multiple documents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )

        return jsonify({"answer": llm_response.choices[0].message.content.strip()})

    except Exception as e:
        logging.error(f"❌ Error in chat_multi_doc: {str(e)}")
        return jsonify({"error": str(e)}), 500


#-------------------analytics---------------
@app.route("/analytics", methods=["POST"])
def get_user_analytics():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        period = data.get("filter", "month")  

        if not user_id:
            return jsonify({"error": "Missing user_id"}), 400

        from Analytics import calculate_analytics
        analytics_data = calculate_analytics(pdf_collection, period=period, user_id=user_id)
        return jsonify(analytics_data)

    except Exception as e:
        logging.error(f"❌ Analytics route error: {str(e)}")
        return jsonify({"error": "Failed to calculate analytics"}), 500


@app.route("/analytics/trends", methods=["POST"])
def analytics_trends():
    data = request.get_json()
    user_id = data.get("user_id")
    filter_by = data.get("filter", "month")

    if not user_id:
        return jsonify({"error": "Missing user ID"}), 400

    now = datetime.now()
    if filter_by == "day":
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif filter_by == "week":
        start_time = now - timedelta(days=7)
    elif filter_by == "month":
        start_time = now - timedelta(days=30)
    else:
        start_time = datetime.min

    pipeline = [
        {
            "$match": {
                "user_id": user_id,
                "timestamp": {"$gte": start_time}
            }
        },
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$timestamp"},
                    "month": {"$month": "$timestamp"},
                    "day": {"$dayOfMonth": "$timestamp"},
                },
                "avg_accuracy": {"$avg": "$ai_data.accuracy"}
            }
        },
        {
            "$sort": {"_id": 1}
        }
    ]

    results = list(pdf_collection.aggregate(pipeline))

    trend = []
    for r in results:
        y, m, d = r["_id"]["year"], r["_id"]["month"], r["_id"]["day"]
        date_str = f"{d:02d}-{m:02d}-{y}"
        trend.append({"date": date_str, "avg_accuracy": r["avg_accuracy"]})

    return jsonify({"trend": trend})

@app.route("/analytics/pdf-details", methods=["POST"])
def analytics_pdf_details():
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "Missing user ID"}), 400

    pdfs = list(pdf_collection.find(
    {"user_id": user_id},
    {"pdfName": 1, "ai_data": 1, "timestamp": 1, "pageCount": 1, "wordCount": 1}
).sort("timestamp", -1))


    for pdf in pdfs:
        pdf["_id"] = str(pdf["_id"])

        # Extract from ai_data if not top-level
        ai_data = pdf.get("ai_data", {})
        pdf["accuracy"] = ai_data.get("accuracy")
        pdf["field_confidences"] = ai_data.get("field_confidences", {})

        # Format timestamp for display
        if "timestamp" in pdf:
            pdf["timestamp"] = pdf["timestamp"].strftime("%d-%m-%Y %H:%M")
    return jsonify({"pdfs": pdfs})
# --------------------------- PDF COMPARE ---------------------------
import fitz  # PyMuPDF
import re
from dateutil import parser as dateparser
from flask import Flask, request, jsonify
from rapidfuzz import fuzz
import diff_match_patch as dmp_module

# ---------- Config ----------
PARA_MATCH_THRESHOLD = 80   # lower to catch minor changes
LINE_MATCH_THRESHOLD = 85   # slightly lower for OCR tolerance
MIN_PARTIAL_THRESHOLD = 60

DATE_RE = re.compile(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b")
NUMERIC_RE = re.compile(r"\b\d+(?:\.\d+)?\b")  # matches integers and decimals

# ---------- Helpers ----------

def normalize_whitespace(text: str) -> str:
    text = text.replace('\r', '\n')
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(ln.strip() for ln in text.splitlines())
    return text.strip()

def normalize_dates(text: str) -> str:
    def repl(m):
        try:
            d = dateparser.parse(m.group(0), dayfirst=True)
            return d.strftime("%d-%m-%Y")
        except Exception:
            return m.group(0)
    return DATE_RE.sub(repl, text)

def extract_paragraphs_from_pdf_bytes(file_bytes: bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    paras = []
    for page in doc:
        raw = page.get_text("text") or ""
        raw = normalize_whitespace(raw)
        # Split on blank lines OR newline + capital letter
        for p in re.split(r"(?:\n\s*\n)|(?:\n(?=[A-Z]))", raw):
            p = p.strip()
            if p:
                p = normalize_dates(p)
                paras.append(p)
    doc.close()
    return paras

def numbers_changed(a: str, b: str) -> bool:
    """Check if numeric values differ between strings."""
    nums_a = re.findall(r"\b\d+(?:\.\d+)?\b", a)
    nums_b = re.findall(r"\b\d+(?:\.\d+)?\b", b)
    return nums_a != nums_b

def dates_changed(a: str, b: str) -> bool:
    """Check if date values differ between strings (after normalization)."""
    dates_a = [normalize_dates(m) for m in DATE_RE.findall(a)]
    dates_b = [normalize_dates(m) for m in DATE_RE.findall(b)]
    return dates_a != dates_b

def word_level_diff_html(a: str, b: str) -> str:
    # NEW: if numeric or date values differ, mark whole thing removed/new
    if numbers_changed(a, b) or dates_changed(a, b):
        return f'<span class="removed">{a}</span><span class="new">{b}</span>'
    
    dmp = dmp_module.diff_match_patch()
    diffs = dmp.diff_main(a, b)
    dmp.diff_cleanupSemantic(diffs)
    parts = []
    for op, data in diffs:
        txt = data.replace("\n", "<br/>")
        if op == 0:
            parts.append(f'<span class="same">{txt}</span>')
        elif op == -1:
            parts.append(f'<span class="removed">{txt}</span>')
        elif op == 1:
            parts.append(f'<span class="new">{txt}</span>')
    return "".join(parts)

# ---------- Main Compare Route ----------

@app.route("/compare", methods=["POST"])
def compare_pdfs():
    try:
        pdf1 = request.files.get("pdf1")
        pdf2 = request.files.get("pdf2")
        if not pdf1 or not pdf2:
            return jsonify({"error": "Both pdf1 and pdf2 are required"}), 400

        paras1 = extract_paragraphs_from_pdf_bytes(pdf1.read())
        paras2 = extract_paragraphs_from_pdf_bytes(pdf2.read())

        matched_2 = set()
        html_blocks = []

        # Match paragraphs regardless of order
        for p1 in paras1:
            best_score = -1
            best_j = None
            for j, p2 in enumerate(paras2):
                if j in matched_2:
                    continue
                score = fuzz.ratio(p1, p2)
                if score > best_score:
                    best_score = score
                    best_j = j

            if best_score >= PARA_MATCH_THRESHOLD and best_j is not None:
                wl_html = word_level_diff_html(p1, paras2[best_j])
                html_blocks.append(f'<div class="para same">{wl_html}</div>')
                matched_2.add(best_j)
            else:
                best_para_j = None
                best_para_score = -1
                for j, p2 in enumerate(paras2):
                    if j in matched_2:
                        continue
                    score = fuzz.partial_ratio(p1, p2)
                    if score > best_para_score:
                        best_para_score = score
                        best_para_j = j

                if best_para_j is None or best_para_score < MIN_PARTIAL_THRESHOLD:
                    html_blocks.append(f'<div class="para removed">{p1}</div>')
                else:
                    p2 = paras2[best_para_j]
                    matched_2.add(best_para_j)

                    lines1 = [ln.strip() for ln in p1.splitlines() if ln.strip()]
                    lines2 = [ln.strip() for ln in p2.splitlines() if ln.strip()]
                    matched_lines2 = set()
                    para_html = ['<div class="para">']

                    for l1 in lines1:
                        best_lscore = -1
                        best_lidx = None
                        for idx2, l2 in enumerate(lines2):
                            if idx2 in matched_lines2:
                                continue
                            score = fuzz.ratio(l1, l2)
                            if score > best_lscore:
                                best_lscore = score
                                best_lidx = idx2
                        if best_lscore >= LINE_MATCH_THRESHOLD and best_lidx is not None:
                            wl_html = word_level_diff_html(l1, lines2[best_lidx])
                            para_html.append(f'<div class="line same">{wl_html}</div>')
                            matched_lines2.add(best_lidx)
                        elif best_lscore >= MIN_PARTIAL_THRESHOLD and best_lidx is not None:
                            wl_html = word_level_diff_html(l1, lines2[best_lidx])
                            para_html.append(f'<div class="line partial">{wl_html}</div>')
                            matched_lines2.add(best_lidx)
                        else:
                            para_html.append(f'<div class="line removed">{l1}</div>')

                    # New lines in p2 not matched
                    for idx2, l2 in enumerate(lines2):
                        if idx2 not in matched_lines2:
                            para_html.append(f'<div class="line new">{l2}</div>')

                    para_html.append('</div>')
                    html_blocks.append("".join(para_html))

        # Any paras in PDF2 not matched at all → NEW
        for j, p2 in enumerate(paras2):
            if j not in matched_2:
                html_blocks.append(f'<div class="para new">{p2}</div>')

        final_html = '<div class="compare-output">' + "\n".join(html_blocks) + '</div>'
        return jsonify({"html_result": final_html}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


#-----------------------------------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ------------------ START SERVER ------------------
if __name__ == "__main__": 
    app.run(debug=True)