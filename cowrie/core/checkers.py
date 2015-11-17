# Copyright (c) 2009-2014 Upi Tamminen <desaster@gmail.com>
# See the COPYRIGHT file for more information

"""
This module contains ...
"""

from sys import modules

from zope.interface import implements

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import ISSHPrivateKey
from twisted.cred.error import UnauthorizedLogin, UnhandledCredentials
from twisted.internet import defer
from twisted.python import log, failure
from twisted.conch import error
from twisted.conch.ssh import keys

from cowrie.core import credentials
from cowrie.core import auth

class HoneypotPublicKeyChecker:
    """
    Checker that accepts, logs and denies public key authentication attempts
    """
    implements(ICredentialsChecker)

    credentialInterfaces = (ISSHPrivateKey,)

    def __init__(self, cfg):
        pass

    def requestAvatarId(self, credentials):
        _pubKey = keys.Key.fromString(credentials.blob)
        log.msg(format='public key attempt for user %(username)s with fingerprint %(fingerprint)s',
                eventid='KIPP0016',
                username=credentials.username,
                fingerprint=_pubKey.fingerprint())
        return failure.Failure(error.ConchError('Incorrect signature'))

class HoneypotNoneChecker:
    """
    Checker that does no authentication check
    """
    implements(ICredentialsChecker)

    credentialInterfaces = (credentials.IUsername,)

    def __init__(self):
        pass

    def requestAvatarId(self, credentials):
        return defer.succeed(credentials.username)

class HoneypotPasswordChecker:
    """
    Checker that accepts "keyboard-interactive" and "password"
    """
    implements(ICredentialsChecker)

    credentialInterfaces = (credentials.IUsernamePasswordIP,
        credentials.IPluggableAuthenticationModulesIP)

    def __init__(self, cfg):
        self.cfg = cfg

    def requestAvatarId(self, credentials):
        if hasattr(credentials, 'password'):
            if self.checkUserPass(credentials.username, credentials.password,
                                  credentials.ip):
                return defer.succeed(credentials.username)
            else:
                return defer.fail(UnauthorizedLogin())
        elif hasattr(credentials, 'pamConversion'):
            return self.checkPamUser(credentials.username,
                                     credentials.pamConversion, credentials.ip)
        return defer.fail(UnhandledCredentials())

    def checkPamUser(self, username, pamConversion, ip):
        r = pamConversion((('Password:', 1),))
        return r.addCallback(self.cbCheckPamUser, username, ip)

    def cbCheckPamUser(self, responses, username, ip):
        for (response, zero) in responses:
            if self.checkUserPass(username, response, ip):
                return defer.succeed(username)
        return defer.fail(UnauthorizedLogin())

    def checkUserPass(self, theusername, thepassword, ip):
        #  UserDB is the default auth_class
        authname = auth.UserDB

        # Is the auth_class defined in the config file?
        if self.cfg.has_option('honeypot', 'auth_class'):
            authclass = self.cfg.get('honeypot', 'auth_class')
            authmodule = "cowrie.core.auth"

            # Check if authclass exists in this module
            if hasattr(modules[authmodule], authclass):
                authname = getattr(modules[authmodule], authclass)
            else:
                log.msg('auth_class: %s not found in %s' % (authclass, authmodule))

        theauth = authname(self.cfg)

        if theauth.checklogin(theusername, thepassword, ip):
            log.msg(eventid='KIPP0002',
                format='login attempt [%(username)s/%(password)s] succeeded',
                username=theusername, password=thepassword)
            return True
        else:
            log.msg(eventid='KIPP0003',
                format='login attempt [%(username)s/%(password)s] failed',
                username=theusername, password=thepassword)
            return False

# vim: set sw=4 et:
