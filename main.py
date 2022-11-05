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
        for c in list(set(word)):
            counter += all_chars[c]
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

    for _ in range(6):

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
                print(word)
        print('Лучшее слово:', best_word)

        in_var += input(
            'Буквы которые не на позиции, но есть в слове '
            '(слитно, без пробелов): '
        )
        not_in_var += input(
            'Буквы которых нет в слове (слитно, без пробелов): '
        )
        pos_var += list(
            filter(
                lambda x: x[1] != '*',
                enumerate(
                    input(
                        'Введите буквы которые стоят на своих местах '
                        '(пример: "аб**а"): '
                    )
                ),
            )
        )
        not_pos_var += list(
            filter(
                lambda x: x[1] != '*',
                enumerate(
                    input(
                        'Введите буквы которые стоят не на своих местах '
                        '(пример: "аб**а"): '
                    )
                ),
            )
        )
