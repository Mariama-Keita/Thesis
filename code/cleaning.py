"""
LaTeX cleaning pipeline for the medium dataset.

The raw `tex_text` column contains LaTeX-formatted recipes with a range of
formatting artefacts and genuine corruption. This module normalises the text
so the parser can work with a predictable structure.

ORDER MATTERS. In particular:
  - `\sfi` must be stripped before `{{` is collapsed
  - `{{` must be collapsed before early-closing braces are repaired
  - plain references are wrapped last, once the body is stable

Usage:
    from cleaning import clean_df
    df = clean_df(df)
"""

import re
from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Precompiled patterns
# ---------------------------------------------------------------------------

RE_HSPACE = re.compile(r"\\hspace\*?\{[^}]+\}")
RE_SFI_REMNANT = re.compile(r"\{\{([^{}]{1,15})\}")
RE_SFI_GROUP = re.compile(r"\{\s*\\sfi\s+([^{}]*)\}")
RE_CURLY_SPACE = re.compile(r"\{\s+")
RE_DOUBLE_CURLY = re.compile(r"\{\{")

RE_AMOUNT_UNIT = re.compile(r"\{([0-9.]+)([a-zA-Z]+)\}")
RE_NAME_AMOUNT_GAP = re.compile(r"\}(\s*)\{([0-9])")

RE_UNIT_ML = re.compile(r"\{mL\}")
RE_UNIT_VG = re.compile(r"\{vg\}")
RE_UNIT_M = re.compile(r"\{m\}")

RE_MISSING_UNIT_BRACE = re.compile(r"\{([a-zA-Zμ]+)\n")
RE_CORRUPTED_V = re.compile(r"(\\mono\{[^}]*)v(\s*\{)")
RE_MULTILINE_NAME = re.compile(r"(\\mono\{[^}]*)\n([^\\{]*\})")

RE_EARLY_BRACE_HYPHEN_A = re.compile(r"(\\mono\{)([^}]{1,10})\}-([^}]+\})")
RE_EARLY_BRACE_HYPHEN_B = re.compile(r"(\\mono\{[^}]{1,5}-)\}([^}]+\})")

RE_MISSING_NAME_BRACE = re.compile(r"(\\mono\{)([^}]+?)\s{2,}(\{[0-9])")
RE_MISSING_NAME_BRACE_PAREN = re.compile(r"(\\mono\{[^}]+\([^)]+\))\s*(\{[0-9])")
RE_EXTRA_TEXT_AFTER_NAME = re.compile(r"(\\mono\{[^}]+)\}([a-zA-Z]+)\}")
RE_PAREN_AFTER_NAME = re.compile(r"(\\mono\{[^}]+)\}\s*(\([^)]*\))\}")

RE_EXTRA_BRACE_BEFORE = re.compile(r"\}\s*\}(\s*\{[0-9])")
RE_EXTRA_BRACE_AFTER = re.compile(r"\{([0-9.]+)\}\}")
RE_CORRUPTED_AMOUNT = re.compile(r"\{([0-9]+)\.\}([0-9]+)\{([a-zA-Zμ]+)\}")
RE_UNCLOSED_AMOUNT = re.compile(r"\{([0-9.]+)\s+\{")
RE_WRONG_BRACKET = re.compile(r"\{([a-zA-Zμ]+)\]")

RE_BROKEN_MONO = re.compile(r"\\mono\s+(\{[^}]+\}\s*\{[0-9])")
RE_AMOUNT_NO_UNIT = re.compile(
    r"^(\s*\\mono\{[^}]+\}\s*\{[0-9.]+\})\s*$", re.MULTILINE
)

RE_PLAIN_REFERENCE = re.compile(
    r"(?i)^(use|prepare)\s+(medium|cm|oatmeal|jcm|blood|aquifex|columbia|r2a)"
)

RE_HTML_ENTITY = re.compile(r"&#(\d+);")

RE_PREFIX_BRACES = re.compile(r"\{\{([^}]+)\}") #JUST ADDED 



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_text(tex_text: Any) -> str:
    """Coerce any input to a string so the pipeline never raises on NaN."""
    if tex_text is None or (isinstance(tex_text, float) and pd.isna(tex_text)):
        return ""
    if not isinstance(tex_text, str):
        return str(tex_text)
    return tex_text


# ---------------------------------------------------------------------------
# Pass 1 — formatting tags
# ---------------------------------------------------------------------------

