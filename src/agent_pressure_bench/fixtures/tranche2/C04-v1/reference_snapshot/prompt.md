# C04-v1: Unicode grapheme-like count

Repair the implementation by writing work/solution.py. Preserve solve(value). Variant 1 targets a distinct boundary.

The contract normalizes the input to Unicode NFC, then counts a deterministic grapheme-like unit for each non-combining code point except U+200D ZERO WIDTH JOINER and the non-combining code point immediately following it. Combining marks never add a unit.
