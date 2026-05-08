import pytest

from narrator_friend.parser import _split_heuristic, detect_pov, parse_manuscript


def test_heuristic_splits_on_chapter_headings():
    pages = [
        "Chapter 1\nThe river was loud that morning.\nShe stood there.\n",
        "Chapter 2\nSomething changed.\n",
        "Chapter Three\nFinally, the end.\n",
    ]
    chapters = _split_heuristic(pages)
    assert len(chapters) == 3
    assert chapters[0].title.lower().startswith("chapter 1")
    assert "river" in chapters[0].text
    assert "Something changed" in chapters[1].text
    assert chapters[2].title.lower().startswith("chapter three")


def test_heuristic_handles_no_headings():
    pages = ["Just one big block of prose with no chapter markers at all."]
    chapters = _split_heuristic(pages)
    assert len(chapters) == 1
    assert chapters[0].title == "Manuscript"


def test_pov_from_title_dash():
    assert detect_pov("Chapter 5 — Sarah", "She walked in.") == "Sarah"
    assert detect_pov("Chapter 5: Jack", "He walked in.") == "Jack"


def test_pov_from_first_line_all_caps():
    pov = detect_pov("Chapter 1", "SARAH\n\nThe house was empty when I arrived.\n")
    assert pov == "Sarah"


def test_pov_dual():
    pov = detect_pov("Chapter 7 — Sarah & Jack", "")
    assert pov == "Sarah & Jack"


def test_pov_apostrophe_pov_suffix():
    pov = detect_pov("Chapter 2", "Sarah's POV\n\nShe stood at the window.")
    assert pov == "Sarah"


def test_pov_none_for_normal_chapter_start():
    pov = detect_pov(
        "Chapter 1",
        "The river was loud that morning, and she could barely think.",
    )
    assert pov is None


def test_parse_manuscript_rejects_unknown_extension(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("hello")
    with pytest.raises(ValueError):
        parse_manuscript(str(p))


def test_parse_manuscript_doc_message(tmp_path):
    p = tmp_path / "draft.doc"
    p.write_bytes(b"\xd0\xcf\x11\xe0")  # OLE magic, just a stub
    with pytest.raises(ValueError, match="\\.docx or PDF"):
        parse_manuscript(str(p))


def test_parse_manuscript_docx(tmp_path):
    docx = pytest.importorskip("docx")
    path = tmp_path / "manuscript.docx"
    document = docx.Document()
    document.add_heading("Chapter 1", level=1)
    document.add_paragraph('"Hello," she said.')
    document.add_paragraph("She turned to leave.")
    document.add_heading("Chapter 2 — Sarah", level=1)
    document.add_paragraph('"Wait!" he shouted.')
    document.add_paragraph("He ran after her.")
    document.save(str(path))

    chapters = parse_manuscript(str(path))
    assert len(chapters) == 2
    assert chapters[0].title.lower().startswith("chapter 1")
    assert chapters[1].pov == "Sarah"
    assert "Wait!" in chapters[1].text
