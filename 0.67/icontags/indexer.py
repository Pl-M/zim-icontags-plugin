# -*- coding: utf-8 -*-

# Copyright 2016-2017 Pavel_M <plprgt@gmail.com>,
# released under the GNU GPL version 3.
# This is a plugin for Zim-wiki program (zim-wiki.org) by Jaap Karssenberg.

import logging

from zim.tokenparser import skip_to_end_token, TEXT
from zim.formats import STRONG
from zim.notebook.index.base import IndexerBase
from zim.notebook.index.pages import PagesViewInternal

from .iconutils import SEVERAL_ICONS, ICON_RE



logger = logging.getLogger('zim.plugins.icontags')

# Table contains page.name and icon;
# icon is a string with icon name, if no icon to show then row is deleted.
# There is only one icon for page.name (page.name should be unique).
# If parser returns several values than icon's value is 'SEVERAL_ICONS')

class IconsIndexer(IndexerBase):
    '''
    This class works with database to index shortcodes for icons.
    It keeps track of all icon shortcodes in the text.
    '''
    PLUGIN_NAME = "icontags"
    PLUGIN_DB_FORMAT = "0.8"
    INIT_SCRIPT = '''
        CREATE TABLE IF NOT EXISTS iconlist (
        id TEXT PRIMARY KEY,
        icon TEXT
        );
        INSERT OR REPLACE INTO zim_index VALUES (%r, %r);
        ''' % (PLUGIN_NAME, PLUGIN_DB_FORMAT)

    TEARDOWN_SCRIPT = '''
        DROP TABLE IF EXISTS "iconlist";
        DELETE FROM zim_index WHERE key = %r;
        ''' % PLUGIN_NAME

    # define signals we want to use - (closure type, return type and arg types)
    __signals__ = {'iconlist-changed': (None, None, (object,))}

    @classmethod
    def new_from_index(cls, index):
        db = index._db
        pagesindexer = index.update_iter.pages
        return cls(db, pagesindexer)

    def __init__(self, db, pagesindexer):
        IndexerBase.__init__(self, db)

        self.db.executescript(self.INIT_SCRIPT)

        self.connectto_all(pagesindexer, (
            ('page-changed', 'page-row-deleted')))


    def on_page_changed(self, o, row, doc):
        # parse page

        new_icon = self._extract_icons(doc.iter_tokens())
        if not new_icon:
            self._ind_remove(row['name'])
        else:
            self._ind_insert(row['name'], new_icon)

    def on_page_row_deleted(self, o, row):
        _ind_remove(self, row['name'])

    def _ind_insert(self, pagename, icon):
        '''Insert (update) new icon to the index.'''
        try:
            cursor = self.db.cursor()
            cursor.execute(
                '''
                INSERT OR REPLACE INTO iconlist (id, icon)
                VALUES (?, ?)''', (pagename, icon) )
            self.emit('iconlist-changed', pagename)
        except:
            logger.exception('ERROR while inserting, pagename:%s, icon:%s', pagename, icon)

    def _ind_remove(self, pagename):
        cursor = self.db.cursor()
        count, = cursor.execute(
            'SELECT count(*) FROM iconlist WHERE id = ?',
            (pagename,)
        ).fetchone()
        if count > 0:
            cursor.execute(
                'DELETE FROM iconlist WHERE id = ?',
                (pagename,)
            )
            self.emit('iconlist-changed', pagename)

    def _extract_icons(self, tokens):
        '''
        Search for icons in the text.
        Use 'STRONG' tag.
        '''
        def find_text(iter):
            next = iter.next()
            text = ""
            if next[0] == TEXT:
                text = next[1]
            skip_to_end_token(token_iter, STRONG)
            return text

        new_icon = False
        token_iter = iter(tokens)

        for el in token_iter:
            if el[0] != STRONG:
                continue
            text = find_text(token_iter)

            search = ICON_RE.findall(text)
            if search:
                if new_icon or len(search) > 1:
                    new_icon = SEVERAL_ICONS
                    break
                new_icon = search[0].lower()
        return new_icon

from zim.notebook.index.base import IndexView



class IconsView(IndexView):
    '''Database "view" that helps to work with indexed icons'''

    def __init__(self, db):
        IndexView.__init__(self, db)
        self._pages = PagesViewInternal(db)

        # Test the db really has an iconlist
        try:
            db.execute('SELECT * FROM iconlist LIMIT 1')
        except sqlite3.OperationalError:
            raise ValueError, 'No iconlist in index'

    def get_icon(self, pagename):
        '''
		Returns an icon for a given pagename.
		'''
        cursor = self.db.cursor()
        cursor.execute('SELECT icon FROM iconlist WHERE id = ?', (pagename,))
        result = cursor.fetchone()
        if result:
            result = result[0]

        return result

