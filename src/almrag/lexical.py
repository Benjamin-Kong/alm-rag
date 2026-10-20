"""SRS-018/019: scoped FTS5 BM25 over versioned synthetic-safe tokens.

Every token is hex encoded before FTS storage/query so unicode61 cannot split
punctuated identifiers or interpret query grammar. No source body is modified.
"""
import re
import unicodedata

LEXICAL_VERSION = 'nfkc-casefold-hangul23-identifier-hex-idmeta-v2'
MAX_QUERY_TERMS = 1024
MAX_QUERY_CHARACTERS = 65536
_WORD = re.compile(r'[^\W_]+(?:[./:+_-][^\W_]+)*', re.UNICODE)
_HANGUL = re.compile(r'[가-힣]+')
_COMPONENT = re.compile(r'[^\W_]+', re.UNICODE)
_KEYS = ('project_uid', 'generation_uid', 'item_uid', 'revision_uid', 'chunk_uid')


class LexicalError(ValueError):
    """Explicit invalid lexical request; no truncated partial search is returned."""
    def __init__(self, message, code='LEXICAL_INVALID_REQUEST'):
        super().__init__(message)
        self.code = code
        self.global_error = False


def terms(text):
    """Return distinct ordered exact identifiers, components and Hangul 2/3-grams."""
    if not isinstance(text, str):
        raise LexicalError('Text must be a string')
    normalized = unicodedata.normalize('NFKC', text).casefold()
    result = dict()
    for match in _WORD.finditer(normalized):
        word = match.group()
        result[word] = None
        for component in _COMPONENT.findall(word):
            result[component] = None
        for hangul in _HANGUL.findall(word):
            result[hangul] = None
            for size in (2, 3):
                for start in range(len(hangul) - size + 1):
                    result[hangul[start:start + size]] = None
    return list(result)


def _encoded(tokens):
    return ['t' + token.encode('utf-8').hex() for token in tokens]


def _transaction(c):
    if not c.in_transaction:
        raise LexicalError('A caller-owned transaction is required', 'LEXICAL_TRANSACTION_REQUIRED')


class LexicalIndex:
    def __init__(self, db):
        self.db = db

    def put(self, c, point):
        _transaction(c)
        try:
            point_id = point['id']
            payload = point['payload']
            values = [payload[key] for key in _KEYS]
            text = point['input_text']
        except (KeyError, TypeError):
            raise LexicalError('Point identity and text are required') from None
        if not isinstance(point_id, str) or not point_id or any(not isinstance(v, str) or not v for v in values):
            raise LexicalError('Point identity must contain nonempty strings')
        owner=c.execute('SELECT source_item_id FROM items WHERE item_uid=? AND project_uid=?',(values[2],values[0])).fetchone()
        if owner is None:raise LexicalError('Item owner missing','LEXICAL_ITEM_MISSING')
        document_terms = ' '.join(_encoded(terms(text+' '+values[2]+' '+owner[0])))
        # SAVEPOINT makes a failed statement atomic even if the caller catches
        # the exception and continues its enclosing publication transaction.
        c.execute('SAVEPOINT lexical_put')
        try:
            c.execute('DELETE FROM keyword_fts WHERE point_uuid=?', (point_id,))
            c.execute('DELETE FROM keyword_documents WHERE point_uuid=?', (point_id,))
            c.execute('INSERT INTO keyword_documents VALUES(?,?,?,?,?,?,?)', (point_id, *values, document_terms))
            c.execute('INSERT INTO keyword_fts(point_uuid,project_uid,generation_uid,terms) VALUES(?,?,?,?)', (point_id, values[0], values[1], document_terms))
            c.execute('RELEASE lexical_put')
        except BaseException:
            c.execute('ROLLBACK TO lexical_put')
            c.execute('RELEASE lexical_put')
            raise

    def search(self, project_uid, generation_uid, query, limit, offset=0, *, c=None, item_uids=None):
        if type(limit) is not int or not 1 <= limit <= 1000 or type(offset) is not int or not 0 <= offset <= 1000000:
            raise LexicalError('Invalid page bounds')
        if not isinstance(query, str) or len(query) > MAX_QUERY_CHARACTERS:
            raise LexicalError('Query is too large', 'LEXICAL_QUERY_TOO_COMPLEX')
        if item_uids is not None:
            if not isinstance(item_uids,list) or len(item_uids)>10000 or any(not isinstance(x,str) or not x or len(x)>1024 for x in item_uids):
                raise LexicalError('Invalid Item filter')
            if not item_uids:return []
        tokens = terms(query)
        if len(tokens) > MAX_QUERY_TERMS:
            raise LexicalError('Query has too many terms', 'LEXICAL_QUERY_TOO_COMPLEX')
        if not tokens:
            return []
        expression = ' OR '.join('"' + token + '"' for token in _encoded(tokens))
        if c is None:
            with self.db.connect() as connection:
                return self._search(connection, project_uid, generation_uid, expression, limit, offset, item_uids)
        return self._search(c, project_uid, generation_uid, expression, limit, offset, item_uids)

    @staticmethod
    def _search(c, project_uid, generation_uid, expression, limit, offset, item_uids):
        predicate='' if item_uids is None else ' AND d.item_uid IN (SELECT value FROM json_each(?))'
        parameters=[] if item_uids is None else [__import__('json').dumps(item_uids)]
        rows = c.execute('''SELECT d.point_uuid,d.project_uid,d.generation_uid,d.item_uid,d.revision_uid,d.chunk_uid,
                                   bm25(keyword_fts) AS relevance
                            FROM keyword_fts JOIN keyword_documents d ON d.point_uuid=keyword_fts.point_uuid
                            WHERE keyword_fts MATCH ? AND d.project_uid=? AND d.generation_uid=?
                                  AND keyword_fts.project_uid=? AND keyword_fts.generation_uid=?
                            '''+predicate+' ORDER BY relevance ASC,d.point_uuid ASC LIMIT ? OFFSET ?',
                         (expression, project_uid, generation_uid, project_uid, generation_uid, *parameters, limit, offset)).fetchall()
        return [{'id': row['point_uuid'], 'score': -float(row['relevance']),
                 'payload': {key: row[key] for key in _KEYS}} for row in rows]

    def delete_generation(self, c, generation_uid):
        _transaction(c)
        c.execute('SAVEPOINT lexical_delete')
        try:
            c.execute('DELETE FROM keyword_fts WHERE generation_uid=?', (generation_uid,))
            c.execute('DELETE FROM keyword_documents WHERE generation_uid=?', (generation_uid,))
            c.execute('RELEASE lexical_delete')
        except BaseException:
            c.execute('ROLLBACK TO lexical_delete')
            c.execute('RELEASE lexical_delete')
            raise
