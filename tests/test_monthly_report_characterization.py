"""Characterization tests for expenses.monthly_report.

These lock in what the function does TODAY, quirks included, so the
refactoring can be checked against them. A test that pins a quirk is marked
QUIRK. If a quirk is fixed on purpose later, update that test deliberately.
"""
import copy

import pytest

import expenses


def exp(amount, category, date):
    return {"amount": amount, "category": category, "date": date}


def month_entry(report, month):
    return next(m for m in report["months"] if m["month"] == month)


# ---- normal behavior -------------------------------------------------------

def test_empty_input():
    assert expenses.monthly_report([]) == {
        "months": [],
        "grand_total": 0.0,
        "skipped": 0,
    }


def test_full_output_shape_for_one_month_two_categories():
    items = [
        exp(10, "Food", "2026-05-03"),
        exp(30, "Rent", "2026-05-20"),
        exp(5.5, "Food", "2026-05-25"),
    ]
    assert expenses.monthly_report(items) == {
        "months": [
            {
                "month": "2026-05",
                "total": 45.5,
                "count": 3,
                "average": 15.17,
                "top_category": "Rent",
                "categories": [
                    {"category": "Food", "total": 15.5, "count": 2, "percent": 34.1},
                    {"category": "Rent", "total": 30.0, "count": 1, "percent": 65.9},
                ],
            }
        ],
        "grand_total": 45.5,
        "skipped": 0,
    }


def test_months_are_sorted_even_when_input_is_not():
    items = [
        exp(1, "A", "2026-07-01"),
        exp(2, "B", "2026-07-02"),
        exp(1, "A", "2026-05-02"),
    ]
    report = expenses.monthly_report(items)
    assert [m["month"] for m in report["months"]] == ["2026-05", "2026-07"]
    july = month_entry(report, "2026-07")
    assert july["total"] == 3.0
    assert july["count"] == 2
    assert july["average"] == 1.5
    assert july["top_category"] == "B"
    assert [c["percent"] for c in july["categories"]] == [33.3, 66.7]
    assert report["grand_total"] == 4.0


def test_categories_within_a_month_are_listed_alphabetically():
    items = [exp(1, "Zed", "2026-05-01"), exp(1, "Alpha", "2026-05-02"), exp(1, "Mid", "2026-05-03")]
    cats = month_entry(expenses.monthly_report(items), "2026-05")["categories"]
    assert [c["category"] for c in cats] == ["Alpha", "Mid", "Zed"]


def test_day_of_month_does_not_matter_only_year_and_month():
    items = [exp(1, "A", "2026-05-01"), exp(1, "A", "2026-05-31")]
    report = expenses.monthly_report(items)
    assert len(report["months"]) == 1
    assert report["months"][0]["count"] == 2


def test_grand_total_adds_up_all_months():
    items = [exp(10, "A", "2026-05-01"), exp(20, "A", "2026-06-01"), exp(30, "B", "2026-07-01")]
    assert expenses.monthly_report(items)["grand_total"] == 60.0


def test_input_list_is_not_modified():
    items = [exp(3, "A", "2026-05-01"), exp(4, None, "2026-06-01")]
    before = copy.deepcopy(items)
    expenses.monthly_report(items)
    assert items == before


def test_values_are_rounded_to_two_places_and_percent_to_one():
    items = [exp(0.1, "A", "2026-05-01")] * 3 + [exp(10, "B", "2026-05-02")]
    may = month_entry(expenses.monthly_report(items), "2026-05")
    assert may["total"] == 10.3
    assert may["average"] == 2.58
    assert [c["percent"] for c in may["categories"]] == [2.9, 97.1]


# ---- skipped rows ----------------------------------------------------------

def test_unusable_rows_are_counted_as_skipped_and_ignored():
    items = [
        None,
        {"amount": 5, "category": "A"},                       # no date key
        exp(5, "A", ""),                                       # empty date
        exp(5, "A", "not-a-date"),                             # unparseable
        exp(5, "A", "2026-05-03 10:00"),                       # has a time part
        exp(5, "A", "2026-05-03"),                             # the one good row
    ]
    report = expenses.monthly_report(items)
    assert report["skipped"] == 5
    assert report["grand_total"] == 5.0
    assert report["months"][0]["count"] == 1


