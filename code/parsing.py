import re


RE_TAG = re.compile(r"\s*\\(mono|chu)")
RE_BARE_TAG = re.compile(r"^\\chu(SolutionB|SolutionC|JCM)\b")
RE_CHU_WRAPPER = re.compile(r"^\\chu\w*\s*\{?")
RE_MONO_NAME = re.compile(r"\\mono\{([^}]*)\}")
RE_COMMENT = re.compile(r"(?i)^(comment|note|\[note\])$")
RE_SOLUTION_LABEL = re.compile(r"(?i)^solution\s+([a-z0-9]+)$")


def read_chu_block(lines, i):
    r"""Accumulate a \chu block starting at line i.

    Returns (text, next_index). Terminates at whichever comes first:
      - the brace that closes an opened block
      - the next line starting with \mono or \chu
      - end of text
    """
    buf, depth, opened = [], 0, False
    for n in range(i, len(lines)):
        line = lines[n]
        if n > i and RE_TAG.match(line):
            return " ".join(buf).strip(), n
        buf.append(line.strip())
        depth += line.count("{") - line.count("}")
        if depth > 0:
            opened = True
        elif opened:
            return " ".join(buf).strip(), n + 1
    return " ".join(buf).strip(), len(lines)


def heading_text(block):
    r"""Strip the \chu wrapper. Returns (tag, text).

    `tag` is the bare-tag name (SolutionB, SolutionC, JCM) when the block uses
    one - those carry their label in the tag rather than the text.
    """
    t = block.strip()
    m = RE_BARE_TAG.match(t)
    if m:
        return m.group(1), t[m.end():].strip().strip("{}").strip()
    while True:
        new = RE_CHU_WRAPPER.sub("", t).strip()
        if new == t:
            break
        t = new
    return None, t.strip("{}").strip()


def is_heading(text):
    """A heading is a short label ending in ':'. Instructions also end in ':'
    when they introduce a list, so length and the absence of a full stop
    separate them."""
    t = text.strip()
    return t.endswith(":") and len(t) < 60 and "." not in t[:-1]


def base_name(s):
    """Reduce a heading or ingredient name to a comparable form."""
    s = re.sub(r"\(see [^)]*\)", "", s)
    s = s.replace("*", "")
    return re.sub(r"[^a-z0-9]", "", s.lower())

def classify_chu(block, ingredient_keys):
    """Classify one \\chu block.

    Returns (kind, label, text) where kind is one of:
      instruction | solution | sub_recipe | comment | needs_review
    or (None, None, None) for an empty spacer block.

    `ingredient_keys` is the set of base_name() values for every \\mono in the
    same medium — a heading is a sub-recipe when its name is among them.
    """
    tag, text = heading_text(block)

    if tag == "JCM":
        return "comment", None, text
    if tag in ("SolutionB", "SolutionC"):
        return "solution", tag[-1], text

    if not text:
        return None, None, None

    if not is_heading(text):
        return "instruction", None, text

    h = text.rstrip(":").strip()
    if RE_COMMENT.match(h):
        return "comment", None, h

    key = base_name(h)
    if key and key in ingredient_keys:
        return "sub_recipe", None, h

    m = RE_SOLUTION_LABEL.match(h)
    if m:
        return "solution", m.group(1).upper(), h

    return "needs_review", None, h


def split_mono(line):
    r"""Extract (name, amount, unit) from a \mono line, respecting nested
    braces. Returns None if the line cannot be read.

    Depth counting is required because component names legitimately contain
    braces: MnSO4·{x}H2O, {Vibrio} suspension, Fe$^{2+}$ solution.
    """
    i = line.find("\\mono")
    if i == -1:
        return None
    j = line.find("{", i)
    if j == -1:
        return None

    depth = 0
    for k in range(j, len(line)):
        if line[k] == "{":
            depth += 1
        elif line[k] == "}":
            depth -= 1
            if depth == 0:
                name, rest = line[j + 1:k], line[k + 1:]
                break
    else:
        return None

    vals = re.findall(r"\{([^{}]*)\}", rest)
    if len(vals) < 2:
        return None
    return name.strip(), vals[0].strip(), vals[1].strip()


def parse_medium(grmd, tex):
    """Walk one medium and return (instructions, compositions).

    Every \\mono is stamped with the id of the \\chu block most recently seen
    above it. A \\mono before any \\chu gets instruction_id = None, meaning a
    base ingredient added before any step.
    """
    lines = tex.splitlines()
    keys = {base_name(m) for m in RE_MONO_NAME.findall(tex)}

    instructions, compositions = [], []
    current = None
    step = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        if "\\mono" in line:
            parsed = split_mono(line)
            if parsed:
                name, amount, unit = parsed
                compositions.append({
                    "medium_id": grmd,
                    "component_name": name,
                    "amount": amount,
                    "unit": unit,
                    "instruction_id": current,
                })
            i += 1

        elif RE_TAG.match(line) and "\\chu" in line:
            block, i = read_chu_block(lines, i)
            kind, label, text = classify_chu(block, keys)
            if kind is None:
                continue                      # spacer
            step += 1
            instructions.append({
                "medium_id": grmd,
                "step_order": step,
                "kind": kind,
                "label": label,
                "text": text,
            })
            current = (grmd, step)            # local key for now

        else:
            i += 1

    return instructions, compositions