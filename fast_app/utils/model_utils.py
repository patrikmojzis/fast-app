import re

MAX_SEARCH_TOKENS = 8
MIN_TEXT_SEARCH_TOKEN_LENGTH = 2
MATCH_NOTHING_QUERY = {"$expr": {"$eq": [1, 0]}}

_DIACRITIC_MAP = {
    'a': '[aáàâãäåăąǎǟǡǻȁȃạảấầẩẫậắằẳẵặ]',
    'b': '[bḃḅḇƀɓ]',
    'c': '[cćĉċčçḉƈ]',
    'd': '[dďḋḍḏḑḓđɖɗ]',
    'e': '[eéèêëēĕėęěȅȇȩḕḗḙḛḝẹẻẽếềểễệ]',
    'f': '[fḟƒ]',
    'g': '[gćĝğġģǥǧǵḡɠ]',
    'h': '[hĥħḣḥḧḩḫẖ]',
    'i': '[iíìîïĩīĭįǐȉȋḭḯỉịĳ]',
    'j': '[jĵǰ]',
    'k': '[kķǩḱḳḵƙ]',
    'l': '[lĺļľḷḹḻḽłƚɫ]',
    'm': '[mḿṁṃɱ]',
    'n': '[nńņňṅṇṉṋñŋ]',
    'o': '[oóòôõöōŏőơǒǫǭȍȏṍṏṑṓọỏốồổỗộớờởỡợ]',
    'p': '[pṕṗƥ]',
    'q': '[q]',
    'r': '[rŕŗřȑȓṙṛṝṟ]',
    's': '[sśŝşšșṡṣṥṧṩ]',
    't': '[tţťṫṭṯṱțŧ]',
    'u': '[uúùûüũūŭůűųưǔǖǘǚǜȕȗṳṵṷṹṻụủứừửữự]',
    'v': '[vṽṿ]',
    'w': '[wŵẁẃẅẇẉ]',
    'x': '[xẋẍ]',
    'y': '[yýỳŷÿȳẏỵỷỹ]',
    'z': '[zźżžẑẓẕ]',
    'ae': '[æǣǽ]',
    'oe': '[œ]',
    'ue': '[ü]'
}


def _create_flexible_regex(word: str) -> str:
    return ''.join(_DIACRITIC_MAP.get(c.lower(), re.escape(c)) for c in word)


def _iter_search_tokens(query: str):
    seen: set[str] = set()

    for chunk in re.findall(r'\d+|\D+', query.lower()):
        if chunk.isdigit():
            words = [chunk]
        else:
            words = re.findall(r'\w+', chunk)

        for word in words:
            if not word:
                continue
            if not word.isdigit() and len(word) < MIN_TEXT_SEARCH_TOKEN_LENGTH:
                continue
            if word in seen:
                continue

            seen.add(word)
            yield word

            if len(seen) >= MAX_SEARCH_TOKENS:
                return


def build_search_query_from_string(query: str, search_fields: list[str] = None) -> dict:
    normalized_fields = [field for field in (search_fields or []) if field]
    words = list(_iter_search_tokens(query))

    if not words:
        return {}
    if not normalized_fields:
        return MATCH_NOTHING_QUERY

    word_conditions = []
    for word in words:
        word_condition = {"$or": [
            {key: {"$regex": _create_flexible_regex(word), "$options": "iu"}}
            for key in normalized_fields
        ]}
        word_conditions.append(word_condition)

    mongo_query = {"$and": word_conditions} if word_conditions else {}
    return mongo_query
