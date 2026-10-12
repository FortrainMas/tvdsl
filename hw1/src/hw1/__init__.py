import json
import os
import sys
from pathlib import Path

from .dfa import load_json, save_json
from .lexer import build, tokenize

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"

USAGE = """\
  uv run hw1 build         построить автоматы, напечатать размеры, сохранить out/dfa.json и out/dfa_min.json
  uv run hw1 test          прогнать tests.json через ДКА и мин. ДКА, сохранить out/test_results.json
  uv run hw1 lex файл      разбить на токены содержимое файла
  uv run hw1 lex "текст"   разбить на токены строку
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        return cmd_build()
    if command == "test":
        return cmd_test()
    if command == "lex" and len(sys.argv) > 2:
        return cmd_lex(sys.argv[2])
    print(USAGE)
    return 1


def cmd_build():
    nfa, dfa, min_dfa = build()
    print(f"НКА (Томпсон):       {len(nfa.eps)} состояний")
    print(f"ДКА (подмножества):  {len(dfa.trans)} состояний")
    print(f"Мин. ДКА (Хопкрофт): {len(min_dfa.trans)} состояний, ловушка — состояние {min_dfa.trap}")
    OUT.mkdir(exist_ok=True)
    save_json(dfa, OUT / "dfa.json")
    save_json(min_dfa, OUT / "dfa_min.json")
    print("Сохранено: out/dfa.json, out/dfa_min.json")
    return 0


def cmd_test():
    _, dfa, min_dfa = build()
    cases = json.loads((ROOT / "tests.json").read_text(encoding="utf-8"))
    results = []
    for text, expected in cases + alphabet_cases():
        got = kinds(tokenize(min_dfa, text))
        ok = got == expected == kinds(tokenize(dfa, text))
        results.append({"input": text, "expected": expected, "got": got, "status": "PASS" if ok else "FAIL"})
        line = f"{'PASS' if ok else 'FAIL'}  {text!r:42} → {got}"
        print(line if ok else f"{line}   (ожидалось: {expected})")

    OUT.mkdir(exist_ok=True)
    (OUT / "test_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    failed = sum(r["status"] == "FAIL" for r in results)
    print(f"\nИтого: {len(results) - failed}/{len(results)} PASS → out/test_results.json")
    return 1 if failed else 0


def alphabet_cases():
    single = {
        "+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH", "<": "LT", ">": "GT", "=": "ASSIGN",
        "(": "LPAREN", ")": "RPAREN", "[": "LBRACKET", "]": "RBRACKET", "{": "LBRACE", "}": "RBRACE",
        ",": "COMMA", ";": "SEMI", ":": "COLON", "|": "PIPE",
    }
    cases = []
    for ch in [chr(c) for c in range(128)] + ["é", "Ж", "→", " "]:
        if not ch.isascii():
            expected = "ERROR"
        elif ch in " \t\r\n":
            expected = ""
        elif ch.isalpha() or ch == "_":
            expected = "IDENT"
        elif ch.isdigit():
            expected = "INT"
        else:
            expected = single.get(ch, "ERROR")
        cases.append([ch, expected])
    return cases


def kinds(tokens):
    return " ".join(kind for kind, _ in tokens)


def cmd_lex(arg):
    table = OUT / "dfa_min.json"
    if not table.exists():
        print("Сначала запусти: uv run hw1 build")
        return 1
    text = Path(arg).read_text(encoding="utf-8") if os.path.isfile(arg) else arg
    for kind, lexeme in tokenize(load_json(table), text):
        print(f"{kind:12} {lexeme!r}")
    return 0
