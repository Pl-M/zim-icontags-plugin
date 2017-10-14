# -*- coding: utf-8 -*-

# Copyright 2016-2017 Pavel_M <plprgt@gmail.com>,
# released under the GNU GPL version 3.
# This is a plugin for Zim-wiki program (zim-wiki.org) by Jaap Karssenberg.

import gtk
import re
import os
import logging

from zim.config import data_dir

logger = logging.getLogger('zim.plugins.icontags')

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
# It is used to filter them from other icons.
RESERVED_ICON_NAMES = {NO_IMAGE, SEVERAL_ICONS, FOLDER_ICON,
                       FOLDER_TAGS_ICON, FILE_ICON, FILE_TAGS_ICON}

# Icons are written in notebook as text (like "[ICON=calendar]") in bold font
# (framed by STRONG_MARKUP).
# Bold is used to look for icons amidst all elements in bold.
STRONG_MARKUP = '**'
PREFIX, POSTFIX = '[ICON=', ']'
ICON_RE = re.compile(r'(?<=\{}).*?(?={})'.format(PREFIX, POSTFIX), re.U)



def getIconMarkup(iconName):
    return '{0}{1}{2}{3}{0}'.format(STRONG_MARKUP, PREFIX, iconName, POSTFIX)

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

class _RenderIcon:
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

ICONS = _load_icons() # init and load all icons

# Use it as: "render_icon(ICONS['tags'])" to return the rendered image.
render_icon = _RenderIcon()


