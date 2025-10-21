import requests
import json
import os

# --- CONFIGURATION (UPDATE THIS) ---
LEAGUE_ID = "1189644119835193344"  # <-- IMPORTANT: Replace with your actual League ID

# --- API URLs ---
ROSTERS_API_URL = f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/rosters"
USERS_API_URL = f"https://api.sleeper.app/v1/league/{LEAGUE_ID}/users"

# --- Output File ---
MAP_OUTPUT_FILE = "roster_name_map.json"

def fetch_roster_user_map():
    """Fetches league rosters and users to create a Roster ID to Team Name mapping."""
    if LEAGUE_ID == "YOUR_LEAGUE_ID_HERE":
        print("❌ ERROR: Please update the LEAGUE_ID variable in the script with your actual ID.")
        return None

    print("Fetching league roster and user data...")

    try:
        # 1. Fetch Rosters (Roster ID -> Owner ID)
        rosters_response = requests.get(ROSTERS_API_URL, timeout=15)
        rosters_response.raise_for_status() 
        rosters_data = rosters_response.json()

        # 2. Fetch Users (Owner ID -> Team Name)
        users_response = requests.get(USERS_API_URL, timeout=15)
        users_response.raise_for_status()
        users_data = users_response.json()

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching league data: {e}")
        return None

    # --- 3. Build the User Name Map (Owner ID -> Name) ---
    user_name_map = {}
    for user in users_data:
        # Sleeper users can set a custom team name in metadata, otherwise use display_name
        team_name = user.get('metadata', {}).get('team_name') or user.get('display_name')
        user_name_map[user['user_id']] = team_name

    # --- 4. Build the Roster ID Map (Roster ID -> Team Name) ---
    roster_name_map = {}
    for roster in rosters_data:
        roster_id = roster['roster_id']
        owner_id = roster.get('owner_id')
        
        # Match the Roster ID to the User's team name
        if owner_id and owner_id in user_name_map:
            roster_name_map[str(roster_id)] = user_name_map[owner_id]
        else:
            roster_name_map[str(roster_id)] = f"Roster {roster_id} (No Owner)"

    # 5. Save the final map to a JSON file
    with open(MAP_OUTPUT_FILE, 'w') as f:
        json.dump(roster_name_map, f, indent=4)

    print(f"✅ Success! Roster map saved to: {os.path.abspath(MAP_OUTPUT_FILE)}")
    
    return roster_name_map

if __name__ == "__main__":
    fetch_roster_user_map()