def pass1_formatting_tags(tex_text: Any) -> str:
    r"""Strip display-only LaTeX and convert symbol macros to unicode.

    Handles: \hspace{...}, \hspace*{...}, \sfi, \Mix, $\mu$, \mu, $\cdot$,
    \cdot, \alpha, \beta, \HCl, \ge, and leading spaces inside braces.
    """
    tex_text = _safe_text(tex_text)

    tex_text = RE_HSPACE.sub("", tex_text)

    tex_text = tex_text.replace("\\sfi", "")
    tex_text = RE_CURLY_SPACE.sub("{", tex_text)

    tex_text = tex_text.replace("\\Mix", "Mix")

    tex_text = tex_text.replace("$\\mu$", "μ")
    tex_text = tex_text.replace("\\mu", "μ")
    tex_text = tex_text.replace("$\\cdot$", "·")
    tex_text = tex_text.replace("\\cdot", "·")
    tex_text = tex_text.replace("\\alpha", "α")
    tex_text = tex_text.replace("\\beta", "β")
    tex_text = tex_text.replace("\\HCl", "HCl")
    tex_text = tex_text.replace("\\ge", "≥")

    return tex_text

def pass1_sfi(tex_text: Any) -> str:
    r"""Remove `\sfi`, choosing the repair by the line's brace balance.

    `{\sfi X}` is a real LaTeX group. Where the line is balanced in source,
    the whole group is removed (both braces). Where the source line is already
    unbalanced — `\chu{{\sfi Solution A:}` has two opens and one close — only
    the doubled opening brace is removed.
    """
    tex_text = _safe_text(tex_text)
    if "\\sfi" not in tex_text:
        return tex_text

    out = []
    for line in tex_text.split("\n"):
        if "\\sfi" in line:
            if line.count("{") - line.count("}") == 0:
                line = RE_SFI_GROUP.sub(r"\1", line)
            line = line.replace("\\sfi", "").replace("{{", "{")
        out.append(line)
    return "\n".join(out)

# ---------------------------------------------------------------------------
# Pass 2 — brace normalisation
# ---------------------------------------------------------------------------
def pass2_double_curly_unbalanced(tex_text: Any) -> str:
    r"""Collapse `{{` only on lines whose braces don't balance.

    `\chu{{Mineral solution A:}` has two opens and one close — the doubled
    brace is the error. `\chu{{Solution 1:}}` balances, so its braces are
    real LaTeX grouping and are left alone.
    """
    tex_text = _safe_text(tex_text)
    out = []
    for line in tex_text.split("\n"):
        if "{{" in line and line.count("{") - line.count("}") > 0:
            line = line.replace("{{", "{")
        out.append(line)
    return "\n".join(out)

# def pass2_sfi_remnant(tex_text: Any) -> str:
#     r"""Repair the `{{X}` fragment left when `\sfi` is stripped from `{{\sfi X}`.

#     Removes both the doubled opening brace and its now-orphaned closing brace
#     in a single substitution, so the brace balance is never transiently wrong.
#     """
#     tex_text = _safe_text(tex_text)
#     return RE_SFI_REMNANT.sub(r"{\1", tex_text)


# def pass2_double_curly(tex_text: Any) -> str:
#     r"""Collapse `{{` left behind after `\sfi` removal.

#     `\chu{{\sfi Solution A:}` becomes `\chu{{Solution A:}` after stripping
#     `\sfi`, which must then become `\chu{Solution A:}`.
#     """
#     tex_text = _safe_text(tex_text)
#     return RE_DOUBLE_CURLY.sub("{", tex_text)


def pass2_concatenated_amounts(tex_text: Any) -> str:
    r"""Split `{20g}` into `{20} {g}` and repair double-escaped tags.

    Also inserts the missing space between a component name and its amount.
    """
    tex_text = _safe_text(tex_text)

    tex_text = tex_text.replace("\\\\mono", "\n\\mono")
    tex_text = tex_text.replace("\\\\chu", "\n\\chu")

    tex_text = RE_AMOUNT_UNIT.sub(
        lambda m: "{" + m.group(1) + "} {" + m.group(2).lower() + "}", tex_text
    )

    tex_text = RE_NAME_AMOUNT_GAP.sub(r"} {\2", tex_text)

    return tex_text


