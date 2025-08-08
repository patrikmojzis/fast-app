import re


def build_search_query_from_string(query: str, search_fields: list[str] = None) -> dict:
    # Preprocess the query string
    # Use regex to split alphanumeric strings into words and numbers
    words = re.findall(r'\d+|\D+', query.lower())

    # Further process each word
    processed_words = []
    for word in words:
        # Split non-numeric words by non-word characters
        if not word.isdigit():
            processed_words.extend(re.findall(r'\w+', word))
        else:
            processed_words.append(word)

    def create_flexible_regex(word):
        diacritic_map = {
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
        return ''.join(diacritic_map.get(c.lower(), re.escape(c)) for c in word)

    # Create a list of conditions for each word
    word_conditions = []
    for word in processed_words:
        word_condition = {"$or": [
            {key: {"$regex": f".*{create_flexible_regex(word)}.*", "$options": "iu"}}
            for key in search_fields
        ]}
        word_conditions.append(word_condition)

    # Combine all word conditions with $and
    mongo_query = {"$and": word_conditions} if word_conditions else {}
    return mongo_query