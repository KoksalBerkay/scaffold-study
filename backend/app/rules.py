"""Deterministic check for "this memory rule is already there, maybe reworded".

Used before a rule is written to a memory file (the Notes agent's RULEs, the memory updater's rewrites), so the
same preference is never saved twice. Two rules count as the same when, after dropping filler words, word endings
and a few synonyms, almost every word of the new rule is already in the old one, with the same negations ("do not
add X" and "add X" are different rules). A rule that adds real content to an old one is new.
"""
from __future__ import annotations

import re

_STOP = set("""a an the this that these those it its it's to of in on at for by with from into onto as and or but if
then than so be is are was were been being do does did done i me my mine you your yours we our us they them their he
she his her student student's students please also just only any all each every some such which who whom what when
where while there here can could should would will shall may might must have has had having about over under up out
very more most own same other""".split())
_NEG = {"not", "no", "never", "nor", "neither", "without", "avoid", "instead"}
_CONTRACT = [(r"\bcan't\b", "can not"), (r"\bwon't\b", "will not"), (r"n't\b", " not")]
_SYN = {"short": "brief", "concise": "brief", "request": "ask", "delete": "remove", "drop": "remove", "erase": "remove",
        "overwrite": "replace", "always": "", "notes": "note", "add": "add", "include": "add", "put": "add", "write": "add",
        "existing": "exist", "current": "exist", "explicit": "explicitly", "unles": "unless", "except": "unless"}


def _stem(w: str) -> str:
    w = _SYN.get(w, w)
    for suf, rep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            w = w[: -len(suf)] + rep
            break
    return _SYN.get(w, w)


def rule_words(text: str) -> frozenset[str]:
    """The content words of one rule, stemmed. A word right after a negation is marked ("!add" in "do not add"),
    so "do X" and "do not X" differ."""
    t = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    for pat, rep in _CONTRACT:
        t = re.sub(pat, rep, t)
    out, neg = set(), False
    for w in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", t):
        if w in _NEG:
            neg = True
            continue
        if w in _STOP:
            continue
        w = _stem(w)
        if not w:
            continue
        out.add("!" + w if neg else w)
        neg = False
    return frozenset(out)


def same_rule(new: str, old: str) -> bool:
    """True when `new` says nothing that `old` does not already say (the same words up to rewording and word
    endings, with the same negations)."""
    n, o = rule_words(new), rule_words(old)
    if not n or not o:
        return False
    if n == o:
        return True
    if min(len(n), len(o)) < 3:
        return False
    common = len(n & o)
    jaccard = common / len(n | o)
    covered = common / len(n)  # how much of the new rule the old one already says
    return jaccard >= 0.7 or (covered >= 0.8 and jaccard >= 0.5)


def bullets(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^\s*[-*]\s+(.+)$", text, re.M)]


def new_rules(rules: list[str], existing_text: str) -> list[str]:
    """The rules that are really new: not already in `existing_text` (as a bullet or verbatim), and not a repeat of
    an earlier rule in the same list."""
    known = bullets(existing_text)
    low = existing_text.lower()
    out: list[str] = []
    for r in rules:
        r = r.strip().lstrip("-* ").strip()
        if not r or r.lower() in low or any(same_rule(r, k) for k in known + out):
            continue
        out.append(r)
    return out


def drop_repeated_bullets(old_text: str, new_text: str) -> tuple[str, list[str]]:
    """For a whole memory file rewritten by a model: remove bullets that were not in the old file and only repeat
    another bullet of the new file (reworded), and second copies of the same bullet. Returns (text, dropped)."""
    old = {b for b in bullets(old_text)}
    kept_old = [b for b in bullets(new_text) if b in old]  # bullets the file already had always win
    seen: set[str] = set()
    kept_new: list[str] = []
    out, dropped = [], []
    for line in new_text.split("\n"):
        m = re.match(r"^\s*[-*]\s+(.+)$", line)
        if not m:
            out.append(line)
            continue
        b = m.group(1).strip()
        if b in seen or (b not in old and any(same_rule(b, k) for k in kept_old + kept_new)):
            dropped.append(b)
            continue
        seen.add(b)
        if b not in old:
            kept_new.append(b)
        out.append(line)
    return "\n".join(out), dropped
