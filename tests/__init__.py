# This file is part getmail module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
try:
    from trytond.modules.getmail.tests.test_getmail import suite
except ImportError:
    from .test_getmail import suite

__all__ = ['suite']
