from vcs.osc import OSC

class VCS(object):
    """Base class for VCS implementations"""

    def get_file(self, *_args):
        """Get a file from the repository."""
        raise NotImplementedError
