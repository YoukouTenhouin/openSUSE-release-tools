import osc.core
from urllib.error import HTTPError

class OSC(object):
    """VCS interface implementation for OSC"""

    def __init__(self, apiurl=None):
        self.apiurl = apiurl

    def get_file(self, *args):
        try:
            url = osc.core.makeurl(self.apiurl, args)
            return osc.core.http_GET(url)
        except HTTPError as e:
            if e.code != 404:
                raise e
            return None
