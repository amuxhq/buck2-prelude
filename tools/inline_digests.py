"""Write each Android toolchain download's SHA-256 and size next to its SHA-1.

usage: inline_digests.py PRELUDE_DIR [DIGESTS_BZL] [--fetch]

A declaration that already has a SHA-256 is left as it is, so after a rebase
only jars the release added need one. DIGESTS_BZL, optional, is a table of
SHA-1 to (sha256, size) or None. A declaration found in neither is fetched
(with --fetch) and checked against its SHA-1; without --fetch it is an error.
"""

import hashlib
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

CALL = re.compile(r"^(third_party_(?:jar|aar|exe)|buck_prebuilt_artifact)\(\n(.*?)^\)", re.M | re.S)
SHA1_LINE = re.compile(r'^(\s*)(oss_)?sha1 = "([0-9a-f]{40})",\n', re.M)
URL = re.compile(r'^\s*(?:oss_)?url = "([^"]+)",$', re.M)
ENTRY = re.compile(r'^    "([0-9a-f]{40})": (?:\("([0-9a-f]{64})", (\d+)\)|None),', re.M)
CENTRAL = "https://repo1.maven.org/maven2"


def maven_url(url):
    if not url.startswith("mvn:"):
        return url
    parts = url.split(":")[1:]
    repo = CENTRAL
    if len(parts) in (6, 7):
        repo, parts = parts[0] + ":" + parts[1], parts[2:]
    if len(parts) == 4:
        group, artifact, kind, version = parts
        classifier = ""
    else:
        group, artifact, kind, classifier, version = parts
        classifier = "-" + classifier
    ext = "-sources.jar" if kind == "src" else "." + kind
    return f"{repo}/{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}{classifier}{ext}"


def fetch(sha1, url):
    print(f"fetching {url}", file=sys.stderr)
    try:
        with urllib.request.urlopen(url, timeout=300) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    if hashlib.sha1(data).hexdigest() != sha1:
        sys.exit(f"{url}: SHA-1 mismatch, expected {sha1}")
    return hashlib.sha256(data).hexdigest(), len(data)


def main():
    args = [a for a in sys.argv[1:] if a != "--fetch"]
    allow_fetch = "--fetch" in sys.argv
    prelude = Path(args[0])
    table = args[1] if len(args) > 1 else None
    digests = {}
    if table:
        digests = {s1: (s256, int(n)) if s256 else None for s1, s256, n in ENTRY.findall(Path(table).read_text())}
    done = skipped = 0
    for path in sorted(p for p in (prelude / "toolchains/android").rglob("BUCK") if p.is_file()):
        text = path.read_text()
        if not CALL.search(text):
            continue

        def patch_call(m):
            nonlocal done, skipped
            body = m.group(2)
            if "sha256 = " in body:
                return m.group(0)
            s = SHA1_LINE.search(body)
            if not s:
                return m.group(0)  # Meta-internal artifact only
            indent, oss, sha1 = s.group(1), s.group(2) or "", s.group(3)
            if sha1 not in digests:
                if not allow_fetch:
                    sys.exit(f"{path}: no digest for {sha1}; rerun with --fetch")
                digests[sha1] = fetch(sha1, maven_url(URL.search(body).group(1)))
            d = digests[sha1]
            if d is None:
                skipped += 1
                return m.group(0)  # origin 404s: leave as upstream declares it
            done += 1
            extra = f'{indent}{oss}sha256 = "{d[0]}",\n{indent}{oss}size_bytes = {d[1]},\n'
            body = body[: s.end()] + extra + body[s.end():]
            return f"{m.group(1)}(\n{body})"

        new = CALL.sub(patch_call, text)
        if new != text:
            path.write_text(new)
    print(f"{done} declarations given a SHA-256 and size, {skipped} left alone (origin 404s)", file=sys.stderr)


main()
