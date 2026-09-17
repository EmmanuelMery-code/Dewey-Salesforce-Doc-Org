"""Low-level Apex parsing helpers (comment/string stripping, method-body extraction,
hardcoded-Id detection, recursion detection, SOQL-injection detection, CRUD/FLS
enforcement detection) used by ``src.analyzer.apex_analyzer``.
"""
from __future__ import annotations

import re
from typing import NamedTuple


SALESFORCE_ID_RE = re.compile(r"['\"]([0-9a-zA-Z]{15}|[0-9a-zA-Z]{18})['\"]")
RESERVED_METHOD_NAMES = {
    "if", "for", "while", "do", "switch", "return", "new", "throw",
    "catch", "try", "else", "super", "this",
}
# Une garde de reentrance doit porter un etat *mutable* et *partage* : un champ static
# non final d'un type qui peut memoriser "deja passe ici" (drapeau, compteur, Set/Map d'Ids).
STATIC_GUARD_FIELD_RE = re.compile(
    r"(?im)^[ \t]*((?:(?:public|private|protected|global|static|final|transient)[ \t]+)+)"
    r"(?:Boolean|Integer|Long|Decimal|Set[ \t]*<[^>;{}]*>|Map[ \t]*<[^>;{}]*>)[ \t]+"
    r"(\w+)[ \t]*(?:=[^;{}]*)?;"
)
# Noms qui trahissent une garde, y compris portee par une autre classe
# (ex. `TriggerBypass.skipAll`, `AccountTriggerHandler.isRunning`).
GUARD_NAME_RE = re.compile(
    r"(?i)\b(\w*(?:recursionguard|alreadyprocessed|alreadyrun|isfirstrun|isrunning|"
    r"hasrun|inprogress|recursion|bypass|guard|skip)\w*)\b"
)
TRIGGER_DECLARATION_RE = re.compile(
    r"(?is)\btrigger\s+\w+\s+on\s+\w+\s*\(([^)]+)\)\s*\{"
)
TRIGGER_AFTER_EVENT_RE = re.compile(
    r"(?i)\bafter\s+(?:insert|update|undelete)\b"
)
PROD_ID_PREFIXES = {
    "001",
    "003",
    "005",
    "006",
    "00D",
    "00E",
    "00Q",
    "00T",
    "00U",
    "500",
    "800",
    "701",
    "801",
    "a0",
    "a1",
    "a2",
    "a3",
    "a4",
    "a5",
    "a6",
    "a7",
    "a8",
    "a9",
}


def _find_hardcoded_ids(body: str) -> set[str]:
    found: set[str] = set()
    for match in SALESFORCE_ID_RE.finditer(body):
        raw = match.group(1)
        prefix = raw[:3]
        if prefix in PROD_ID_PREFIXES:
            found.add(raw)
        elif prefix[:2] in {p for p in PROD_ID_PREFIXES if len(p) == 2}:
            found.add(raw)
    return found


def _count_code_lines(body: str) -> int:
    count = 0
    in_block_comment = False
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped[2:]:
                in_block_comment = True
            continue
        if stripped.startswith("//"):
            continue
        count += 1
    return count


