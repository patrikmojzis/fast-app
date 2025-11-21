import re

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


def _iter_processed_words(words: list[str]):
    for word in words:
        if word.isdigit():
            yield word
        else:
            yield from re.findall(r'\w+', word)


def build_search_query_from_string(query: str, search_fields: list[str] = None) -> dict:
    # Preprocess the query string
    # Use regex to split alphanumeric strings into words and numbers
    words = re.findall(r'\d+|\D+', query.lower())

    # Create a list of conditions for each word
    word_conditions = []
    for word in _iter_processed_words(words):
        word_condition = {"$or": [
            {key: {"$regex": f".*{_create_flexible_regex(word)}.*", "$options": "iu"}}
            for key in search_fields
        ]}
        word_conditions.append(word_condition)

    # Combine all word conditions with $and
    mongo_query = {"$and": word_conditions} if word_conditions else {}
    return mongo_query
