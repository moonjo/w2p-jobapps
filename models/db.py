# -*- coding: utf-8 -*-
from MySQLdb.constants.FIELD_TYPE import VARCHAR, DATE

#########################################################################
## This scaffolding model makes your app work on Google App Engine too
## File is released under public domain and you can use without limitations
#########################################################################

## if SSL/HTTPS is properly configured and you want all HTTP requests to
## be redirected to HTTPS, uncomment the line below:
# request.requires_https()

if not request.env.web2py_runtime_gae:
    ## if NOT running on Google App Engine use SQLite or other DB
    db = DAL('sqlite://xrecruit.sqlite')
    dbmrxcms = DAL('sqlite://mrxcms.sqlite')
    #session.connect(request, response, db=db, masterapp='xhours')
else:
    ## connect to Google BigTable (optional 'google:datastore://namespace')
    db = DAL('google:datastore')
    ## store sessions and tickets there
    session.connect(request, response, db=db)
    ## or store session in Memcache, Redis, etc.
    ## from gluon.contrib.memdb import MEMDB
    ## from google.appengine.api.memcache import Client
    ## session.connect(request, response, db = MEMDB(Client()))

## by default give a view/generic.extension to all actions from localhost
## none otherwise. a pattern can be 'controller/function.extension'
response.generic_patterns = ['*'] if request.is_local else []
## (optional) optimize handling of static files
# response.optimize_css = 'concat,minify,inline'
# response.optimize_js = 'concat,minify,inline'

#########################################################################
## Here is sample code if you need for
## - email capabilities
## - authentication (registration, login, logout, ... )
## - authorization (role based authorization)
## - services (xml, csv, json, xmlrpc, jsonrpc, amf, rss)
## - old style crud actions
## (more options discussed in gluon/tools.py)
#########################################################################

from gluon.tools import Auth, Crud, Service, PluginManager, prettydate

auth = Auth(db, cas_provider=URL('xcas', 'default','user',args=['cas'],scheme=True,host=True))
crud, service, plugins = Crud(db), Service(), PluginManager()

## create all tables needed by auth if not custom tables
auth.settings.extra_fields['auth_user'] = [
    Field('location', length=25, default='Toronto'),
    ]
auth.define_tables(username=True, signature=False, migrate=False)

## configure email
mail = auth.settings.mailer
mail.settings.server = 'logging' or 'mail.com'
mail.settings.sender = 'systems@mail.com'
mail.settings.login = 'admin@pass'

## configure auth policy
auth.settings.registration_requires_verification = False
auth.settings.registration_requires_approval = False
auth.settings.reset_password_requires_verification = True

one_day = 3600 * 24
auth.settings.expiration = one_day # seconds * hours * days
auth.settings.long_expiration = one_day * 7 # seconds * hours * days
auth.settings.remember_me_form = True

## if you need to use OpenID, Facebook, MySpace, Twitter, Linkedin, etc.
## register with janrain.com, write your domain:api_key in private/janrain.key
from gluon.contrib.login_methods.rpx_account import use_janrain
use_janrain(auth, filename='private/janrain.key')

#########################################################################
## Define your tables below (or better in another model file) for example
##
## >>> db.define_table('mytable',Field('myfield','string'))
##
## Fields can be 'string','text','password','integer','double','boolean'
##       'date','time','datetime','blob','upload', 'reference TABLENAME'
## There is an implicit 'id integer autoincrement' field
## Consult manual for more options, validators, etc.
##
## More API examples for controllers:
##
## >>> db.mytable.insert(myfield='value')
## >>> rows=db(db.mytable.myfield=='value').select(db.mytable.ALL)
## >>> for row in rows: print row.id, row.myfield
#########################################################################

dbmrxcms.define_table('jobop_visa',
    Field('status', length=255),
    migrate=False)

dbmrxcms.define_table('jobop_category',
    Field('name', length=255),
    Field('visible', 'integer', default=1),
    migrate=False)

