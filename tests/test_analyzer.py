from crystal.analyzer import (
    DEFAULT_WORDS_PER_HOUR,
    analyze_text,
    count_words,
    detect_dialogue_mode,
    recording_time,
)


def test_count_words_basic():
    assert count_words("Hello, world!") == 2
    assert count_words("It's a don't-care thing.") == 4
    assert count_words("") == 0


def test_pure_narration():
    text = "She walked to the river and watched the water."
    b = analyze_text(text)
    assert b.dialogue_words == 0
    assert b.tag_words == 0
    assert b.narration_words == 9
    assert b.total_words == 9


def test_dialogue_with_after_tag():
    text = '"Get out of here," she said sharply.'
    b = analyze_text(text)
    assert b.dialogue_words == 4  # "Get out of here"
    assert b.tag_words == 3  # "she said sharply"
    assert b.narration_words == 0
    assert b.dialogue_lines == 1


def test_dialogue_with_before_tag():
    text = 'Sarah whispered, "I love you."'
    b = analyze_text(text)
    assert b.dialogue_words == 3
    assert b.tag_words == 2  # "Sarah whispered"
    assert b.narration_words == 0


def test_curly_quotes_normalised():
    text = "“Hello,” he said."
    b = analyze_text(text)
    assert b.dialogue_words == 1
    assert b.tag_words == 2
    assert b.narration_words == 0


def test_action_beat_stays_narration():
    # No tag verb after the dialogue — should be classified as narration, not tag.
    text = '"Get out." She slammed the door behind her.'
    b = analyze_text(text)
    assert b.dialogue_words == 2
    assert b.tag_words == 0
    assert b.narration_words == 6  # "She slammed the door behind her"


def test_mixed_paragraph():
    text = (
        '"Are you sure?" he asked. She nodded slowly. '
        '"I have to go," Sarah whispered, glancing at the door.'
    )
    b = analyze_text(text)
    assert b.dialogue_lines == 2
    assert b.dialogue_words == 3 + 4
    # "he asked" + "Sarah whispered" — adverb chunks are tag-attached.
    assert b.tag_words >= 4
    assert b.narration_words >= 3  # "She nodded slowly" remains narration


def test_recording_time():
    assert recording_time(9300, 9300) == "1:00"
    assert recording_time(0) == "0:00"
    assert recording_time(DEFAULT_WORDS_PER_HOUR // 2) == "0:30"


# UK single-quote dialogue ---------------------------------------------------

UK_SAMPLE = (
    "'Get out,' she said. 'Now.'\n"
    "'I don't want to,' he replied, holding the kids' hands.\n"
    "Sarah whispered, 'It's all I have left.'\n"
    "She wasn't sure what came next."
)


def test_detect_uk_single_mode():
    assert detect_dialogue_mode(UK_SAMPLE) == "single"


def test_detect_us_double_mode():
    text = '"Hello," she said. "How are you?" he asked.'
    assert detect_dialogue_mode(text) == "double"


def test_uk_dialogue_skips_apostrophes():
    b = analyze_text(UK_SAMPLE, mode="single")
    # Four lines of dialogue: "Get out", "Now", "I don't want to", "It's all I have left"
    assert b.dialogue_lines == 4
    # Apostrophes inside contractions must NOT split the dialogue; "I don't want to" → 4 words
    assert b.dialogue_words == 2 + 1 + 4 + 5  # 12
    assert b.tag_words >= 4  # "she said" + "he replied" + "Sarah whispered"


def test_uk_dialogue_does_not_eat_possessives():
    # "the kids' hands" is a possessive, not dialogue. With auto mode this
    # paragraph alone is double mode (no single-quote dialogue) so should be
    # all narration.
    text = "She held the kids' hands tightly and didn't speak."
    b = analyze_text(text)
    assert b.dialogue_words == 0
    assert b.tag_words == 0
    assert b.narration_words == 9


def test_unclosed_open_quote_does_not_hang():
    # Regression: an opening single quote with no matching close before a
    # paragraph break used to leave the scan index parked, causing an infinite
    # loop in `_find_single_dialogue` and a hung /analyze request.
    import threading

    text = (
        "'Twas the night before Christmas and not a creature was stirring.\n\n"
        "The next morning, Sarah opened her eyes."
    )
    result: dict = {}

    def run():
        result["mode"] = detect_dialogue_mode(text)
        result["analysis"] = analyze_text(text)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout=2.0)
    assert not t.is_alive(), "analyze_text hung on unclosed opening single quote"
    assert "analysis" in result
