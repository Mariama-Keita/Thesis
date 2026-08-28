"""
Parse cleaned medium LaTeX into four relational tables.

Input:  data/medium_clean.csv  (from cleaning.py)
Output: medium, component, instruction, composition

    from parsing import build_tables
    tables = build_tables(clean_df)

The six primitives below do the reading; `parse_medium` walks one medium and
emits rows; `build_tables` runs the walk over the whole dataset and assembles
the four tables.
"""
# new parser
import re
import pandas as pd


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

RE_TAG = re.compile(r"\s*\\(mono|chu)")
RE_BARE_TAG = re.compile(r"^\\chu(SolutionB|SolutionC|JCM)\b")
RE_CHU_WRAPPER = re.compile(r"^\\chu\w*\s*\{?")
RE_MONO_NAME = re.compile(r"\\mono\{([^}]*)\}")
RE_COMMENT = re.compile(r"(?i)^(comment|note|\[note\])$")
RE_SOLUTION_LABEL = re.compile(r"(?i)^solution\s+([a-z0-9]+)$")

RE_MEDIUM_REF = re.compile(r"\(see (?:Medium|JCM Medium) No\.?\s*\[?(\d+)\]?\)", re.I)
RE_SEE_BELOW = re.compile(r"\(see below\)", re.I)

RE_REF_TEXT = re.compile(
    r"(?i)use.*medium no|prepare.*medium no|see medium no|use.*available|"
    r"prepare.*agar|use aquifex|use solution a of|use vero|use jcm"
)
RE_SOL_TEXT = re.compile(r"(?i)solution\s+[a-zA-Z0-9]+:|basic.*solution:|fwm solution")


# ---------------------------------------------------------------------------
# The six primitives
# ---------------------------------------------------------------------------

def read_chu_block(lines, i):
    r"""Accumulate a \chu block starting at line i.

    Returns (text, next_index). Terminates at whichever comes first:
      1. the brace that closes an opened block
      2. the next line starting with \mono or \chu
      3. end of text

    Rule 2 exists because the brace is unreliable: 28 mediums have \chu blocks
    with no closing brace, and bare tags (\chuJCM, \chuSolutionB) open no brace
    at all. The `opened` flag is required for the same reason — without it a
    bare tag terminates immediately, since its depth never goes positive.
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
    one — those carry their label in the tag rather than in the text, so they
    must be caught before the wrapper is stripped (the wrapper pattern's `\w*`
    would otherwise swallow the label).

    Source defects handled: `\chu{\chu{X:}` (tag typed twice, medium 1209) and
    `\chu{{X:}}` (doubled braces, medium 995).
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
    """A heading is a short label ending in ':'.

    The colon alone is not enough — instructions end in ':' too when they
    introduce a list ("add the following solutions:"). That misclassified 521
    blocks. Length and the absence of a full stop separate them: a heading is
    a label, an instruction is a sentence.
    """
    t = text.strip()
    return t.endswith(":") and len(t) < 60 and "." not in t[:-1]


def base_name(s):
    """Reduce a heading or component name to a comparable form.

    Compared with `==`, never `in`. Substring matching produced false
    positives: 'Solution A' normalised to 'solutiona', which appears inside
    '5% K2HPO4 solution (autoclaved)' once spaces are stripped, because the
    'a' of 'autoclaved' fuses onto 'solution'.
    """
    s = RE_MEDIUM_REF.sub("", s)
    s = RE_SEE_BELOW.sub("", s)
    s = s.replace("*", "")
    return re.sub(r"[^a-z0-9]", "", s.lower())


def strip_reference(name):
    """Remove '(see …)' pointers so a component name is just the name.

    'Trace vitamins* (see Medium No. [197])' -> 'Trace vitamins'. Without this
    the same substance appears as several distinct components depending on
    which medium it was cited from.
    """
    s = RE_MEDIUM_REF.sub("", name)
    s = RE_SEE_BELOW.sub("", s)
    s = s.replace("*", "")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,;])", r"\1", s)
    return s.strip().rstrip(",").strip()


def split_mono(line):
    r"""Extract (name, amount, unit) from a \mono line. None if unreadable.

    Depth counting is required because component names legitimately contain
    braces: MnSO4·{x}H2O (variable hydration), {Vibrio} suspension (genus),
    Fe$^{2+}$ solution (ionic charge). A flat `[^}]+` pattern stops at the
    first inner brace and truncates the name.
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


