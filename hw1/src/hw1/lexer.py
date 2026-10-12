from .dfa import minimize, nfa_to_dfa
from .regex import NFA, regex_to_nfa

KEYWORDS = [
    "function", "requires", "returns", "ensures", "uses", "int", "if", "else", "while", "invariant",
    "assert", "assume", "length", "true", "false", "not", "and", "or", "forall", "exists",
]

TOKENS = [
    ("WS", r"[ \t\r\n]+"),
    ("COMMENT", r"//[^\n]*"),
    *[("KW_" + kw.upper(), kw) for kw in KEYWORDS],
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("INT", r"0|[1-9][0-9]*"),
    ("BAD_INT", r"0[0-9]+"),
    ("EQ", "=="), ("NE", "!="), ("LE", "<="), ("GE", ">="), ("ARROW", "->"), ("FATARROW", "=>"),
    ("LT", "<"), ("GT", ">"), ("ASSIGN", "="),
    ("PLUS", r"\+"), ("MINUS", "-"), ("STAR", r"\*"), ("SLASH", "/"),
    ("LPAREN", r"\("), ("RPAREN", r"\)"), ("LBRACKET", r"\["), ("RBRACKET", r"\]"),
    ("LBRACE", "{"), ("RBRACE", "}"), ("COMMA", ","), ("SEMI", ";"), ("COLON", ":"), ("PIPE", r"\|"),
]

SKIP = {"WS", "COMMENT"}


def build():
    nfa = NFA()
    start = nfa.new_state()
    for i, (_, regex) in enumerate(TOKENS):
        s, e = regex_to_nfa(nfa, regex)
        nfa.eps[start].append(s)
        nfa.accept[e] = i
    dfa = nfa_to_dfa(nfa, start, [name for name, _ in TOKENS])
    return nfa, dfa, minimize(dfa)


def tokenize(dfa, text):
    tokens = []
    pos = 0
    while pos < len(text):
        state, end, kind = dfa.start, pos + 1, "ERROR"
        for i in range(pos, len(text)):
            state = dfa.step(state, text[i])
            if state == dfa.trap:
                break
            if dfa.accept[state]:
                end, kind = i + 1, dfa.accept[state]
        if kind not in SKIP:
            tokens.append((kind, text[pos:end]))
        pos = end
    return tokens
