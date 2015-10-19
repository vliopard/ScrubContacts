import os
import sys
import web
import time
import math
import codecs

import atom.data
import atom.http_core

import gdata.data
import gdata.gauth
import gdata.contacts
import gdata.contacts.data
import gdata.contacts.client

from datetime import datetime
from bson.objectid import ObjectId

from pymongo import MongoClient
from pymongo import ASCENDING, DESCENDING

urls = (
    '/', 'Index',
    '/oauth2callback', 'oauth2callback',
    '/success', 'success'
    )

app = web.application(urls, globals(), True)
render = web.template.render('templates/')

USER_AGENT = 'ScrubContacts'

settings = open('settings.cfg')
# TODO: TASK: CHECK CLIENT_SECRET DOES NOT HAVE \N AT ITS EOL
APPLICATION_REDIRECT_URI, CLIENT_ID, CLIENT_SECRET, SUCCESS = settings.readline().split(',')
settings.close()

CLIENT_CODE = ''
CLIENT_TOKEN = ''
SCOPE = 'http://www.google.com/m8/feeds/'
head = 'http://www.google.com/m8/feeds/contacts/'
group_url = 'http://www.google.com/m8/feeds/groups/'
user_name = 'user@email.com'
tail = '/base/'
cplus_url = 'https://www.google.com/contacts/u/0/?cplus=0#contact/'

auth_token = gdata.gauth.OAuth2Token(client_id=CLIENT_ID,
                                     client_secret=CLIENT_SECRET,
                                     scope=SCOPE,
                                     user_agent=USER_AGENT)
authorize_url = auth_token.generate_authorize_url(redirect_uri=APPLICATION_REDIRECT_URI)
client = gdata.contacts.client.ContactsClient()
direct = False
feed_count = 0
max_result = 30000

start_time = time.time()


# This is the main working project, called when ScrubContacts is accessed
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def access(code):
    redirect_url = APPLICATION_REDIRECT_URI+'?code='+code
    url = atom.http_core.ParseUri(redirect_url)
    try:
        auth_token.get_access_token(url.query)
        global CLIENT_CODE
        CLIENT_CODE = code
        global CLIENT_TOKEN
        CLIENT_TOKEN = auth_token.access_token
        # redirect_url = atom.http_core.Uri.parse_uri(self.request.uri)
        # client = gdata.contacts.service.ContactsService(source='ScrubContacts')
        global client
        auth_token.authorize(client)
        info = client.GetContacts()
        global user_name
        user_name = info.id.text
        global direct

        print '_'*80
        print '0. List Contacts                    - Test for showing all contacts on screen'
        print '1. Test Create Contact              - Just testing new contact insertion'
        print '2. Test Update Contact Name         - Just testing update contact information'
        print '3. Bulk change names                - Change contact names from file [id,name]'
        print '4. Write Contacts to File CSV       - Write a CSV to undupe contacts in one column'
        print '5. Merge prototype name             - Supervisioned merge process with name'
        print '6. Write Contacts to File Report    - Same as List Contacts on screen but in disk'
        print '7. Merge prototype name DIRECT      - Non Supervisioned merge process with name'
        print '8. Format Phones                    - Format all phones from the contact list'
        print '9. Batch Rename                     - Rename all contacts from OldName to NewName'
        print 'A. Batch Rename from bulk name list - Rename all contacts based on a list [old,new]'
        print 'E. Merge prototype mail             - Supervisioned merge process with email'
        print 'F. Merge prototype mail DIRECT      - Non Supervisioned merge process with email'
        print 'I. Import contacts                  - Import contacts from file'
        print 'X. Delete all contacts              - Remove all contacts from account'
        print '_'*80
        opt = raw_input('Select: ').lower()

        if opt == '0':
            list_feed(display_contacts())
        if opt == '1':
            list_contact(create_contact(), True)
        if opt == '2':
            contact_id = raw_input('Contact ID: ')
            name = raw_input('New Contact Name: ')
            update_contact_name(head + user_name + tail + contact_id, name)
        if opt == '3':
            change_names('change_names.txt')
        if opt == '4':
            write_feed(display_contacts())
        if opt == '5':
            batch_merge('Name', display_contacts())
        if opt == '6':
            read_file('dupeID.txt')
        if opt == '7':
            direct = True
            batch_merge('Name', display_contacts())
        if opt == '8':
            batch_format_phones(display_contacts())
        if opt == '9':
            old = raw_input('Old Name: ')
            new = raw_input('New Name: ')
            batch_rename(display_contacts(), old, new)
        if opt == 'a':
            batch_rename_from_list(display_contacts())
        if opt == 'e':
            batch_merge('Mail', display_contacts())
        if opt == 'f':
            direct = True
            batch_merge('Mail', display_contacts())
        if opt == 'i':
            import_contacts('import_contacts.txt')
        if opt == 'x':
            batch_delete(display_contacts())
        bye()
        # web.seeother(SUCCESS)
        # render.done_form()
    except Exception, e:
        print e
    pass


# ==================================================================================================================== #
# BASIC FUNCTIONS FOR ADD, GET, CHANGE AND REMOVE CONTACTS
# ==================================================================================================================== #


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def add_contact(contact_entry):
    try:
        global client
        return client.CreateContact(contact_entry)
    except gdata.client.RequestError, e:
        error_status(e, contact_entry.name.text)
    pass
    return None


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def get_contact(contact_url):
    try:
        global client
        return client.GetContact(contact_url)
    except gdata.client.RequestError, e:
        error_status(e, contact_url)
    pass
    return None


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def get_user_url(uid):
    return head + user_name + tail + uid


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def get_contact_uid(contact_url):
    return get_contact(get_user_url(contact_url))


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def change_contact(contact_entry):
    try:
        updated_contact = client.Update(contact_entry)
        return updated_contact
    except gdata.client.RequestError, e:
        error_status(e, contact_entry.id.text)
    pass
    return None


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def remove_contact(contact_entry):
    try:
        global client
        client.Delete(contact_entry)
    except gdata.client.RequestError, e:
        error_status(e, contact_entry.id.text)
    pass


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def delete_contact_by_url(contact_url):
    remove_contact(get_contact(contact_url))


# This just calls Operating System to clear the screen
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def clear():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def bye():
    sys.exit()


# Remove non digit characters and returns just a string with numbers
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def get_num(number):
    if not number:
        return '0'
    return ''.join(element for element in number if element.isdigit())  # re.sub(r'\D', '', phone)


# Uses authorize URL to get GData Token
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def get_token():
    global authorize_url
    web.seeother(authorize_url)


