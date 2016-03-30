# -*- coding: utf-8 -*-
"""
Jobapps - job application database

Membership required: admin, supe, hr, recruit

Websocket server
python /opt/web2py/gluon/contrib/websocket_messaging2.py -k web2py4me -p 8080 -l 192.168.1.1

"""
import os
import time
from datetime import datetime, date, timedelta
import xlwt
from collections import defaultdict
import logging
import logging.config
logging.config.fileConfig('logging.conf')
logger = logging.getLogger("web2py.app.{0}".format(request.application))
logger.setLevel(logging.DEBUG)
import re
import MySQLdb
from contextlib import closing
import random
from gluon.contrib import simplejson
from gluon.contrib.websocket_messaging2 import websocket_send

mail = auth.settings.mailer
mail.settings.server = 'mail.com'
mail.settings.sender = 'noreply@mail.com'
mail.settings.login = 'admin:pass'

__version__ = '2.4c'

WEBSOCKET_IP = '192.168.1.1:8080' #'192.168.4.66:8888'
WEBSOCKET_KEY = 'Akjf2HFoy'
WEBSOCKET_GROUP = 'xrecruit'

SSE_INTERVAL = 5 * 60 # sse send interval (seconds)
MSGLIMIT = 10
TIME_FORMAT = '%b %d %Y %I:%M %p'

# email recipients 
INTERVIEW_WATCHERS_TO = ['watcher_to@mail.com'] # status_id 2
INTERVIEW_WATCHERS_NY = ['watcher_ny@mail.com']

INTERVIEW_POST_PASS = ['personA@mail.com']

OFFER_REQUIRED_TO = ['personB@mail.com'] # status_id 10
OFFER_REQUIRED_NY = ['personC@mail.com'] # status_id 10

OFFER_MADE_TO = ['personD@mail.com'] # status_id 13
OFFER_MADE_NY = ['personE@mail.com'] # status_id 13

PM_STATUS = [1,2,3,7,8,9,10,11,12,14,15]

def print_timing(func):
    def wrapper(*arg, **kwargs):
        t1 = time.time()
        res = func(*arg, **kwargs)
        t2 = time.time()
        border = '==='
        output = '[%s] %s  %s took %0.3f sec  %s' %(request.application.upper(), border, func.func_name, (t2-t1)*1.0, border)
        logger.debug(output)
        return res
    return wrapper

def xcheck(f):
    """Decorator to prevent unauthorized external access
    
    >>> f = lambda x: 1
    >>> x = xcheck(f)
    """
    def wrapper(*args, **kwargs):
        if not request.is_local:
            ipaddys = re.compile('^(192\.168|1\.2|10\.1)\..+$')
            if not ipaddys.search(request.client):
                # remote access restriction
                logger.error("{0} - Access attempt from unauthorized ip: {1}".format(request.application.upper(), request.client))
                raise HTTP(403, "Unauthorized access")
            else:
                # local access
                #logger.debug("Local access from {0}".format(request.client))
                pass
                
        return f(*args, **kwargs)
    return wrapper

@xcheck
@auth.requires_login()
@auth.requires(auth.has_membership('admin') or auth.has_membership('supe') or auth.has_membership('hr') or auth.has_membership('recruit'))
def index():
    """Main page
    """
    #session.forget()
    session.depts = None
    session.all_projects = None
    session.all_users = None
    session.project_names = None
    session.holidays = None
    session.current_task_ids = None
    session.user_tasks = None
    session.thumbnails = None
    session.timelog_form_vals = None
    
    dbupdate = dbmrxcms().select(dbmrxcms.xrecruit_update.ALL,orderby=~dbmrxcms.xrecruit_update.id).first()
    session.last_update = dbupdate.date_created
    session.last_updater = dbupdate.client
    
    theader = [
               TH('Applicant'),
               TH('Status'),
               TH('Position'),
               TH('Studio'),
               TH('Cover'),
               TH('CV'),
               TH('Reel'),
               TH('Applied On'),
               TH('VISA'),
               TH('Country'),
               TH('How'),
               TH('reel_detail'),
               TH('hearsay_detail'),
               TH('imdb'),
               TH('linkedin'),
               TH('email'),
               TH('phone'),
               TH('visa_status'),
               TH('status_id'),
               TH('applicant_id'),
               TH('posting_visible'),
               TH('interview_id'),
               TH('interview_date'),
               TH('interviewer'),
               TH('interview_done'),
               TH('interview_xuser_id'),
               ]
    
    table = TABLE(
                  THEAD(TR(*theader)),
                  TFOOT(TR(*theader)),
                  _id='application-table',
                  _class='table table-striped table-bordered dataTable'
                  )
    
    # Watchlist
    watchlist = watchlistGrid()
    
    # news ticker
    ticker = getXrecruitUpdate()
    
    filter_vals = ''
    if request.cookies.has_key(request.application):
        filter_vals = request.cookies[request.application].value
    
    filterform = filterPanel()
    
    opts, tabs = getBookmarks()
    bookmarkpanel = bookmarkPanel(opts, tabs)
    
    status_select = statusSelect()
    
    hr_perm = auth.has_membership('admin') or auth.has_membership('supe') or auth.has_membership('hr')
    
    # get subscribed posting ids
    subscribed = []
    srows = dbmrxcms((dbmrxcms.xrecruit_watch_subscribe.watch_id==dbmrxcms.xrecruit_watch.id) & \
                     (dbmrxcms.xrecruit_watch.username==auth.user.username)).select()
    for srow in srows:
        subscribed.append(srow.xrecruit_watch_subscribe.posting_id)
    
    # comment template
    comment_template = LI(
                          DIV(
                              DIV(
                                  SPAN('{0}', _class='text-muted'),
                                  SPAN(
                                       SMALL('{1}', _class='text-italic'),
                                       _class='text-muted date-span'
                                       ),
                                  ),
                              P('{2}',
                                SPAN(_class='fa fa-reply reply-icon', _title='Reply'),
                                SPAN(_class='fa fa-times text-red delete-icon', _title='Delete'),
                                _class='comment-body'
                                ),
                              _class='comment-container new-comment'
                              ),
                          DIV(
                              TEXTAREA(_class='form-control comment-input', _placeholder='reply to above comment', _rows=1),
                              BUTTON('Reply',
                                     **{'_class':'btn btn-primary btn-sm reply-submit',
                                        '_data-comment':'{3}',
                                        '_data-application':'{4}',
                                        }
                                     ),
                              _class='reply-input collapse',
                              ),
                          UL(_class='ul-reply'),
                          _class='app-{5}',
                          _id='comment-{3}',
                          )
    
    interview_template = DIV(
                             SPAN(
                                  SPAN('{0}', _class='date-display'),
                                  INPUT(**{'_class': 'form-control input-sm date-edit',
                                           '_value': '{1}',
                                           '_data-interviewid': '{2}',
                                           }
                                        )
                                  ),
                             SPAN('{3}', _class='interview-title'),
                             SPAN('{4}', _class='label label-as-badge label-{5}'),
                             SPAN(**{'_class': 'fa fa-times pull-right pointer interview-delete',
                                     '_data-interviewid': '{2}',
                                     '_data-application': '{6}',
                                     '_title': 'Cancel Interview'
                                     }),
                             _id='interview-detail-{2}',
                             _class='interview-detail interview-{6}'
                             )
    
    notice = DIV(
                 SPAN('Testing Message', _class='notice-body'),
                 SPAN(
                      A('[close]', _href='#', _class='dismiss'),
                      A('[close all]', _href='#', _class='dismiss-all'),
                      _class='pull-right'
                      ),
                 _id='notify_warning',
                 _class='warning message'
                 )
    
    return dict(table=table,
                notice=notice,
                filter_form=filterform,
                bookmarks=bookmarkpanel,
                watchlist_grid=watchlist,
                status_select=status_select,
                ticker=ticker,
                filter_vals=filter_vals,
                tab_template=tabContentTemplate(),
                interview_template=interview_template,
                subscribed=subscribed,
                hr_permission=hr_perm,
                comment_template=comment_template,
                websocket_ip=WEBSOCKET_IP,
                websocket_key=WEBSOCKET_KEY,
                websocket_group=WEBSOCKET_GROUP
                )

def formGen(table=False):
    """Generate form element
    @param filter: for filtering tablesorter
    
    >>> f = formGen()
    >>> f.XML().startswith('<form')
    >>> True
    """
    positions = [OPTION(p.title) for p in dbmrxcms().select(dbmrxcms.jobop_posting.title, distinct=True)]
    
    if table:
        visas = [OPTION('CAN'), OPTION('US'), OPTION('VISA')]
        statuses = [OPTION(s.name) for s in dbmrxcms().select(dbmrxcms.jobop_status.ALL, orderby=dbmrxcms.jobop_status.ordering)]
        locs = [OPTION(loc.name) for loc in dbmrxcms().select(dbmrxcms.jobop_location.ALL)]
        hows = [OPTION(h.name) for h in dbmrxcms().select(dbmrxcms.jobop_hearsay.ALL)]
        futures = ''
        interviews = ''
        cls = ' multi-select'
        m = 'multiple'
        id = 'mform'
        prefix= 'ts'
        name_prefix = 'ts-'
        categories = ''
        btns = DIV(
                   DIV(
                       BUTTON('Clear', _id='ts-clear', _class='form-control btn btn-danger reset'),
                       _class='col-sm-offset-2 col-sm-10'
                       ),
                   _class='form-group'
                   )
        
    else:
        positions.insert(0, OPTION('-- All Positions --', _value=''))
        statuses = [OPTION('-- All Status --', _value='')] + [OPTION(s.name, _value=s.id) for s in dbmrxcms().select(dbmrxcms.jobop_status.ALL, orderby=dbmrxcms.jobop_status.ordering)]
        cats = [OPTION('-- All Categories --', _value='')] + [OPTION(c.name, _value=c.id) for c in dbmrxcms().select(dbmrxcms.jobop_category.ALL)]
        locs = [OPTION('-- All Studios --', _value='')] + [OPTION(loc.name, _value=loc.id) for loc in dbmrxcms().select(dbmrxcms.jobop_location.ALL)]
        visas = [OPTION('-- All VISA Status --', _value='')] + [OPTION(v.status, _value=v.id) for v in dbmrxcms().select(dbmrxcms.jobop_visa.ALL)]
        hows = [OPTION('-- All --', _value='')] + [OPTION(h.name, _value=h.id) for h in dbmrxcms().select(dbmrxcms.jobop_hearsay.ALL)]
        futures = DIV(
                       LABEL('Future:', _class='control-label text-muted col-sm-2'),
                       DIV(
                           SELECT(
                                  OPTION('Include Future Considerations', _value='1'),
                                  OPTION('Exclude Future Considerations', _value='0'),
                                  _id='future',
                                  _name='future',
                                  _class='form-control',
                                  value='1',
                                  ),
                           _class='col-sm-10'
                           ),
                       _class='form-group'
                       )
        interviews = DIV(
                         LABEL('Interview:', _class='control-label text-muted col-sm-2'),
                         DIV(
                             SELECT(OPTION('-- All States --', _value=''),
                                    OPTION('Not Scheduled', _value='0'),
                                    OPTION('Scheduled', _value='1'),
                                    OPTION('Completed', _value='2'),
                                    _id='interview',
                                    _name='interview',
                                    _class='form-control',
                                    value='',
                                    ),
                             _class='col-sm-10'
                             ),
                           _class='form-group'
                           )
        cls = ''
        m = ''
        id = 'filterform'
        prefix= 'filter'
        name_prefix = ''
        categories = DIV(
                         LABEL('Category:', _class='control-label text-muted col-sm-2'),
                         DIV(
                             SELECT(cats, _name='category', _class='form-control{0}'.format(cls), _multiple=m),
                             _class='col-sm-10'
                             ),
                         _class='form-group'
                         )
        btns = DIV(
                   DIV(
                       DIV(
                           DIV(
                               BUTTON('Reset', _id='filter-clear', _class='btn btn-default', _type='reset'),
                               _class='btn-group',
                               ),
                           DIV(
                               BUTTON('Filter', _id='filter-submit', _class='btn btn-primary', _type='submit'),
                               _class='btn-group',
                               ),
                           _class='btn-group btn-group-justified',
                           ),
                       _class='col-sm-offset-2 col-sm-10'
                       ),
                   _class='form-group'
                   )
    
    # form body
    filter_form = FORM(
                       DIV(
                           DIV(
                               LABEL('Position:', _class='control-label text-muted col-sm-2'),
                               DIV(
                                   SELECT(positions, _id='{0}-position'.format(prefix), _name='{0}position'.format(name_prefix), _class='form-control{0}'.format(cls), value='', _multiple=m),
                                   _class='col-sm-10'
                                   ),
                               _class='form-group'
                               ),
                           categories,
                           DIV(
                               LABEL('Status:', _class='control-label text-muted col-sm-2'),
                               DIV(
                                   SELECT(statuses, _id='{0}-status'.format(prefix), _name='{0}status'.format(name_prefix), _class='form-control{0}'.format(cls), value='', _multiple=m),
                                   _class='col-sm-10'
                                   ),
                               _class='form-group'
                               ),
                           DIV(
                               LABEL('Studio:', _class='control-label text-muted col-sm-2'),
                               DIV(
                                   SELECT(locs, _id='{0}-studio'.format(prefix), _name='{0}location'.format(name_prefix), _class='form-control{0}'.format(cls), value='', _multiple=m),
                                   _class='col-sm-10'
                                   ),
                               _class='form-group'
                               ),
                           DIV(
                               LABEL('VISA:', _class='control-label text-muted col-sm-2'),
                               DIV(
                                   SELECT(visas, _id='{0}-visa'.format(prefix), _name='{0}visa'.format(name_prefix), _class='form-control{0}'.format(cls), value='', _multiple=m),
                                   _class='col-sm-10'
                                   ),
                               _class='form-group'
                               ),
                           interviews,
                           _class='col-sm-6'),
                       DIV(
                           futures,
                           DIV(
                               LABEL('How:', _class='control-label text-muted col-sm-2'),
                               DIV(
                                   SELECT(hows, _id='{0}-how'.format(prefix), _name='{0}how'.format(name_prefix), _class='form-control{0}'.format(cls), value='', _multiple=m),
                                   _class='col-sm-10'
                                   ),
                               _class='form-group'
                               ),
                           DIV(
                               LABEL('Country:', _class='control-label text-muted col-sm-2'),
                               DIV(
                                   INPUT(_id='{0}-country'.format(prefix), _name='{0}country'.format(name_prefix), _class='form-control'),
                                   _class='col-sm-10'
                                   ),
                               _class='form-group'
                               ),
                           DIV(
                               LABEL('Date:', _class='control-label text-muted col-sm-2'),
                               DIV(
                                   BUTTON(
                                          I(_class='fa fa-calendar'),
                                          SPAN('Pick a Date Range', _id='{0}-daterange-label'.format(prefix), _class='daterange-label'),
                                          SPAN(_class='caret'),
                                          _id='{0}-dateapplied'.format(prefix),
                                          _class='btn btn-default'
                                          ),
                                   INPUT(_id='{0}-datestart'.format(prefix), _name='{0}datestart'.format(name_prefix), _class='hidden'),
                                   INPUT(_id='{0}-dateend'.format(prefix), _name='{0}dateend'.format(name_prefix), _class='hidden'),
                                   _class='col-sm-10'
                                   ),
                               _class='form-group'
                               ),
                           btns,
                           _class='col-sm-6'),
                       _id=id,
                       _class='form-horizontal',
                       )
    
    return filter_form

