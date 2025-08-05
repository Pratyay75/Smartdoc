import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from .env
search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
search_api_key = os.getenv("AZURE_SEARCH_API_KEY")
index_name = os.getenv("AZURE_SEARCH_INDEX")

# Headers for request
headers = {
    "Content-Type": "application/json",
    "api-key": search_api_key
}

# URL to create index
url = f"{search_endpoint}/indexes/{index_name}?api-version=2023-07-01-Preview"

# Define the index structure
index_config = {
    "name": index_name,
    "fields": [
        {"name": "id", "type": "Edm.String", "key": True, "searchable": False},
        {"name": "content", "type": "Edm.String", "searchable": True},
        {
            "name": "embedding",
            "type": "Collection(Edm.Single)",
            "searchable": True,  # ✅ FIXED: must be searchable
            "dimensions": 1536,  # ✅ FIXED: must be named "dimensions"
            "vectorSearchConfiguration": "default"
        },
        {"name": "metadata", "type": "Edm.String", "searchable": True}
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

# Call Azure Cognitive Search to create the index
response = requests.put(url, headers=headers, data=json.dumps(index_config))

# Output result
print("Status Code:", response.status_code)
print(response.json())
