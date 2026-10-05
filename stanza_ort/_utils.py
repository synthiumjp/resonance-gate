"""Whitespace/MISC helpers copied from stanza.models.common.utils (Stanza 1.14.0, Apache-2.0)."""
def escape_misc_space(space):
    spaces = []
    for char in space:
        if char == ' ':
            spaces.append('\\s')
        elif char == '\t':
            spaces.append('\\t')
        elif char == '\r':
            spaces.append('\\r')
        elif char == '\n':
            spaces.append('\\n')
        elif char == '|':
            spaces.append('\\p')
        elif char == '\\':
            spaces.append('\\\\')
        elif char == ' ':
            spaces.append('\\u00A0')
        else:
            spaces.append(char)
    escaped_space = "".join(spaces)
    return escaped_space

def unescape_misc_space(misc_space):
    spaces = []
    pos = 0
    while pos < len(misc_space):
        if misc_space[pos:pos+2] == '\\s':
            spaces.append(' ')
            pos += 2
        elif misc_space[pos:pos+2] == '\\t':
            spaces.append('\t')
            pos += 2
        elif misc_space[pos:pos+2] == '\\r':
            spaces.append('\r')
            pos += 2
        elif misc_space[pos:pos+2] == '\\n':
            spaces.append('\n')
            pos += 2
        elif misc_space[pos:pos+2] == '\\p':
            spaces.append('|')
            pos += 2
        elif misc_space[pos:pos+2] == '\\\\':
            spaces.append('\\')
            pos += 2
        elif misc_space[pos:pos+6] == '\\u00A0':
            spaces.append(' ')
            pos += 6
        else:
            spaces.append(misc_space[pos])
            pos += 1
    unescaped_space = "".join(spaces)
    return unescaped_space

def space_before_to_misc(space):
    """
    Convert whitespace to SpacesBefore specifically for the start of a document.

    In general, UD datasets do not have both SpacesAfter on a token and SpacesBefore on the next token.

    The space(s) are only marked on one of the tokens.

    Only at the very beginning of a document is it necessary to mark what spaces occurred before the actual text,
    and the default assumption is that there is no space if there is no SpacesBefore annotation.
    """
    if not space:
        return ""
    escaped_space = escape_misc_space(space)
    return "SpacesBefore=%s" % escaped_space

def space_after_to_misc(space):
    """
    Convert whitespace back to the escaped format - either SpaceAfter=No or SpacesAfter=...
    """
    if not space:
        return "SpaceAfter=No"
    if space == " ":
        return ""
    escaped_space = escape_misc_space(space)
    return "SpacesAfter=%s" % escaped_space

def misc_to_space_before(misc):
    """
    Find any SpacesBefore annotation in the MISC column and turn it into a space value
    """
    if not misc:
        return ""
    pieces = misc.split("|")
    for piece in pieces:
        if not piece.lower().startswith("spacesbefore="):
            continue
        misc_space = piece.split("=", maxsplit=1)[1]
        return unescape_misc_space(misc_space)
    return ""

def misc_to_space_after(misc):
    """
    Convert either SpaceAfter=No or the SpacesAfter annotation

    see https://universaldependencies.org/misc.html#spacesafter

    We compensate for some treebanks using SpaceAfter=\n instead of SpacesAfter=\n
    On the way back, though, those annotations will be turned into SpacesAfter
    """
    if not misc:
        return " "
    pieces = misc.split("|")
    if any(piece.lower() == "spaceafter=no" for piece in pieces):
        return ""
    if "SpaceAfter=Yes" in pieces:
        # as of UD 2.11, the Cantonese treebank had this as a misc feature
        return " "
    if "SpaceAfter=No~" in pieces:
        # as of UD 2.11, a weird typo in the Russian Taiga dataset
        return ""
    for piece in pieces:
        if piece.startswith("SpaceAfter=") or piece.startswith("SpacesAfter="):
            misc_space = piece.split("=", maxsplit=1)[1]
            return unescape_misc_space(misc_space)
    return " "
