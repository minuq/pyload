# -*- coding: utf-8 -*-

import re

from urllib import unquote
from urlparse import urljoin, urlparse

from module.network.HTTPRequest import BadHeader
from module.plugins.internal.SimpleHoster import create_getInfo, fileUrl
from module.plugins.Hoster import Hoster


class BasePlugin(Hoster):
    __name__    = "BasePlugin"
    __type__    = "hoster"
    __version__ = "0.32"

    __pattern__ = r'^unmatchable$'

    __description__ = """Base Plugin when any other didnt fit"""
    __license__     = "GPLv3"
    __authors__     = [("RaNaN", "RaNaN@pyload.org"),
                       ("Walter Purcaro", "vuolter@gmail.com")]


    @classmethod
    def getInfo(cls, url="", html=""):  #@TODO: Move to hoster class in 0.4.10
        url = unquote(url)
        return {'name'  : (urlparse(url).path.split('/')[-1]
                           or urlparse(url).query.split('=', 1)[::-1][0].split('&', 1)[0]
                           or _("Unknown")),
                'size'  : 0,
                'status': 3 if url else 8,
                'url'   : url}


    def setup(self):
        self.chunkLimit     = -1
        self.resumeDownload = True


    def process(self, pyfile):
        """main function"""

        pyfile.name = self.getInfo(pyfile.url)['name']

        if not pyfile.url.startswith("http"):
            self.fail(_("No plugin matched"))

        for _i in xrange(5):
            try:
                link = fileUrl(self, unquote(pyfile.url))

                if link:
                    self.download(link, disposition=True)
                else:
                    self.fail(_("File not found"))

            except BadHeader, e:
                if e.code is 404:
                    self.offline()

                elif e.code in (401, 403):
                    self.logDebug("Auth required", "Received HTTP status code: %d" % e.code)

                    account = self.core.accountManager.getAccountPlugin('Http')
                    servers = [x['login'] for x in account.getAllAccounts()]
                    server  = urlparse(pyfile.url).netloc

                    if server in servers:
                        self.logDebug("Logging on to %s" % server)
                        self.req.addAuth(account.getAccountData(server)['password'])
                    else:
                        pwd = self.getPassword()
                        if ':' in pwd:
                            self.req.addAuth(pwd)
                        else:
                            self.fail(_("Authorization required"))
                else:
                    self.fail(e)
            else:
                break
        else:
            self.fail(_("No file downloaded"))  #@TODO: Move to hoster class in 0.4.10

        check = self.checkDownload({'empty file': re.compile(r'\A\Z'),
                                    'html file' : re.compile(r'\A\s*<!DOCTYPE html'),
                                    'html error': re.compile(r'\A\s*(<.+>)?\d{3}(\Z|\s+)')})
        if check:
            self.fail(check.capitalize())


getInfo = create_getInfo(BasePlugin)