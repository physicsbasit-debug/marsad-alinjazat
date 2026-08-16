from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.backup import create_database_backup, restore_database_backup, validate_database_file


def main() -> int:
    parser = argparse.ArgumentParser(description="أدوات صيانة مرصد الإنجازات")
    sub = parser.add_subparsers(dest="command", required=True)

    backup_parser = sub.add_parser("backup", help="إنشاء نسخة SQLite متسقة")
    backup_parser.add_argument("--label", default="manual")

    verify_parser = sub.add_parser("verify", help="فحص نسخة SQLite")
    verify_parser.add_argument("source")

    restore_parser = sub.add_parser("restore", help="استعادة نسخة SQLite بعد إيقاف الخادم")
    restore_parser.add_argument("source")
    restore_parser.add_argument("--confirm", required=True, help="يجب أن تكون RESTORE")

    args = parser.parse_args()
    if args.command == "backup":
        path = create_database_backup(label=args.label)
        if path is None:
            print("لا توجد قاعدة بيانات حالية لإنشاء نسخة منها.")
            return 1
        result = validate_database_file(path)
        print(json.dumps({"path": str(path), **result}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "verify":
        print(json.dumps(validate_database_file(Path(args.source)), ensure_ascii=False, indent=2))
        return 0
    if args.command == "restore":
        print(json.dumps(
            restore_database_backup(Path(args.source), confirmation=args.confirm),
            ensure_ascii=False,
            indent=2,
        ))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
