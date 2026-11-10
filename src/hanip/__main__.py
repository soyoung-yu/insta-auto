"""CLI: python -m hanip run | approve | preview | status | curriculum [--count N] [--force]"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import truststore


def _setup_logging(repo: Path) -> None:
    logs = repo / "logs"
    logs.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(logs / f"{date.today().isoformat()}.log", encoding="utf-8"), logging.StreamHandler()],
    )


def main(argv: list[str] | None = None) -> int:
    # Trust the macOS keychain (corporate TLS inspection) while keeping verification on.
    truststore.inject_into_ssl()

    from hanip.config import load_settings
    from hanip.curriculum import generate_curriculum, load_curriculum, save_curriculum
    from hanip.notify import open_file
    from hanip.pipeline import approve, run_daily
    from hanip.state import load_state, next_number, theme_for

    ap = argparse.ArgumentParser(prog="hanip")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="오늘 분량 생성 (평일 9시 launchd)")
    sub.add_parser("approve", help="오늘 승인 대기 중인 게시물 올리기")
    sub.add_parser("preview", help="승인 대기 중인 미리보기 다시 열기")
    sub.add_parser("status", help="현재 진행 상황")
    cur = sub.add_parser("curriculum", help="커리큘럼 생성")
    cur.add_argument("--count", type=int, default=60)
    cur.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    settings = load_settings()
    _setup_logging(settings.repo_dir)
    state = load_state(settings.state_path)

    if args.cmd == "run":
        print(run_daily(settings, today=date.today()).value)
        return 0
    if args.cmd == "approve":
        outcome = approve(settings, today=date.today())
        if outcome.value == "nothing_to_approve":
            print("오늘 승인할 게시물이 없어요. 날짜가 지난 미리보기는 다음 실행에서 다시 만들어요.")
        print(outcome.value)
        return 0 if outcome.value in ("published", "nothing_to_approve") else 1
    if args.cmd == "preview":
        if not state.pending:
            print("승인 대기 중인 게시물이 없어요.")
            return 1
        open_file(Path(state.pending.dir) / "preview.html")
        return 0
    if args.cmd == "status":
        n = next_number(state)
        topics = load_curriculum(settings.curriculum_path) if settings.curriculum_path.exists() else []
        nxt = topics[state.curriculum_index].title_ko if state.curriculum_index < len(topics) else "(커리큘럼 없음/소진)"
        print(f"다음 회차: No.{n:02d} ({theme_for(n)}) · 주제: {nxt}")
        print(f"게시 완료: {state.published_count}회 · 커리큘럼 위치: {state.curriculum_index}/{len(topics)}")
        if state.pending:
            print(f"승인 대기: No.{state.pending.number:02d} ({state.pending.date}) → python -m hanip approve")
        for h in state.history[-5:]:
            print(f"  No.{h.number:02d} {h.date} {h.topic_id} {h.theme} {h.media_id}")
        return 0
    if args.cmd == "curriculum":
        if settings.curriculum_path.exists() and not args.force:
            print(f"{settings.curriculum_path} 이 이미 있어요. 덮어쓰려면 --force")
            return 1
        topics = generate_curriculum(args.count)
        save_curriculum(topics, settings.curriculum_path)
        print(f"{len(topics)}개 주제를 저장했어요: {settings.curriculum_path}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
