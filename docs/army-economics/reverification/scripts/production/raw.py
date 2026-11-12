import json
P='/home/user/aoe2_matchup/data/local/army-economics/scratch/production-review/current-raw-source.json'
D=json.load(open(P))
E=D['effects']; T=D['techs']; C=D['civs']
def eff(i):
    e=E[str(i)]; return e['name'], e['effect_commands']
