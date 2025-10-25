import pandas as pd
import matplotlib.pyplot as plt
import json
import os
from matplotlib.ticker import MaxNLocator
import matplotlib.colors as mcolors

# --- USER-EDITABLE CONFIGURATION ---
# Player data file from Sleeper API (used for position/name mapping)
PLAYER_DATA_FILE = 'sleeper_players_20251013_181714.json'
# Roster data file (used for team name/color mapping)
ROSTER_NAME_MAP_FILE = 'roster_name_map.json'
# Folder containing weekly matchup JSONs
DATA_FOLDER = 'ytd_matchups_data'

# ENTER PLAYER ID HERE (Set to None to disable the featured line)
# Example: 4984 (a QB)
FEATURED_PLAYER_ID = "9488" 

# --- PLOTTING CONFIG ---
TEAM_COLORS = list(mcolors.TABLEAU_COLORS.values()) # 10 distinct colors for league teams


# --- MAP LOADING FUNCTIONS ---

def create_player_maps(file_path):
    """Loads the Sleeper player data and creates Player ID -> Position and Player ID -> Name maps."""
    print(f"Loading player data from {file_path} to create player maps...")
    try:
        with open(file_path, 'r') as f:
            player_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"\nFATAL ERROR loading player data: {e}")
        return None, None
        
    position_map = {}
    name_map = {}
    
    for player_id, details in player_data.items():
        position = details.get('position')
        full_name = details.get('full_name')

        if position:
            position_map[player_id] = position
        if full_name:
            name_map[player_id] = full_name
            
    print(f"Successfully mapped data for {len(position_map)} players.")
    return position_map, name_map


def load_roster_map(file_path):
    """Loads the Roster ID -> Owner/Team Name mapping."""
    print(f"Loading roster data from {file_path}...")
    try:
        with open(file_path, 'r') as f:
            return {str(k): v for k, v in json.load(f).items()} # Ensure keys are strings
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"\nFATAL ERROR loading roster map: {e}")
        return None


# --- Part 1: Data Loading and Benchmark Calculation ---

def get_benchmark_scores(series):
    """Calculates the points of the 6th and 18th highest-scoring players."""
    sorted_scores = series.sort_values(ascending=False).reset_index(drop=True)
    sixth_highest = sorted_scores.get(5, float('nan'))
    eighteenth_highest = sorted_scores.get(17, float('nan'))
    return sixth_highest, eighteenth_highest


def prepare_positional_data(position_map, name_map, roster_map, data_folder=DATA_FOLDER):
    """Processes weekly Sleeper JSONs to extract all starter data."""
    print("\nStarting weekly matchup data processing...")
    all_starter_data = []

    if not os.path.exists(data_folder):
        print(f"FATAL ERROR: Matchup data folder '{data_folder}' was not found.")
        return pd.DataFrame()

    for filename in os.listdir(data_folder):
        if filename.startswith("matchups_week_") and filename.endswith(".json"):
            file_path = os.path.join(data_folder, filename)
            
            try:
                week = int(filename.split('_')[2].split('.')[0]) 
            except (IndexError, ValueError):
                continue
                
            with open(file_path, 'r') as f:
                week_data = json.load(f)
            
            if not isinstance(week_data, list):
                continue

            for box_score in week_data:
                roster_id = str(box_score.get('roster_id'))
                starter_ids = set(box_score.get('starters', []))
                player_points_map = box_score.get('players_points', {}) 

                if not starter_ids or not player_points_map:
                    continue 

                for player_id in starter_ids:
                    points = player_points_map.get(player_id)
                    position = position_map.get(player_id, 'UNK')
                    full_name = name_map.get(player_id, 'Unknown Player')
                    team_name = roster_map.get(roster_id, f"Roster {roster_id}") 

                    if points is not None and position in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
                        starter_record = {
                            'Week': week,
                            'Player_ID': player_id, 
                            'Player_Name': full_name,
                            'Position': position, 
                            'Points': points,
                            'Roster_ID': roster_id,
                            'Team_Name': team_name,
                        }
                        all_starter_data.append(starter_record)

    if not all_starter_data:
        print("ERROR: No starter data successfully loaded. Check your JSON file contents.")
        return pd.DataFrame()

    df_starters = pd.DataFrame(all_starter_data)
    df_starters['Position'] = df_starters['Position'].replace({'DEF': 'D/ST'})
    
    # --- Calculate Benchmarks ---
    benchmark_df = (
        df_starters
        .groupby(['Week', 'Position'])['Points']
        .apply(lambda x: pd.Series(get_benchmark_scores(x), 
                                   index=['6th_Highest_Points', '18th_Highest_Points']))
        .unstack()
        .reset_index()
    )

    # Merge the benchmarks back into the main DataFrame
    df_final = pd.merge(df_starters, benchmark_df, on=['Week', 'Position'], how='left')
    
    print(f"Data prepared successfully for {len(df_final['Week'].unique())} weeks.")
    return df_final


# --- Part 2: Visualization (Updated for lines and font size) ---

