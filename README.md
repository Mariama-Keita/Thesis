# Microbial Growth Medium Database

## Project Overview

This project transforms a dataset of **1165 microbial growth mediums** from a raw LaTeX-formatted source into a structured relational database. The goal is to make the data queryable, analysable, and ready for ontology development.

Each medium in the dataset describes a recipe for growing a specific microorganism - listing the chemical and biological components, their quantities, and the preparation instructions.

---

## The Data

Each medium has three fields:

| Field | Description |
|-------|-------------|
| `grmd` | Unique medium number - primary key |
| `md_name` | Medium name |
| `tex_text` | Raw LaTeX content containing components and preparation instructions |

The `tex_text` uses two main LaTeX constructs:
- `\mono{component} {amount} {unit}` - an ingredient with its quantity
- `\chu{...}` - a preparation instruction

Data is **not included** in this repository as it contains sensitive information.

---

## Database Design

The raw data is parsed into four relational tables:

### Medium
The fact table - one row per medium.
```
id, name, type
```

### Component
All unique chemical and biological substances across all mediums. A component exists independently of any medium - `KH₂PO₄` is stored once and referenced by any medium that uses it.
```
id, name
```

### Instruction
The preparation steps for each medium, stored in order. A medium can have base instructions, solution-based instructions (Solution A, B, C), sub-recipe definitions, and comments.
```
id, medium_id, step_order, type, solution_label, text
```

### Composition
The bridge table that connects a medium to its components, with quantities. Also records which instruction step a component belongs to, and whether it references another medium.
```
id, medium_id, component_id, instruction_id, amount, unit, ref_medium_id, ref_type
```

---

## Medium Types

Exploration revealed four distinct medium structures:

| Type | Count | Description |
|------|-------|-------------|
| standard | 964 | Base components followed by preparation instructions |
| reference | 175 | Modifications of another medium (Use/Prepare Medium No. X) |
| solution | 60 | Organised into separate solutions (A, B, C) with no base components |
| unique | 2 | One-of-a-kind structures (biological source, single instruction) |

---

## Notebook Pipeline

```
medium.csv (raw)
      ↓
01_exploration.ipynb   --> understanding the data structure and quality
      ↓
02_cleaning.ipynb      --> normalizing LaTeX, fixing dirty data --> clean_medium.csv
      ↓
03_parsing.ipynb       --> parsing into 4 tables --> medium.db (SQLite)
```

---

## Documentation

Detailed exploration findings are in `docs/01_exploration.md` - covering all data quality issues found, LaTeX tag meanings, medium type classification, dirty data catalogue, and design decisions.

---

## Future Direction

- Chemical vs biological component classification
- Ontology development (RDF) from the relational model
- Cross-reference resolution - building the full ingredient tree of any medium by following references recursively
- Analysis of which components co-occur across mediums
