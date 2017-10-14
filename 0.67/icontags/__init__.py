# -*- coding: utf-8 -*-

# Copyright 2016-2017 Pavel_M <plprgt@gmail.com>,
# released under the GNU GPL version 3.
# This is a plugin for Zim-wiki program (zim-wiki.org) by Jaap Karssenberg.


import logging

from zim.plugins import PluginClass, extends, WindowExtension, ObjectExtension
from zim.actions import action
from zim.gui.widgets import LEFT_PANE, PANE_POSITIONS

from .panelview import IconTagsPluginWidget
from .iconutils import SEVERAL_ICONS, ICON_RE
from .indexer import IconsIndexer



logger = logging.getLogger('zim.plugins.icontags')

TAGSMANAGER_KEY ='<alt>2'


class IconTagsPlugin(PluginClass):

    plugin_info = {
  'name': _('IconTags'), # T: plugin name
  'description': _(
        'This plugin provides a new Index like panel with icons, tagnames and '
        'some other features.\n'
        'A new Tagsmanager dialog is present to simplify some basic operations '
        'with tags.\n' ), # T: plugin description
  'author': 'Pavel_M',
  'help': 'Plugins:IconTags',}

    plugin_preferences = (
  # key, type, label, default
  ('pane', 'choice', _('Position in the window'), LEFT_PANE, PANE_POSITIONS),
  # T: option for plugin preferences
  ('show_lines', 'bool', _('Show lines in tree'), False), # T: preferences option
  ('enable_indexing', 'bool', _('Enable icon shortcodes'), False), # T: preferences option
  )


@extends('Notebook')
class NotebookExtension(ObjectExtension):

    def __init__(self, plugin, notebook):
        ObjectExtension.__init__(self, plugin, notebook)
        self.notebook = notebook
        self.plugin = plugin


@extends('MainWindow')
class MainWindowExtension(WindowExtension):

    uimanager_xml = '''
    <ui>
        <menubar name='menubar'>
            <menu action='tools_menu'>
                <placeholder name='plugin_items'>
                    <menuitem action='show_tagsmanager'/>
                </placeholder>
            </menu>
            <menu action='insert_menu'>
                <placeholder name='plugin_items'>
                    <menuitem action='insert_icon'/>
                </placeholder>
            </menu>
        </menubar>
    </ui>'''

    def __init__(self, plugin, window):
        WindowExtension.__init__(self, plugin, window)

        self.index = self.window.ui.notebook.index # XXX

        self.indexer = None
        self._indexing_enabled = plugin.preferences['enable_indexing']

        if self._indexing_enabled:
            if self.index.get_property(IconsIndexer.PLUGIN_NAME) != IconsIndexer.PLUGIN_DB_FORMAT:
                self._destroy_indexer()
                self._initialize_indexer(True)
            else:
                self._initialize_indexer(False)

        self.widget = None
        self.on_preferences_changed(plugin.preferences)
        self.connectto(plugin.preferences, 'changed', self.on_preferences_changed)


    def on_preferences_changed(self, preferences):
        if self.widget:
            self.window.remove(self.widget)

        self.widget = IconTagsPluginWidget(self.window.ui.notebook.index,
                                           self.window.ui, self.uistate)

        if preferences['enable_indexing'] != self._indexing_enabled:
            self._indexing_enabled = preferences['enable_indexing']
            if self._indexing_enabled:
                self._initialize_indexer(True)
            else:
                self._destroy_indexer()
        self.widget.setIndexer(preferences['enable_indexing'])

        self.window.add_tab(_('icIndex'), self.widget, preferences['pane'])
        self.widget.show_lines(preferences['show_lines'])

        self.widget.show_all()

    def on_iconlist_changed(self, o, pagename):
        self.widget.update_page(pagename)

    def _initialize_indexer(self, reindex):
        if self.indexer:
            self.indexer.disconnect_all()
        self.indexer = IconsIndexer.new_from_index(self.index)
        self.connectto(self.indexer, 'iconlist-changed', self.on_iconlist_changed)
        if reindex:
            self.index.flag_reindex()

    def _destroy_indexer(self):
        # Delete table and disable indexing.
        if self.indexer:
            self.indexer.disconnect_all()
        self.index._db.executescript(IconsIndexer.TEARDOWN_SCRIPT) # XXX
        self.index.set_property(IconsIndexer.PLUGIN_NAME, None)
        self.indexer = None
        self.index.flag_reindex()

    def teardown(self):
        if self.widget:
            self.window.remove(self.widget)
            self.widget = None

        if self.indexer:
            self.indexer.disconnect_all()
            self.indexer = None

    @action(_('Tags Manager'), accelerator = TAGSMANAGER_KEY)
    def show_tagsmanager(self):
        '''Show Tags Manager dialog.'''
        if self.widget:
            self.widget.show_tagsmanager(self.window)

    @action(_('Insert Icon'))
    def insert_icon(self):
        '''
        Create widget to choose icon and insert icon shortcode
        to the cursor position.
        '''
        if self.widget:
            self.widget.insert_icon(self.window.pageview)


