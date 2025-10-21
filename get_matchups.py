import requests
import json
import os

# --- CONFIGURATION (UPDATE THESE VALUES) ---
LEAGUE_ID = "1189644119835193344"  # <-- IMPORTANT: Replace with your actual League ID
CURRENT_WEEK = 6                   # <-- IMPORTANT: Set this to the current week number (e.g., 5)
OUTPUT_DIR = "ytd_matchups_data"   # Directory to save all weekly files

# --- API URL Template ---
BASE_URL = f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/matchups/"

def fetch_ytd_matchups():
    """Fetches matchup data from Week 1 up to the CURRENT_WEEK."""
    
    if LEAGUE_ID == "YOUR_LEAGUE_ID_HERE":
        print("❌ ERROR: Please update the LEAGUE_ID variable in the script with your actual ID.")
        return

    # 1. Create the output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

    print(f"Starting data pull for League ID {LEAGUE_ID} (Weeks 1 through {CURRENT_WEEK})...")
    
    all_matchups_data = {}

    for week in range(1, CURRENT_WEEK + 1):
        week_url = BASE_URL + str(week)
        output_path = os.path.join(OUTPUT_DIR, f"matchups_week_{week}.json")
        
        print(f"  -> Fetching Week {week} data...")
        
        try:
            # 2. Make the GET request
            response = requests.get(week_url, timeout=30)
            response.raise_for_status() 

            matchup_data = response.json()
            
            # 3. Save the data to its specific weekly file
            with open(output_path, 'w') as f:
                json.dump(matchup_data, f, indent=4)
            
            print(f"     ✅ Week {week} saved to {output_path}")

        except requests.exceptions.RequestException as e:
            print(f"     ❌ Error fetching Week {week}: {e}")
            # Continue to the next week if one fails
            continue 
    
    print("\nData pull complete! All individual weekly files have been saved.")

if __name__ == "__main__":
    fetch_ytd_matchups()