def _strip_comments_and_strings(body: str, keep_string_markers: bool = False) -> str:
    """Supprime les commentaires // et /* */ ainsi que les chaines litterales, en conservant les positions (remplacees par des espaces).

    ``keep_string_markers`` conserve les guillemets delimitant les litteraux (contenu toujours
    blanchi) : indispensable pour compter les arguments d'un appel, sinon ``f('a')`` et ``f()``
    deviennent indiscernables.
    """
    out = []
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        nxt = body[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and body[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == "/" and nxt == "*":
            out.append("  ")
            i += 2
            while i < n and not (body[i] == "*" and i + 1 < n and body[i + 1] == "/"):
                out.append(" " if body[i] != "\n" else "\n")
                i += 1
            if i < n:
                out.append("  ")
                i += 2
        elif ch in ('"', "'"):
            quote = ch
            out.append(quote if keep_string_markers else " ")
            i += 1
            while i < n and body[i] != quote:
                if body[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                else:
                    out.append(" " if body[i] != "\n" else "\n")
                    i += 1
            if i < n:
                out.append(quote if keep_string_markers else " ")
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


CLASS_DECLARATION_RE = re.compile(r"(?i)\bclass\s+(\w+)")

METHOD_HEADER_RE = re.compile(
    r"(?m)"
    r"^[ \t]*"
    r"(?:(?:public|private|protected|global)\s+)?"
    r"(?:(?:static|virtual|abstract|override|webservice|final|transient)\s+)*"
    r"(?:[\w<>\[\],\. ]+?)\s+"
    r"(\w+)\s*\(([^;{}]*?)\)\s*"
    r"\{"
)
LOCAL_DECLARATION_RE = re.compile(
    r"(?m)(?:^|[{};(])\s*(?:final\s+)?"
    r"(\w+(?:\s*<[^<>;{}]*(?:<[^<>;{}]*>)?[^<>;{}]*>)?(?:\s*\[\s*\])?)"
    r"\s+(\w+)\s*(?==)"
)
CAST_RE = re.compile(r"^\(\s*(\w+(?:\s*<[^;{}]*>)?)\s*\)\s*\S")
NEW_INSTANCE_RE = re.compile(r"^new\s+(\w+(?:\s*<[^;{}]*>)?(?:\s*\[\s*\])?)\s*[\(\[{]")


class ApexMethod(NamedTuple):
    """Une methode Apex avec sa signature, pour distinguer les surcharges homonymes."""

    name: str
    param_types: tuple[str, ...]
    params_raw: str
    body: str

    @property
    def signature(self) -> str:
        return f"{self.name}({', '.join(self.param_types)})"

    @property
    def param_key(self) -> tuple[str, ...]:
        return tuple(t.lower() for t in self.param_types)


def _split_top_level(text: str) -> list[str]:
    """Decoupe sur les virgules de premier niveau, en respectant (), [], {} et les generiques."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for index, ch in enumerate(text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "<" and index > 0 and (text[index - 1].isalnum() or text[index - 1] == "_"):
            # `Map<String, Object>` est un generique ; `a < b` est une comparaison.
            depth += 1
        elif ch == ">" and depth > 0:
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return parts


def _normalize_type(raw: str) -> str:
    return re.sub(r"\s+", "", raw)


def _parse_parameter_types(params_raw: str) -> tuple[str, ...]:
    """``'Map<String, Object> args, Id recordId'`` -> ``('Map<String,Object>', 'Id')``."""
    if not params_raw.strip():
        return ()
    types: list[str] = []
    for chunk in _split_top_level(params_raw):
        tokens = chunk.strip().split()
        if len(tokens) < 2:
            # Parametre illisible (macro, annotation) : type inconnu.
            types.append("")
            continue
        if tokens[0].lower() == "final":
            tokens = tokens[1:]
        types.append(_normalize_type(" ".join(tokens[:-1])))
    return tuple(types)


def _extract_method_bodies(clean_body: str) -> list[ApexMethod]:
    """Retourne les methodes (nom, types des parametres, corps) du code (commentaires deja retires)."""
    results: list[ApexMethod] = []
    for match in METHOD_HEADER_RE.finditer(clean_body):
        name = match.group(1)
        if name.lower() in RESERVED_METHOD_NAMES:
            continue
        brace_start = match.end() - 1
        depth = 0
        idx = brace_start
        end = brace_start
        while idx < len(clean_body):
            ch = clean_body[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = idx + 1
                    break
            idx += 1
        if end > brace_start:
            results.append(
                ApexMethod(
                    name=name,
                    param_types=_parse_parameter_types(match.group(2)),
                    params_raw=match.group(2),
                    body=clean_body[brace_start:end],
                )
            )
    return results


def _find_recursion_guards(clean: str) -> set[str]:
    """Retourne les identifiants (en minuscules) pouvant servir de garde de reentrance.

    Deux sources :
      - les champs ``static`` non ``final`` d'un type porteur d'etat (Boolean, Integer,
        Set<...>, Map<...>) declares dans le code analyse ;
      - les identifiants dont le nom trahit une garde, meme portee par une autre classe
        (``TriggerBypass.skipAll``, ``AccountTriggerHandler.isRunning``).
    """
    guards: set[str] = set()
    for match in STATIC_GUARD_FIELD_RE.finditer(clean):
        modifiers = match.group(1).lower().split()
        if "static" in modifiers and "final" not in modifiers:
            guards.add(match.group(2).lower())
    guards.update(match.group(1).lower() for match in GUARD_NAME_RE.finditer(clean))
    return guards


def _body_is_guarded(body: str, guards: set[str]) -> bool:
    """Vrai si ``body`` *consulte* une garde, et pas seulement si la classe en declare une.

    Un champ static declare mais jamais teste ne protege rien : on exige une lecture, sous
    forme de condition (``if``/``while``) ou d'interrogation de collection (``contains``).
    """
    for guard in guards:
        name = re.escape(guard)
        read_patterns = (
            rf"(?i)\b(?:if|while)\s*\([^{{;]*\b{name}\b",
            rf"(?i)\b{name}\s*\.\s*(?:contains|containsKey|isEmpty|get)\s*\(",
            rf"(?i)!\s*(?:\w+\s*\.\s*)?{name}\b",
        )
        if any(re.search(pattern, body) for pattern in read_patterns):
            return True
    return False


def _is_self_invocation(method_body: str, call_start: int, class_name: str | None) -> bool:
    """Determine si l'appel qui commence a ``call_start`` cible bien la methode courante.

    Un appel qualifie (``new AccountService().doIt()``, ``svc.doIt()``, ``Other.doIt()``)
    porte le meme nom simple mais designe une autre implementation : seuls les appels
    non qualifies, ``this.doIt()`` et ``MaClasse.doIt()`` sont de l'auto-invocation.
    """
    prefix = method_body[:call_start].rstrip()
    if prefix.endswith("."):
        receiver = prefix[:-1].rstrip()
        if re.search(r"(?<![\w.])this$", receiver):
            return True
        if class_name and re.search(rf"(?<![\w.]){re.escape(class_name)}$", receiver):
            return True
        return False
    return not re.search(r"(?<![\w.])new$", prefix)


def _local_variable_types(method: ApexMethod) -> dict[str, str]:
    """Types connus dans la portee de la methode : ses parametres + ses variables locales."""
    known: dict[str, str] = {}
    for chunk in _split_top_level(method.params_raw):
        tokens = chunk.strip().split()
        if len(tokens) < 2:
            continue
        if tokens[0].lower() == "final":
            tokens = tokens[1:]
        if len(tokens) >= 2:
            known[tokens[-1].lower()] = _normalize_type(" ".join(tokens[:-1]))
    for match in LOCAL_DECLARATION_RE.finditer(method.body):
        declared_type = _normalize_type(match.group(1))
        if declared_type.lower() in {"return", "else", "new", "if", "while", "case"}:
            continue
        known[match.group(2).lower()] = declared_type
    return known


def _infer_argument_type(argument: str, known_types: dict[str, str]) -> str | None:
    """Type de l'expression passee en argument, ou ``None`` si indecidable.

    ``None`` est un resultat normal et fréquent (retour d'appel, expression composee) : il
    conduit la detection a s'abstenir plutot qu'a deviner.
    """
    expr = argument.strip()
    if not expr:
        return None
    if expr.startswith("'") and expr.endswith("'"):
        return "String"
    if re.fullmatch(r"(?i)(?:true|false)", expr):
        return "Boolean"
    if re.fullmatch(r"-?\d+", expr):
        return "Integer"
    if re.fullmatch(r"(?i)-?\d+L", expr):
        return "Long"
    if re.fullmatch(r"-?\d+\.\d+", expr):
        return "Decimal"
    cast = CAST_RE.match(expr)
    if cast:
        return _normalize_type(cast.group(1))
    instantiation = NEW_INSTANCE_RE.match(expr)
    if instantiation:
        return _normalize_type(instantiation.group(1))
    if re.fullmatch(r"\w+", expr):
        return known_types.get(expr.lower())
    return None


def _call_arguments(method_body: str, paren_index: int) -> list[str] | None:
    """Arguments de l'appel dont la parenthese ouvrante est a ``paren_index``, ou None si non equilibre."""
    depth = 0
    for idx in range(paren_index, len(method_body)):
        ch = method_body[idx]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                inner = method_body[paren_index + 1 : idx]
                if not inner.strip():
                    return []
                return _split_top_level(inner)
    return None


def _call_targets_same_signature(
    target: ApexMethod,
    overloads: list[ApexMethod],
    arguments: list[str],
    known_types: dict[str, str],
) -> bool:
    """Vrai si l'appel resout vers ``target`` lui-meme, et non vers une de ses surcharges.

    Le nom ne suffit pas : ``doIt(Id)`` qui appelle ``doIt(Id, Boolean)`` delegue a une autre
    implementation et ne boucle pas. On compare donc l'arite, puis les types quand plusieurs
    surcharges partagent la meme arite. Si un type reste indecidable, on s'abstient.
    """
    if len(arguments) != len(target.param_types):
        return False
    rivals = [m for m in overloads if len(m.param_types) == len(arguments) and m is not target]
    if not rivals:
        return True
    inferred = [_infer_argument_type(arg, known_types) for arg in arguments]
    if any(t is None for t in inferred):
        return False
    return tuple(t.lower() for t in inferred) == target.param_key


def _detect_self_recursive_methods(body: str) -> list[str]:
    """Retourne la liste des noms de methodes qui s'invoquent elles-memes depuis leur propre corps.

    Chaque element retourne est une signature (``walk(Id, Integer)``) : avec les surcharges,
    le nom seul ne designe pas une implementation unique.

    La detection est volontairement conservatrice :
      - on ignore les methodes dont le nom est un mot reserve / courant ;
      - on ignore les appels qualifies vers une homonyme d'une autre classe / instance ;
      - on ignore les appels qui resolvent vers une *surcharge* (arite ou types differents) ;
      - on ignore une methode qui consulte elle-meme une garde de reentrance (la garde est
        evaluee methode par methode : une garde posee ailleurs dans la classe n'arrete pas
        une recursion interne a une autre methode).
    """
    clean = _strip_comments_and_strings(body, keep_string_markers=True)
    guards = _find_recursion_guards(clean)

    class_match = CLASS_DECLARATION_RE.search(clean)
    class_name = class_match.group(1) if class_match else None

    methods = _extract_method_bodies(clean)
    recursive: set[str] = set()
    for method in methods:
        if len(method.name) < 3:
            continue
        if _body_is_guarded(method.body, guards):
            continue
        overloads = [m for m in methods if m.name == method.name]
        known_types = _local_variable_types(method)
        call_re = re.compile(rf"\b{re.escape(method.name)}\s*\(")
        for match in call_re.finditer(method.body):
            if not _is_self_invocation(method.body, match.start(), class_name):
                continue
            arguments = _call_arguments(method.body, match.end() - 1)
            if arguments is None:
                continue
            if _call_targets_same_signature(method, overloads, arguments, known_types):
                recursive.add(method.signature)
                break
    return sorted(recursive)


def _detect_trigger_after_save_recursion(body: str) -> tuple[set[str], str] | None:
    """Detecte un trigger after-save qui modifie ses propres enregistrements declencheurs.

    Retourne :
      - None si le pattern n'est pas detecte ;
      - (events, dml_sample) si le risque existe, ou events est l'ensemble "after insert/update/undelete"
        declare et dml_sample est l'extrait textuel du DML incrimine.
    """
    clean = _strip_comments_and_strings(body)

    header = TRIGGER_DECLARATION_RE.search(clean)
    if not header:
        return None
    events_raw = header.group(1)
    after_events = {
        f"after {m.group(0).split()[-1].lower()}"
        for m in TRIGGER_AFTER_EVENT_RE.finditer(events_raw)
    }
    if not after_events:
        return None

    if _body_is_guarded(clean, _find_recursion_guards(clean)):
        return None

    direct_dml_re = re.compile(
        r"(?i)\b(?:insert|update|upsert|delete|undelete)\s+Trigger\s*\.\s*(?:new|newMap)\b"
    )
    direct_dml_values_re = re.compile(
        r"(?i)\b(?:insert|update|upsert|delete|undelete)\s+Trigger\s*\.\s*newMap\s*\.\s*values\s*\(\s*\)"
    )
    database_dml_re = re.compile(
        r"(?i)\bDatabase\s*\.\s*(?:insert|update|upsert|delete|undelete)\s*\(\s*"
        r"Trigger\s*\.\s*(?:new|newMap\s*\.\s*values\s*\(\s*\))"
    )
    for pat in (direct_dml_values_re, direct_dml_re, database_dml_re):
        match = pat.search(clean)
        if match:
            return after_events, _shorten(match.group(0))

    assign_re = re.compile(
        r"(?i)\b([A-Za-z_]\w*)\s*=\s*Trigger\s*\.\s*(?:new|newMap\s*\.\s*values\s*\(\s*\))"
    )
    aliases = {m.group(1) for m in assign_re.finditer(clean)}
    for alias in aliases:
        alias_direct = re.compile(
            rf"(?i)\b(?:insert|update|upsert|delete|undelete)\s+{re.escape(alias)}\b"
        )
        alias_db = re.compile(
            rf"(?i)\bDatabase\s*\.\s*(?:insert|update|upsert|delete|undelete)\s*\(\s*{re.escape(alias)}\b"
        )
        for pat in (alias_direct, alias_db):
            match = pat.search(clean)
            if match:
                return after_events, _shorten(match.group(0))
    return None


def _shorten(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "..."


def _detect_soql_injection(body: str) -> list[int]:
    """Detect dynamic SOQL queries with potential injection risks."""
    clean = _strip_comments_and_strings(body)
    injection_lines = []

    # Look for Database.query(dynamic_string)
    # We look for concatenation (+) or variable interpolation ($)
    # while excluding String.escapeSingleQuotes
    query_re = re.compile(r"Database\.query\s*\(([^)]+)\)", re.IGNORECASE)

    for match in query_re.finditer(clean):
        arg = match.group(1)
        # If the argument contains concatenation or variable interpolation
        # and doesn't seem to use escapeSingleQuotes or bind variables
        if ("+" in arg or "$" in arg) and "escapesinglequotes" not in arg.lower() and ":" not in arg:
            line_num = body[: match.start()].count("\n") + 1
            injection_lines.append(line_num)

    return injection_lines


def _has_security_enforcement(body: str) -> bool:
    """Check if the class uses any explicit CRUD/FLS enforcement mechanism."""
    clean = _strip_comments_and_strings(body).upper()

    enforcements = [
        "WITH USER_MODE",
        "WITH SYSTEM_MODE",
        "WITH SECURITY_ENFORCED",
        "SECURITY.STRIPINACCESSIBLE",
        "ACCESSLEVEL.USER_MODE",
        "ACCESSLEVEL.SYSTEM_MODE",
        "ISACCESSIBLE(",
        "ISCREATEABLE(",
        "ISUPDATEABLE(",
        "ISDELETABLE(",
    ]

    return any(e in clean for e in enforcements)
