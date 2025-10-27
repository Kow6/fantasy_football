import pandas as pd
import json
import os
from collections import defaultdict

# ====================================================================
# CONFIGURATION
# IMPORTANT: UPDATE PLAYER_DATA_FILE with your exact timestamped name
# ====================================================================
YTD_DATA_DIR = "ytd_matchups_data"
PLAYER_DATA_FILE = "sleeper_players.json" 
ROSTER_MAP_FILE = "roster_name_map.json"
OUTPUT_FILE = "ytd_starter_analysis.csv"

# Positions to track for YTD starters
POSITIONS_OF_INTEREST = ['QB', 'RB', 'WR', 'TE']

# ====================================================================
# DATA LOADING FUNCTIONS
# ====================================================================
def load_data(file_path, data_type):
    """Generic function to load a JSON file with error handling."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ ERROR: {data_type} file not found at {file_path}. Please check the filename or run the corresponding data script.")
        return None
    except Exception as e:
        print(f"❌ ERROR: Failed to load {data_type} data from {file_path}: {e}")
        return None

# ====================================================================
# MAIN ANALYSIS FUNCTION
# ====================================================================
def analyze_ytd_starters():
    """Aggregates starter scores by position for all teams YTD and saves to CSV."""
    
    # 1. Load Required Maps
    player_map = load_data(PLAYER_DATA_FILE, "Player Map")
    roster_name_map = load_data(ROSTER_MAP_FILE, "Roster Name Map")
    if player_map is None or roster_name_map is None:
        return

    # 2. Initialize the master tracking dictionary
    # Structure: {roster_id: {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0}}
    team_totals = defaultdict(lambda: {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0}) 

    # 3. Process all weekly matchup files
    print(f"Processing YTD matchup data from directory: {YTD_DATA_DIR}...")
    
    for filename in os.listdir(YTD_DATA_DIR):
        if filename.endswith('.json'):
            file_path = os.path.join(YTD_DATA_DIR, filename)
            
            try:
                with open(file_path, 'r') as f:
                    matchup_data = json.load(f)
            except Exception as e:
                print(f"     ❌ Error loading {filename}: {e}. Skipping.")
                continue
            
            # Iterate through each team's object in the weekly data
            for team in matchup_data:
                roster_id = str(team.get('roster_id')) # Ensure ID is string for map lookup
                players_scores = team.get('players_points', {})
                starters = team.get('starters', [])

                if not roster_id: continue 

                # Iterate through all starters for this team this week
                for player_id in starters:
                    
                    # Get position from the Player Map
                    player_info = player_map.get(player_id, {})
                    position = player_info.get('position')
                    
                    # Get the score for the week
                    score = players_scores.get(player_id, 0)
                    
                    # Accumulate score if the position is tracked
                    if position in POSITIONS_OF_INTEREST:
                        team_totals[roster_id][position] += score

            
    # 4. Convert results to a Pandas DataFrame
    results_list = []
    for roster_id, data in team_totals.items():
        # Get the Team Name from the map
        team_name = roster_name_map.get(roster_id, f'Roster {roster_id} (Unknown)')
        
        data['Team Name'] = team_name
        data['Roster ID'] = roster_id
        results_list.append(data)
        
    df = pd.DataFrame(results_list)

    # Calculate Total Starter Points
    df['Total Starter Points'] = df[POSITIONS_OF_INTEREST].sum(axis=1)

    # Reorder columns for a clean view
    df = df[['Team Name', 'Roster ID'] + POSITIONS_OF_INTEREST + ['Total Starter Points']]
    
    # 5. Save the final results to CSV
    df.to_csv(OUTPUT_FILE, index=False)

    print("\n✅ Analysis Complete!")
    print(f"Results saved to: {os.path.abspath(OUTPUT_FILE)}")
    



if __name__ == "__main__":
    analyze_ytd_starters()


