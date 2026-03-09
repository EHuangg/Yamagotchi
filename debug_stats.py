from api.espn_client import ESPNClient

client = ESPNClient()
team = client.connect()

for player in team.roster[:3]:  # just first 3 players
    print(f"\n--- {player.name} ---")
    print(f"  stats keys: {list(player.stats.keys()) if player.stats else 'EMPTY'}")
    print(f"  stats: {player.stats}")
    print(f"  projected_avg_points: {getattr(player, 'projected_avg_points', 'N/A')}")
    print(f"  projected_total_points: {getattr(player, 'projected_total_points', 'N/A')}")
    print(f"  total_points: {getattr(player, 'total_points', 'N/A')}")