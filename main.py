# -*- coding: utf-8 -*-
# Solver для игры "5 букв" (русское Wordle)
# Формат ответа на ход: строка из 5 символов:
#   'ж' — буква и позиция верны (exact)
#   'б' — буква есть, но позиция неверна (present)
#   'с' — буквы нет (absent) ИЛИ это лишний повтор
# Можно вводить: "жжбсб посол" или просто "жжбсб" (тогда берётся предложенное слово)

from collections import defaultdict

def normalize(s: str) -> str:
    # игра просит использовать Е вместо Ё
    return s.replace('ё', 'е').replace('Ё', 'Е')

def load_words(path: str):
    with open(path, 'r', encoding='utf8') as f:
        words = [normalize(w.strip()) for w in f]
    # 5 букв, без дефисов
    return [w for w in words if len(w) == 5 and '-' not in w]

def build_weights(words):
    # частотный вес по символам
    all_chars = defaultdict(int)
    for w in words:
        for ch in set(w):
            all_chars[ch] += 1

    all_words = {}
    for w in words:
        score = 0.0
        for ch in w:
            cc = w.count(ch)
            # чаще встречающиеся буквы важнее; штрафуем повторы геометрической суммой
            score += (all_chars[ch] / cc) * sum(1 / 2 ** (n - 1) for n in range(1, cc + 1))
        all_words[w] = score

    # список (слово, вес), отсортированный по убыванию веса
    return sorted(all_words.items(), key=lambda x: x[1], reverse=True)

def checker(constraints, word: str) -> bool:
    in_set       = constraints['in']         # set
    not_in_set   = constraints['not in']     # set
    pos_var      = constraints['pos']        # list[(idx, ch)]
    not_pos_var  = constraints['not pos']    # list[(idx, ch)]
    min_counts   = constraints['min_counts'] # dict[ch] -> int
    max_counts   = constraints['max_counts'] # dict[ch] -> int (верхняя граница) или None

    # буквы, которые точно есть (хотя бы по одной)
    for ch in in_set:
        if ch not in word:
            return False

    # букв, которых точно нет
    for ch in not_in_set:
        if ch in word:
            return False

    # точные позиции
    for i, ch in pos_var:
        if word[i] != ch:
            return False

    # запреты позиций
    for i, ch in not_pos_var:
        if word[i] == ch:
            return False

    # ограничения по количеству
    # нижние
    for ch, m in min_counts.items():
        if word.count(ch) < m:
            return False
    # верхние
    for ch, M in max_counts.items():
        if M is not None and word.count(ch) > M:
            return False

    return True

def update_constraints_by_feedback(selected_word: str,
                                   result: str,
                                   in_set: set,
                                   not_in_set: set,
                                   pos_var: list,
                                   not_pos_var: list,
                                   min_counts: dict,
                                   max_counts: dict):
    """
    Обновляем ограничения по одному ходу.
    Используем двухпроходную схему: сначала считаем по каждой букве,
    сколько раз она НЕ серая в этом ходе (это и есть минимум для неё в слове),
    а затем уточняем верхние границы, если есть серые для лишних повторов.
    """
    selected_word = normalize(selected_word)

    # Подсчёты по текущему ходу
    count_b = defaultdict(int)  # 'б'
    count_j = defaultdict(int)  # 'ж'
    count_s = defaultdict(int)  # 'с'

    for p, c in enumerate(result):
        ch = selected_word[p]
        if c == 'ж':
            count_j[ch] += 1
        elif c == 'б':
            count_b[ch] += 1
        elif c == 'с':
            count_s[ch] += 1
        else:
            raise ValueError('Ожидались только символы ж/б/с')

    # Множество букв, которые по этому ходу точно присутствуют
    present_this_guess = {ch for ch in set(selected_word) if (count_b[ch] + count_j[ch]) > 0}

    # Позиционные ограничения
    for p, c in enumerate(result):
        ch = selected_word[p]
        if c == 'ж':
            pos_var.append((p, ch))
        elif c == 'б':
            not_pos_var.append((p, ch))
        elif c == 'с':
            # если буква известна как присутствующая (в этом ходе или ранее) — это запрет позиции,
            # иначе — её нет вовсе
            if ch in present_this_guess or ch in in_set:
                not_pos_var.append((p, ch))
            else:
                not_in_set.add(ch)

    # Обновляем множества присутствующих букв
    for ch in present_this_guess:
        in_set.add(ch)
        not_in_set.discard(ch)  # вдруг попадала раньше из-за серой с лишнего повтора

    # Обновляем min/max по количеству
    for ch in set(selected_word):
        non_grey = count_b[ch] + count_j[ch]
        grey     = count_s[ch]

        if non_grey > 0:
            # минимум — сколько раз буква НЕ серая в этом ходе
            min_counts[ch] = max(min_counts.get(ch, 0), non_grey)

        if grey > 0:
            if non_grey == 0:
                # ни одного попадания — буквы нет вообще
                max_counts[ch] = 0
                not_in_set.add(ch)
                in_set.discard(ch)
            else:
                # есть и серые, и несерые — лишние повторы отсекаем
                prev = max_counts.get(ch, None)
                max_counts[ch] = non_grey if prev is None else min(prev, non_grey)

def main():
    words = load_words('russian_nouns.txt')
    ranked = build_weights(words)

    in_set = set()
    not_in_set = set()
    pos_var = []       # [(idx, ch)]
    not_pos_var = []   # [(idx, ch)]
    min_counts = {}    # {ch: min}
    max_counts = {}    # {ch: max or 0}  (если ключа нет — верхняя граница неизвестна)

    result = ''
    first_time = True

    while result != 'жжжжж':
        best_word = ''
        for w, weight in ranked:
            if checker(
                {
                    'in': in_set,
                    'not in': not_in_set,
                    'pos': pos_var,
                    'not pos': not_pos_var,
                    'min_counts': min_counts,
                    'max_counts': max_counts,
                },
                w,
            ):
                if not best_word:
                    best_word = w
                print(f'{w}: {weight:.3f}')

        if best_word:
            print('Лучшее слово:', best_word)
        else:
            print('Ошибка, нет подходящих слов!')
            break

        prompt = (
            'Введите результаты и введённое слово'
            + (' (пример: "жжбсб посол" или просто "жжбсб")' if first_time else '')
            + ': '
        )
        data = input(prompt).split()
        first_time = False

        if len(data) == 2:
            selected_word = normalize(data[1]) or best_word
        else:
            selected_word = best_word
        result = data[0]

        if len(result) != 5 or len(selected_word) != 5:
            raise ValueError('Нужно 5 символов результата и слово из 5 букв')

        update_constraints_by_feedback(
            selected_word, result,
            in_set, not_in_set, pos_var, not_pos_var,
            min_counts, max_counts
        )

if __name__ == '__main__':
    main()
