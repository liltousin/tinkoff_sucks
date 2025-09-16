# -*- coding: utf-8 -*-
# Полный бенч солвера: прогон по всему словарю (без лимита ходов) + список слов >6 ходов.
from __future__ import annotations
import os, time, math, argparse, shutil, sys
from collections import Counter

from solver import (
    load_words, build_ranked,
    Constraints, update_constraints,
    GREEN, YELLOW, GRAY, normalize
)

# ---------- Wordle feedback (ж/б/с) ----------
def feedback(secret: str, guess: str) -> str:
    """Корректный ответ игры ж/б/с с учётом повторов."""
    secret = normalize(secret)
    guess  = normalize(guess)
    res = ['с'] * 5
    s_cnt = Counter(secret)

    # зелёные
    for i, (g, s) in enumerate(zip(guess, secret)):
        if g == s:
            res[i] = GREEN
            s_cnt[g] -= 1

    # белые/жёлтые
    for i, g in enumerate(guess):
        if res[i] == GREEN:
            continue
        if s_cnt[g] > 0:
            res[i] = YELLOW
            s_cnt[g] -= 1

    return ''.join(res)

# ---------- helpers ----------
def term_cols() -> int:
    return shutil.get_terminal_size(fallback=(80, 24)).columns

def fmt_time(sec: float) -> str:
    if math.isinf(sec) or sec > 99*3600:
        return "--:--"
    sec = int(round(sec))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

# ---------- Progress bar ----------
class Progress:
    """Ровный прогресс-бар: авто-ужатие под ширину терминала + очистка строки."""
    def __init__(self, total: int, prefix: str = "", nominal_width: int = 40):
        self.total = max(1, total)
        self.prefix = prefix
        self.nominal_width = max(10, nominal_width)
        self.start = time.time()

    def update(self, i: int):
        i = min(i, self.total)
        frac = i / self.total
        elapsed = max(1e-6, time.time() - self.start)
        rate = i / elapsed
        eta  = (self.total - i) / rate if rate > 0 else float('inf')

        # Базовые куски
        left = f"{self.prefix}["
        right = (f"] {i}/{self.total} "
                 f"({frac*100:5.1f}%) | {rate:5.2f}/s | ETA {fmt_time(eta)}")

        cols = term_cols()
        avail = max(3, cols - len(left) - len(right) - 1)  # место под бар
        width = min(self.nominal_width, avail)

        filled = int(frac * width)
        bar = "█" * filled + "·" * (width - filled)
        line = left + bar + right

        # очистили строку и обрезали по ширине, чтобы не было переноса
        sys.stdout.write("\r\033[K" + line[:cols])
        sys.stdout.flush()
        if i == self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()

# ---------- Статистика ----------
def describe_distribution(steps_list):
    if not steps_list:
        return {"n": 0, "avg": 0.0, "median": 0, "p90": 0, "p95": 0, "dist": {}}
    s = sorted(steps_list)
    n = len(s)
    def pct(p):
        idx = max(0, min(n-1, int(math.ceil(p/100.0 * n) - 1)))
        return s[idx]
    dist = {}
    for x in s:
        dist[x] = dist.get(x, 0) + 1
    return {
        "n": n,
        "avg": sum(s)/n,
        "median": pct(50),
        "p90": pct(90),
        "p95": pct(95),
        "dist": dict(sorted(dist.items())),
    }

def text_hist(dist_dict, total_success):
    """Рисуем гистограмму, которая точно помещается в ширину терминала."""
    if total_success == 0:
        return "(нет успешных партий)"
    cols = term_cols()
    max_count = max(dist_dict.values())
    scale = 1.0 if max_count == 0 else 1.0  # масштаб подберём после расчёта места

    lines = []
    for step in sorted(dist_dict):
        c = dist_dict[step]
        # левая часть строки без бара
        left = f"{step:>2} ход(а/ов): {c:>6} | {100.0*c/total_success:5.1f}% | "
        # сколько остаётся под бар
        avail = max(0, cols - len(left))
        # линейный масштаб бара к максимуму, но не шире экрана
        max_bar = avail
        bar_len = 0 if max_count == 0 else int(round(c / max_count * max_bar))
        bar = "█" * bar_len
        lines.append((left + bar)[:cols])
    return "\n".join(lines)

