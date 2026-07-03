import pytest

from app.services.boggle import (
    can_form_word,
    generate_board,
    is_real_word,
    score_for_word_length,
    score_words,
)


def _board_with_word(word: str) -> list[str]:
    board = ["X"] * 25
    for i, letter in enumerate(word.upper()):
        board[i] = letter
    return board


def test_generate_board_is_deterministic_per_seed():
    assert generate_board("2026-06-26") == generate_board("2026-06-26")


def test_generate_board_differs_across_seeds():
    assert generate_board("2026-06-26") != generate_board("2026-06-27")


def test_generate_board_has_25_cells():
    assert len(generate_board("seed")) == 25


@pytest.mark.parametrize(
    "length,expected",
    [(1, 0), (3, 0), (4, 1), (5, 2), (6, 3), (7, 5), (8, 11), (12, 11)],
)
def test_score_for_word_length(length, expected):
    assert score_for_word_length(length) == expected


def test_can_form_word_along_adjacent_path():
    board = _board_with_word("CATS")
    assert can_form_word(board, "CATS") is True
    assert can_form_word(board, "STAC") is True  # adjacency is symmetric


def test_can_form_word_rejects_word_not_on_board():
    board = _board_with_word("CATS")
    assert can_form_word(board, "DOGS") is False


def test_can_form_word_rejects_reusing_the_same_cell():
    board = ["A"] + ["X"] * 24
    assert can_form_word(board, "AA") is False


def test_can_form_word_handles_qu_tile():
    board = ["QU", "E", "S", "T"] + ["X"] * 21
    assert can_form_word(board, "QUEST") is True
    assert can_form_word(board, "QEST") is False  # Q never appears without U


def test_score_words_validates_real_word_on_board():
    board = _board_with_word("CATS")
    valid_words, score = score_words(board, ["cats"])
    assert valid_words == ["CATS"]
    assert score == 1


def test_score_words_deduplicates_case_insensitively():
    board = _board_with_word("CATS")
    valid_words, score = score_words(board, ["cats", "CATS", "Cats"])
    assert valid_words == ["CATS"]
    assert score == 1


def test_score_words_rejects_short_unreal_and_unformable_words():
    board = _board_with_word("CATS")
    valid_words, score = score_words(board, ["cat", "zzzqx", "dogs"])
    assert valid_words == []
    assert score == 0


def test_is_real_word():
    assert is_real_word("cats") is True
    assert is_real_word("zzzqx") is False
