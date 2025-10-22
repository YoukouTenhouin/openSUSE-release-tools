#!/usr/bin/python3
import datetime
import sys
from datetime import datetime, date, timedelta
import cmdln
import json
from xml.etree import ElementTree as ET

import osc.core
from plat.gitea import Request as GiteaRequest

import ReviewBot

class SourceOBS(ReviewBot.ReviewBot):
    def __init__(self, *args, **kwargs):
        ReviewBot.ReviewBot.__init__(self, *args, **kwargs)
        # TODO
        pass

    def _search_requests_obs(self, ns):
        # XXX make this work on Gitea
        since = date.today() - timedelta(days=1)
        since = since.strftime('%Y-%m-%d')
        xquery = f"starts-with(action/target/@project,'{ns}') and (state/@name='new' or state/@name='review' or state/@name='accepted') and state/@when>='{since}'"
        xmlresult = osc.core.search(self.apiurl, None, request=xquery)['request']
        for i in xmlresult.iter('request'):
            req = osc.core.Request()
            req.read(i)
            yield req

    def _list_orgs_git(self):
        # List all organizations on gitea
        # TODO: move this into platform interface
        params = {"page": 1}
        while True:
            res = self.platform.api.get('orgs', params=params).json()

            if not res:
                return

            for i in res:
                # print("Org", i["name"])
                yield i

            params["page"] += 1

    def _list_repos_git(self, org):
        # List all repos under a given organization
        # TODO: move this into platform interface
        params = {"page": 1}
        while True:
            res = self.platform.api.get(f'orgs/{org}/repos', params=params).json()

            if not res:
                return

            for i in res:
                # print("Repo", org, i["name"])
                yield i

            params["page"] += 1

    def _list_reqs_git(self, org, repo, params={}):
        # List all PRs under a given repository
        # TODO: move this into platform interface
        params["page"] = 1
        while True:
            res = self.platform.api.get(
                f'repos/{org}/{repo}/pulls',
                params=params,
                raise_for_status=False
            )
            if res.status_code == 404:
                # Some repositories does not contain any data. Skip those
                # for now.
                return
            res.raise_for_status()
            res = res.json()

            if not res:
                return

            for json in res:
                # print("Req", org, repo, json["number"])
                # print(json)
                ret = GiteaRequest()
                ret.read(json, org, repo)
                yield ret

            params["page"] += 1

    def _search_requests_git(self, ns):
        since = date.today() - timedelta(days=1)
        for org in self._list_orgs_git():
            # TODO: filter by ns on gitea
            for repo in self._list_repos_git(org["name"]):
                for req in self._list_reqs_git(
                        org["name"], repo["name"],
                        params={"sort": "recentupdate"}
                ):
                    updated_at = datetime.fromisoformat(req.updated_at).date()
                    if since > updated_at:
                        break
                    yield req

    def _search_requests(self, ns):
        if self.platform_type == "OBS":
            return self._search_requests_obs(ns)
        elif self.platform_type == "GITEA":
            return self._search_requests_git(ns)
        else:
            raise NotImplementedError()

    def do_fetch(self, opts, cmdopts):
        requests = self._search_requests(cmdopts.namespace)
        for req in requests:
            actions = []
            for action in req.actions:
                a = {}
                if hasattr(action, 'src_package'):
                    a["sourcepackage"] = action.src_package,
                if hasattr(action, 'src_project'):
                    a["sourceproject"] = action.src_project,
                if hasattr(action, 'tgt_package'):
                    a["targetpackage"] = action.tgt_package,
                if hasattr(action, 'tgt_project'):
                    a["targetproject"] = action.tgt_project,
                actions.append(a)
            print(json.dumps({
                "request": req.reqid,
                "actions": actions
            }))

class CommandLineInterface(ReviewBot.CommandLineInterface):
    def __init__(self, *args, **kwargs):
        ReviewBot.CommandLineInterface.__init__(self, *args, **kwargs)
        self.clazz = SourceOBS

    @cmdln.option('-n', '--namespace', default='openSUSE:', help='Namespace to fetch requests from')
    def do_fetch(self, subcmd, opts, *args):
        self.checker.do_fetch(self.options, opts)

if __name__ == "__main__":
    app = CommandLineInterface()
    sys.exit(app.main())