def tristateMenu(name, opts):
    tselect = SELECT(opts, _id='filter-{0}'.format(name), _multiple='multiple', _class='hidden tristate-dropdown', _name=name)
    """operand = SELECT([OPTION('AND', _value='and'), OPTION('OR', _value='or')],
                      _id='tristate-op-{0}'.format(name),
                      _class='form-control operand-select',
                      )
    """
    tmenu = DIV(tselect, _class='btn-group')
    return tmenu

@auth.requires_login()
def getBookmarks():
    """
    """
    def getApplications(ids):
        rows = dbmrxcms((dbmrxcms.jobop_applicant.id==dbmrxcms.jobop_application.applicant_id) & \
                        (dbmrxcms.jobop_posting.id==dbmrxcms.jobop_application.posting_id) & \
                        (dbmrxcms.jobop_posting.location_id==dbmrxcms.jobop_location.id) & \
                        (dbmrxcms.jobop_status.id==dbmrxcms.jobop_application.status_id) & \
                        (dbmrxcms.jobop_application.id.belongs(ids))
                        ).select(dbmrxcms.jobop_application.id,
                                 dbmrxcms.jobop_applicant.first_name,
                                 dbmrxcms.jobop_applicant.last_name,
                                 dbmrxcms.jobop_posting.title,
                                 dbmrxcms.jobop_location.name,
                                 dbmrxcms.jobop_status.name,
                                 )
        return rows
    
    bopts = []
    blists = []
    
    for bk in dbmrxcms(dbmrxcms.xrecruit_bookmark.username==auth.user.username).select(orderby=dbmrxcms.xrecruit_bookmark.name):
        bopts.append(OPTION(bk.name, _value=bk.id))
        
        lis = []
        if (bk.application_ids):
            appids = bk.application_ids.split(',')
            for a in getApplications(appids):
                lis.append(LI(
                              DIV(
                                  DIV(
                                      SPAN('{0} {1}'.format(a.jobop_applicant.first_name, a.jobop_applicant.last_name),
                                           _class='bm-name'
                                           ),
                                      SPAN(a.jobop_status.name,
                                           _class='status label label-default'
                                           ),
                                      ),
                                  DIV('{0} - {1}'.format(a.jobop_posting.title, a.jobop_location.name),
                                      _class='bm-position'
                                      ),
                                  _class='leftside'
                                  ),
                              DIV(
                                  SPAN(
                                       I(_class='fa fa-times'),
                                       _class='bookmark-remove'),
                                  _class='rightside'
                                  ),
                              **{'_class': 'bookmark-item',
                                 '_data-id': a.jobop_application.id
                                 }
                              ))
        blists.append(DIV(UL(*lis, _class='bookmark-list'),_id='bookmark-{0}'.format(bk.id),_class='tab-pane'))
        
    bopts.insert(0, OPTION('Placeholder', _value='temp'))
    blists.insert(0, DIV(UL(_class='bookmark-list'),_id='bookmark-temp',_class='tab-pane active'))
    
    return bopts, blists

def bookmarkPanel(select_options, bookmarks):
    """Return Bookmark list
    """
    bdiv = DIV(
               DIV(
                   DIV(
                       DIV(
                           LABEL(
                                 I(_class='fa fa-trash-o'),
                                 _id='bookmark-delete',
                                 _class='btn btn-default',
                                 ),
                           LABEL(
                                 I(_class='fa fa-share-alt'),
                                 _id='bookmark-share',
                                 _class='btn btn-default hidden',
                                 ),
                           LABEL(
                                 I(_class='fa fa-save'),
                                 _id='bookmark-save',
                                 _class='btn btn-default',
                                 ),
                           LABEL(
                                 I(_class='fa fa-edit'),
                                 _id='bookmark-edit',
                                 _class='btn btn-default disabled',
                                 ),
                           LABEL(
                                 I(_class='fa fa-plus'),
                                 _id='bookmark-new',
                                 _class='btn btn-default',
                                 ),
                           _class='btn-group btn-group-justified'
                           ),
                       _class='form-group-padder'
                       ),
                   _class='form-group'
                   ),
               DIV(
                   DIV(
                       SELECT(*select_options,
                              _id='bookmark-select', _class='form-control input-sm'),
                       DIV(
                           INPUT(_id='bookmark-name', _class='form-control input-sm'),
                           SPAN(
                                I(_class='fa fa-check'),
                                _id='bookmark-new-create',
                                _class='input-group-addon btn'
                                ),
                           SPAN(
                                I(_class='fa fa-times'),
                                _id='bookmark-new-cancel',
                                _class='input-group-addon btn'
                                ),
                           _id='bookmark-new-form',
                           _class='input-group hidden'
                           ),
                       DIV(
                           INPUT(_id='bookmark-editname', _class='form-control input-sm'),
                           SPAN(
                                I(_class='fa fa-check'),
                                _id='bookmark-edit-submit',
                                _class='input-group-addon btn'
                                ),
                           SPAN(
                                I(_class='fa fa-times'),
                                _id='bookmark-edit-cancel',
                                _class='input-group-addon btn'
                                ),
                           _id='bookmark-edit-form',
                           _class='input-group hidden'
                           ),
                       DIV(
                           INPUT(_id='bookmark-savename', _class='form-control input-sm'),
                           SPAN(
                                I(_class='fa fa-check'),
                                _id='bookmark-save-submit',
                                _class='input-group-addon btn'
                                ),
                           SPAN(
                                I(_class='fa fa-times'),
                                _id='bookmark-save-cancel',
                                _class='input-group-addon btn'
                                ),
                           _id='bookmark-save-form',
                           _class='input-group hidden'
                           ),
                       _class='form-group-padder'
                       ),
                   _class='form-group'
                   ),
               DIV(
                   DIV(bookmarks,
                       _id='bookmark-tabs',
                       _class='tab-content'
                       ),
                   _id='bookmark-tab-div',
                   _class='form-group'
                   ),
               _class=''
               )
    
    return bdiv

def filterPanel():
    """Return Filter side panel with tristate dropdowns
    """
    positions = [OPTION(p.title, **{'_class':'noselect', '_data-tristate':'tri-off'}) for p in dbmrxcms().select(dbmrxcms.jobop_posting.title, distinct=True)]
    statuses = [OPTION(s.name, _value=s.id, **{'_class':'noselect', '_data-tristate':'tri-off'}) for s in dbmrxcms().select(dbmrxcms.jobop_status.ALL, orderby=dbmrxcms.jobop_status.ordering)]
    locs = [OPTION(loc.name, _value=loc.id, **{'_class':'noselect', '_data-tristate':'tri-off'}) for loc in dbmrxcms().select(dbmrxcms.jobop_location.ALL)]
    visas = [OPTION(v.status, _value=v.id, **{'_class':'noselect', '_data-tristate':'tri-off'}) for v in dbmrxcms().select(dbmrxcms.jobop_visa.ALL)]
    hows = [OPTION(h.name, _value=h.id, **{'_class':'noselect', '_data-tristate':'tri-off'}) for h in dbmrxcms().select(dbmrxcms.jobop_hearsay.ALL)]
    
    future_checkbox = DIV(
                          LABEL('Hide Future: ',
                                INPUT(_id='filter-future', _name='future', _type='checkbox'),
                                _class='control-label text-muted',
                                _title='Hide Future Considerations'
                                ),
                          _class='form-group'
                          )
    
    fpanel = FORM(
                 DIV(
                     LABEL('Position', _class='control-label text-muted'),
                     tristateMenu('position', positions),
                     _class='form-group'
                     ),
                 DIV(
                     LABEL('Status', _class='control-label text-muted'),
                     tristateMenu('status', statuses),
                     _class='form-group'
                     ),
                 DIV(
                     LABEL('Studio', _class='control-label text-muted'),
                     tristateMenu('location', locs),
                     _class='form-group'
                     ),
                 DIV(
                     LABEL('VISA', _class='control-label text-muted'),
                     tristateMenu('visa', visas),
                     _class='form-group'
                     ),
                 DIV(
                     LABEL('How', _class='control-label text-muted'),
                     tristateMenu('how', hows),
                     _class='form-group'
                     ),
                 DIV(
                     LABEL('Country', _class='control-label text-muted'),
                     INPUT(_id='filter-country', _name='country', _class='form-control input-sm', _placeholder='country of residence'),
                     _class='form-group'
                     ),
                 DIV(
                     LABEL('Date', _class='control-label text-muted'),
                     DIV(
                         BUTTON(
                                I(_class='fa fa-calendar'),
                                SPAN('Pick a Date Range', _id='filter-daterange-label', _class='daterange-label'),
                                SPAN(_class='caret'),
                                _id='filter-dateapplied',
                                _class='btn btn-default'
                                ),
                         INPUT(_id='filter-datestart', _name='datestart', _class='hidden'),
                         INPUT(_id='filter-dateend', _name='dateend', _class='hidden'),
                         _class='clearboth'
                         ),
                     _class='form-group'
                     ),#future_checkbox,
                 _id='filter-form',
                 _class='slidemenu',
                 )
    return fpanel

@auth.requires_login()
def watchlistGrid():
    """Return postings checkbox grid for subscription panel
    ordered by location > category > alphabetical
    """
    # get current user's setting
    subscribed = []
    ignored = []
    
    watch = dbmrxcms(dbmrxcms.xrecruit_watch.username==auth.user.username).select().first()
    if watch:
        ignored = [i.posting_id for i in dbmrxcms(dbmrxcms.xrecruit_watch_ignore.watch_id==watch.id).select()]
        subscribed = [s.posting_id for s in dbmrxcms(dbmrxcms.xrecruit_watch_subscribe.watch_id==watch.id).select()]
        
    toronto = defaultdict(set)
    newyork = defaultdict(set)
    
    # get postings
    dataset = dbmrxcms((dbmrxcms.jobop_posting.cat_id==dbmrxcms.jobop_category.id)&(dbmrxcms.jobop_posting.archived==0) ).select(dbmrxcms.jobop_posting.ALL, dbmrxcms.jobop_category.name)
    
    for d in dataset:
        v = (d['jobop_posting.id'], d['jobop_posting.title'])
        if d['jobop_posting.location_id']  == 1:
            toronto[d['jobop_category.name']].add(v)
        else:
            newyork[d['jobop_category.name']].add(v)
            
    # build ul grid
    to_litems = []
    for tcat in sorted(toronto.keys()):
        to_litems.append(STRONG(tcat))
        to_cats = []
        for p in sorted(toronto[tcat]):
            ignore = p[0] in ignored
            subs = p[0] in subscribed
            to_cats.append(LI(
                              LABEL(
                                    INPUT(_name='subscribe_%d' %p[0], _class='inline-cb subcb', _type='checkbox', value=subs),
                                    SPAN(p[1], _class='posting-label'),
                                    _class='pointer',
                                    ),
                              _class='posting-li',
                              ))
        to_litems.append(UL(to_cats, _class='posting-grid'))
        
    #logger.debug(newyork)
    ny_litems = []
    for ncat in sorted(newyork.keys()):
        ny_litems.append(STRONG(ncat))
        ny_cats = []
        for p in sorted(newyork[ncat]):
            ignore = p[0] in ignored
            subs = p[0] in subscribed
            ny_cats.append(LI(
                              LABEL(
                                    INPUT(_name='subscribe_%d' %p[0], _class='inline-cb subcb', _type='checkbox', value=subs),
                                    SPAN(p[1], _class='posting-label'),
                                    _class='pointer',
                                    ),
                              _class='posting-li',
                              ))
        ny_litems.append(UL(ny_cats, _class='posting-grid'))
        
    grid = DIV(
               DIV(
                   H4('TORONTO', _style='font-weight:bold;color:#428BCA;'),
                   DIV(to_litems),
                   ),
               BR(),
               DIV(
                   H4('NEW YORK', _style='font-weight:bold;color:#D9534F;'),
                   DIV(ny_litems),
                   ),
               _class='checkbox-grid'
               )
    return grid

def applicantApps():
    applicant_id = int(request.vars.applicantid)
    application_id = int(request.vars.applicationid)
    applinks, interviews = singleApplicantApps(applicant_id, application_id)
    
    result = {'links': ''.join([a.xml() for a in applinks]),
              'interviews': ''.join([i.xml() for i in interviews])
              }
    return simplejson.dumps(result)

