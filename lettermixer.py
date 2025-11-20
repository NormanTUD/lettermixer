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
    p.add_argument('-n', type=int, default=100, help='total number of characters to generate')
    p.add_argument('--space-prob', type=float, default=0.04, help='base probability to insert space when generating')
    p.add_argument('--min-block', type=int, default=3, help='minimum letters between spaces')
    p.add_argument('--sleep', type=float, default=0.05, help='sleep between frames (seconds)')
    p.add_argument('--dict', type=str, default='/usr/share/dict/ngerman', help='path to wordlist')
    return p.parse_args()

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stderr)
    return logging.getLogger('evolver')

def load_wordlist(path, min_len=1):
    import re
    words = set()
    pattern = re.compile(r'^[a-zA-Z]+$')  # nur Buchstaben
    try:
        with open(path, encoding='utf-8', errors='ignore') as fh:
            for ln in fh:
                w = ln.strip()
                if not w:
                    continue
                if w.isupper():  # optional: kann man auch entfernen
                    continue
                if not pattern.match(w):
                    continue
                w = w.lower()
                if len(w) >= min_len:
                    words.add(w)
    except FileNotFoundError:
        raise SystemExit(f'Wordlist not found: {path}')
    from collections import defaultdict
    by_len = defaultdict(list)
    for w in words:
        by_len[len(w)].append(w)
    return words, by_len

def random_text(total_chars, min_block=3, space_prob=0.04):
    parts = []
    cur_len = 0
    while cur_len < total_chars:
        block_len = random.randint(min_block, min_block + 6)
        block = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(block_len))
        if parts and random.random() < space_prob:
            parts.append(' ')
            cur_len += 1
            if cur_len >= total_chars:
                break
        parts.append(block)
        cur_len += len(block)
    s = ''.join(parts)[:total_chars]
    s = re.sub(r' {2,}', ' ', s)
    return s

def find_letter_blocks(s):
    return [m for m in re.finditer(r'[a-z]{3,}', s)]

def pick_dict_word_for_length(by_len, target_len):
    if target_len in by_len and by_len[target_len]:
        return random.choice(by_len[target_len])
    # try nearby lengths
    for delta in range(1, 6):
        for L in (target_len - delta, target_len + delta):
            if L > 0 and L in by_len and by_len[L]:
                w = random.choice(by_len[L])
                if len(w) <= target_len + 2:
                    return w
    return None

def mutate_block(block, space_prob, min_block):
    chars = list(block)
    for i in range(len(chars)):
        if random.random() < 0.15:
            chars[i] = random.choice('abcdefghijklmnopqrstuvwxyz')
    return ''.join(chars)

def try_split_block(block, min_block):
    if len(block) < min_block * 2:
        return None
    split_pos = random.randint(min_block, len(block) - min_block)
    left = block[:split_pos]
    right = block[split_pos:]
    return left + ' ' + right

def try_merge_neighbors(s, idx_start, idx_end):
    left = s[:idx_start].rstrip()
    right = s[idx_end:].lstrip()
    # try remove nearest space between left and right if it exists
    m = re.search(r' (?! )', s[:idx_start+1][::-1])  # not necessary; simpler approach below
    # simpler: remove one space around the block if exists (merge around index)
    s2 = re.sub(r' {2,}', ' ', s)
    return s2

def iterate_once(s, wordset, by_len, epoch, min_block, space_prob, logger):
    blocks = find_letter_blocks(s)
    if not blocks:
        return s
    s_list = list(s)
    for m in blocks:
        start, end = m.span()
        block = s[start:end]
        if block in wordset:
            continue
        p_replace = min(0.02 + epoch * 0.003, 0.65)
        r = random.random()
        if r < p_replace:
            w = pick_dict_word_for_length(by_len, len(block))
            if w:
                w = w[:len(block)]
                s_list[start:end] = list(w)
                continue
        if r < p_replace + 0.12:
            candidate = try_split_block(block, min_block)
            if candidate:
                if len(candidate) == len(block) + 1:
                    s_list[start:end] = list(candidate)
                    continue
        if r < p_replace + 0.12 + 0.10:
            new_block = mutate_block(block, space_prob, min_block)
            if len(new_block) >= min_block:
                s_list[start:end] = list(new_block)
                continue
        # fallback: small random rewrite but keep it as a block (no spaces)
        fallback = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(len(block)))
        s_list[start:end] = list(fallback)
    s2 = ''.join(s_list)
    s2 = re.sub(r' {2,}', ' ', s2)
    # avoid isolated single letters: if any token of length 1 exists, merge it with left or right neighbor
    tokens = re.findall(r'\b\w+\b', s2)
    if any(len(t) == 1 for t in tokens):
        parts = re.split(r'(\s+)', s2)
        rebuilt = []
        for i, p in enumerate(parts):
            if re.fullmatch(r'\s+', p):
                rebuilt.append(p)
                continue
            if len(p) == 1:
                left = rebuilt[-1] if rebuilt and not re.fullmatch(r'\s+', rebuilt[-1]) else None
                if left and len(left) >= min_block:
                    rebuilt[-1] = left + p
                    continue
                # try merge with next non-space part
                j = i + 1
                while j < len(parts) and re.fullmatch(r'\s+', parts[j]):
                    j += 1
                if j < len(parts):
                    parts[j] = p + parts[j]
                    continue
                # else just keep (rare)
            rebuilt.append(p)
        s2 = ''.join(rebuilt)
        s2 = re.sub(r' {2,}', ' ', s2)
    return s2

def clear_and_print(s):
    print('\033[H\033[J', end='')
    print(s)

def main():
    args = parse_args()
    logger = setup_logging()
    wordset, by_len = load_wordlist(args.dict, min_len=1)
    text = random_text(args.n, min_block=args.min_block, space_prob=args.space_prob)
    epoch = 0
    try:
        while True:
            clear_and_print(text)
            time.sleep(args.sleep)
            new_text = iterate_once(text, wordset, by_len, epoch, args.min_block, args.space_prob, logger)
            tokens = [t for t in re.findall(r'\b\w+\b', new_text) if t]
            if tokens and all(t.lower() in wordset for t in tokens):
                clear_and_print(new_text)
                logger.info('All tokens are dictionary words; finished.')
                break
            if new_text == text:
                epoch += 1
            else:
                epoch += 1
            text = new_text
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting cleanly (exit code 0).")
        sys.exit(0)

if __name__ == '__main__':
    main()
