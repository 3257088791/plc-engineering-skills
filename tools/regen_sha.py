#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重算 assets/ 下校验脚本的 SHA256SUMS.txt。

改动 skills/*/assets/ 里的 .py 后必须运行，否则 auto-flow-master-00 的 G5-07 门禁
（复制前比对哈希）会判 E14_SELFCHECK_FAIL。

用法：python tools/regen_sha.py [--skills <技能根目录>]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TARGETS = {
    "auto-flow-master-00/assets/checkers": ["check_stage4.py", "check_stage5.py"],
    "sim-trace-05/assets": ["validate_stage5.py"],
    "eval-archive-06/assets": [
        "stage6_collect.py", "stage6_render.py", "validate_stage6.py",
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills", default=None)
    a = ap.parse_args()
    root = Path(a.skills) if a.skills else Path(__file__).resolve().parent.parent / "skills"
    if not root.is_dir():
        print(f"FAIL\n - 技能目录不存在：{root}")
        return 2

    for rel, files in TARGETS.items():
        d = root / rel
        if not d.is_dir():
            print(f"SKIP  {rel}（目录不存在）")
            continue
        lines = []
        for name in files:
            p = d / name
            if not p.is_file():
                print(f"SKIP  {rel}/{name}（文件不存在）")
                continue
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {name}")
        if lines:
            p = d / "SHA256SUMS.txt"
            with p.open("w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + "\n")
            print(f"WROTE {rel}/SHA256SUMS.txt  ({len(lines)} 项)")
    return 0


if __name__ == "__main__":
    sys.exit(main())