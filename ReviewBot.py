#!/usr/bin/python3

import PackageLookup, ReviewChoices, CommentFromLogHandler, CommandLine from ReviewBotOBS
import ReviewBotOBS from ReviewBotOBS

class ReviewBot(object):
    """
    A generic obs request reviewer
    Inherit from this class and implement check functions for each action type:

    def check_action_<type>(self, req, action):
        return (None|True|False)
    """

    DEFAULT_REVIEW_MESSAGES = {'accepted': 'ok', 'declined': 'review failed'}
    REVIEW_CHOICES: Tuple[ReviewChoices, ...] = (
        ReviewChoices.NORMAL, ReviewChoices.NO, ReviewChoices.ACCEPT,
        ReviewChoices.ACCEPT_ONPASS, ReviewChoices.FALLBACK_ONFAIL, ReviewChoices.FALLBACK_ALWAYS
    )

    COMMENT_MARKER_REGEX = re.compile(r'<!-- (?P<bot>[^ ]+) state=(?P<state>[^ ]+)(?: result=(?P<result>[^ ]+))? -->')

    @attribute
    def config_defaults(self):
        return self.impl.config_defaults

    def __init__(self, *args, **kwargs):
        self.impl = ReviewBotOBS(*args, **kwargs)

    def load_config(self, filename=None):
        return self.impl.load_config(filename)

    def has_staging(self, project):
        return self.impl.has_staging(project)

    def staging_api(self, project):
        return self.impl.staging_api(project)

    @property
    def review_mode(self) -> ReviewChoices:
        return self.impl.review_mode

    @review_mode.setter
    def review_mode(self, value: Union[ReviewChoices, str]) -> None:
        self.impl.review_mode = value

    def set_request_ids(self, ids):
        self.impl.set_request_ids(ids)

    # function called before requests are reviewed
    def prepare_review(self):
        return self.impl.prepare_review(self)

    def check_requests(self):
        return self.impl.check_requests(self)

    def request_override_check_users(self, project: str) -> List[str]:
        return self.impl.request_override_check_users(project)

    def request_override_check(self, force: bool = False) -> Optional[bool]:
        return self.impl.request_override_check(self, force)

    def request_commands(self, command: str, who_allowed=None, request=None, action=None,
                         include_description=True) -> Generator[Tuple[List[str], Optional[str]], None, None]:
        return self.impl.request_commands(command, who_allowed, request, action, include_description)

    # allow_duplicate=True should only be used if it makes sense to force a
    # re-review in a scenario where the bot adding the review will rerun.
    # Normally a declined review will automatically be reopened along with the
    # request and any other bot reviews already added will not be touched unless
    # the issuing bot is rerun which does not fit normal workflow.
    def add_review(self, req, by_group=None, by_user=None, by_project=None, by_package=None,
                   msg=None, allow_duplicate=False):
        return self.impl.add_review(req, by_group, by_user, by_project, by_package, msg, allow_duplicate)

    def devel_project_review_add(self, request, project, package, message='adding devel project review'):
        return self.impl.devel_project_review_add(request, project, package, message)

    def devel_project_review_ensure(self, request, project, package, message='submitter not devel maintainer'):
        return self.impl.devel_project_review_ensure(request, project, package, message)

    def devel_project_review_needed(self, request, project, package):
        return self.impl.devel_project_review_needed(request, project, package)

    def check_one_request(self, req: osc.core.Request):
        return self.impl.check_one_request(req)

    def action_method(self, action: osc.core.Action):
        return self.impl.action_method(action)

    def review_message_key(self, result):
        return self.impl.review_message_key(result)

    def check_action_maintenance_incident(self, req, a):
        return self.impl.check_action_maintenance_incident(self, req, a)

    def check_action_maintenance_release(self, req: osc.core.Request, a: osc.core.Action):
        return self.impl.check_action_maintenance_release(req)

    def check_action_submit(self, req: osc.core.Request, a: osc.core.Action):
        return self.impl.check_action_submit(req)

    def check_action__default(self, req, a):
        return self.impl.check_action__default(req, a)

    def check_source_submission(self, src_project: str, src_package: str, src_rev: str, target_project: str, target_package: str) -> None:
        return self.impl.check_source_submission(src_project, src_package, src_rev, target_project, target_package)

    @staticmethod
    def _get_sourceinfo(apiurl, project, package, rev=None):
        # XXX: dispatch based on impl type
        return ReviewBotOBS._get_sourceinfo(apiurl, project, package, rev)

    def get_originproject(self, project, package, rev=None):
        return self.impl.get_originproject(project, package, rev)

    def get_sourceinfo(self, project, package, rev=None):
        return self.impl.get_sourceinfo(project, package, rev)

    def can_accept_review(self, request_id):
        """return True if there is a new review for the specified reviewer"""
        url = osc.core.makeurl(self.apiurl, ('request', str(request_id)))
        try:
            root = ET.parse(osc.core.http_GET(url)).getroot()
            if self.review_user and self._has_open_review_by(root, 'by_user', self.review_user):
                return True
            if self.review_group and self._has_open_review_by(root, 'by_group', self.review_group):
                return True
        except HTTPError as e:
            print(f'ERROR in URL {url} [{e}]')
        return False

    def set_request_ids_search_review(self):
        review = None
        if self.review_user:
            review = f"@by_user='{self.review_user}' and @state='new'"
        if self.review_group:
            review = osc.core.xpath_join(review, f"@by_group='{self.review_group}' and @state='new'")
        url = osc.core.makeurl(self.apiurl, ('search', 'request'), {
                               'match': f"state/@name='review' and review[{review}]", 'withfullhistory': 1})
        root = ET.parse(osc.core.http_GET(url)).getroot()

        self.requests = []

        for request in root.findall('request'):
            req = osc.core.Request()
            req.read(request)
            self.requests.append(req)

    # also used by openqabot
    def ids_project(self, project, typename):
        xpath = f"(state/@name='review' or state/@name='new') and (action/target/@project='{project}' and action/@type='{typename}')"
        url = osc.core.makeurl(self.apiurl, ('search', 'request'),
                               {'match': xpath,
                                'withfullhistory': 1})
        root = ET.parse(osc.core.http_GET(url)).getroot()

        ret = []

        for request in root.findall('request'):
            req = osc.core.Request()
            req.read(request)
            ret.append(req)
        return ret

    def set_request_ids_project(self, project, typename):
        self.requests = self.ids_project(project, typename)

    def comment_handler_add(self, level=logging.INFO):
        """Add handler to start recording log messages for comment."""
        self.comment_handler = CommentFromLogHandler(level)
        self.logger.addHandler(self.comment_handler)

    def comment_handler_remove(self):
        self.logger.removeHandler(self.comment_handler)

    def comment_handler_lines_deduplicate(self):
        self.comment_handler.lines = list(OrderedDict.fromkeys(self.comment_handler.lines))

    def comment_write(self, state='done', result=None, project=None, package=None,
                      request=None, message=None, identical=False, only_replace=False,
                      info_extra=None, info_extra_identical=True, bot_name_suffix=None):
        """Write comment if not similar to previous comment and replace old one.

        The state, result, and info_extra (dict) are combined to create the info
        that is passed to CommentAPI methods for creating a marker and finding
        previous comments. self.bot_name, which defaults to class, will be used
        as the primary matching key. When info_extra_identical is set to False
        info_extra will not be included when finding previous comments to
        compare message against.

        A comment from the same bot will be replaced when a new comment is
        written. The only_replace flag will restrict to only writing a comment
        if a prior one is being replaced. This can be useful for writing a final
        comment that indicates a change from previous uncompleted state, but
        only makes sense to post if a prior comment was posted.

        The project, package, and request variables control where the comment is
        placed. If no value is given the default is the request being reviewed.

        If no message is provided the content will be extracted from
        self.comment_handler.line which is provided by CommentFromLogHandler. To
        use this call comment_handler_add() at the point which messages should
        start being collected. Alternatively the self.comment_handler setting
        may be set to True to automatically set one on each request.

        The previous comment body line count is compared to see if too similar
        to bother posting another comment which is useful for avoiding
        re-posting comments that contain irrelevant minor changes. To force an
        exact match use the identical flag to replace any non-identical
        comment body.
        """
        if project:
            kwargs = {'project_name': project}
            if package:
                kwargs['package_name'] = package
        else:
            if request is None:
                request = self.request
            kwargs = {'request_id': request.reqid}
        debug_key = '/'.join(kwargs.values())

        if message is None:
            if not len(self.comment_handler.lines):
                self.logger.debug(f'skipping empty comment for {debug_key}')
                return
            message = '\n\n'.join(self.comment_handler.lines)

        bot_name = self.bot_name
        if bot_name_suffix:
            bot_name = '::'.join([bot_name, bot_name_suffix])

        info = {'state': state, 'result': result}
        if info_extra and info_extra_identical:
            info.update(info_extra)

        comments = self.comment_api.get_comments(**kwargs)
        comment, _ = self.comment_api.comment_find(comments, bot_name, info)

        if info_extra and not info_extra_identical:
            # Add info_extra once comment has already been matched.
            info.update(info_extra)

        message = self.comment_api.add_marker(message, bot_name, info)
        message = self.comment_api.truncate(message.strip())

        if self._is_comment_identical(comment, message, identical):
            # Assume same state/result and number of lines in message is duplicate.
            self.logger.debug(f'previous comment too similar on {debug_key}')
            return

        if comment is None:
            self.logger.debug(f'broadening search to include any state on {debug_key}')
            comment, _ = self.comment_api.comment_find(comments, bot_name)
        if comment is not None:
            self.logger.debug(f'removing previous comment on {debug_key}')
            if not self.dryrun:
                self.comment_api.delete(comment['id'])
        elif only_replace:
            self.logger.debug(f'no previous comment to replace on {debug_key}')
            return

        self.logger.debug(f'adding comment to {debug_key}: {message}')
        if not self.dryrun:
            self.comment_api.add_comment(comment=message, **kwargs)

        self.comment_handler_remove()

    def _is_comment_identical(self, comment, message, identical):
        if comment is None:
            return False
        if identical:
            # Remove marker from comments since handled during comment_find().
            return self.comment_api.remove_marker(comment['comment']) == self.comment_api.remove_marker(message)
        else:
            return comment['comment'].count('\n') == message.count('\n')

    def _check_matching_srcmd5(self, project, package, rev, history_limit=5):
        """check if factory sources contain the package and revision. check head and history"""
        self.logger.debug(f"checking {package} in {project}")
        try:
            osc.core.show_package_meta(self.apiurl, project, package)
        except (HTTPError, URLError):
            self.logger.debug("new package")
            return None

        si = self.get_sourceinfo(project, package)
        if rev == si.verifymd5:
            self.logger.debug("srcmd5 matches")
            return True

        if history_limit:
            self.logger.debug("%s not the latest version, checking history", rev)
            u = osc.core.makeurl(self.apiurl, ['source', project, package, '_history'], {'limit': history_limit})
            try:
                r = osc.core.http_GET(u)
            except HTTPError:
                self.logger.debug("package has no history!?")
                return None

            root = ET.parse(r).getroot()
            # we need this complicated construct as obs doesn't honor
            # the 'limit' parameter use above for obs interconnect:
            # https://github.com/openSUSE/open-build-service/issues/2545
            for revision, i in zip(reversed(root.findall('revision')), count()):
                node = revision.find('srcmd5')
                if node is None:
                    continue
                self.logger.debug(f"checking {node.text}")
                if node.text == rev:
                    self.logger.debug(f"got it, rev {revision.get('rev')}")
                    return True
                if i == history_limit:
                    break

            self.logger.debug("srcmd5 not found in history either")

        return False

    def request_age_wait(
            self,
            age_min: Optional[Union[str, int, float]] = None,
            request=None,
            target_project: Optional[str] = None
    ) -> bool:
        if not request:
            request = self.request

        if not target_project:
            target_project = self.action.tgt_project

        if age_min is None or isinstance(age_min, str):
            key = self.request_age_min_key if age_min is None else age_min
            age_min = int(Config.get(self.apiurl, target_project).get(key, self.request_age_min_default))

        age = request_age(request).total_seconds()
        if age < age_min:
            self.logger.info('skipping {} of age {:.2f}s since it is younger than {}s'.format(
                request.reqid, age, age_min))
            return True

        return False