def singleApplicantApps(applicant_id, current_application_id):
    """Return applicant's applications
    """
    # get applications
    apps = dbmrxcms((dbmrxcms.jobop_posting.id==dbmrxcms.jobop_application.posting_id) & \
                    (dbmrxcms.jobop_posting.location_id==dbmrxcms.jobop_location.id) & \
                    (dbmrxcms.jobop_status.id==dbmrxcms.jobop_application.status_id) & \
                    (dbmrxcms.jobop_application.applicant_id==applicant_id)
                    ).select(dbmrxcms.jobop_application.id,
                             dbmrxcms.jobop_posting.title,
                             dbmrxcms.jobop_posting.visible,
                             dbmrxcms.jobop_location.name,
                             dbmrxcms.jobop_status.name,
                             dbmrxcms.jobop_interview.id,
                             dbmrxcms.jobop_interview.date,
                             dbmrxcms.jobop_interview.interviewer,
                             dbmrxcms.jobop_interview.done,
                             left=dbmrxcms.jobop_interview.on(dbmrxcms.jobop_interview.application_id==dbmrxcms.jobop_application.id),
                             orderby=dbmrxcms.jobop_posting.title,
                             )
    
    links = []
    interviews = {}
    
    for app in apps:
        if app['jobop_application.id'] == current_application_id:
            cls = 'tab-link-selected'
        else:
            cls = 'tab-link'
        
        links.append(DIV(
                         SPAN('{0} - {1} [{2}]'.format(app['jobop_posting.title'], app['jobop_location.name'], app['jobop_status.name']),
                              **{'_data-application': app['jobop_application.id'],
                                 '_data-future': 1 if app['jobop_posting.visible']==0 else 0,
                                 }
                              ),
                        _class=cls
                        ))
        
        if app['jobop_interview.id']:
            interview_entry = generateInterviewDataDiv(app)
            k = '{0}-{1}'.format(app['jobop_interview.date'].strftime('%Y-%m-%d'), app['jobop_posting.title'])
            interviews[k] = interview_entry
            
    # sort interviews by date desc
    intvs = []
    for k in sorted(interviews.keys(), reverse=True):
        intvs.append(interviews[k])
    
    return (links, intvs)
    
def tabContent(appdata):
    """Return application detail for the tab
    """
    application_id = appdata['application_id']
    # other application info
    applinks, appinterviews = singleApplicantApps(appdata['applicant_id'], application_id)
    if not appinterviews:
        appinterviews = ['None scheduled']
        
    if appdata['applicant_cover_letter']:
        cl = filelink(appdata['applicant_cover_letter'], 'Cover Letter', False)
    else:
        cl = ''
    
    if appdata['applicant_cv_file']:
        cv = filelink(appdata['applicant_cv_file'], 'CV', False)
    else:
        cv = ''
        
    if cl and cv:
        attachments_td = TD(cl, SPAN(', '), cv)
    else:
        attachments_td = TD(cl, cv)
        
    bookmark_btn = BUTTON('Bookmark',
                          **{'_class': 'btn btn-inverse btn-xs bookmarker',
                             '_data-applicationid': appdata['application_id'],
                             '_data-name': appdata['applicant_first_name'],
                             '_data-position': '{0} - {1}'.format(appdata['posting_title'], appdata['location_name']),
                             '_data-status': appdata['status_name']
                             }
                          )
    
    status_select = statusSelect(appdata['status_id'], application_id)
    
    this_link = 'http://{0}/{1}#application-{2}'.format(request.env.http_host, request.application, application_id)
    
    rows = [
            TR(
               TH('This App', _class='text-muted cell-label'),
               TD(bookmark_btn,
                  A(
                    SPAN(_class='fa fa-link'),
                    ' link to this ',
                    _href=this_link
                    ),
                  SPAN('#{0}'.format(application_id), _class='app-number text-muted pull-right'),
                  )
               ),
            TR(
               TH('Status', _class='text-muted cell-label input-label'),
               TD(status_select),
               ),
            TR(
               TH('Schedule', _class='text-muted cell-label input-label'),
               TD(
                  DIV(
                      INPUT(_class='form-control input-sm interview-date', _type='text'),
                      DIV(
                          BUTTON('Set', _class='btn btn-sm btn-default interview-set'),
                          BUTTON('Cancel', _class='btn btn-sm btn-default interview-cancel'),
                          **{'_class': 'input-group-btn',
                             '_data-applicationid': application_id
                             }
                          ),
                      _class='input-group'
                      )
                  ),
               _id='interview-{0}'.format(application_id),
               _class='hidden-input-row'
               ),
            TR(
               TH('Interview', _class='text-muted cell-label'),
               TD(appinterviews,
                  _id='interview-cell-{0}'.format(application_id),
                  _class='interview-cell'
                  )
               ),
            TR(
               TH('Applied On', _class='text-muted cell-label'),
               TD(appdata['application_date_applied']),
               ),
            TR(
               TH('Attachments', _class='text-muted cell-label'),
               attachments_td,
               _class='applicant-attachments'
               ),
            TR(
               TH('Links', _class='text-muted cell-label'),
               TD(
                  iconLink(appdata['applicant_reel']),
                  iconLink(appdata['applicant_linkedin'], 'linkedin'),
                  iconLink(appdata['applicant_imdb'], 'imdb'),
                  _class='applicant-links'
                  )
               ),
            TR(
               TH('reel info', _class='text-muted cell-label'),
               TD(appdata['applicant_reel_detail'],
                  _class='applicant-reeldetail'
                  ),
               _class='sub-row'
               ),
            TR(
               TH('Contact', _class='text-muted cell-label'),
               TD(
                  A(appdata['applicant_email'], _href='mailto:{0}'.format(appdata['applicant_email'])),
                  BR(),
                  appdata['applicant_phone'],
                  )
               ),
            TR(
               TH('VISA', _class='text-muted cell-label'),
               TD('from {0}'.format(appdata['applicant_country']),
                  BR(),
                  appdata['visa_status'],
                  )
               ),
            TR(
               TH('How?', _class='text-muted cell-label'),
               TD(appdata['hearsay_name'],
                  BR(),
                  appdata['applicant_hearsay_detail'],
                  _class='mcwrap'
                  )
               ),
            TR(
               TH('All Apps', _class='text-muted cell-label'),
               TD(applinks,
                  **{'_id': 'app-list-{0}'.format(application_id),
                     '_class': 'app-list',
                     '_data-application': application_id
                     }
                  )
               ),
            ]
    
    # info
    thead = THEAD(TR(TH(_class='empty-th col-sm-2'), TH(_class='empty-th col-sm-10')))
    info_table = DIV(
                     TABLE(thead, *rows, _class='table table-condensed tab-table'),
                     _class='table-responsive'
                     )
    left_col = DIV(info_table, _class='col-md-6 col-lg-5')
    
    # comments
    right_col = DIV(commentsForm(application_id),
                    _class='col-md-6 col-lg-7'
                    )
    
    result = DIV(left_col, right_col, _class='row')
    return result

def tabContentTemplate():
    """Return detail tab template
    """
    rows = [
            TR(
               TH('This App', _class='text-muted cell-label'),
               TD(
                  BUTTON('Bookmark',
                         **{'_class': 'btn btn-inverse btn-xs bookmarker',
                            '_data-applicationid': 'APPLICATION_ID',
                            '_data-name': 'APPLICANT_NAME',
                            '_data-position': 'POSTING_TITLE',
                            '_data-status': 'STATUS_NAME'
                            }
                         ),
                  A(
                    SPAN(_class='fa fa-link'),
                    ' link to this ',
                    _href='http://{0}/{1}#application-APPLICATION_ID'.format(request.env.http_host, request.application)
                    ),
                  SPAN('#APPLICATION_ID', _class='app-number text-muted pull-right'),
                  )
               ),
            TR(
               TH('Status', _class='text-muted cell-label input-label'),
               TD('STATUS_SELECT')
               ),
            TR(
               TH('Schedule', _class='text-muted cell-label input-label'),
               TD(
                  DIV(
                      INPUT(_class='form-control input-sm interview-date', _type='text'),
                      DIV(
                          BUTTON('Set', _class='btn btn-sm btn-default interview-set'),
                          BUTTON('Cancel', _class='btn btn-sm btn-default interview-cancel'),
                          **{'_class': 'input-group-btn',
                             '_data-applicationid': 'APPLICATION_ID'
                             }
                          ),
                      _class='input-group'
                      )
                  ),
               _id='interview-APPLICATION_ID',
               _class='hidden-input-row'
               ),
            TR(
               TH('Interview', _class='text-muted cell-label'),
               TD(
                  I(_class='fa fa-spin fa-refresh'),
                  _id='interview-cell-APPLICATION_ID',
                  _class='interview-cell'
                  )
               ),
            TR(
               TH('Applied On', _class='text-muted cell-label'),
               TD('APPLICATION_DATE_APPLIED'),
               ),
            TR(
               TH('Attachments', _class='text-muted cell-label'),
               TD(_class='applicant-attachments'),
               ),
            TR(
               TH('Links', _class='text-muted cell-label'),
               TD(_class='applicant-links')
               ),
            TR(
               TH('reel info', _class='text-muted cell-label'),
               TD(_class='applicant-reeldetail'),
               _class='sub-row'
               ),
            TR(
               TH('Contact', _class='text-muted cell-label'),
               TD(
                  A('APPLICANT_EMAIL', _href='mailto:APPLICANT_EMAIL'),
                  BR(),
                  'APPLICANT_PHONE',
                  )
               ),
            TR(
               TH('VISA', _class='text-muted cell-label'),
               TD('from APPLICANT_COUNTRY',
                  BR(),
                  'VISA_STATUS'
                  )
               ),
            TR(
               TH('How?', _class='text-muted cell-label'),
               TD('HEARSAY_NAME',
                  BR(),
                  'APPLICANT_HEARSAY_DETAIL',
                  _class='mcwrap'
                  )
               ),
            TR(
               TH('All Apps', _class='text-muted cell-label'),
               TD(
                  I(_class='fa fa-spin fa-refresh'),
                  **{'_id': 'app-list-APPLICATION_ID',
                     '_class':'app-list',
                     '_data-application': 'APPLICATION_ID'
                     }
                  )
               ),
            ]
    
    # info
    thead = THEAD(TR(TH(_class='empty-th col-sm-2'), TH(_class='empty-th col-sm-10')))
    info_table = DIV(
                     TABLE(thead, *rows, _class='table table-condensed tab-table'),
                     _class='table-responsive'
                     )
    left_col = DIV(info_table, _class='col-md-6 col-lg-5')
    # comments
    right_col = DIV(commentsForm(0, template=True), _class='col-md-6 col-lg-7')
    
    result = DIV(left_col, right_col, _class='row')
    return result
    
def getApplicationContent():
    """Return application data
    """
    tab_label = ''
    result = {}
    application_id = request.vars.id
    if application_id:
        query = (dbmrxcms.jobop_applicant.id==dbmrxcms.jobop_application.applicant_id) & \
                (dbmrxcms.jobop_applicant.visa_id==dbmrxcms.jobop_visa.id) & \
                (dbmrxcms.jobop_posting.id==dbmrxcms.jobop_application.posting_id) & \
                (dbmrxcms.jobop_posting.location_id==dbmrxcms.jobop_location.id) & \
                (dbmrxcms.jobop_category.id==dbmrxcms.jobop_posting.cat_id) & \
                (dbmrxcms.jobop_applicant.hearsay_id==dbmrxcms.jobop_hearsay.id) & \
                (dbmrxcms.jobop_status.id==dbmrxcms.jobop_application.status_id) & \
                (dbmrxcms.jobop_posting.archived==0) & \
                (dbmrxcms.jobop_application.id==application_id)
                
        row = dbmrxcms(query).select(dbmrxcms.jobop_interview.id,
                                 dbmrxcms.jobop_interview.xuser_id,
                                 dbmrxcms.jobop_interview.date,
                                 dbmrxcms.jobop_interview.interviewer,
                                 dbmrxcms.jobop_interview.done,
                                 dbmrxcms.jobop_application.date_applied,
                                 dbmrxcms.jobop_application.id,
                                 dbmrxcms.jobop_status.id,
                                 dbmrxcms.jobop_status.name,
                                 dbmrxcms.jobop_status.code,
                                 dbmrxcms.jobop_posting.id,
                                 dbmrxcms.jobop_posting.title,
                                 dbmrxcms.jobop_posting.visible,
                                 dbmrxcms.jobop_category.name,
                                 dbmrxcms.jobop_location.name,
                                 dbmrxcms.jobop_applicant.id,
                                 dbmrxcms.jobop_applicant.first_name,
                                 dbmrxcms.jobop_applicant.last_name,
                                 dbmrxcms.jobop_applicant.email,
                                 dbmrxcms.jobop_applicant.phone,
                                 dbmrxcms.jobop_applicant.cover_letter,
                                 dbmrxcms.jobop_applicant.cv_file,
                                 dbmrxcms.jobop_applicant.reel,
                                 dbmrxcms.jobop_applicant.reel_detail,
                                 dbmrxcms.jobop_applicant.imdb,
                                 dbmrxcms.jobop_applicant.linkedin,
                                 dbmrxcms.jobop_applicant.candidacy,
                                 dbmrxcms.jobop_applicant.country,
                                 dbmrxcms.jobop_applicant.hearsay_detail,
                                 dbmrxcms.jobop_hearsay.name,
                                 dbmrxcms.jobop_visa.status,
                                 dbmrxcms.jobop_visa.id,
                                 left=dbmrxcms.jobop_interview.on(dbmrxcms.jobop_interview.application_id==dbmrxcms.jobop_application.id),
                                 ).first()
        
        if row:
            if row.jobop_interview.date:
                interview_date = row.jobop_interview.date.strftime('%Y-%m-%d')
            else:
                interview_date = ''
                
            result = {'application_id': int(application_id),
                      'applicant_country': row.jobop_applicant.country,
                      'applicant_cover_letter': row.jobop_applicant.cover_letter,
                      'applicant_cv_file': row.jobop_applicant.cv_file,
                      'applicant_email': row.jobop_applicant.email,
                      'applicant_first_name': '{0} {1}'.format(row.jobop_applicant.first_name, row.jobop_applicant.last_name).title(),
                      'applicant_hearsay_detail': row.jobop_applicant.hearsay_detail,
                      'applicant_id': row.jobop_applicant.id,
                      'applicant_imdb': row.jobop_applicant.imdb,
                      'applicant_linkedin': row.jobop_applicant.linkedin,
                      'applicant_phone': row.jobop_applicant.phone,
                      'applicant_reel': row.jobop_applicant.reel,
                      'applicant_reel_detail': row.jobop_applicant.reel_detail or '',
                      'application_date_applied': row.jobop_application.date_applied.strftime(TIME_FORMAT).capitalize(),
                      'hearsay_name': row.jobop_hearsay.name,
                      'interview_date': interview_date,
                      'interview_done': row.jobop_interview.done,
                      'interview_id': row.jobop_interview.id or '',
                      'interview_interviewer': row.jobop_interview.interviewer or '',
                      'interview_xuser_id': row.jobop_interview.xuser_id or '',
                      'location_name': row.jobop_location.name,
                      'posting_title': row.jobop_posting.title,
                      'posting_visible': row.jobop_posting.visible,
                      'status_id': row.jobop_status.id,
                      'status_name': row.jobop_status.name,
                      'visa_id': row.jobop_visa.id,
                      'visa_status': row.jobop_visa.status,
                      'future': 1 if row.jobop_posting.visible==0 else 0,
                      }
            # tab label
            if row.jobop_location.name == 'Toronto':
                loc_badge = SPAN('T', _class='studio-tag label label-primary').xml()
            elif row.jobop_location.name == 'New York':
                loc_badge = SPAN('N', _class='studio-tag label label-danger').xml()
            else:
                loc_badge = SPAN('L', _class='studio-tag label label-warning').xml()
            tab_label = '{0}<strong>{1} {2}</strong> / {3}'.format(loc_badge, row.jobop_applicant.first_name, row.jobop_applicant.last_name, row.jobop_posting.title)
            
    data  = {'content': tabContent(result).xml(),
             'label': tab_label,
             'future': result['future'],
             }
    
    return simplejson.dumps(data)

