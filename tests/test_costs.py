from narrator_friend.costs import (
    DEFAULT_EDITING_RATE,
    DEFAULT_NARRATOR_RATE,
    EXPERIENCE_RATES,
    estimate_costs,
    finished_hours,
)


def test_finished_hours_basic():
    assert finished_hours(9300, 9300) == 1.0
    assert finished_hours(18600, 9300) == 2.0
    assert finished_hours(0, 9300) == 0.0
    assert finished_hours(100, 0) == 0.0


def test_experience_rate_presets():
    # The whole point — ACX-scale presets for new/mid/experienced narrators.
    assert EXPERIENCE_RATES["new"] == 150.0
    assert EXPERIENCE_RATES["mid"] == 275.0
    assert EXPERIENCE_RATES["experienced"] == 400.0


def test_estimate_costs_defaults_no_proofing():
    # 10 finished hours at ACX rate.
    c = estimate_costs(93000, 9300)
    assert c.finished_hours == 10.0
    assert c.narrator_rate == DEFAULT_NARRATOR_RATE
    assert c.editing_rate == DEFAULT_EDITING_RATE
    assert c.proofing_rate == 0.0
    assert c.narrator_cost == 10.0 * DEFAULT_NARRATOR_RATE
    assert c.editing_cost == 10.0 * DEFAULT_EDITING_RATE
    assert c.proofing_cost == 0.0
    assert c.total_cost == c.narrator_cost + c.editing_cost


def test_estimate_costs_with_custom_rates_and_proofing():
    c = estimate_costs(
        total_words=9300,
        words_per_hour=9300,
        narrator_rate=200,
        editing_rate=80,
        proofing_rate=40,
    )
    assert c.finished_hours == 1.0
    assert c.narrator_cost == 200.0
    assert c.editing_cost == 80.0
    assert c.proofing_cost == 40.0
    assert c.total_cost == 320.0


def test_estimate_costs_scales_with_book_length():
    # 5 finished hours @ $300/hr narrator + $75/hr editing
    c = estimate_costs(46500, 9300, narrator_rate=300, editing_rate=75)
    assert c.finished_hours == 5.0
    assert c.narrator_cost == 1500.0
    assert c.editing_cost == 375.0
    assert c.total_cost == 1875.0


def test_estimate_costs_handles_empty_book():
    c = estimate_costs(0, 9300, narrator_rate=300, editing_rate=80, proofing_rate=40)
    assert c.finished_hours == 0.0
    assert c.narrator_cost == 0.0
    assert c.editing_cost == 0.0
    assert c.proofing_cost == 0.0
    assert c.total_cost == 0.0


def test_estimate_costs_negative_rates_clamped():
    c = estimate_costs(9300, 9300, narrator_rate=-50, editing_rate=-1)
    assert c.narrator_rate == 0.0
    assert c.editing_rate == 0.0
    assert c.total_cost == 0.0


def test_to_dict_round_trip():
    c = estimate_costs(9300, 9300, narrator_rate=275, editing_rate=75, proofing_rate=37.5)
    d = c.to_dict()
    assert d["finished_hours"] == 1.0
    assert d["narrator_cost"] == 275.0
    assert d["editing_cost"] == 75.0
    assert d["proofing_cost"] == 37.5
    assert d["total_cost"] == 387.5


def test_report_exposes_total_finished_hours():
    # Smoke-test that the new field is populated end-to-end via build_report.
    from narrator_friend.parser import Chapter
    from narrator_friend.report import build_report

    # 1860 words of plain narration, 9300 wph -> 0.2 finished hours
    text = ("hello world " * 930).strip()
    chapters = [Chapter(title="Ch 1", text=text, page_start=1, pov=None)]
    r = build_report(chapters, words_per_hour=9300)
    assert r.totals.total_words == 1860
    assert abs(r.total_finished_hours - 0.2) < 1e-9
    assert "total_finished_hours" in r.to_dict()
