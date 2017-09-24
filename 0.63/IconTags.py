# -*- coding: utf-8 -*-

# Copyright 2016 Pavel_M <plprgt@gmail.com>,
# released under the GNU GPL version 3.
# This is a plugin for Zim program by Jaap Karssenberg <jaap.karssenberg@gmail.com>.

import gobject
import gtk
import pango
import re
import logging
import os

from zim.plugins import PluginClass, extends, WindowExtension, ObjectExtension
from zim.actions import action
from zim.gui.pageindex import PageTreeStore, PageTreeView, \
    NAME_COL, TIP_COL, PATH_COL, EMPTY_COL, STYLE_COL, \
    FGCOLOR_COL, WEIGHT_COL, N_CHILD_COL
from zim.notebook import Path
from zim.gui.widgets import LEFT_PANE, PANE_POSITIONS, \
    encode_markup_text, ui_environment, \
    ScrolledWindow, BrowserTreeView, Dialog, SingleClickTreeView, MessageDialog
from zim.signals import ConnectorMixin, SIGNAL_AFTER
from zim.gui.clipboard import INTERNAL_PAGELIST_TARGET
from zim.formats import STRONG
from zim.config import data_dir


logger = logging.getLogger('zim.plugins.icontags')

def _load_icons():
    '''
    Load icons for the plugin from 'ICONS_DIRECTORY' folder (files with png format).
    Icons are stored as dict: {'name': 'icon'}, where icon is a name of the icon in the factory (or gtk).
    For example an icon with name 'name' will have an icon file 'name.png'
    in this folder or a 'NO_IMAGE' icon if it is not available.
    '''
    # Use IconFactory to get the same size for all icons.
    factory = gtk.IconFactory()
    factory.add_default()
    icons = {
        NO_IMAGE: gtk.STOCK_MISSING_IMAGE, # icon has no image
        SEVERAL_ICONS: gtk.STOCK_DIALOG_QUESTION, # not clear what icon to use
        # Icons below can be overwritten if there is a certain file in the 'ICONS_DIRECTORY'.
        'apply': gtk.STOCK_APPLY, # additional GTK icon
        #'info': gtk.STOCK_INFO, # additional GTK icon
        FOLDER_ICON: gtk.STOCK_DIRECTORY, # for pages with children    
        FOLDER_TAGS_ICON: gtk.STOCK_DIRECTORY, # for pages with children and with tags    
        FILE_ICON: gtk.STOCK_FILE, # for ordinary pages
        FILE_TAGS_ICON: gtk.STOCK_FILE # for ordinary pages with tags    
        }

    # Icons from directory.
    dir = data_dir(ICONS_DIRECTORY)
    counter = 0 # to count number of loaded icons
    if dir:
        for file in dir.list('*.png'):
            # not all installs have svg support, so only check png for now..
            name = file[:-4].lower() # e.g. 'calendar.png' -> 'calendar'
            icon_name = 'p_Icon_' + name # e.g. 'Calendar' -> 'p_Icon_calendar'            
            try:
                pixbuf = gtk.gdk.pixbuf_new_from_file(str(dir+file))
                icon = gtk.IconSet(pixbuf)
                factory.add(icon_name, icon)
                icons[name] = icon_name
                counter += 1
            except:
                logger.error('IconTags: Error while loading icons.')
        logger.debug('IconTags: {} icons loaded from: {}'.format(counter, dir.path))
    else:
        logger.debug('''IconTags: Folder with icons doesn't exist.''')
                
    return icons

class Render_Icon():
    '''
    This class is used to render icons and to cache them.
    '''
    def __init__(self):
        self.cache = {}
        self.size = gtk.ICON_SIZE_LARGE_TOOLBAR

    def __call__(self, icon):
        try:
            return self.cache[icon]
        except KeyError: # element not in cache
            result = gtk.Label().render_icon(icon, self.size)
            self.cache[icon] = result
            return result

render_icon = Render_Icon()
# It is used like this: "render_icon(ICONS['tags'])" to return rendered image.

# Table contains page.id and icon;
# icon is a string with icon name, if no icon to show then row is deleted.
# There is only one icon for page.id (if parser returns several
# values than icon's value is 'SEVERAL_ICONS')
SQL_FORMAT_VERSION = (0, 6)
SQL_FORMAT_VERSION_STRING = "0.6"

SQL_CREATE_TABLE = '''
create table if not exists iconlist (
id INTEGER PRIMARY KEY,
icon TEXT
);
'''

ICON_COL = 8 #: Column with icons
# Directory where additional icons are.
ICONS_DIRECTORY = os.path.join('pixmaps', 'Tags_Icons')