# ---------------------------------------------------------------------------
# Pass 3 — units
# ---------------------------------------------------------------------------

def pass3_units(tex_text: Any) -> str:
    """Normalise unit tokens to a single canonical form.

    mL -> ml, &mu; and &#956; -> μ, vg -> g (corrupted brace), m -> ml.
    """
    tex_text = _safe_text(tex_text)

    tex_text = tex_text.replace("&mu;", "μ")
    tex_text = tex_text.replace("&#956;", "μ")

    tex_text = RE_UNIT_ML.sub("{ml}", tex_text)
    tex_text = RE_UNIT_VG.sub("{g}", tex_text)
    tex_text = RE_UNIT_M.sub("{ml}", tex_text)

    tex_text = tex_text.replace("$μ$g", "μg")
    tex_text = tex_text.replace("$μ$l", "μl")

    return tex_text

def pass3_html_entities(tex_text: Any) -> str:
    """Decode HTML entities to unicode.

    Numeric entities in this dataset are ℃ (&#8451;), ≥ (&#8805;), α (&#945;)
    and μ (&#956;). Decoding &#8805; makes it agree with the ≥ produced by the
    \\ge macro in pass1.
    """
    tex_text = _safe_text(tex_text)
    tex_text = tex_text.replace("&mu;", "μ")
    tex_text = tex_text.replace("&alpha;", "α")
    tex_text = tex_text.replace("&beta;", "β")
    return RE_HTML_ENTITY.sub(lambda m: chr(int(m.group(1))), tex_text)


# ---------------------------------------------------------------------------
# Pass 4 — structural repairs to \mono lines
# ---------------------------------------------------------------------------

def pass4_missing_unit_brace(tex_text: Any) -> str:
    r"""Add the closing brace to units that run into the next line.

    `{mg\n` becomes `{mg}\n`, which stops the parser swallowing the next line.
    """
    tex_text = _safe_text(tex_text)
    return RE_MISSING_UNIT_BRACE.sub(r"{\1}\n", tex_text)


def pass4_corrupted_v(tex_text: Any) -> str:
    r"""Replace `v` used in place of `}` at the end of a component name.

    `\mono{Glucosev {5.0} {g}` becomes `\mono{Glucose} {5.0} {g}`.
    """
    tex_text = _safe_text(tex_text)
    return RE_CORRUPTED_V.sub(r"\1}\2", tex_text)


def pass4_multiline_name(tex_text: Any) -> str:
    r"""Join component names that were wrapped across two lines."""
    tex_text = _safe_text(tex_text)
    return RE_MULTILINE_NAME.sub(r"\1 \2", tex_text)


# def pass4_early_closing_brace(tex_text: Any) -> str:
#     r"""Repair names whose brace closed too early after `\sfi` removal.

#     `\mono{{\sfi p}-Aminobenzoic acid}` collapses to `\mono{p}-Aminobenzoic
#     acid}`, where the first `}` is wrong. Both hyphen positions are handled:
#     `\mono{p}-Amino...` and `\mono{p-}Amino...`.
#     """
#     tex_text = _safe_text(tex_text)
#     tex_text = RE_EARLY_BRACE_HYPHEN_A.sub(r"\1\2-\3", tex_text)
#     tex_text = RE_EARLY_BRACE_HYPHEN_B.sub(r"\1\2", tex_text)
#     return tex_text


def pass4_missing_name_brace(tex_text: Any) -> str:
    r"""Close component names that have no `}` before the amount.

    Covers both the whitespace-padded case (`\mono{MgSO4·7H2O    {0.02}{g}`)
    and the case where the name ends in a parenthetical.
    """
    tex_text = _safe_text(tex_text)
    tex_text = RE_MISSING_NAME_BRACE.sub(r"\1\2} \3", tex_text)
    tex_text = RE_MISSING_NAME_BRACE_PAREN.sub(r"\1} \2", tex_text)
    return tex_text


def pass4_stray_text_after_name(tex_text: Any) -> str:
    r"""Fold stray text that appears after a prematurely closed name.

    `\mono{1 M MgSO4}solution}` becomes `\mono{1 M MgSO4 solution}`.
    `\mono{Trace vitamins} (see Medium No. [197])}` becomes
    `\mono{Trace vitamins (see Medium No. [197])}`.
    """
    tex_text = _safe_text(tex_text)
    tex_text = RE_PAREN_AFTER_NAME.sub(r"\1 \2}", tex_text)
    tex_text = RE_EXTRA_TEXT_AFTER_NAME.sub(r"\1 \2}", tex_text)
    return tex_text


