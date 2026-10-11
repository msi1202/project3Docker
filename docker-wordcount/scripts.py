#!/usr/bin/env python3

import os
import re
import socket
import sys
from collections import Counter
from datetime import datetime, timezone

DATA_DIR = os.environ.get("DATA_DIR", "/home/data")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
RESULT_FILE = os.path.join(OUTPUT_DIR, "result.txt")

FILE_IF = "IF.txt"
FILE_SONG = "AlwaysRememberUsThisWay.txt"

# A word is a run of letters, optionally joined by apostrophes (don't, rock'n'roll).
# Digits are allowed so a line like "Verse 2" still counts the "2".
WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")

# Contractions whose expansion can't be worked out from a simple suffix rule.
SPECIAL_CONTRACTIONS = {
    "won't": ["will", "not"],
    "can't": ["can", "not"],
    "shan't": ["shall", "not"],
    "ain't": ["am", "not"],
    "let's": ["let", "us"],
    "y'all": ["you", "all"],
    "'cause": ["because"],
    "'til": ["until"],
    "'em": ["them"],
    "o'clock": ["of", "the", "clock"],
    "ma'am": ["madam"],
}

# Words where 's means "is" (it's -> it is). On any other word 's is
# treated as possessive (Mary's -> mary).
S_MEANS_IS = {
    "it", "that", "what", "there", "here", "he", "she", "who", "where",
    "when", "why", "how", "everything", "nothing", "something", "everyone",
    "someone", "this",
}

SUFFIXES = [
    ("n't", ["not"]),
    ("'re", ["are"]),
    ("'ve", ["have"]),
    ("'ll", ["will"]),
    ("'d", ["would"]),
    ("'m", ["am"]),
]


def read_text(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.isfile(path):
        sys.exit(f"ERROR: {path} not found. Copy the file into {DATA_DIR}.")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def normalize(text):
    """Lower-case the text and turn curly quotes into a plain apostrophe."""
    text = text.lower()
    for ch in ("’", "‘", "ʼ", "`", "´"):
        text = text.replace(ch, "'")
    return text


def tokenize(text):
    """Return the words in the text. A contraction stays one word."""
    return WORD_RE.findall(normalize(text))


def expand_contraction(word):
    """Split one contraction into its parts: "i'm" -> ["i", "am"]."""
    if "'" not in word:
        return [word]
    if word in SPECIAL_CONTRACTIONS:
        return list(SPECIAL_CONTRACTIONS[word])
    for suffix, replacement in SUFFIXES:
        if word.endswith(suffix) and len(word) > len(suffix):
            return [word[: -len(suffix)]] + replacement
    if word.endswith("'s"):
        base = word[:-2]
        return [base, "is"] if base in S_MEANS_IS else [base]
    # Anything else (rock'n'roll, o'er): split on the apostrophe.
    return [part for part in word.split("'") if part]


def tokenize_with_contractions_split(text):
    """Like tokenize(), but contractions are split into separate words."""
    text = normalize(text)
    words = []
    for match in re.finditer(r"'?[a-z0-9]+(?:'[a-z0-9]+)*", text):
        token = match.group(0)
        if token.startswith("'") and token not in SPECIAL_CONTRACTIONS:
            token = token[1:]  # a stray opening quote, not a contraction
        words.extend(expand_contraction(token))
    return words


def top_n(words, n=3):
    return Counter(words).most_common(n)


def get_ip_addresses():
    """Return (container_ip, host_ip). host_ip is None if it can't be found."""
    try:
        container_ip = socket.gethostbyname(socket.gethostname())
    except OSError:
        container_ip = "unknown"

    # If gethostname() resolves to 127.x, ask the OS which interface it would
    # use to reach the outside world. connect() on UDP sends no packets.
    if container_ip.startswith("127.") or container_ip == "unknown":
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                container_ip = s.getsockname()[0]
        except OSError:
            pass

    # The host machine's own IP, if passed in, or Docker Desktop's host alias.
    host_ip = os.environ.get("HOST_IP")
    if not host_ip:
        try:
            host_ip = socket.gethostbyname("host.docker.internal")
        except OSError:
            host_ip = None
    return container_ip, host_ip


def format_top(pairs):
    return "\n".join(
        f"  {rank}. {word:<12} {count}" for rank, (word, count) in enumerate(pairs, 1)
    )


def main():
    if_text = read_text(FILE_IF)
    song_text = read_text(FILE_SONG)

    # a) word count per file (a contraction counts as one word here)
    if_words = tokenize(if_text)
    song_words = tokenize(song_text)
    if_count = len(if_words)
    song_count = len(song_words)

    # b) grand total
    grand_total = if_count + song_count

    # c) top 3 in IF.txt
    if_top3 = top_n(if_words)

    # d) split contractions, then top 3 in AlwaysRememberUsThisWay.txt
    song_words_split = tokenize_with_contractions_split(song_text)
    song_top3 = top_n(song_words_split)
    contractions_found = sorted({w for w in song_words if "'" in w})

    # e) IP address
    container_ip, host_ip = get_ip_addresses()

    line = "=" * 56
    lines = [
        line,
        "            DOCKER WORD COUNT PROJECT - RESULTS",
        line,
        f"Run at (UTC): {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
        f"Data folder:  {DATA_DIR}",
        "",
        "a) Total words in each file",
        f"  {FILE_IF:<30} {if_count}",
        f"  {FILE_SONG:<30} {song_count}",
        "",
        "b) Grand total of words (both files)",
        f"  {grand_total}",
        "",
        f"c) Top 3 most frequent words in {FILE_IF}",
        format_top(if_top3),
        "",
        f"d) Top 3 most frequent words in {FILE_SONG}",
        "   (after splitting contractions, e.g. I'm -> I am, can't -> can not)",
        format_top(song_top3),
        f"  Contractions found and split: {len(contractions_found)} distinct",
        f"  ({', '.join(contractions_found) if contractions_found else 'none'})",
        f"  Word count with contractions split: {len(song_words_split)}",
        "",
        "e) IP address of the machine running this container",
        f"  Container IP:  {container_ip}",
    ]
    if host_ip:
        lines.append(f"  Host IP:       {host_ip}")
    lines += [
        "",
        f"f) Results written to {RESULT_FILE}",
        line,
    ]

    # f) write result.txt, then print it to the console
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    with open(RESULT_FILE, "r", encoding="utf-8") as f:
        print(f.read(), end="")


if __name__ == "__main__":
    main()