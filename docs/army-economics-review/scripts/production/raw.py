import json
P='/tmp/claude-0/-home-user-aoe2-matchup/c64ba011-deb2-5026-8014-2063b1e15df5/scratchpad/mt/data/local/army-economics/scratch/production-review/current-raw-source.json'
D=json.load(open(P))
E=D['effects']; T=D['techs']; C=D['civs']
def eff(i):
    e=E[str(i)]; return e['name'], e['effect_commands']
