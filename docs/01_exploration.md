# Medium Dataset -Exploration Notes

## Overview

This document records the findings from the exploratory analysis of the medium dataset (`medium.csv`). It is intended as a reference for anyone reading the code or continuing this work.

---

## Dataset Structure

The raw CSV has **3 columns**:

| Column | Type | Description |
|--------|------|-------------|
| `grmd` | int | Unique medium number -primary key |
| `md_name` | string | Medium name |
| `tex_text` | string | Raw LaTeX content -components and instructions |

**Basic stats:**
- Total mediums: **1165**
- Duplicate `grmd`: **0** -every medium ID is unique
- Null `tex_text`: **0** -every medium has content
- Null `md_name`: **4** -see below

---

## Data Quality Issues Found

### 1. Missing Medium Names (4 mediums)

| grmd | tex_text starts with |
|------|----------------------|
| 611  | Casamino acids |
| 1262 | NaNO₃ |
| 1263 | NaNO₃ |
| 1264 | Yeast extract |

- `grmd` 1262 and 1263 start identically but diverge at position 296 -one uses Na₂CO₃, the other NaCl. They are **different mediums**, both missing names in the source data.
- All 4 are stored with `md_name = NULL` in the Medium table.
- Not a blocker -`grmd` is the primary key.

### 2. tex_text Length Variation

```
min  :   40 chars  --> very short (single instruction, no components)
mean : 1080 chars  --> typical medium recipe
max  : 5756 chars  --> complex medium with multiple solutions
```

Short mediums (< 100 chars): **57** -mostly references to other mediums.

The shortest medium (grmd 664, DISTILLED WATER):
```
\chu{Autoclaved distilled water.}
```
Just one instruction, no components at all.

---

## LaTeX Tags Found

Running `re.findall(r'\\[a-zA-Z]+')` across all `tex_text` values revealed:

```
{'\\mono', '\\chu', '\\chuSolutionB', '\\chuSolutionC', '\\chuJCM',
 '\\Mix', '\\sfi', '\\mu', '\\alpha', '\\beta', '\\cdot', '\\ge',
 '\\hspace', '\\HCl'}
```

### Tags that matter for parsing

| Tag | Meaning |
|-----|---------|
| `\mono` | Ingredient line -name, amount, unit |
| `\chu` | Instruction (general -needs sub-classification) |
| `\chuSolutionB` | Explicit Solution B block |
| `\chuSolutionC` | Explicit Solution C block |
| `\chuJCM` | Comment/note -spans **multiple lines** |
| `\Mix` | Appears INSIDE `\chu{}` -just means "Mix", treat as plain text |

### Tags to strip (formatting only, no meaning)

| Tag | Meaning | Action |
|-----|---------|--------|
| `\sfi` | Font style (sans-serif italic) | Strip entirely |
| `\hspace{...}` | Horizontal space | Strip entirely |
| `\mu` | Greek letter μ | Replace with `μ` |
| `\alpha` | Greek letter α | Replace with `α` |
| `\beta` | Greek letter β | Replace with `β` |
| `\cdot` | Dot operator · | Replace with `·` |
| `\HCl` | Shorthand macro | Replace with `HCl` |
| `\ge` | Greater than or equal | Replace with `≥` |

---

## Medium Types Discovered

Exploration revealed **five distinct medium structures** based on how `tex_text` begins:

| Type | Count | Description |
|------|-------|-------------|
| standard | 954 | Starts with `\mono` -base components followed by instructions |
| reference | 175 | Starts with `\chu` -modifications of another medium (Use/Prepare Medium No. X) |
| solution | 60 | Starts with `\chu{Solution}` -organised into lettered (A, B, C) or numbered (1, 2, 3) solutions |
| plain reference | 10 | No LaTeX tag -reference text missing `\chu{}` wrapper |
| unique | 2 | Biological source (Vero E6) or single instruction (Distilled water) |
| **Total** | **1165** | |

> **Note:** 36 mediums overlap between reference and solution categories.
> The 201 mediums that start with `\chu` break down as:
> 175 reference + 60 solution + 2 unique − 36 overlap = 201 ✓

### How we identified them

**201 mediums start with `\chu` instead of `\mono`** (no base components).
**10 mediums start with plain text** -references missing the `\chu{}` wrapper.

Within the 201 that start with `\chu`:
- **175** are references -detected by patterns like `Use Medium No`, `Prepare Medium No`, `see Medium No`, `Use commercially available`, `Prepare.*agar`
- **60** are solution-based -detected by `Solution [A-Z0-9]+:` (lettered AND numbered)
- **2** are genuinely unique -biological source (Vero E6) and simple (distilled water)

> **Note:** `\sfi` inside `\chu` caused early misclassification. `\chu{\sfi Solution A:}` and
> `\chu{{\sfi Solution A:}` (double curly) were initially missed. Always strip `\sfi` and
> normalize braces **before** classifying.
>
> **Note:** Numbered solutions (Solution 1, Solution 2...) exist alongside lettered ones
> (Solution A, B, C). The solution pattern must catch both: `r'(?i)solution\s+[a-zA-Z0-9]+:'`

---

## Line Patterns (confirmed by testing grmd 1205 and 1326)

### Pattern 1 -Standard medium (grmd 1205)

```
\mono{...} {amount} {unit}    <-- base component (instruction_id = NULL)
\mono{...} {amount} {unit}    <-- base component
\chu{instruction text}        <-- instruction step 1
\mono{...} {amount} {unit}    <-- component added IN this step
\chu{instruction text}        <-- instruction step 2
\chu{sub recipe name:}        <-- sub recipe definition
\mono{...} {amount} {unit}    <-- component of sub recipe
\chu{Comment:}
\chuJCM text continues...     <-- multiline comment block
continuation line...
final line of comment.}       <-- closes with }
```

