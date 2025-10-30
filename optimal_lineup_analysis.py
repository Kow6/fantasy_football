import pandas as pd
import json
import os
import numpy as np

# --- FILE CONFIGURATION ---
PLAYER_DATA_FILE = 'sleeper_players.json'
ROSTER_NAME_MAP_FILE = 'roster_name_map.json'
DATA_FOLDER = 'ytd_matchups_data'
OUTPUT_CSV_FILE = 'optimal_lineup_analysis.csv'

# --- STARTER SLOT DEFINITION ---
STARTER_SLOTS = {
    'QB': 1,
    'RB': 2,
    'WR': 3,
    'TE': 1,
    'FLEX': 2,
    'SUPERFLEX': 1
}
FLEX_ELIGIBLE = ['RB', 'WR', 'TE']
SF_ELIGIBLE = ['QB', 'RB', 'WR', 'TE']

# Define a minimum threshold for a "playing" week score (used for bye/inactivity filtering)
MIN_PLAYING_SCORE = 0.1 

# --- MAP LOADING FUNCTIONS ---

def load_maps():
    """Loads player data and roster data to create necessary maps, excluding IR players."""
    
    print(f"Loading player data from {PLAYER_DATA_FILE}...")
    try:
        with open(PLAYER_DATA_FILE, 'r') as f:
            player_data = json.load(f)
    except Exception as e:
        print(f"FATAL ERROR loading {PLAYER_DATA_FILE}: {e}")
        return None, None, None
        
    position_map = {}
    name_map = {}
    
    for p_id, details in player_data.items():
        position = details.get('position')
        full_name = details.get('full_name')
        injury_status = details.get('injury_status')
        
        # --- EXCLUSION CHECK 1: Injury Reserve (IR) ---
        if injury_status == "IR":
            continue

        if position and full_name:
            position_map[p_id] = position.replace('DEF', 'D/ST') # Standardize DEF
            name_map[p_id] = full_name
    
    print(f"Loaded player data for {len(position_map)} players (excluding IR).")

    # 2. Load Roster Map (ID to Team Name)
    # --- FIX APPLIED HERE: Changed ROSTER_NAME_MAP_MAP_FILE to ROSTER_NAME_MAP_FILE ---
    print(f"Loading roster map from {ROSTER_NAME_MAP_FILE}...")
    try:
        with open(ROSTER_NAME_MAP_FILE, 'r') as f:
            roster_map = {str(k): v for k, v in json.load(f).items()}
    except Exception as e:
        print(f"FATAL ERROR loading {ROSTER_NAME_MAP_FILE}: {e}")
        return None, None, None
        
    return position_map, name_map, roster_map


# --- DATA PROCESSING FUNCTION ---

