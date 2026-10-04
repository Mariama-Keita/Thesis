import pytest
from code import cleaning


def test_pass1_clean_basic():
    s = r"This \hspace{5pt} has \mu and \Mix and \sfi"
    out = cleaning.pass1_clean(s)
    assert "\u03bc" in out or 'μ' in out
    assert 'Mix' in out
    assert '\\hspace' not in out


def test_fix_concatenated_amounts_split():
    s = r"\mono{Agar}{20g}\\mono{Distilled water}{980mL}"
    out = cleaning.fix_concatenated_amounts(s)
    assert '{20} {g}' in out
    assert '\n\\mono' in out


def test_pass3_units_normalize():
    s = 'value {mL} and {vg} &mu; $\u03bc$g'
    out = cleaning.pass3_units(s)
    assert '{ml}' in out
    assert '{g}' in out
    assert 'μ' in out


def test_fix_missing_closing_brace():
    s = "name {mg\nother"
    out = cleaning.fix_missing_closing_brace(s)
    assert '{mg}\n' in out


def test_fix_corrupted_v():
    s = r"\mono{Glucosev {20}{g}"
    out = cleaning.fix_corrupted_v(s)
    assert '\\mono{Glucose} {' in out or 'Glucose} {' in out


def test_clean_text_pipeline():
    s = r"\mono{Agar}{20g}\\mono{Distilled water}{980mL}"
    out = cleaning.clean_text(s)
    assert '{20} {g}' in out
    assert '{980} {ml}' in out or '{980} {ml}' in out