# Authorize GData Client via OAuth2 Token
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def authorize(token):
    credentials = gdata.gauth.OAuth2Token(client_id=CLIENT_ID,
                                          client_secret=CLIENT_SECRET,
                                          scope=SCOPE,
                                          user_agent=USER_AGENT,
                                          access_token=token)
    global client
    credentials.authorize(client)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def error_message(message, error):
    print '____________________________________________'
    print '|                                          |'
    print '|   %s: [%s]' % (message, error)
    print '|__________________________________________|'


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def batch_delete(feed):
    for contact in feed.entry:
        remove_contact(contact)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_name(name):
    # given_name=gdata.data.GivenName(text='Elizabeth'),
    # family_name=gdata.data.FamilyName(text='Bennet'),
    return gdata.data.Name(full_name=gdata.data.FullName(text=name))


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_note(note):
    return atom.data.Content(text=note)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_email(name, email, primary, locale):
    re = gdata.data.OTHER_REL
    if locale == 'w':
        re = gdata.data.WORK_REL
    if locale == 'h':
        re = gdata.data.HOME_REL
    if locale == 'o':
        re = gdata.data.OTHER_REL
    return gdata.data.Email(address=email, primary=primary, rel=re, display_name=name)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_email_rel(rel, email):
    return gdata.data.Email(address=email, rel=rel)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_email_label(label, email):
    return gdata.data.Email(address=email, label=label)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_phone(number, primary, locale):
    re = gdata.data.MAIN_REL
    if locale == 'ho':
        re = gdata.data.HOME_REL
    if locale == 'wo':
        re = gdata.data.WORK_REL
    if locale == 'ot':
        re = gdata.data.OTHER_REL
    if locale == 'mo':
        re = gdata.data.MOBILE_REL
    if locale == 'ma':
        re = gdata.data.MAIN_REL
    if locale == 'hf':
        re = gdata.data.HOME_FAX_REL
    if locale == 'wf':
        re = gdata.data.WORK_FAX_REL
    if locale == 'gv':
        re = gdata.data.GOOGLE_TALK_PROTOCOL
    if locale == 'pg':
        re = gdata.data.PAGER_REL
    return gdata.data.PhoneNumber(text=number, rel=re, primary=primary)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_phone_rel(rel, number):
    return gdata.data.PhoneNumber(text=number, rel=rel)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_phone_label(label, number):
    return gdata.data.PhoneNumber(text=number, label=label)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def is_mobile(number):
    mob = len(get_num_format(get_num(number)))
    if mob == 11 or mob == 16 or mob == 17 or mob == 11 or mob == 20 or mob == 23:
        return True
    return False


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_phone_rel_type(other, number):
    if is_mobile(number):
        return set_phone_rel(gdata.data.MOBILE_REL, number)
    return set_phone_rel(other, number)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_phone_label_type(other, number):
    if is_mobile(number):
        return set_phone_label('Mobile', number)
    return set_phone_label(other, number)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_messenger(address, protocol):
    return gdata.data.Im(address=address, rel=gdata.data.OTHER_REL, protocol=protocol)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_im(address, kind):
    re = 'http://schemas.google.com/g/2005#'+kind
    if kind == 'hangouts':
        re = gdata.data.GOOGLE_TALK_PROTOCOL
    if kind == 'aim':
        re = gdata.data.AIM_PROTOCOL
    if kind == 'yim':
        re = gdata.data.YAHOO_MESSENGER_PROTOCOL
    if kind == 'skype':
        re = gdata.data.SKYPE_PROTOCOL
    if kind == 'qq':
        re = gdata.data.QQ_PROTOCOL
    if kind == 'msn':
        re = gdata.data.MSN_PROTOCOL
    if kind == 'icq':
        re = gdata.data.ICQ_PROTOCOL
    if kind == 'jaber':
        re = gdata.data.JABBER_PROTOCOL
    return gdata.data.Im(address=address, rel=gdata.data.OTHER_REL, protocol=re)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_nick(nick):
    return gdata.contacts.data.NickName(text=nick)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_birth(birth):
    return gdata.contacts.data.Birthday(when=birth)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_custom(k, v):
    return gdata.contacts.data.UserDefinedField(key=k, value=v)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_group(group_name):
    return gdata.contacts.data.GroupMembershipInfo(href=group_name)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_group_by_id(cid):
    return gdata.contacts.data.GroupMembershipInfo(href=group_url + user_name + tail + cid)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_occupation(oc):
    return gdata.contacts.data.Occupation(text=oc)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_title(title):
    # return atom.Title(text=title)
    # return '<ns0:title>' + title + '</ns0:title>'
    return atom.data.Title(text=title)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_web_rel(name, url):
    return gdata.contacts.data.Website(href=url, rel=name)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_web_label(name, url):
    return gdata.contacts.data.Website(href=url, label=name)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_event(name, dt):
    return gdata.contacts.data.Event(when=gdata.data.When(start=dt), rel=name)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_gender(oc):
    # TODO: TASK: FIX GENDER TO GET IT WORKING
    return gdata.contacts.Gender(value=oc, text=oc)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def make_gender(oc):
    return '<ns0:gender xmlns:ns0="http://schemas.google.com/contact/2008" value="'+oc+'" />'


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_relation(okind, name):
    return gdata.contacts.data.Relation(rel=okind, text=name)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_org(okind, primary, company, role):
    return gdata.data.Organization(label=okind, primary=primary, name=gdata.data.OrgName(text=company),
                                   title=gdata.data.OrgTitle(text=role))


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def create_org():
    return gdata.data.Organization(label='Work', primary='true')


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_org_title(title):
    return gdata.data.OrgTitle(text=title)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_org_name(name):
    return gdata.data.OrgName(text=name)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_job(job):
    return gdata.data.OrgJobDescription(text=job)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_postal_rel_short(rel, address):
    return gdata.data.StructuredPostalAddress(rel=rel,
                                              formatted_address=gdata.data.FormattedAddress(text=address))


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_postal_label_short(label, address):
    return gdata.data.StructuredPostalAddress(label=label,
                                              formatted_address=gdata.data.FormattedAddress(text=address))


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_postal(kind, street, city, state, zip_code, country, primary):
    k = kind
    if kind == 'h':
        k = gdata.data.HOME_REL
    if kind == 'w':
        k = gdata.data.WORK_REL
    return gdata.data.StructuredPostalAddress(rel=k,
                                              primary=primary,
                                              street=gdata.data.Street(text=street),
                                              city=gdata.data.City(text=city),
                                              region=gdata.data.Region(text=state),
                                              postcode=gdata.data.Postcode(text=zip_code),
                                              country=gdata.data.Country(text=country),
                                              formatted_address=gdata.data.FormattedAddress(text=street))


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_star_group():
    return set_group_by_id('17')


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_main_group():
    return set_group_by_id('6')


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def deep_get_attribute(obj, attr):
    try:
        val = reduce(getattr, attr.split('.'), obj)
    except AttributeError:
        return 'empty'
    return val


# DISPLAY CONTACTS
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def display_contacts():
    query = gdata.contacts.client.ContactsQuery()
    global max_result
    query.max_results = max_result
    global client
    print 'Retrieving contact list...'
    st_time = time.time()
    feed = client.GetContacts(q=query)
    print 'Retrieved in: %s' % (time.time() - st_time)
    return feed


# DISPLAY CONTACTS
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def list_feed(feed):
    # list_contact = gdata.contacts.data.ContactEntry()
    for i, entry in enumerate(feed.entry):
        # print entry
        # list_contact = entry
        # list_contact(list_contact)
        list_contact(entry, True)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def get_num_format(number):
    new_num = number
    n = get_num(number)
    v = str(n)
    l = len(v)
    d = l / 3
    i = math.floor(d)
    if l < 8:  # service 144 or 24 999
        if l == 4:
            new_num = v[:2] + '-' + v[-2:]
        else:
            new_num = v[-3:]
            if l > 3:
                v = v[:-3]
                for x in range(0, int(i)):
                    new_num = v[-3:] + '-' + new_num
                    v = v[:-3]
                if d > i:
                    new_num = v + '-' + new_num
    elif l == 8:  # phone 1111 2222
        new_num = v[:4] + '-' + v[-4:]
    elif l == 9:  # mobile 911 112 222
        new_num = v[:3] + '-' + v[3:-3] + '-' + v[-3:]
    elif l == 10:  # phone +area (19) 1112 2222
        new_num = '(' + v[:2] + ') ' + v[2:-4] + '-' + v[-4:]
    elif l == 11:
        if v[:4] == '0800':  # 0800 111 2222
            new_num = v[:4] + '-' + v[4:-4] + '-' + v[-4:]
        elif v[:1] == '0':  # phone 0+area (019) 1112 2222
            new_num = '(' + v[:3] + ') ' + v[3:-4] + '-' + v[-4:]
        else:  # mobile +area (19) 911 112 222
            new_num = '(' + v[:2] + ') ' + v[2:-6] + '-' + v[5:-3] + '-' + v[-3:]
    elif l == 12:  # mobile 0+area (019) 911 112 222
        new_num = '(' + v[:3] + ') ' + v[3:-6] + '-' + v[6:-3] + '-' + v[-3:]
    elif l == 13:  # phone w/ carrier 041 (19) 1112 2222
        new_num = v[:3] + ' (' + v[3:-8] + ') ' + v[5:-4] + '-' + v[-4:]
    elif l == 14:  # mobile w/ carrier 041 (19) 911 112 222
        new_num = v[:3] + ' (' + v[3:-9] + ') ' + v[5:-6] + '-' + v[8:-3] + '-' + v[-3:]
    elif l == 15:  # phone international 55 041 (19) 1112 2222
        new_num = v[:2] + ' ' + v[2:-10] + ' (' + v[5:-8] + ') ' + v[7:-4] + '-' + v[-4:]
    elif l == 16:  # mobile international 55 041 (19) 911 112 222
        new_num = v[:2] + ' ' + v[2:-11] + ' (' + v[5:-9] + ') ' + v[7:-6] + '-' + v[10:-3] + '-' + v[-3:]
    return new_num


