"""Keep pending damage after the last attacker dies in the recorded timeline."""
def terminal_row(rows):
    def totals(row):return tuple(sum(u['hp'] for u in row['sides'][o]) for o in ('2','3'))
    index=next((i for i,r in enumerate(rows) if any(not any(u['hp']>0 for u in r['sides'][o]) for o in ('2','3'))),None)
    if index is None:return rows[-1]
    end=rows[index];previous=totals(end)
    for row in rows[index+1:]:
        current=totals(row)
        if any(now<before-.00001 for now,before in zip(current,previous)):end=row
        previous=current
    return end
