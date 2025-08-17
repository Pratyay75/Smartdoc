# create_multi_doc_index.py
import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
search_api_key = os.getenv("AZURE_SEARCH_API_KEY")
index_name = os.getenv("AZURE_MULTI_DOC_INDEX")  # <- separate index name in .env

headers = {
    "Content-Type": "application/json",
    "api-key": search_api_key
}

url = f"{search_endpoint}/indexes/{index_name}?api-version=2023-07-01-Preview"

index_config = {
    "name": index_name,
    "fields": [
        {"name": "id", "type": "Edm.String", "key": True, "searchable": False},
        {"name": "content", "type": "Edm.String", "searchable": True},
        {
            "name": "embedding",
            "type": "Collection(Edm.Single)",
            "searchable": True,
            "dimensions": 1536,
            "vectorSearchConfiguration": "default"
        },
        {"name": "metadata", "type": "Edm.String", "searchable": True},   # "source:<blob_name>"
        {"name": "filename", "type": "Edm.String", "searchable": True}    # ✅ Added field
    ],
    "vectorSearch": {
        "algorithmConfigurations": [
            {
                "name": "default",
                "kind": "hnsw",
                "hnswParameters": {
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": "cosine"
                }
            }
        ]
    }
}

response = requests.put(url, headers=headers, data=json.dumps(index_config))
print("Status Code:", response.status_code)
try:
    print(response.json())
except Exception:
    print("No JSON response returned")