# DISPLAY CONTACT
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def list_contact(contact_entry, paused):
    website_tabs = 61
    phone_tabs = 61
    email_tabs = 50
    addr_tabs = 40
    if contact_entry is not None:
        print '__________________________________________________________'
        var = deep_get_attribute(contact_entry, 'id.text')
        if var != 'empty':
            print '17 MAIN: [%s]' % (cplus_url + var.rstrip().rsplit('/', 1)[-1])
        # var = deep_get_attribute(contact_entry, 'etag')
        # if var != 'empty':
        #     print '01 ETAG:[%s]' % var
        var = deep_get_attribute(contact_entry, 'nickname.text')
        if var != 'empty':
            print '02 NICK: [%s]' % var
        var = deep_get_attribute(contact_entry, 'title.text')
        if var != 'empty':
            print '03 TITL: [%s]' % var
        var = deep_get_attribute(contact_entry, 'name.full_name.text')
        if var != 'empty':
            print '04 NAME: [%s]' % var
        var = deep_get_attribute(contact_entry, 'organization.name.text')
        if var != 'empty':
            print '05 ORGN: [%s]' % var
        var = deep_get_attribute(contact_entry, 'organization.title.text')
        if var != 'empty':
            print '06 ORGT: [%s]' % var
        var = deep_get_attribute(contact_entry, 'birthday.when')
        if var != 'empty':
            print '07 BRTH: [%s]' % var
        # var = deep_get_attribute(contact_entry, 'gender.value')
        # if var != 'empty':
        #     print '21 GNDR:[%s]' % var
        for udf in contact_entry.event:
            print '08 EVNT: %s:[%s]' % (udf.rel if udf.rel is not None else udf.label, udf.when.start)
        for udf in contact_entry.user_defined_field:
            print '09 USER: %s:[%s]' % (udf.key, udf.value)
        for udf in contact_entry.relation:
            print '10 RELT: %s:[%s]' % (udf.rel if udf.rel is not None else udf.label, udf.text)
        website = []
        for udf in contact_entry.website:
            website.append([udf.rel if udf.rel is not None else udf.label, udf.href])
        web_list = sorted(website, key=lambda x: x[1])
        for udf in web_list:
            print '11 WEBS: [%s]%s[%s]' % \
                  (udf[1],
                   ' '*(website_tabs-len(udf[1])) if len(udf[1]) < website_tabs else ' ',
                   udf[0])
        for udf in contact_entry.im:
            print '12 IMSG %s:[%s]' % (udf.protocol, udf.address)
        for udf in contact_entry.structured_postal_address:
            rel_or_label = udf.rel if udf.rel is not None else udf.label
            print '13 ZIPC: [%s]%s[%s]' % \
                  (rel_or_label,
                   ' '*(addr_tabs-len(rel_or_label)) if len(rel_or_label) < addr_tabs else ' ',
                   udf.formatted_address.text)
        email = []
        for udf in contact_entry.email:
            email.append([udf.rel if udf.rel is not None else udf.label, udf.address, udf.primary, udf.display_name])
        mail_list = sorted(email, key=lambda x: x[1])
        for udf in mail_list:
            print '14 MAIL: [%s] [%s] [%s]%s[%s]' % \
                  (udf[2] if udf[2] is not None else '    ',
                   udf[3] if udf[3] is not None else ' ',
                   udf[1],
                   ' '*(email_tabs-len(udf[1])) if len(udf[1]) < email_tabs else ' ',
                   udf[0])
        for udf in contact_entry.phone_number:
            number = get_num_format(udf.text)
            print '15 PHNE: [%s]%s[%s]' % \
                  (number,
                   ' '*(phone_tabs-len(number)) if len(number) < phone_tabs else ' ',
                   udf.rel if udf.rel is not None else udf.label)
        # for udf in contact_entry.link:
        #     print '16 %s:[%s]' % (udf.rel, udf.href)
        var = deep_get_attribute(contact_entry, 'content.text')
        if var != 'empty':
            print '18 NOTE: [%s]' % var
        for group in contact_entry.group_membership_info:
            print '19 GRPS: [%s]' % group.href
        # var = deep_get_attribute(contact_entry, 'updated.text')
        # if var != 'empty':
        #     print '20 UPDT:[%s]' % var
        var = deep_get_attribute(contact_entry, 'occupation')
        if var != 'empty' and var is not None:
            print '22 OCCP: [%s]' % var
        var = deep_get_attribute(contact_entry, 'organization.job_description')
        if var != 'empty' and var is not None:
            print '23 JDSC: [%s]' % var
        # print '__________________________________________________________'
        if paused:
            enter_or_quit()


# WRITE CONTACT
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def write_contact(contact_entry, target):
    if contact_entry is not None:
        # target.write('__________________________________________________________\n')
        # target.write('01 ETAG:[' + deep_get_attribute(contact_entry, 'etag') + ']\n')
        # target.write('02 NICK:[' + deep_get_attribute(contact_entry, 'nickname.text') + ']\n')
        # target.write('03 TITL:[' + deep_get_attribute(contact_entry, 'title.text') + ']\n')
        target.write('04 NAME:[' + deep_get_attribute(contact_entry, 'name.full_name.text') + ']\n')
        # target.write('05 ORGN:[' + deep_get_attribute(contact_entry, 'organization.name.text') + ']\n')
        # target.write('06 ORGT:[' + deep_get_attribute(contact_entry, 'organization.title.text') + ']\n')
        target.write('07 BRTH:[' + deep_get_attribute(contact_entry, 'birthday.when') + ']\n')
        # for udf in contact_entry.event:
        #     target.write('08 ' + (udf.rel if udf.rel is not None else udf.label) + ':[' + udf.when.start + ']\n')
        for udf in contact_entry.user_defined_field:
            target.write('09 ' + udf.key + ':[' + udf.value + ']\n')
        # for udf in contact_entry.relation:
        #     target.write('10 ' + (udf.rel if udf.rel is not None else udf.label) + ':[' + udf.text + ']\n')
        for udf in contact_entry.website:
            target.write('11 ' + (udf.rel if udf.rel is not None else udf.label) + ':[' + udf.href + ']\n')
        # for udf in contact_entry.im:
        #     target.write('12 IM ' + udf.protocol + ':[' + udf.address + ']\n')
        # for udf in contact_entry.structured_postal_address:
            # target.write('13 ' + (udf.rel if udf.rel is not None else udf.label) +
            #              ':[' + udf.formatted_address.text + ']\n')
        for udf in contact_entry.email:
            target.write('14 ' + (udf.rel if udf.rel is not None else udf.label) + ':[' + udf.address + ']\n')
        for udf in contact_entry.phone_number:
            target.write('15 ' + (udf.rel if udf.rel is not None else udf.label) + ':[' + get_num(udf.text) + ']\n')
        # for udf in contact_entry.link:
        #     target.write('16 ' + udf.rel + ':[' + udf.href + ']\n')
        # target.write('17 MAIN:[' + deep_get_attribute(contact_entry, 'id.text') + ']\n')
        # target.write('18 NOTE:[' + deep_get_attribute(contact_entry, 'content.text') + ']\n')
        # for group in contact_entry.group_membership_info:
        #     target.write('19 GRPS:[' + group.href + ']\n')
        # target.write('20 UPDT:[' + deep_get_attribute(contact_entry, 'updated.text') + ']\n')
        target.write('__________________________________________________________\n')