def test_zero_negative_and_none_amounts_are_skipped():
    items = [exp(0, "A", "2026-05-01"), exp(-5, "A", "2026-05-02"), exp(None, "A", "2026-05-03"), exp(7, "A", "2026-05-04")]
    report = expenses.monthly_report(items)
    assert report["skipped"] == 3
    may = month_entry(report, "2026-05")
    assert may["total"] == 7.0
    assert may["count"] == 1


# ---- quirks ----------------------------------------------------------------

def test_QUIRK_month_with_only_skipped_amounts_still_appears_as_empty_entry():
    # The month key is created before the amount is validated, so a valid date
    # with a bad amount leaves behind an empty month row.
    items = [exp(0, "A", "2026-05-01"), exp(-5, "A", "2026-06-01"), exp(None, "A", "2026-07-01")]
    report = expenses.monthly_report(items)
    assert report["skipped"] == 3
    assert report["grand_total"] == 0.0
    assert report["months"] == [
        {"month": m, "total": 0.0, "count": 0, "average": 0, "top_category": None, "categories": []}
        for m in ("2026-05", "2026-06", "2026-07")
    ]


def test_QUIRK_top_category_tie_goes_to_first_one_seen_not_alphabetical():
    items = [exp(10, "B", "2026-05-01"), exp(10, "A", "2026-05-02")]
    may = month_entry(expenses.monthly_report(items), "2026-05")
    assert may["top_category"] == "B"
    assert [c["category"] for c in may["categories"]] == ["A", "B"]


def test_QUIRK_top_category_tie_flips_with_input_order():
    items = [exp(10, "A", "2026-05-02"), exp(10, "B", "2026-05-01")]
    assert month_entry(expenses.monthly_report(items), "2026-05")["top_category"] == "A"


def test_QUIRK_missing_or_empty_category_becomes_uncategorized():
    items = [exp(10, "", "2026-05-01"), exp(5, None, "2026-05-02")]
    may = month_entry(expenses.monthly_report(items), "2026-05")
    assert may["top_category"] == "Uncategorized"
    assert may["categories"] == [
        {"category": "Uncategorized", "total": 15.0, "count": 2, "percent": 100.0}
    ]


def test_QUIRK_categories_are_case_sensitive():
    items = [exp(10, "Food", "2026-05-01"), exp(10, "food", "2026-05-02")]
    may = month_entry(expenses.monthly_report(items), "2026-05")
    assert [c["category"] for c in may["categories"]] == ["Food", "food"]


def test_QUIRK_unpadded_date_is_accepted_and_month_key_is_normalized():
    report = expenses.monthly_report([exp(10, "A", "2026-5-3")])
    assert report["skipped"] == 0
    assert report["months"][0]["month"] == "2026-05"


def test_QUIRK_year_below_1000_is_not_zero_padded_and_sorts_after_later_years():
    items = [exp(1, "A", "0999-01-01"), exp(1, "A", "2026-01-01")]
    months = [m["month"] for m in expenses.monthly_report(items)["months"]]
    assert months == ["2026-01", "999-01"]


def test_QUIRK_month_totals_use_float_addition_hidden_only_by_final_rounding():
    # Raw float addition of 0.1 three times is 0.30000000000000004. The result
    # looks right only because the output is rounded to 2 places.
    items = [exp(0.1, "A", "2026-05-01")] * 3
    assert expenses.monthly_report(items)["months"][0]["total"] == 0.3


def test_QUIRK_row_missing_category_or_amount_key_crashes_instead_of_being_skipped():
    with pytest.raises(KeyError):
        expenses.monthly_report([{"amount": 10, "date": "2026-05-01"}])
    with pytest.raises(KeyError):
        expenses.monthly_report([{"category": "A", "date": "2026-05-01"}])


def test_QUIRK_string_amount_crashes_with_type_error():
    with pytest.raises(TypeError):
        expenses.monthly_report([exp("5", "A", "2026-05-01")])