def buildTable(dataset, id='result', xcols=[], links={}):
    """Return table from data
    """
    hide_bad = not (auth.has_membership("admin") or auth.has_membership("hr"))
    
    ths = [TH('Applicant', **{'_data-priority':'critical'}),
           TH('Status', **{'_class':'resizable-false', '_data-priority':'2'}),
           TH('Position', **{'_class':'', '_data-priority':'critical'}),
           TH('Studio', **{'_class':'resizable-false', '_data-priority':'3'}),
           TH('Cover', **{'_class':'onecol resizable-false', '_data-priority':'6'}),
           TH('CV', **{'_class':'onecol resizable-false', '_data-priority':'6'}),
           TH('Reel', **{'_data-priority':'7'}),
           TH('Applied On', **{'_class':'resizable-false', '_data-priority':'4'}),
           TH('VISA', **{'_class':'onecol resizable-false', '_data-priority':'5'}),
           TH('Country', **{'_class':'resizable-false', '_data-priority':'8'}),
           TH('How', **{'_class':'resizable-false', '_data-priority':'9'}),
           ]
    xths = set()
    
    rows = []
    for d in dataset:
        if d['jobop_interview.id'] and not d['jobop_interview.done']:
            interview_on = 1
            interview_icon = 'fa-check'
            interview_badge = 'label-badge label-success'
            interview_date = d['jobop_interview.date']
            if interview_date:
                interview_date = interview_date.strftime('%Y/%m/%d')
            interviewer = d['jobop_interview.interviewer']
        else:
            interview_on = 0
            interview_icon = 'fa-ban'
            interview_badge = 'label-badge label-default'
            interview_date = ''
            interviewer = ''
        interview_req = SPAN(
                             I(_class='fa fa-lg {0}'.format(interview_icon)),
                             _class='interview-marker label {0}'.format(interview_badge),
                             )
        
        status = d['jobop_status.name']
        date_applied = d['jobop_application.date_applied'].strftime(TIME_FORMAT).capitalize()
        date_applied_str = d['jobop_application.date_applied'].strftime('%a, %d %b %Y %I:%M %p')
        
        position = d['jobop_posting.title']
        
        studio = d['jobop_location.name']
        applicant = '{0} {1}'.format(d['jobop_applicant.first_name'], d['jobop_applicant.last_name']).title()
        
        reel_detail = ''
        if d['jobop_applicant.reel_detail']:
            reel_detail = d['jobop_applicant.reel_detail']
        
        reel_link = 'Not Required'
        if d['jobop_applicant.reel']:
            reel_link = []
            pathstr = d['jobop_applicant.reel']
            # deal with comma, AND
            rlinks = re.split('\s+and\s+|\s+&+s+|,(?i)', pathstr)
            for rlink in rlinks:
                rlink = rlink.strip()
                
                if rlink.startswith('http'):
                    anchor_head = ''
                else:
                    anchor_head = 'http://'
                
                rlink_str = rlink
                if len(rlink_str) > 39:
                    try:
                        rlink_str = rlink_str.split('/')[0]
                    except:
                        rlink_str = rlink_str[:39]
                if reel_link:
                    reel_link.append(BR())
                reel_link.append(A(rlink_str, _href='{0}{1}'.format(anchor_head, rlink), _target='_reel'))
                
        visa = visaDescription(d['jobop_visa.id'])
        nationality = d['jobop_applicant.country']
        hearsay = d['jobop_hearsay.name']
        hearsay_detail = textToHtml(d['jobop_applicant.hearsay_detail'])
        
        # cover letter file link
        if d['jobop_applicant.cover_letter']:
            coverletter_link = filelink(d['jobop_applicant.cover_letter'])
        else:
            coverletter_link = I(_class='fa fa-times')
            
        # cv file link
        cv_link = filelink(d['jobop_applicant.cv_file'])
        
        rowcls = ''
        if not d['jobop_applicant.candidacy']:
            if hide_bad:
                continue
            rowcls = 'danger'
        
        cols = [TD(applicant), # first name + last name
                TD(status), #interview flag
                TD(position), # posting title
                TD(studio), # studio
                TD(coverletter_link, _class='text-center'), # cover letter link
                TD(cv_link, _class='text-center'), # cv link
                TD(reel_link, **{'_data-detail':reel_detail}), # reel url
                TD(date_applied), # date applied
                TD(visa), # visa status
                TD(nationality), # country of residence
                TD(hearsay, **{'_data-detail':hearsay_detail}),
                ]
        
        for x in xcols:
            field, label, pos = x
            try:
                v = d[field]
                if v:
                    if isinstance(v, date):
                        v = v.strftime('%b %d %Y')
                    xths.add((label,pos))
                    if len(cols) < pos:
                        cols.append(TD(v))
                    else:
                        cols.insert(pos, TD(v))
            except Exception:
                pass
            
        tooltip = ''
        # if posting is invisible, future consideration
        if d['jobop_posting.visible'] == 0:
            rowcls += ' future'
            tooltip = 'Future consideration'
        
        # color by status
        if status == 'Make Offer':
            rowcls += ' offer'
        
        aa = links.get(d['jobop_applicant.id'],'')
        
        rows.append(TR(cols,
                       **{'_id': 'application-%d' %d['jobop_application.id'],
                          '_class': rowcls,
                          '_data-applicantid': d['jobop_applicant.id'],
                          '_data-postingid': d['jobop_posting.id'],
                          '_data-datetime': date_applied_str,
                          '_data-email': d['jobop_applicant.email'],
                          '_data-phone': d['jobop_applicant.phone'],
                          '_data-idate': interview_date,
                          '_data-status': d['jobop_status.id'],
                          '_data-statuscode': d['jobop_status.code'],
                          '_data-interview': interview_on,
                          '_data-interviewer': d['jobop_interview.interviewer'],
                          '_data-iid': d['jobop_interview.id'],
                          '_data-xuser': d['jobop_interview.xuser_id'],
                          '_data-visa': d['jobop_visa.status'],
                          '_data-allapps': aa,
                          '_data-imdb': d['jobop_applicant.imdb'],
                          '_data-linkedin': d['jobop_applicant.linkedin'],
                          '_title': tooltip,
                          }
                       ))
    
    for x in xths:
        if len(ths) < x[1]:
            ths.append(TH(x[0]))
        else:
            ths.insert(x[1], TH(x[0]))
            
    thead = THEAD(TR(ths))
    table = TABLE(thead, TBODY(rows), _id=id, _class='tablesorter')
    return table

def iconLink(link, type='reel', fortable=False):
    """Return icon link for web link
    """
    if fortable:
        reel_cls = 'fa fa-external-link'
        tooltip = ''
    else:
        reel_cls = 'fa fa-external-link-square fa-lg'
        tooltip = 'Reel'
    
    if link:
        if not link.startswith('http'):
            link = 'http://{0}'.format(link)
        
        if type == 'reel':
            # could be multiple links
            if (link.find(',') > -1):
                tmp = map(lambda x:x.strip(), link.split(','))
                a = SPAN([A(I(_class=reel_cls),_href=t,_class='inline-icon',_title=tooltip,_target='_link') for t in tmp])
            else:
                tmp = re.split('(https?://)', link)[1:]
                if len(tmp) > 3:
                    anchors = [tmp[i]+tmp[i+1] for i in range(0,len(tmp),2)]
                    z = [A(I(_class=reel_cls),_href=c,_class='inline-icon',_title=tooltip,_target='_link') for c in anchors]
                    z.append(I(''))
                    a = SPAN(z)
                else:
                    a = A(I(_class=reel_cls), _href=link, _class='inline-icon', _title=tooltip, _target='_link')
                    
        elif type == 'imdb':
            a = A(I(_class='fa fa-video-camera fa-lg'), _href=link, _class='inline-icon', _title='IMDB', _target='_link')
        elif type == 'linkedin':
            a = A(I(_class='fa fa-linkedin-square fa-lg'), _href=link, _class='inline-icon', _title='LinkedIn', _target='_link')
        
        if fortable:
            a = a.xml()
        return a
    return ''

def filelink(f, label=None, html=True):
    """Return icon link for file path
    """
    if f:
        _, ext = os.path.splitext(f)
        file_icon = 'fa-file-text-o text-black fa-lg'
        if ext in ['.doc', '.docx', '.rtf']:
            file_icon = 'fa-file-word-o text-blue fa-lg'
        elif ext in ['.pdf']:
            file_icon = 'fa-file-pdf-o text-red fa-lg'
            
        if not label:
            file_link = A(I(_class='fa fa-lg '+file_icon),
                          _href=URL('static', 'xproj/xrecruit/{0}'.format(os.path.basename(f))),
                          _target='_file'
                          )
        else:
            file_link = A(
                          I(_class='inline-icon fa '+file_icon),
                          ' '+label,
                          _href=URL('static', 'xproj/xrecruit/{0}'.format(os.path.basename(f))),
                          _target='_file'
                          )
    else:
        file_link = I(_class='fa fa-times')
    
    if html:
        return file_link.xml()
    return file_link

@auth.requires_login()
def statusSelect(status_id=None, application_id=None):
    """Build status select per user permission
    """
    if status_id and application_id:
        attrs = {'_id': 'status-{0}'.format(application_id),
                 '_class': 'form-control input-sm status-update',
                 '_data-org': status_id,
                 '_data-applicationid': application_id
                 }
    else:
        attrs = {'_id': 'status-APPLICATION_ID',
                 '_class': 'form-control input-sm status-update',
                 '_data-org': 'STATUS_ID',
                 '_data-applicationid': 'APPLICATION_ID'
                 }
    
    hr_perm = auth.has_membership('admin') or auth.has_membership('supe') or auth.has_membership('hr')
    
    # if hired, no more status update for PMs
    if status_id == 6 and not hr_perm:
        return SELECT(OPTION('Hired'), **attrs)
    
    status_opts = []
    rows = dbmrxcms().select(dbmrxcms.jobop_status.ALL, orderby=dbmrxcms.jobop_status.ordering)
    for s in rows:
        if hr_perm or s.id in PM_STATUS:
            if status_id and application_id:
                if s.id ==3 and status_id != 3 and not hr_perm:
                    continue
                parms = {'_value':s.id}
                if s.id == status_id:
                    parms['_selected'] = True
                opt = OPTION(s.name, **parms)
            else:
                opt = OPTION(s.name, _value=s.id)
            status_opts.append(opt)
            
    return SELECT(status_opts, **attrs)
    