# DISPLAY CONTACTS
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def write_feed(feed):
    target = codecs.open('google.csv', 'w', 'utf-8')
    line = 'ID;FULL NAME;EMAIL ADDR\n'
    target.write(line)
    for i, entry in enumerate(feed.entry):
        # write_contact(entry, target)
        write_contact_csv(entry, target)
        # check_field_dupes(entry, target)
    target.close()


# WRITE CONTACT
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def write_contact_csv(contact_entry, target):
    line1 = deep_get_attribute(contact_entry, 'id.text') + ';' + \
            deep_get_attribute(contact_entry, 'name.full_name.text') + ';'
    not_udf = True
    for udf5 in contact_entry.email:
        not_udf = False
        line3 = line1 + udf5.address + '\n'
        target.write(line3)
    for udf6 in contact_entry.phone_number:
        not_udf = False
        line3 = line1 + get_num(udf6.text) + '\n'
        target.write(line3)
    for udf0 in contact_entry.event:
        not_udf = False
        line3 = line1 + (udf0.rel if udf0.rel is not None else udf0.label) + ' | ' + udf0.when.start + '\n'
        target.write(line3)
    for udf1 in contact_entry.user_defined_field:
        not_udf = False
        line3 = line1 + udf1.key + ' | ' + udf1.value + '\n'
        target.write(line3)
    for udf2 in contact_entry.website:
        not_udf = False
        line3 = line1 + (udf2.rel if udf2.rel is not None else udf2.label) + ' | ' + udf2.href + '\n'
        target.write(line3)
    for udf3 in contact_entry.im:
        not_udf = False
        line3 = line1 + udf3.protocol + ' | ' + udf3.address + '\n'
        target.write(line3)
    for udf4 in contact_entry.link:
        not_udf = False
        line3 = line1 + udf4.rel + ' | ' + udf4.href + '\n'
        target.write(line3)		
    if not_udf:
        line3 = line1 + 'otherRef\n'
        target.write(line3)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def prepare_merge(feed, kind):
    global feed_count
    feed_count = 0
    lines = []
    for entry in feed.entry:
        feed_count += 1
        # TODO: TASK: ORDER BY MAIL AND PHONE (SELECT FIRST ALPHABET EMAIL AND SHORT PHONE NUMBER)
        if kind == 'EMail':
            # TODO: TASK: USE EMAIL SORT (GET FIRST?)
            item = [deep_get_attribute(entry, 'id.text'), deep_get_attribute(entry, 'name.full_name.text')]
        elif kind == 'Phone':
            # TODO: TASK: USE PHONE SORT (GET FIRST?)
            item = [deep_get_attribute(entry, 'id.text'), deep_get_attribute(entry, 'name.full_name.text')]
        else:
            item = [deep_get_attribute(entry, 'id.text'), deep_get_attribute(entry, 'name.full_name.text')]
        lines.append(item)
    # target = codecs.open('merge.txt', 'w', 'utf-8')
    web_list = sorted(lines, key=lambda x: x[1])
    values = []
    for line in web_list:
        values.append(line[0])
        # target.write(line[0] + ';' + line[1])
    # target.close()
    return values


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def is_valid_date(date):
    try:
        datetime.strptime(date, '%Y-%m-%d')
        return True
    except ValueError:
        return False


# UPDATE
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def update_contact_name(contact_url, name):
    # First retrieve the contact to modify from the API.
    contact_entry = get_contact(contact_url)
    if contact_entry is not None:
        f_name = deep_get_attribute(contact_entry, 'name.full_name.text')
        global start_time
        if f_name != name:
            list_contact(contact_entry, False)
            # print '_________________________________________________________________________'
            print 'change [%s]' % f_name
            print '    to [%s]' % name
            print '_________________________________________________________________________'
            val = raw_input('Change? (a)bort, (s)kip, ENTER to confirm: ').lower()
            start_time = time.time()
            if val == 's':
                print 'skipped'
            elif val == 'a':
                print 'System shutdown...'
                bye()
            else:
                if f_name == 'empty':
                    contact_entry.name = set_name(name)
                else:
                    contact_entry.name.full_name.text = name
                dt = deep_get_attribute(contact_entry, 'birthday.when')
                changed = False
                if dt != 'empty':
                    birth = is_valid_date(contact_entry.birthday.when)
                    if birth is not True:
                        last_five = contact_entry.birthday.when[-5:]
                        test_number = int(last_five[:2])
                        if test_number <= 12:
                            new_date = '1900-' + last_five[:2] + '-' + contact_entry.birthday.when[-2:]
                        else:
                            new_date = '1900-' + contact_entry.birthday.when[-2:] + '-' + last_five[:2]
                        print 'New calc date: %s' % new_date
                        birth = is_valid_date(new_date)
                        changed = True
                        if birth:
                            contact_entry.birthday.when = new_date
                        else:
                            contact_entry.birthday.when = ''
                # contact_entry.name.given_name.text = 'New'
                # contact_entry.name.family_name.text = 'Name'
                updated_contact = change_contact(contact_entry)
                print 'Updated:  [%s]' % updated_contact.updated.text
                print '=============================================================================='
                print 'New Name: [%s]' % updated_contact.name.full_name.text
                if changed:
                    print 'New Date: [%s]' % contact_entry.birthday.when
                print 'Elapsed time %s' % (time.time() - start_time)
                return updated_contact
        else:
            print 'Identical, next...'
    return None


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def error_status(e, name):
    if e.status == 404:
        error_message('NOT FOUND 404', name)
    elif e.status == 412:
        error_message('ETAGS MISMATCH 412', name)
    elif e.status == 503:
        error_message('BACKEND ERROR 503', name)
    elif e.status == 500:
        error_message('BACKEND ERROR 500', name)
    elif e.status == 400:
        error_message('400 Error', e)
    else:
        error_message('Something went wrong', e.status)
        print e


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def count_lines(file_name):
    non_blank_count = 0
    rf = open(file_name)
    lines = rf.readlines()
    for line in lines:
        if line.strip():
            non_blank_count += 1
    rf.close()
    return non_blank_count


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def change_names(file_name):
    print 'getting total...'
    max_lines = count_lines(file_name)
    rf = open(file_name)
    lines = rf.readlines()
    i = 0
    for line in lines:
        i += 1
        url, cname = line.split(',')
        print '=============================================================================='
        print '\nSequence number [%s/%s] ContactPlus URL: [ %s ]' % (i, max_lines, (cplus_url + url.rsplit('/', 1)[-1]))
        update_contact_name(url, normalize(cname))
    rf.close()


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def normalize(value):
    value = value.decode('windows-1252')
    value = value.rstrip()
    # print value.encode('utf-8')
    return value


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def import_contacts(file_name):
    print 'getting total...'
    max_lines = count_lines(file_name)
    rf = open(file_name)
    lines = rf.readlines()
    i = 0
    for line in lines:
        i += 1
        cname, email, phone, account, address, manager, company, department = line.split(';')
        print 'Sequence number [%s/%s]' % (i, max_lines)

        new_contact = gdata.contacts.data.ContactEntry()
        
        if cname != '':
            new_contact.name = set_name(normalize(cname))
        if email != '':
            new_contact.email.append(set_email_label('Work', email.lower()))
        if phone != '':
            new_contact.phone_number.append(set_phone_label_type('Work', get_num_format(phone)))
        if account != '':
            new_contact.user_defined_field.append(set_custom('Account', account))
        if address != '':
            new_contact.structured_postal_address.append(set_postal_label_short('Work', normalize(address)))
        if manager != '':
            new_contact.user_defined_field.append(set_custom('Manager', normalize(manager)))
        if company != '':
            new_contact.organization = set_org('Work', 'true', normalize(company), '')
        if department != '':
            new_contact.user_defined_field.append(set_custom('Department', department))
        new_contact.group_membership_info.append(set_main_group())  # My Contacts
        new_contact.group_membership_info.append(set_group_by_id('1837ec138fe7a16a'))  # Eldorado
        add_contact(new_contact)
        print '_'*80
    rf.close()