### Pattern 2 -Solution-based medium (grmd 1326)

```
\chu{Solution A:}             <-- NO base components, starts with solution
\mono{...} {amount} {unit}    <-- component of Solution A
\chuSolutionB:}               <-- explicit Solution B tag
\mono{...} {amount} {unit}    <-- component of Solution B
\chuSolutionC:}               <-- explicit Solution C tag
\mono{...} {amount} {unit}    <-- component of Solution C
\chu{final instruction}       <-- how to combine all solutions
```

### Pattern 3 -Numbered solution medium (grmd 1096)

```
\chu{\sfi Solution 1:}        <-- numbered instead of lettered
\mono{...} {amount} {unit}    <-- component of Solution 1
\chu{Solution 2:}
\mono{...} {amount} {unit}    <-- component of Solution 2
```

### Pattern 4 -Simple medium (grmd 664)

```
\chu{Autoclaved distilled water.}   <-- one instruction, no components
```

### Pattern 5 -Plain reference (no tag)

```
Use Medium No. [770], replacing betaine solution...   <-- no \chu wrapper!
```

---

## \mono Format Variations

Standard format:
```
\mono{component name} {amount} {unit}
```

Variations found:

| Variation | Example | Count | Action |
|-----------|---------|-------|--------|
| No space between braces | `{0.20}{g}` | 12652 | Normalize |
| Leading space in name | `\mono{ NH₄Cl}` | 8 | Strip name |
| `\sfi` inside name | `\mono{{\sfi p}-Aminobenzoic acid}` | many | Strip `\sfi` |
| `v` instead of `}` | `\mono{Glucosev {5.0}{g}` | several | Replace `v` with `}` |
| Missing `}` on name | `\mono{MgSO₄·7H₂O {0.02}{g}` | several | Recover |
| `\hspace` in amount | `{0.09\hspace{-0.5em}}{g}` | several | Strip `\hspace` |
| Two monos on one line | `\mono{Agar}{20g}\\mono{...}` | 1 | Split |
| Truly malformed | `\mono{Trace vitamins}(see...){1.0 {L}` | few | Flag and skip |

**Total \mono lines:** ~12926  
**Missing amount/unit (before cleaning):** 1326 -most are recoverable after stripping `\sfi`

---

## Units Found

| Unit | Count | Action |
|------|-------|--------|
| `g` | 6201 | Keep |
| `ml` | 2998 | Keep |
| `mg` | 1445 | Keep |
| `L` | 883 | Keep |
| `$\mu$g` | 33 | --> `μg` |
| `mM` | 12 | Keep |
| `$\mu$l` | 10 | --> `μl` |
| `mL` | 6 | --> `ml` |
| `&mu;g` | 5 | --> `μg` |
| `vg` | 4 | --> `g` (corrupted `}`) |
| `&#956;l` | 1 | --> `μl` |
| `m` | 1 | --> `ml` (truncated) |
| malformed | 1 | Flag and skip |

> **Note:** Mixed encoding (LaTeX `$\mu$` and HTML `&mu;` and `&#956;`) suggests the data
> was sourced or converted from multiple formats.

---

## Cross References

| Type | Count | Description |
|------|-------|-------------|
| External | 556 | `see Medium No. [X]` -references another medium |
| Internal | 270 | `see below` -references a sub recipe in the same medium |
| Both | 152 | Medium has both types |

These are stored in the Composition table via `ref_medium_id` and `ref_type` columns.

> **Note:** 47% of mediums reference another medium -cross references are not edge cases,
> they are a core feature of the data.

---

## Target Table Design

### Medium (fact table)
```
id        --> grmd
name      --> md_name (nullable)
type      --> standard / reference / solution / plain_reference / unique
```

### Instruction (dimension)
```
id
medium_id      --> FK --> Medium
step_order     --> preserves order of instructions
type           --> instruction / solution / sub_recipe / comment
solution_label --> A, B, C, 1, 2, 3 or NULL
text
```

### Component (dimension -shared, deduplicated)
```
id
name           --> no FK to Medium, reused across all mediums
```

### Composition (bridge table)
```
id
medium_id      --> FK --> Medium
component_id   --> FK --> Component
instruction_id --> FK --> Instruction (NULL if base component)
amount
unit
ref_medium_id  --> FK --> Medium (if references another medium)
ref_type       --> external / internal / NULL
```

---

## Key Insights

1. **`\mono` appears both before and after `\chu`** -components added during a specific instruction step are still components, just linked to an instruction via `instruction_id`.

2. **`\chu` is overloaded** -the same tag is used for general instructions, solution labels, sub recipe definitions, and comments. Always classify from the text content, not just the tag.

3. **`\chuJCM` is multiline** -the parser needs state awareness to accumulate lines until the closing `}`.

4. **`\sfi` is the biggest source of false mismatches** -stripping it first fixes most of the 1326 "missing amount/unit" cases.

5. **47% of mediums reference another medium** -cross references are not edge cases, they are a core feature of the data.

6. **Solution labels can be lettered (A, B, C) or numbered (1, 2, 3)** -the solution detection pattern must handle both.

7. **10 mediums have no LaTeX tag at all** -plain text references missing the `\chu{}` wrapper, need special handling.

8. **Cleaning must happen before parsing** -the dirty data is complex enough that mixing cleaning and parsing logic would make debugging very difficult.

---

## Notebook Pipeline

```
medium.csv (raw)
      ↓
01_exploration.ipynb   --> understanding the data (this document)
      ↓
02_cleaning.ipynb      --> clean tex_text --> output clean_medium.csv
      ↓
03_parsing.ipynb       --> parse clean CSV --> build 4 tables --> save to SQLite
```