dbmrxcms.define_table('jobop_location',
    Field('code', length=24),
    Field('name', length=64),
    migrate=False)

dbmrxcms.define_table('jobop_status',
    Field('code', length=24),
    Field('name', length=64),
    Field('ordering', 'integer', default=0),
    migrate=False)

dbmrxcms.define_table('jobop_hearsay',
    Field('name', length=128),
    Field('visible', 'integer', default=1),
    migrate=False)

dbmrxcms.define_table('jobop_posting',
    Field('cat_id', dbmrxcms.jobop_category, label='Category', writable=False),
    Field('location_id', dbmrxcms.jobop_location, label='Location', writable=False),
    Field('title', length=255),
    Field('description', length=255),
    Field('date_posted', 'datetime'),
    Field('reel_required', 'integer', default=1),
    Field('visible', 'integer', default=1),
    Field('archived', 'integer', default=0),
    migrate=False)

dbmrxcms.define_table('jobop_applicant',
    Field('first_name', length=64),
    Field('last_name', length=64),
    Field('email', length=128),
    Field('phone', length=24),
    Field('address', length=255),
    Field('cover_letter', length=128),
    Field('cv_file', length=128),
    Field('reel', length=128),
    Field('reel_detail', length=128),
    Field('imdb', length=128),
    Field('linkedin', length=128),
    Field('country', length=56),
    Field('visa_id', dbmrxcms.jobop_visa),
    Field('hearsay_id', dbmrxcms.jobop_hearsay),
    Field('hearsay_detail', length=255),
    Field('candidacy', 'integer', default=1),
    migrate=False)

dbmrxcms.define_table('jobop_application',
    Field('applicant_id', dbmrxcms.jobop_applicant, label='Applicant'),
    Field('posting_id', dbmrxcms.jobop_posting),
    Field('status_id', dbmrxcms.jobop_status),
    Field('date_applied', 'datetime'),
    Field('comments', length=500),
    migrate=False)

dbmrxcms.define_table('jobop_opening',
    Field('posting_id', dbmrxcms.jobop_posting),
    Field('location_id', dbmrxcms.jobop_location),
    Field('date_posted', 'datetime'),
    migrate=False)

dbmrxcms.define_table('jobop_comment',
    Field('application_id', dbmrxcms.jobop_application, label='Application'),
    Field('username', length=64, label='Poster'),
    Field('date_added', 'datetime'),
    Field('content', 'text'),
    Field('parent_id', 'reference jobop_comment', label='Reply To'),
    Field('priority', 'integer', default=0),
    migrate=False)

dbmrxcms.define_table('jobop_interview',
    Field('application_id', dbmrxcms.jobop_application, label='Application'),
    Field('xuser_id', 'integer', label='Requester'),
    Field('voider_id', 'integer', label='Cancelled by'),
    Field('date', 'date'),
    Field('cancel', 'integer', default=0),
    Field('done', 'integer', default=0),
    Field('interviewer', length=255),
    migrate=False)

dbmrxcms.define_table('xrecruit_update',
    Field('application_id', dbmrxcms.jobop_application, label='Application'),
    Field('content', 'text'),
    Field('client', length=45),
    Field('date_created', 'datetime'),
    Field('updated', 'datetime'),
    migrate=False)

dbmrxcms.define_table('xrecruit_watch',
    Field('username', length=128),
    migrate=False)

dbmrxcms.define_table('xrecruit_watch_subscribe',
    Field('watch_id', dbmrxcms.xrecruit_watch),
    Field('posting_id', dbmrxcms.jobop_posting),
    migrate=False)

dbmrxcms.define_table('xrecruit_watch_ignore',
    Field('watch_id', dbmrxcms.xrecruit_watch),
    Field('posting_id', dbmrxcms.jobop_posting),
    migrate=False)

dbmrxcms.define_table('xrecruit_bookmark',
    Field('name', length=64),
    Field('username', length=64),
    Field('application_ids', length=255),
    migrate=False)


## after defining tables, uncomment below to enable auditing
# auth.enable_record_versioning(db)
