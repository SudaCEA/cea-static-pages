"""Generate the per-work media fixture used by the mirror-2610 detail page.

Each work record binds one team from ``data/ranking.json`` to:

    description  short intro copy shown in the left rail
    video        optional clip source for the video panel
    links        optional download / play / project URLs

The availability pattern below is deterministic so the page can show every
combination (video only, links only, nothing) while the real submissions are
still being collected.

Usage:
    .venv\\Scripts\\python.exe gamejam\\tools\\generate_works.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "mirror-2610" / "data"
RANKING_FILE = DATA_DIR / "ranking.json"
WORKS_FILE = DATA_DIR / "works.json"

SCHEMA_VERSION = 1
VIDEO_SRC = "assets/video-placeholder.mp4"
LINK_BASE = "https://example.com/cea-gamejam-2026/works"

DESCRIPTION_TEMPLATES = (
    "《{work}》由「{team}」在 48 小时内完成。作品围绕「镜」展开，"
    "把反射、时间与操作手感拧成同一条线索。",
    "「{team}」的《{work}》把镜面当作关卡本身：每一次反射都会改变路线，"
    "玩家需要在倒影与现实之间往返。",
    "《{work}》是「{team}」的限时作品。核心玩法建立在一面会记忆的镜子上，"
    "走过的路径会在倒影里重演。",
    "「{team}」用《{work}》回答同一个题目：如果镜子比你先一步行动，"
    "你还能相信看到的方向吗？",
)

# Deterministic availability so every state is reachable with a few steps.
def has_video(index: int) -> bool:
    return index % 3 != 2


def has_download(index: int) -> bool:
    return index % 4 != 3


def has_play(index: int) -> bool:
    return index % 3 != 1


def has_project(index: int) -> bool:
    return index % 2 == 0


def build_works(ranking: dict) -> list[dict]:
    works = []
    for index, team in enumerate(ranking.get("teams", [])):
        team_id = team.get("teamId")
        work_title = team.get("workTitle") or "未命名作品"
        team_name = team.get("teamName") or "未知队伍"
        slug = f"{team_id:02d}"

        links = {
            "download": (
                f"{LINK_BASE}/{slug}/build.zip" if has_download(index) else None
            ),
            "play": f"{LINK_BASE}/{slug}/play" if has_play(index) else None,
            "project": f"{LINK_BASE}/{slug}" if has_project(index) else None,
        }

        works.append({
            "teamId": team_id,
            "workTitle": work_title,
            "teamName": team_name,
            "description": DESCRIPTION_TEMPLATES[index % len(DESCRIPTION_TEMPLATES)]
            .format(work=work_title, team=team_name),
            "video": {"src": VIDEO_SRC} if has_video(index) else None,
            "links": links,
        })
    return works


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the committed fixture differs from a fresh generation",
    )
    args = parser.parse_args()

    ranking = json.loads(RANKING_FILE.read_text(encoding="utf-8"))
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone(timedelta(hours=8))).isoformat(
            timespec="seconds"
        ),
        "generator": "tools/generate_works.py",
        "source": "mirror-2610/data/ranking.json",
        "note": "测试数据：视频与链接均为占位，等待真实投稿替换",
        "works": build_works(ranking),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if args.check:
        current = WORKS_FILE.read_text(encoding="utf-8") if WORKS_FILE.is_file() else ""
        if current.split('"generatedAt"')[0] + current.split('"note"')[-1] != \
                text.split('"generatedAt"')[0] + text.split('"note"')[-1]:
            print(f"{WORKS_FILE} is out of date; rerun without --check")
            return 1
        print(f"{WORKS_FILE} is up to date")
        return 0

    WORKS_FILE.write_text(text, encoding="utf-8")
    videos = sum(1 for work in payload["works"] if work["video"])
    links = sum(
        1
        for work in payload["works"]
        for value in work["links"].values()
        if value
    )
    print(f"wrote {WORKS_FILE.relative_to(ROOT)}: {len(payload['works'])} works, "
          f"{videos} with video, {links} links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