def generate_positional_charts(df_final):
    """Generates and saves the scatter plots with cutoff lines, colored by team, with annotations."""
    if df_final.empty:
        print("No data to plot. Exiting.")
        return
        
    plot_dir = './positional_plots_annotated'
    if not os.path.exists(plot_dir):
        os.makedirs(plot_dir)
        print(f"Created output directory: {plot_dir}")

    chart_positions = sorted(df_final['Position'].unique())
    
    unique_rosters = sorted(df_final['Roster_ID'].unique())
    roster_color_map = {
        roster_id: TEAM_COLORS[i % len(TEAM_COLORS)] 
        for i, roster_id in enumerate(unique_rosters)
    }
    
    print(f"Generating charts for positions: {', '.join(chart_positions)}")

    for pos in chart_positions:
        pos_df = df_final[df_final['Position'] == pos].copy()
        
        if len(pos_df) < 18:
             print(f"Skipping {pos}: Insufficient data ({len(pos_df)} total points).")
             continue
        
        benchmarks = pos_df.drop_duplicates(subset=['Week']).sort_values(by='Week')
        
        fig, ax = plt.subplots(figsize=(14, 8))

        # --- SCATTER PLOT (Individual Starters, colored by team) ---
        grouped_teams = pos_df.groupby('Roster_ID')
        
        for roster_id, group in grouped_teams:
            team_name = group['Team_Name'].iloc[0]
            team_color = roster_color_map[roster_id]
            
            # Plot the points for this team
            ax.scatter(
                group['Week'], 
                group['Points'], 
                label=team_name, 
                alpha=0.7, 
                color=team_color, 
                s=50,
                zorder=10
            )

            # Add player name annotations (smaller font size: 6)
            for i in group.index:
                player_name_abbr = group['Player_Name'][i].split(' ')[-1]
                
                ax.annotate(
                    player_name_abbr, 
                    (group['Week'][i], group['Points'][i]), 
                    textcoords="offset points", 
                    xytext=(5, 5), 
                    ha='left', 
                    fontsize=6, 
                    color=team_color
                )

        # --- BENCHMARK LINES ---
        ax.plot(
            benchmarks['Week'], 
            benchmarks['6th_Highest_Points'], 
            label='Top 6 Cutoff (Low-end Starter)', 
            color='forestgreen', 
            # Changed from '-' to ':' (dotted)
            linestyle=':', 
            linewidth=2,
            zorder=5
        )
        
        ax.plot(
            benchmarks['Week'], 
            benchmarks['18th_Highest_Points'], 
            label='Top 18 Cutoff (Flex/Bench)', 
            color='darkorange', 
            linestyle='--',
            linewidth=2,
            zorder=5
        )
        
        # --- FEATURED PLAYER LINE ---
        if FEATURED_PLAYER_ID is not None:
            featured_player_df = pos_df[pos_df['Player_ID'] == FEATURED_PLAYER_ID].sort_values(by='Week')

            if not featured_player_df.empty:
                # Use the player's full name for the legend
                player_name = featured_player_df['Player_Name'].iloc[0]
                
                ax.plot(
                    featured_player_df['Week'],
                    featured_player_df['Points'],
                    label=f'Featured Player: {player_name}',
                    color='red',
                    linestyle='-',
                    linewidth=3,
                    zorder=15 # Ensure this line is on top
                )


        # --- Customizations ---
        ax.set_title(f'Weekly Points Dispersion: {pos}', fontsize=16, fontweight='bold')
        ax.set_xlabel('Week', fontsize=12)
        ax.set_ylabel('Points Scored', fontsize=12)
        
        if not benchmarks['Week'].empty:
            max_week = int(benchmarks['Week'].max())
            ax.set_xticks(range(1, max_week + 1)) 
            ax.set_xlim(left=0.5, right=max_week + 0.5)
        
        ax.yaxis.set_major_locator(MaxNLocator(integer=True)) 

        ax.legend(title="Fantasy Team", bbox_to_anchor=(1.05, 1), loc='upper left', frameon=True)
        ax.grid(True, axis='y', linestyle=':', alpha=0.6)
        
        plt.tight_layout(rect=[0, 0, 0.85, 1])
        
        # Save the chart
        file_name = f'{pos}_Weekly_Score_Comparison_Annotated.png'
        plt.savefig(os.path.join(plot_dir, file_name))
        plt.close(fig)

    print(f"\n✅ Success! All positional charts have been saved to the '{plot_dir}' folder.")


# --- Main Execution Block ---
if __name__ == "__main__":
    
    # 1. Load Maps
    position_map, name_map = create_player_maps(PLAYER_DATA_FILE)
    roster_map = load_roster_map(ROSTER_NAME_MAP_FILE)
    
    if position_map is not None and name_map is not None and roster_map is not None:
        # 2. Prepare Data
        final_df = prepare_positional_data(position_map, name_map, roster_map)
        
        # 3. Generate Charts
        if not final_df.empty:
            generate_positional_charts(final_df)
        else:
            print("Analysis completed, but final DataFrame is empty. No charts generated.")
    else:
        print("\nFix map file errors (player data or roster map) before running the script.")