def wrap_tokens(tokens, sep=" ", prefix=""):
    """Печатает токены (словечки) с переносами по ширине терминала."""
    cols = term_cols()
    line = prefix
    out_lines = []
    for t in tokens:
        piece = (sep if line else "") + t
        if len(line) + len(piece) > cols:
            out_lines.append(line)
            line = t
        else:
            line += piece
    if line:
        out_lines.append(line)
    return "\n".join(out_lines)

# ---------- Основной прогон ----------
def evaluate(dict_path: str, list_over6: bool = True):
    words = load_words(dict_path)
    ranked = build_ranked(words)  # [(word, score)] по убыванию

    total = len(words)
    progress = Progress(total, prefix="Бенч: ")

    solved_steps = []        # числа шагов для успешных слов
    over6_words = []         # (secret, steps) — всё, что решалось >6 ходов
    failed = []              # секреты, где кандидаты внезапно кончились (маловероятно)

    t0 = time.time()
    for idx, secret in enumerate(words, 1):
        cons = Constraints()
        steps = 0

        while True:
            # первое допустимое слово из предранжированного списка
            guess = None
            for w, _score in ranked:
                if cons.allows(w):
                    guess = w
                    break
            if guess is None:
                failed.append(secret)
                break

            fb = feedback(secret, guess)
            steps += 1

            if fb == GREEN * 5:
                solved_steps.append(steps)
                if steps > 6:
                    over6_words.append((secret, steps))
                break

            update_constraints(cons, guess, fb)

        progress.update(idx)

    dt = time.time() - t0

    # Итоги
    success = len(solved_steps)
    fail = len(failed)
    stats = describe_distribution(solved_steps)
    le6 = sum(v for k, v in stats['dist'].items() if k <= 6) if success else 0

    print("\n=== ИТОГИ ===")
    print(f"Слов в словаре: {total}")
    print(f"Время бенча:   {dt:.2f} сек")
    print(f"Решено:        {success} ({(success/total*100):.2f}%)")
    print(f"Не решено:     {fail} ({(fail/total*100):.2f}%)")

    if success:
        print("\nРаспределение по числу ходов (успешные):")
        print(text_hist(stats['dist'], success))
        print("\nСреднее:           {:.3f}".format(stats['avg']))
        print("Медиана:           {}".format(stats['median']))
        print("90-й перцентиль:   {}".format(stats['p90']))
        print("95-й перцентиль:   {}".format(stats['p95']))
        print("Доля ≤6 ходов:     {:.2f}%".format(100.0 * le6 / success if success else 0.0))

    if list_over6:
        over6_words.sort(key=lambda x: (x[1], x[0]))  # по шагам, затем по слову
        print("\nСлова, которые НЕ удалось найти за ≤6 ходов (решались 7+):")
        print(f"Всего: {len(over6_words)}")
        if over6_words:
            tokens = [f"{w}({s})" for w, s in over6_words]
            print(wrap_tokens(tokens))
        else:
            print("(пусто)")

def main():
    parser = argparse.ArgumentParser(description="Бенч солвера по всему словарю (без лимита ходов)")
    parser.add_argument("--dict", default="data/russian_nouns.txt",
                        help="Путь к словарю (по умолчанию data/russian_nouns.txt)")
    parser.add_argument("--no-over6", action="store_true",
                        help="Не печатать список слов, решённых за >6 ходов")
    args = parser.parse_args()

    dict_path = args.dict
    if not os.path.isfile(dict_path):
        alt = "russian_nouns.txt"
        if os.path.isfile(alt):
            dict_path = alt

    evaluate(dict_path, list_over6=not args.no_over6)

if __name__ == "__main__":
    main()