def process_matchup_data(position_map, name_map, roster_map, data_folder=DATA_FOLDER):
    """
    Processes all weekly matchup data to find every player's score, filters out 0.0 scores,
    and then calculates median and ownership.
    """
    print(f"\nProcessing matchup data from {data_folder}...")
    all_player_scores = []
    player_scores_by_week = {} # {player_id: [(week, score), ...]}
    player_to_roster = {} 
    
    ELIGIBLE_POSITIONS = ['QB', 'RB', 'WR', 'TE']

    if not os.path.exists(data_folder):
        print(f"FATAL ERROR: Matchup data folder '{data_folder}' was not found.")
        return None

    for filename in os.listdir(data_folder):
        if filename.startswith("matchups_week_") and filename.endswith(".json"):
            file_path = os.path.join(data_folder, filename)
            
            try:
                with open(file_path, 'r') as f:
                    week_data = json.load(f)
            except Exception as e:
                print(f"Error loading {filename}: {e}")
                continue
            
            if not isinstance(week_data, list): continue

            # Determine the current week number from the filename
            try:
                week_num = int(filename.split('_')[2].split('.')[0])
            except:
                week_num = 0

            for box_score in week_data:
                roster_id = str(box_score.get('roster_id'))
                players = box_score.get('players', [])
                player_points_map = box_score.get('players_points', {}) 

                if not players or not player_points_map: continue

                for player_id in players:
                    position = position_map.get(player_id)
                    
                    if position in ELIGIBLE_POSITIONS:
                        points = player_points_map.get(player_id)
                        
                        # --- Store ALL scores for the last 2 week check ---
                        if player_id not in player_scores_by_week:
                            player_scores_by_week[player_id] = []
                        if points is not None:
                            player_scores_by_week[player_id].append({'week': week_num, 'points': points})
                        
                        # --- Only record non-zero scores for median calculation ---
                        if points is not None and points >= MIN_PLAYING_SCORE:
                            all_player_scores.append([player_id, points])
                        
                        # Update ownership to the latest roster seen
                        player_to_roster[player_id] = roster_id

    if not all_player_scores:
        print("ERROR: No non-zero player scores successfully loaded. Check data consistency.")
        return None

    df_scores = pd.DataFrame(all_player_scores, columns=['Player_ID', 'Points'])
    
    # Calculate median points for each player
    df_median = df_scores.groupby('Player_ID')['Points'].median().reset_index()
    df_median.rename(columns={'Points': 'Median_Points'}, inplace=True)
    
    # --- EXCLUSION CHECK 2: Last 2 Consecutive Zeros ---
    players_to_exclude = set()
    latest_week = max(s['week'] for scores in player_scores_by_week.values() for s in scores) if player_scores_by_week else 0
    
    for player_id, scores in player_scores_by_week.items():
        # Filter scores to only include the last two weeks present in the data
        sorted_scores = sorted([s for s in scores if s['week'] >= latest_week - 1], key=lambda x: x['week'], reverse=True)
        
        # Check if the player has at least two weeks of data (or equivalent coverage)
        if len(sorted_scores) >= 2:
            last_score = sorted_scores[0]['points']
            second_last_score = sorted_scores[1]['points']
            
            # Check for two consecutive scores less than MIN_PLAYING_SCORE (i.e., two zeros/near-zeros)
            if last_score < MIN_PLAYING_SCORE and second_last_score < MIN_PLAYING_SCORE:
                players_to_exclude.add(player_id)

    # Filter out players with consecutive zeros
    df_median = df_median[~df_median['Player_ID'].isin(players_to_exclude)].copy()
    print(f"Excluded {len(players_to_exclude)} players with consecutive zero scores.")

    # Merge with maps
    df_median['Position'] = df_median['Player_ID'].map(position_map)
    df_median['Player_Name'] = df_median['Player_ID'].map(name_map)
    df_median['Roster_ID'] = df_median['Player_ID'].map(player_to_roster)
    
    # Final cleanup and sort
    df_median = df_median.dropna(subset=['Position', 'Roster_ID'])
    df_median = df_median[df_median['Position'].isin(ELIGIBLE_POSITIONS)]
    df_median.sort_values(by=['Roster_ID', 'Median_Points'], ascending=[True, False], inplace=True)
    
    return df_median


# --- OPTIMAL LINEUP SELECTION ---

def select_optimal_lineup(df_median):
    """
    Selects the optimal lineup and returns all remaining non-starter players for backup analysis.
    """
    
    optimal_lineup_data = []
    remaining_players = []
    
    MANDATORY_SLOTS = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1}

    for roster_id, team_df in df_median.groupby('Roster_ID'):
        
        selected_ids = set()
        available_pool = team_df.copy()
        
        # 1. Select Mandatory Positions (QB, RB, WR, TE)
        for pos, count in MANDATORY_SLOTS.items():
            pos_players = available_pool[available_pool['Position'] == pos].head(count)
            
            for index, player in pos_players.iterrows():
                optimal_lineup_data.append({
                    'Roster_ID': roster_id,
                    'Position': pos,
                    'Player_Name': player['Player_Name'],
                    'Median_Points': player['Median_Points']
                })
                selected_ids.add(player['Player_ID'])

        # Update the available pool by removing mandatory selections
        available_pool = available_pool[~available_pool['Player_ID'].isin(selected_ids)]

        # 2. Select FLEX (2 spots: RB/WR/TE)
        flex_pool = available_pool[available_pool['Position'].isin(FLEX_ELIGIBLE)].head(STARTER_SLOTS['FLEX'])
        
        for index, player in flex_pool.iterrows():
            optimal_lineup_data.append({
                'Roster_ID': roster_id,
                'Position': 'FLEX',
                'Player_Name': player['Player_Name'],
                'Median_Points': player['Median_Points']
            })
            selected_ids.add(player['Player_ID'])

        # Update the available pool by removing FLEX selections
        available_pool = available_pool[~available_pool['Player_ID'].isin(selected_ids)]
        
        # 3. Select SUPERFLEX (1 spot: best remaining QB/RB/WR/TE)
        sf_pool = available_pool[available_pool['Position'].isin(SF_ELIGIBLE)].head(STARTER_SLOTS['SUPERFLEX'])

        for index, player in sf_pool.iterrows():
            optimal_lineup_data.append({
                'Roster_ID': roster_id,
                'Position': 'SUPERFLEX',
                'Player_Name': player['Player_Name'],
                'Median_Points': player['Median_Points']
            })
            selected_ids.add(player['Player_ID'])

        # 4. Collect Remaining Players (for backup analysis)
        remaining_df = available_pool[~available_pool['Player_ID'].isin(selected_ids)].copy()
        
        for index, player in remaining_df.iterrows():
             remaining_players.append({
                'Roster_ID': roster_id,
                'Position': player['Position'],
                'Player_Name': player['Player_Name'],
                'Median_Points': player['Median_Points']
            })

    return pd.DataFrame(optimal_lineup_data), pd.DataFrame(remaining_players)