# Special names for icons.
NO_IMAGE = 'Error: icon has no image.'
SEVERAL_ICONS = 'Error: not clear what icon to choose.'
FOLDER_ICON = '_default_folder'
FOLDER_TAGS_ICON = FOLDER_ICON + '_tags'
FILE_ICON = '_default_file'
FILE_TAGS_ICON = FILE_ICON + '_tags'

# List of all special names for icons.
# Need this to filter them from other icons.
RESERVED_ICON_NAMES = set([NO_IMAGE, SEVERAL_ICONS, FOLDER_ICON,
                           FOLDER_TAGS_ICON, FILE_ICON, FILE_TAGS_ICON])

ICONS = _load_icons() # init and load all icons

# Icons are written in notebook as text (like "[ICON=calendar]") in bold font
# (framed by STRONG_MARKUP).
# Bold is used to look for icons amidst all elements in bold.
STRONG_MARKUP = '**'
PREFIX, POSTFIX = '[ICON=', ']'
ICON_RE = re.compile(r'(?<=\{}).*?(?={})'.format(PREFIX, POSTFIX), re.U)

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

    def extend(self, obj):
        name = obj.__class__.__name__
        if name == 'MainWindow':
            index = obj.ui.notebook.index # XXX
            i_ext = self.get_extension(IconsIndexExtension, index = index)
            mw_ext = MainWindowExtension(self, obj, i_ext)
            self.extensions.add(mw_ext)
        else:
            PluginClass.extend(self, obj)


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

    def __init__(self, plugin, window, index_ext):
        WindowExtension.__init__(self, plugin, window)
        self.index_ext = index_ext # index of icons in pages

        self.widget = IconTagsPluginWidget(self.window.ui.notebook.index, self.index_ext,
                                           self.window.ui, self.uistate) # XXX
        self.on_preferences_changed(plugin.preferences)
        self.connectto(plugin.preferences, 'changed', self.on_preferences_changed)

    def on_preferences_changed(self, preferences):
        if self.widget is None:
            return

        try:
            self.window.remove(self.widget)
        except ValueError:
            pass
        self.window.add_tab(_('icIndex'), self.widget, preferences['pane'])
        self.widget.show_lines(preferences['show_lines'])

        # Start after a while to give time to close previous window.
        gobject.timeout_add(100, lambda *a: self._init_index_ext(preferences))

        self.widget.show_all()

    def _init_index_ext(self, preferences):
        if preferences['enable_indexing']:
            # Initialize extended index database.
            if not self.initialize_db():
                preferences['enable_indexing'] = False
        else:
            # Delete table and disable indexing.
            self.index_ext.teardown()
            # Clear icons from treeview.
            self.widget.reload_model()

    def teardown(self):
        try:
            self.window.remove(self.widget)
        except ValueError:
            pass
        self.widget.disconnect_all()
        self.widget = None

    @action(_('Tags Manager'), accelerator = TAGSMANAGER_KEY)
    def show_tagsmanager(self):
        '''Show Tags Manager dialog.'''
        self.widget.show_tagsmanager(self.window)

    @action(_('Insert Icon'))
    def insert_icon(self):
        '''
        Create widget to choose icon and insert icon shortcode 
        to the cursor position.
        '''
        self.widget.insert_icon(self.window.pageview)

    def initialize_db(self):
        if not self.index_ext.db_initialized:
            self.index_ext.connect_signals() # enable signals to update
            header_message = _('IconTags: Need to index the notebook')
            text_message = _(
                'Icon shortcodes are enabled.\n'
                'To find them the index needs to be rebuild.\n'
                'It can take up some time. You can stop it \n' 
                'by pressing cancel in the updating window.')
            MessageDialog(self.window, (header_message, text_message)).run()
            logger.info('Database for Icons is not initialized, need to rebuild the index.')

            finished = self.window.ui.reload_index(flush=True) # XXX
            # Flush + Reload will also initialize iconlist
            if not finished:
                self.index_ext.db_initialized = False
                return False
        return True



