# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## Customize your APP title, subtitle and menus here
#########################################################################
response.logo = DIV(
                    A(IMG(_src=URL('static', 'images/mrx_logo_small.png')),
                      _class="navbar-brand",
                      _href=URL('index'),
                      _style="padding-top:4px;padding-left:15px;",
                      ),
                    _class='navbar-header',
                    )
response.title = ' '.join(word.capitalize() for word in request.application.split('_'))
response.subtitle = T('customize me!')

## read more at http://dev.w3.org/html5/markup/meta.name.html
response.meta.author = 'Sean Kim <moonbal@gmail.com>'
response.meta.description = 'xRecruit'
response.meta.keywords = 'recruitment database'
response.meta.generator = 'Web2py Web Framework'

## your http://google.com/analytics id
response.google_analytics_id = None

#########################################################################
## this is the main application menu add/remove items as required
#########################################################################

response.menu = [
    ('', False, A('XHours', _href=URL('xhours','default','index'), _target='_blank')),
    ('', False, A('Watch List', **{'_href':'#', '_class':'menu-link', '_data-toggle':'modal', '_data-target':'#watchlist'})),
    ('', False, SPAN(INPUT(_id='bookmark-toggle', _type='checkbox'), LABEL('Bookmarks', _for='bookmark-toggle'))),
    ('', False, SPAN(INPUT(_id='filter-toggle', _type='checkbox'), LABEL('Filter', _id='filter-label', _for='filter-toggle'))),
    ('', False, A("Wiki", _href="http://wiki/Xrecruit", _target="_blank"), []),
]

DEVELOPMENT_MENU = False

#########################################################################
## provide shortcuts for development. remove in production
#########################################################################

def _():
    # shortcuts
    app = request.application
    ctr = request.controller
    # useful links to internal and external resources
    response.menu += []
    
if DEVELOPMENT_MENU: _()
