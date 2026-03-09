from api.espn_client import ESPNClient

client = ESPNClient()
team = client.connect()
print("Roster:")
for team in client.league.teams:
    print(team.team_id, team.team_name)