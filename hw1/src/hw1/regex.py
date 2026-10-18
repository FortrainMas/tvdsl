class NFA:
    def __init__(self):
        self.eps = []
        self.moves = []
        self.accept = {}

    def new_state(self):
        self.eps.append([])
        self.moves.append([])
        return len(self.eps) - 1


ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}


class Parser:
    def __init__(self, nfa, text):
        self.nfa, self.text, self.pos = nfa, text, 0

    def peek(self):
        return self.text[self.pos] if self.pos < len(self.text) else None

    def take(self):
        ch = self.peek()
        if ch is None:
            raise ValueError(f"неожиданный конец регулярки {self.text!r}")
        self.pos += 1
        return ch

    def parse(self):
        frag = self.alt()
        if self.pos != len(self.text):
            raise ValueError(f"лишний символ {self.peek()!r} в регулярке {self.text!r}")
        return frag

    def alt(self):
        frags = [self.concat()]
        while self.peek() == "|":
            self.pos += 1
            frags.append(self.concat())
        if len(frags) == 1:
            return frags[0]
        start, end = self.nfa.new_state(), self.nfa.new_state()
        for s, e in frags:
            self.nfa.eps[start].append(s)
            self.nfa.eps[e].append(end)
        return start, end

    def concat(self):
        start = end = self.nfa.new_state()
        while self.peek() not in (None, "|", ")"):
            s, e = self.repeat()
            self.nfa.eps[end].append(s)
            end = e
        return start, end

    def repeat(self):
        s, e = self.atom()
        while self.peek() in ("*", "+", "?"):
            op = self.take()
            start, end = self.nfa.new_state(), self.nfa.new_state()
            self.nfa.eps[start].append(s)
            self.nfa.eps[e].append(end)
            if op in "*+":
                self.nfa.eps[e].append(s)
            if op in "*?":
                self.nfa.eps[start].append(end)
            s, e = start, end
        return s, e

    def atom(self):
        ch = self.take()
        if ch == "(":
            frag = self.alt()
            if self.take() != ")":
                raise ValueError(f"ожидалась ')' в регулярке {self.text!r}")
            return frag
        if ch == "[":
            chars = self.char_class()
        elif ch == "\\":
            chars = {self.escape()}
        elif ch in "*+?)]|":
            raise ValueError(f"неожиданный {ch!r} в регулярке {self.text!r}")
        else:
            chars = {ch}
        s, e = self.nfa.new_state(), self.nfa.new_state()
        self.nfa.moves[s].append((frozenset(chars), e))
        return s, e

    def char_class(self):
        negate = self.peek() == "^"
        if negate:
            self.pos += 1
        chars = set()
        while (ch := self.take()) != "]":
            if ch == "\\":
                ch = self.escape()
            if self.peek() == "-" and self.text[self.pos + 1 : self.pos + 2] not in ("", "]"):
                self.pos += 1
                hi = self.take()
                if hi == "\\":
                    hi = self.escape()
                chars |= {chr(c) for c in range(ord(ch), ord(hi) + 1)}
            else:
                chars.add(ch)
        if negate:
            chars = {chr(c) for c in range(128)} - chars
        return chars

    def escape(self):
        ch = self.take()
        return ESCAPES.get(ch, ch)


def regex_to_nfa(nfa, text):
    return Parser(nfa, text).parse()
