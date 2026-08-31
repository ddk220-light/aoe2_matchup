"""Trace friendly physical-overlap episodes in live Arbalester-vs-HCA run 1.

This is observation-only analysis.  A graph edge exists when two friendly
units' axis-aligned collision boxes intersect.  Connected components define 2-unit,
3-unit, and larger overlap groups.  Exact-member components are tracked as
episodes so pair-to-triple transitions remain visible.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
import json
import math
from pathlib import Path
import statistics
import struct

import analyze_live_melee_group_variance as group
from analyze_live_melee_1v1 import action_of, merged_entities, seed_snapshot


ROOT = Path(__file__).resolve().parents[1]
MATCHUP = "arbalester_vs_heavy_cav_archer"
FRAMES = (
    ROOT / "calibration" / "live_observations" / "ranged_matrix_5x_2026-08-29"
    / MATCHUP / "run_001" / "raw recordings" / f"{MATCHUP}.frames.bin"
)
OUTPUT = (
    ROOT / "calibration" / "reports" / "arbalester_hca_participation_2026-08-30"
    / "live_run1_overlap_episodes.json"
)
WINDOW_SECONDS = 20.0
SNAP_RESEED = 400_000
EXPECTED = {2: (492, 27), 3: (474, 18)}
COLLISION_RADIUS = {2: 0.2, 3: 0.25}
LABEL = {2: "Chinese Arbalesters", 3: "Saracen Heavy Cavalry Archers"}


def rounded(value, digits=5):
    return round(value, digits)


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def centroid(units):
    return (
        statistics.fmean(unit["x"] for unit in units),
        statistics.fmean(unit["y"] for unit in units),
    )


def cluster_indices(values, tolerance=0.15, descending=False):
    clusters = []
    for value in sorted(values, reverse=descending):
        if not clusters or abs(value - statistics.fmean(clusters[-1])) > tolerance:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    centers = [statistics.fmean(cluster) for cluster in clusters]
    return centers


def nearest_cluster(value, centers):
    return min(range(len(centers)), key=lambda index: abs(value - centers[index])) + 1


def formation_metadata(selected):
    by_owner = {
        owner: [unit for unit in selected.values() if unit["owner"] == owner]
        for owner in (2, 3)
    }
    center = {owner: centroid(units) for owner, units in by_owner.items()}
    dx = center[3][0] - center[2][0]
    dy = center[3][1] - center[2][1]
    length = math.hypot(dx, dy)
    base_axis = (dx / length, dy / length)
    output = {}
    axes = {}
    for owner in (2, 3):
        direction = base_axis if owner == 2 else (-base_axis[0], -base_axis[1])
        lateral = (-direction[1], direction[0])
        axes[owner] = {"forward": direction, "lateral": lateral}
        projections = []
        for unit in by_owner[owner]:
            rel_x = unit["x"] - center[owner][0]
            rel_y = unit["y"] - center[owner][1]
            projections.append({
                "id": unit["id"],
                "forward": rel_x * direction[0] + rel_y * direction[1],
                "lateral": rel_x * lateral[0] + rel_y * lateral[1],
                "x": unit["x"],
                "y": unit["y"],
            })
        rank_centers = cluster_indices(
            [row["forward"] for row in projections], descending=True
        )
        column_centers = cluster_indices(
            [row["lateral"] for row in projections], descending=False
        )
        for row in projections:
            output[row["id"]] = {
                "owner": owner,
                "army": LABEL[owner],
                "initialRank": nearest_cluster(row["forward"], rank_centers),
                "initialColumn": nearest_cluster(row["lateral"], column_centers),
                "initialX": rounded(row["x"]),
                "initialY": rounded(row["y"]),
                "initialForward": rounded(row["forward"]),
                "initialLateral": rounded(row["lateral"]),
            }
    return output, axes


def overlap_components(selected, prior, dt, formation):
    output = {2: [], 3: []}
    for owner in (2, 3):
        units = [unit for unit in selected.values() if unit["owner"] == owner]
        by_id = {unit["id"]: unit for unit in units}
        adjacency = {unit["id"]: set() for unit in units}
        edge_depth = {}
        threshold = 2 * COLLISION_RADIUS[owner]
        for left_index, left in enumerate(units):
            for right in units[left_index + 1:]:
                # AoE2 collision_size_x/y are axis-aligned half-extents.  Both
                # units here have equal X/Y values, so physical separation is
                # the Chebyshev metric used by the simulation collision solver.
                distance = max(
                    abs(right["x"] - left["x"]),
                    abs(right["y"] - left["y"]),
                )
                depth = threshold - distance
                if depth > 1e-9:
                    adjacency[left["id"]].add(right["id"])
                    adjacency[right["id"]].add(left["id"])
                    edge_depth[tuple(sorted((left["id"], right["id"])))] = depth
        visited = set()
        for start in sorted(adjacency):
            if start in visited or not adjacency[start]:
                continue
            stack = [start]
            members = []
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                members.append(current)
                stack.extend(adjacency[current] - visited)
            members.sort()
            member_edges = [
                {"pair": list(pair), "depth": rounded(depth)}
                for pair, depth in edge_depth.items()
                if pair[0] in members and pair[1] in members
            ]
            member_edges.sort(key=lambda row: row["depth"], reverse=True)
            states = []
            for unit_id in members:
                unit = by_id[unit_id]
                previous = prior.get(unit_id)
                speed = (
                    math.hypot(unit["x"] - previous["x"], unit["y"] - previous["y"])
                    / max(dt, 1e-9)
                    if previous else 0.0
                )
                states.append({
                    "id": unit_id,
                    "rank": formation[unit_id]["initialRank"],
                    "column": formation[unit_id]["initialColumn"],
                    "actionState": unit.get("action_state"),
                    "targetId": unit.get("target_id"),
                    "speed": rounded(speed),
                    "x": rounded(unit["x"]),
                    "y": rounded(unit["y"]),
                })
            moving = sum(state["speed"] > 0.05 for state in states)
            firing = sum(state["actionState"] == 7 for state in states)
            reloading = sum(state["actionState"] == 6 for state in states)
            if moving and (firing or reloading):
                signature = "moving follower compresses into firing/reloading unit"
            elif moving >= 2:
                signature = "moving units converge"
            elif firing or reloading:
                signature = "attack-line compression while firing/reloading"
            else:
                signature = "stationary or low-speed compression"
            output[owner].append({
                "members": members,
                "size": len(members),
                "edges": member_edges,
                "meanDepth": rounded(statistics.fmean(row["depth"] for row in member_edges)),
                "maxDepth": rounded(max(row["depth"] for row in member_edges)),
                "states": states,
                "movingMembers": moving,
                "firingMembers": firing,
                "reloadingMembers": reloading,
                "behavioralSignature": signature,
            })
    return output


def shared_intersection_fraction(member_ids, by_id, owner):
    """Return common AABB intersection area as a fraction of one unit body."""
    radius = COLLISION_RADIUS[owner]
    members = [by_id[member_id] for member_id in member_ids]
    width = max(
        0.0,
        min(member["x"] + radius for member in members)
        - max(member["x"] - radius for member in members),
    )
    height = max(
        0.0,
        min(member["y"] + radius for member in members)
        - max(member["y"] - radius for member in members),
    )
    return width * height / ((2 * radius) ** 2)


def lateral_spread(frame, members, owner, axes):
    units = [frame["units"].get(member) for member in members]
    if any(unit is None for unit in units):
        return None
    lateral = axes[owner]["lateral"]
    values = [unit["x"] * lateral[0] + unit["y"] * lateral[1] for unit in units]
    return max(values) - min(values)


def decode():
    doc = entity_store = world_id = None
    first_frame_t = None
    prior_t = None
    prior = {}
    formation = axes = None
    frames = []
    active = {}
    episodes = []
    active_contacts = {}
    contact_episodes = []
    max_mutual_clique = {2: 0, 3: 0}
    max_mutual_clique_event = {2: None, 3: None}
    max_overlap_degree = {2: 0, 3: 0}
    max_overlap_degree_event = {2: None, 3: None}
    max_firing_overlap_degree = {2: 0, 3: 0}
    contact_depth_samples = defaultdict(list)
    shared_intersection_samples = defaultdict(list)
    prior_action = {}
    first_shot_by_unit = {}

    with FRAMES.open("rb") as stream:
        while True:
            header = stream.read(4)
            if len(header) < 4:
                break
            (length,) = struct.unpack("<I", header)
            payload = stream.read(length)
            if len(payload) != length:
                break
            sequence = group.pb.FrameSequence()
            sequence.ParseFromString(payload)
            for frame in sequence.frame:
                patch = frame.patch
                if patch and len(patch) > SNAP_RESEED:
                    doc, entity_store, world_id = seed_snapshot(patch)
                    first_frame_t = None
                    prior_t = None
                    prior = {}
                    frames = []
                    active = {}
                    episodes = []
                    active_contacts = {}
                    contact_episodes = []
                    max_mutual_clique = {2: 0, 3: 0}
                    max_mutual_clique_event = {2: None, 3: None}
                    max_overlap_degree = {2: 0, 3: 0}
                    max_overlap_degree_event = {2: None, 3: None}
                    max_firing_overlap_degree = {2: 0, 3: 0}
                    contact_depth_samples = defaultdict(list)
                    shared_intersection_samples = defaultdict(list)
                    prior_action = {}
                    first_shot_by_unit = {}
                    formation = axes = None
                    continue
                if entity_store is None:
                    continue
                if patch:
                    group.D.apply_patch(doc, patch, entity_store, world_id)
                selected = {}
                for key, entity in merged_entities(doc, entity_store, world_id):
                    owner = entity.get(2)
                    master = entity.get(1)
                    if owner not in EXPECTED or master != EXPECTED[owner][0]:
                        continue
                    selected[key] = {
                        "key": key,
                        "id": entity.get(0),
                        "owner": owner,
                        "x": float(entity.get(3)),
                        "y": float(entity.get(4)),
                        "hp": float(entity.get(12)),
                        **action_of(doc, entity),
                    }
                if first_frame_t is None:
                    roster = Counter(unit["owner"] for unit in selected.values())
                    if roster != Counter({owner: row[1] for owner, row in EXPECTED.items()}):
                        continue
                    first_frame_t = frame.time / 1000.0
                    formation, axes = formation_metadata(selected)
                t = frame.time / 1000.0 - first_frame_t
                if t > WINDOW_SECONDS + 0.05:
                    continue
                now = frame.time / 1000.0
                dt = now - prior_t if prior_t is not None else 1 / 60
                by_id = {unit["id"]: unit for unit in selected.values()}
                components = overlap_components(selected, prior, dt, formation)
                frame_index = len(frames)
                frame_record = {
                    "t": t,
                    "units": by_id,
                    "components": components,
                }
                frames.append(frame_record)

                shot_starts = set()
                for unit_id, unit in by_id.items():
                    state = unit.get("action_state")
                    if state == 7 and prior_action.get(unit_id) != 7:
                        shot_starts.add(unit_id)
                        first_shot_by_unit.setdefault(unit_id, t)
                    prior_action[unit_id] = state

                seen = set()
                for owner in (2, 3):
                    for component in components[owner]:
                        key = (owner, tuple(component["members"]))
                        seen.add(key)
                        if key not in active:
                            active[key] = {
                                "owner": owner,
                                "army": LABEL[owner],
                                "members": component["members"],
                                "size": component["size"],
                                "startFrame": frame_index,
                                "endFrame": frame_index,
                                "startSecond": t,
                                "endSecond": t,
                                "observations": 0,
                                "maxDepth": 0.0,
                                "depthSum": 0.0,
                                "framesWithFiring": 0,
                                "shotStartsWhileOverlapping": 0,
                                "onset": component,
                            }
                        episode = active[key]
                        episode["endFrame"] = frame_index
                        episode["endSecond"] = t
                        episode["observations"] += 1
                        episode["maxDepth"] = max(episode["maxDepth"], component["maxDepth"])
                        episode["depthSum"] += component["meanDepth"]
                        episode["framesWithFiring"] += component["firingMembers"] > 0
                        episode["shotStartsWhileOverlapping"] += sum(
                            member in shot_starts for member in component["members"]
                        )
                for key in list(active):
                    if key not in seen:
                        episodes.append(active.pop(key))

                seen_contacts = set()
                for owner in (2, 3):
                    edge_depth = {}
                    for component in components[owner]:
                        for edge in component["edges"]:
                            edge_depth[tuple(edge["pair"])] = edge["depth"]
                    overlap_degree = Counter()
                    overlap_neighbors = defaultdict(list)
                    for left_id, right_id in edge_depth:
                        overlap_degree[left_id] += 1
                        overlap_degree[right_id] += 1
                        overlap_neighbors[left_id].append(right_id)
                        overlap_neighbors[right_id].append(left_id)
                    if overlap_degree:
                        unit_id, degree = max(
                            overlap_degree.items(),
                            key=lambda row: (row[1], -row[0]),
                        )
                        if degree > max_overlap_degree[owner]:
                            max_overlap_degree[owner] = degree
                            max_overlap_degree_event[owner] = {
                                "second": rounded(t),
                                "unitId": unit_id,
                                "degree": degree,
                                "neighbors": sorted(overlap_neighbors[unit_id]),
                                "actionState": by_id[unit_id].get("action_state"),
                            }
                        for firing_id, firing_degree in overlap_degree.items():
                            if by_id[firing_id].get("action_state") == 7:
                                max_firing_overlap_degree[owner] = max(
                                    max_firing_overlap_degree[owner],
                                    firing_degree,
                                )
                    groups = [
                        (pair, [{"pair": list(pair), "depth": depth}])
                        for pair, depth in edge_depth.items()
                    ]
                    for component in components[owner]:
                        for size in (3, 4):
                            for member_group in combinations(component["members"], size):
                                pairs = list(combinations(member_group, 2))
                                if all(tuple(sorted(pair)) in edge_depth for pair in pairs):
                                    groups.append((member_group, [
                                        {
                                            "pair": list(tuple(sorted(pair))),
                                            "depth": edge_depth[tuple(sorted(pair))],
                                        }
                                        for pair in pairs
                                    ]))
                    largest = 0
                    largest_members = None
                    for component in components[owner]:
                        member_ids = component["members"]
                        for size in range(min(6, len(member_ids)), 1, -1):
                            matching = next((
                                group_ids for group_ids in combinations(member_ids, size)
                                if all(tuple(sorted(pair)) in edge_depth for pair in combinations(group_ids, 2))
                            ), None)
                            if matching is not None:
                                largest = max(largest, size)
                                if size == largest:
                                    largest_members = tuple(sorted(matching))
                                break
                    if largest > max_mutual_clique[owner]:
                        max_mutual_clique[owner] = largest
                        clique_depths = [
                            edge_depth[tuple(sorted(pair))]
                            for pair in combinations(largest_members, 2)
                        ] if largest_members else []
                        max_mutual_clique_event[owner] = {
                            "second": rounded(t),
                            "members": list(largest_members or ()),
                            "size": largest,
                            "meanDepth": rounded(statistics.fmean(clique_depths))
                            if clique_depths else 0,
                            "maxDepth": rounded(max(clique_depths)) if clique_depths else 0,
                            "formation": [formation[member] for member in (largest_members or ())],
                            "actionStates": {
                                str(member): by_id[member].get("action_state")
                                for member in (largest_members or ())
                            },
                        }
                    for members, onset_edges in groups:
                        members = tuple(sorted(members))
                        key = (owner, members)
                        seen_contacts.add(key)
                        if key not in active_contacts:
                            active_contacts[key] = {
                                "owner": owner,
                                "army": LABEL[owner],
                                "members": list(members),
                                "size": len(members),
                                "startSecond": t,
                                "endSecond": t,
                                "observations": 0,
                                "depthSum": 0.0,
                                "edgeDepthSums": {},
                                "edgeDepthMaxima": {},
                                "sharedIntersectionFractionSum": 0.0,
                                "maxSharedIntersectionFraction": 0.0,
                                "maxDepth": 0.0,
                                "framesWithFiring": 0,
                                "shotStartsWhileOverlapping": 0,
                                "formation": [formation[member] for member in members],
                                "onsetEdges": [
                                    {"pair": row["pair"], "depth": rounded(row["depth"])}
                                    for row in onset_edges
                                ],
                            }
                        contact = active_contacts[key]
                        contact["endSecond"] = t
                        contact["observations"] += 1
                        depths = [row["depth"] for row in onset_edges]
                        contact_depth_samples[(owner, len(members))].append(
                            statistics.fmean(depths)
                        )
                        shared_fraction = shared_intersection_fraction(
                            members,
                            by_id,
                            owner,
                        )
                        shared_intersection_samples[(owner, len(members))].append(
                            shared_fraction
                        )
                        contact["depthSum"] += statistics.fmean(depths)
                        contact["sharedIntersectionFractionSum"] += shared_fraction
                        contact["maxSharedIntersectionFraction"] = max(
                            contact["maxSharedIntersectionFraction"],
                            shared_fraction,
                        )
                        for edge in onset_edges:
                            pair_key = "-".join(str(value) for value in edge["pair"])
                            contact["edgeDepthSums"][pair_key] = (
                                contact["edgeDepthSums"].get(pair_key, 0.0) + edge["depth"]
                            )
                            contact["edgeDepthMaxima"][pair_key] = max(
                                contact["edgeDepthMaxima"].get(pair_key, 0.0),
                                edge["depth"],
                            )
                        contact["maxDepth"] = max(contact["maxDepth"], max(depths))
                        contact["framesWithFiring"] += any(
                            by_id[member].get("action_state") == 7 for member in members
                        )
                        contact["shotStartsWhileOverlapping"] += sum(
                            member in shot_starts for member in members
                        )
                for key in list(active_contacts):
                    if key not in seen_contacts:
                        contact_episodes.append(active_contacts.pop(key))
                prior = by_id
                prior_t = now
    episodes.extend(active.values())
    contact_episodes.extend(active_contacts.values())
    if not frames:
        raise RuntimeError("no exact-roster frames decoded")

    for episode in episodes:
        episode["startSecond"] = rounded(episode["startSecond"])
        episode["endSecond"] = rounded(episode["endSecond"])
        episode["durationSeconds"] = rounded(
            max(0.0, episode["endSecond"] - episode["startSecond"] + 1 / 60)
        )
        episode["meanDepth"] = rounded(
            episode.pop("depthSum") / max(episode["observations"], 1)
        )
        episode["maxDepth"] = rounded(episode["maxDepth"])
        episode["firingFrameShare"] = rounded(
            episode.pop("framesWithFiring") / max(episode["observations"], 1)
        )
        onset_spread = lateral_spread(
            frames[episode["startFrame"]], episode["members"], episode["owner"], axes
        )
        after_index = min(len(frames) - 1, episode["endFrame"] + 30)
        after_spread = lateral_spread(
            frames[after_index], episode["members"], episode["owner"], axes
        )
        episode["lateralSpreadAtOnset"] = (
            rounded(onset_spread) if onset_spread is not None else None
        )
        episode["lateralSpreadHalfSecondAfter"] = (
            rounded(after_spread) if after_spread is not None else None
        )
        episode["lateralFanOut"] = (
            rounded(after_spread - onset_spread)
            if onset_spread is not None and after_spread is not None else None
        )
        episode["endedWithAllMembersPresent"] = all(
            member in frames[min(len(frames) - 1, episode["endFrame"] + 1)]["units"]
            for member in episode["members"]
        )
        episode.pop("startFrame")
        episode.pop("endFrame")

    episodes.sort(key=lambda row: (row["startSecond"], row["owner"], row["members"]))
    for episode in contact_episodes:
        episode["startSecond"] = rounded(episode["startSecond"])
        episode["endSecond"] = rounded(episode["endSecond"])
        episode["durationSeconds"] = rounded(
            max(0.0, episode["endSecond"] - episode["startSecond"] + 1 / 60)
        )
        episode["meanDepth"] = rounded(
            episode.pop("depthSum") / max(episode["observations"], 1)
        )
        episode["meanDepthByPair"] = {
            pair: rounded(total / max(episode["observations"], 1))
            for pair, total in episode.pop("edgeDepthSums").items()
        }
        episode["maxDepthByPair"] = {
            pair: rounded(value)
            for pair, value in episode.pop("edgeDepthMaxima").items()
        }
        episode["meanSharedIntersectionFraction"] = rounded(
            episode.pop("sharedIntersectionFractionSum")
            / max(episode["observations"], 1)
        )
        episode["maxSharedIntersectionFraction"] = rounded(
            episode["maxSharedIntersectionFraction"]
        )
        episode["maxDepth"] = rounded(episode["maxDepth"])
        episode["firingFrameShare"] = rounded(
            episode.pop("framesWithFiring") / max(episode["observations"], 1)
        )
    contact_episodes.sort(
        key=lambda row: (row["startSecond"], row["owner"], row["members"])
    )
    for episode in contact_episodes:
        if episode["size"] not in (3, 4):
            continue
        member_set = set(episode["members"])
        candidates = [
            row for row in contact_episodes
            if row["owner"] == episode["owner"]
            and row["size"] == episode["size"] - 1
            and set(row["members"]).issubset(member_set)
            and row["startSecond"] <= episode["startSecond"] - 0.01
            and row["endSecond"] >= episode["startSecond"] - 0.02
        ]
        if not candidates:
            episode["entryComparison"] = None
            continue
        incumbent = max(
            candidates,
            key=lambda row: episode["startSecond"] - row["startSecond"],
        )
        incumbent_set = set(incumbent["members"])
        entrant = next(iter(member_set - incumbent_set))
        incumbent_depths = [
            row["depth"] for row in episode["onsetEdges"]
            if set(row["pair"]).issubset(incumbent_set)
        ]
        entrant_depths = [
            row["depth"] for row in episode["onsetEdges"]
            if entrant in row["pair"]
        ]
        incumbent_pair_keys = [
            "-".join(str(value) for value in sorted(pair))
            for pair in combinations(sorted(incumbent_set), 2)
        ]
        entrant_pair_keys = [
            "-".join(str(value) for value in sorted((entrant, member)))
            for member in sorted(incumbent_set)
        ]
        incumbent_lifetime_means = [
            episode["meanDepthByPair"][pair]
            for pair in incumbent_pair_keys
        ]
        entrant_lifetime_means = [
            episode["meanDepthByPair"][pair]
            for pair in entrant_pair_keys
        ]
        incumbent_lifetime_maxima = [
            episode["maxDepthByPair"][pair]
            for pair in incumbent_pair_keys
        ]
        entrant_lifetime_maxima = [
            episode["maxDepthByPair"][pair]
            for pair in entrant_pair_keys
        ]
        episode["entryComparison"] = {
            "incumbentMembers": sorted(incumbent_set),
            "entrant": entrant,
            "incumbentMeanDepth": rounded(statistics.fmean(incumbent_depths)),
            "entrantMeanDepth": rounded(statistics.fmean(entrant_depths)),
            "entrantMaxDepth": rounded(max(entrant_depths)),
            "entrantIsShallower": (
                statistics.fmean(entrant_depths) < statistics.fmean(incumbent_depths)
            ),
            "incumbentLifetimeMeanDepth": rounded(
                statistics.fmean(incumbent_lifetime_means)
            ),
            "entrantLifetimeMeanDepth": rounded(
                statistics.fmean(entrant_lifetime_means)
            ),
            "entrantLifetimeIsShallower": (
                statistics.fmean(entrant_lifetime_means)
                < statistics.fmean(incumbent_lifetime_means)
            ),
            "incumbentLifetimeMaxDepth": rounded(
                statistics.fmean(incumbent_lifetime_maxima)
            ),
            "entrantLifetimeMaxDepth": rounded(
                statistics.fmean(entrant_lifetime_maxima)
            ),
        }
    summary = {}
    for owner in (2, 3):
        current = [episode for episode in episodes if episode["owner"] == owner]
        owner_contacts = [
            row for row in contact_episodes if row["owner"] == owner
        ]
        counts = Counter(
            str(episode["size"]) if episode["size"] < 4 else "4+"
            for episode in current
        )
        unique_sets = defaultdict(set)
        for episode in current:
            bucket = str(episode["size"]) if episode["size"] < 4 else "4+"
            unique_sets[bucket].add(tuple(episode["members"]))
        firing_episodes = sum(episode["firingFrameShare"] > 0 for episode in current)
        summary[str(owner)] = {
            "army": LABEL[owner],
            "collisionDiameter": 2 * COLLISION_RADIUS[owner],
            "firstOverlapSecond": min((row["startSecond"] for row in current), default=None),
            "lastOverlapObservationSecond": max((row["endSecond"] for row in current), default=None),
            "episodeCountsByComponentSize": dict(counts),
            "uniqueMemberSetsByComponentSize": {
                key: len(value) for key, value in unique_sets.items()
            },
            "maxComponentSize": max((row["size"] for row in current), default=0),
            "maxMutualOverlapSize": max_mutual_clique[owner],
            "firstMaximumMutualOverlap": max_mutual_clique_event[owner],
            "maxOverlapDegree": max_overlap_degree[owner],
            "firstMaximumOverlapDegree": max_overlap_degree_event[owner],
            "maxFiringOverlapDegree": max_firing_overlap_degree[owner],
            "episodesWithAnyFiring": firing_episodes,
            "shotStartsWhileOverlapping": sum(
                row["shotStartsWhileOverlapping"] for row in current
            ),
            "unitsEverOverlapping": sorted({
                member for row in current for member in row["members"]
            }),
            "firstTwoUnitEpisode": next(
                (row for row in current if row["size"] == 2), None
            ),
            "firstThreeUnitEpisode": next(
                (row for row in current if row["size"] == 3), None
            ),
            "pairContactEpisodes": sum(
                row["owner"] == owner and row["size"] == 2 for row in contact_episodes
            ),
            "uniqueOverlappingPairs": len({
                tuple(row["members"]) for row in contact_episodes
                if row["owner"] == owner and row["size"] == 2
            }),
            "mutualTripleEpisodes": sum(
                row["owner"] == owner and row["size"] == 3 for row in contact_episodes
            ),
            "uniqueMutualTriples": len({
                tuple(row["members"]) for row in contact_episodes
                if row["owner"] == owner and row["size"] == 3
            }),
            "firstPairContact": next(
                (row for row in contact_episodes if row["owner"] == owner and row["size"] == 2),
                None,
            ),
            "firstMutualTriple": next(
                (row for row in contact_episodes if row["owner"] == owner and row["size"] == 3),
                None,
            ),
            "fourWayMutualEpisodes": sum(
                row["size"] == 4 for row in owner_contacts
            ),
            "uniqueFourWayMutualSets": len({
                tuple(row["members"]) for row in owner_contacts if row["size"] == 4
            }),
            "entrantDepthComparison": {
                str(size): {
                    "episodes": len(rows),
                    "meanIncumbentDepthAtEntry": rounded(statistics.fmean(
                        row["entryComparison"]["incumbentMeanDepth"] for row in rows
                    )) if rows else None,
                    "meanEntrantDepthAtEntry": rounded(statistics.fmean(
                        row["entryComparison"]["entrantMeanDepth"] for row in rows
                    )) if rows else None,
                    "entrantShallowerShare": rounded(statistics.fmean(
                        row["entryComparison"]["entrantIsShallower"] for row in rows
                    )) if rows else None,
                    "meanIncumbentLifetimeDepth": rounded(statistics.fmean(
                        row["entryComparison"]["incumbentLifetimeMeanDepth"] for row in rows
                    )) if rows else None,
                    "meanEntrantLifetimeDepth": rounded(statistics.fmean(
                        row["entryComparison"]["entrantLifetimeMeanDepth"] for row in rows
                    )) if rows else None,
                    "entrantLifetimeShallowerShare": rounded(statistics.fmean(
                        row["entryComparison"]["entrantLifetimeIsShallower"] for row in rows
                    )) if rows else None,
                    "meanIncumbentLifetimeMaxDepth": rounded(statistics.fmean(
                        row["entryComparison"]["incumbentLifetimeMaxDepth"] for row in rows
                    )) if rows else None,
                    "meanEntrantLifetimeMaxDepth": rounded(statistics.fmean(
                        row["entryComparison"]["entrantLifetimeMaxDepth"] for row in rows
                    )) if rows else None,
                }
                for size in (3, 4)
                for rows in [[
                    row for row in owner_contacts
                    if row["size"] == size and row.get("entryComparison")
                ]]
            },
            "contactDepthDistribution": {
                str(size): {
                    "observations": len(contact_depth_samples[(owner, size)]),
                    "mean": rounded(statistics.fmean(contact_depth_samples[(owner, size)]))
                    if contact_depth_samples[(owner, size)] else None,
                    "p50": rounded(percentile(contact_depth_samples[(owner, size)], 0.50))
                    if contact_depth_samples[(owner, size)] else None,
                    "p90": rounded(percentile(contact_depth_samples[(owner, size)], 0.90))
                    if contact_depth_samples[(owner, size)] else None,
                    "p95": rounded(percentile(contact_depth_samples[(owner, size)], 0.95))
                    if contact_depth_samples[(owner, size)] else None,
                    "p99": rounded(percentile(contact_depth_samples[(owner, size)], 0.99))
                    if contact_depth_samples[(owner, size)] else None,
                    "maximum": rounded(max(contact_depth_samples[(owner, size)]))
                    if contact_depth_samples[(owner, size)] else None,
                }
                for size in (2, 3, 4)
            },
            "sharedIntersectionDistribution": {
                str(size): {
                    "observations": len(shared_intersection_samples[(owner, size)]),
                    "mean": rounded(statistics.fmean(
                        shared_intersection_samples[(owner, size)]
                    )) if shared_intersection_samples[(owner, size)] else None,
                    "p50": rounded(percentile(
                        shared_intersection_samples[(owner, size)], 0.50
                    )) if shared_intersection_samples[(owner, size)] else None,
                    "p90": rounded(percentile(
                        shared_intersection_samples[(owner, size)], 0.90
                    )) if shared_intersection_samples[(owner, size)] else None,
                    "maximum": rounded(max(
                        shared_intersection_samples[(owner, size)]
                    )) if shared_intersection_samples[(owner, size)] else None,
                }
                for size in (2, 3, 4)
            },
        }

    return {
        "schemaVersion": 1,
        "source": {"run": 1, "framesBin": str(FRAMES)},
        "windowSeconds": WINDOW_SECONDS,
        "definition": (
            "Friendly overlap graph uses live unit centers and axis-aligned physical "
            "collision half-extents; connected components are exact-member episodes."
        ),
        "collisionRadius": {str(owner): value for owner, value in COLLISION_RADIUS.items()},
        "formation": {str(key): value for key, value in sorted(formation.items())},
        "summary": summary,
        "episodes": episodes,
        "pairAndMutualTripleEpisodes": contact_episodes,
        "firstTwentyEpisodes": episodes[:20],
        "firstShotSecondByUnit": {
            str(key): rounded(value) for key, value in sorted(first_shot_by_unit.items())
        },
    }


def main():
    document = decode()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
