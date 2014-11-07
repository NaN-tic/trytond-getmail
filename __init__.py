# This file is part getmail module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from .getmail import *


def register():
    Pool.register(
        GetmailServer,
        module='getmail', type_='model')