class CommandLineInterface(cmdln.Cmdln):
    def __init__(self, *args, **kwargs):
        cmdln.Cmdln.__init__(self, args, kwargs)
        Cache.init()
        self.clazz = ReviewBot

    def get_optparser(self):
        parser = cmdln.Cmdln.get_optparser(self)
        parser.add_option("--apiurl", '-A', metavar="URL", help="api url")
        parser.add_option("--user", metavar="USER", help="reviewer user name")
        parser.add_option("--group", metavar="GROUP", help="reviewer group name")
        parser.add_option("--dry", action="store_true", help="dry run")
        parser.add_option("--debug", action="store_true", help="debug output")
        parser.add_option("--osc-debug", action="store_true", help="osc debug output")
        parser.add_option("--verbose", action="store_true", help="verbose")
        parser.add_option("--review-mode", dest='review_mode', choices=[c.value for c in ReviewBot.REVIEW_CHOICES], help="review behavior")
        parser.add_option("--fallback-user", dest='fallback_user', metavar='USER', help="fallback review user")
        parser.add_option("--fallback-group", dest='fallback_group', metavar='GROUP', help="fallback review group")
        parser.add_option('-c', '--config', dest='config', metavar='FILE', help='read config file FILE')

        return parser

    def postoptparse(self):
        level = None
        if (self.options.debug):
            level = logging.DEBUG
        elif (self.options.verbose):
            level = logging.INFO

        logging.basicConfig(level=level, format='[%(levelname).1s] %(message)s')
        self.logger = logging.getLogger(self.optparser.prog)

        conf.get_config(override_apiurl=self.options.apiurl)

        if (self.options.osc_debug):
            conf.config['debug'] = True

        self.checker = self.setup_checker()
        if self.options.config:
            self.checker.load_config(self.options.config)

        if self.options.review_mode:
            self.checker.review_mode = self.options.review_mode

        if self.options.fallback_user:
            self.checker.fallback_user = self.options.fallback_user

        if self.options.fallback_group:
            self.checker.fallback_group = self.options.fallback_group

    def setup_checker(self):
        """ reimplement this """
        apiurl = conf.config['apiurl']
        if apiurl is None:
            raise osc.oscerr.ConfigError("missing apiurl")
        user = self.options.user
        group = self.options.group
        # if no args are given, use the current oscrc "owner"
        if user is None and group is None:
            user = conf.get_apiurl_usr(apiurl)

        return self.clazz(apiurl=apiurl,
                          dryrun=self.options.dry,
                          user=user,
                          group=group,
                          logger=self.logger)

    def do_id(self, subcmd, opts, *args):
        """${cmd_name}: check the specified request ids

        ${cmd_usage}
        ${cmd_option_list}
        """
        self.checker.set_request_ids(args)
        return self.checker.check_requests()

    @cmdln.option('-n', '--interval', metavar="minutes", type="int", help="periodic interval in minutes")
    def do_review(self, subcmd, opts, *args):
        """${cmd_name}: check requests that have the specified user or group as reviewer

        ${cmd_usage}
        ${cmd_option_list}
        """
        if self.checker.review_user is None and self.checker.review_group is None:
            raise osc.oscerr.WrongArgs("missing reviewer (user or group)")

        def work():
            self.checker.set_request_ids_search_review()
            return self.checker.check_requests()

        return self.runner(work, opts.interval)

    @cmdln.option('-n', '--interval', metavar="minutes", type="int", help="periodic interval in minutes")
    def do_project(self, subcmd, opts, project, typename):
        """${cmd_name}: check all requests of specified type to specified

        ${cmd_usage}
        ${cmd_option_list}
        """

        def work():
            self.checker.set_request_ids_project(project, typename)
            return self.checker.check_requests()

        return self.runner(work, opts.interval)

    def runner(self, workfunc, interval):
        """ runs the specified callback every <interval> minutes or
        once if interval is None or 0
        """
        class ExTimeout(Exception):
            """raised on timeout"""

        if not interval:
            return workfunc()

        def alarm_called(nr, frame):
            raise ExTimeout()
        signal.signal(signal.SIGALRM, alarm_called)

        while True:
            try:
                workfunc()
            except Exception as e:
                self.logger.exception(e)

            if os.isatty(0):
                self.logger.info("sleeping %d minutes. Press enter to check now ..." % interval)
                signal.alarm(interval * 60)
                try:
                    input()
                except ExTimeout:
                    pass
                signal.alarm(0)
                self.logger.info(f"recheck at {datetime.datetime.now().isoformat()}")
            else:
                self.logger.info("sleeping %d minutes." % interval)
                time.sleep(interval * 60)

            # Reset all memoize session caches which are designed for single
            # tool run and not extended usage.
            memoize_session_reset()

            # Reload checker to flush instance variables and thus any config
            # or caches they may contain.
            self.postoptparse()


if __name__ == "__main__":
    app = CommandLineInterface()
    sys.exit(app.main())