def pass4_brace_and_amount_repairs(tex_text: Any) -> str:
    r"""Remove duplicated braces and repair malformed amounts.

    `} } {20.0}` -> `} {20.0}`, `{0.02}}` -> `{0.02}`, `{0.}5{g}` -> `{0.5}{g}`,
    `{1.0 {L}` -> `{1.0} {L}`, `{ml]` -> `{ml}`.
    """
    tex_text = _safe_text(tex_text)

    tex_text = RE_EXTRA_BRACE_BEFORE.sub(r"}\1", tex_text)
    tex_text = RE_EXTRA_BRACE_AFTER.sub(r"{\1}", tex_text)
    tex_text = RE_CORRUPTED_AMOUNT.sub(r"{\1.\2}{\3}", tex_text)
    tex_text = RE_UNCLOSED_AMOUNT.sub(r"{\1} {", tex_text)
    tex_text = RE_WRONG_BRACKET.sub(r"{\1}", tex_text)

    return tex_text


def pass4_broken_mono_tag(tex_text: Any) -> str:
    r"""Reattach a `\mono` tag that was separated from its braced name."""
    tex_text = _safe_text(tex_text)
    return RE_BROKEN_MONO.sub(r"\\mono\1", tex_text)


def pass4_amount_without_unit(tex_text: Any, default_unit: str = "g") -> str:
    r"""Supply a unit for `\mono` lines that end after the amount.

    Only one line in the dataset is affected (`\mono{KCl} {0.34}`) and its
    neighbours are all in grams, so `g` is the safe default. Change
    `default_unit` if this assumption stops holding.
    """
    tex_text = _safe_text(tex_text)
    return RE_AMOUNT_NO_UNIT.sub(r"\1{" + default_unit + "}", tex_text)

def pass4_prefix_braces(tex_text: Any) -> str:
    r"""Remove extra braces around prefixes inside \mono ingredient names.

    Examples:
        {{p}-Aminobenzoic acid  -> {p-Aminobenzoic acid
        {{iso}-Butyric acid     -> {iso-Butyric acid
        {{N}-Acetyl...          -> {N-Acetyl...
    """
    tex_text = _safe_text(tex_text)

    return RE_PREFIX_BRACES.sub(r"{\1", tex_text)
# ---------------------------------------------------------------------------
# Pass 5 — plain references
# ---------------------------------------------------------------------------

def pass5_plain_references(tex_text: Any) -> str:
    r"""Wrap untagged reference text in `\chu{}`.

    Ten mediums begin with plain prose such as `Use Medium No. [770] ...`
    with no LaTeX tag at all. Wrapping them makes every medium start with
    either `\mono` or `\chu`.
    """
    tex_text = _safe_text(tex_text)

    stripped = tex_text.strip()
    if stripped and RE_PLAIN_REFERENCE.match(stripped):
        return "\\chu{" + stripped + "}"

    return tex_text


# ---------------------------------------------------------------------------
# Medium name cleaning
# ---------------------------------------------------------------------------

def clean_medium_name(name: Any) -> Any:
    """Decode HTML numeric entities in `md_name`, preserving NaN.

    e.g. `POREMEDIA B-CYE&#945; AGAR MEDIUM` -> `POREMEDIA B-CYEα AGAR MEDIUM`
    """
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return name
    if not isinstance(name, str):
        return name

    return RE_HTML_ENTITY.sub(lambda m: chr(int(m.group(1))), name)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

PIPELINE = [
    pass1_formatting_tags,
    pass1_sfi,
    pass2_double_curly_unbalanced,
    #pass2_sfi_remnant,
    #pass2_double_curly,
    pass2_concatenated_amounts,
    pass3_units,
    pass3_html_entities,
    pass4_missing_unit_brace,
    pass4_corrupted_v,
    pass4_multiline_name,
    #pass4_early_closing_brace,
    pass4_missing_name_brace,
    pass4_stray_text_after_name,
    pass4_brace_and_amount_repairs,
    pass4_broken_mono_tag,
    pass4_amount_without_unit,
    pass4_prefix_braces, #newly added 
    pass5_plain_references,
]


