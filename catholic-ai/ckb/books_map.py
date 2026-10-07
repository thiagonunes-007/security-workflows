"""Mapas estruturais hebraico -> Vulgata para livros em que o alinhador por comprimento não serve.

Ester e Daniel: a Vulgata contém acréscimos gregos (deuterocanônicos) sem par no hebraico.
Fronteiras conferidas contra o texto latino do CKB (ver tests/test_books_map.py).
"""


def esther_to_vulgate(c: int, v: int) -> tuple[int, int]:
    """Heb Ester 1,1-10,3 = Vulgata 1,1-10,3 (acréscimos: Vulgata 10,4-16,24, sem par hebraico)."""
    return c, v


def daniel_to_vulgate(c: int, v: int) -> tuple[int, int]:
    """Heb 3,24-33 (aramaico) = Vul 3,91-100 (Vul 3,24-90 = Cântico dos três jovens, só em grego);
    Heb 6,1 = Vul 5,31 e Heb 6,2-29 = Vul 6,1-28. Vul 13 (Susana) e 14 (Bel) sem par hebraico."""
    if c == 3 and v >= 24:
        return 3, v + 67
    if c == 6:
        return (5, 31) if v == 1 else (6, v - 1)
    return c, v


STRUCTURAL = {"Esth": esther_to_vulgate, "Dan": daniel_to_vulgate}
