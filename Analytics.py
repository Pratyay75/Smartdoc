from datetime import datetime, timedelta
from collections import defaultdict
from statistics import mean

def calculate_analytics(pdf_collection, period="month", user_id=None):
    days = {"day": 0, "week": 7, "month": 30, "all": 10000}
    now = datetime.utcnow()

    if period == "day":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period in days:
        cutoff = now - timedelta(days=days[period])
    else:
        cutoff = now - timedelta(days=30)

    query = {"timestamp": {"$gte": cutoff}} if period != "all" else {}
    if user_id:
        query["user_id"] = user_id

    records = list(pdf_collection.find(query))

    if not records:
        return {
            "total_pdfs": 0,
            "field_confidences": {},
            "top_review_fields": [],
            "lowest_accuracy_pdf": None
        }

    total_pdfs = len(records)
    field_confidence = defaultdict(list)
    manual_reviews = defaultdict(int)
    lowest_accuracy_pdf = {"pdfName": None, "accuracy": 100.0}

    for rec in records:
        ai_data = rec.get("ai_data", {})
        user_data = rec.get("user_updated_data", {})

     
        for field in ["name", "contractAmount", "issueDate"]:
            ai_conf = ai_data.get("field_confidences", {}).get(field)
            if ai_conf is not None:
                try:
                    field_confidence[field].append(float(ai_conf))
                except ValueError:
                    pass  # skip non-numeric

            ai_val = ai_data.get(field)
            user_val = user_data.get(field)
            if ai_val:
                is_corrected = user_val and str(ai_val).strip() != str(user_val).strip()
                if is_corrected:
                    manual_reviews[field] += 1

        corrected = sum(
            1 for f in ["name", "contractAmount", "issueDate"]
            if user_data.get(f) and str(user_data[f]).strip() != str(ai_data.get(f, "")).strip()
        )
        accuracy = round(((3 - corrected) / 3) * 100, 2)

        if accuracy < lowest_accuracy_pdf["accuracy"]:
            lowest_accuracy_pdf = {
                "pdfName": rec.get("pdfName"),
                "accuracy": accuracy
            }

    field_avg_conf = {k: round(mean(v), 2) for k, v in field_confidence.items()}
    top_fields_review = sorted(manual_reviews, key=manual_reviews.get, reverse=True)[:3]

    return {
        "total_pdfs": total_pdfs,
        "field_confidences": field_avg_conf,
        "top_review_fields": top_fields_review,
        "lowest_accuracy_pdf": lowest_accuracy_pdf
    }