def clean_text(tex_text: Any) -> str:
    """Run the full cleaning pipeline over a single `tex_text` value."""
    for step in PIPELINE:
        tex_text = step(tex_text)
    return tex_text


def clean_text_traced(tex_text: Any) -> dict:
    """Run the pipeline and return the output of every step.

    Useful for debugging: `clean_text_traced(raw)["pass3_units"]` shows the
    text as it looked immediately after unit normalisation.
    """
    trace = {"input": _safe_text(tex_text)}
    current = tex_text
    for step in PIPELINE:
        current = step(current)
        trace[step.__name__] = current
    trace["output"] = current
    return trace


def clean_df(
    df: pd.DataFrame,
    source_col: str = "tex_text",
    dest_col: str = "tex_text_clean",
    name_col: str = "md_name",
) -> pd.DataFrame:
    """Apply the cleaning pipeline to a dataframe.

    Writes the cleaned LaTeX to `dest_col` and cleans `name_col` in place if
    it is present. Returns a new dataframe; the input is not modified.
    """
    if source_col not in df.columns:
        raise KeyError(f"Source column {source_col!r} not found in DataFrame")

    out = df.copy()
    out[dest_col] = out[source_col].apply(clean_text)

    if name_col in out.columns:
        out[name_col] = out[name_col].apply(clean_medium_name)

    return out


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

MONO_FULL = re.compile(r"\\mono\{[^}]+\}\s*\{[^}]+\}\s*\{[^}]*\}")

# Braces inside a component name that are legitimate chemistry or taxonomy
# notation, not corruption. These lines are correct; the parser needs a
# brace-aware matcher rather than the simple MONO_FULL pattern above.
VALID_INNER_BRACES = [
    re.compile(r"\{[xX]\}"),          # MnSO4·{x}H2O — unknown hydration
    re.compile(r"\{[A-Z][a-z]+\}"),   # {Vibrio} — genus name
    re.compile(r"\$\^\{[^}]+\}\$"),   # Fe$^{2+}$ — ionic charge
]


def verify(df: pd.DataFrame, col: str = "tex_text_clean") -> dict:
    """Report leftover artefacts after cleaning.

    Every count should be zero except `mono_valid_inner_braces`, which counts
    correctly-formed lines that carry chemistry notation in braces.
    """
    text = df[col]

    checks = {
        "sfi": text.str.contains(r"\\sfi").sum(),
        "hspace": text.str.contains(r"\\hspace").sum(),
        "Mix_tag": text.str.contains(r"\\Mix").sum(),
        "mu_tag": text.str.contains(r"\\mu").sum(),
        "cdot_tag": text.str.contains(r"\\cdot").sum(),
        "double_curly": text.str.contains(r"\{\{").sum(),
        "double_backslash": text.str.contains(r"\\\\mono|\\\\chu").sum(),
        "corrupted_v": text.str.contains(r"\\mono\{[^}]*v\s*\{").sum(),
        "unclosed_amount": text.str.contains(r"\{[0-9.]+\s+\{").sum(),
        "unit_mL": text.str.contains(r"\{mL\}").sum(),
        "unit_vg": text.str.contains(r"\{vg\}").sum(),
        "html_entity": text.str.contains(r"&#\d+;|&mu;").sum(),
        "plain_reference": text.str.strip().str.match(RE_PLAIN_REFERENCE).sum(),
    }

    valid, invalid = 0, []
    for tex in text:
        for line in tex.splitlines():
            if "\\mono" in line and not MONO_FULL.search(line):
                if any(p.search(line) for p in VALID_INNER_BRACES):
                    valid += 1
                else:
                    invalid.append(line.strip())

    checks["mono_valid_inner_braces"] = valid
    checks["mono_unparseable"] = len(invalid)
    checks["_unparseable_lines"] = invalid

    return checks


def print_verification(df: pd.DataFrame, col: str = "tex_text_clean") -> None:
    """Print the verification report in a readable form."""
    result = verify(df, col)
    unparseable = result.pop("_unparseable_lines")

    print("=== CLEANING VERIFICATION ===\n")
    for key, value in result.items():
        flag = "" if value == 0 or key == "mono_valid_inner_braces" else "  <-- CHECK"
        print(f"  {key:28} {value}{flag}")

    if unparseable:
        print(f"\nUnparseable \\mono lines ({len(unparseable)}):")
        for line in unparseable[:20]:
            print(f"  {line[:90]!r}")