def classify_chu(block, ingredient_keys):
    r"""Classify one \chu block into (kind, label, text).

    kind: instruction | solution | sub_recipe | comment | needs_review
    or (None, None, None) for an empty `\chu{}` spacer.

    `ingredient_keys` is the set of base_name() values for every \mono in the
    same medium. A heading is a sub-recipe when its name is among them — the
    heading text alone cannot decide it, because `Solution A:` (a part of the
    medium) and `Mineral solution A:` (a sub-recipe) are indistinguishable by
    shape. Only the ingredient list separates them.
    """
    tag, text = heading_text(block)

    if tag == "JCM":
        return "comment", None, text
    if tag in ("SolutionB", "SolutionC"):
        return "solution", tag[-1], f"Solution {tag[-1]}"

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


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------

def parse_medium(grmd, tex):
    r"""Walk one medium, returning (instructions, compositions).

    Every \mono is stamped with the step number of the \chu block most
    recently seen above it. A \mono appearing before any \chu gets step=None,
    meaning a base component — in the pot before any step. 954 mediums have
    base components; the 211 that open with \chu do not.
    """
    lines = tex.splitlines()
    keys = {base_name(m) for m in RE_MONO_NAME.findall(tex)}

    instructions, compositions = [], []
    current, step, i = None, 0, 0

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
                    "step": current,
                })
            i += 1

        elif RE_TAG.match(line) and "\\chu" in line:
            block, i = read_chu_block(lines, i)
            kind, label, text = classify_chu(block, keys)
            if kind is None:
                continue
            step += 1
            instructions.append({
                "medium_id": grmd,
                "step_order": step,
                "kind": kind,
                "label": label,
                "text": text,
            })
            current = step

        else:
            i += 1

    return instructions, compositions


# ---------------------------------------------------------------------------
# Medium type
# ---------------------------------------------------------------------------

def medium_type(tex):
    r"""Label what kind of medium this is.

    standard  — starts with \mono: its own recipe
    solution  — built from Solution A/B/C, no base components
    reference — a modification of another medium, few components of its own
    unique    — neither (a cell-culture source; autoclaved distilled water)

    The categories overlap in reality: 40 mediums match both the solution and
    reference patterns. This resolves that by priority order, which is a
    simplification. The column's purpose is to explain why a medium has few or
    no composition rows — a `reference` medium is a pointer, not missing data.
    """
    t = tex.strip()
    if t.startswith("\\mono"):
        return "standard"
    if RE_SOL_TEXT.search(t):
        return "solution"
    if RE_REF_TEXT.search(t):
        return "reference"
    return "unique"


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------

