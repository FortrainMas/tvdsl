from hw2.parser import parse

INT, ARRAY, BOOL, UNKNOWN = "int", "int[]", "bool", "?"


def check(text):
    ast, errors = parse(text)
    if errors:
        return ast, errors
    checker = Checker()
    checker.program(ast)
    return ast, [f"{line}:{col}: {msg}" for line, col, msg in sorted(set(checker.errors))]


class Checker:
    def __init__(self):
        self.errors = []
        self.functions = {}
        self.scopes = []
        self.in_predicate = False

    def error(self, node, msg):
        self.errors.append((node["line"], node["col"], msg))

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def declare(self, var, kind):
        if self.lookup(var["name"]):
            self.error(var, f"имя {var['name']} уже объявлено")
        else:
            self.scopes[-1][var["name"]] = {"type": var["type"], "kind": kind}

    def program(self, ast):
        for item in ast["items"]:
            if item["name"] in self.functions:
                self.error(item, f"{item['name']} уже объявлена")
            else:
                self.functions[item["name"]] = item
        for item in ast["items"]:
            if item["node"] == "formula":
                self.formula(item)
            else:
                self.function(item)

    def formula(self, node):
        self.scopes = [{}]
        for param in node["params"]:
            self.declare(param, "param")
        self.predicate(node["body"])

    def function(self, node):
        self.scopes = [{}]
        for param in node["params"]:
            self.declare(param, "param")
        self.predicate(node["requires"])
        for result in node["returns"]:
            self.declare(result, "return")
        self.predicate(node["ensures"])
        for local in node["uses"]:
            self.declare(local, "local")
        self.statement(node["body"])
        for local in node["uses"]:
            if self.lookup(local["name"])["type"] is None:
                self.error(local, f"не удалось вывести тип {local['name']}: нет ни одного присваивания")
        variables = self.scopes[0].items()
        node["locals"] = [{"name": name, "type": var["type"]} for name, var in variables if var["kind"] == "local"]

    def predicate(self, node):
        if node is not None:
            self.in_predicate = True
            self.expect(node, BOOL, "предикат")
            self.in_predicate = False

    def statement(self, node):
        kind = node["node"]
        if kind == "block":
            for child in node["body"]:
                self.statement(child)
        elif kind == "if":
            self.expect(node["cond"], BOOL, "условие if")
            self.statement(node["then"])
            if node["else"] is not None:
                self.statement(node["else"])
        elif kind == "while":
            self.expect(node["cond"], BOOL, "условие while")
            self.predicate(node["invariant"])
            self.statement(node["body"])
        elif kind in ("assert", "assume"):
            self.predicate(node["cond"])
        else:
            self.assign(node)

    def assign(self, node):
        targets, value = node["targets"], node["value"]
        if len(set(targets)) < len(targets):
            self.error(node, "одна и та же переменная дважды слева от =")
        if value["node"] == "call":
            types = self.call(value)
        else:
            var = self.lookup(targets[0])
            types = [self.expr(value, var["type"] if var else None)]
        if len(types) != len(targets):
            if types != [UNKNOWN]:
                self.error(node, f"слева переменных: {len(targets)}, а {value['name']} возвращает значений: {len(types)}")
            types = [UNKNOWN] * len(targets)
        for name, type_ in zip(targets, types):
            self.store(node, name, type_)

    def store(self, node, name, type_):
        if type_ == BOOL:
            self.error(node["value"], f"нельзя присвоить логическое значение в {name}: у переменных нет типа bool")
            type_ = UNKNOWN
        var = self.lookup(name)
        if var is None:
            self.scopes[-1][name] = {"type": type_, "kind": "local"}
        elif var["kind"] == "param":
            self.error(node, f"параметр {name} только для чтения")
        elif var["type"] in (None, UNKNOWN):
            var["type"] = type_
        elif type_ not in (var["type"], UNKNOWN):
            self.error(node, f"{name} имеет тип {var['type']}, а присваивается {type_}")

    def expect(self, node, want, what):
        got = self.expr(node, want)
        if got not in (want, UNKNOWN):
            self.error(node, f"{what}: ожидался {want}, а получен {got}")

    def expr(self, node, want=None):
        kind = node["node"]
        if kind == "int":
            result = INT
        elif kind == "bool":
            result = BOOL
        elif kind == "var":
            result = self.variable(node, want)
        elif kind == "neg":
            self.expect(node["arg"], INT, "унарный минус")
            result = INT
        elif kind == "not":
            self.expect(node["arg"], BOOL, "not")
            result = BOOL
        elif kind == "binop":
            result = self.binop(node)
        elif kind == "index":
            self.expect(node["array"], ARRAY, "индексация")
            self.expect(node["index"], INT, "индекс массива")
            result = INT
        elif kind == "call":
            result = self.single_value(node)
        else:
            result = self.quantifier(node)
        node["type"] = result
        return result

    def variable(self, node, want):
        name = node["name"]
        var = self.lookup(name)
        if var is None:
            self.error(node, f"имя {name} не объявлено или используется до первого присваивания")
            return UNKNOWN
        if var["type"] is None:
            if want in (INT, ARRAY):
                var["type"] = want
            else:
                self.error(node, f"не удалось вывести тип {name}: чтение до первого присваивания")
                var["type"] = UNKNOWN
        return var["type"]

    def binop(self, node):
        op = node["op"]
        operand = BOOL if op in ("and", "or", "->") else INT
        self.expect(node["left"], operand, f"оператор {op}")
        self.expect(node["right"], operand, f"оператор {op}")
        return INT if op in ("+", "-", "*", "/") else BOOL

    def single_value(self, node):
        types = self.call(node)
        if len(types) > 1:
            self.error(node, f"{node['name']} возвращает значений: {len(types)}, в выражении можно только одно")
            return UNKNOWN
        return types[0]

    def call(self, node):
        name, args = node["name"], node["args"]
        what = [f"аргумент {i} функции {name}" for i in range(1, len(args) + 1)]
        if node.get("sugar"):
            params, types = [ARRAY, INT, INT], [ARRAY]
            what = ["обновление массива", "индекс массива", "значение элемента массива"]
        elif name == "length":
            params, types = [ARRAY], [INT]
        elif name not in self.functions:
            self.error(node, f"неизвестная функция {name}")
            params, types = None, [UNKNOWN]
        elif self.functions[name]["node"] == "formula":
            params, types = self.signature(name), [BOOL]
            if not self.in_predicate:
                self.error(node, f"формулу {name} можно использовать только в предикатах")
                types = [UNKNOWN]
        else:
            params = self.signature(name)
            types = [result["type"] for result in self.functions[name]["returns"]]
        if params is None or len(args) != len(params):
            if params is not None:
                self.error(node, f"{name}: ожидалось аргументов: {len(params)}, а передано: {len(args)}")
            for arg in args:
                self.expr(arg)
        else:
            for arg, param, label in zip(args, params, what):
                self.expect(arg, param, label)
        if node.get("sugar") and args[0]["type"] != ARRAY:
            types = [UNKNOWN]
        node["type"] = types[0] if len(types) == 1 else types
        return types

    def signature(self, name):
        return [param["type"] for param in self.functions[name]["params"]]

    def quantifier(self, node):
        if not self.in_predicate:
            self.error(node, f"квантор {node['node']} можно использовать только в предикатах")
        self.scopes.append({})
        self.declare(node["var"], "bound")
        self.expect(node["body"], BOOL, f"тело {node['node']}")
        self.scopes.pop()
        return BOOL