# TODO: TASK: Always check attribute or define new with methods above
# write down csv with ID, name, email, phone
# order by merge (name, email, phone) (MONGO DB?)
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def batch_merge(column, feed):
    print 'Batch Merge - Using [%s]' % column
    # get elements ordered list - DONE
    #   get first - DONE
    #       merge while same attribute 1, 2, 3... adding items
    #           if item is already at list, skip
    #       check 1, 2, 3 are merged
    #       remove 1, 2, 3
    #       next
    # _______________________________________________________
    # merge by elements: (same name, same mail, same phone)
    # same home phone is not a duplicate
    # max_lines = count_lines('ordered.txt')
    # f = open('ordered.txt')
    # lines = f.readlines()
    print 'Preparing list...'
    lines = prepare_merge(feed, column)
    print 'List Total [%s]' % feed_count
    i = 0
    m = 0
    main_comp = lines[0].rstrip()
    for line in lines:
        i += 1
        # update_contact_name(line)

        contact_entry1 = get_contact(main_comp)
        if contact_entry1 is not None:
            f_name1 = deep_get_attribute(contact_entry1, 'name.full_name.text')
            contact_entry2 = get_contact(lines[i].rstrip())
            if contact_entry2 is not None:
                f_name2 = deep_get_attribute(contact_entry2, 'name.full_name.text')
                if f_name1 == f_name2:
                    print '\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n VVVVVVVV ==== NEW COMPARISON STARTS HERE ==== VVVVVVVV'
                    list_contact(contact_entry1, False)
                    list_contact(contact_entry2, False)
                    print '__________________________________________________________________________'
                    print 'Sequence number [%s/%s] [%s]<=>[%s] [%s][%s]' % (i, feed_count, m+1, i+1, f_name1, f_name2)
                    if column == 'EMail':
                        # TODO: TASK: MERGE CONTACTS BY EMAIL (UNDUPE NAME 1, 2 OR VALUE)
                        merge_contacts_by_email(contact_entry1, contact_entry2)
                    elif column == 'Phone':
                        # TODO: TASK: MERGE CONTACTS BY PHONE (UNDUPE NAME 1, 2 OR VALUE)
                        merge_contacts_by_phone(contact_entry1, contact_entry2)
                    else:
                        merge_contacts_by_name(contact_entry1, contact_entry2)
                else:
                    m = i
                    main_comp = lines[i].rstrip()
        else:
            m = i - 1
            main_comp = line.rstrip()
    # f.close()


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def set_value(kind, value):
    if kind == 'nick':
        return set_nick(value)
    if kind == 'title':
        return set_title(value)
    if kind == 'orgname':
        return set_org_name(value)
    if kind == 'gender':
        return set_gender(value)
    if kind == 'orgtitle':
        return set_org_title(value)
    if kind == 'birthday':
        if value == 'empty':
            # new_date = '1800-01-01'
            # return set_birth(new_date)
            return None
        if is_valid_date(value) is not True:
            last_five = value[-5:]
            test_number = int(last_five[:2])
            if test_number <= 12:
                new_date = '1900-' + last_five[:2] + '-' + value[-2:]
            else:
                new_date = '1900-' + value[-2:] + '-' + last_five[:2]
            if is_valid_date(new_date):
                return set_birth(new_date)
        else:
            return set_birth(value)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def undupe_item(item_one, item_two, kind):
    item_one = item_one.strip()
    item_two = item_two.strip()
    if item_one != item_two:
        if item_two != 'empty' and item_two != '':
            if item_one != 'empty' and item_one != '':
                print '1. %s' % item_one
                print '2. %s' % item_two
                answer = raw_input('1, 2 or new value: ')
                if answer == '2':
                    item_one = item_two
                elif answer != '1':
                    item_one = answer
            else:
                item_one = item_two
    return set_value(kind, item_one)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def debug(message):
    val = raw_input(message + "\n____________________________\nENTER to continue, (q)uit: ").lower()
    if val == 'q':
        bye()


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def merge_contacts_by_email(contact_keep, contact_remove):
    # TODO: TASK: SAME IDEA DIFFERENT LOOPS
    return


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def merge_contacts_by_phone(contact_keep, contact_remove):
    # TODO: TASK: SAME IDEA DIFFERENT LOOPS
    return


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def merge_contacts_by_name(contact_keep, contact_remove):
    global client
    global direct
    same_name_email = False
    something_changed = False
    what_changed = []

    if deep_get_attribute(contact_keep, 'name.full_name.text') == \
            deep_get_attribute(contact_remove, 'name.full_name.text'):
        for event_keep in contact_keep.email:
            for event_remove in contact_remove.email:
                if event_keep.address == event_remove.address:
                    same_name_email = True
                    break

    if direct:
        same_name_email = True

    if not same_name_email:
        ans = raw_input('Contacts do not have a common e-mail address. Want to merge anyway? [y/n/q]: ').lower()
        if ans == 'y':
            same_name_email = True
        if ans == 'q':
            bye()

    if same_name_email:
        item_one = deep_get_attribute(contact_keep, 'content.text')
        item_two = deep_get_attribute(contact_remove, 'content.text')
        if item_one != item_two:
            if item_two != 'empty':
                if item_one != 'empty':
                    contact_keep.content.text = item_one + '\n_______\n' + item_two
                    something_changed = True
                    what_changed.append('18.NOTE(merge)')
                else:
                    contact_keep.content.text = item_two
                    something_changed = True
                    what_changed.append('18.NOTE')

        # TODO: TASK: * JOB DESCRIPTION, * OCCUPATION, * GENDER
        # temp_gender = undupe_item(deep_get_attribute(contact_keep, 'gender.value'),
        #                           deep_get_attribute(contact_remove, 'gender.value'),
        #                           'gender')
        # if temp_gender.value != deep_get_attribute(contact_keep, 'gender.value'):
        #     contact_keep.gender = set_gender(temp_gender.value)
        #     something_changed = True
        #     what_changed.append(
        #         '21.GNDR: [' + deep_get_attribute(contact_keep, 'gender.value') + '] => [' + temp_gender.value + ']')

        temp_nick = undupe_item(deep_get_attribute(contact_keep, 'nickname.text'),
                                deep_get_attribute(contact_remove, 'nickname.text'),
                                'nick')
        if temp_nick.text != deep_get_attribute(contact_keep, 'nickname.text'):
            contact_keep.nickname = temp_nick
            something_changed = True
            what_changed.append(
                '02.NICK: [' + deep_get_attribute(contact_keep, 'nickname.text') + '] => [' + temp_nick.text + ']')

        temp_title = undupe_item(deep_get_attribute(contact_keep, 'title.text'),
                                 deep_get_attribute(contact_remove, 'title.text'),
                                 'title')
        if temp_title.text != deep_get_attribute(contact_keep, 'title.text'):
            contact_keep.title = temp_title
            something_changed = True
            what_changed.append(
                '03.TITL: [' + deep_get_attribute(contact_keep, 'title.text') + '] => [' + temp_title.text + ']')

        org_name = undupe_item(deep_get_attribute(contact_keep, 'organization.name.text'),
                               deep_get_attribute(contact_remove, 'organization.name.text'),
                               'orgname')
        org_title = undupe_item(deep_get_attribute(contact_keep, 'organization.title.text'),
                                deep_get_attribute(contact_remove, 'organization.title.text'),
                                'orgtitle')

        if (deep_get_attribute(contact_keep, 'organization.name.text') == 'empty') \
                and (deep_get_attribute(contact_keep, 'organization.title.text') == 'empty'):
            contact_keep.organization = create_org()

        if (org_name.text != 'empty') and \
                (org_name.text != deep_get_attribute(contact_keep, 'organization.name.text')):
            contact_keep.organization.name = org_name
            something_changed = True
            what_changed.append('05.ORGN')
        if (org_title.text != 'empty') and \
                (org_title.text != deep_get_attribute(contact_keep, 'organization.title.text')):
            contact_keep.organization.title = org_title
            something_changed = True
            what_changed.append('06.ORGT')

        b_day = undupe_item(deep_get_attribute(contact_keep, 'birthday.when'),
                            deep_get_attribute(contact_remove, 'birthday.when'),
                            'birthday')
        if b_day is not None:
            if b_day.when != deep_get_attribute(contact_keep, 'birthday.when'):
                contact_keep.birthday = b_day
                something_changed = True
                what_changed.append('07.BRTH')

        group = False
        for group_keep in contact_keep.group_membership_info:
            for group_remove in contact_remove.group_membership_info:
                if group_keep.href != group_remove.href:
                    group_keep.append(set_group(group_remove.href))
                    group = True
        if group:
            something_changed = True
            what_changed.append('19.GRPS')

        event = False
        for event_keep in contact_keep.event:
            for event_remove in contact_remove.event:
                if event_remove.rel is not None:
                    if event_keep.rel != event_remove.rel:
                        event_keep.append(set_event(event_remove.rel, event_remove.when.start))
                        event = True
                else:
                    if event_keep.label != event_remove.label:
                        event_keep.append(set_event(event_remove.label, event_remove.when.start))
                        event = True
        if event:
            something_changed = True
            what_changed.append('08.EVNT')

        relation = False
        for event_keep in contact_keep.relation:
            for event_remove in contact_remove.relation:
                if event_remove.rel is not None:
                    if event_keep.rel != event_remove.rel:
                        event_keep.append(set_relation(event_remove.rel, event_remove.text))
                        relation = True
                else:
                    if event_keep.label != event_remove.label:
                        event_keep.append(set_relation(event_remove.label, event_remove.text))
                        relation = True
        if relation:
            something_changed = True
            what_changed.append('10.RELT')

        ws = False
        if contact_keep.website:
            website = []
            for site_list in contact_keep.website:
                website.append((site_list.rel if site_list.rel is not None else site_list.label) + '|' + site_list.href)
            for event_remove in contact_remove.website:
                check = (event_remove.rel if event_remove.rel is not None else event_remove.label) +\
                        '|' + event_remove.href
                if check not in website:
                    if event_remove.rel is not None:
                        contact_keep.website.append(set_web_rel(event_remove.rel, event_remove.href))
                    else:
                        contact_keep.website.append(set_web_label(event_remove.label, event_remove.href))
                    ws = True
        else:
            if contact_remove.website:
                contact_keep.website = []
                for event_remove in contact_remove.website:
                    if event_remove.rel is not None:
                        contact_keep.website.append(set_web_rel(event_remove.rel, event_remove.href))
                    else:
                        contact_keep.website.append(set_web_label(event_remove.label, event_remove.href))
                    ws = True
        if ws:
            something_changed = True
            what_changed.append('11.WEBS')

        em = False
        if contact_keep.email:
            email = []
            for email_list in contact_keep.email:
                email.append(email_list.address)
            for event_remove in contact_remove.email:
                if event_remove.address not in email:
                    if event_remove.rel is not None:
                        contact_keep.email.append(set_email_rel(event_remove.rel, event_remove.address.lower()))
                    else:
                        contact_keep.email.append(set_email_label(event_remove.label, event_remove.address.lower()))
                    em = True
        else:
            if contact_remove.email:
                contact_keep.email = []
                for event_remove in contact_remove.email:
                    if event_remove.rel is not None:
                        contact_keep.email.append(set_email_rel(event_remove.rel, event_remove.address.lower()))
                    else:
                        contact_keep.email.append(set_email_label(event_remove.label, event_remove.address.lower()))
                    em = True
        if em:
            something_changed = True
            what_changed.append('14.MAIL')

        ph = False
        if contact_keep.phone_number:
            number = []
            for number_list in contact_keep.phone_number:
                number.append((number_list.rel if number_list.rel is not None else number_list.label) +
                              '|' + get_num(number_list.text))
            for event_remove in contact_remove.phone_number:
                check = (event_remove.rel if event_remove.rel is not None else event_remove.label) + \
                        '|' + get_num(event_remove.text)
                if check not in number:
                    if event_remove.rel is not None:
                        contact_keep.phone_number.append(
                            set_phone_rel_type(event_remove.rel, get_num_format(event_remove.text)))
                    else:
                        contact_keep.phone_number.append(
                            set_phone_label_type(event_remove.label, get_num_format(event_remove.text)))
                    ph = True
        else:
            if contact_remove.phone_number:
                contact_keep.phone_number = []
                for event_remove in contact_remove.phone_number:
                    if event_remove.rel is not None:
                        contact_keep.phone_number.append(
                            set_phone_rel_type(event_remove.rel, get_num_format(event_remove.text)))
                    else:
                        contact_keep.phone_number.append(
                            set_phone_label_type(event_remove.label, get_num_format(event_remove.text)))
                    ph = True
        if ph:
            something_changed = True
            what_changed.append('15.PHNE')

        # TODO: TASK: HANDLE POSTAL ADDRESS TO BE ADDED TO THE CONTACT WHILE MERGING
        pa = False
        if contact_keep.structured_postal_address:
            for event_keep in contact_keep.structured_postal_address:
                for event_remove in contact_remove.structured_postal_address:
                    if event_remove.rel is not None:
                        if event_keep.rel != event_remove.rel and \
                                        event_keep.formatted_address.text != event_remove.formatted_address.text:
                            event_keep.append(
                                set_postal_rel_short(event_remove.rel, event_remove.formatted_address.text))
                            pa = True
                    else:
                        if event_keep.label != event_remove.label and \
                                        event_keep.formatted_address.text != event_remove.formatted_address.text:
                            event_keep.append(
                                set_postal_label_short(event_remove.label, event_remove.formatted_address.text))
                            pa = True
        else:
            contact_keep.structured_postal_address = []
            if contact_remove.structured_postal_address:
                for event_remove in contact_remove.structured_postal_address:
                    if event_remove.rel is not None:
                        contact_keep.structured_postal_address.append(
                            set_postal_rel_short(event_remove.rel, event_remove.formatted_address.text))
                    else:
                        contact_keep.structured_postal_address.append(
                            set_postal_label_short(event_remove.label, event_remove.formatted_address.text))
                    pa = True
        if pa:
            something_changed = True
            what_changed.append('13.ZIPC')

        ud = False
        for event_keep in contact_keep.user_defined_field:
            for event_remove in contact_remove.user_defined_field:
                if (event_keep.key != event_remove.key) and (event_keep.value != event_remove.value):
                    event_keep.append(set_custom(event_remove.key, event_remove.value))
                    ud = True
        if ud:
            something_changed = True
            what_changed.append('09.USER')

        im = False
        for event_keep in contact_keep.im:
            for event_remove in contact_remove.im:
                if (event_keep.protocol != event_remove.protocol) and (event_keep.address != event_remove.address):
                    event_keep.append(set_messenger(event_remove.address, event_remove.protocol))
                    im = True
        if im:
            something_changed = True
            what_changed.append('12.IMSG')

        # TODO: TASK: SEE IF PHOTO MUST BE HANDLED
        lk = False
        for event_keep in contact_keep.link:
            for event_remove in contact_remove.link:
                if (event_keep.rel != event_remove.rel) and (event_keep.href != event_remove.href):
                    if event_remove.rel != 'self' and event_remove.rel != 'edit':
                        event_keep.append(set_web_rel(event_remove.rel, event_remove.href))
                        lk = True
        if lk:
            something_changed = True
            what_changed.append('16.LINK')

        list_contact(contact_keep, False)
        if something_changed:
            print 'CHANGED FIELDS TO THIS CONTACT: %s' % what_changed
        else:
            print '[NO CHANGES]: 2nd contact have less or same items.'
        if not direct:
            debug("|>|>|> It seems everything is ok... Update?")
        if something_changed:
            updated = change_contact(contact_keep)
            print 'Updated: [%s]' % updated.updated.text
            # if sleep_on:
            time.sleep(3)  # This is to avoid etag mismatch when google is slow to update contact
        else:
            print "|> |> |>  No changes made the original contact. Does not need to update. <| <| <|"
        remove_contact(contact_remove)
    else:
        print 'Contacts are not the same (not same e-mail, not same profile link)...'


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def enter_or_quit():
    val = raw_input('Press ENTER to continue... (q)uit: ').lower()
    if val == 'q':
        bye()


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def check_field_dupes(contact_entry, target):
    line1 = deep_get_attribute(contact_entry, 'id.text') + ';' + \
            deep_get_attribute(contact_entry, 'name.full_name.text') + ';'
    for udf0 in contact_entry.event:
        line3 = line1 + (udf0.rel if udf0.rel is not None else udf0.label) + ' | ' + udf0.when.start + '\n'
        target.write(line3)
    for udf1 in contact_entry.user_defined_field:
        line3 = line1 + udf1.key + ' | ' + udf1.value + '\n'
        target.write(line3)
    for udf2 in contact_entry.website:
        line3 = line1 + (udf2.rel if udf2.rel is not None else udf2.label) + ' | ' + udf2.href + '\n'
        target.write(line3)
    for udf3 in contact_entry.im:
        line3 = line1 + udf3.protocol + ' | ' + udf3.address + '\n'
        target.write(line3)
    for udf4 in contact_entry.link:
        line3 = line1 + udf4.rel + ' | ' + udf4.href + '\n'
        target.write(line3)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def batch_rename_from_list(feed):
    # batch change 'Name_'  or  '_Name_'  or 'Name_'	(case sensitive)
    rf = open('batch_rename.txt')
    lines = rf.readlines()
    for contact_entry in feed.entry:
        var = deep_get_attribute(contact_entry, 'name.full_name.text')
        for line in lines:
            # TODO: TASK: CHECK STRING IS NOT TRIMMED, IT MUST NOT BE TRIMMED!
            old, new = line.split(',')
            if old in var:
                new = new.decode('windows-1252')
                new = new.rstrip()
                print '__________________________________________________________'
                var = deep_get_attribute(contact_entry, 'id.text')
                if var != 'empty':
                    print 'MAIN:[%s]' % (cplus_url + var.rstrip().rsplit('/', 1)[-1])
                print 'OLD NAME:[%s]' % contact_entry.name.full_name.text
                contact_entry.name.full_name.text = contact_entry.name.full_name.text.replace(old, new)
                print 'NEW NAME:[%s]' % contact_entry.name.full_name.text
                updated = change_contact(contact_entry)
                print 'Updated: [%s]' % updated.updated.text
                # if sleep_on:
                time.sleep(3)  # This is to avoid etag mismatch when google is slow to update contact
    rf.close()


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def batch_rename(feed, old, new):
    # batch change 'Name_'  or  '_Name_'  or 'Name_'	(case sensitive)
    for contact_entry in feed.entry:
        var = deep_get_attribute(contact_entry, 'name.full_name.text')
        if old in var:
            print '__________________________________________________________'
            var = deep_get_attribute(contact_entry, 'id.text')
            if var != 'empty':
                print 'MAIN:[%s]' % (cplus_url + var.rstrip().rsplit('/', 1)[-1])
            print 'OLD NAME:[%s]' % contact_entry.name.full_name.text
            contact_entry.name.full_name.text = contact_entry.name.full_name.text.replace(old, new)
            print 'NEW NAME:[%s]' % contact_entry.name.full_name.text
            updated = change_contact(contact_entry)
            print 'Updated: [%s]' % updated.updated.text
            # if sleep_on:
            time.sleep(3)  # This is to avoid etag mismatch when google is slow to update contact


