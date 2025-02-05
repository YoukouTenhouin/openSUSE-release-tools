import plat.base

from dateutil.parser import parse as date_parse
import os
import json

class CommentAPI:
    """Stub CommentAPI implementation"""
    def __init__(self):
        pass

    def get_comments(self, request_id):
        return {}

    def request_as_comment_dict(self, request):
        return {
            'who': request.creator,
            'when': date_parse(request.created_at),
            'id': '-1',
            'parent': None,
            'comment': request.description,
        }

    def comment_find(self, comments, bot, info_match=None):
        return None, None

    def command_find(self, comments, user, command, who_allowed):
        if False: yield

class RequestAction:
    """Stub action structure for running as an Gitea Action"""
    def __init__(
            self,
            src_project,
            src_package,
            src_rev,
            dst_project,
            dst_package,
   ):
        self.type = "submit" # XXX is there any other types when running as an action?
        self.src_project = src_project
        self.src_package = src_package
        self.src_rev = src_rev
        self.tgt_project = dst_project
        self.tgt_package = dst_package

class Request:
    """Stub request structure for running as an Gitea Action"""
    def __init__(self):
        context = _read_context()

        pr = context["event"]["pull_request"]
        src_full_name = pr["head"]["repo"]["full_name"]
        src_project, src_package = src_full_name.split('/', 1)
        src_rev = context["sha"]
        dst_full_name = pr["base"]["repo"]["full_name"]
        dst_project, dst_package = dst_full_name.split('/', 1)
        creator = pr["user"]["login"]
        created_at = pr["created_at"]
        description = pr["body"]

        self.reqid = '1'
        self.actions = [RequestAction(src_project, src_package, src_rev, dst_project, dst_package)]
        self.creator = creator
        self.created_at = created_at
        self.description = description
        self.reviews = []

def _read_context():
    env = os.environ["GITHUB_CONTEXT"]
    return json.loads(env)

class Action(plat.base.PlatformBase):
    """Platform interface implementation for running as Gitea Actions"""
    def __init__(self, logger):
        self.logger = logger
        self.comment_api = CommentAPI()

    @staticmethod
    def get_stub_request():
        return Request()

    @property
    def name(self) -> str:
        return "ACTION"

    def get_request(self, request_id, with_full_history=False):
        # thanks to duck-typing we can return a stub request struct
        return Action.get_stub_request()
