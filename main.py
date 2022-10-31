import sqlite3
import requests
import re
import os
import enum
from html.parser import HTMLParser

BASE_URL = 'http://www.skarnik.by/'
DATABASE_FILE = 'vocabulary.db'

class VocabularyType(enum.Enum):
    rus_bel = 1
    bel_rus = 2
    bel_def = 3

class SkarnikHTMLParser(HTMLParser):
    rus_bel_alphabet_urls: [str] = []
    bel_rus_alphabet_urls: [str] = []
    bel_definition_alphabet_urls: [str] = []

    base_url: str

    def __init__(self, base_url: str):
        HTMLParser.__init__(self)
        self.base_url = base_url
        self.rus_bel_alphabet_urls = []
        self.bel_rus_alphabet_urls = []
        self.bel_definition_alphabet_urls = []

    def handle_starttag(self, tag, attrs):
        if tag is not None and tag == 'a' and attrs is not None:
            attrs_dict = dict(map(lambda x: (x[0], x[1]), attrs))
            if 'href' in attrs_dict:
                href: str = attrs_dict['href']
                if href.startswith(self.base_url + 'litara-tsbm/'):
                    self.bel_definition_alphabet_urls.append(href)
                elif href.startswith(self.base_url + 'litara/'):
                    self.bel_rus_alphabet_urls.append(href)
                elif href.startswith(self.base_url + 'bukva/'):
                    self.rus_bel_alphabet_urls.append(href)


class SkarnikLetterHTMLParser(HTMLParser):
    words: {str: int} = {}

    current_href = ""
    current_word_id: int = None

    def __init__(self):
        HTMLParser.__init__(self)
        self.current_href = ""
        self.current_word_id = None
        self.words = {}

    def a_href(self, attrs) -> str:
        href: str = ""
        if attrs is None:
            return href
        attrs_dict = dict(map(lambda x: (x[0], x[1]), attrs))
        if 'href' in attrs_dict:
            href: str = attrs_dict['href']
        return href

    def a_href_word_id(self, attrs) -> int:
        href: str = self.a_href(attrs=attrs)
        word_id = None
        if href is None:
            return word_id
        match = re.search(r'/([0-9]+)$', href)
        if match is None:
            return word_id
        word_id = match.group(1)
        if word_id is None:
            return word_id
        return int(word_id)

    def handle_starttag(self, tag, attrs):
        if tag is not None and tag == 'a':
            self.current_href = self.a_href(attrs=attrs)
            self.current_word_id = self.a_href_word_id(attrs=attrs)

    def handle_endtag(self, tag):
        if tag is not None and tag == 'a':
            self.current_href = ""
            self.current_word_id = None

    def handle_data(self, data):
        if data is None or self.current_word_id is None:
            return
        word = data.strip()
        if len(word) == 0:
            return
        self.words[word] = self.current_word_id
        self.current_word_id = None
        self.current_href = ""


def download_words(urls: list) -> {str: int}:
    words: {str: int} = {}
    for letter_url in urls:
        print(f'[VERBOSE] Download: {letter_url}')
        skarnik_letter_request = requests.get(url=letter_url)
        if skarnik_letter_request.status_code != 200:
            print(f'Error: {letter_url} response code {skarnik_letter_request.status_code}.')
            return None
        skarnik_letter_content = skarnik_letter_request.content.decode('utf8')
        skarnik_letter_html = SkarnikLetterHTMLParser()
        skarnik_letter_html.words = {}
        skarnik_letter_html.feed(skarnik_letter_content)
        words = words | skarnik_letter_html.words  # merge dicts

    return words


def create_database(filename: str):
    print(f'[VERBOSE] Recreate database: {filename}')
    if os.path.exists(filename):
        os.remove(filename)

    con = sqlite3.connect(DATABASE_FILE)
    cur = con.cursor()
    database_create_queries = [
        r'CREATE TABLE vocabulary(id INTEGER PRIMARY KEY, word_id INTEGER, word TEXT, lword TEXT, lang_id INTEGER, first_char VARCHAR(1), word_mask TEXT);',
        r'CREATE UNIQUE INDEX wordid_langid_unique ON vocabulary (word_id, lang_id);',
        r'CREATE INDEX firstchar_lang_index ON vocabulary (first_char, lang_id);',
        r'CREATE INDEX lword_lang_index ON vocabulary (lword, lang_id);',
        r'CREATE INDEX wordmask_firstchar_lang_index ON vocabulary (word_mask, first_char, lang_id);',
        r'CREATE INDEX lword_firstchar_lang_index ON vocabulary (lword, first_char, lang_id);',
        r'CREATE INDEX wordmask_index ON vocabulary (word_mask);',
        r'CREATE INDEX lword_index ON vocabulary (lword);']

    for query in database_create_queries:
        cur.execute(query)
        con.commit()

    return con, cur