# FORMAT ALL PHONE NUMBERS FROM ALL CONTACTS
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def batch_format_phones(feed):
    phone_tabs = 61
    phone_changed = False
    for contact_entry in feed.entry:
        phone_list = []
        for udf in contact_entry.phone_number:
            phone_list.append('PHNE: [%s]%s[%s]' %
                              (udf.text,
                               ' '*(phone_tabs-len(udf.text)) if len(udf.text) < phone_tabs else ' ',
                               udf.rel if udf.rel is not None else udf.label))
            phone_changed = True
            udf.text = get_num_format(udf.text)
            # udf.text = None
            # contact_entry.phone_number.append(get_num_format(udf.text))
        if phone_changed:
            dt = deep_get_attribute(contact_entry, 'birthday.when')
            if dt != 'empty':
                birth = is_valid_date(contact_entry.birthday.when)
                if birth is not True:
                    last_five = contact_entry.birthday.when[-5:]
                    test_number = int(last_five[:2])
                    if test_number <= 12:
                        new_date = '1900-' + last_five[:2] + '-' + contact_entry.birthday.when[-2:]
                    else:
                        new_date = '1900-' + contact_entry.birthday.when[-2:] + '-' + last_five[:2]
                    birth = is_valid_date(new_date)
                    if birth:
                        contact_entry.birthday.when = new_date
                    else:
                        contact_entry.birthday.when = ''
            print '__________________________________________________________'
            var = deep_get_attribute(contact_entry, 'id.text')
            if var != 'empty':
                print 'MAIN:[%s]' % (cplus_url + var.rstrip().rsplit('/', 1)[-1])
            var = deep_get_attribute(contact_entry, 'name.full_name.text')
            if var != 'empty':
                print 'NAME:[%s]' % var
            for udf in phone_list:
                print udf
            print '__________________________________________________________'
            for udf in contact_entry.phone_number:
                print 'PHNE: [%s]%s[%s]' % (udf.text,
                                            ' '*(phone_tabs-len(udf.text)) if len(udf.text) < phone_tabs else ' ',
                                            udf.rel if udf.rel is not None else udf.label)
            updated = change_contact(contact_entry)
            print 'Updated: [%s]' % updated.updated.text
            phone_changed = False
            # if sleep_on:
            time.sleep(2)  # This is to avoid etag mismatch when google is slow to update contact


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def read_file(file_name):
    rf = open(file_name)
    lines = rf.readlines()
    i = 0
    target = codecs.open('contactlist.txt', 'w', 'utf-8')
    for line in lines:
        i += 1
        target.write('[' + str(i) + '][' + line.rstrip() + ']\n')
        # list_contact(get_contact(line.rstrip()), true)
        write_contact(get_contact(line.rstrip()), target)
    target.close()
    rf.close()


