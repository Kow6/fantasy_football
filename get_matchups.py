import requests
import json
from datetime import datetime
import os

# --- CONFIGURATION (UPDATE THESE VALUES) ---
LEAGUE_ID = "1189644119835193344"  # <-- IMPORTANT: Replace this with your actual League ID
WEEK_NUMBER = 1                   # <-- IMPORTANT: Set the week you want to analyze

# --- API URL ---
MATCHUPS_API_URL = f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/matchups/{WEEK_NUMBER}"

# --- Output File ---
OUTPUT_FILE = f"matchups_week_{WEEK_NUMBER}.json"

# --- Function to Fetch and Save Data ---
def fetch_and_save_matchups():
    """Fetches matchup data for a specific week and saves it to a JSON file."""
    if LEAGUE_ID == "YOUR_LEAGUE_ID_HERE":
        print("❌ ERROR: Please update the LEAGUE_ID variable in the script with your actual ID.")
        return

    print(f"Fetching Week {WEEK_NUMBER} matchup data for League ID: {LEAGUE_ID}...")

    try:
        # 1. Make the GET request to the Sleeper API
        response = requests.get(MATCHUPS_API_URL, timeout=30)
        response.raise_for_status() 

        # 2. Get the JSON response (which is a list of matchup objects)
        matchup_data = response.json()

        # 3. Save the data to a local JSON file
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(matchup_data, f, indent=4)
        
        # 4. Report success
        print(f"✅ Success! Matchup data for Week {WEEK_NUMBER} downloaded.")
        print(f"File saved to: {os.path.abspath(OUTPUT_FILE)}")
        print("Remember to add this file to your .gitignore if you don't want to commit it.")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data: {e}")

if __name__ == "__main__":
    fetch_and_save_matchups()