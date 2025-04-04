#!/usr/bin/python3

import argparse
import logging
import sys


import re
from lxml import etree as ET

import osc.conf
import osc.core
from osc.core import http_GET
from osc.core import makeurl
import osclib
from osclib.core import source_file_ensure
from osclib.core import source_file_load
from osclib.conf import Config

SUPPORTED_ARCHS = ['x86_64', 'aarch64', 'ppc64le', 's390x']
DEFAULT_REPOSITORY = 'standard'
META_PACKAGE = '000productcompose'
PRODUCTCOMPOSE_SEPERATOR_LINE = '# The following is generated by skippkg-finder'


class SkippkgFinder(object):
    def __init__(self, opensuse_project, print_only):
        self.opensuse_project = opensuse_project
        self.opensuse_nonfree_project = opensuse_project + ":NonFree"
        self.print_only = print_only
        self.apiurl = osc.conf.config['apiurl']
        self.debug = osc.conf.config['debug']

        config = Config.get(self.apiurl, opensuse_project)

        # Product compose input file
        self.skippkg_finder_productcompose_input_file = config.get('skippkg-finder-productcompose-input-file', '')
        # Repositories be used for product build
        self.skippkg_finder_product_repos = set(config.get('skippkg-finder-product-repos', '').split())
        # Binary package matches the regex from `skippkg-finder-skiplist-ignores`
        # be found in `package_binaries` will be ignored
        # The format must like SUSE:SLFO:Main:Build_gettext-runtime or SUSE:SLFO:Main:Build_gettext-runtime:mini
        # format definition: PROJECT-NAME_PACKAGE-NAME
        self.skiplist_to_ignore = set(config.get('skippkg-finder-to-ignore', '').split())
        # Supplement binary package to be ignored in the ftp-tree
        self.skiplist_supplement_regex = set(config.get('skippkg-finder-supplement-regex', '').split())
        # Drops off binary package from the ignoring list
        self.skiplist_ignorelist_whitelist = set(config.get('skippkg-finder-ignorelist-whitelist', '').split())

    def get_project_binary_list(self, project, repository, arch, index_by_arch=False, package_binaries={}):
        """
        Return binarylist of a project
        """
        path = ['build', project, repository, arch]
        url = makeurl(self.apiurl, path, {'view': 'binaryversions'})
        root = ET.parse(http_GET(url)).getroot()

        for binary_list in root:
            package = binary_list.get('package')
            index = project + "_" + package
            if index_by_arch:
                index = arch

            if index not in package_binaries:
                package_binaries[index] = []
            for binary in binary_list:
                filename = binary.get('name')
                result = re.match(osclib.core.RPM_REGEX, filename)
                if not result:
                    continue

                if result.group('arch') == 'src' or result.group('arch') == 'nosrc':
                    continue
                if result.group('name').endswith('-debuginfo') or result.group('name').endswith('-debuginfo-32bit'):
                    continue
                if result.group('name').endswith('-debugsource'):
                    continue

                if result.group('name') not in package_binaries[index]:
                    package_binaries[index].append(result.group('name'))

        return package_binaries

    def create_output(self, input_file, to_ignore_list=[], nonfree_packagelist={}):
        """
        Return a result data with unneeded packageset and nonfree packageset
        """
        output = []
        lines = input_file.splitlines()
        for line in lines:
            if line.startswith('___') and line.endswith('___'):
                if 'leap_nonfree' in line:
                    output.append(f"- name: {line.strip('___')}\n")
                    if line.strip('___').split('_', 2)[-1] in SUPPORTED_ARCHS:
                        output.append('  architectures:\n')
                        output.append(f"  - {line.strip('___').split('_', 2)[-1]}\n")
                    output.append('  packages:\n')
                    for pkg in sorted(nonfree_packagelist[line.strip('___').split('_', 2)[-1]]):
                        output.append(f"  - {pkg}\n")
                    continue
                if 'leap_unneeded' in line:
                    output.append('- name: leap_unneeded\n')
                    output.append('  packages:\n')
                    for pkg in sorted(to_ignore_list):
                        output.append(f"  - {pkg}\n")
                    continue
            output.append(line + '\n')

        return output

    def crawl(self):
        """Main method"""

        if not (self.skippkg_finder_product_repos and
                self.skippkg_finder_productcompose_input_file):
            print('Please define product repository list by \'skippkg-finder-product-repos\''
                  ' and \'skippkg-finder-productcompose-input-file\' in OSRT:Config')
            quit()
        # Any existing binary package from listed repositories
        fullbinarylist = []
        # package_binaries[] is a pre-formated binarylist per each package
        # Access to the conotent uses for example package_binaries['SUSE:SLFO:Main:Build_curl:mini']
        package_binaries = {}

        product_repos = {}
        for reponame in self.skippkg_finder_product_repos:
            prj, repo = reponame.split("_", 1)
            product_repos[prj] = repo
        # Inject binarylist to a list per package name no matter what archtectures was
        for arch in SUPPORTED_ARCHS:
            for prj in product_repos.keys():
                package_binaries = self.get_project_binary_list(prj, product_repos[prj], arch, False, package_binaries)

        for pkg in package_binaries.keys():
            fullbinarylist += package_binaries[pkg]

        # Preparing a packagelist to be ignored
        to_ignore_list = []
        for pkg in self.skiplist_to_ignore:
            if pkg in package_binaries:
                [to_ignore_list.append(p.strip()) for p in package_binaries[pkg]]
            else:
                logging.info(f"Can not find source package: {pkg}")
        for regex in self.skiplist_supplement_regex:
            for binary in fullbinarylist:
                result = re.match(regex, binary)
                if result and binary not in to_ignore_list:
                    to_ignore_list.append(binary)
        # Handling package whitelist
        [to_ignore_list.remove(pkg) for pkg in self.skiplist_ignorelist_whitelist if pkg in to_ignore_list]

        # Processing NonFree packagelist
        package_binaries.clear()
        package_binaries['allarchs'] = []
        for arch in SUPPORTED_ARCHS:
            package_binaries = self.get_project_binary_list(self.opensuse_nonfree_project, DEFAULT_REPOSITORY,
                                                            arch, True, package_binaries)

        package_binaries['allarchs'] = set(package_binaries['x86_64']) & set(package_binaries['aarch64']) & \
            set(package_binaries['ppc64le']) & set(package_binaries['s390x'])

        for arch in SUPPORTED_ARCHS:
            p = package_binaries[arch].copy()
            for pkg in package_binaries[arch]:
                if pkg in package_binaries['allarchs']:
                    p.remove(pkg)
            package_binaries[arch] = p

        input_file = source_file_load(self.apiurl, self.opensuse_project, META_PACKAGE,
                                      str(self.skippkg_finder_productcompose_input_file).strip())
        result_string = ''.join(map(str, self.create_output(input_file, to_ignore_list,
                                                            nonfree_packagelist=package_binaries)))

        if not self.print_only:
            source_file_ensure(self.apiurl, self.opensuse_project, META_PACKAGE,
                               str(self.skippkg_finder_productcompose_input_file).strip().replace('.in', ''),
                               result_string, 'Update the skip list')
        else:
            print(result_string)


def main(args):
    osc.conf.get_config(override_apiurl=args.apiurl)
    osc.conf.config['debug'] = args.debug

    if args.opensuse_project is None:
        print("Please pass --opensuse-project argument. See usage with --help.")
        quit()

    uc = SkippkgFinder(args.opensuse_project, args.print_only)
    uc.crawl()


if __name__ == '__main__':
    description = 'Overwrites unneeded part in productcompose according to the pre-defined rules. '\
                  'This tool only works for product-composer with ftp-tree build scenario.'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-A', '--apiurl', metavar='URL', help='API URL')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='print info useful for debuging')
    parser.add_argument('-o', '--opensuse-project', dest='opensuse_project', metavar='OPENSUSE_PROJECT',
                        help='openSUSE project on buildservice')
    parser.add_argument('-p', '--print-only', action='store_true',
                        help='show the result instead of the uploading')

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug
                        else logging.INFO)

    sys.exit(main(args))