class Index(object):
    def GET(self):
        get_token()
        return render.success_form()

    def POST(self):
        form = web.input(greet="Hello")
        greeting = "%s" % form.greet
        return render.index(greeting=greeting)


class success:
    def GET(self):
        return render.done_form()


class oauth2callback:
    def GET(self):
        form = web.input(code="mycode")
        try:
            access(form.code)
        except Exception, e:
            print e
        pass
        web.seeother(SUCCESS)
        return render.done_form()


# ==================================================================================================================
# TEST AREA - EACH ONE FOUND HERE IS JUST FOR TESTING PURPOSES AND THEY ARE NOT REALLY BEING USED INTO THIS PROJECT
# ==================================================================================================================


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def mongodb():
    db_client = MongoClient()
    db = db_client.test_database
    post = {"author": "Mike", "text": "My first blog post!",
            "tags": ["mongodb", "python", "pymongo"], "date": datetime.datetime.utcnow()}
    posts = db.posts
    post_id = posts.insert_one(post).inserted_id
    db.collection_names(include_system_collections=False)
    posts.find_one()
    posts.find_one({"author": "Mike"})
    posts.find_one({"author": "Eliot"})
    posts.find_one({"_id": post_id})
    post_id_as_str = str(post_id)
    posts.find_one({"_id": post_id_as_str})
    document = db_client.db.collection.find_one({'_id': ObjectId(post_id)})
    print document
    new_posts = [{"author": "Mike",
                  "text": "Another post!",
                  "tags": ["bulk", "insert"],
                  "date": datetime.datetime(2009, 11, 12, 11, 14)},
                 {"author": "Eliot",
                  "title": "MongoDB is fun",
                  "text": "and pretty easy too!",
                  "date": datetime.datetime(2009, 11, 10, 10, 45)}]
    result = posts.insert_many(new_posts)
    print result.inserted_ids
    for post in posts.find():
        print post
    for post in posts.find({"author": "Mike"}):
        print post
    posts.count()
    posts.find({"author": "Mike"}).count()
    d = datetime.datetime(2009, 11, 12, 12)
    for post in posts.find({"date": {"$lt": d}}).sort("author"):
        print post
    print posts.find({"date": {"$lt": d}}).sort("author").explain()["cursor"]
    print posts.find({"date": {"$lt": d}}).sort("author").explain()["nscanned"]
    posts.create_index([("date", DESCENDING), ("author", ASCENDING)])
    print posts.find({"date": {"$lt": d}}).sort("author").explain()["cursor"]
    print posts.find({"date": {"$lt": d}}).sort("author").explain()["nscanned"]
    employees = db["employees"]
    employees.insert({"name": "Lucas Hightower", 'gender': 'm', 'phone': '520-555-1212', 'age': 8})
    cursor = db.employees.find()
    print cursor
    for employee in db.employees.find():
        print employee
    print employees.find({"name": "Rick Hightower"})[0]
    cursor = employees.find({"age": {"$lt": 35}})
    for employee in cursor:
        print "under 35: %s" % employee
    diana = employees.find_one({"_id": ObjectId("4f984cce72320612f8f432bb")})
    print "Diana %s" % diana


