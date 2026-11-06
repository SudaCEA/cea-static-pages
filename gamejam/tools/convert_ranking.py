#!/usr/bin/env python3
"""Convert the exported GameJam rating CSV into display-ready JSON.

The aggregation follows the ranking page in cea-event-hub:
- one latest submission per submitting team
- excluded teams are removed before ranking and their ratings are ignored
- judge submissions count as scores but judge teams are never ranked
- self-ratings are ignored
- overall score is the mean of the four criterion averages
- equal overall scores share a rank
- each criterion's highest average wins that criterion award
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import locale
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = (
    PAGE_ROOT
    / "assets"
    / "mirror-26"
    / "cea-submissions-2026-codejam-rating-20261106-113938.csv"
)
DEFAULT_OUT = PAGE_ROOT / "mirror-2610" / "data" / "ranking.json"

KIND = "gamejam-rating"
EPSILON = 1e-9
STORED_PRECISION = 4
DISPLAY_PRECISION = 2

# Manually excluded from this event's ranking. Team 14 did not submit a
# project; its received ratings are ignored as well.
EXCLUDED_TEAMS = {
    14: "对的对的",
}

CRITERIA = (
    {
        "id": "creativity",
        "label": "创意分",
        "awardTitle": "创意奖",
        "blurb": "核心玩法、机制或表达的新意与趣味。",
    },
    {
        "id": "completeness",
        "label": "完成度",
        "awardTitle": "完成度奖",
        "blurb": "可玩闭环、流程顺畅与关键功能齐全。",
    },
    {
        "id": "art",
        "label": "美术分",
        "awardTitle": "美术奖",
        "blurb": "画面、UI 与音效的统一和感染力。",
    },
    {
        "id": "themeFit",
        "label": "切题程度",
        "awardTitle": "切题奖",
        "blurb": "对 Game Jam 主题的理解与契合。",
    },
)

REQUIRED_COLUMNS = (
    "id",
    "kind",
    "submitted_at",
    "payload.submitterTeamId",
    "payload.submitterTeamName",
    "payload.submitterRole",
    "payload.ratings",
)


def text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
        return number if number > 0 and str(number) == value.strip() else None
    return None


def score_value(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or not 1 <= number <= 10:
        return None
    return number


def rounded(value: float | None) -> float | None:
    return None if value is None else round(value, STORED_PRECISION)


def top_vote(votes: Counter[str]) -> str:
    if not votes:
        return ""
    return votes.most_common(1)[0][0]


def configure_collation() -> None:
    """Use Chinese collation for tied names when the host provides it."""
    for name in (
        "Chinese (Simplified)_China.936",
        "Chinese_China.936",
        "zh_CN.UTF-8",
        "zh_CN.utf8",
    ):
        try:
            locale.setlocale(locale.LC_COLLATE, name)
            return
        except locale.Error:
            continue


def name_key(name: str) -> str:
    try:
        return locale.strxfrm(name)
    except (ValueError, locale.Error):
        return name


def parse_submissions(csv_path: Path) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    submissions: list[dict[str, Any]] = []
    ignored_kinds = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = [column for column in REQUIRED_COLUMNS if column not in fields]
        if missing:
            raise ValueError("CSV is missing columns: " + ", ".join(missing))

        rows = list(reader)

    for row_number, row in enumerate(rows, start=2):
        if not any(text(value) for value in row.values()):
            continue
        if text(row.get("kind")) != KIND:
            ignored_kinds += 1
            continue

        raw_ratings = text(row.get("payload.ratings"))
        if not raw_ratings:
            warnings.append({"row": row_number, "message": "payload.ratings is empty"})
            continue
        try:
            ratings = json.loads(raw_ratings)
        except json.JSONDecodeError as error:
            warnings.append({
                "row": row_number,
                "message": f"payload.ratings is not valid JSON: {error.msg}",
            })
            continue
        if not isinstance(ratings, list):
            warnings.append({
                "row": row_number,
                "message": "payload.ratings is not an array",
            })
            continue

        submitter_team_id = positive_int(row.get("payload.submitterTeamId"))
        submitter_name = (
            text(row.get("payload.submitterTeamName"))
            or text(row.get("submitter_name"))
        )
        role = "judge" if text(row.get("payload.submitterRole")) == "judge" else "team"
        ratings_out: list[dict[str, Any]] = []
        seen_targets: set[int] = set()
        self_ratings = 0

        for item in ratings:
            if not isinstance(item, dict):
                warnings.append({
                    "row": row_number,
                    "message": "a rating is not an object",
                })
                continue
            target_id = positive_int(item.get("teamId"))
            if target_id is None:
                warnings.append({
                    "row": row_number,
                    "message": "a rating has an invalid teamId",
                })
                continue
            if submitter_team_id is not None and target_id == submitter_team_id:
                self_ratings += 1
                continue
            if target_id in seen_targets:
                warnings.append({
                    "row": row_number,
                    "message": f"duplicate rating for team #{target_id}",
                })
                continue

            raw_scores = item.get("scores")
            if not isinstance(raw_scores, dict):
                warnings.append({
                    "row": row_number,
                    "message": f"team #{target_id} has no scores object",
                })
                continue

            scores: dict[str, float] = {}
            valid = True
            for criterion in CRITERIA:
                value = score_value(raw_scores.get(criterion["id"]))
                if value is None:
                    valid = False
                    break
                scores[criterion["id"]] = value
            if not valid:
                warnings.append({
                    "row": row_number,
                    "message": f"team #{target_id} has incomplete or out-of-range scores",
                })
                continue

            seen_targets.add(target_id)
            ratings_out.append({
                "teamId": target_id,
                "teamName": text(item.get("teamName")),
                "workTitle": text(item.get("workTitle")),
                "scores": scores,
            })

        if not ratings_out:
            warnings.append({
                "row": row_number,
                "message": "submission has no usable ratings",
            })
            continue
        if self_ratings:
            warnings.append({
                "row": row_number,
                "message": f"ignored {self_ratings} self-rating(s)",
            })

        submissions.append({
            "index": len(submissions),
            "id": positive_int(row.get("id")),
            "row": row_number,
            "submittedAt": text(row.get("submitted_at")),
            "submitterTeamId": submitter_team_id,
            "submitterName": submitter_name,
            "submitterRole": role,
            "selfRatings": self_ratings,
            "ratings": ratings_out,
        })

    return submissions, ignored_kinds, warnings


def is_newer(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    if (
        candidate["submittedAt"]
        and current["submittedAt"]
        and candidate["submittedAt"] != current["submittedAt"]
    ):
        return candidate["submittedAt"] > current["submittedAt"]
    if (
        candidate["id"] is not None
        and current["id"] is not None
        and candidate["id"] != current["id"]
    ):
        return candidate["id"] > current["id"]
    return candidate["index"] > current["index"]


def dedupe_submissions(submissions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[int, dict[str, Any]] = {}
    for submission in submissions:
        team_id = submission["submitterTeamId"]
        if not team_id:
            continue
        current = best.get(team_id)
        if current is None or is_newer(submission, current):
            best[team_id] = submission
    return [
        submission
        for submission in submissions
        if not submission["submitterTeamId"]
        or best.get(submission["submitterTeamId"]) is submission
    ]


def build_analysis(
    submissions: list[dict[str, Any]],
    ignored_kinds: int,
    warnings: list[dict[str, Any]],
    excluded_team_ids: set[int],
) -> dict[str, Any]:
    deduped = dedupe_submissions(submissions)
    used = [
        submission
        for submission in deduped
        if submission["submitterTeamId"] not in excluded_team_ids
    ]
    duplicate_submission_count = len(submissions) - len(deduped)
    if duplicate_submission_count:
        warnings.append({
            "row": None,
            "message": f"kept the latest submission for each team; ignored {duplicate_submission_count} older duplicate(s)",
        })

    judge_ids = {
        submission["submitterTeamId"]
        for submission in used
        if submission["submitterTeamId"] and submission["submitterRole"] == "judge"
    }
    teams: dict[int, dict[str, Any]] = {}
    self_submission_counts: Counter[int] = Counter()
    judge_submission_count = 0
    judge_target_count = 0
    excluded_rating_count = 0

    def ensure_team(team_id: int) -> dict[str, Any]:
        team = teams.get(team_id)
        if team is None:
            team = {
                "id": team_id,
                "received": 0,
                "expected": 0,
                "sums": {criterion["id"]: 0.0 for criterion in CRITERIA},
                "nameVotes": Counter(),
                "workVotes": Counter(),
                "submitterNames": [],
                "awards": [],
            }
            teams[team_id] = team
        return team

    for submission in used:
        if submission["submitterRole"] == "judge":
            judge_submission_count += 1
        team_id = submission["submitterTeamId"]
        if team_id and team_id not in judge_ids:
            submitter_team = ensure_team(team_id)
            if submission["submitterName"]:
                submitter_team["submitterNames"].append(submission["submitterName"])
            self_submission_counts[team_id] += 1
        for rating in submission["ratings"]:
            if rating["teamId"] in excluded_team_ids:
                continue
            if rating["teamId"] in judge_ids:
                continue
            target = ensure_team(rating["teamId"])
            if rating["teamName"]:
                target["nameVotes"][rating["teamName"]] += 1
            if rating["workTitle"]:
                target["workVotes"][rating["workTitle"]] += 1

    rating_count = 0
    self_rating_count = 0
    for submission in used:
        self_rating_count += int(submission["selfRatings"])
        for rating in submission["ratings"]:
            if submission["submitterTeamId"] and rating["teamId"] == submission["submitterTeamId"]:
                continue
            if rating["teamId"] in excluded_team_ids:
                excluded_rating_count += 1
                continue
            if rating["teamId"] in judge_ids:
                judge_target_count += 1
                continue
            target = ensure_team(rating["teamId"])
            target["received"] += 1
            for criterion in CRITERIA:
                target["sums"][criterion["id"]] += rating["scores"][criterion["id"]]
            rating_count += 1

    if judge_target_count:
        warnings.append({
            "row": None,
            "message": f"ignored {judge_target_count} rating(s) aimed at judge teams",
        })

    expected_team_count = 0
    complete_team_count = 0
    for team in teams.values():
        team["expected"] = len(used) - self_submission_counts.get(team["id"], 0)
        team["name"] = (
            next((name for name in team["submitterNames"] if name), "")
            or top_vote(team["nameVotes"])
            or f"队伍 #{team['id']}"
        )
        team["workTitle"] = top_vote(team["workVotes"])
        team["scores"] = {
            criterion["id"]: (
                team["sums"][criterion["id"]] / team["received"]
                if team["received"]
                else None
            )
            for criterion in CRITERIA
        }
        team["total"] = (
            sum(team["scores"].values()) if team["received"] else None
        )
        team["overall"] = (
            team["total"] / len(CRITERIA) if team["total"] is not None else None
        )
        team["complete"] = team["expected"] > 0 and team["received"] >= team["expected"]
        if team["expected"] > 0:
            expected_team_count += 1
        if team["complete"]:
            complete_team_count += 1

    ranked = [team for team in teams.values() if team["received"] > 0]
    ranked.sort(key=lambda team: (
        -team["overall"],
        -team["received"],
        name_key(team["name"]),
        team["id"],
    ))

    previous_rank = 0
    for index, team in enumerate(ranked):
        if index > 0 and abs(team["overall"] - ranked[index - 1]["overall"]) <= EPSILON:
            team["rank"] = previous_rank
        else:
            team["rank"] = index + 1
            previous_rank = team["rank"]
    for index, team in enumerate(ranked):
        tie_before = (
            index > 0
            and abs(team["overall"] - ranked[index - 1]["overall"]) <= EPSILON
        )
        tie_after = (
            index < len(ranked) - 1
            and abs(team["overall"] - ranked[index + 1]["overall"]) <= EPSILON
        )
        team["tied"] = tie_before or tie_after

    unranked = [team for team in teams.values() if team["received"] == 0]
    unranked.sort(key=lambda team: (name_key(team["name"]), team["id"]))
    for team in unranked:
        team["rank"] = None
        team["tied"] = False

    awards: list[dict[str, Any]] = []
    for criterion in CRITERIA:
        criterion_id = criterion["id"]
        candidates = [
            team for team in ranked
            if team["scores"][criterion_id] is not None
        ]
        if not candidates:
            awards.append({
                "id": criterion_id,
                "title": criterion["awardTitle"],
                "criterionId": criterion_id,
                "criterionLabel": criterion["label"],
                "blurb": criterion["blurb"],
                "bestScore": None,
                "tied": False,
                "winners": [],
                "runners": [],
            })
            continue

        best = max(team["scores"][criterion_id] for team in candidates)
        winners = [
            team for team in candidates
            if abs(team["scores"][criterion_id] - best) <= EPSILON
        ]
        winners.sort(key=lambda team: (team["rank"], team["id"]))
        rest = [
            team for team in candidates
            if abs(team["scores"][criterion_id] - best) > EPSILON
        ]
        rest.sort(key=lambda team: (
            -team["scores"][criterion_id],
            team["rank"],
            team["id"],
        ))

        def award_entry(team: dict[str, Any]) -> dict[str, Any]:
            return {
                "teamId": team["id"],
                "teamName": team["name"],
                "workTitle": team["workTitle"],
                "rank": team["rank"],
                "score": rounded(team["scores"][criterion_id]),
            }

        for winner in winners:
            winner["awards"].append(criterion_id)

        awards.append({
            "id": criterion_id,
            "title": criterion["awardTitle"],
            "criterionId": criterion_id,
            "criterionLabel": criterion["label"],
            "blurb": criterion["blurb"],
            "bestScore": rounded(best),
            "tied": len(winners) > 1,
            "winners": [award_entry(team) for team in winners],
            "runners": [award_entry(team) for team in rest[:3]],
        })

    def team_payload(team: dict[str, Any]) -> dict[str, Any]:
        return {
            "rank": team["rank"],
            "tied": team["tied"],
            "teamId": team["id"],
            "teamName": team["name"],
            "workTitle": team["workTitle"],
            "ratingCount": team["received"],
            "expectedCount": team["expected"],
            "complete": team["complete"],
            "scores": {
                criterion["id"]: rounded(team["scores"][criterion["id"]])
                for criterion in CRITERIA
            },
            "totalScore": rounded(team["total"]),
            "overallScore": rounded(team["overall"]),
            "awards": team["awards"],
        }

    completeness = {
        "submissionCount": len(used),
        "sourceSubmissionCount": len(submissions),
        "duplicateSubmissionCount": duplicate_submission_count,
        "teamCount": len(teams),
        "rankedTeamCount": len(ranked),
        "unrankedTeamCount": len(unranked),
        "excludedTeamCount": len(excluded_team_ids),
        "excludedSubmissionCount": len(deduped) - len(used),
        "excludedRatingCount": excluded_rating_count,
        "ratingCount": rating_count,
        "judgeTeamCount": len(judge_ids),
        "judgeSubmissionCount": judge_submission_count,
        "expectedTeamCount": expected_team_count,
        "completeTeamCount": complete_team_count,
        "incompleteTeamCount": max(0, expected_team_count - complete_team_count),
        "selfRatingCount": self_rating_count,
        "ignoredKindCount": ignored_kinds,
    }

    return {
        "teams": [team_payload(team) for team in ranked],
        "unranked": [team_payload(team) for team in unranked],
        "awards": awards,
        "stats": completeness,
    }


def convert(csv_path: Path, out_path: Path) -> dict[str, Any]:
    configure_collation()
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    submissions, ignored_kinds, warnings = parse_submissions(csv_path)
    if not submissions:
        raise ValueError("No usable submissions found in the CSV")

    analysis = build_analysis(
        submissions,
        ignored_kinds,
        warnings,
        set(EXCLUDED_TEAMS),
    )

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    row_count = len(rows)
    first_row = rows[0] if rows else {}
    event_id = text(first_row.get("payload.eventId"))
    criteria_version = positive_int(first_row.get("payload.criteriaVersion"))
    try:
        source_csv = csv_path.relative_to(PAGE_ROOT).as_posix()
    except ValueError:
        source_csv = str(csv_path)

    payload = {
        "schemaVersion": 1,
        "event": {
            "id": event_id,
            "criteriaVersion": criteria_version,
        },
        "source": {
            "csv": source_csv,
            "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            "rowCount": row_count,
            "generatedAt": datetime.now().astimezone().replace(microsecond=0).isoformat(),
            "generator": "tools/convert_ranking.py",
        },
        "scoring": {
            "criteria": [
                {
                    "id": criterion["id"],
                    "label": criterion["label"],
                    "awardTitle": criterion["awardTitle"],
                    "maxScore": 10,
                }
                for criterion in CRITERIA
            ],
            "minCriterionScore": 1,
            "maxCriterionScore": 10,
            "maxTotalScore": 40,
            "rankBy": "overallScore",
            "storedPrecision": STORED_PRECISION,
            "displayPrecision": DISPLAY_PRECISION,
            "rankTies": "shared",
        },
        **analysis,
        "excludedTeams": [
            {"teamId": team_id, "teamName": team_name}
            for team_id, team_name in sorted(EXCLUDED_TEAMS.items())
        ],
        "warnings": warnings,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    csv_path = args.csv.expanduser().resolve()
    out_path = args.out.expanduser().resolve()
    payload = convert(csv_path, out_path)
    print(
        f"Wrote {out_path} "
        f"({len(payload['teams'])} ranked teams, "
        f"{len(payload['awards'])} awards, "
        f"{payload['stats']['ratingCount']} ratings)"
    )


if __name__ == "__main__":
    main()
