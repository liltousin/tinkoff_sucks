def checker(d: dict, word):
    for c in d['in']:
        if c not in word:
            return False
    for c in d['not in']:
        if c in word:
            return False
    if d['pos']:
        for i, c in d['pos']:
            if word[i] != c:
                return False
    if d['not pos']:
        for i, c in d['not pos']:
            if word[i] == c:
                return False
    return True


def check_var_in_pos(var, pos_var):
    for p, v in pos_var:
        if var == v:
            return p
    return False


with open('russian_nouns.txt', 'r', encoding='utf8') as f:
    words = [word.rstrip() for word in f.readlines()]
    filtered_words = list(
        filter(lambda x: len(x) == 5 and '-' not in x, words)
    )
    all_chars = {}
    for word in filtered_words:
        for c in list(set(word)):
            if c not in all_chars.keys():
                all_chars[c] = 1
            else:
                all_chars[c] += 1
    all_words = {}
    for word in filtered_words:
        counter = 0
        for c in word:
            cc = word.count(c)
            counter += (
                all_chars[c]
                / cc
                * sum(1 / 2 ** (n - 1) for n in range(1, cc + 1))
            )
        all_words[word] = counter
    most_best_words = sorted(
        [(k, v) for k, v in all_words.items()],
        key=lambda x: int(x[1]),
        reverse=True,
    )

    in_var = ''
    not_in_var = ''
    pos_var = []
    not_pos_var = []

    result = ''

    first_time = True

    while result != 'жжжжж':

        best_word = ''

        for word, weight in most_best_words:

            if checker(
                {
                    'in': in_var,
                    'not in': not_in_var,
                    'pos': pos_var,
                    'not pos': not_pos_var,
                },
                word,
            ):
                if not best_word:
                    best_word = word
                print(f'{word}: {weight}')
        if best_word:
            print('Лучшее слово:', best_word)
        else:
            print('Ошибка, нет таких слов!')
            break

        data = input(
            'Введите результаты и введенное слово'
            + (
                ' (не обязательно если вы использовали лучшее слово, '
                'пример: "жжбсб посол" или просто "жжбсб")'
                if first_time
                else ''
            )
            + ': '
        ).split()

        first_time = False

        if len(data) == 2:
            selected_word = data[1]
            if selected_word == '':
                selected_word = best_word
        else:
            selected_word = best_word
        result = data[0]

        if len(result) != 5 or len(selected_word) != 5:
            raise ValueError

        for p, c in enumerate(result):
            i = selected_word[p]
            if c == 'с':
                if pos := check_var_in_pos(i, pos_var):
                    not_pos_var += list(
                        filter(lambda x: x[0] != pos, enumerate(i * 5))
                    )
                else:
                    not_in_var += i
            elif c == 'б':
                in_var += i
                not_pos_var += [(p, i)]
            elif c == 'ж':
                pos_var += [(p, i)]
            else:
                raise ValueError
