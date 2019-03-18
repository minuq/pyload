# -*- coding: utf-8 -*-
# AUTHOR: RaNaN, vuolter

import time

from queue import Queue

import pycurl
from ..network.exceptions import Abort, Fail, Reconnect, Retry, Skip

from .plugin_thread import PluginThread


class DownloadThread(PluginThread):
    """
    thread for downloading files from 'real' hoster plugins.
    """

    # ----------------------------------------------------------------------
    def __init__(self, manager):
        """
        Constructor.
        """
        super().__init__(manager)

        self.queue = Queue()  #: job queue
        self.active = False

        self.start()

    # ----------------------------------------------------------------------
    def run(self):
        """
        run method.
        """
        pyfile = None

        while True:
            del pyfile
            self.active = self.queue.get()
            pyfile = self.active

            if self.active == "quit":
                self.active = False
                self.m.threads.remove(self)
                return True

            try:
                if not pyfile.hasPlugin():
                    continue
                # this pyfile was deleted while queueing

                pyfile.plugin.checkForSameFiles(starting=True)
                self.pyload.log.info(self._("Download starts: {}".format(pyfile.name)))

                # start download
                self.pyload.addonManager.downloadPreparing(pyfile)
                pyfile.plugin.preprocessing(self)

                self.pyload.log.info(
                    self._("Download finished: {}").format(pyfile.name)
                )
                self.pyload.addonManager.downloadFinished(pyfile)
                self.pyload.files.checkPackageFinished(pyfile)

            except NotImplementedError:
                self.pyload.log.error(
                    self._("Plugin {} is missing a function").format(pyfile.pluginname)
                )
                pyfile.setStatus("failed")
                pyfile.error = "Plugin does not work"
                self.clean(pyfile)
                continue

            except Abort:
                pyfile.setStatus("aborted")
                self.pyload.log.info(self._("Download aborted: {}").format(pyfile.name))
                self.clean(pyfile)
                continue

            except Reconnect:
                self.queue.put(pyfile)
                # pyfile.req.clearCookies()

                while self.m.reconnecting.isSet():
                    time.sleep(0.5)

                continue

            except Retry as exc:
                reason = exc.args[0]
                self.pyload.log.info(
                    self._("Download restarted: {name} | {msg}").format(
                        name=pyfile.name, msg=reason
                    )
                )
                self.queue.put(pyfile)
                continue

            except Fail as exc:
                msg = exc.args[0]

                if msg == "offline":
                    pyfile.setStatus("offline")
                    self.pyload.log.warning(
                        self._("Download is offline: {}").format(pyfile.name)
                    )
                elif msg == "temp. offline":
                    pyfile.setStatus("temp. offline")
                    self.pyload.log.warning(
                        self._("Download is temporary offline: {}").format(pyfile.name)
                    )
                else:
                    pyfile.setStatus("failed")
                    self.pyload.log.warning(
                        self._("Download failed: {name} | {msg}").format(
                            name=pyfile.name, msg=msg
                        )
                    )
                    pyfile.error = msg

                self.pyload.addonManager.downloadFailed(pyfile)
                self.clean(pyfile)
                continue

            except pycurl.error as exc:
                if len(exc.args) == 2:
                    code, msg = exc.args
                else:
                    code = 0
                    msg = exc.args

                self.pyload.log.debug(f"pycurl exception {code}: {msg}")

                if code in (7, 18, 28, 52, 56):
                    self.pyload.log.warning(
                        self._(
                            "Couldn't connect to host or connection reset, waiting 1 minute and retry."
                        )
                    )
                    wait = time.time() + 60

                    pyfile.waitUntil = wait
                    pyfile.setStatus("waiting")
                    while time.time() < wait:
                        time.sleep(1)
                        if pyfile.abort:
                            break

                    if pyfile.abort:
                        self.pyload.log.info(
                            self._("Download aborted: {}").format(pyfile.name)
                        )
                        pyfile.setStatus("aborted")

                        self.clean(pyfile)
                    else:
                        self.queue.put(pyfile)

                    continue

                else:
                    pyfile.setStatus("failed")
                    self.pyload.log.error(
                        self._("pycurl error {}: {}").format(code, msg)
                    )
                    if self.pyload.debug:
                        self.writeDebugReport(pyfile)

                    self.pyload.addonManager.downloadFailed(pyfile)

                self.clean(pyfile)
                continue

            except Skip as exc:
                pyfile.setStatus("skipped")

                self.pyload.log.info(
                    self._("Download skipped: {name} due to {plugin}").format(
                        name=pyfile.name, plugin=exc
                    )
                )

                self.clean(pyfile)

                self.pyload.files.checkPackageFinished(pyfile)

                self.active = False
                self.pyload.files.save()

                continue

            except Exception as exc:
                pyfile.setStatus("failed")
                self.pyload.log.warning(
                    self._("Download failed: {name} | {msg}").format(
                        name=pyfile.name, msg=exc
                    ),
                    exc_info=self.pyload.debug > 1,
                    stack_info=self.pyload.debug > 2,
                )
                pyfile.error = str(exc)

                if self.pyload.debug:
                    self.writeDebugReport(pyfile)

                self.pyload.addonManager.downloadFailed(pyfile)
                self.clean(pyfile)
                continue

            finally:
                self.pyload.files.save()
                pyfile.checkIfProcessed()
                # exc_clear()

            # pyfile.plugin.req.clean()

            self.active = False
            pyfile.finishIfDone()
            self.pyload.files.save()

    def put(self, job):
        """
        assing job to thread.
        """
        self.queue.put(job)

    def stop(self):
        """
        stops the thread.
        """
        self.put("quit")