@extends('Index')
class IconsIndexExtension(ObjectExtension):
    '''
    This class works with database to index shortcodes for icons.
    It keeps track of all icon shortcodes in the text.
    '''
    # define signals we want to use - (closure type, return type and arg types)
    __signals__ = {'icon-changed': (None, None, ())}

    def __init__(self, plugin, index):
        ObjectExtension.__init__(self, plugin, index)
        self.plugin = plugin
        self.index = index
        self.cache = {} # to cache self.get() function

        self.db_initialized = False
        db_version = self.index.properties['plugin_iconlist_format']
        if db_version == '%i.%i' % SQL_FORMAT_VERSION:
            self.db_initialized = True
            self.connect_signals()

    def connect_signals(self):
        '''Connect to signals to update Index.'''
        self.connectto_all(self.index, (
            ('initialize-db', self.initialize_db, None, SIGNAL_AFTER),
            ('page-indexed', self.index_page),
            ('page-deleted', lambda a: self._ind_remove(a.id)),
        ))

        # Update cache if icons are changed.
	self.connectto(self, 'iconlist-changed', self._update_cache)

    def initialize_db(self, index):
        '''
        This function should be started to enable indexing.
        It should be started only once unless table was dropped.
        '''
        with index.db_commit:
            index.db.executescript(SQL_CREATE_TABLE)
            logger.info('Iconlist database table is created.')
        self.index.properties['plugin_iconlist_format'] = '%i.%i' % SQL_FORMAT_VERSION
        self.db_initialized = True

    def teardown(self):
        self.disconnect_all()
        self._drop_table()

    def _drop_table(self):
        self.index.properties['plugin_iconlist_format'] = 0
        try:
            self.index.db.execute('DROP TABLE "iconlist"')
        except:
            if self.db_initialized:
                logger.exception('Could not drop "iconlist" table.')

        self.db_initialized = False

    def index_page(self, index, path, page):
        if not self.db_initialized:
            return False

        parsetree = page.get_parsetree()
        if not parsetree:
            return False

        icon_in_index = self.get_icon(path)
        icon = self._extract_icons(parsetree)
        if icon != icon_in_index:
            with self.index.db_commit:
                if not icon:
                    self._ind_remove(path, icon)
                else:
                    self._ind_insert(path, icon)

    def _update_cache(self, o, path):
        self.cache.pop(path, None)

    def _ind_insert(self, path, icon):
        '''Insert (update) new icon to the index.'''
        if not self.db_initialized:
            return False

        with self.index.db_commit:
            try:
                cursor = self.index.db.cursor()
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO iconlist (id, icon)
                    VALUES (?, ?)''', (path.id, icon) )
                self.emit('iconlist-changed', path)
            except:
                logger.exception('ERROR while inserting, path:%s, icon:%s', path, icon)

    def _ind_remove(self, path, _emit=True):
        if not self.db_initialized:
            return False

        with self.index.db_commit:
            cursor = self.index.db.cursor()
            cursor.execute(
                'DELETE FROM iconlist WHERE id = ?', (path.id,) )
            self.emit('iconlist-changed', path)

    def get_icon(self, path):
        '''
        Returns an icon for a given path.
        '''
        if not self.db_initialized:
            return False

        # Look in cache.
        try:
            return self.cache[path]
        except KeyError: # element not in cache
            pass
        if len(self.cache) > 200:
            self.cache = {}

        cursor = self.index.db.cursor()
        cursor.execute('SELECT icon FROM iconlist WHERE id = ?', (path.id,))
        result = cursor.fetchone()
        if result:
            result = result[0]

        self.cache[path] = result
        return self.cache[path]

    def _extract_icons(self, parsetree):
        '''
        Search for icons in the parsetree. 
        Use 'STRONG' tag.
        '''

        new_icon = False
        strings = (a.gettext() for a in parsetree.findall(STRONG))

        for string in strings:
            search = ICON_RE.findall(string)
            if search:
                if new_icon or len(search) > 1:
                    new_icon = SEVERAL_ICONS
                    break
                new_icon = search[0].lower()
        return new_icon


class IconTagsPluginWidget(ConnectorMixin, gtk.ScrolledWindow):
    '''Main Widget.'''

    def __init__(self, index, index_ext, ui, uistate): # XXX
        gtk.ScrolledWindow.__init__(self)
        self.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	self.set_shadow_type(gtk.SHADOW_IN)

        self.ui = ui
        self.treeview = IconsTreeView(ui) # XXX
        self.add(self.treeview)

        self.uistate = uistate
        self.uistate.setdefault('Open pages', 'default') # values 'default, collapse, disable'
        self.treeview.change_view(self.uistate['Open pages'])

        self.uistate.setdefault('show tags', False) # show tags with names
        self.uistate.setdefault('Icons for Tags', {}) # set icons for available tags

        # All available tags in the notebook.
        tags = [a.name for a in index.list_all_tags()]
        # Check that tags and icons are still available.
        self.uistate['Icons for Tags'] = dict(
            [(tag, icon) for (tag, icon) in self.uistate['Icons for Tags'].iteritems()
             if ( (tag in tags) and (icon in ICONS) )] )

        self.index = index
        self.index_ext = index_ext
        self._show_tagged = False # if True - show only pages with tags

	self.connectto(self.treeview, 'populate-popup', self.on_populate_popup)
        self.connectto_all(ui, ( # XXX
            'open-page',
            ('start-index-update', lambda o: self.disconnect_model()),
            ('end-index-update', lambda o: self.reload_model()), ))

        self.reload_model()

    def disconnect_model(self):
        '''
        Stop the model from listening to the index. Used to
        unhook the model before reloading the index. Typically
        should be followed by reload_model().
        '''
        self.treeview.disconnect_index()

    def reload_model(self):
        '''
        Re-initialize the treeview model. This is called when
        reloading the index to get rid of out-of-sync model errors
        without need to close the app first.
        '''
        # Save expanded paths.
        paths = []
        def func(treeview, path):
            paths.append(path)
        self.treeview.map_expanded_rows(func)
        model = self.treeview.get_model()
        if isinstance(model, gtk.TreeModelFilter):
            # Convert to TreeModel format.
            paths = [model.convert_path_to_child_path(a) for a in paths]

        model = IconsTreeStore(self.index, self.index_ext,
                               self.uistate['show tags'], self.uistate['Icons for Tags'])
        self.treeview.set_model(model, self._show_tagged)

        # Expand saved paths.
        model = self.treeview.get_model()
        for path in paths:
            if isinstance(model, gtk.TreeModelFilter):
                # Convert to TreeModelFilter format.                
                path = model.convert_child_path_to_path(path)
            self.treeview.expand_row(path, open_all = False)

    def on_open_page(self, ui, page, path):
        treepath = self.treeview.set_current_page(path, vivificate = True)
        self.treeview.get_selection().unselect_all()

        if treepath:
            if self.treeview.view == 'disable':
                # Only select.
                self.treeview.get_selection().select_path(treepath)
            else:
                # Select and expand.
                self.treeview.select_treepath(treepath) 

    def toggle_show_tagged(self):
        '''Show all pages or only pages with tags.'''
        self._show_tagged = not self._show_tagged
        self.reload_model()

    def toggle_show_tags(self):
        '''Show/hide tags near the pagename.'''
        self.uistate['show tags'] = not self.uistate['show tags']
        self.reload_model()

    def show_lines(self, value):
        '''Show/hide vertical lines.'''
        self.treeview.set_enable_tree_lines(value)

    def on_populate_popup(self, treeview, menu):
        '''Add popup menu options.'''
        menu.prepend(gtk.SeparatorMenuItem())

        # Add menu with view options.
        view_menu = gtk.Menu()
        # Add options to show tags and tagged pages.
        items = ( (_('Show only Pages with Tags'), self._show_tagged,
                   lambda o: self.toggle_show_tagged()),
                  (_('Show Tags'), self.uistate['show tags'],
                   lambda o: self.toggle_show_tags()) )
        for name, active, func in items:
            item = gtk.CheckMenuItem(name)
            item.set_active(active)
            item.connect('activate', func)
            view_menu.append(item)
        view_menu.append(gtk.SeparatorMenuItem())

        # Add options to switch between views.
        def _change_view(item, event):
            self.uistate['Open pages'] = item.zim_view
            self.treeview.change_view(self.uistate['Open pages'])

        items = ( (_('Default'), 'default'),
                  (_('Collapse other Pages'), 'collapse'),
                  (_('Disable'), 'disable') )
        item = None
        for name, view in items:
            item = gtk.RadioMenuItem(group = item, label = name)
            if view == self.uistate['Open pages']:
                item.set_active(True)
            item.zim_view = view
            item.connect('button-release-event', _change_view)
            view_menu.append(item)

        item = gtk.MenuItem('View')
        item.set_submenu(view_menu)
        menu.prepend(item)

        menu.show_all()

    def insert_icon(self, pageview):
        '''Create widget to choose an icon and insert an icon shortcode.'''

        def _insert(item):
            '''Insert an icon shortcode to the cursor position.'''
            buffer = pageview.view.get_buffer()
            text = '{0}{1}{2}{3}{0}'.format(STRONG_MARKUP, PREFIX, item, POSTFIX)
            buffer.insert_at_cursor(text)

        menu = gtk.Menu()
        icons = sorted([(a, render_icon(b)) for (a,b) in ICONS.iteritems()
                        if a not in RESERVED_ICON_NAMES])
        for name, icon in icons:
            image = gtk.Image()
            image.set_from_pixbuf(icon)
            item = gtk.ImageMenuItem(name)
            item.set_image(image)
            item.set_use_underline(False)
            item.connect('button-release-event', lambda item, _:
                         _insert(item.get_label()))
            menu.append(item)
	menu.popup(None, None, None, 3, 0)
        menu.show_all()

    def show_tagsmanager(self, window):
        '''Run TagsManager dialog.'''
        def update(dialog):
            if dialog.result:
                self.reload_model()

	dialog = TagsManagerDialog.unique(self.ui, window, self.index, self.uistate)
        dialog.connect('destroy', update)
        dialog.present()


class IconsTreeStore(PageTreeStore):
    '''
    Model to show tags and icons alongside the pagename.
    This model uses cache for storing page's properties for 'on_get_value' function
    to avoid excessive SQL queries and improve performance.
    Cache is a dict with values for NAME_COL, TIP_COL and ICON_COL for each cached page;
    cache[path.name] = (NAME_COL value, TIP_COL value, ICON_COL value).
    Icons are stored in cache as strings, to render them to images use 'render_icon'.
    The size of cache is limited and it is cleared automatically after some time.
    '''
    COLUMN_TYPES = (
		gobject.TYPE_STRING, # NAME_COL
		gobject.TYPE_PYOBJECT, # PATH_COL
		bool, # EMPTY_COL
		pango.Style, # STYLE_COL
		gobject.TYPE_STRING, # FGCOLOR_COL
		int, # WEIGHT_COL
		gobject.TYPE_STRING, # N_CHILD_COL
		gobject.TYPE_STRING, # TIP_COL
		gobject.TYPE_OBJECT # ICON_COL
    )

    def __init__(self, index, index_ext, show_tags, icons_for_tags):
        self.index_ext = index_ext
        self.icons_for_tags = icons_for_tags
        self.show_tags = show_tags

        # Cache pagenames with tags.
        self._pagenames_cache = {}
        self._clear_cache_scheduled = False

        PageTreeStore.__init__(self, index)

    def on_get_value(self, iter, column):
        '''
        Modify to return new pagenames, tooltips and icons.
        Columns 'NAME_COL', 'TIP_COL' and 'ICON_COL' use cache, 
        other columns works with default methods.
        '''

        path = iter.indexpath
        if (column == NAME_COL) or (column == TIP_COL):
            try:
                return self._pagenames_cache[path.name][column]
            except KeyError:
                pass
        elif column == ICON_COL:
            try:
                return render_icon(self._pagenames_cache[path.name][column])
            except KeyError:
                pass
        else:
            return PageTreeStore.on_get_value(self, iter, column)

        # Value is not in cache.
        # Find tags, icons and put values to cache.
        tags = [a.name for a in self.index.list_tags(path)]
        icon = self.index_ext.get_icon(path)

        if icon:
            icon = ICONS.get(icon, ICONS[NO_IMAGE])
        elif tags:
            # Check icons for tags.
            _icons = [self.icons_for_tags[a] for a in tags
                      if a in self.icons_for_tags]
            if _icons:
                # Check whether all icons are the same.
                if len( set(_icons) ) > 1:
                    icon = ICONS[SEVERAL_ICONS]
                else:
                    icon = ICONS[_icons[0]]
            elif path.haschildren:
                icon = ICONS[FOLDER_TAGS_ICON]
            else:
                icon = ICONS[FILE_TAGS_ICON]
        else:
            if path.haschildren:
                icon = ICONS[FOLDER_ICON]
            else:
                icon = ICONS[FILE_ICON]

        if tags and self.show_tags: # show tags after page name
            name = '{} ({})'.format(path.basename, ', '.join(tags))
        else:
            name = path.basename

        self._pagenames_cache[path.name] = {NAME_COL: name,
                                            TIP_COL: encode_markup_text(name),
                                            ICON_COL: icon}

        # Launch function to clear cache.
        if not self._clear_cache_scheduled:
            self._clear_pagenames_cache()

        return self.on_get_value(iter, column)

    def _clear_pagenames_cache(self):
        if not self._clear_cache_scheduled:
            def _clear():
                '''Clear tags cache.'''
                if len(self._pagenames_cache) > 200:
                    self._pagenames_cache = {}
                self._clear_cache_scheduled = False
        	return False # to not call again

            gobject.timeout_add(500, _clear)
            self._clear_cache_scheduled = True

    def _connect(self):
        PageTreeStore._connect(self)

        def on_tag_changed(o, tag, path, _):
            '''
            If a tag is added to a page or removed from a page
            emit signal to update.
            '''
	    self._flush()
            treepath = self.get_treepath(path)
            treeiter = self.get_iter(treepath)
            self._pagenames_cache.pop(path.name, None)
            self.emit('row-changed', treepath, treeiter)

        def on_iconlist_changed(o, path):
            '''If an icon is changed update cache.'''
            self._flush()
            self._pagenames_cache.pop(path.name, None)


        self.connectto_all(self.index, (
            ('tag-inserted', on_tag_changed),
            ('tag-removed', on_tag_changed)
        ))
	self.connectto(self.index_ext, 'iconlist-changed',
                       on_iconlist_changed)


class IconsTreeView(PageTreeView):
    '''This class output the tree with pages.'''

    def __init__(self, ui, model = None):
        self._PageTreeView_init_(ui)
        self.view = 'default' # set_current_page behaviour
        self.set_name('zim-icontags-pagelist')
        if model:
            self.set_model(model)

    def _PageTreeView_init_(self, ui):
        '''
        This is a slightly modified copy of PageTreeView constructor 
        with one additional column for icons.
        '''
        BrowserTreeView.__init__(self)
        self.set_name('zim-pageindex')
        self.ui = ui
        self._cleanup = None # temporary created path that needs to be removed later

        column = gtk.TreeViewColumn('_pages_')
        self.append_column(column)

        # Added Icon column.
        cr0 = gtk.CellRendererPixbuf()
        column.pack_start(cr0, expand = False)
        column.set_attributes(cr0, pixbuf = ICON_COL)

        cr1 = gtk.CellRendererText()
        cr1.set_property('ellipsize', pango.ELLIPSIZE_END)
        column.pack_start(cr1, True)
        column.set_attributes(cr1, text=NAME_COL,
                              style=STYLE_COL, foreground=FGCOLOR_COL, weight=WEIGHT_COL)

        cr2 = self.get_cell_renderer_number_of_items()
        column.pack_start(cr2, False)
        column.set_attributes(cr2, text=N_CHILD_COL, weight=WEIGHT_COL)

        if gtk.gtk_version >= (2, 12) \
           and gtk.pygtk_version >= (2, 12):
            self.set_tooltip_column(TIP_COL)

        self.set_headers_visible(False)

        self.set_enable_search(True)
        self.set_search_column(0)

        self.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK, (INTERNAL_PAGELIST_TARGET,),
            gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_MOVE )
        self.enable_model_drag_dest(
            (INTERNAL_PAGELIST_TARGET,),
            gtk.gdk.ACTION_MOVE )

    def change_view(self, view):
        assert (view in ('default', 'collapse', 'disable')), 'Bug: other view value given.'
        self.view = view

    def do_initialize_popup(self, menu):
        '''
        Disable some items in popup menu for only tagged pages mode. 
        Although it is possible to leave it as is but it is not 
        recommended to create or change page names since not all pages 
        are shown.
        '''
        model = self.get_model()
        if not isinstance(model, gtk.TreeModelFilter):
            PageTreeView.do_initialize_popup(self, menu)
            return 

        path = self.get_selected_path() or Path(':')

        item = gtk.MenuItem(_('Open in New Window'))
        item.connect('activate', lambda o: self.ui.open_new_window(path))
        menu.append(item)

        menu.append(gtk.SeparatorMenuItem())

        item = gtk.ImageMenuItem('gtk-copy')
        item.connect('activate', lambda o: self.do_copy())
        menu.append(item)

        self.populate_popup_expand_collapse(menu)
        menu.show_all()

    def set_model(self, model, _show_tagged = False):
        '''
        Set the model to be used.
	:param _show_tagged: if True enable tagged mode.
        '''
        # disconnect previous model
        oldmodel = self.get_model()
        if oldmodel:
            if isinstance(oldmodel, gtk.TreeModelFilter):
                oldmodel = oldmodel.get_model()
            oldmodel.disconnect_index()

        if _show_tagged:
            model = self._init_modelfilter(model)
        PageTreeView.set_model(self, model)

    def _init_modelfilter(self, model):
        '''
        Introduce gtk.TreeModelFilter to show only pages with tags.
        '''

        def func(model, iter):
            '''Function to filter pages.'''
            if model.iter_has_child(iter):
                return True # parent will be seen
            else:
                # Show only tagged pages.
                try:
                    # Check if there is any tag present.
                    next(model.index.list_tags(model.get_user_data(iter).indexpath))
                except StopIteration:
                    return False
                return True

        modelfilter = model.filter_new(root = None)
        modelfilter.set_visible_func(func)

        # HACK add some methods and attributes
        # (can not subclass gtk.TreeModelFilter because it lacks a constructor)
        def get_indexpath(treeiter):
	    '''Get an L{IndexPath} for a C{gtk.TreeIter}'''
            childiter = modelfilter.convert_iter_to_child_iter(treeiter)
            if childiter:
        	return model.get_indexpath(childiter)
            else:
        	return None

        def get_treepath(path):
            '''Get a gtk TreePath for a given L{IndexPath}'''
            treepath = model.get_treepath(path)
            if treepath:
                return modelfilter.convert_child_path_to_path(treepath)
            else:
                return None

        modelfilter.get_indexpath = get_indexpath
        modelfilter.get_treepath = get_treepath
        modelfilter.index = model.index
        modelfilter.set_current_page = model.set_current_page
        return modelfilter

    def set_current_page(self, path, vivificate = False):
        '''
        Ensure that parent with tagged pages will autoexpand 
        if clicked on some of its children. 
        Also added new view options.
	:param path: a notebook L{Path} object for the page.
        '''
        model = self.get_model()
        if model is None:
            return None # index not yet initialized ...

        if self.view == 'collapse':
            # Collapse all other pages and expand only current page.
            self.collapse_all()

        if (not isinstance(model, gtk.TreeModelFilter)) or model.get_treepath(path):
            return PageTreeView.set_current_page(self, path, vivificate)

        # Path may be invisible due to modelfilter.
        if path.parent and (not path.parent.isroot) and (self.view != 'disable'):
            # Expand parent path if it is available.
            parent_treepath = model.get_treepath(path.parent)
            if parent_treepath:
                self.expand_to_path(parent_treepath)
        return None


# ------------------------
# ----- Tags Manager -----
# ------------------------

class TagsManagerDialog(Dialog):
    '''
    Tags Manager dialog to do some basic operations with 
    tags and to set icons for tags.
    '''
    def __init__(self, window, index, uistate):

        Dialog.__init__(self, window, _('Tags Manager (IconTags plugin)'), # T: dialog title
                        buttons=gtk.BUTTONS_OK_CANCEL,
                        defaultwindowsize=(450, 400) )

        # Don't confuse with local variable 'self.uistate',
        # which is already determined for this class.
        self._window = window
        self.plugin_uistate = uistate
        self.show_pages_button = gtk.ToggleButton('Show Pages')
	self.show_pages_button.connect('toggled', self.toggle_show_pages)
        self.add_extra_button(self.show_pages_button)

        self.treeview_tags = TagsManagerTagsView(index, self.plugin_uistate['Icons for Tags'])
        self.treeview_pages = TagsManagerPagesView(index, window.ui)
        self.scrolled_widget = ScrolledWindow(self.treeview_tags)
        self.vbox.pack_start(self.scrolled_widget, True)

        self.treeview_tags.connect('row-activated', self.get_tag)

        # Enable left/right arrows to navigate between views.
        self.treeview_tags.connect('key-release-event', self.toggle_view)
        self.treeview_pages.connect('key-release-event', self.toggle_view)

        # Update if tags change.
        self.connectto_all(index, (
            ('tag-inserted', lambda *a: self.update()),
            ('tag-removed', lambda *a: self.update())
        ))

        self.show_all()

    def toggle_view(self, treeview, event):
        '''Change view by pressing Left/Right arrows on keyboard.'''
        key = gtk.gdk.keyval_name(event.keyval)
        if key == 'Right' and treeview == self.treeview_tags:
            self.show_pages_button.set_active(True)
        elif key == 'Left' and treeview == self.treeview_pages:
            self.show_pages_button.set_active(False)

    def get_tag(self, treeview, path, column):
        '''Place the tag to the cursor position.'''
        model = treeview.get_model()
        iter = model.get_iter(path)
        tag = '@' + model.get_value(iter, treeview.TAG_COL)
        buffer = self._window.pageview.view.get_buffer()
        buffer.insert_tag_at_cursor(tag)

    def update(self):
        '''Update both tags and pages trees.'''
        self.treeview_tags.refill_model()
        self.treeview_pages.refill_model(self.treeview_pages.current_tag)

    def toggle_show_pages(self, button):
        ''' 'Show Pages' button is clicked.'''
        for widget in self.scrolled_widget.get_children():
            self.scrolled_widget.remove(widget)

        model, iter = self.treeview_tags.get_selection().get_selected()
        if button.get_active():
            self.scrolled_widget.add(self.treeview_pages)
            # Set values for 'self.treeview_pages'.            
            if iter:
                selected_tag = model.get_value(iter, self.treeview_tags.TAG_COL)
                self.treeview_pages.refill_model(selected_tag)
        else:
            self.scrolled_widget.add(self.treeview_tags)
            # Scroll to tag in 'self.treeview_tags'.            
            if iter:
                path = model.get_path(iter)
                self.treeview_tags.scroll_to_cell(path)
        self.show_all()

    def do_response_ok(self, *a):
        ''' OK button is pressed.'''
        self.plugin_uistate['Icons for Tags'] = self.treeview_tags.icons_for_tags
        self.result = True
	return True


class TagsManagerTagsView(SingleClickTreeView):
    '''
    Class to show tags with icons in a treeview.
    Is used in Tags Manager Dialog.
    '''
    TAG_COL = 0 # column with tag name
    ICON_COL = 1 # column with icon image
    ICON_NAME = 2 # column to sort ICON_COL
    N_PAGES_COL = 3 # column to show number of pages

    def __init__(self, index, preferences):
        self.index = index
        # Icons corresponding to tags, prevent unnecessary changing.
        self.icons_for_tags = preferences.copy()

        self.model = gtk.ListStore(str, gtk.gdk.Pixbuf, str, int) # TAG_COL, ICON_COL, ICON_NAME, N_PAGES_COL
        SingleClickTreeView.__init__(self, self.model)

        cells = (('Tags', self.TAG_COL, True),
                 ('Pages', self.N_PAGES_COL, False))
        for name, col_id, expand in (cells):
            cell = gtk.CellRendererText()
            cell.set_property('ellipsize', pango.ELLIPSIZE_END)
            cell.set_property('cell-background', 'white')
            col = gtk.TreeViewColumn(name, cell)
            col.set_attributes(cell, text = col_id)
            col.set_resizable(expand)
            col.set_expand(expand)
            col.set_sort_column_id(col_id)
            self.append_column(col)

        cell = gtk.CellRendererPixbuf()
        cell.set_property('cell-background', 'white')
        col = gtk.TreeViewColumn('Icon', cell)
        col.set_attributes(cell, pixbuf = self.ICON_COL)
        col.set_resizable(False)
        col.set_expand(False)
        col.set_sort_column_id(self.ICON_NAME)
        self.append_column(col)
 
        self.refill_model()
 
    def row_activated(self, path, column):
        if column.get_sort_column_id() != self.ICON_NAME:
            return False

        def set_icon(path, icon_name = None):

            iter = self.model.get_iter(path)
            tag = self.model.get_value(iter, self.TAG_COL)
            tag = unicode(tag) #  to use with non latin characters

            if icon_name:
                self.icons_for_tags[tag] = icon_name
            else:
                self.icons_for_tags.pop(tag, None)
            self.refill_model()
            return True

        menu = gtk.Menu()

        item = gtk.MenuItem('None')
        item.connect('activate', lambda item: set_icon(path))
        menu.append(item)

        icons = sorted([(a, render_icon(b)) for (a,b) in ICONS.iteritems()
                        if a not in RESERVED_ICON_NAMES])
        for name, icon in icons:
            image = gtk.Image()
            image.set_from_pixbuf(icon)
            item = gtk.ImageMenuItem(name)
            item.set_use_underline(False)
            item.set_image(image)
            item.zim_icon_name = name
            item.connect('activate', lambda item: set_icon(path, item.zim_icon_name))
            menu.append(item)

        menu.show_all()
        menu.popup(None, None, None, 3, 0)

    def refill_model(self):
        '''Update model.'''
        self.model.clear()

        for tag in [a.name for a in self.index.list_all_tags()]:
            if tag in self.icons_for_tags:
                icon_name = self.icons_for_tags[tag]
                rendered_icon = render_icon(ICONS[icon_name])
            else:
                icon_name, rendered_icon = None, None

            self.model.append([tag, rendered_icon, icon_name,
                               self.index.n_list_tagged_pages(tag)])

        # Sort tags by number of pages and then by names.
        self.model.set_sort_column_id(self.TAG_COL, order = gtk.SORT_ASCENDING)
        self.model.set_sort_column_id(self.N_PAGES_COL, order = gtk.SORT_DESCENDING)


class TagsManagerPagesView(SingleClickTreeView):
    '''
    Class to show pages for a selected tag.
    Is used in Tags Manager Dialog.
    '''
    PAGE_COL = 0 # column with page name
    TAGS_N_COL = 1 # column with number of tags for the page    
    TAGS_COL = 2 # column with all tags for the page

    def __init__(self, index, ui):
        self.index = index
        self.ui = ui
        self.current_tag = None

        self.model = gtk.ListStore(str, int, str) # PAGE_COL, TAGS_COL
        SingleClickTreeView.__init__(self, self.model)

        cells = (('Page', self.PAGE_COL, True),
                 ('N', self.TAGS_N_COL, False),
                 ('Tags', self.TAGS_COL, True))
        for name, col_id, expand in (cells):
            cell = gtk.CellRendererText()
            cell.set_property('ellipsize', pango.ELLIPSIZE_END)
            cell.set_property('cell-background', 'white')
            col = gtk.TreeViewColumn(name, cell)
            col.set_attributes(cell, text = col_id)
            col.set_resizable(expand)
	    col.set_expand(expand)
	    col.set_sort_column_id(col_id)
            self.append_column(col)

        self.connect('row-activated', lambda treeview, path, column:
                              self.row_activated(path, column))
        self.refill_model()

    def refill_model(self, tag = None):
        '''Update model.'''
        self.model.clear()
        self.current_tag = tag

        if tag:
            tag = unicode(tag) #  to use with non latin names

            for page in self.index.list_tagged_pages(tag):
                # Exclude current tag to not include it in sorting.
                tags = [tag] + sorted([a.name for a in self.index.list_tags(page)
                               if a.name != tag])
                self.model.append([page.name, len(tags), ', '.join(tags)])

        # Sort pages by names.
        self.model.set_sort_column_id(self.PAGE_COL, order = gtk.SORT_DESCENDING)

    def row_activated(self, path, column):
        '''Open page in the view.'''
        iter = self.model.get_iter(path)
        name = self.model.get_value(iter, self.PAGE_COL)
	self.ui.open_page(Path(name))

