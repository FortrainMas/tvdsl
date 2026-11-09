from hw1.lexer import TOKENS

from .lexer import tokenize

SHOW = {name: repr(regex.replace("\\", "")) for name, regex in TOKENS}
SHOW.update(IDENT="имя", INT="число", EOF="конец файла")

COMPARE = ("EQ", "NE", "LT", "LE", "GT", "GE")


class ParseError(Exception):
    pass


def parse(text):
    tokens, errors = tokenize(text)
    parser = Parser(tokens)
    ast = parser.program()
    return ast, [f"{line}:{col}: {msg}" for line, col, msg in sorted(set(errors + parser.errors))]


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.errors = []

    def at(self, *kinds):
        return self.tokens[self.pos].kind in kinds

    def take(self):
        tok = self.tokens[self.pos]
        if tok.kind != "EOF":
            self.pos += 1
        return tok

    def expect(self, kind):
        if not self.at(kind):
            self.fail(SHOW[kind])
        return self.take()

    def fail(self, expected):
        tok = self.tokens[self.pos]
        got = SHOW["EOF"] if tok.kind == "EOF" else repr(tok.text)
        raise ParseError((tok.line, tok.col, f"ожидалось {expected}, а встретилось {got}"))

    def skip(self):
        depth = 0
        while not self.at("EOF"):
            kind = self.tokens[self.pos].kind
            if kind == "RBRACE" and depth == 0:
                return
            self.pos += 1
            if kind == "LBRACE":
                depth += 1
            elif kind == "RBRACE":
                depth -= 1
                if depth == 0:
                    return
            elif kind == "SEMI" and depth == 0:
                return

    def comma_list(self, item):
        items = [item()]
        while self.at("COMMA"):
            self.take()
            items.append(item())
        return items

    def program(self):
        items = []
        if self.at("EOF"):
            self.errors.append((1, 1, "пустая программа: нет ни одной функции"))
        while not self.at("EOF"):
            start = self.pos
            try:
                items.append(self.item())
            except ParseError as error:
                self.errors.append(error.args[0])
                self.skip()
                if self.pos == start:
                    self.take()
        return {"node": "program", "items": items}

    def item(self):
        if self.at("KW_FUNCTION"):
            self.take()
        name = self.expect("IDENT").text
        self.expect("LPAREN")
        params = [] if self.at("RPAREN") else self.comma_list(self.var_def)
        self.expect("RPAREN")
        if self.at("FATARROW"):
            self.take()
            body = self.expr()
            self.expect("SEMI")
            return {"node": "formula", "name": name, "params": params, "body": body}
        requires = ensures = None
        uses = []
        if self.at("KW_REQUIRES"):
            self.take()
            requires = self.expr()
        self.expect("KW_RETURNS")
        returns = self.comma_list(self.var_def)
        if self.at("KW_ENSURES"):
            self.take()
            ensures = self.expr()
        if self.at("KW_USES"):
            self.take()
            uses = self.comma_list(lambda: self.var_def(typed=False))
        return {
            "node": "function",
            "name": name,
            "params": params,
            "requires": requires,
            "returns": returns,
            "ensures": ensures,
            "uses": uses,
            "body": self.statement(),
        }

    def var_def(self, typed=True):
        name = self.expect("IDENT").text
        if not typed and not self.at("COLON"):
            return {"name": name, "type": None}
        self.expect("COLON")
        self.expect("KW_INT")
        if not self.at("LBRACKET"):
            return {"name": name, "type": "int"}
        self.take()
        self.expect("RBRACKET")
        return {"name": name, "type": "int[]"}

    def statement(self):
        if self.at("LBRACE"):
            return self.block()
        if self.at("KW_IF"):
            self.take()
            self.expect("LPAREN")
            cond = self.expr()
            self.expect("RPAREN")
            then = self.statement()
            other = None
            if self.at("KW_ELSE"):
                self.take()
                other = self.statement()
            return {"node": "if", "cond": cond, "then": then, "else": other}
        if self.at("KW_WHILE"):
            self.take()
            self.expect("LPAREN")
            cond = self.expr()
            self.expect("RPAREN")
            invariant = None
            if self.at("KW_INVARIANT"):
                self.take()
                invariant = self.expr()
            return {"node": "while", "cond": cond, "invariant": invariant, "body": self.statement()}
        if self.at("KW_ASSERT", "KW_ASSUME"):
            kind = self.take().text
            cond = self.expr()
            self.expect("SEMI")
            return {"node": kind, "cond": cond}
        if self.at("IDENT"):
            return self.assignment()
        self.fail("оператор")

    def block(self):
        self.expect("LBRACE")
        body = []
        while not self.at("RBRACE", "EOF"):
            try:
                body.append(self.statement())
            except ParseError as error:
                self.errors.append(error.args[0])
                self.skip()
        self.expect("RBRACE")
        return {"node": "block", "body": body}

    def assignment(self):
        name = self.take().text
        if self.at("LBRACKET"):
            indices = []
            while self.at("LBRACKET"):
                self.take()
                indices.append(self.expr())
                self.expect("RBRACKET")
            self.expect("ASSIGN")
            value = self.expr()
            self.expect("SEMI")
            for k in reversed(range(len(indices))):
                array = {"node": "var", "name": name}
                for index in indices[:k]:
                    array = {"node": "index", "array": array, "index": index}
                value = {"node": "call", "name": "set", "args": [array, indices[k], value]}
            return {"node": "assign", "targets": [name], "value": value}
        targets = [name]
        while self.at("COMMA"):
            self.take()
            targets.append(self.expect("IDENT").text)
        self.expect("ASSIGN")
        start = self.tokens[self.pos]
        value = self.expr()
        if len(targets) > 1 and value["node"] != "call":
            raise ParseError((start.line, start.col, "справа от x, y = должен быть вызов функции"))
        self.expect("SEMI")
        return {"node": "assign", "targets": targets, "value": value}

    def expr(self):
        left = self.or_expr()
        if self.at("ARROW"):
            self.take()
            return {"node": "binop", "op": "->", "left": left, "right": self.expr()}
        return left

    def or_expr(self):
        left = self.and_expr()
        while self.at("KW_OR"):
            self.take()
            left = {"node": "binop", "op": "or", "left": left, "right": self.and_expr()}
        return left

    def and_expr(self):
        left = self.not_expr()
        while self.at("KW_AND"):
            self.take()
            left = {"node": "binop", "op": "and", "left": left, "right": self.not_expr()}
        return left

    def not_expr(self):
        if self.at("KW_NOT"):
            self.take()
            return {"node": "not", "arg": self.not_expr()}
        left = self.sum()
        if self.at(*COMPARE):
            op = self.take().text
            return {"node": "binop", "op": op, "left": left, "right": self.sum()}
        return left

    def sum(self):
        left = self.term()
        while self.at("PLUS", "MINUS"):
            op = self.take().text
            left = {"node": "binop", "op": op, "left": left, "right": self.term()}
        return left

    def term(self):
        left = self.unary()
        while self.at("STAR", "SLASH"):
            op = self.take().text
            left = {"node": "binop", "op": op, "left": left, "right": self.unary()}
        return left

    def unary(self):
        if self.at("MINUS"):
            self.take()
            return {"node": "neg", "arg": self.unary()}
        return self.atom()

    def atom(self):
        tok = self.tokens[self.pos]
        if self.at("INT"):
            self.take()
            return {"node": "int", "value": int(tok.text)}
        if self.at("KW_TRUE", "KW_FALSE"):
            self.take()
            return {"node": "bool", "value": tok.kind == "KW_TRUE"}
        if self.at("LPAREN"):
            self.take()
            inner = self.expr()
            self.expect("RPAREN")
            return inner
        if self.at("KW_FORALL", "KW_EXISTS"):
            self.take()
            self.expect("LPAREN")
            var = self.var_def()
            self.expect("PIPE")
            body = self.expr()
            self.expect("RPAREN")
            return {"node": tok.text, "var": var, "body": body}
        if self.at("IDENT", "KW_LENGTH"):
            self.take()
            if tok.kind == "KW_LENGTH" or self.at("LPAREN"):
                self.expect("LPAREN")
                args = [] if self.at("RPAREN") else self.comma_list(self.expr)
                self.expect("RPAREN")
                return {"node": "call", "name": tok.text, "args": args}
            node = {"node": "var", "name": tok.text}
            while self.at("LBRACKET"):
                self.take()
                node = {"node": "index", "array": node, "index": self.expr()}
                self.expect("RBRACKET")
            return node
        self.fail("выражение")