def parse_skarnik(base_url: str, db_con: sqlite3.Connection, db_cur: sqlite3.Cursor):
    skarnik_request = requests.get(url=base_url)
    if skarnik_request.status_code != 200:
        print(f'Error: {base_url} response code {skarnik_request.status_code}.')
        return

    skarnik_content = skarnik_request.content.decode('utf8')
    skarnik_html = SkarnikHTMLParser(base_url=base_url)
    skarnik_html.feed(skarnik_content)

    rusbel_words = download_words(skarnik_html.rus_bel_alphabet_urls)
    if rusbel_words is None:
        print(f'Error: rus_bel vocabulary download problem.')
        return
    belrus_words = download_words(skarnik_html.bel_rus_alphabet_urls)
    if belrus_words is None:
        print(f'Error: bel_rus vocabulary download problem.')
        return
    beldef_words = download_words(skarnik_html.bel_definition_alphabet_urls)
    if beldef_words is None:
        print(f'Error: bel_definition vocabulary download problem.')
        return

    def insert_word(db_cur: sqlite3.Cursor, word: str, word_id: int, vocabulary_type: VocabularyType):
        if word is None or len(word) == 0 or word_id is None or vocabulary_type is None:
            return

        def process_word(pr_word: str):
            pairs = {'и': 'і', 'е': 'ё', 'щ': 'ў', 'ъ': '‘', '\'': '‘'}
            pr_word = pr_word.lower()
            for key, value in pairs.items():
                pr_word = pr_word.replace(key, value)
            return pr_word

        word_mask = process_word(word)
        first_char = word[0].lower()
        lang_id = vocabulary_type.value
        lword = word.lower()
        data = (word, word_id, lword, word_mask, lang_id, first_char)
        db_cur.execute('INSERT OR IGNORE INTO vocabulary (word, word_id, lword, word_mask, lang_id, first_char) VALUES (?, ?, ?, ?, ?, ?);', data)

    print(f'[VERBOSE] Adding words into database...')
    db_cur.execute('BEGIN TRANSACTION')
    for word, word_id in rusbel_words.items():
        insert_word(db_cur=db_cur, word=word, word_id=word_id, vocabulary_type=VocabularyType.rus_bel)
    for word, word_id in belrus_words.items():
        insert_word(db_cur=db_cur, word=word, word_id=word_id, vocabulary_type=VocabularyType.bel_rus)
    for word, word_id in beldef_words.items():
        insert_word(db_cur=db_cur, word=word, word_id=word_id, vocabulary_type=VocabularyType.bel_def)
    db_cur.execute('COMMIT')
    db_con.commit()

db_con, db_cur = create_database(filename=DATABASE_FILE)
parse_skarnik(base_url=BASE_URL, db_con=db_con, db_cur=db_cur)
db_con.close()
print(f'[VERBOSE] Success')

#
# def generate_database_index():
#     con = sqlite3.connect("vocabulary.db")
#     cur = con.cursor()
#
#     pairs = {'и': 'і', 'е': 'ё', 'щ': 'ў', 'ъ': '‘', '\'': '‘'}
#
#     def process_word(word: str):
#         word = word.lower()
#         for key, value in pairs.items():
#             word = word.replace(key, value)
#         return word
#
#     first_letters = {}
#     words = {}
#     try:
#         cur.execute("ALTER TABLE vocabulary ADD first_char VARCHAR(1);")
#         con.commit()
#     except:
#         pass
#
#     try:
#         cur.execute("ALTER TABLE vocabulary ADD word_mask TEXT;")
#         con.commit()
#     except:
#         pass
#
#     for row in cur.execute("SELECT id, word FROM vocabulary"):
#         word_id = row[0]
#         initial_word: str = row[1]
#         processed_word = initial_word[0]
#         first_letters[word_id] = processed_word.lower()
#     cur.execute('BEGIN TRANSACTION')
#     for word_id, letter in first_letters.items():
#         data = (letter, word_id)
#         cur.execute('UPDATE vocabulary SET first_char = ? WHERE id = ?', data)
#     cur.execute('COMMIT')
#     con.commit()
#     print(f'first_letters: {len(first_letters)}')
#
#     for row in cur.execute("SELECT id, word FROM vocabulary"):
#         word_id = row[0]
#         initial_word: str = row[1]
#         processed_word = process_word(initial_word)
#         words[word_id] = processed_word
#
#     cur.execute('BEGIN TRANSACTION')
#     for word_id, lword in words.items():
#         data = (lword, word_id)
#         cur.execute('UPDATE vocabulary SET word_mask = ? WHERE id = ?', data)
#     cur.execute('COMMIT')
#     con.commit()
#     print(f'words: {len(words)}')
#
#     try:
#         cur.execute("CREATE INDEX firstchar_lang_index ON vocabulary (first_char, lang_id)")
#         cur.execute("CREATE INDEX wordmask_firstchar_lang_index ON vocabulary (word_mask, first_char, lang_id)")
#         cur.execute("CREATE INDEX wordmask_index ON vocabulary (word_mask)")
#         # cur.execute("CREATE INDEX wordmask_lword_index  ON vocabulary (word_mask, lword)")
#         con.commit()
#     except:
#         pass
#
#     con.close()
