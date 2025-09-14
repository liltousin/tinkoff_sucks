# -*- coding: utf-8 -*-
# RU Wordle Solver («5 букв») — понятная версия без внешних зависимостей.

from __future__ import annotations
from dataclasses import dataclass, field
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple

# Обозначения ответа игры
GREEN = 'ж'   # буква и позиция верны (exact)
YELLOW = 'б'  # буква есть, позиция неверна (present)
GRAY = 'с'    # буквы нет (absent) ИЛИ это лишний повтор

Word = str
PosChar = Tuple[int, str]  # (позиция, буква)


def normalize(s: str) -> str:
    """Нормализуем буквы: ё → е (игра обычно так делает)."""
    return s.replace('ё', 'е').replace('Ё', 'Е')


def load_words(path: str) -> List[Word]:
    """Читаем словарь: по одному слову в строке, 5 букв, без дефиса."""
    with open(path, 'r', encoding='utf8') as f:
        words = [normalize(w.strip()) for w in f]
    return [w for w in words if len(w) == 5 and '-' not in w]


def letter_frequencies(words: List[Word]) -> Dict[str, int]:
    """N(c): в скольких словах встречается буква c (по уникальным буквам на слово)."""
    freq = defaultdict(int)
    for w in words:
        for ch in set(w):
            freq[ch] += 1
    return dict(freq)


def repeat_penalty(m: int) -> float:
    """
    Геометрический штраф за повторы: 1 + 1/2 + 1/4 + ... + (1/2)^(m-1)
    Закрытая форма: 2 * (1 - 2^{-m})
    """
    return 2.0 * (1.0 - (0.5 ** m))


def score_word(word: Word, N: Dict[str, int]) -> float:
    """Вес слова: сумма по уникальным буквам N(c) * penalty(count_in_word)."""
    cnt = Counter(word)
    return sum(N.get(ch, 0) * repeat_penalty(m) for ch, m in cnt.items())


def build_ranked(words: List[Word]) -> List[Tuple[Word, float]]:
    """Предрасчёт (слово, вес) по убыванию веса."""
    N = letter_frequencies(words)
    scored = [(w, score_word(w, N)) for w in words]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


@dataclass
class Constraints:
    """Все накопленные ограничения после ходов игрока."""
    present: Set[str] = field(default_factory=set)         # буквы, которые точно есть (>=1)
    absent: Set[str] = field(default_factory=set)          # букв точно нет (или max=0)
    exact: List[PosChar] = field(default_factory=list)     # точные позиции (i == ch)
    not_pos: List[PosChar] = field(default_factory=list)   # запреты позиций (i != ch)
    min_counts: Dict[str, int] = field(default_factory=dict)  # минимум вхождений буквы
    max_counts: Dict[str, int] = field(default_factory=dict)  # максимум (0,1,2,...) или нет ключа = неизвестно

    def allows(self, word: Word) -> bool:
        """Проверяем, подходит ли слово под все ограничения."""
        cnt = Counter(word)

        # есть/нет буквы
        for ch in self.present:
            if cnt[ch] == 0:
                return False
        for ch in self.absent:
            if cnt[ch] > 0:
                return False

        # позиции
        for i, ch in self.exact:
            if word[i] != ch:
                return False
        for i, ch in self.not_pos:
            if word[i] == ch:
                return False

        # количества
        for ch, m in self.min_counts.items():
            if cnt[ch] < m:
                return False
        for ch, M in self.max_counts.items():
            if M is not None and cnt[ch] > M:
                return False

        return True


def update_constraints(cons: Constraints, guess: Word, feedback: str) -> None:
    """
    Обновляем ограничения по одному ходу.
    1) считаем по букве: сколько GREEN/YELLOW/GRAY,
    2) расставляем позиционные правила,
    3) обновляем present/absent,
    4) считаем min/max по количеству.
    """
    guess = normalize(guess)
    if len(guess) != 5 or len(feedback) != 5:
        raise ValueError("Нужны 5 букв слова и 5 символов ответа")

    # Подсчёты статусов для каждой буквы из этого хода
    cg = Counter()  # GREEN per letter
    cy = Counter()  # YELLOW per letter
    ca = Counter()  # GRAY per letter

    for i, mark in enumerate(feedback):
        ch = guess[i]
        if mark == GREEN:
            cg[ch] += 1
        elif mark == YELLOW:
            cy[ch] += 1
        elif mark == GRAY:
            ca[ch] += 1
        else:
            raise ValueError("Ожидались только символы: ж/б/с")

    # Позиции
    for i, mark in enumerate(feedback):
        ch = guess[i]
        if mark == GREEN:
            cons.exact.append((i, ch))
        elif mark == YELLOW:
            cons.not_pos.append((i, ch))
        elif mark == GRAY:
            # если буква известна как присутствующая (в этом ходе или ранее) — это запрет позиции,
            # иначе — буквы нет вовсе
            if (cg[ch] + cy[ch]) > 0 or ch in cons.present:
                cons.not_pos.append((i, ch))
            else:
                cons.absent.add(ch)

    # Присутствие
    for ch in {c for c in set(guess) if (cg[c] + cy[c]) > 0}:
        cons.present.add(ch)
        cons.absent.discard(ch)  # на случай прежней ошибки из "лишней серой"

    # Количественные рамки
    for ch in set(guess):
        non_gray = cg[ch] + cy[ch]  # минимум видимых вхождений этой буквы
        gray = ca[ch]

        if non_gray > 0:
            cons.min_counts[ch] = max(cons.min_counts.get(ch, 0), non_gray)

        if gray > 0:
            if non_gray == 0:
                # все серые → буквы нет вовсе
                cons.max_counts[ch] = 0
                cons.absent.add(ch)
                cons.present.discard(ch)
            else:
                # часть букв — лишние повторы
                prev = cons.max_counts.get(ch, None)
                cons.max_counts[ch] = non_gray if prev is None else min(prev, non_gray)


def main():
    import argparse, os
    parser = argparse.ArgumentParser(description="RU Wordle Solver (понятная версия)")
    parser.add_argument(
        "--dict",
        default="data/russian_nouns.txt",
        help="Путь к словарю (по умолчанию data/russian_nouns.txt)",
    )
    args = parser.parse_args()

    dict_path = args.dict
    if not os.path.isfile(dict_path):
        # Фоллбек на корень репо
        alt = "russian_nouns.txt"
        if os.path.isfile(alt):
            dict_path = alt

    words = load_words(dict_path)
    ranked = build_ranked(words)  # [(word, score)] по убыванию

    cons = Constraints()
    result = ""
    first_time = True

    while result != GREEN * 5:
        best = ""
        for w, score in ranked:
            if cons.allows(w):
                if not best:
                    best = w
                print(f"{w}: {score:.3f}")

        if not best:
            print("Ошибка: нет подходящих слов под текущие ограничения.")
            return

        print("Лучшее слово:", best)

        prompt = (
            'Введите результат и введённое слово'
            + (' (пример: "жжбсб посол" или просто "жжбсб")' if first_time else '')
            + ': '
        )
        data = input(prompt).split()
        first_time = False

        if len(data) == 2:
            guess = normalize(data[1]) or best
        else:
            guess = best
        result = data[0]

        if len(result) != 5 or len(guess) != 5:
            raise ValueError("Нужно 5 символов результата и слово из 5 букв.")

        update_constraints(cons, guess, result)


if __name__ == "__main__":
    main()