@auth.requires_login()
def generateInterviewDataDiv(data=None, id=None):
    """
    """
    if id:
        data = dbmrxcms((dbmrxcms.jobop_interview.id==id) & \
                   (dbmrxcms.jobop_application.id==dbmrxcms.jobop_interview.application_id) & \
                   (dbmrxcms.jobop_posting.id==dbmrxcms.jobop_application.posting_id) & \
                   (dbmrxcms.jobop_location.id==dbmrxcms.jobop_posting.location_id)
                   ).select(dbmrxcms.jobop_application.id,dbmrxcms.jobop_interview.ALL,dbmrxcms.jobop_posting.title,dbmrxcms.jobop_location.name).first()
    if not data:
        return ''
    
    application_id = data['jobop_application.id']
    
    if not id:
        id = data['jobop_interview.id']
        
    if re.match('to(ronto)?', data['jobop_location.name'], re.I):
        loc = 'label-primary'
    else:
        loc = 'label-danger'
    
    if data['jobop_interview.interviewer']:
        interviewer = SPAN('by ', data['jobop_interview.interviewer'])
    else:
        interviewer = ''
    
    delete_btn = ''
    date_input = ''
    dcls = ''
    
    if auth.has_membership('admin') or auth.has_membership('supe') or auth.has_membership('hr'):
        delete_btn = SPAN(**{'_class': 'fa fa-times pull-right pointer interview-delete',
                             '_data-interviewid': id,
                             '_data-application': application_id,
                             '_title': 'Cancel interview'
                             })
        
        if date.today() <= data['jobop_interview.date']:
            date_input = INPUT(**{'_class': 'form-control input-sm date-edit',
                              '_value': data['jobop_interview.date'].strftime('%Y/%m/%d'),
                              '_data-interviewid': data['jobop_interview.id'],
                              }
                           )
            dcls = ' date-editor'
    
    # check if interview date passed
    if date.today() > data['jobop_interview.date']:
        icls = ' interview-complete'
    else:
        icls = ''
        
    div = DIV(
              SPAN(
                   SPAN(data['jobop_interview.date'].strftime('%b %d %Y'),
                        _class='date-display{0}'.format(dcls)
                        ),
                   date_input
                   ),
              SPAN(data['jobop_posting.title'], _class='interview-title'),
              SPAN(data['jobop_location.name'], _class='label label-as-badge {0}'.format(loc)),
              interviewer,
              delete_btn,
              **{'_id': 'interview-detail-{0}'.format(id),
                 '_class': 'interview-detail interview-{0}{1}'.format(application_id, icls),
                 }
              )
    return div

@auth.requires_login()
def interviewCreate():
    """Create Interview entry
    """
    appid = int(request.vars.application_id)
    idate = request.vars.date
    interviewer = request.vars.interviewer
    uid = auth.user.id
    updaterid = request.vars.updater
    uname = currentUser()
    
    ret = dbmrxcms.jobop_interview.insert(application_id=appid,
                                          xuser_id=uid,
                                          interviewer=interviewer,
                                          date=idate
                                          )
    
    logger.info("Update-Insert Interview Request - Application ({0}) by '{1}'".format(appid, uname))
    
    div = generateInterviewDataDiv(id=ret)
    if div:
        div = div.xml()
        # update status to Interview Pending
        ret = dbmrxcms(dbmrxcms.jobop_application.id==appid).update(status_id=3)
        
    msg = '{0} scheduled an Interview for <a href="#application-{1}" class="keyword applicant">%(applicant)s / <span class="position">%(position)s</span></a>'.format(uname, appid)
    if interviewer:
        msg += ' with {0}'.format(interviewer)
    
    d = datetime.strptime(idate, '%Y-%m-%d')
    data = {'id':ret,'date':idate.replace('-','/'),'datestr':d.strftime('%b %d %Y')}
    addXrecruitUpdate(appid, msg, updaterid, {'name':'interview-create','value':data})
    return simplejson.dumps({'content':div})

@auth.requires_login()
def interviewUpdate():
    """Change interview date
    """
    appid = int(request.vars.application_id)
    updaterid = request.vars.updater
    intid = int(request.vars.interview_id)
    intdate = request.vars.date
    
    ret = dbmrxcms(dbmrxcms.jobop_interview.id==intid).update(date=intdate)
    addXrecruitUpdate(appid, '', updaterid, {'name':'interview-update','value':{'id':intid,'date':intdate.replace('-','/')}})
    return simplejson.dumps(ret)
    
@auth.requires_login()
def interviewDelete():
    appid=  request.vars.application_id
    updaterid = request.vars.updater
    intid = request.vars.interview_id
    
    interview_data = dbmrxcms(dbmrxcms.jobop_interview.id==intid).select().first()
    if interview_data:
        application_id = interview_data.application_id
        dbmrxcms(dbmrxcms.jobop_interview.id==intid).delete()
        # change status to HOLD if no interviews found for application
        rows = dbmrxcms(dbmrxcms.jobop_interview.application_id==application_id).select()
        if not rows:
            ret = dbmrxcms(dbmrxcms.jobop_application.id==application_id).update(status_id=14)
            statusid = 14
            statusname = 'Hold'
        else:
            statusid = ''
            statusname = ''
        # update
        addXrecruitUpdate(appid, '', updaterid, {'name':'interview-delete','value':{'id':intid,'status':statusid,'statusname':statusname}})
        return simplejson.dumps({'msg':'deleted'})
    return simplejson.dumps({'msg':'no'})

@auth.requires_login()
def updateStatus():
    """Update appplication status
    """
    appid = int(request.vars.application_id)
    statusid = int(request.vars.status_id)
    updaterid = request.vars.updater
    
    uname = currentUser()
    ret = dbmrxcms(dbmrxcms.jobop_application.id==appid).update(status_id=statusid)
    logger.info("Update Status - Application ({0}) to Status ({1}) by '{2}'".format(appid, statusid, uname))
    
    # 3=interview pending
    if not statusid in [3]:
        # 9=interview complete
        if statusid == 9:
            addXrecruitUpdate(appid, '', updaterid, {'name':'interview-complete','value':{'id':9,'name':'Interview Complete'}})
        else:
            msg = '{0} updated <a href="#application-{1}" class="keyword applicant">%(applicant)s / <span class="position">%(position)s</span></a> status to <span class="keyword status">%(status)s</span>'.format(uname, appid)
            addXrecruitUpdate(appid, msg, updaterid, {'name':'status', 'value':{'id':statusid,'name':''}})
            
    # email notify - 2=Interview Request, 11=Make Offer, 11=Pass post-interview, 13=Offer Out
    if statusid in [2, 10, 11, 13]:
        # get application info
        row = dbmrxcms((dbmrxcms.jobop_applicant.id==dbmrxcms.jobop_application.applicant_id) & \
                       (dbmrxcms.jobop_posting.id==dbmrxcms.jobop_application.posting_id) & \
                       (dbmrxcms.jobop_location.id==dbmrxcms.jobop_posting.location_id) & \
                       (dbmrxcms.jobop_application.id==appid)).select(dbmrxcms.jobop_applicant.first_name,
                                                                      dbmrxcms.jobop_applicant.last_name,
                                                                      dbmrxcms.jobop_posting.id,
                                                                      dbmrxcms.jobop_posting.title,
                                                                      dbmrxcms.jobop_location.name,
                                                                      ).first()
        if row:
            studio = row['jobop_location.name'].lower()
            ilabel = '{0} {1}'.format(row['jobop_applicant.first_name'], row['jobop_applicant.last_name']).title()
            iname = A(ilabel, _target='_xrecruit', _href='http://{0}/{1}#application-{2}'.format(request.env.http_host, request.application, appid)).xml()
            recipients = None
            
            if 2 == statusid:
                subject = "Interview requested by {0} for {1} ({2})".format(uname, ilabel, row['jobop_posting.title'])
                msg = "<html><body><p>Interview requested by {0} for <strong>{1}</strong> ({2})</p>Application ID # {3}</body></html>".format(uname, iname, row['jobop_posting.title'], appid)
                if studio == 'toronto':
                    recipients = INTERVIEW_WATCHERS_TO
                else:
                    recipients = INTERVIEW_WATCHERS_NY
                    # check if request is from toronto
                    if re.match('to(ronto)?', auth.user.location, re.I):
                        recipients += INTERVIEW_WATCHERS_TO
                        
            elif 10 == statusid:
                subject = "Make Offer requested by {0} for {1} ({2})".format(uname, ilabel, row['jobop_posting.title'])
                msg = "<html><body><p>Make Offer requested by {0} for <strong>{1}</strong> ({2})</p>Application ID # {3}</body></html>".format(uname, iname, row['jobop_posting.title'], appid)
                if studio == 'toronto':
                    recipients = OFFER_REQUIRED_TO
                else:
                    recipients = OFFER_REQUIRED_NY
                    
            elif 11 == statusid:
                subject = "Pass Post-Interview by {0} for {1} ({2})".format(uname, ilabel, row['jobop_posting.title'])
                msg = "<html><body><p>{0} passed on <strong>{1}</strong> ({2}) post-interview.</p>Application ID # {3}</body></html>".format(uname, iname, row['jobop_posting.title'], appid)
                recipients = INTERVIEW_POST_PASS
            elif 13 == statusid:
                subject = "Offer made to {0} for position of {1}".format(ilabel, row['jobop_posting.title'])
                msg = "<html><body><p>Offer made to <strong>{0}</strong> for position of {1}</p>Application ID # {2}</body></html>".format(iname, row['jobop_posting.title'], appid)
                if studio == 'toronto':
                    recipients = set(OFFER_MADE_TO)
                else:
                    recipients = set(OFFER_MADE_NY)
                subscribers = dbmrxcms((dbmrxcms.xrecruit_watch_subscribe.posting_id==row['jobop_posting.id']) & \
                                       (dbmrxcms.xrecruit_watch_subscribe.watch_id==dbmrxcms.xrecruit_watch.id)
                                       ).select(dbmrxcms.xrecruit_watch.username)
                for s in subscribers:
                    recipients.add('{0}@mrxfx.com'.format(s.username))
                recipients = list(recipients)
            
            if recipients and appid not in [84,857]:
                notifyEmail(subject, msg, recipients, appid)
            else:
                logger.debug("Notification email not sent - no recipients")
                
    return response.json(ret)

def notifyEmail(subject, msg, recipients, appid=None):
    """Email when interview is requested INTERVIEW_WATCHERS_TO, INTERVIEW_WATCHERS_NY
    @param subejct: email subject string
    @param msg: email body string
    @param recipients: list of strings
    @param appid: application id integer
    """
    mailman(recipients, subject, msg)
    reps = ','.join(recipients)
    if appid:
        msg = "Notify Email To:[{0}] {1}".format(reps, subject)
    else:
        msg = "Notify Email {0} To:[{1}] {2}".format(appid, reps, subject)
    logger.info(msg)

def commentsForm(appid, template=False):
    """
    """
    if not template:
        comments = getCommentsServer(appid)
        if not comments:
            comments = [LI(SPAN('No comments', _class='text-muted'), _class='app-comment')]
    else:
        comments = [I(_class='fa fa-spin fa-refresh')]
        appid = 'APPLICATION_ID'
    
    form = DIV(
               DIV(
                   LABEL('Comments', _class='text-muted', _style='font-weight:300;'),
                   _style='margin-bottom:0'
                   ),
               DIV(
                   TEXTAREA(_id='commenter-text-{0}'.format(appid),
                            _class='form-control comment-input',
                            _rows=1
                            ),
                   _class='comments-wrapper'
                   ),
               DIV(
                   BUTTON('Post Comment',
                          **{'_class': 'btn btn-default btn-sm comment-submit',
                             '_data-application': appid
                             }
                          ),
                   DIV(
                       INPUT(
                             _id='commentcc-{0}'.format(appid),
                             _class='form-control input-sm sb-cc-input',
                             _placeholder='cc'
                             ),
                       SPAN(_class='fa fa-envelope-o fa-lg sb-icon-cc', _title='CC Email Comment'),
                       _class='pull-right sb-cc sb-cc-closed'
                       )
                   ),
               HR(),
               DIV(
                   UL(*comments,
                      _id='comments-list-{0}'.format(appid),
                      _class='comments'
                      )
                   ),
               _id='comment-{0}'.format(appid),
               _style='margin-top:1em;'
               )
    return form

@auth.requires_login()
def getCommentsServer(appid):
    """Return comments & replies for the application
    """
    
    if auth.has_membership('admin') or auth.has_membership('supe') or auth.has_membership('hr'):
        delete_btn = SPAN(_class='fa fa-times text-red delete-icon', _title='Delete')
    else:
        delete_btn = ''
    
    def li_comment(comment, reply=False, replies=[]):
        if not comment.content:
            return ''
        
        delete_icon = delete_btn
        
        if reply:
            cls = 'app-reply'
            text_cls = 'comment-text'
            reply_icon = ''
            reply_ul = ''
            reply_input = ''
        else:
            cls = 'app-comment'
            reply_ul = UL(replies, _class='ul-reply')
            reply_input = DIV(
                              TEXTAREA(_class='form-control comment-input', _placeholder='reply to above comment', _rows=1),
                              BUTTON('Reply',
                                     **{'_class':'btn btn-primary btn-sm reply-submit',
                                        '_data-comment':comment.id,
                                        '_data-application':comment.application_id,
                                        }
                                     ),
                              _class='reply-input collapse',
                              )
            
            if comment.content == 'deleted comment':
                text_cls = 'comment-text deleted-comment'
                reply_icon = ''
                delete_icon = ''
            else:
                text_cls = 'comment-text'
                reply_icon = SPAN(_class='fa fa-reply reply-icon', _title='Reply')
            
        content = SPAN(
                       XML(comment.content.replace('\n', '<br>')),
                       _class=text_cls
                       )
        
        return LI(
                  DIV(
                      DIV(SPAN(comment.username, _class='text-muted'),
                          SPAN(SMALL(comment.date_added.strftime(TIME_FORMAT).capitalize(), _class='text-italic'), _class='text-muted date-span'),
                          ),
                      P(content, reply_icon, delete_icon, _class='comment-body'),
                      _class='comment-container',
                      ),
                  reply_input,
                  reply_ul,
                  _class=cls,
                  _id='comment-%d' %comment.id
                  )
        
    def get_replies(pid, replies):
        filtered = filter(lambda x:x.parent_id==pid, replies)
        result = []
        for r in filtered:
            li = li_comment(r, reply=True)
            result.append(li)
        return result
    
    comments = dbmrxcms((dbmrxcms.jobop_comment.application_id==appid)&(dbmrxcms.jobop_comment.parent_id==None)).select(orderby=~dbmrxcms.jobop_comment.date_added)
    replies = dbmrxcms((dbmrxcms.jobop_comment.application_id==appid)&(dbmrxcms.jobop_comment.parent_id!=None)).select(orderby=dbmrxcms.jobop_comment.date_added)
    
    result = []
    for comment in comments:
        creplies = get_replies(comment.id, replies)
        li = li_comment(comment, replies=creplies)
        if li:
            result.append(li)
    return result

