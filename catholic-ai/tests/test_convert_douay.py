from scripts.convert_douay_rheims import BOOKS, convert


def fake(books):
    return {"books": [{"name": n, "chapters": ch} for n, ch in books.items()]}


def full(extra=None):
    books = {n: [{"chapter": 1, "verses": [{"verse": 1, "text": "In the beginning."}]}] for n in BOOKS}
    books.update(extra or {})
    return fake(books)


def test_verse_per_passage_and_ref_format():
    data = full({"John": [{"chapter": 3, "verses": [
        {"verse": 16, "text": "For God so  loved\nthe world."}, {"verse": 17, "text": "Next."}]}]})
    rows, gaps = convert(data)
    jo = [r for r in rows if r["ref"].startswith("Jo ")]
    assert [r["ref"] for r in jo] == ["Jo 3,16", "Jo 3,17"]
    assert jo[0]["text"] == "For God so loved the world."


def test_window_groups_verses_and_empty_verses_reported():
    data = full({"John": [{"chapter": 11, "verses": [
        {"verse": 55, "text": "a"}, {"verse": 56, "text": "b"}, {"verse": 57, "text": ""}, {"verse": 58, "text": "d"}]}]})
    rows, gaps = convert(data, window=2)
    assert gaps == ["Jo 11,57"]
    assert [r["ref"] for r in rows if r["ref"].startswith("Jo ")] == ["Jo 11,55-56", "Jo 11,58"]


def test_non_canonical_books_dropped():
    data = full({"Laodiceans": [{"chapter": 1, "verses": [{"verse": 1, "text": "x"}]}]})
    rows, _ = convert(data)
    assert not any("Laodiceans" in r["section"] for r in rows)