# --- OUTPUT FORMATTING ---

def format_output_csv(df_optimal, df_remaining, roster_map):
    """
    Formats the DataFrame with optimal lineup, total score, and top backups, 
    then outputs to CSV.
    """
    
    final_output = []
    category_order = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'SUPERFLEX']
    backup_positions = ['QB', 'RB', 'WR', 'TE']
    
    sorted_roster_ids = sorted(df_optimal['Roster_ID'].unique(), key=int)
    
    for roster_id in sorted_roster_ids:
        team_name = roster_map.get(roster_id, f"Roster {roster_id}")

        # --- 1. Detail Rows (Optimal Lineup) ---
        team_df = df_optimal[df_optimal['Roster_ID'] == roster_id].copy()
        team_df['Team Name'] = team_name
        
        detail_rows = team_df[['Team Name', 'Position', 'Player_Name', 'Median_Points']].copy()
        detail_rows.rename(columns={'Player_Name': 'Player Name', 'Median_Points': 'Median Points'}, inplace=True)
        
        detail_rows['Position_Category'] = pd.Categorical(detail_rows['Position'], categories=category_order, ordered=True)
        detail_rows = detail_rows.sort_values(by=['Position_Category', 'Median Points'], ascending=[True, False])
        detail_rows['Slot_Index'] = detail_rows.groupby('Position_Category', observed=True).cumcount()
        detail_rows = detail_rows.sort_values(by=['Position_Category', 'Slot_Index']).drop(columns=['Position_Category', 'Slot_Index'])
        
        final_output.append(detail_rows)
        
        # --- 2. Summary Row (Total) ---
        total_median = team_df['Median_Points'].sum()
        summary_row = pd.DataFrame([{
            'Team Name': team_name,
            'Position': 'TOTAL',
            'Player Name': '',
            'Median Points': total_median
        }])
        final_output.append(summary_row)

        # --- 3. Backup Rows ---
        backup_df = df_remaining[df_remaining['Roster_ID'] == roster_id].copy()
        
        if not backup_df.empty:
            for pos in backup_positions:
                # Find the best remaining player for this position
                top_backup = backup_df[backup_df['Position'] == pos].head(1)
                
                if not top_backup.empty:
                    backup_data = top_backup.iloc[0]
                    
                    backup_row = pd.DataFrame([{
                        'Team Name': team_name,
                        'Position': f'BACKUP {pos}',
                        'Player Name': backup_data['Player_Name'],
                        'Median Points': backup_data['Median_Points']
                    }])
                    final_output.append(backup_row)
            
            # Add an empty row for separation
            final_output.append(pd.DataFrame([{'Team Name': team_name, 'Position': np.nan, 'Player Name': np.nan, 'Median Points': np.nan}]))


    df_final_output = pd.concat(final_output, ignore_index=True)
    
    # Output to CSV
    df_final_output.to_csv(OUTPUT_CSV_FILE, index=False)
    
    print(f"\n✅ Success! Optimal lineups and backups saved to {OUTPUT_CSV_FILE}")
    print("The CSV includes columns: Team Name, Position, Player Name, Median Points, with TOTAL and BACKUP rows.")
    
    try:
        # Use a slice to show the beginning of two different teams, including totals and backups
        # Find the index of the first 'TOTAL' row + 5 more rows (4 backups + 1 NaN spacer)
        total_rows = df_final_output[df_final_output['Position'].str.contains('TOTAL', na=False)]
        first_team_end_index = total_rows.index[0] + 6 if not total_rows.empty else 20
        
        preview_data = df_final_output.head(first_team_end_index)
        
        return preview_data.to_markdown(index=False, floatfmt=".2f")
    except ImportError:
        print("\nNOTE: Could not display table preview in terminal. Please install 'tabulate' for previews: pip install tabulate")
        return None 


# --- MAIN EXECUTION ---

if __name__ == '__main__':
    position_map, name_map, roster_map = load_maps()
    
    if position_map is None or name_map is None or roster_map is None:
        print("\nScript failed due to missing files or data loading errors.")
    else:
        df_median_scores = process_matchup_data(position_map, name_map, roster_map)
        
        if df_median_scores is not None and not df_median_scores.empty:
            df_optimal_lineup, df_remaining_players = select_optimal_lineup(df_median_scores)
            
            if not df_optimal_lineup.empty:
                preview = format_output_csv(df_optimal_lineup, df_remaining_players, roster_map)
                if preview:
                    print("\n--- PREVIEW OF OPTIMAL LINEUP CSV (IR & Inactive Filtered) ---")
                    print(preview)
            else:
                print("\nError: Could not determine any optimal lineups.")
        else:
            print("\nError: Failed to calculate median scores. Check data consistency.")