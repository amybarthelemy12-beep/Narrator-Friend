from crystal.analyzer import (
    DEFAULT_WORDS_PER_HOUR,
    analyze_text,
    count_words,
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
