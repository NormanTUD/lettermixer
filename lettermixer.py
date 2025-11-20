#!/usr/bin/env python3
import argparse
import logging
import random
import re
import sys
import time
from collections import defaultdict

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("-n", type=int, default=120, help="total characters")
    p.add_argument("--min-block", type=int, default=3, help="minimum letters per block")
    p.add_argument("--mutrate", type=float, default=0.10, help="per-char mutation probability for unfrozen letters")
    p.add_argument("--space-prob", type=float, default=0.04, help="base probability to create a space when free")
    p.add_argument("--sleep", type=float, default=0.05, help="delay between frames")
    p.add_argument("--dict", type=str, default="/usr/share/dict/ngerman", help="path to wordlist")
    return p.parse_args()

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    return logging.getLogger("weasel-evo")

def load_wordset(path, min_block):
    pat = re.compile(r"^[a-zA-Z]+$")
    wordset = set()
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            for ln in fh:
                w = ln.strip()
                if not w:
                    continue
                if not pat.match(w):
                    continue
                lw = w.lower()
                if len(lw) >= min_block:
                    wordset.add(lw)
    except FileNotFoundError:
        raise SystemExit(f"Wordlist not found: {path}")
    return wordset

def build_random_string(n, min_block, space_prob):
    # build left-to-right ensuring: no leading/trailing space, no double spaces, >=min_block letters between spaces
    out = []
    last_space_pos = -1
    i = 0
    while i < n:
        # decide whether we can place a space here
        can_place_space = False
        if i != 0 and i != n-1:
            left_letters = i - (last_space_pos + 1)
            # ensure at least min_block letters since last space
            if left_letters >= min_block:
                # ensure room for min_block after this space
                if (n - i - 1) >= min_block:
                    can_place_space = True
        if can_place_space and random.random() < space_prob:
            out.append(' ')
            last_space_pos = i
        else:
            out.append(random.choice('abcdefghijklmnopqrstuvwxyz'))
        i += 1
    # final sanitise: collapse multiple spaces (shouldn't happen) and trim ends
    s = ''.join(out)
    s = re.sub(r' {2,}', ' ', s).strip()
    # ensure min length by padding if trimmed
    while len(s) < n:
        s += random.choice('abcdefghijklmnopqrstuvwxyz')
    return s[:n]

def find_dictionary_matches(s, wordset, min_block):
    # Return non-overlapping matches (start,end,word)
    candidates = []
    for m in re.finditer(r'[a-z]{%d,}' % min_block, s):
        sub = m.group()
        if sub in wordset:
            # check word boundaries: either start or space before, and either end or space after
            start, end = m.span()
            left_ok = (start == 0) or (s[start-1] == ' ')
            right_ok = (end == len(s)) or (s[end] == ' ')
            if left_ok and right_ok:
                candidates.append((start, end, sub))
    # sort by length desc, then by start to freeze longer words first, avoid overlaps
    candidates.sort(key=lambda x: (-(x[1]-x[0]), x[0]))
    chosen = []
    occ = [False] * len(s)
    for start, end, sub in candidates:
        if any(occ[i] for i in range(start, end)):
            continue
        chosen.append((start, end, sub))
        for i in range(start, end):
            occ[i] = True
    return chosen

def freeze_matches(frozen, s, matches):
    n = len(s)
    for start, end, _ in matches:
        for i in range(start, end):
            frozen[i] = True
        # freeze adjacent spaces if they exist (and are spaces)
        if start - 1 >= 0 and s[start-1] == ' ':
            frozen[start-1] = True
        if end < n and s[end] == ' ':
            frozen[end] = True

def get_next_frozen_space_index(s, frozen, i):
    # return smallest j>i such that frozen[j] and s[j]==' ', else return len(s)
    n = len(s)
    for j in range(i+1, n):
        if frozen[j] and s[j] == ' ':
            return j
    return n

def get_prev_frozen_space_index(s, frozen, i):
    # largest j<i such that frozen[j] and s[j]==' ', else -1
    for j in range(i-1, -1, -1):
        if frozen[j] and s[j] == ' ':
            return j
    return -1

def mutate_unfrozen(s, frozen, min_block, space_prob, mutrate):
    n = len(s)
    out = list(s)
    # find previous (to left) space index (either frozen space or a placed space during this pass)
    last_space = -1
    # Precompute next frozen-space indices to ensure we don't create too-short gaps
    next_frozen_space = [n] * n
    next_idx = n
    for i in range(n-1, -1, -1):
        if frozen[i] and s[i] == ' ':
            next_idx = i
        next_frozen_space[i] = next_idx

    for i in range(n):
        if frozen[i]:
            # respect frozen char and update last_space if it's a space
            out[i] = s[i]
            if s[i] == ' ':
                last_space = i
            continue

        # cannot be space at borders
        if i == 0 or i == n - 1:
            # must be letter
            ch = s[i]
            if random.random() < mutrate:
                ch = random.choice('abcdefghijklmnopqrstuvwxyz')
            out[i] = ch
            continue

        # count letters since last_space
        left_letters = i - (last_space + 1)
        # distance to next frozen space
        nfsp = next_frozen_space[i]
        right_available = nfsp - i - 1  # letters we can place before hitting that frozen space
        # If nfsp==n then right_available = n - i -1

        # decide whether to put space here
        can_place_space = False
        if left_letters >= min_block and right_available >= min_block:
            # also ensure previous char is not space
            prev_char = out[i-1]
            if prev_char != ' ':
                can_place_space = True

        if can_place_space and random.random() < space_prob:
            out[i] = ' '
            last_space = i
            continue

        # otherwise place or mutate letter
        ch = s[i]
        if random.random() < mutrate:
            ch = random.choice('abcdefghijklmnopqrstuvwxyz')
        out[i] = ch
        # if we just placed a letter, nothing else
    # final sanitization: collapse accidental double spaces and fix ends (shouldn't be needed often)
    s2 = ''.join(out)
    s2 = re.sub(r' {2,}', ' ', s2).strip()
    # if trimming removed chars from edges, pad with letters to keep length
    if len(s2) < n:
        s2 = s2 + ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(n - len(s2)))
    return s2[:n]

def all_tokens_valid(s, wordset, min_block):
    toks = re.findall(r'[a-z]{%d,}' % min_block, s)
    if not toks:
        return False
    return all(t in wordset for t in toks)

def clear_and_print(s):
    print('\033[H\033[J', end='')
    print(s)

def main():
    args = parse_args()
    logger = setup_logging()
    wordset = load_wordset(args.dict, args.min_block)
    if not wordset:
        raise SystemExit("No words loaded of required min length; adjust dictionary or min-block.")

    s = build_random_string(args.n, args.min_block, args.space_prob)
    frozen = [False] * len(s)
    epoch = 0

    try:
        while True:
            # detect dictionary words and freeze them (and their surrounding spaces)
            matches = find_dictionary_matches(s, wordwordset := wordset, min_block := args.min_block)  # safe names
            # note: matches are non-overlapping and prefer longer words
            freeze_matches(frozen, s, matches)

            clear_and_print(s)
            time.sleep(args.sleep)

            # termination: all letter tokens of length >= min_block are dictionary words
            if all_tokens_valid(s, wordset, args.min_block):
                logger.info("All tokens are dictionary words; finished.")
                break

            # mutate unfrozen positions (letters and spaces can change)
            s = mutate_unfrozen(s, frozen, args.min_block, args.space_prob, args.mutrate)
            epoch += 1

    except KeyboardInterrupt:
        print("\nInterrupted cleanly. Exit 0.")
        sys.exit(0)

if __name__ == "__main__":
    main()
