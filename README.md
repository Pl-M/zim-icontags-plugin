# zim-icontags-plugin

This is a plugin for Zim-wiki program (http://zim-wiki.org/).  
This plugin can be used in Zim 0.63/0.65/0.67.

**The version for Zim 0.67 is currently in test mode and may contain bugs.**

### What is this plugin for
This plugin provides a new Index like panel with some new features:
* icons for every page set individually or based on available tags
* tags near a pagename
* onclick actions in the panel to auto close other opened elements

A new Tagsmanager dialog is added to simplify some basic operations with tags and allow to set icons for pages based on tags. 
More information can be found in [IconTags.txt](IconTags.txt).

### How to install
The plugin can be installed like any other plugin by copying [IconTags.py](0.63/IconTags.py) file for Zim 0.63-0.65 or [icontags](0.67/icontags) folder for Zim 0.67 to the folder with plugins (for more information look at https://github.com/jaap-karssenberg/zim-wiki/wiki/Plugins). 

To install icons the [Tags_Icons](Tags_Icons) directory with all files in it should be copied to the zim's 'pixmaps' folder.    
In Windows this folder can be found in Zim's directory (e.g. "C:/Zim Desktop Wiki/data" for version with installer and "C:/Zim Portable/App/ZimDesktopWiki/data" for a portable version); in Linux Mint in "/usr/share/zim/pixmaps".

### How to install new icons
An icon should be a small png file (e.g. 24x24 px or 64x64 px, if size doesn't fit the program will scale it). To install a new icon it should be manually copied to the [Tags_Icons](Tags_Icons) directory. After restarting Zim the icon will be loaded by the plugin.

### License
The plugin [IconTags.py](IconTags.py) is released under the GNU GPL version 3.    
Icons are from Tango Desktop Project (http://tango.freedesktop.org/). The Tango base icon theme is released to the Public Domain.

### Screenshots
![icIndex](Screenshots/IconTags%20plugin%20icIndex.jpg?raw=true)
![TagsManager](Screenshots/IconTags%20plugin%20TagsManager.jpg?raw=true)

