"""Audio must not enter git — checked, not trusted to a convention.

Publication is the one corpus decision that cannot be reversed. A corpus
we built and never published is the only structurally clean position we
hold against training-data contamination (methodology §7.3): once a clip
is committed it is crawled, it enters somebody's next training set, and
no later ruling withdraws it.

`.gitignore` is the mechanism; this is the check that the mechanism is
still in place. It exists because the protection was already claimed once
and was not true: `ml/evaluation/README.md` described `corpus-inbox/` as
a gitignored staging directory for months while only `data/` was ignored,
and two synthesis outputs sat tracked at the repository root the whole
time. A rule nobody verifies is a rule that quietly stops holding.

The test asks git, not the file, because what matters is the *effective*
behaviour: an ignore rule that a later negation cancels would still read
correctly in `.gitignore`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]

AUDIO_SUFFIXES = frozenset({".wav", ".flac", ".mp3", ".m4a", ".ogg"})

#: Deliberately committed audio, if there is ever any. An entry here is a
#: decision with a reason, which is the whole point of an allowlist: it
#: makes the exception visible instead of making the rule negotiable.
ALLOWED_TRACKED_AUDIO: frozenset[str] = frozenset()

#: Where recorded audio is staged before it becomes a released, pinned
#: manifest. Named in the recording protocol; ignored so that doing the
#: homework cannot publish the result.
CORPUS_INBOX = "ml/evaluation/corpus-inbox"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )


def _is_git_repository() -> bool:
    return (REPO / ".git").exists() and _git("rev-parse", "--git-dir").returncode == 0


needs_git = pytest.mark.skipif(
    not _is_git_repository(), reason="not a git checkout (source distribution)"
)


@needs_git
def test_no_audio_is_tracked() -> None:
    tracked = _git("ls-files").stdout.splitlines()
    audio = {
        path
        for path in tracked
        if Path(path).suffix.lower() in AUDIO_SUFFIXES and path not in ALLOWED_TRACKED_AUDIO
    }
    assert not audio, (
        f"audio is tracked in git: {sorted(audio)}. Committing audio is "
        "irreversible — it is crawled and enters training sets. Either "
        "`git rm --cached` it, or add it to ALLOWED_TRACKED_AUDIO with a "
        "reason and a `!` exception in .gitignore."
    )


@needs_git
@pytest.mark.parametrize("suffix", sorted(AUDIO_SUFFIXES))
def test_every_audio_extension_is_ignored(suffix: str) -> None:
    # check-ignore exits 0 when the path WOULD be ignored. The path need
    # not exist, which is the point: the guard has to hold before the
    # recording is made, not after.
    probe = f"scratch-probe{suffix}"
    assert _git("check-ignore", "-q", probe).returncode == 0, (
        f"{suffix} files are not ignored; recording one and committing it "
        "would publish it permanently"
    )


@needs_git
def test_the_corpus_staging_directory_is_ignored() -> None:
    # The README tells the founder to record into this directory. That
    # instruction is safe only while this holds.
    assert _git("check-ignore", "-q", f"{CORPUS_INBOX}/en-read-01.wav").returncode == 0, (
        f"{CORPUS_INBOX}/ is not ignored — the recording protocol in "
        "ml/evaluation/README.md would publish the corpus it collects"
    )


@needs_git
def test_the_staging_directory_stays_ignored_whatever_it_holds() -> None:
    # Consent forms, speaker rosters and session notes land here too, and
    # they are exactly the material that must never be published.
    for name in ("speakers.csv", "consent/participant-01.pdf", "session-notes.md"):
        assert _git("check-ignore", "-q", f"{CORPUS_INBOX}/{name}").returncode == 0, (
            f"{CORPUS_INBOX}/{name} is not ignored; the directory must be "
            "ignored as a directory, not only by audio extension"
        )
