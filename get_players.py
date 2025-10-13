import requests
import json
import os
from datetime import datetime

# --- Configuration ---
# Sleeper API endpoint for all NFL players
PLAYER_API_URL = "https://api.sleeper.app/v1/players/nfl"

# The name of the file to save the player data to (includes a timestamp)
NOW = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = f"sleeper_players_{NOW}.json"

# --- Function to Fetch and Save Data ---
def fetch_and_save_players():
    """Fetches all NFL player data from Sleeper and saves it to a JSON file."""
    print("Fetching all NFL player data from Sleeper API...")

    try:
        # 1. Make the GET request to the Sleeper API
        response = requests.get(PLAYER_API_URL, timeout=30)
        
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status() 

        # 2. Get the JSON response (which is a massive dictionary)
        player_data = response.json()

        # 3. Save the data to a local JSON file
        with open(OUTPUT_FILE, 'w') as f:
            # The indent=4 makes the file readable for inspection
            json.dump(player_data, f, indent=4)
        
        # 4. Report success
        print(f"✅ Success! Data for {len(player_data)} players downloaded.")
        print(f"File saved to: {os.path.abspath(OUTPUT_FILE)}")
        print("Your player IDs are the dictionary keys in this file.")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    fetch_and_save_players()