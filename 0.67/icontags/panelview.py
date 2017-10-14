# -*- coding: utf-8 -*-

# Copyright 2016-2017 Pavel_M <plprgt@gmail.com>,
# released under the GNU GPL version 3.
# This is a plugin for Zim-wiki program (zim-wiki.org) by Jaap Karssenberg.


import gobject
import gtk
import pango
import logging

from zim.gui.pageindex import PageTreeStore, PageTreeView, \
    NAME_COL, TIP_COL, STYLE_COL, \
    FGCOLOR_COL, WEIGHT_COL, N_CHILD_COL
from zim.notebook import Path
from zim.gui.widgets import encode_markup_text, BrowserTreeView
from zim.signals import ConnectorMixin
from zim.gui.clipboard import INTERNAL_PAGELIST_TARGET
from zim.notebook.index.tags import TagsView
from zim.notebook.index.pages import PageIndexRecord
from zim.notebook.index.pages import IndexNotFoundError

from .tagsmanager import TagsManagerDialog
from .iconutils import render_icon, getIconMarkup
from .iconutils import NO_IMAGE, SEVERAL_ICONS, FOLDER_ICON, \
    FOLDER_TAGS_ICON, FILE_ICON, FILE_TAGS_ICON, RESERVED_ICON_NAMES, ICONS
from .indexer import IconsView

logger = logging.getLogger('zim.plugins.icontags')



ICON_COL = 8 #: Column with icons


class IconTagsPluginWidget(ConnectorMixin, gtk.ScrolledWindow):
    '''Main Widget.'''

    def __init__(self, index, ui, uistate): # XXX
        gtk.ScrolledWindow.__init__(self)
        self.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.set_shadow_type(gtk.SHADOW_IN)

        self.ui = ui
        self.index = index
        self.iconsindex = None

        self.treeview = IconsTreeView(ui) # XXX
        self.add(self.treeview)

        self.uistate = uistate
        self.uistate.setdefault('Open pages', 'default') # values 'default, collapse, disable'
        self.treeview.change_view(self.uistate['Open pages'])

        self.uistate.setdefault('show tags', False) # show tags with names
        self.uistate.setdefault('Icons for Tags', {}) # set icons for available tags

        # All available tags in the notebook.
        tags = [a.name for a in TagsView.new_from_index(index).list_all_tags()]

        # Check that tags and icons are still available.
        self.uistate['Icons for Tags'] = dict(
            [(tag, icon) for (tag, icon) in self.uistate['Icons for Tags'].iteritems()
             if ( (tag in tags) and (icon in ICONS) )] )

        self._show_tagged = False # if True - show only pages with tags

        self.connectto(self.treeview, 'populate-popup', self.on_populate_popup)
        self.connectto_all(ui, ( # XXX
            'open-page',
            ('start-index-update', lambda o: self.disconnect_model()),
            ('end-index-update', lambda o: self.reload_model()), ))

        self.reload_model()

    def setIndexer(self, isset):
        """This function is called from outside to set value."""
        if isset:
            self.iconsindex = IconsView.new_from_index(self.index)
        else:
            self.iconsindex = None
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

        model = IconsTreeStore(self.index, self.iconsindex,
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
        """This function is called from outside to show/hide vertical lines."""
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

    def update_page(self, pagename):
        self.treeview.get_model().update_page(pagename)

    def insert_icon(self, pageview):
        '''Create widget to choose an icon and insert an icon shortcode.'''

        def _insert(item):
            '''Insert an icon shortcode to the cursor position.'''
            text = getIconMarkup(item)
            pageview.view.get_buffer().insert_at_cursor(text)

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
            oldmodel.disconnect_all()

        if _show_tagged:
            model = self._init_modelfilter(model)
        PageTreeView.set_model(self, model)

    def _init_modelfilter(self, model):
        '''
        Introduce gtk.TreeModelFilter to show only pages with tags.
        '''
        tagsview = TagsView.new_from_index(model.index)

        def func(model, iter):
            '''Function to filter pages.'''
            if model.iter_has_child(iter):
                return True # parent will be seen
            else:
                # Show only tagged pages.
                try:
                    # Check if there is any tag present.
                    next(tagsview.list_tags(model.get_indexpath(iter)))
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
            treepath = None
            try:
                treepath = model.find(path)
            except IndexNotFoundError:
                return None

            if treepath:
                return modelfilter.convert_child_path_to_path(treepath)
            else:
                return None

        def set_current_page(path):
            treepath = model.set_current_page(path)
            if treepath:
                return modelfilter.convert_child_path_to_path(treepath)
            else:
                return None

        modelfilter.get_indexpath = get_indexpath
        modelfilter.get_treepath = get_treepath
        modelfilter.index = model.index
        modelfilter.set_current_page = set_current_page
        modelfilter.update_page = model.update_page

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

    def __init__(self, index, iconindex, show_tags, icons_for_tags):
        self.index = index
        self.iconindex = iconindex
        self.icons_for_tags = icons_for_tags
        self.show_tags = show_tags

        # Cache pagenames with tags.
        self._pagenames_cache = {}
        self._clear_cache_scheduled = False

        PageTreeStore.__init__(self, index)
        self._connect()

    def on_get_value(self, iter, column):
        '''
        Modify to return new pagenames, tooltips and icons.
        Columns 'NAME_COL', 'TIP_COL' and 'ICON_COL' use cache,
        other columns works with default methods.
        '''

        if (column == NAME_COL) or (column == TIP_COL):
            try:
                return self._pagenames_cache[iter.row['name']][column]
            except KeyError:
                pass
        elif column == ICON_COL:
            try:
                return render_icon(self._pagenames_cache[iter.row['name']][column])
            except KeyError:
                pass
        else:
            return PageTreeStore.on_get_value(self, iter, column)

        # Value is not in cache.
        # Find tags, icons and put values to cache.
        page = PageIndexRecord(iter.row)
        tags = [a.name for a in TagsView.new_from_index(self.index).list_tags(page)]
        icon = None

        if self.iconindex:
            icon = self.iconindex.get_icon(iter.row['name'])

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
            elif page.haschildren:
                icon = ICONS[FOLDER_TAGS_ICON]
            else:
                icon = ICONS[FILE_TAGS_ICON]
        else:
            if page.haschildren:
                icon = ICONS[FOLDER_ICON]
            else:
                icon = ICONS[FILE_ICON]

        if tags and self.show_tags: # show tags after page name
            name = '{} ({})'.format(page.basename, ', '.join(tags))
        else:
            name = page.basename

        self._pagenames_cache[iter.row['name']] = {NAME_COL: name,
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

    def update_page(self, pagename):
        '''Update page in the cache and in the treeview.'''

        self._pagenames_cache.pop(pagename, None)
        try:
            treepath = self.find(Path(pagename))
        except IndexNotFoundError:
            return None
        else:
            treeiter = self.get_iter(treepath)
            self.emit('row-changed', treepath, treeiter)

    def _connect(self):
        def on_tag_changed(o, row, pagerow):
            self.update_page(pagerow['name'])

        self.connectto_all(self.index.update_iter.tags, (
            ('tag-added-to-page', on_tag_changed),
            ('tag-removed-from-page', on_tag_changed),
        ))
