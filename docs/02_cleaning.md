# Medium Dataset — Cleaning Notes

## Overview

This document records the cleaning stage: what was wrong with the raw
`tex_text`, how each problem was repaired, and what deliberately was not
repaired. It follows on from `01_exploration.md`.

The goal of cleaning is **not** to produce perfectly valid LaTeX. It is to make
every `\mono` and `\chu` line individually parseable. Whole-file brace balance
is explicitly *not* a target — see [What we did not fix](#what-we-did-not-fix).

**Input:** `data/medium.csv` (1165 rows, raw)

**Output:** `data/medium_clean.csv` (1165 rows, `tex_text_clean` column)

**Code:** `code/cleaning.py`

---

## Results

| Metric | Before | After |
|--------|--------|-------|
| Mediums | 1165 | 1165 |
| `\mono` lines unreadable | — | **0** |
| Unique units | 13 | **7** |
| Mediums with unbalanced braces | 59 | **28** |
| Mediums broken by cleaning | — | **0** |

31 of the 59 brace imbalances were repaired as a side effect. None were
introduced. The remaining 28 are source defects that cannot be repaired from
the data available — see [Known source defects](#known-source-defects).

---

## How "clean" is verified

Cleaning is verified with **the same function the parser will use**, not with a
regex approximation:

```python
def split_mono(line):
    """Extract (name, amount, unit) from a \\mono line, respecting nesting.

    Returns None if the line cannot be read.
    """
    ...
```

A line is *readable* if `split_mono` returns a complete `(name, amount, unit)`
triple. All 12931 `\mono` lines are readable.

> **Why this matters.** An earlier version of this check used a flat regex
> `\\mono\{[^}]+\}\s*\{[^}]+\}\s*\{[^}]*\}`. Because `[^}]+` cannot cross a
> nested brace, that regex reported **0 failures while the data was being
> silently corrupted**, and **78 failures once it was correct**. The metric was
> measuring regex convenience, not correctness. Verify with the function you
> will actually use.

Note that readability is about *extraction succeeding*, not about the extracted
name being in a canonical form. Name normalisation is a Component-table
question and is deferred to the parsing stage.

---

## The pipeline

15 passes, applied in order. Order is load-bearing — see
[Ordering constraints](#ordering-constraints).

| # | Pass | What it fixes |
|---|------|---------------|
| 1 | `pass1_formatting_tags` | `\hspace{...}`, `\hspace*{...}`, `\Mix`, `$\mu$`, `\mu`, `$\cdot$`, `\cdot`, `\alpha`, `\beta`, `\HCl`, `\ge`, leading spaces in braces |
| 2 | `pass1_sfi` | `\sfi` removal with brace repair (count-based) |
| 3 | `pass2_double_curly_unbalanced` | `{{` on unbalanced lines only (count-based) |
| 4 | `pass2_concatenated_amounts` | `{20g}` → `{20} {g}`, `\\mono` → `\mono` |
| 5 | `pass3_units` | `mL`→`ml`, `vg`→`g`, `m`→`ml`, `&mu;`→`μ` |
| 6 | `pass3_html_entities` | `&#8451;`→`℃`, `&#8805;`→`≥`, `&#945;`→`α` |
| 7 | `pass4_missing_unit_brace` | `{mg\n` → `{mg}\n` |
| 8 | `pass4_corrupted_v` | `\mono{Glucosev` → `\mono{Glucose}` |
| 9 | `pass4_multiline_name` | component name wrapped across two lines |
| 10 | `pass4_missing_name_brace` | `\mono{name   {0.02}{g}` → `\mono{name} {0.02}{g}` |
| 11 | `pass4_stray_text_after_name` | `\mono{X}solution}` → `\mono{X solution}` |
| 12 | `pass4_brace_and_amount_repairs` | `}}`, `{0.}5{g}`, `{1.0 {L}`, `{ml]` |
| 13 | `pass4_broken_mono_tag` | `\mono   {name}` → `\mono{name}` |
| 14 | `pass4_amount_without_unit` | `\mono{KCl} {0.34}` → adds `{g}` |
| 15 | `pass5_plain_references` | wraps untagged reference prose in `\chu{}` |

---

## Two passes are count-based, not regex

Passes 2 and 3 branch on `line.count("{") - line.count("}")` rather than
matching a pattern. **This is deliberate and must not be "tidied up" into a
regex.**

The two cases are textually identical — only the brace count distinguishes
them:

```
\chu{{Mineral solution A:}     2 open, 1 close  →  collapse to \chu{
\chu{{Solution 1:}}            2 open, 2 close  →  leave alone
```

An unconditional `{{` → `{` substitution was tried. It repaired 28 mediums and
**broke 56** — the balanced ones, where `{...}` is real LaTeX grouping.

The same applies to `\sfi`. `{\sfi X}` is a genuine LaTeX group:

```
\mono{{\sfi p}-Aminobenzoic acid}    balanced   → remove the whole group
\chu{{\sfi Solution A:}              unbalanced → remove only the doubled brace
```

Regex cannot count. Any pattern-based approach fires on both shapes.

---

## Ordering constraints

- `\sfi` must be handled **before** `{{` collapsing, since stripping `\sfi`
  is what creates some of the `{{` cases.
- Plain references are wrapped **last**, once the body is stable.
- HTML entity decoding runs after unit normalisation so `&mu;` is handled once,
  in one place.

`clean_text_traced()` returns the text after every individual pass. When
something goes wrong, it names the pass:

```python
trace = cleaning.clean_text_traced(raw_text)
for name, text in trace.items():
    print(f"{name:32} {brace_balance(text):+d}")
```

This is how both brace-repair bugs were located.

---

## Units

13 variants in the source, 7 after cleaning:

| Unit | Count | Source variants folded in |
|------|-------|---------------------------|
| `g` | 7229 | `vg` (corrupted `}`) |
| `ml` | 3038 | `mL`, `m` (truncated) |
| `mg` | 1532 | — |
| `L` | 883 | — |
| `μg` | 38 | `$\mu$g`, `&mu;g` |
| `mM` | 12 | — |
| `μl` | 11 | `$\mu$l`, `&#956;l` |

> The mixed encodings — LaTeX `$\mu$`, HTML named `&mu;`, HTML numeric
> `&#956;` — indicate the data passed through more than one format conversion.

---

## What we did not fix

### Braces inside component names are valid

79 `\mono` lines carry braces inside the component name. These are **correct**
and require no repair — they are chemistry and taxonomy notation:

| Notation | Meaning | Example |
|----------|---------|---------|
| `{x}` | variable hydration | `MnSO$_4$·{x}H$_2$O` |
| `{N}`, `{p}`, `{myo}` | italicised locant / stereochemistry prefix | `2.5% {N}-Acetyl-D-glucosamine solution` |
| `{Genus}` | italicised organism name | `Concentrated {Vibrio} suspension` |
| `$^{2+}$` | ionic charge | `Fe$^{2+}$ solution` |

`split_mono`'s depth counter reads all of them correctly.

> An early pass tried to "repair" these with `\mono\{([^}]{1,10})\}-`. Because
> the trigger was any short string rather than a known prefix, it matched
> `\mono{2.5% {N}` and deleted a real brace. The pass was removed.

### Whole-file brace balance

28 mediums have `\chu` blocks with no closing brace. **No instruction text is
lost** — the block simply runs to the next tag:

```
\chu{Mix components thoroughly and autoclave under a N$_2$-CO$_2$ gas mixture.
Aseptically and anaerobically add the following solutions:
                                        ← no closing }
\mono{8% NaHCO$_3$ solution*} {25.0}{ml}   ← block ends here
```

Repairing this in the cleaner would require locating the block boundary — which
is exactly what the instruction parser does anyway. Implementing it twice
invites the two implementations to disagree, so it is handled once, in the
parser:

```python
def read_chu_block(lines, i):
    """Terminate at the closing brace, the next \\mono / \\chu line,
    or end of text — whichever comes first."""
```

Also contributing to the count: `\chuSolutionB:}` and `\chuJCM ... }` are
written **without an opening brace** throughout the dataset. That is the macro
syntax, not damage. Medium 1326 is `-2` purely from two `\chuSolution` tags.

### Component name normalisation

Three artefacts remain in component names, deferred to the parsing stage
because they affect **deduplication**, not readability:

| Artefact | Example | Question |
|----------|---------|----------|
| `$_2$` subscripts | `KH$_2$PO$_4$` | keep LaTeX, or render `KH₂PO₄`? |
| `--` en-dash | `filter--sterilized`, `ISP--3` | normalise to `-`? |
| `\%` escape | `15\% MgSO$_4$ solution` | unescape to `%`? |

The subscript decision is the significant one: `KH$_2$PO$_4$` and `KH₂PO₄`
would deduplicate as **two separate components**. This is a modelling choice
worth confirming with the supervisor.

---

## Known source defects

Recorded, not repaired. These are errors in the source data.

### Chemical formula errors

| Observed | Expected | Occurrences |
|----------|----------|-------------|
| `Fe(SO$_4$)$_3$·{x}H$_2$O` | `Fe$_2$(SO$_4$)$_3$·{x}H$_2$O` | 1 (vs 12 correct) |
| `NH$_4$CI` | `NH$_4$Cl` | medium 1326 |

Both are **OCR signatures** — capital `I` for lowercase `l`, a dropped
subscript. The `v`-for-`}` corruption already repaired in pass 8 is the same
class of error. This predicts more such defects exist.

A systematic sweep belongs **after** parsing, on the deduplicated Component
table, where near-duplicate detection plus frequency asymmetry makes them
visible:

```
Fe$_2$(SO$_4$)$_3$·{x}H$_2$O   →  12 mediums
Fe(SO$_4$)$_3$·{x}H$_2$O       →   1 medium    ← suspect
```

A rare chemical and a typo look alike in isolation; the usage-count asymmetry
is what separates them.

### Truncated / unterminated instructions

28 mediums, listed below. Text is complete; only the terminator is absent.

```
50, 255, 301, 391, 425, 492, 544, 567, 631, 811, 894, 942, 962, 1014,
1074, 1149, 1155, 1167, 1175, 1179, 1205, 1209, 1227, 1326, 1331, 1347,
1375, 1405
```

Carried into parsing as `UNBALANCED_MEDIUMS` — flagged in output, not repaired.

### Missing medium names

4 mediums have `md_name = NULL` (611, 1262, 1263, 1264). Not a blocker; `grmd`
is the primary key. Mediums 1262 and 1263 share a base recipe but differ at one
component (Na₂CO₃ vs NaCl) — they are distinct mediums, not duplicates.

---

## Handing off to the parser

```python
UNBALANCED_MEDIUMS = set(...)   # 28 IDs — flag, do not repair
split_mono(line)                # depth-counting extractor, the foundation
read_chu_block(lines, i)        # multiline \chu accumulator
```

Open decisions for the parsing stage:

1. Component name normalisation — `$_2$`, `--`, `\%` (affects deduplication)
2. OCR typo sweep on the deduplicated Component table
3. Chemical vs biological component classification

---

## Lessons

1. **Verify with the function you will use, not a proxy for it.** The regex
   check reported 0 on corrupt data and 78 on correct data.

2. **A repair split across two passes will eventually disagree with itself.**
   Both brace bugs came from one logical fix implemented as two conditional
   passes. Make the repair atomic.

3. **Regex cannot count.** Where the decision depends on balance rather than
   shape, use arithmetic.

4. **Fixing good data to tidy bad data is a bad trade.** The rejected variant
   left 8 fewer mediums unbalanced but corrupted 3 that were fine.

5. **Cheap invariants catch what targeted checks miss.** Every check asked "is
   the bad thing gone?" The brace-balance count asked "is the good thing still
   there?" — and found damage nothing else was looking for.
