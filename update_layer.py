import requests
from datetime import datetime, timedelta
import json
import os

CLIENT_ID = os.environ["SH_CLIENT_ID"]
CLIENT_SECRET = os.environ["SH_CLIENT_SECRET"]
INSTANCE_ID = "45611b79-eeba-4a56-b9e1-8398eaeb4edf"
LAYER_ID = "TRUE-COLOR-S2L2A"

# Your area of interest (North Cascades)
BBOX = [-122.0, 48.7, -121.0, 49.1]

def get_token():
    r = requests.post(
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
    )
    r.raise_for_status()
    return r.json()["access_token"]

def find_best_date(token):
    """Find most recent scene with <20% cloud cover in last 60 days"""
    end = datetime.utcnow()
    start = end - timedelta(days=60)
    
    r = requests.post(
        "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "bbox": BBOX,
            "datetime": f"{start.strftime('%Y-%m-%dT00:00:00Z')}/{end.strftime('%Y-%m-%dT00:00:00Z')}",
            "collections": ["sentinel-2-l2a"],
            "filter": "eo:cloud_cover < 20",
            "sortby": [{"field": "datetime", "direction": "desc"}],
            "limit": 1
        }
    )
    r.raise_for_status()
    features = r.json().get("features", [])
    if not features:
        print("No clear scenes found, widening to 40% cloud cover...")
        r = requests.post(
            "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "bbox": BBOX,
                "datetime": f"{start.strftime('%Y-%m-%dT00:00:00Z')}/{end.strftime('%Y-%m-%dT00:00:00Z')}",
                "collections": ["sentinel-2-l2a"],
                "filter": "eo:cloud_cover < 40",
                "sortby": [{"field": "datetime", "direction": "desc"}],
                "limit": 1
            }
        )
        features = r.json().get("features", [])
    
    best_date = features[0]["properties"]["datetime"][:10]
    print(f"Best scene date: {best_date}")
    return best_date

def update_layer(token, best_date):
    # First get current configuration
    r = requests.get(
        f"https://sh.dataspace.copernicus.eu/configuration/v1/wms/instances/{INSTANCE_ID}/layers",
        headers={"Authorization": f"Bearer {token}"}
    )
    r.raise_for_status()
    layers = r.json()
    
    # Find and update our layer
    for layer in layers:
        if layer["id"] == LAYER_ID:
            # Set time range to 8-day window ending on best date
            end_date = datetime.strptime(best_date, "%Y-%m-%d")
            start_date = end_date - timedelta(days=8)
            
            layer["datasourceDefaults"]["timeRange"] = {
                "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                "to": end_date.strftime("%Y-%m-%dT23:59:59Z")
            }
            
            # Push update
            r2 = requests.put(
                f"https://sh.dataspace.copernicus.eu/configuration/v1/wms/instances/{INSTANCE_ID}/layers/{LAYER_ID}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=layer
            )
            r2.raise_for_status()
            print(f"Layer updated to {start_date.date()} / {end_date.date()}")
            return
    
    print("Layer not found!")

if __name__ == "__main__":
    token = get_token()
    best_date = find_best_date(token)
    update_layer(token, best_date)