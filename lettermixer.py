#!/usr/bin/env python3
import argparse
import logging
import random
import re
import sys
import time

# configuration / defaults
LETTER_ALPHABET = 'abcdefghijklmnopqrstuvwxyz'
SPACE_CHAR = ' '

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('-n', type=int, default=120, help='total characters (string length)')
    p.add_argument('--min-block', type=int, default=3, help='minimum letters between spaces (and minimum word length)')
    p.add_argument('--mutrate', type=float, default=0.20, help='probability per unfrozen char to mutate each iteration')
    p.add_argument('--sleep', type=float, default=0.05, help='delay between frames (seconds)')
    p.add_argument('--dict', type=str, default='/usr/share/dict/ngerman', help='path to wordlist')
    p.add_argument('--seed', type=int, default=None, help='random seed (optional)')
    return p.parse_args()

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stderr)
    return logging.getLogger('weasel')

def load_wordset(path, min_block):
    pat = re.compile(r'^[a-zA-Z]+$')
    wset = set()
    try:
        with open(path, encoding='utf-8', errors='ignore') as fh:
            for ln in fh:
                w = ln.strip()
                if not w:
                    continue
                if not pat.fullmatch(w):
                    continue
                if w.isupper():
                    continue
                lw = w.lower()
                if len(lw) >= min_block:
                    wset.add(lw)
    except FileNotFoundError:
        raise SystemExit(f'Wordlist not found: {path}')
    return wset

def random_letter():
    return random.choice(LETTER_ALPHABET)

def build_initial_string(n, min_block, space_prob=0.04):
    # build char list of length n obeying basic spacing constraints
    chars = []
    while len(chars) < n:
        # avoid leading space
        if len(chars) == 0:
            chars.append(random_letter())
            continue
        # avoid creating double spaces or violating min_block to end
        remaining = n - len(chars)
        left_since_space = 0
        for i in range(len(chars)-1, -1, -1):
            if chars[i] == SPACE_CHAR:
                break
            left_since_space += 1
        can_place_space = (
            left_since_space >= min_block and
            (remaining - 1) >= min_block
        )
        if can_place_space and random.random() < space_prob:
            chars.append(SPACE_CHAR)
        else:
            chars.append(random_letter())
    # ensure no trailing space
    if chars[-1] == SPACE_CHAR:
        chars[-1] = random_letter()
    return ''.join(chars[:n])

def find_word_matches(s, wordset, min_block):
    # find [a-z]{min_block,} that are bounded by start/space and end/space
    matches = []
    for m in re.finditer(r'[a-z]{%d,}' % min_block, s):
        start, end = m.span()
        token = m.group()
        left_ok = (start == 0) or (s[start-1] == SPACE_CHAR)
        right_ok = (end == len(s)) or (s[end] == SPACE_CHAR)
        if left_ok and right_ok and token in wordset:
            matches.append((start, end, token))
    # prefer longer words first to avoid overlapping freezes
    matches.sort(key=lambda t: (-(t[1]-t[0]), t[0]))
    # keep non-overlapping
    chosen = []
    occ = [False] * len(s)
    for start, end, tok in matches:
        if any(occ[i] for i in range(start, end)):
            continue
        chosen.append((start, end, tok))
        for i in range(start, end):
            occ[i] = True
    return chosen

def freeze_matrix_from_matches(n, matches):
    # create frozen flags per character and associate word_id
    frozen = [False] * n
    word_id = [None] * n
    words = []
    for wid, (start, end, tok) in enumerate(matches):
        words.append({'id': wid, 'start': start, 'end': end, 'word': tok})
        for i in range(start, end):
            frozen[i] = True
            word_id[i] = wid
        # freeze adjacent spaces if exist
        if start - 1 >= 0 and start - 1 < n and word_id[start-1] is None and frozen[start-1] is False:
            if_chars = True
            # if the char is space, freeze it
            # freeze space before only if it is a space
            # but user wanted spaces around detected word frozen -> freeze if space
            # preserve position (freeze only if it's actually a space)
            pass
        if start - 1 >= 0 and start - 1 < n and frozen[start-1] is False and word_id[start-1] is None:
            # freeze space before if it is a space
            # (we freeze only the space char, not arbitrary char)
            frozen[start-1] = frozen[start-1] or False
        if end < n and frozen[end] is False and word_id[end] is None:
            frozen[end] = frozen[end] or False
    # freeze adjacent spaces explicitly (if they are spaces)
    for wid, w in enumerate(words):
        s = w['start']
        e = w['end']
        if s - 1 >= 0 and not frozen[s-1] and s-1 < n:
            if current_char is None: pass
        # simpler: caller will freeze adjacent spaces in separate pass below
    # We'll do a second pass freezing spaces adjacent to matched words
    for start, end, tok in matches:
        if start - 1 >= 0 and start - 1 < n and s_char is None:
            pass
    # The above complicated logic is unnecessary; we'll do straightforward freeze:
    # freeze spaces adjacent to words if they are spaces
    for start, end, tok in matches:
        if start - 1 >= 0 and start - 1 < n and s_char is None:
            pass
    # Clear and implement simply:
    for start, end, tok in matches:
        if start - 1 >= 0 and start - 1 < n and start - 1 >= 0:
            if False: pass
    # Re-implement cleanly below (avoid overcomplication)
    for start, end, tok in matches:
        if start - 1 >= 0 and start - 1 < n and start - 1 >= 0:
            # if there's a space directly adjacent, freeze it
            pass
    # Because above got messy, simplify: return frozen, word_id, words; freezing adjacent spaces will be done by caller.
    return frozen, word_id, words

