import json
from pathlib import Path

ALPHABET = [chr(c) for c in range(128)]


class DFA:
    def __init__(self, trans, accept, trap):
        self.trans = trans
        self.accept = accept
        self.trap = trap
        self.start = 0

    def step(self, state, ch):
        return self.trans[state][ord(ch)] if ord(ch) < 128 else self.trap


def eps_closure(nfa, states):
    result, stack = set(states), list(states)
    while stack:
        for t in nfa.eps[stack.pop()]:
            if t not in result:
                result.add(t)
                stack.append(t)
    return frozenset(result)


def nfa_to_dfa(nfa, start, names):
    first = eps_closure(nfa, [start])
    index = {first: 0}
    subsets = [first]
    trans = []
    for subset in subsets:
        row = []
        for ch in ALPHABET:
            moved = [t for s in subset for chars, t in nfa.moves[s] if ch in chars]
            target = eps_closure(nfa, moved)
            if target not in index:
                index[target] = len(subsets)
                subsets.append(target)
            row.append(index[target])
        trans.append(row)

    accept = []
    for subset in subsets:
        tokens = [nfa.accept[s] for s in subset if s in nfa.accept]
        accept.append(names[min(tokens)] if tokens else None)
    return DFA(trans, accept, trap=index[frozenset()])


def minimize(dfa):
    n = len(dfa.trans)
    back = [[[] for _ in range(n)] for _ in ALPHABET]
    for s in range(n):
        for c in range(len(ALPHABET)):
            back[c][dfa.trans[s][c]].append(s)

    groups = {}
    for s in range(n):
        groups.setdefault(dfa.accept[s], set()).add(s)
    blocks = list(groups.values())
    block_of = [0] * n
    for b, members in enumerate(blocks):
        for s in members:
            block_of[s] = b

    work = set(range(len(blocks)))
    while work:
        splitter = blocks[work.pop()]
        for c in range(len(ALPHABET)):
            hit = {}
            for t in splitter:
                for s in back[c][t]:
                    hit.setdefault(block_of[s], set()).add(s)
            for b, inside in hit.items():
                outside = blocks[b] - inside
                if not outside:
                    continue
                blocks[b] = outside
                blocks.append(inside)
                new = len(blocks) - 1
                for s in inside:
                    block_of[s] = new
                if b in work or len(inside) <= len(outside):
                    work.add(new)
                else:
                    work.add(b)

    number = {}
    for s in range(n):
        number.setdefault(block_of[s], len(number))
    some_state = {number[block_of[s]]: s for s in range(n)}
    trans = [[number[block_of[t]] for t in dfa.trans[some_state[i]]] for i in range(len(number))]
    accept = [dfa.accept[some_state[i]] for i in range(len(number))]
    return DFA(trans, accept, trap=number[block_of[dfa.trap]])


def save_json(dfa, path):
    rows = ",\n    ".join(json.dumps(row) for row in dfa.trans)
    Path(path).write_text(
        "{\n"
        '  "alphabet": "ASCII 0..127; символ с кодом >= 128 ведёт в trap",\n'
        f'  "start": {dfa.start},\n'
        f'  "trap": {dfa.trap},\n'
        f'  "accept": {json.dumps(dfa.accept)},\n'
        f'  "transitions": [\n    {rows}\n  ]\n'
        "}\n",
        encoding="utf-8",
    )


def load_json(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return DFA(data["transitions"], data["accept"], data["trap"])
