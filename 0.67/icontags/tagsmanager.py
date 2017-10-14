# -*- coding: utf-8 -*-

# Copyright 2016-2017 Pavel_M <plprgt@gmail.com>,
# released under the GNU GPL version 3.
# This is a plugin for Zim-wiki program (zim-wiki.org) by Jaap Karssenberg.

import gtk
import pango

from zim.notebook import Path
from zim.gui.widgets import  ScrolledWindow, Dialog, SingleClickTreeView
from zim.notebook.index.tags import TagsView

from .iconutils import render_icon, RESERVED_ICON_NAMES, ICONS



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
        self.connectto_all(index.update_iter.tags, (
            ('tag-row-inserted', lambda *a: self.update()),
            ('tag-row-deleted', lambda *a: self.update())
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
        tag = '@' + model.get_value(model.get_iter(path), treeview.TAG_COL)
        self._window.pageview.view.get_buffer().insert_tag_at_cursor(tag)

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
        for name, col_id, expand in cells:
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

            tag = self.model.get_value(self.model.get_iter(path), self.TAG_COL)
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

        tagview = TagsView.new_from_index(self.index)
        for tag in [a.name for a in tagview.list_all_tags()]:
            if tag in self.icons_for_tags:
                icon_name = self.icons_for_tags[tag]
                rendered_icon = render_icon(ICONS[icon_name])
            else:
                icon_name, rendered_icon = None, None

            self.model.append([tag, rendered_icon, icon_name,
                               tagview.n_list_pages(tag)])

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
        self.tagview = TagsView.new_from_index(index)
        self.ui = ui
        self.current_tag = None

        self.model = gtk.ListStore(str, int, str) # PAGE_COL, TAGS_COL
        SingleClickTreeView.__init__(self, self.model)

        cells = (('Page', self.PAGE_COL, True),
                 ('N', self.TAGS_N_COL, False),
                 ('Tags', self.TAGS_COL, True))
        for name, col_id, expand in cells:
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

            for page in self.tagview.list_pages(tag):
                # Exclude current tag to not include it in sorting.
                tags = [tag] + sorted([a.name for a in self.tagview.list_tags(page)
                               if a.name != tag])
                self.model.append([page.name, len(tags), ', '.join(tags)])

        # Sort pages by names.
        self.model.set_sort_column_id(self.PAGE_COL, order = gtk.SORT_DESCENDING)

    def row_activated(self, path, column):
        '''Open page in the view.'''
        name = self.model.get_value(self.model.get_iter(path), self.PAGE_COL)
        self.ui.open_page(Path(name))

