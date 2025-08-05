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
from ingest_pdf import push_chunks_to_search
# ------------------ CONFIG ------------------
load_dotenv()

app = Flask(__name__, static_folder="frontend/build", static_url_path="")

from flask_cors import CORS

CORS(app, supports_credentials=True, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "https://smartdoc.azurewebsites.net"
        ]
    }
})




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
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX_NAME")


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


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ------------------ START SERVER ------------------
#if __name__ == "__main__": 
 #   app.run(debug=True)