@auth.requires_login()
def getComments():
    """Return comments & replies for the application
    """
    if auth.has_membership('admin') or auth.has_membership('supe') or auth.has_membership('hr'):
        delete_btn = SPAN(_class='fa fa-times text-red delete-icon', _title='Delete')
    else:
        delete_btn = ''
    
    def li_comment(comment, reply=False, replies=[]):
        if not comment.content:
            return ''
        
        delete_icon = delete_btn
        
        if reply:
            cls = 'app-reply'
            text_cls = 'comment-text'
            reply_icon = ''
            reply_ul = ''
            reply_input = ''
        else:
            cls = 'app-comment'
            reply_ul = UL(replies, _class='ul-reply')
            reply_input = DIV(
                              TEXTAREA(_class='form-control comment-input', _placeholder='reply to above comment', _rows=1),
                              BUTTON('Reply',
                                     **{'_class':'btn btn-primary btn-sm reply-submit',
                                        '_data-comment':comment.id,
                                        '_data-application':comment.application_id,
                                        }
                                     ),
                              _class='reply-input collapse',
                              )
            
            if comment.content == 'deleted comment':
                text_cls = 'comment-text deleted-comment'
                reply_icon = ''
                delete_icon = ''
            else:
                text_cls = 'comment-text'
                reply_icon = SPAN(_class='fa fa-reply reply-icon', _title='Reply')
            
        content = SPAN(
                       XML(comment.content.replace('\n', '<br>')),
                       _class=text_cls
                       )
        
        return LI(
                  DIV(
                      DIV(SPAN(comment.username, _class='text-muted'),
                          SPAN(SMALL(comment.date_added.strftime(TIME_FORMAT).capitalize(), _class='text-italic'), _class='text-muted date-span'),
                          ),
                      P(content, reply_icon, delete_icon, _class='comment-body'),
                      _class='comment-container'
                      ),
                  reply_input,
                  reply_ul,
                  _class=cls,
                  _id='comment-%d' %comment.id
                  )
        
    def get_replies(pid, replies):
        filtered = filter(lambda x:x.parent_id==pid, replies)
        result = []
        for r in filtered:
            li = li_comment(r, reply=True)
            result.append(li)
        return result
    
    appid = int(request.vars.application_id)
    
    comments = dbmrxcms((dbmrxcms.jobop_comment.application_id==appid)&(dbmrxcms.jobop_comment.parent_id==None)).select(orderby=~dbmrxcms.jobop_comment.date_added)
    replies = dbmrxcms((dbmrxcms.jobop_comment.application_id==appid)&(dbmrxcms.jobop_comment.parent_id!=None)).select(orderby=dbmrxcms.jobop_comment.date_added)
    
    result = ''
    for comment in comments:
        creplies = get_replies(comment.id, replies)
        li = li_comment(comment, replies=creplies)
        if li:
            result += li.xml()
    
    if not result:
        result = LI(SPAN('No comments', _class='text-muted'), _class='app-comment').xml()
    return result

@auth.requires_login()
def removeComment():
    """Delete comment
    """
    application_id = request.vars.application_id
    updaterid = request.vars.updater
    try:
        commentid = int(request.vars.comment_id)
    except ValueError:
        logger.error('Error deleting Comment: invalid comment ID')
        return response.json(0)
    
    comment = dbmrxcms((dbmrxcms.jobop_comment.id==commentid)).select().first()
    if not comment:
        logger.error("Error deleting Comment: comment with ID {0} doesn't exist".format(commentid))
        return response.json(0)
    
    remove_li = 1
    if comment.parent_id:
        # reply
        dbmrxcms((dbmrxcms.jobop_comment.id==commentid)).delete()
        addXrecruitUpdate(application_id, '', updaterid, {'name':'reply-remove', 'value':commentid})
    else:
        # check if this comment has replies
        if dbmrxcms((dbmrxcms.jobop_comment.parent_id==commentid)).select():
            # has replies, leave a placeholder
            dbmrxcms((dbmrxcms.jobop_comment.id==commentid)).update(content='deleted comment')
            addXrecruitUpdate(application_id, '', updaterid, {'name':'comment-remove-empty', 'value':commentid})
            remove_li = 0
        else:
            # not replies, delete this comment
            dbmrxcms((dbmrxcms.jobop_comment.id==commentid)).delete()
            addXrecruitUpdate(application_id, '', updaterid, {'name':'comment-remove', 'value':commentid})
        
    return response.json({'remove':remove_li})

@auth.requires_login()
def emailComment(to, applink, apptitle, comment):
    """Email comment to users
    """
    if isinstance(to, str):
        to = [to]
    if to and comment:
        subject = '[xRecruit] {0} commented by {1} {2}'.format(apptitle, auth.user.first_name, auth.user.last_name)
        message = '<html><a href="{0}">{1}</a><p>{2}<p></html>'.format(applink, apptitle, comment)
        sender = '{0}@mrxfx.com'.format(auth.user.username)
        mailman(to, subject, message, sender)
        
@auth.requires_login()
def addComment():
    """Create comment for the application
    """
    try:
        appid = int(request.vars.application_id)
    except ValueError:
        logger.error('Error creating Comment: invalid application ID')
        return response.json(0)
    
    body = request.vars.content
    updaterid = request.vars.updater
    cc = request.vars['cc[]']
    appo = request.vars.apposition
    location = request.vars.location
    
    uname = currentUser()
    d = datetime.now()
    dstr = d.strftime('%Y-%m-%d %H:%M:%S')
    dhum = d.strftime(TIME_FORMAT).capitalize()
    ret = dbmrxcms.jobop_comment.insert(application_id=appid,
                                        username=uname,
                                        content=body,
                                        date_added=dstr
                                        )
    logger.info("Add Comment - Application ({0}) by '{1}'".format(appid, uname))
    
    if cc:
        applink = URL('index', scheme=True, host=True) + '#application-{0}'.format(appid)
        apptitle = '{0} {1}'.format(appo, location)
        emailComment(cc, applink, apptitle, body)
        
    msg = '{0} commented on <a href="#application-{1}" class="keyword applicant">%(applicant)s / <span class="position">%(position)s</span></a>'.format(uname, appid)
    
    comment_data = {'id':ret, 'content':body, 'poster':uname, 'date':dhum}
    addXrecruitUpdate(appid, msg, updaterid, {'name':'comment-add', 'value':comment_data})
    return response.json({'id':ret, 'poster':uname, 'date':dhum})

@auth.requires_login()
def addReply():
    """Create reply for comment
    """
    try:
        appid = int(request.vars.application_id)
    except ValueError:
        logger.error('Error creating Reply: invalid application ID')
        return response.json(0)
    try:
        commentid = int(request.vars.comment_id)
    except ValueError:
        logger.error('Error creating Reply: invalid comment ID')
        return response.json(0)
    body = request.vars.content
    updaterid = request.vars.updater
    cc = request.vars['cc[]']
    appo = request.vars.apposition
    location = request.vars.location
    
    uname = currentUser()
    d = datetime.now()
    dstr = d.strftime('%Y-%m-%d %H:%M:%S')
    dhum = d.strftime(TIME_FORMAT).capitalize()
    ret = dbmrxcms.jobop_comment.insert(application_id=appid,
                                        username=uname,
                                        content=body,
                                        date_added=dstr,
                                        parent_id=commentid
                                        )
    logger.info("Add Reply - Application ({0}), Comment ({1}) by '{2}'".format(appid, commentid, uname))
    '''
    # reply email disabled for now
    if cc:
        applink = URL('index', scheme=True, host=True) + '#application-{0}'.format(appid)
        apptitle = '{0} {1}'.format(appo, location)
        emailComment(cc, applink, apptitle, body)
    '''
    msg = '{0} replied to <a href="#application-{1}" class="keyword applicant">%(applicant)s / <span class="position">%(position)s</span></a>'.format(uname, appid)
    
    reply_data = {'id':ret, 'parent':commentid, 'content':body, 'poster':uname, 'date':dhum}
    addXrecruitUpdate(appid, msg, updaterid, {'name':'reply-add', 'value':reply_data})
    return response.json({'id':ret, 'poster':uname, 'date':dhum})

def savePreference():
    """Save user preference in cookie
    """
    #cookie_name = request.application
    cookie_name = 'xrecruit_filter'
    
    response.cookies[cookie_name] = simplejson.dumps(request.vars.filterval)
    response.cookies[cookie_name]['expires'] =  30 * 24 * 3600
    response.cookies[cookie_name]['path'] = '/'
    

def updateWatchlist():
    """Update user's watchlist (ignore, subscribe) - need page reload
    
    only checked values will pass (value == 'on')
    """
    ignore_new = set()
    subscribe_new = set()
    for k in request.vars.keys():
        type, id = k.split('_')
        if type == 'ignore':
            ignore_new.add(int(id))
        elif type == 'subscribe':
            subscribe_new.add(int(id))
            
    # get user's watchlist id
    watch = dbmrxcms(dbmrxcms.xrecruit_watch.username==auth.user.username).select().first()
    if watch:
        watchid = watch.id
        tmp = dbmrxcms((dbmrxcms.xrecruit_watch_ignore.watch_id==watchid)).select(dbmrxcms.xrecruit_watch_ignore.posting_id)
        ignore_cur = set([t.posting_id for t in tmp])
        
        tmp = dbmrxcms((dbmrxcms.xrecruit_watch_subscribe.watch_id==watchid)).select(dbmrxcms.xrecruit_watch_subscribe.posting_id)
        subscribe_cur = set([t.posting_id for t in tmp])
        
    else:
        watchid = dbmrxcms.xrecruit_watch.insert(username=auth.user.username)
        ignore_cur = set([])
        subscribe_cur = set([])
    
    # ignore list
    for i in list(ignore_new-ignore_cur):
        dbmrxcms.xrecruit_watch_ignore.insert(watch_id=watchid, posting_id=i)
    id = list(ignore_cur-ignore_new)
    if id:
        dbmrxcms((dbmrxcms.xrecruit_watch_ignore.watch_id==watchid)& \
                 (dbmrxcms.xrecruit_watch_ignore.posting_id.belongs(id))
                 ).delete()
    
    # subscribe list
    for i in list(subscribe_new-subscribe_cur):
        dbmrxcms.xrecruit_watch_subscribe.insert(watch_id=watchid, posting_id=i)
    wd = list(subscribe_cur-subscribe_new)
    if wd:
        dbmrxcms((dbmrxcms.xrecruit_watch_subscribe.watch_id==watchid)& \
                 (dbmrxcms.xrecruit_watch_subscribe.posting_id.belongs(wd))
                 ).delete()
    
    return ''

# BOOKMARK
@auth.requires_login()
def deleteBookmark():
    """Delete bookmark
    """
    dbmrxcms(dbmrxcms.xrecruit_bookmark.id==request.vars.id).delete()
    return ''

@auth.requires_login()
def newBookmark():
    """Create new Bookmark entry
    """
    name = request.vars.name
    application_ids = request.vars.appids
    if name and auth.user.username:
        fields = {'name':name, 'username':auth.user.username}
        if request.vars.has_key('appids'):
            fields['application_ids'] = request.vars.appids
        ret = dbmrxcms.xrecruit_bookmark.insert(**fields)
        return simplejson.dumps({'id':ret})
    return ''

def updateBookmark():
    """Update bookmark
    """
    bid = request.vars.id
    fields = {}
    if request.vars.has_key('appids'):
        fields['application_ids'] = request.vars.appids
    if request.vars.has_key('name'):
        fields['name'] = request.vars.name
    if fields:
        dbmrxcms(dbmrxcms.xrecruit_bookmark.id==bid).update(**fields)
    return ''

def importBookmarks():
    """Import bookmark
    """
    if not request.vars.has_key('bookmark'):
        redirect(URL('index'))
        
    row = dbmrxcms(dbmrxcms.xrecruit_bookmark.id==request.vars.bookmark).select().first()
    if row:
        # check name
        dupes = dbmrxcms(dbmrxcms.xrecruit_bookmark.name==row.name).select()
        if dupes:
            name = '{0}{1}'.format(row.name, len(dupes))
        else:
            name = row.name
        ret = dbmrxcms.xrecruit_bookmark.insert(name=name,
                                                username=auth.user.username,
                                                application_ids=row.application_ids
                                                )
    else:
        ret = ''
    redirect(URL('index'))
    return dict()


