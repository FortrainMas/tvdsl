from collections import namedtuple

from hw1.lexer import SKIP, build

Token = namedtuple("Token", "kind text line col")

DFA = build()[2]


def tokenize(text):
    tokens, errors = [], []
    pos, line, col = 0, 1, 1
    while pos < len(text):
        state, end, kind = DFA.start, pos + 1, "ERROR"
        for i in range(pos, len(text)):
            state = DFA.step(state, text[i])
            if state == DFA.trap:
                break
            if DFA.accept[state]:
                end, kind = i + 1, DFA.accept[state]
        if kind == "COMMENT":
            end = text.find("\n", pos)
            if end == -1:
                end = len(text)
        lexeme = text[pos:end]
        if lexeme == "→":
            kind = "ARROW"
        if kind == "ERROR":
            errors.append((line, col, f"неизвестный символ {lexeme!r}"))
        elif kind == "BAD_INT":
            errors.append((line, col, f"число с ведущим нулём {lexeme!r}"))
            tokens.append(Token("INT", lexeme, line, col))
        elif kind not in SKIP:
            tokens.append(Token(kind, lexeme, line, col))
        if "\n" in lexeme:
            line += lexeme.count("\n")
            col = len(lexeme) - lexeme.rfind("\n")
        else:
            col += len(lexeme)
        pos = end
    tokens.append(Token("EOF", "", line, col))
    return tokens, errors