def resolve_references(comp_df, instr_df, medium_names):
    r"""Classify each component's pointer, adding ref_medium_id and ref_type.

    A component name may carry a pointer: `Trace vitamins (see Medium No.
    [197])`. Resolving it takes two lookups — which medium, and which part of
    it. Medium 197 is a full medium containing a `\chu{Trace vitamins:}`
    heading, so the number alone is not enough.

    ref_type:
      internal   a heading in THIS medium defines the component
      sub_recipe a heading in the CITED medium defines it
      whole      the component IS the cited medium (its name matches md_name)
      unresolved cites a medium, but matches neither a heading nor its name
      external   says "(see below)" but no local heading matches
      None       a plain chemical, no pointer

    `whole` was discovered by noticing that unresolvable references whose
    target had zero headings had names matching the target's own name:
    'Marine agar 2216' -> medium 118 'MARINE AGAR 2216'.
    """
    sub_keys = {}
    for r in instr_df[instr_df["kind"].isin(["sub_recipe", "needs_review"])].itertuples():
        sub_keys.setdefault(r.medium_id, set()).add(base_name(r.text))

    local_keys = {}
    for r in instr_df[instr_df["kind"] == "sub_recipe"].itertuples():
        local_keys.setdefault(r.medium_id, set()).add(base_name(r.text))

    name_keys = {k: base_name(str(v)) for k, v in medium_names.items() if pd.notna(v)}

    def classify(row):
        key = base_name(row["clean_name"])

        if key in local_keys.get(row["medium_id"], set()):
            return "internal"

        if pd.isna(row["ref_medium_id"]):
            return "external" if row["ref_below"] else None

        target = int(row["ref_medium_id"])
        if key in sub_keys.get(target, set()):
            return "sub_recipe"
        if key and key == name_keys.get(target):
            return "whole"
        return "unresolved"

    comp_df = comp_df.copy()
    comp_df["ref_medium_id"] = comp_df["component_name"].str.extract(RE_MEDIUM_REF)[0]
    comp_df["ref_below"] = comp_df["component_name"].str.contains(RE_SEE_BELOW)
    comp_df["clean_name"] = comp_df["component_name"].apply(strip_reference)
    comp_df["ref_type"] = comp_df.apply(classify, axis=1)
    return comp_df


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def build_tables(clean_df, source_col="tex_text_clean"):
    """Run the walk over every medium and assemble the four tables.

    Returns a dict of dataframes: medium, component, instruction, composition.
    """
    all_ins, all_comp = [], []
    for row in clean_df.itertuples():
        tex = getattr(row, source_col)
        ins, comp = parse_medium(row.grmd, tex)
        all_ins.extend(ins)
        all_comp.extend(comp)

    instr_df = pd.DataFrame(all_ins)
    comp_df = pd.DataFrame(all_comp)

    medium_df = pd.DataFrame({
        "medium_id": clean_df["grmd"].values,
        "name": clean_df["md_name"].values,
        "type": clean_df[source_col].apply(medium_type).values,
    })

    comp_df = resolve_references(
        comp_df, instr_df, dict(zip(medium_df["medium_id"], medium_df["name"]))
    )

    # Component table — deduplicated on the pointer-stripped name
    component_df = (
        comp_df["clean_name"].value_counts()
        .rename_axis("name").reset_index(name="n_uses")
    )
    component_df.insert(0, "component_id", range(1, len(component_df) + 1))
    name_to_id = dict(zip(component_df["name"], component_df["component_id"]))
    comp_df["component_id"] = comp_df["clean_name"].map(name_to_id)

    # Global instruction id, so composition can carry a real foreign key
    instr_df = instr_df.reset_index(drop=True)
    instr_df.insert(0, "instruction_id", range(1, len(instr_df) + 1))
    key = {(r.medium_id, r.step_order): r.instruction_id for r in instr_df.itertuples()}
    comp_df["instruction_id"] = [
        key.get((m, s)) if pd.notna(s) else None
        for m, s in zip(comp_df["medium_id"], comp_df["step"])
    ]

    composition_df = comp_df[[
        "medium_id", "component_id", "amount", "unit",
        "instruction_id", "ref_medium_id", "ref_type",
    ]].copy()

    return {
        "medium": medium_df,
        "component": component_df,
        "instruction": instr_df,
        "composition": composition_df,
    }


def write_tables(tables, out_dir, db_path=None):
    """Write each table to CSV, and optionally to a SQLite database."""
    import sqlite3

    for name, df_ in tables.items():
        df_.to_csv(f"{out_dir}/{name}.csv", index=False)

    if db_path:
        conn = sqlite3.connect(db_path)
        for name, df_ in tables.items():
            df_.to_sql(name, conn, if_exists="replace", index=False)
        conn.commit()
        conn.close()


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(tables, clean_df, source_col="tex_text_clean"):
    """Check the tables against the source. Every count should reconcile."""
    med, comp, instr, comps = (
        tables["medium"], tables["component"],
        tables["instruction"], tables["composition"],
    )

    mono_lines = sum(t.count("\\mono") for t in clean_df[source_col])
    unreadable = sum(
        1 for t in clean_df[source_col] for l in t.splitlines()
        if "\\mono" in l and split_mono(l) is None
    )

    out = {
        "mediums": len(med),
        "mediums_unnamed": int(med["name"].isna().sum()),
        "components_unique": len(comp),
        "instructions": len(instr),
        "compositions": len(comps),
        "mono_lines_in_source": mono_lines,
        "mono_unreadable": unreadable,
        "compositions_unmapped_component": int(comps["component_id"].isna().sum()),
        "mediums_with_no_components": len(set(med["medium_id"]) - set(comps["medium_id"])),
    }

    print("=== PARSING VERIFICATION ===\n")
    for k, v in out.items():
        print(f"  {k:34} {v}")

    print("\n  medium types")
    for k, v in med["type"].value_counts().items():
        print(f"    {k:14} {v}")

    print("\n  instruction kinds")
    for k, v in instr["kind"].value_counts().items():
        print(f"    {k:14} {v}")

    print("\n  reference types")
    for k, v in comps["ref_type"].value_counts(dropna=False).items():
        print(f"    {str(k):14} {v}")

    return out