@auth.requires_login()
def exportSpreadsheet():
    """Export table as spreadsheet
    """
    include_interviews = request.vars.interviews == '1'
    
    columns = ['jobop_applicant.first_name',
               'jobop_status.name',
               'jobop_posting.title',
               'jobop_location.name',
               'jobop_applicant.reel',
               'jobop_application.date_applied',
               'jobop_applicant.email',
               'jobop_applicant.phone',
               'jobop_visa.status',
               'jobop_applicant.country',
               'jobop_hearsay.name',
               'jobop_applicant.hearsay_detail',
               'jobop_applicant.imdb',
               'jobop_applicant.linkedin',
               ]
    if include_interviews:
        columns.extend(['jobop_interview.date', 'jobop_interview.interviewer'])
    
    row_fields = [c.replace('jobop_','').replace('.','_') for c in columns]
    
    vars = {'draw':1,
            'order[0][column]':0,
            'order[0][dir]':'asc',
            'columns[0][data]':'applicant_first_name',
            'columns[0][name]':'jobop_applicant.first_name',
            'columns[0][searchable]':'true',
            'columns[0][orderable]':'true',
            }
    
    result = DataTablesServer(vars, columns, 'jobop_application.id', username=auth.user.username).output_result()
    
    link = ''
    
    if result['data']:
        book = xlwt.Workbook(encoding='utf-8')
        sheet = book.add_sheet('job applications')
        
        # headers
        sheet_data = ['Applicant',
                      'Status',
                      'Position',
                      'Studio',
                      'Reel',
                      'Date Applied',
                      'Email',
                      'Phone',
                      'Visa Status',
                      'Country',
                      'How',
                      'How Detail',
                      'IMDB',
                      'LinkedIn',
                      ]
        if include_interviews:
            sheet_data.extend(['Interview Date', 'Interviewed By'])
            
        for c, sd in enumerate(sheet_data):
            sheet.write(0, c, sd)
        
        for num_row, row in enumerate(result['data']):
            row_data = []
            for r in row_fields:
                if r == 'application_date_applied':
                    v = datetime.strptime(row['application_date_applied'], TIME_FORMAT).strftime('%Y-%m-%d')
                else:
                    v = row[r]
                row_data.append(v)
            
            for num_col, col in enumerate(row_data):
                sheet.write(num_row+1, num_col, col)
                
        filepath = "/tmp/mrxjobs_{0}.xls".format(datetime.today().strftime('%y%m%d%H%M%S'))
        book.save(filepath)
        link = URL('static', filepath)
        
    return link


def visaDescription(id):
    """Return visa status short description
    |  1 | Authorised to work in Canada             |
    |  2 | Authorised to work in the US             |
    |  3 | Require VISA to work in Canada           |
    |  4 | Require VISA to work in the US           |
    |  5 | Authorised to work in Canada and the US  |
    |  6 | Require VISA to work in Canada or the US |
    """
    if id == 1:
        msg = 'CAN'
    elif id == 2:
        msg = 'US'
    elif id == 3:
        msg = 'VISA'
    elif id == 4:
        msg = 'VISA'
    elif id == 5:
        msg = 'CAN/US'
    elif id == 6:
        msg = 'VISA'
    
    return msg

def getRecruiters():
    """Get users with access to XRecruit
    """
    group_id = [auth.id_group('admin'),
                auth.id_group('supe'),
                auth.id_group('hr'),
                auth.id_group('recruit')]
    recruiters = []
    for row in db((db.auth_membership.group_id.belongs(group_id))).select(db.auth_membership.user_id):
        recruiters.append(row.user_id)
    users = db(db.auth_user.id.belongs(recruiters)).select()
    return users

def getUsernames():
    """Return user names, id for autocomplete
    """
    pat = re.compile('(\w+)X([\d]*)')
    result = []
    val = request.vars.term
    if val:
        recruiters = getRecruiters()
        rows = db(((db.auth_user.first_name.contains(val)) |\
                  (db.auth_user.last_name.contains(val)) |\
                  (db.auth_user.username.contains(val))) &\
                  db.auth_user.id.belongs(recruiters)
                  ).select()
        
        for row in rows:
            result.append({'label':'{0} {1}'.format(row.first_name, row.last_name),
                           'value':'{0}@mrxfx.com'.format(row.username)})
    return simplejson.dumps(result)

@auth.requires_login()
def shareEmail():
    to = request.vars.emails.split(',')
    content = request.vars.content
    subject = '[XRecruit] {0} {1} shared bookmarks with you!'.format(auth.user.first_name, auth.user.last_name)
    if to and content:
        sender = '{0}@mrxfx.com'.format(auth.user.username)
        message = '<html><p>{0}<p></html>'.format(content)
        mailman(to, subject, message, sender)
    return ''

def mailman(to, subject, body, sender=None):
    """Email
    @param to: list of email addresses
    @param subject: email subject
    @param body: message
    @param sender: sender email address
    """
    if sender:
        mail.send(to=to, subject=subject, message=body, sender=sender)
    else:
        mail.send(to=to, subject=subject, message=body)
    logging.info('Mailed [{0}] for ({1})'.format(','.join(to), subject))
    
@auth.requires_login()
def applicationTable():
    """
    """
    columns = [
               'jobop_applicant.first_name',
               'jobop_status.name',
               'jobop_posting.title',
               'jobop_location.name',
               'jobop_applicant.cover_letter',
               'jobop_applicant.cv_file',
               'jobop_applicant.reel',
               'jobop_application.date_applied',
               'jobop_visa.id',
               'jobop_applicant.country',
               'jobop_hearsay.name',
               'jobop_applicant.reel_detail',
               'jobop_applicant.hearsay_detail',
               'jobop_applicant.imdb',
               'jobop_applicant.linkedin',
               'jobop_applicant.email',
               'jobop_applicant.phone',
               'jobop_visa.status',
               'jobop_status.id',
               'jobop_applicant.id',
               'jobop_posting.visible',
               'jobop_interview.id',
               'jobop_interview.date',
               'jobop_interview.interviewer',
               'jobop_interview.done',
               'jobop_interview.xuser_id',
               'COUNT(jobop_comment.id)',
               ]
    
    result = DataTablesServer(request.vars, columns, 'jobop_application.id', username=auth.user.username).output_result()
    #result = {'draw':0,'recordsTotal':0,'recordsFiltered':0,'data':[]}
    return simplejson.dumps(result)


class DataTablesServer:
    """Ajax data server for Datatables
    """
    def __init__( self, request, columns, index, collection='default', username=None):
        
        self.columns = columns
        self.index = index
        
        # table - element, branch, category, tag
        self.collection = collection
        
        # values specified by the datatable for filtering, sorting, paging
        self.request_values = request
        
        # results from the db
        self.result_data = None
         
        # total in the table after filtering
        self.cardinality_filtered = 0
        
        # total in the table unfiltered
        self.cadinality = 0
        
        if username:
            ignore_query = dbmrxcms((dbmrxcms.xrecruit_watch.username==auth.user.username) & \
                                    (dbmrxcms.xrecruit_watch_ignore.watch_id==dbmrxcms.xrecruit_watch.id)).select()
            self.ignore_ids = [i.xrecruit_watch_ignore.posting_id for i in ignore_query]
        else:
            self.ignore_ids = []
            
        self.run_queries()
        
    def run_queries(self):
        """
        """
        #db = current.db
        
        # pages has 'start' and 'length' attributes
        pages = self.paging()
        
        # the term you entered into the datatable search
        filtering = self.filtering()
        
        # the document field you chose to sort
        sorting = self.sorting()
        
        limit = (pages['start'], pages['start'] + pages['length'])
        
        if self.collection == 'default':
            query = (dbmrxcms.jobop_applicant.id==dbmrxcms.jobop_application.applicant_id) & \
                    (dbmrxcms.jobop_applicant.visa_id==dbmrxcms.jobop_visa.id) & \
                    (dbmrxcms.jobop_posting.id==dbmrxcms.jobop_application.posting_id) & \
                    (dbmrxcms.jobop_posting.location_id==dbmrxcms.jobop_location.id) & \
                    (dbmrxcms.jobop_category.id==dbmrxcms.jobop_posting.cat_id) & \
                    (dbmrxcms.jobop_applicant.hearsay_id==dbmrxcms.jobop_hearsay.id) & \
                    (dbmrxcms.jobop_status.id==dbmrxcms.jobop_application.status_id) & \
                    (dbmrxcms.jobop_posting.archived==0) & \
                    ~(dbmrxcms.jobop_posting.id.belongs(self.ignore_ids))
                    
            if filtering['or']:
                query &= filtering['or']
            
            self.cardinality_filtered = dbmrxcms(query).count()
            
            # counting comments
            comment_count = dbmrxcms.jobop_comment.id.count()
            
            # left join interview
            if limit[1] > 0:
                rows = dbmrxcms(query).select(
                                              dbmrxcms.jobop_applicant.ALL,
                                              dbmrxcms.jobop_application.ALL,
                                              dbmrxcms.jobop_posting.ALL,
                                              dbmrxcms.jobop_location.ALL,
                                              dbmrxcms.jobop_status.ALL,
                                              dbmrxcms.jobop_visa.ALL,
                                              dbmrxcms.jobop_hearsay.ALL,
                                              dbmrxcms.jobop_interview.ALL,
                                              comment_count,
                                              left=[dbmrxcms.jobop_interview.on(dbmrxcms.jobop_interview.application_id==dbmrxcms.jobop_application.id),
                                                    dbmrxcms.jobop_comment.on(dbmrxcms.jobop_comment.application_id==dbmrxcms.jobop_application.id),
                                                    ],
                                              groupby=dbmrxcms.jobop_application.id,
                                              limitby=limit,
                                              orderby=sorting
                                              )
            else:
                rows = dbmrxcms(query).select(
                                              dbmrxcms.jobop_applicant.ALL,
                                              dbmrxcms.jobop_application.ALL,
                                              dbmrxcms.jobop_posting.ALL,
                                              dbmrxcms.jobop_location.ALL,
                                              dbmrxcms.jobop_status.ALL,
                                              dbmrxcms.jobop_visa.ALL,
                                              dbmrxcms.jobop_hearsay.ALL,
                                              dbmrxcms.jobop_interview.ALL,
                                              comment_count,
                                              left=[dbmrxcms.jobop_interview.on(dbmrxcms.jobop_interview.application_id==dbmrxcms.jobop_application.id),
                                                    dbmrxcms.jobop_comment.on(dbmrxcms.jobop_comment.application_id==dbmrxcms.jobop_application.id),
                                                    ],
                                              groupby=dbmrxcms.jobop_application.id,
                                              orderby=sorting
                                              )
        else:
            self.result_data = []
            self.cardinality_filtered = 0
            self.cardinality = 0
            return None
        
        self.result_data = rows.as_list()
        self.cardinality = len(self.result_data)
        
    def filtering(self):
        """
        """
        #db = current.db
        # build your filter spec
        filter = {'or':None, 'and':None}
        # the term put into search is logically concatenated with 'or' between all columns
        
        global_or_filter = None
        
        # GLOBAL search
        if self.request_values.has_key('search[value]'):
            g_search_val = self.request_values['search[value]']
            if g_search_val != '':
                for i in range( len(self.columns) ):
                    if self.request_values['columns[{0}][searchable]'.format(i)] == 'false':
                        continue
                    table_name, col_name = self.request_values['columns[{0}][name]'.format(i)].split('.')
                    if dbmrxcms[table_name][col_name].type in ['id', 'datetime']:
                        continue
                    
                    search_string = g_search_val.split()
                    try:
                        if global_or_filter:
                            global_or_filter |= dbmrxcms[table_name][col_name].contains(search_string, all=False)
                        else:
                            global_or_filter = dbmrxcms[table_name][col_name].contains(search_string, all=False)
                        
                        if table_name == 'jobop_applicant' and col_name == 'first_name':
                            global_or_filter |= dbmrxcms[table_name]['last_name'].contains(search_string, all=False)
                        
                    except SyntaxError, e:
                        logger.error(str(e) + ': [{0}][{1}] type:{2}'.format(table_name, col_name, dbmrxcms[table_name][col_name].type))
                        
                #filter['or'] = global_or_filter
        
        column_filters = []
        for i in range( len(self.columns) ):
            if not self.request_values.has_key('columns[{0}][search][value]'.format(i)):
                continue
            
            search_val = self.request_values['columns[{0}][search][value]'.format(i)]
            if self.request_values['columns[{0}][searchable]'.format(i)] == 'false' or search_val == '':
                continue
            
            vals = []
            nots = []
            for x in search_val.split(','):
                if x.startswith('-'):
                    nots.append(x[1:].strip())
                else:
                    vals.append(x.strip())
            
            table_name, col_name = self.request_values['columns[{0}][name]'.format(i)].split('.')
            
            column_or_filter = None
            
            if col_name == 'date_applied':
                if search_val and search_val != '|':
                    dstart = None
                    dend = None
                    fmts = ['%Y-%m-%d', '%m-%d-%Y', '%Y/%m/%d', '%m/%d/%Y']
                    for fmt in fmts:
                        try:
                            dstart, dend = map(lambda x:datetime.strptime(x, fmt), search_val.split('|'))
                            break
                        except ValueError, e:
                            pass
                    
                    if dstart and dend:
                        if column_or_filter:
                            if dstart == dend:
                                # HACK since we can't compare just the date of datetime field, change datestart to 1 sec before midnight of previous day, dateend to midnight next day 
                                dstart = (dstart - timedelta(days=1)).replace(hour=23,minute=59,second=59)
                                dend = (dend + timedelta(days=1)).replace(hour=0,minute=0,second=0)
                            column_or_filter |= (dbmrxcms[table_name][col_name] >= dstart) & (dbmrxcms[table_name][col_name] <= dend)
                        else:
                            if dstart == dend:
                                dstart = (dstart - timedelta(days=1)).replace(hour=23,minute=59,second=59)
                                dend = (dend + timedelta(days=1)).replace(hour=0,minute=0,second=0)
                            column_or_filter = (dbmrxcms[table_name][col_name] >= dstart) & (dbmrxcms[table_name][col_name] <= dend)
                    else:
                        logger.warning('Incorrect date format used for dt filtering: {0}'.format(search_val))
                else:
                    logger.debug("Null values ignored for date filter")
                    
            elif col_name in ['name', 'title']:
                if table_name in ['jobop_status','jobop_location','jobop_visa','jobop_hearsay']:
                    col_name = 'id'
                
                for v in vals:
                    if column_or_filter:
                        column_or_filter |= dbmrxcms[table_name][col_name] == v
                    else:
                        column_or_filter = dbmrxcms[table_name][col_name] == v
                
                if nots:
                    if column_or_filter:
                        column_or_filter &= ~dbmrxcms[table_name][col_name].belongs(nots)
                    else:
                        column_or_filter = ~dbmrxcms[table_name][col_name].belongs(nots)
                
            else:
                for v in vals:
                    x = '%{0}%'.format(v)
                    if column_or_filter:
                        column_or_filter |= dbmrxcms[table_name][col_name].like(x)
                    else:
                        column_or_filter = dbmrxcms[table_name][col_name].like(x)
                
                for n in nots:
                    x = '%{0}%'.format(v)
                    if column_or_filter:
                        column_or_filter &= ~dbmrxcms[table_name][col_name].like(x)
                    else:
                        column_or_filter = ~dbmrxcms[table_name][col_name].like(x)
                        
            if column_or_filter:
                column_filters.append(column_or_filter)
            
        
        z = None
        for f in column_filters:
            if not z:
                z = f
            else:
                z &= f
        
        if global_or_filter:
            if z:
                z &= global_or_filter
            else:
                z = global_or_filter
            
        filter['or'] = z
        return filter
        
    def sorting(self):
        """
        """
        #db = current.db
        
        ordering = None
        
        if self.request_values.has_key('order[0][column]'):
            
            if (self.request_values['order[0][column]'] > -1):
                for i in range(len(self.columns)):
                    if not self.request_values.has_key('order[{0}][column]'.format(i)):
                        break
                        
                    order_col = int(self.request_values['order[{0}][column]'.format(i)])
                    order_dir = self.request_values['order[{0}][dir]'.format(i)]
                    
                    if self.request_values['columns[{0}][orderable]'.format(order_col)] == 'false':
                        continue
                        
                    if self.request_values['columns[{0}][name]'.format(order_col)].startswith('COUNT('):
                        col_name = self.request_values['columns[{0}][name]'.format(order_col)]
                        if ordering:
                            if order_dir == 'asc':
                                ordering |= col_name
                            else:
                                ordering |= '~'+col_name
                        else:
                            if order_dir == 'asc':
                                ordering = col_name
                            else:
                                ordering = '~'+col_name
                                
                    else:
                        table_name, col_name = self.request_values['columns[{0}][name]'.format(order_col)].split('.')
                        
                        if ordering:
                            if order_dir == 'asc':
                                ordering |= dbmrxcms[table_name][col_name]
                            else:
                                ordering |= ~dbmrxcms[table_name][col_name]
                        else:
                            if order_dir == 'asc':
                                ordering = dbmrxcms[table_name][col_name]
                            else:
                                ordering = ~dbmrxcms[table_name][col_name]
                                
        return ordering
        
    def paging(self):
        """
        """
        pages = {'start':0, 'length':0}
        
        if self.request_values.has_key('start'):
            if (self.request_values['start'] != "" ) and (self.request_values['length'] != -1 ):
                pages['start'] = int(self.request_values['start'])
                pages['length'] = int(self.request_values['length'])
                
        return pages
        
    def output_result(self):
        """DT_RowId
        """
        output = {}
        output['draw'] = int(self.request_values['draw'])
        output['recordsTotal'] = self.cardinality
        output['recordsFiltered'] = self.cardinality_filtered
        
        checkbox = '<input type="checkbox" class="dt-checkbox row-checkbox">'
        
        data = []
        
        for row in self.result_data:
            x = self.index.split('.')
            aaData_row = {'DT_RowId':row[x[0]][x[1]]}
            
            for i in range( len(self.columns) ):
                column = self.columns[i].replace('jobop_','').replace('.','_')
                
                if column == 'checkbox':
                    aaData_row[column] = checkbox
                    continue
                
                if self.columns[i].startswith('COUNT('):
                    column = 'count'
                    t = '_extra'
                    c = self.columns[i]
                else:
                    t, c = self.columns[i].split('.') # xelements_element.name
                
                if t == 'jobop_applicant' and c == 'first_name':
                    val = '{0} {1}'.format(row[t]['first_name'], row[t]['last_name']).title()
                elif t == 'jobop_visa' and c == 'id':
                    val = visaDescription(row['jobop_visa']['id'])
                elif c in ['cv_file', 'cover_letter']:
                    val = filelink(row[t][c])
                elif c == 'reel':
                    val = iconLink(row[t][c], fortable=True)
                else:
                    val = row[t][c]
                    
                if hasattr(val, 'isoformat'):
                    if column == 'interview_date':
                        val = val.strftime('%Y-%m-%d')
                    else:
                        val = val.strftime(TIME_FORMAT).capitalize()
                    
                aaData_row[column] = val
                
            data.append(aaData_row)
            
        output['data'] = data
        
        return output

