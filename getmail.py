# This file is part of getmail module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from datetime import datetime
from email.utils import parseaddr
from email.header import decode_header
import easyimap
import email
import logging
from trytond.config import config
from trytond.model import ModelView, ModelSQL, DeactivableMixin, fields, Unique
from trytond.pool import Pool,PoolMeta
from trytond.pyson import Eval, Equal, Not
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.transaction import Transaction


logger = logging.getLogger(__name__)

QUEUE_NAME = config.get('electronic_mail', 'queue_name', default='default')


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super(Cron, cls).__setup__()
        cls.method.selection.extend([
            ('getmail.server|getmail_servers', "Get Mail Servers"),
        ])


class GetmailServer(DeactivableMixin, ModelSQL, ModelView):
    'Getmail Server'
    __name__ = 'getmail.server'
    name = fields.Char('Name', required=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('done', 'Done'),
            ], 'State', readonly=True)
    server = fields.Char('Server', required=True, states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    port = fields.Integer('Port', required=True, states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    folder = fields.Char('Folder', states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            })
    limit = fields.Integer('Limit', states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        help='Total emails by connection. Default is 10')
    timeout = fields.Integer('Time Out', states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        help='Default is 15')
    type = fields.Selection([
            #  ('pop', 'POP Server'),
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
    password = fields.Char('Password', required=True, strip=False, states={
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
        t = cls.__table__()
        cls._sql_constraints += [
            ('account_uniq', Unique(t, t.username),
                'The email account must be unique!'),
        ]
        cls.active.states.update({
                'readonly': Not(Equal(Eval('state'), 'draft')),
                })
        cls.active.depends.add('state')
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
    def default_priority():
        return 5

    @staticmethod
    def default_type():
        return 'imap'

    @staticmethod
    def default_ssl():
        return True

    @staticmethod
    def default_attachment():
        return False

    @staticmethod
    def default_port():
        return 993

    @fields.depends('ssl', 'type')
    def on_change_with_port(self):
        res = 0
        if self.type == 'imap':
            res = self.ssl and 993 or 143
        return res

    @classmethod
    @ModelView.button
    def done(cls, servers):
        cls.write(servers, {
            'state': 'done',
            })

    @classmethod
    @ModelView.button
    def draft(cls, servers):
        cls.write(servers, {
            'state': 'draft',
            })

    @classmethod
    @ModelView.button
    def get_server_test(cls, servers):
        '''Get server connection'''
        for server in servers:
            if server.type == 'imap':
                folder = server.folder or 'INBOX'
                timeout = server.timeout or 15
                try:
                    imapper = easyimap.connect(
                        server.server,
                        server.username,
                        server.password,
                        folder,
                        timeout,
                        server.ssl,
                        server.port,
                        )
                    imapper.quit()
                except Exception as e:
                    raise UserError(gettext('getmail.imap_error', error=e))
                raise UserError(gettext('getmail.imap_successful'))
            else:
                raise UserError(gettext('getmail.unimplemented_protocol'))

    @classmethod
    @ModelView.button
    def get_server_emails(self, servers):
        '''Get emails from server and call getmail method'''
        for server in servers:
            messages = []
            limit = server.limit or 10
            timeout = server.timeout or 15
            if server.type == 'imap':
                folder = server.folder or 'INBOX'
                try:
                    imapper = easyimap.connect(
                        server.server,
                        server.username,
                        server.password,
                        folder,
                        timeout,
                        server.ssl,
                        server.port,
                        )
                    #  messages = imapper.listup(20)
                    messages = imapper.unseen(limit)
                    imapper.quit()
                except Exception as e:
                    raise UserError(gettext('getmail.imap_error', error=e))
            else:
                raise UserError(gettext('getmail.unimplemented_protocol'))
            logger.info(
                'Process %s email(s) from %s' % (
                    len(messages),
                    server.name,
                ))
            model_name = server.model.model
            model = Pool().get(model_name)
            model.getmail(server, messages)

    @classmethod
    def validate(cls, servers):
        for server in servers:
            server.check_model()

    def check_model(self):
        '''Check model must contain getmail method.'''
        model_name = self.model.model
        model = Pool().get(model_name)
        if not hasattr(model, 'getmail'):
            raise UserError(gettext('get_mail.check_model',
                    model=self.model.rec_name,
                    server=self.rec_name,
                    ))

    @classmethod
    def getmail_servers(cls):
        """
        Cron download email from servers:
        - Active
        - State: Done
        """
        servers = cls.search([('state', '=', 'done'), ('active', '=', True)])
        with Transaction().set_context(queue_name=QUEUE_NAME):
            for server in servers:
                cls.__queue__.get_server_emails([server])
        return True

    @staticmethod
    def get_party_from_email(email):
        party = None
        address = None
        cmechanisms = Pool().get('party.contact_mechanism').search([
            ('type', '=', 'email'),
            ('value', '=', email),
            ], limit=1)
        if cmechanisms:
            party = cmechanisms[0].party
        return party, address

    @staticmethod
    def get_email(email):
        return parseaddr(email)[1]

    @staticmethod
    def get_date(date):
        '''Convert date from timezone'''
        if date:
            timestamp = email.utils.mktime_tz(email.utils.parsedate_tz(date))
            return datetime.fromtimestamp(timestamp)
        return datetime.now()

    @staticmethod
    def get_filename(fname):
        '''Decode filename acording email header'''
        name, encoding = decode_header(fname)[0]
        if encoding:
            return name.decode(encoding)
        return name
