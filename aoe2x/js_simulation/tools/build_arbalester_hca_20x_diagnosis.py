"""Build the traceable 20-live-vs-20-simulation Arbalester/HCA diagnosis.

The artifact is deliberately diagnostic.  It compares outcome distributions
and reusable mechanics, but never emits runtime calibration parameters.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import argparse
import html
import json
import math
from pathlib import Path
import statistics
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIVE = (
    ROOT / "calibration" / "live_observations"
    / "arbalester_hca_20x_2026-08-30" / "grpc_20x_analysis.json"
)
DEFAULT_SIM = (
    ROOT / "calibration" / "reports"
    / "arbalester_hca_20x_2026-08-30" / "results.json"
)
DEFAULT_SIM_PARTICIPATION = (
    ROOT / "calibration" / "reports"
    / "arbalester_hca_20x_2026-08-30"
    / "simulation_seed4_participation.json"
)
DEFAULT_OUTPUT = (
    ROOT / "calibration" / "reports"
    / "arbalester_hca_20x_diagnosis_2026-08-30"
)
VIEWER_URL = (
    "https://starlight.tail82a190.ts.net/golden-map/"
    "?mode=problem-matchups&matchup=arbalester_vs_heavy_cav_archer&seed=4"
)


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def rounded(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def summary(values: list[float]) -> dict:
    return {
        "n": len(values),
        "mean": rounded(mean(values)),
        "median": rounded(median(values)),
        "min": rounded(min(values)) if values else None,
        "max": rounded(max(values)) if values else None,
    }


def wilson(successes: int, trials: int, z: float = 1.959963984540054) -> list[float]:
    if not trials:
        return [0.0, 0.0]
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    spread = (
        z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
        / denominator
    )
    return [round(max(0.0, center - spread), 4), round(min(1.0, center + spread), 4)]


def average_dict(rows: list[dict], fields: list[str]) -> dict:
    return {
        field: rounded(mean([float(row[field]) for row in rows if row.get(field) is not None]), 4)
        for field in fields
    }


def live_window_by_winner(participation: list[dict]) -> dict:
    output = {}
    fields = [
        "meanAlive", "meanActive", "meanFiring", "meanNotFiring",
        "meanInRangeNotFiring", "meanSeekingMoving", "meanSeekingStationary",
        "meanUntargetedStationary", "shotStarts", "damageHits",
    ]
    for winner in ("arbalester", "heavy_cav_archer"):
        winner_runs = [row for row in participation if row["winner"] == winner]
        output[winner] = {"runs": len(winner_runs), "windows": {}}
        for seconds in (5, 10, 20):
            key = f"window_{seconds}s"
            output[winner]["windows"][str(seconds)] = {
                owner: average_dict([row[key][owner] for row in winner_runs], fields)
                for owner in ("2", "3")
            }
    return output


def unit_timing_by_winner(live_runs: list[dict]) -> dict:
    grouped: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for run in live_runs:
        frames_path = Path(run["frames_bin"])
        decoded = frames_path.parents[1] / "grpc_opening_variance.json"
        payload = json.loads(decoded.read_text(encoding="utf-8"))
        for unit in payload["units"]:
            grouped[run["winner"]][int(unit["owner"])].append(unit)

    fields = [
        "first_target_t", "first_attack_state_t", "first_damage_dealt_t",
        "path_before_first_damage_dealt", "path_total",
    ]
    output = {}
    for winner, owner_rows in grouped.items():
        output[winner] = {}
        for owner, rows in owner_rows.items():
            output[winner][str(owner)] = {
                "units": len(rows),
                "damage_dealer_share": rounded(
                    sum(row.get("first_damage_dealt_t") is not None for row in rows)
                    / max(1, len(rows)), 4,
                ),
                **{
                    field: summary([
                        float(row[field]) for row in rows if row.get(field) is not None
                    ])
                    for field in fields
                },
            }
    return output


def live_outcomes(runs: list[dict]) -> dict:
    winners = {
        winner: [row for row in runs if row["winner"] == winner]
        for winner in ("arbalester", "heavy_cav_archer")
    }
    scores = []
    for row in runs:
        initial_hp = 1080 if row["winner"] == "arbalester" else 1440
        direction = -1 if row["winner"] == "arbalester" else 1
        scores.append(direction * float(row["winner_hp"]) / initial_hp * 100)
    return {
        "runs": len(runs),
        "arbalester_wins": len(winners["arbalester"]),
        "heavy_cav_archer_wins": len(winners["heavy_cav_archer"]),
        "arbalester_win_rate": rounded(len(winners["arbalester"]) / len(runs), 4),
        "arbalester_win_rate_wilson_95": wilson(len(winners["arbalester"]), len(runs)),
        "signed_score": summary(scores),
        "by_winner": {
            winner: {
                "runs": len(rows),
                "winner_hp": summary([float(row["winner_hp"]) for row in rows]),
                "survivors": summary([float(row["survivors"]) for row in rows]),
                "elimination_seconds": summary([
                    float(row["grpc_elimination_game_seconds"]) for row in rows
                ]),
            }
            for winner, rows in winners.items()
        },
    }


def sim_outcomes(simulation: dict) -> dict:
    runs = simulation["runs"]
    arb_wins = [row for row in runs if int(row["winnerOwner"]) == 2]
    hca_wins = [row for row in runs if int(row["winnerOwner"]) == 3]
    return {
        "runs": len(runs),
        "arbalester_wins": len(arb_wins),
        "heavy_cav_archer_wins": len(hca_wins),
        "arbalester_win_rate": rounded(len(arb_wins) / len(runs), 4),
        "arbalester_win_rate_wilson_95": wilson(len(arb_wins), len(runs)),
        "signed_score": summary([float(row["score"]) for row in runs]),
        "by_winner": {
            "arbalester": {
                "runs": len(arb_wins),
                "winner_hp": summary([float(row["winnerHp"]) for row in arb_wins]),
                "elimination_seconds": summary([float(row["ticks"]) / 60 for row in arb_wins]),
                "seeds": [int(row["openingSeed"]) for row in arb_wins],
            },
            "heavy_cav_archer": {
                "runs": len(hca_wins),
                "winner_hp": summary([float(row["winnerHp"]) for row in hca_wins]),
                "elimination_seconds": summary([float(row["ticks"]) / 60 for row in hca_wins]),
                "seeds": [int(row["openingSeed"]) for row in hca_wins],
            },
        },
    }


def opening_mechanics(live_runs: list[dict], sim_runs: list[dict]) -> dict:
    live = {}
    for owner in (2, 3):
        side = f"side{owner}"
        live[str(owner)] = {
            "unique_first_targets": summary([
                float(row["acquisition"][side]["unique_first_targets"])
                for row in live_runs
            ]),
            "maximum_shared_first_target": summary([
                float(row["acquisition"][side]["maximum_units_sharing_first_target"])
                for row in live_runs
            ]),
            "opening_hits": summary([
                float(row["first_two_game_seconds"]["hits_by_side"].get(str(owner), 0))
                for row in live_runs
            ]),
        }
    sim = {}
    for owner in (2, 3):
        rows = [row["mechanics"]["openingByOwner"][str(owner)] for row in sim_runs]
        first_targets = [
            row["mechanics"]["firstTargetDistributionByOwner"][str(owner)]["targets"]
            for row in sim_runs
        ]
        sim[str(owner)] = {
            "unique_first_targets": summary([float(len(row)) for row in first_targets]),
            "maximum_shared_first_target": summary([
                float(max(row.values(), default=0)) for row in first_targets
            ]),
            "opening_hits": summary([float(row["hits"]) for row in rows]),
        }
    return {"live": live, "simulation": sim}


def pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def number(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=ROOT.parents[1], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def render_html(report: dict) -> str:
    live = report["outcomes"]["live"]
    sim = report["outcomes"]["simulation"]
    comparison = report["outcome_comparison"]
    windows = report["live_winner_separation"]["participation"]
    timings = report["live_winner_separation"]["unit_timing"]
    live_arb = windows["arbalester"]["windows"]
    live_hca = windows["heavy_cav_archer"]["windows"]
    opening = report["opening_mechanics"]
    rate_gap = abs(live["arbalester_win_rate"] - sim["arbalester_win_rate"])
    hca_active_delta = (
        live_hca["20"]["3"]["meanActive"] - live_arb["20"]["3"]["meanActive"]
    )
    hca_hit_delta = (
        live_hca["20"]["3"]["damageHits"] - live_arb["20"]["3"]["damageHits"]
    )
    run_rows = "".join(
        "<tr>"
        f"<td>{row['repeat']}</td>"
        f"<td>{'Arbalester' if row['winner'] == 'arbalester' else 'HCA'}</td>"
        f"<td>{number(row['winner_hp'], 0)}</td>"
        f"<td>{number(row['survivors'], 0)}</td>"
        f"<td><code>{html.escape(row['frames_bin'])}</code></td>"
        "</tr>"
        for row in report["live_runs"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Arbalester vs HCA — 20× diagnosis</title>
<style>
:root{{--bg:#0c1016;--panel:#151b24;--soft:#202938;--text:#edf3fa;--muted:#aab7c8;--blue:#57a6ff;--red:#ff706b;--green:#64d890;--line:#344155}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}}main{{max-width:1080px;margin:auto;padding:28px 18px 64px}}h1{{font-size:clamp(27px,5vw,43px);line-height:1.08;margin:.2rem 0 .8rem}}h2{{margin:2rem 0 .7rem;font-size:21px}}p{{max-width:850px}}.eyebrow,.muted{{color:var(--muted)}}.eyebrow{{text-transform:uppercase;letter-spacing:.11em;font-size:12px}}.lead{{font-size:18px;color:#d9e5f3}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:22px 0}}.card,section{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:17px}}.value{{font-size:30px;font-weight:750;line-height:1.1;margin:.2rem 0}}.arb{{color:var(--blue)}}.hca{{color:var(--red)}}.good{{color:var(--green)}}ul{{padding-left:1.2rem}}li+li{{margin-top:.55rem}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{color:var(--muted);font-weight:600}}code{{font:11px/1.35 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere;color:#ced9e6}}a{{color:#7ebcff}}.scroll{{overflow:auto}}details{{margin-top:1rem}}summary{{cursor:pointer;color:#dbe8f7}}.callout{{border-left:4px solid var(--green)}}
</style></head><body><main>
<div class="eyebrow">Golden ranged-vs-ranged · 27 Chinese Arbalesters vs 18 Saracen HCA</div>
<h1>The live game genuinely flips this matchup</h1>
<p class="lead">The earlier 5–0 HCA sample was not the underlying rule. Across 20 new, exact-scenario captures, both armies win. The current simulator is in the same mixed-winner regime and lies inside the live sample’s broad uncertainty. The remaining discrepancy is behavioral: its opening engages too many Arbalesters and spreads their first targets too broadly.</p>
<div class="cards">
 <div class="card"><div class="muted">Live game</div><div class="value"><span class="arb">{live['arbalester_wins']} Arb</span> / <span class="hca">{live['heavy_cav_archer_wins']} HCA</span></div><div>Arbalester win rate {pct(live['arbalester_win_rate'])}; 95% interval {pct(live['arbalester_win_rate_wilson_95'][0])}–{pct(live['arbalester_win_rate_wilson_95'][1])}.</div></div>
 <div class="card"><div class="muted">Current simulator, seeds 0–19</div><div class="value"><span class="arb">{sim['arbalester_wins']} Arb</span> / <span class="hca">{sim['heavy_cav_archer_wins']} HCA</span></div><div>Arbalester win rate {pct(sim['arbalester_win_rate'])}; rate gap {rate_gap * 100:.0f} points.</div></div>
 <div class="card"><div class="muted">Checkpoint engine</div><div class="value good">{html.escape(report['engine_commit'])}</div><div>Locally committed before this diagnostic; nothing pushed.</div></div>
</div>
<section class="callout"><h2>What actually decides the live run</h2>
<ul>
 <li>The first five seconds do <strong>not</strong> separate the winners: both outcome groups have essentially the same opening target concentration and early hit volume.</li>
 <li>The separation appears during firing-lane turnover, roughly seconds 10–20. HCA-winning captures average <strong>{number(hca_active_delta)} more active HCA</strong> and <strong>{number(hca_hit_delta)} more HCA damage hits</strong> over the first 20 seconds than Arbalester-winning captures.</li>
 <li>The rear HCA are delayed rather than permanently idle: <strong>{pct(timings['arbalester']['3']['damage_dealer_share'])}</strong> eventually deal damage in Arbalester-winning runs and <strong>{pct(timings['heavy_cav_archer']['3']['damage_dealer_share'])}</strong> do so in HCA-winning runs.</li>
 <li>This is a cascade, not a hard seed rule: one or two HCA acquire usable lanes earlier, preserve an extra shooter through the middle exchange, and the count/HP lead compounds. Initial target choice alone does not predict the winner.</li>
</ul></section>
<h2>Outcome and survivor magnitude</h2>
<section class="scroll"><table><thead><tr><th>System</th><th>Winner</th><th>Runs</th><th>Winner HP mean</th><th>HP range</th><th>Fight length mean</th></tr></thead><tbody>
<tr><td>Live</td><td>Arbalester</td><td>{live['by_winner']['arbalester']['runs']}</td><td>{number(live['by_winner']['arbalester']['winner_hp']['mean'])}</td><td>{number(live['by_winner']['arbalester']['winner_hp']['min'],0)}–{number(live['by_winner']['arbalester']['winner_hp']['max'],0)}</td><td>{number(live['by_winner']['arbalester']['elimination_seconds']['mean'])} s</td></tr>
<tr><td>Live</td><td>HCA</td><td>{live['by_winner']['heavy_cav_archer']['runs']}</td><td>{number(live['by_winner']['heavy_cav_archer']['winner_hp']['mean'])}</td><td>{number(live['by_winner']['heavy_cav_archer']['winner_hp']['min'],0)}–{number(live['by_winner']['heavy_cav_archer']['winner_hp']['max'],0)}</td><td>{number(live['by_winner']['heavy_cav_archer']['elimination_seconds']['mean'])} s</td></tr>
<tr><td>Simulator</td><td>Arbalester</td><td>{sim['by_winner']['arbalester']['runs']}</td><td>{number(sim['by_winner']['arbalester']['winner_hp']['mean'])}</td><td>{number(sim['by_winner']['arbalester']['winner_hp']['min'],0)}–{number(sim['by_winner']['arbalester']['winner_hp']['max'],0)}</td><td>{number(sim['by_winner']['arbalester']['elimination_seconds']['mean'])} s</td></tr>
<tr><td>Simulator</td><td>HCA</td><td>{sim['by_winner']['heavy_cav_archer']['runs']}</td><td>{number(sim['by_winner']['heavy_cav_archer']['winner_hp']['mean'])}</td><td>{number(sim['by_winner']['heavy_cav_archer']['winner_hp']['min'],0)}–{number(sim['by_winner']['heavy_cav_archer']['winner_hp']['max'],0)}</td><td>{number(sim['by_winner']['heavy_cav_archer']['elimination_seconds']['mean'])} s</td></tr>
</tbody></table></section>
<p class="muted">Conditional winner-HP delta: {pct(comparison['arbalester_winner_hp_relative_delta'])} for Arbalester-winning runs and {pct(comparison['heavy_cav_archer_winner_hp_relative_delta'])} for HCA-winning runs. Mean signed-outcome score differs by {number(comparison['signed_score_mean_delta_points'])} points.</p>
<h2>The mechanics mismatch that remains</h2>
<section><ul>
 <li>Live Arbalesters choose <strong>{number(opening['live']['2']['unique_first_targets']['mean'])}</strong> unique first targets on average; the simulator chooses <strong>{number(opening['simulation']['2']['unique_first_targets']['mean'])}</strong>.</li>
 <li>The live opening concentrates up to <strong>{number(opening['live']['2']['maximum_shared_first_target']['mean'])}</strong> Arbalesters onto the same first target; the simulator averages <strong>{number(opening['simulation']['2']['maximum_shared_first_target']['mean'])}</strong>.</li>
 <li>In the first two seconds after first damage, live Arbalesters land <strong>{number(opening['live']['2']['opening_hits']['mean'])}</strong> hits on average versus <strong>{number(opening['simulation']['2']['opening_hits']['mean'])}</strong> in simulation. The simulator compresses and activates the formation too quickly.</li>
 <li>Therefore the close winner rate is encouraging but is not proof that movement/targeting is finished; it can contain compensating errors. This report does not prescribe a matchup-specific correction.</li>
</ul><p><a href="{VIEWER_URL}">Open the representative simulator seed 4 in the Tailnet viewer</a>.</p></section>
<h2>Traceability</h2>
<section><p>Live evidence: <code>{html.escape(report['sources']['live_analysis'])}</code><br>Simulator evidence: <code>{html.escape(report['sources']['simulation_results'])}</code><br>Generated {html.escape(report['generated_at'])}.</p>
<details><summary>All 20 live captures and exact frames.bin paths</summary><div class="scroll"><table><thead><tr><th>Run</th><th>Winner</th><th>HP</th><th>Survivors</th><th>Source</th></tr></thead><tbody>{run_rows}</tbody></table></div></details>
</section>
<h2>Method and limits</h2>
<section><ul>
 <li>Every live round reloads the exact golden ranged-vs-ranged scenario; capture validation checks the 27/18 rosters and literal authored positions before accepting a run.</li>
 <li>“Active” means alive with a resolved hostile target inside the DAT attack envelope and currently attacking or reloading. Damage hits come from full-rate gRPC HP deltas and action/kill attribution.</li>
 <li>Live RNG cannot be assigned the simulator’s numeric seeds, so this is a distribution comparison, not seed-by-seed pairing. Twenty rounds reveal flips but still leave broad winner-rate uncertainty.</li>
 <li>No captured winner, HP value, timing, or waypoint is used as a runtime override. The remaining deltas are reported as mechanics work, not force-fit calibration.</li>
</ul></section>
</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", type=Path, default=DEFAULT_LIVE)
    parser.add_argument("--simulation", type=Path, default=DEFAULT_SIM)
    parser.add_argument("--simulation-participation", type=Path,
                        default=DEFAULT_SIM_PARTICIPATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    live_doc = json.loads(args.live.resolve().read_text(encoding="utf-8"))
    sim_doc = json.loads(args.simulation.resolve().read_text(encoding="utf-8"))
    sim_row = next(
        row for row in sim_doc["rows"]
        if row["key"] == "arbalester_vs_heavy_cav_archer"
    )
    if live_doc.get("generated_from_completed_runs") != 20:
        raise SystemExit("live analysis must contain exactly 20 completed runs")
    if len(sim_row["simulation"]["runs"]) != 20:
        raise SystemExit("simulation comparison must contain exactly 20 seeds")
    if len(live_doc.get("participation", [])) != 20:
        raise SystemExit("live analysis must contain participation for all 20 runs")

    live_outcome = live_outcomes(live_doc["runs"])
    simulation_outcome = sim_outcomes(sim_row["simulation"])
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_commit": git_commit(),
        "matchup": {
            "family": "ranged_vs_ranged",
            "side2": "27 Chinese Arbalesters",
            "side3": "18 Saracen Heavy Cavalry Archers",
        },
        "sources": {
            "live_analysis": str(args.live.resolve()),
            "live_capture_manifest": live_doc["capture_manifest"],
            "simulation_results": str(args.simulation.resolve()),
            "simulation_seed4_participation": str(args.simulation_participation.resolve()),
        },
        "outcomes": {
            "live": live_outcome,
            "simulation": simulation_outcome,
        },
        "outcome_comparison": {
            "arbalester_win_rate_gap_points": rounded(abs(
                live_outcome["arbalester_win_rate"]
                - simulation_outcome["arbalester_win_rate"]
            ) * 100),
            "arbalester_winner_hp_relative_delta": rounded(abs(
                simulation_outcome["by_winner"]["arbalester"]["winner_hp"]["mean"]
                - live_outcome["by_winner"]["arbalester"]["winner_hp"]["mean"]
            ) / live_outcome["by_winner"]["arbalester"]["winner_hp"]["mean"], 4),
            "heavy_cav_archer_winner_hp_relative_delta": rounded(abs(
                simulation_outcome["by_winner"]["heavy_cav_archer"]["winner_hp"]["mean"]
                - live_outcome["by_winner"]["heavy_cav_archer"]["winner_hp"]["mean"]
            ) / live_outcome["by_winner"]["heavy_cav_archer"]["winner_hp"]["mean"], 4),
            "signed_score_mean_delta_points": rounded(abs(
                simulation_outcome["signed_score"]["mean"]
                - live_outcome["signed_score"]["mean"]
            )),
        },
        "opening_mechanics": opening_mechanics(
            live_doc["runs"], sim_row["simulation"]["runs"]
        ),
        "live_winner_separation": {
            "participation": live_window_by_winner(live_doc["participation"]),
            "unit_timing": unit_timing_by_winner(live_doc["runs"]),
        },
        "live_runs": live_doc["runs"],
        "simulation_runs": [
            {
                "seed": row["openingSeed"],
                "winner_owner": row["winnerOwner"],
                "winner_hp": row["winnerHp"],
                "ticks": row["ticks"],
                "score": row["score"],
            }
            for row in sim_row["simulation"]["runs"]
        ],
        "interpretation": {
            "winner_distribution": (
                "The live game genuinely flips this matchup; compare distributions, "
                "not a single deterministic expected winner."
            ),
            "live_separator": (
                "Winner separation emerges during firing-lane turnover after the opening, "
                "not from the first target choice alone."
            ),
            "remaining_engine_delta": (
                "The simulator spreads Arbalester opening targets and activates shooters "
                "too quickly, so similar outcome frequency may include compensating errors."
            ),
        },
    }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "diagnosis.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "report.html").write_text(render_html(report), encoding="utf-8")
    print(args.output / "report.html")


if __name__ == "__main__":
    main()