"""
websocket
"""
def websocket_test():
    updaterid = request.vars.updater
    data = response.json({'type':'update', 'value':updaterid})
    websocket_send('http://{0}'.format(WEBSOCKET_IP), data, WEBSOCKET_KEY, WEBSOCKET_GROUP)

def getAppInfo(app_id, applicant=False):
    """Return Application title, location, status and Applicant name
    """
    if applicant:
        row = dbmrxcms(dbmrxcms.jobop_applicant.id==app_id).select(jobop_applicant.first_name,jobop_applicant.last_name).first()
        if row:
            return {'applicant': '{0} {1}'.format(row.jobop_applicant.first_name, row.jobop_applicant.last_name).title(),
                    'position': '',
                    'posting_id':'',
                    'status': '',
                    }
    else:
        row = dbmrxcms((dbmrxcms.jobop_applicant.id==dbmrxcms.jobop_application.applicant_id) & \
                        (dbmrxcms.jobop_posting.id==dbmrxcms.jobop_application.posting_id) & \
                        (dbmrxcms.jobop_posting.location_id==dbmrxcms.jobop_location.id) & \
                        (dbmrxcms.jobop_status.id==dbmrxcms.jobop_application.status_id) & \
                        (dbmrxcms.jobop_application.id==app_id)).select(
                            dbmrxcms.jobop_applicant.first_name,
                            dbmrxcms.jobop_applicant.last_name,
                            dbmrxcms.jobop_posting.id,
                            dbmrxcms.jobop_posting.title,
                            dbmrxcms.jobop_status.name,
                            dbmrxcms.jobop_location.name,).first()
        if row:
            return {'applicant': '{0} {1}'.format(row.jobop_applicant.first_name, row.jobop_applicant.last_name).title(),
                    'position': row.jobop_posting.title,
                    'posting_id': row.jobop_posting.id,
                    'status': row.jobop_status.name,
                    'location':row.jobop_location.name,
                    }
    return {'applicant':'','position':'','status':'','posting_id':'', 'location':''}

def addXrecruitUpdate(app_id, msg, updater_id, target, applicant=False):
    """Insert new update message and delete old one
    mrxcms u.submitApplication.php does this in raw SQL
    
    @param app_id: application id
    @param msg: message text with format strings
    @param updater: client who updated (uuid string)
    @param applicant: app_id is applicant id
    @return: dictionary
    """
    # skip test user
    #if app_id in [84, 857]:
    #    data = response.json({'type':'update', 'value':updater_id})
    #    return None
    
    if target['name'] not in ['comment-remove-empty', 'comment-remove', 'reply-remove', 'interview-delete', 'interview-update', 'interview-complete']:
        # delete excess old messages
        rows = dbmrxcms().select(dbmrxcms.xrecruit_update.ALL,orderby=dbmrxcms.xrecruit_update.id)
        
        old = [rows[i].id for i in range(len(rows)-MSGLIMIT)]
        dbmrxcms(dbmrxcms.xrecruit_update.id.belongs(old)).delete()
        
        info = getAppInfo(app_id, applicant)
        posting_id = info['posting_id']
        message = msg % info
        
        if target['name'] == 'interview-create':
            target['value']['position'] = info['position']
            target['value']['location'] = info['location']
            target['value']['loctag'] = 'primary' if info['location'] == 'Toronto' else 'danger'
            
        notice = DIV(
                     SPAN('{0} - '.format(datetime.now().strftime('%I:%M %p').lower()), _class='keyword'),
                     SPAN('MSG'),
                     SPAN(
                          A('[x]', _href='#', _class='dismiss'),
                          A(' [close all]', _href='#', _class='dismiss-all'),
                          _class='pull-right'
                          ),
                     _id='notify_warning',
                     _class='warning message'
                     )
        notice = XML(notice).replace('MSG', message)
        
        if target['name'] == 'status':
            target['value']['name'] = info['status']
        
        # debugging
        if app_id not in [84, 857]:
            # insert latest message
            ret = dbmrxcms.xrecruit_update.insert(application_id=app_id,
                                                  client=request.client,
                                                  content=message,
                                                  date_created=datetime.now()
                                                  )
            logger.debug('Added XrecruitMessage %d' %ret)
    else:
        posting_id = ''
        if not app_id:
            app_id = ''
        notice = ''
        
    if app_id in [84, 857]:
        return
    
    # broadcast via websocket
    data = response.json({'type':'update',
                          'value':updater_id,
                          'posting':posting_id,
                          'notify': XML(notice),
                          'applicationid':app_id,
                          'target':target['name'],
                          'targetdata':target['value'],
                          })
    # sleep for 5 seconds before broadcasting
    time.sleep(5)
    websocket_send('http://{0}'.format(WEBSOCKET_IP), data, WEBSOCKET_KEY, WEBSOCKET_GROUP)

def getXrecruitUpdate():
    """Return list of LI objects
    """
    now = datetime.now()
    result = []
    rows = dbmrxcms().select(dbmrxcms.xrecruit_update.ALL,orderby=dbmrxcms.xrecruit_update.id)
    for row in rows:
        if row.content:
            tstamp = exact_datetime(row.date_created)
            body = '{0} ~ {1}'.format(row.content,tstamp)
            result.append(LI(XML(body), _class='ticker-message'))
    if not result:
        result = [LI('Nothing to report', _class='ticker-message')]
    
    return result[::-1] # reverse

def update_ticker():
    tdata = getXrecruitUpdate()
    ticker = UL(*tdata, _id='ticker', _class='newsticker')
    return ticker.xml()

@auth.requires_login()
def currentUser():
    """Return currently logged in username + email
    """
    return '{0} {1}'.format(auth.user.first_name, auth.user.last_name).title()

def textToHtml(txt):
    return '<pre>{0}</pre>'.format(txt)

def exact_datetime(time=False):
    """Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    now = datetime.now()
    if type(time) is int:
        datetimeobj = datetime.fromtimestamp(time)
        diff = now - datetimeobj
    elif isinstance(time, datetime):
        diff = now - time
        datetimeobj = time
    elif not time:
        diff = now - now
        datetimeobj = now
        
    second_diff = diff.seconds
    day_diff = diff.days
    
    if day_diff < 0:
        return ""
    
    if day_diff == 0:
        if now.day == datetimeobj.day:
            return datetimeobj.strftime('%I:%m %p')
        else:
            return "Yesterday"
        
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return "{0} days ago".format(str(day_diff))
    if day_diff < 31:
        w = day_diff / 7
        s = 'weeks' if w > 1 else 'week'
        return "{0} {1} ago".format(str(w), s)
    if day_diff < 365:
        m = day_diff / 30
        s = 'months' if m > 1 else 'month'
        return "{0} {1} ago".format(str(m), s)
    
    y = day_diff / 365
    s = 'years' if y > 1 else 'year'
    return "{0} {1} ago".format(str(y), s)

def pretty_date(time=False):
    """Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    now = datetime.now()
    if type(time) is int:
        datetimeobj = datetime.fromtimestamp(time)
        diff = now - datetimeobj
    elif isinstance(time, datetime):
        diff = now - time
        datetimeobj = time
    elif not time:
        diff = now - now
        datetimeobj = now
        
    second_diff = diff.seconds
    day_diff = diff.days
    
    if day_diff < 0:
        return ''
    
    if day_diff == 0:
        if second_diff < 60:
            return "Just now"
        if second_diff < 120:
            return "A minute ago"
        if second_diff < 3600:
            return "{0} minutes ago".format(str(second_diff / 60))
        if second_diff < 7200:
            return "An hour ago"
        if second_diff < 86400:
            return "{0} hours ago".format(str(second_diff / 3600))
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return "{0} days ago".format(str(day_diff))
    if day_diff < 31:
        w = day_diff / 7
        s = 'weeks' if w > 1 else 'week'
        return "{0} {1} ago".format(str(w), s)
    if day_diff < 365:
        m = day_diff / 30
        s = 'months' if m > 1 else 'month'
        return "{0} {1} ago".format(str(m), s)
    
    y = day_diff / 365
    s = 'years' if y > 1 else 'year'
    return "{0} {1} ago".format(str(y), s)


"""
 default methods
"""

def user():
    """
    exposes:
    http://..../[app]/default/user/login
    http://..../[app]/default/user/logout
    http://..../[app]/default/user/register
    http://..../[app]/default/user/profile
    http://..../[app]/default/user/retrieve_password
    http://..../[app]/default/user/change_password
    use @auth.requires_login()
        @auth.requires_membership('group name')
        @auth.requires_permission('read','table name',record_id)
    to decorate functions that need access control
    """
    return dict(form=auth())

def download():
    """
    allows downloading of uploaded files
    http://..../[app]/default/download/[filename]
    """
    return response.download(request, db)

def call():
    """
    exposes services. for example:
    http://..../[app]/default/call/jsonrpc
    decorate with @services.jsonrpc the functions to expose
    supports xml, json, xmlrpc, jsonrpc, amfrpc, rss, csv
    """
    return service()

@auth.requires_signature()
def data():
    """
    http://..../[app]/default/data/tables
    http://..../[app]/default/data/create/[table]
    http://..../[app]/default/data/read/[table]/[id]
    http://..../[app]/default/data/update/[table]/[id]
    http://..../[app]/default/data/delete/[table]/[id]
    http://..../[app]/default/data/select/[table]
    http://..../[app]/default/data/search/[table]
    but URLs must be signed, i.e. linked with
      A('table',_href=URL('data/tables',user_signature=True))
    or with the signed load operator
      LOAD('default','data.load',args='tables',ajax=True,user_signature=True)
    """
    return dict(form=crud())
