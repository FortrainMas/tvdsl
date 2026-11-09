import json
import sys
from pathlib import Path

from .lexer import tokenize
from .parser import parse

ROOT = Path(__file__).resolve().parents[2]

USAGE = """\
  uv run hw2 файл.funny       напечатать AST в JSON или ошибки
  uv run hw2 lex файл.funny   напечатать токены с позициями
  uv run hw2 test             прогнать tests/good и tests/bad
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args == ["test"]:
        return run_tests()
    if len(args) == 2 and args[0] == "lex":
        return cmd_lex(read(args[1]))
    if len(args) == 1 and Path(args[0]).is_file():
        return cmd_parse(args[0])
    print(USAGE)
    return 1


def read(path):
    return Path(path).read_text(encoding="utf-8")


def cmd_parse(path):
    ast, errors = parse(read(path))
    if errors:
        for error in errors:
            print(f"{path}:{error}")
        return 1
    print(json.dumps(ast, ensure_ascii=False, indent=2))
    return 0


def cmd_lex(text):
    tokens, errors = tokenize(text)
    for tok in tokens:
        print(f"{tok.line}:{tok.col}\t{tok.kind:10} {tok.text!r}")
    for line, col, msg in errors:
        print(f"{line}:{col}: {msg}")
    return 1 if errors else 0


def run_tests():
    failed = 0
    files = sorted((ROOT / "tests").glob("*/*.funny"))
    for path in files:
        ast, errors = parse(read(path))
        if path.parent.name == "good":
            expected = json.loads(read(path.with_suffix(".json")))
            ok = not errors and ast == expected
            got = errors or "AST отличается от эталона"
        else:
            expected = read(path.with_suffix(".txt")).splitlines()
            ok = errors == expected
            got = errors
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {path.parent.name}/{path.name}")
        if not ok:
            print(f"      получено: {got}")
    print(f"\nИтого: {len(files) - failed}/{len(files)} PASS")
    return 1 if failed else 0
