#This file is part of getmail module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval, Equal, Not
from datetime import datetime
import logging
import re
import email
import base64

try:
    import easyimap
except ImportError:
    message = 'Unable to import easyimap'
    logging.getLogger('GetMail').error(message)
    raise Exception(message)

__all__ = ['GetmailServer']


class GetmailServer(ModelSQL, ModelView):
    'Getmail Server'
    __name__ = 'getmail.server'
    name = fields.Char('Name', required=True)
    active = fields.Boolean('Active', states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    state = fields.Selection([
            ('draft', 'Draft'),
            ('done', 'Done'),
            ], 'State', readonly=True)
    server = fields.Char('Server', required=True, states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    port = fields.Integer('Port', required=True, states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, on_change_with=['ssl', 'type'])
    folder = fields.Char('Folder', states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    limit = fields.Integer('Limit', states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
            help='Total emails by connection. Default is 10')
    type = fields.Selection([
#            ('pop', 'POP Server'),
            ('imap', 'IMAP Server')
            ], 'Server Type', required=True, states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    ssl = fields.Boolean('SSL', states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    attachment = fields.Boolean('Add Attachments',
            help='Fetches mail with attachments if true.')
    username = fields.Char('User Name', required=True, states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    password = fields.Char('Password', required=True, states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    note = fields.Text('Description')
    model = fields.Many2One('ir.model', 'Model', required=True, states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
            help='Select a model have getmail method.')
    priority = fields.Integer('Server Priority', states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
            help='Priority between 0 to 10, define the order of Processing')

    @classmethod
    def __setup__(cls):
        super(GetmailServer, cls).__setup__()
        cls._constraints += [
            ('check_model', 'check_model'),
            ]
        cls._sql_constraints += [
            ('account_uniq', 'UNIQUE(username)',
                'The email account must be unique!'),
        ]
        cls._error_messages.update({
            'pop_successful': 'POP3 Test Connection was successful',
            'pop_error': 'Error POP3 Server:\n%s',
            'imap_successful': 'IMAP Test Connection was successful',
            'imap_error': 'Error IMAP Server:\n%s',
            'unimplemented_protocol': 'This protocol is not implemented yet.',
            'check_model': 'Don\'t available "getmail" method in model.',
            'check_folder': 'Don\'t available folder in Email Server.',
        })
        cls._buttons.update({
            'done': {
                'invisible': Eval('state') == 'done',
                },
            'draft': {
                'invisible': Eval('state') == 'draft',
                },
            'get_server_test': {
                },
            'get_server_emails': {
                'invisible': Eval('state') == 'draft',
                },
        })

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_priority():
        return 5

    @staticmethod
    def default_type():
        return 'imap'

    @staticmethod
    def default_attach():
        return False

    @staticmethod
    def default_port():
        return 993

    def on_change_with_port(self):
        res = 0
        if self.type == 'imap':
            res = self.ssl and 993 or 143
        return res

    @classmethod
    @ModelView.button
    def done(cls, servers):
        done = []
        for server in servers:
            done.append(server)
        cls.write(done, {
            'state': 'done',
            })

    @classmethod
    @ModelView.button
    def draft(cls, servers):
        draft = []
        for server in servers:
            draft.append(server)
        cls.write(draft, {
            'state': 'draft',
            })

    @classmethod
    @ModelView.button
    def get_server_test(cls, servers):
        '''Get server connection'''
        for server in servers:
            if server.type == 'imap':
                folder = server.folder or 'INBOX'
                try:
                    imapper = easyimap.connect(
                        server.server,
                        server.username,
                        server.password,
                        folder)
                    imapper.quit()
                except Exception, e:
                    cls.raise_user_error('imap_error', e)
                cls.raise_user_error('imap_successful')
            else:
                cls.raise_user_error('unimplemented_protocol')

    @classmethod
    @ModelView.button
    def get_server_emails(self, servers):
        '''Get emails from server and call getmail method'''
        for server in servers:
            messages = []
            limit = server.limit or 10
            if server.type == 'imap':
                folder = server.folder or 'INBOX'
                try:
                    imapper = easyimap.connect(
                        server.server,
                        server.username,
                        server.password,
                        folder)
                    #messages = imapper.listup(20)
                    messages = imapper.unseen(limit)
                    imapper.quit()
                except Exception, e:
                    self.raise_user_error('imap_error', e)
            else:
                self.raise_user_error('unimplemented_protocol')
            logging.getLogger('Getmail').info(
                'Process %s email(s) from %s' % (
                    len(messages),
                    server.name,
                ))
            model_name = server.model.model
            model = Pool().get(model_name)
            model.getmail(messages,
                attachments=server.attachment)

    @classmethod
    def check_model(cls, servers):
        '''Check model must contain getmail method.'''
        for server in servers:
            model_name = server.model.model
            model = Pool().get(model_name)
            if hasattr(model, 'getmail'):
                return True
            return False

    @classmethod
    def getmail_servers(cls):
        """
        Cron download email from servers:
        - Active
        - State: Done
        """
        servers = cls.search([('state', '=', 'done'), ('active', '=', True)])
        cls.get_server_emails(servers)
        return True

    @staticmethod
    def get_party_from_email(email):
        party = None
        address = None
        cmechanism = Pool().get('party.contact_mechanism').search([
            ('type', '=', 'email'),
            ('value', 'in', email),
            ], limit=1)
        if cmechanism:
            party = cmechanism[0].party
            if cmechanism[0].address:
                address = cmechanism[0].address
        return party, address

    @staticmethod
    def get_email(text):
        return re.findall(r'([^ ,<@]+@[^> ,]+)', text)

    @staticmethod
    def get_date(date):
        date_tz = email.utils.parsedate_tz(date)
        return datetime(*date_tz[:6])