def freeze_flags_with_adjacent_spaces(s, frozen, word_id, matches):
    n = len(s)
    for wid, (start, end, tok) in enumerate(matches):
        # freeze word letters
        for i in range(start, end):
            frozen[i] = True
            word_id[i] = wid
        # freeze space immediately before the word, falls vorhanden
        if start - 1 >= 0 and s[start - 1] == SPACE_CHAR:
            frozen[start - 1] = True
            word_id[start - 1] = wid
        # freeze space immediately after the word, falls vorhanden
        if end < n and s[end] == SPACE_CHAR:
            frozen[end] = True
            word_id[end] = wid
    return frozen, word_id

def can_place_space_at(s_chars, idx, frozen, min_block):
    n = len(s_chars)
    if idx == 0 or idx == n - 1:
        return False
    if s_chars[idx-1] == SPACE_CHAR or s_chars[idx] == SPACE_CHAR:
        # if we're testing to set idx to space, ensure not double space with left/current
        if s_chars[idx-1] == SPACE_CHAR:
            return False
    # measure left letters until previous space
    left = 0
    j = idx - 1
    while j >= 0 and s_chars[j] != SPACE_CHAR:
        left += 1
        j -= 1
    right = 0
    k = idx + 1
    while k < n and s_chars[k] != SPACE_CHAR:
        right += 1
        k += 1
    if left >= min_block and right >= min_block:
        return True
    return False

def mutate_once(s, frozen, word_id, min_block, mutrate):
    n = len(s)
    chars = list(s)
    # precompute next/prev frozen-space to help rules (not strictly necessary)
    # perform per-position mutation
    for i in range(n):
        if frozen[i]:
            continue
        if random.random() >= mutrate:
            continue
        # choose uniformly among letters + space
        candidates = list(LETTER_ALPHABET) + [SPACE_CHAR]
        random.shuffle(candidates)
        chosen = None
        # try up to some attempts to pick candidate that preserves constraints
        attempts = 0
        for cand in candidates:
            attempts += 1
            if attempts > 40:
                break
            # candidate cannot be leading/trailing space
            if cand == SPACE_CHAR and (i == 0 or i == n - 1):
                continue
            # cannot create double spaces
            left = chars[i-1] if i-1 >= 0 else None
            right = chars[i+1] if i+1 < n else None
            if cand == SPACE_CHAR:
                if left == SPACE_CHAR or right == SPACE_CHAR:
                    continue
                # ensure min_block on both sides if we place a space here
                # count left letters
                lcount = 0
                j = i - 1
                while j >= 0 and chars[j] != SPACE_CHAR:
                    lcount += 1
                    j -= 1
                rcount = 0
                k = i + 1
                while k < n and chars[k] != SPACE_CHAR:
                    rcount += 1
                    k += 1
                if lcount < min_block or rcount < min_block:
                    continue
                # also ensure we're not placing inside a frozen word zone such that it would split it
                # if any frozen char exists within left or right runs, disallow changing to space
                j = i - 1
                while j >= 0 and chars[j] != SPACE_CHAR:
                    if frozen[j]:
                        break
                    j -= 1
                else:
                    j = -1
                if j != -1:
                    continue
                k = i + 1
                while k < n and chars[k] != SPACE_CHAR:
                    if frozen[k]:
                        break
                    k += 1
                else:
                    k = n
                if k != n:
                    continue
                chosen = cand
                break
            else:
                # letter candidate: always allowed (but must be lowercase)
                chosen = cand
                break
        if chosen is None:
            # fallback: place letter (keep current or random)
            chosen = random.choice(LETTER_ALPHABET)
        chars[i] = chosen
    return ''.join(chars)

def render_colored(s, frozen, word_id):
    # color locked words (and their frozen spaces) green, others default
    GREEN = '\033[92m'
    RESET = '\033[0m'
    out = []
    n = len(s)
    i = 0
    while i < n:
        if frozen[i]:
            wid = word_id[i]
            # gather contiguous region with same word_id (or frozen but None)
            j = i
            while j < n and frozen[j] and word_id[j] == wid:
                j += 1
            segment = s[i:j]
            out.append(GREEN + segment + RESET)
            i = j
        else:
            out.append(s[i])
            i += 1
    return ''.join(out)

def all_tokens_valid(s, wordset, min_block):
    toks = re.findall(r'[a-z]{%d,}' % min_block, s)
    if not toks:
        return False
    return all(t in wordset for t in toks)

def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)
    logger = setup_logging()
    wordset = load_wordset(args.dict, args.min_block)
    if not wordset:
        raise SystemExit("No words loaded for given min_block; adjust dictionary or min-block.")

    s = build_initial_string(args.n, args.min_block, space_prob=0.04)
    n = len(s)
    # initial frozen matrix: all False
    frozen = [False] * n
    word_id = [None] * n
    # epoch counter
    epoch = 0

    try:
        while True:
            # detect matches and freeze them (and adjacent spaces)
            matches = find_word_matches(s, wordset, args.min_block)
            frozen, word_id = [False]*n, [None]*n
            frozen, word_id = freeze_flags_with_adjacent_spaces(s, frozen, word_id, matches)

            # display
            sys.stdout.write('\033[H\033[J')
            print(render_colored(s, frozen, word_id))
            # termination: if all tokens of len>=min_block are dictionary words
            if all_tokens_valid(s, wordset, args.min_block):
                logger.info("All tokens are dictionary words; finished.")
                break

            # mutate unfrozen positions (letters and spaces)
            s = mutate_once(s, frozen, word_id, args.min_block, args.mutrate)

            epoch += 1
            time.sleep(args.sleep)

    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting cleanly (exit code 0).")
        print("Final string (locked words highlighted):")
        print(render_colored(s, frozen, word_id))
        sys.exit(0)

if __name__ == '__main__':
    main()
