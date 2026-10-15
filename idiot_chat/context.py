"""Bounded, opt-in text snapshots. Never follow links or traverse excluded folders."""
import codecs
import os
import stat
from dataclasses import dataclass
from pathlib import Path

TEXT_EXTENSIONS = {'.txt', '.md', '.rst', '.csv', '.tsv', '.json', '.yaml', '.yml', '.toml',
                   '.ini', '.cfg', '.xml', '.html', '.css', '.js', '.jsx', '.ts', '.tsx',
                   '.py', '.rb', '.go', '.rs', '.java', '.c', '.h', '.cpp', '.sql', '.sh'}
EXCLUDED_DIRS = {'node_modules', 'venv', 'env', 'dist', 'build', '__pycache__', 'vendor',
                 'target', 'coverage'}
SENSITIVE_NAMES = ('secret', 'credential', 'password', 'private_key', 'api_key', 'token')


@dataclass(frozen=True)
class ContextSnapshot:
    text: str
    files: tuple
    scanned: int
    skipped: int
    truncated: bool


def _clip(text, budget):
    if len(text) <= budget:
        return text
    marker = '\n[truncated]'
    return text[:max(0, budget - len(marker))] + marker[:budget]


def index_folder(folder, max_chars=24000, per_file_chars=6000, max_files=40, max_entries=5000):
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise ValueError('Choose an existing, readable folder.')
    if min(max_chars, per_file_chars, max_files, max_entries) <= 0:
        raise ValueError('Context limits must be positive.')
    paths, pending = [], [root]
    scanned = skipped = 0
    truncated = False
    while pending and scanned < max_entries:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if scanned >= max_entries:
                        truncated = True
                        break
                    scanned += 1
                    name = entry.name.lower()
                    if (name.startswith('.') or entry.is_symlink()
                            or any(word in name for word in SENSITIVE_NAMES)):
                        skipped += 1
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if name not in EXCLUDED_DIRS:
                                pending.append(Path(entry.path))
                            else:
                                skipped += 1
                        elif entry.is_file(follow_symlinks=False) and Path(name).suffix in TEXT_EXTENSIONS:
                            paths.append(Path(entry.path))
                        else:
                            skipped += 1
                    except OSError:
                        skipped += 1
        except OSError:
            if directory == root:
                raise ValueError('Cannot read this folder. Check filesystem permissions.') from None
            skipped += 1
    truncated = truncated or bool(pending)
    chunks, included = [], []
    used = 0
    for path in sorted(paths):
        if len(included) >= max_files or used >= max_chars:
            truncated = True
            break
        try:
            # Recheck at read time: links may have changed since scanning.
            if path.is_symlink() or root not in path.resolve().parents:
                skipped += 1
                continue
            flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
            descriptor = os.open(path, flags)
            with os.fdopen(descriptor, 'rb') as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    skipped += 1
                    continue
                raw = handle.read(per_file_chars * 4 + 1)
            if b'\x00' in raw:
                skipped += 1
                continue
            decoder = codecs.getincrementaldecoder('utf-8-sig')()
            text = decoder.decode(raw, final=len(raw) < per_file_chars * 4 + 1)
            if any(ord(char) < 32 and char not in '\n\r\t' for char in text):
                skipped += 1
                continue
        except (OSError, UnicodeError):
            skipped += 1
            continue
        relative = path.relative_to(root).as_posix()
        file_truncated = len(text) > per_file_chars or len(raw) > per_file_chars * 4
        body = _clip(text + ('\n[truncated]' if file_truncated else ''), per_file_chars)
        chunk = '\n--- %s ---\n%s' % (relative, body)
        remaining = max_chars - used
        clipped = _clip(chunk, remaining)
        truncated = truncated or file_truncated or len(chunk) > remaining
        if len(clipped) <= len('\n--- %s ---\n' % relative):
            truncated = True
            break
        chunks.append(clipped)
        included.append(relative)
        used += len(clipped)
    return ContextSnapshot(''.join(chunks), tuple(included), scanned, skipped, truncated)
