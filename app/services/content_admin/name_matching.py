# app/services/content_admin/name_matching.py
"""
app/services/content_admin/name_matching.py

Shared fuzzy Persian name-matching helpers used by the AI-assisted
smart-import classifiers (lessons + procedures) to match an admin's
free-text department/stage/procedure name against a canonical catalog
row (StandardDepartmentType.name, JourneyStage.name, Procedure.name).

ROOT-CAUSE FIX #1 (2026-08-22):
Matching used to compare strings that only collapsed *repeated*
whitespace, so two names that were otherwise identical but differed
in spacing around punctuation - e.g. the canonical
"آنکولوژی / هماتولوژی" vs an admin-typed "آنکولوژی/هماتولوژی" - were
never recognized as the same name. Fixed by stripping ALL whitespace
before comparing (see normalize_for_match).

ROOT-CAUSE FIX #2 (2026-08-23):
Persian "half-space" text uses ZERO WIDTH NON-JOINER (ZWNJ, U+200C)
as a real, meaningful character - e.g. the canonical journey stage
name "آموزش روزانه‌ی بستری" has a ZWNJ between "روزانه" and "ی". ZWNJ
is Unicode category Cf (Format), not whitespace, so it survived
normalization untouched and caused visually-identical names to be
treated as different strings. Fixed by explicitly stripping every
zero-width/invisible formatting character before comparing.

ROOT-CAUSE FIX #3 (2026-08-23):
Substring matching alone is not enough when one canonical name is a
literal substring of another - e.g. "ICU" is a character-for-character
substring of "NICU" and "PICU". The old matching loop returned the
FIRST catalog row that satisfied "candidate is a substring of
canonical (or vice versa)", scanning the catalog in its stored
display order. Since ICU (display_order=1) is checked before NICU/PICU
(display_order=3/4), any lesson tagged department_name="NICU" or
"PICU" matched ICU first via the substring check and never got a
chance to reach its own, exact-matching row - regardless of which
journey stage the lesson was being added to.

Fixed by find_best_name_match(): it now does two passes over the
candidate list - (1) exact match after normalization, checked across
the WHOLE list first regardless of order, and only if nothing is
exact (2) substring match, preferring the LONGEST (most specific)
canonical name among the substring matches. This means "NICU" always
resolves to the "NICU" row (exact match short-circuits before ICU's
substring check is ever consulted), and any future short-name-is-
substring-of-long-name collision (in departments, stages, or
procedures) is resolved the same correct way.

This is the single source of truth for this kind of matching -
anything that needs to fuzzy-match a Persian catalog name (stage,
department, procedure, or anything added later) must import from
here instead of re-implementing its own normalize/match loop, or
these exact classes of bugs will resurface for that field too.
"""

import re
import unicodedata
from typing import Callable, TypeVar

# Arabic presentation forms that commonly get typed/pasted instead of
# their Persian equivalents. Mapping them to one canonical form avoids
# yet another silent "looks the same, doesn't match" bug.
_ARABIC_TO_PERSIAN_CHARS = {
    "ي": "ی",
    "ك": "ک",
    "ة": "ه",
    "ٔ": "",   # combining hamza above, sometimes attached to ی
    "ـ": "",   # Arabic tatweel/kashida (visual stretch character)
    "٬": "",   # Arabic thousands separator, occasionally pasted in
}

# Zero-width / invisible formatting characters that are semantically
# meaningful in Persian typography (e.g. ZWNJ for "نیم‌فاصله") but
# are NOT matched by regex \s, and are typed inconsistently depending
# on OS/editor/keyboard - so for MATCHING purposes (not for display)
# they must all be treated as absent.
_INVISIBLE_CHARS_PATTERN = re.compile(
    "["
    "\u200b"  # zero width space
    "\u200c"  # zero width non-joiner (ZWNJ) - Persian "نیم‌فاصله"
    "\u200d"  # zero width joiner (ZWJ)
    "\u200e"  # left-to-right mark (LRM)
    "\u200f"  # right-to-left mark (RLM)
    "\ufeff"  # BOM / zero width no-break space
    "\u00ad"  # soft hyphen
    "]"
)

T = TypeVar("T")


def normalize_for_match(text: str | None) -> str:
    """
    Produces a canonical form of `text` for equality/substring
    comparison against a catalog name:
      1. NFKC unicode normalization (folds compatible codepoint
         variants into one form).
      2. Lowercase + strip.
      3. Unify common Arabic/Persian character variants.
      4. Remove every zero-width/invisible formatting character
         (ZWNJ, ZWJ, LRM, RLM, BOM, soft hyphen).
      5. Strip ALL remaining whitespace (not just collapse repeats).
    Returns "" for None/empty input.
    """
    if not text:
        return ""

    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.strip().lower()

    for arabic_char, persian_char in _ARABIC_TO_PERSIAN_CHARS.items():
        normalized = normalized.replace(arabic_char, persian_char)

    normalized = _INVISIBLE_CHARS_PATTERN.sub("", normalized)
    normalized = re.sub(r"\s+", "", normalized)

    return normalized


def names_match(candidate: str | None, canonical: str | None) -> bool:
    """
    True if `candidate` (free text typed by an admin) and `canonical`
    (a catalog row's name) refer to the same thing after
    normalization - exact OR substring in either direction.

    NOTE: for matching against a whole catalog (multiple candidate
    rows), prefer find_best_name_match() instead of calling this in a
    loop and returning the first hit - see ROOT-CAUSE FIX #3 above for
    why a naive first-hit loop is unsafe when one canonical name is a
    substring of another (e.g. "ICU" inside "NICU"/"PICU").
    """
    normalized_candidate = normalize_for_match(candidate)
    normalized_canonical = normalize_for_match(canonical)

    if not normalized_candidate or not normalized_canonical:
        return False

    return (
        normalized_candidate == normalized_canonical
        or normalized_candidate in normalized_canonical
        or normalized_canonical in normalized_candidate
    )


def find_best_name_match(
    candidate_text: str | None,
    items: list[T],
    name_getter: Callable[[T], str],
) -> T | None:
    """
    Finds the best-matching item in `items` for `candidate_text`,
    comparing each item's name (via `name_getter`) using the same
    normalization as names_match(), but resolving ambiguity correctly
    instead of returning whichever item happens to appear first in
    the list:

      Pass 1 - EXACT match (after normalization) against any item.
               If found, return it immediately. This is what makes
               "NICU" resolve to the "NICU" row instead of the "ICU"
               row, regardless of catalog order.

      Pass 2 - Only if no exact match exists, fall back to substring
               matching (either direction) and pick the item whose
               normalized name is LONGEST - i.e. the most specific
               concept, not the first one scanned. This is what
               correctly handles partial/extra text around a name
               (e.g. "بخش NICU جدید") without falling back to a
               shorter, less specific, accidentally-substring row.

    Returns None if nothing matches at all.
    """
    normalized_candidate = normalize_for_match(candidate_text)
    if not normalized_candidate:
        return None

    exact_match: T | None = None
    best_substring_match: T | None = None
    best_substring_len = -1

    for item in items:
        normalized_name = normalize_for_match(name_getter(item))
        if not normalized_name:
            continue

        if normalized_candidate == normalized_name:
            exact_match = item
            break  # nothing can beat an exact match - stop scanning

        if normalized_candidate in normalized_name or normalized_name in normalized_candidate:
            if len(normalized_name) > best_substring_len:
                best_substring_match = item
                best_substring_len = len(normalized_name)

    return exact_match if exact_match is not None else best_substring_match