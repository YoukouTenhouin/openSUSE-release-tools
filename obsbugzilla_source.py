#!/usr/bin/python3
import datetime
import sys
from datetime import datetime, timedelta, timezone
import cmdln
import json

import osc.core

import ReviewBot

class SourceOBS(ReviewBot.ReviewBot):
    def __init__(self, *args, **kwargs):
        ReviewBot.ReviewBot.__init__(self, *args, **kwargs)
        # TODO
        pass

    def _search_requests_obs(self, ns, since, **kwargs):
        since = since.strftime('%Y-%m-%d')
        xquery = f"starts-with(action/target/@project,'{ns}') and (state/@name='new' or state/@name='review' or state/@name='accepted') and state/@when>='{since}'"
        xmlresult = osc.core.search(self.apiurl, None, request=xquery)['request']
        for i in xmlresult.iter('request'):
            req = osc.core.Request()
            req.read(i)
            yield req

    def _search_requests_gitea(self, since, **kwargs):
        params = {
            "type": "pulls",
            "state": "open",
            "sort": "recentupdate",
            "since": since.isoformat("T")
        }
        return self.platform.search(params)

    def _search_requests(self, **kwargs):
        if self.platform_type == "OBS":
            return self._search_requests_obs(**kwargs)
        elif self.platform_type == "GITEA":
            return self._search_requests_gitea(**kwargs)
        else:
            raise NotImplementedError()

    def do_fetch(self, opts, cmdopts):
        if cmdopts.since:
            since = datetime.fromisoformat(cmdopts.since)
        else:
            since = datetime.now(timezone.utc) - timedelta(days=1)
        requests = self._search_requests(ns=cmdopts.namespace, since=since)
        for req in requests:
            actions = []
            for action in req.actions:
                a = {}
                if hasattr(action, 'src_package'):
                    a["sourcepackage"] = action.src_package
                if hasattr(action, 'src_project'):
                    a["sourceproject"] = action.src_project
                if hasattr(action, 'tgt_package'):
                    a["targetpackage"] = action.tgt_package
                if hasattr(action, 'tgt_project'):
                    a["targetproject"] = action.tgt_project
                actions.append(a)
            print(json.dumps({
                "request": req.reqid,
                "title": req.title,
                "body": req.description,
                "actions": actions
            }))

class CommandLineInterface(ReviewBot.CommandLineInterface):
    def __init__(self, *args, **kwargs):
        ReviewBot.CommandLineInterface.__init__(self, *args, **kwargs)
        self.clazz = SourceOBS

    @cmdln.option('-n', '--namespace', default='openSUSE:', help='Namespace to fetch requests from')
    @cmdln.option('--since', help='only check pull requests after the given time.')
    def do_fetch(self, subcmd, opts, *args):
        self.checker.do_fetch(self.options, opts)

if __name__ == "__main__":
    app = CommandLineInterface()
    sys.exit(app.main())