# CREATE
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def create_contact():
    new_contact = gdata.contacts.data.ContactEntry()
    new_contact.title = set_title('My Title')
    new_contact.occupation = set_occupation('My Occupation')
    new_contact.organization.job_description = set_job('My Job Description')
    new_contact.gender = set_gender('male')
    new_contact.website.append(set_web_rel('profile', 'www.my_url.com'))
    new_contact.relation.append(set_relation('brother', 'My Brother'))
    new_contact.event.append(set_event('anniversary', '2009-09-09'))
    new_contact.organization = set_org('Work', 'true', 'My Company', 'My Role')
    new_contact.name = set_name('My Name')
    new_contact.content = set_note('My Note')
    new_contact.email.append(set_email('My EMail Name', 'email@my.mail', 'true', 'h'))
    new_contact.phone_number.append(set_phone('206 555 120 120', 'true', 'ho'))
    new_contact.im.append(set_im('sim_id', 'Other'))
    new_contact.nickname = set_nick('nick name')
    new_contact.birthday = set_birth('2009-07-23')
    new_contact.user_defined_field.append(set_custom('Key1', 'Value1'))
    new_contact.structured_postal_address.append(set_postal('h', 'rua1', 'cidade1', 'estado1', 'cep1', 'pais1', 'true'))
    new_contact.group_membership_info.append(set_main_group())
    return add_contact(new_contact)


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def print_all_groups():
    global client
    feed = client.GetGroups()
    for entry in feed.entry:
        print 'Atom Id: %s' % entry.id.text
        print 'Group Name: %s' % entry.title.text
        print 'Last Updated: %s' % entry.updated.text
        print 'Extended Properties:'
        for extended_property in entry.extended_property:
            if extended_property.value:
                value = extended_property.value
            else:
                value = extended_property.GetXmlBlob()
            print '  %s = %s' % (extended_property.name, value)
        print 'Self Link: %s' % entry.GetSelfLink().href
        if not entry.system_group:
            print 'Edit Link: %s' % entry.GetEditLink().href
            print 'ETag: %s' % entry.etag
        else:
            print 'System Group Id: %s' % entry.system_group.id


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def print_query_results():
    query = gdata.contacts.client.ContactsQuery()
    query.max_results = max_result
    query.start_index = 1
    # query['sortorder'] = "ascending"
    # query.sort_order = 'ascending'
    # query.sortorder = 'ascending'
    # query. = '2008-01-01'
    # query['showdeleted'] = 'true'
    # query.orderby = 'lastmodified'
    # query.group = 'atomid'
    # query.updated_min = '2008-01-01'
    global client
    feed = client.GetContacts(q=query)
    for contact in feed.entry:
        print contact.name.full_name
        print 'Updated on %s' % contact.updated.text


# GET MEMBERSHIP
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def print_group_membership_info(contact_url):
    global client
    contact = client.GetContact(contact_url)
    for group_membership_info in contact.group_membership_info:
        print "Group's Atom ID: %s" % group_membership_info.href


# TODO: <<<WRITE A DESCRIPTION HERE>>>
def list_min_feed(feed):
    for i, entry in enumerate(feed.entry):
        print '\n%s) %s' % (i+1, entry.name.full_name.text)
        if entry.content:
            print '%s' % entry.content.text
        for email in entry.email:
            # Display the primary email address for the contact.
            if email.primary and email.primary == 'true':
                print '    %s' % email.address
        # Show the contact groups that this contact is a member of.
        for group in entry.group_membership_info:
            print '    Member of group: %s' % group.href
        # Display extended properties.
        for extended_property in entry.extended_property:
            if extended_property.value:
                print extended_property.value
            else:
                print '    Extended Property - %s: %s' % (extended_property.name, extended_property.GetXmlBlob())


# PRINT CONTACTS
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def print_contacts():
    global client
    print client.get_contacts()
    for i, entry in enumerate(client.entry):
        print entry.name.full_name


# LIST MAX CONTACTS
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def max_res(total):
    query = gdata.contacts.client.ContactsQuery()
    query.max_results = total
    global client
    feed = client.GetContacts(q=query)
    list_feed(feed)
    return feed


# SET MEMBERSHIP
# TODO: <<<WRITE A DESCRIPTION HERE>>>
def add_group_membership(contact_url, group_atom_id):
    global client
    contact = get_contact(contact_url)
    contact.group_membership_info.append(gdata.contacts.data.GroupMembershipInfo(href=group_atom_id))
    return change_contact(contact)


# ===========================================
# Runs application when it is directly called
if __name__ == "__main__":
    app.run()

# ==================================================================================================================== #
