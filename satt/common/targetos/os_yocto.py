# -*- coding: utf-8 -*-
'''
// Copyright (c) 2015 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
'''

""" LinuxOs Class

"""

import os
import re
import sys
import time
import pickle
import platform
import subprocess
from satt.common import helper
from satt.common import envstore
from satt.common.targetos.targetos import TargetOs


class YoctoOs(TargetOs):
    """ Linux specific impl
    """
    _package_hashes = []

    def __init__(self):
        # Base class init call
        TargetOs.__init__(self)

# ####################################
# Public methods
# ####################################
    def get_os_data(self, trace_path):
        TargetOs.get_os_data(self, trace_path)
        self.debug_print("Yocto::get_os_data")
        self._get_build_info()

    def get_vmlinux_path(self):
        self.debug_print("Yocto::get_vmlinux_path")
        kernel_path = envstore.store.get_variable('sat_path_kernel')
        if os.path.lexists(kernel_path):
            return os.path.join(kernel_path, 'vmlinux')
        else:
            print "Error: Incorrect kernel path, check configuration!"
            sys.exit(-1)

    def get_system_map_path(self):
        self.debug_print("Yocto::get_system_map_path")
        kernel_path = envstore.store.get_variable('sat_path_kernel')
        if os.path.lexists(kernel_path):
            return os.path.join(kernel_path, 'System.map')
        else:
            print "Error: Incorrect kernel path, check configuration!"
            sys.exit(-1)

    def get_name(self):
        self.debug_print("Yocto::get_name")
        return 'Yocto'

    def copy_binaries(self):
        ''' extract ipk debug packages into sysroot folder
        '''
        self.debug_print("Yocto::copy_binaries")
        target_build_path = envstore.store.get_variable('sat_target_build')
        if os.path.lexists(os.path.join(self._trace_path, 'binaries', 'system')):
            os.remove(os.path.join(self._trace_path, 'binaries', 'system'))
        os.symlink(target_build_path, os.path.join(self._trace_path, 'binaries', 'system'))

        md5_cmd = 'md5'
        try:
            subprocess.check_output(['which', md5_cmd])
        except:
            md5_cmd = 'md5sum'

        # Yocto specific *dbg*.dep file search abd unpack
        pkgtype="deb" # could be "ipk" or "rpm"

        # Create md5 hash to keep count which packages has been unpacked
        satt_pkg_cache_file = os.path.join(os.path.dirname(os.path.dirname(target_build_path)), '.satt-cache')
        if os.path.exists(satt_pkg_cache_file):
            self._package_hashes = pickle.load(open(satt_pkg_cache_file, 'rb'))

        # Search for the deploy path from the build folders
        # by travelling down path and search for the match
        target_pkg_path = target_build_path
        while(True):
            target_pkg_path = os.path.dirname(target_pkg_path)
            if (os.path.exists(os.path.join(target_pkg_path, 'deploy', pkgtype))):
                target_pkg_path = os.path.join(target_pkg_path, 'deploy', pkgtype)
                break
            if (target_pkg_path == "/"):
                target_pkg_path = False
                break

        if os.path.exists(target_pkg_path):
            dbg_pkg_hash_list = []
            pkgs = []
            # Search all dbg packages
            for rootfolder, directors, fns in os.walk(target_pkg_path):
                for subdir in directors:
                    root, dirs, files = os.walk(os.path.join(target_pkg_path, subdir)).next()
                    tmp_pkgs = filter(lambda k: '-dbg' in k, files)
                    pkgs.extend([f'{subdir}/{s}' for s in tmp_pkgs])
            pkgs_len = len(pkgs)
            pkgs_count = 0
            print('Unpack .deb debug packages:')
            for pkg in pkgs:
                # TODO create cross compatible shell_comman_api android, linux, chrome os etc
                checksum_line = subprocess.check_output([md5_cmd, os.path.join(target_pkg_path, pkg)]).strip()
                if match := re.search("([0-9a-fA-F]{32}) (.*)", checksum_line):
                    checksum = match.group(1)
                    if checksum not in self._package_hashes:
                        os.system(f'dpkg -x {os.path.join(target_pkg_path, pkg)} {target_build_path}')
                        self._package_hashes.append(checksum)
                pkgs_count = pkgs_count + 1
                # Print progress bar kind of
                sys.stdout.write('\r {0} / {1} '.format(pkgs_count, pkgs_len))
                sys.stdout.flush()
            print('Done')
            pickle.dump(self._package_hashes, open(satt_pkg_cache_file, 'wb'), pickle.HIGHEST_PROTOCOL)
        else:
            print(
                f"ERROR!!!!: Path does not exists, where debug symbol {pkgtype} packages should be !!!"
            )
            print("Continuing without debug symbols, only interface functions will be visible!!!")
            time.sleep(5)

    def get_debug_paths(self):
        #Return path where debug ipks were extracted (see copy_binaries)
        target_build_path = envstore.store.get_variable('sat_target_build')
        return os.path.join(target_build_path, 'usr', 'lib', '.debug')

    # Methods for CONFIG
    # ##################
    def config(self, variables):
        variables['sat_target_source'] = ''
        self._set_sat_kernel_paths(variables)
        self._set_sat_target_paths(variables)

    def _set_sat_kernel_paths(self, variables):
        print helper.color.BOLD + 'Select kernel paths:' + helper.color.END
        if variables['sat_control_bus'] == 'SHELL':
            # TODO what if SSH command?
            kmods = '/lib/modules/' + platform.release()
            if os.path.exists(kmods):
                variables['sat_path_modules'] = kmods

        selection = 'n'
        if variables['sat_path_modules'] != '':
            selection = raw_input("   Use kernel modules path: '" + variables['sat_path_modules'] + "' ? [Y/n] ")
        if selection == 'n' or selection == 'N':
            self.print_path_type_hint('sat_path_modules')
            while(True):
                self._helper.prepare_readline()
                variables['sat_path_modules'] = raw_input('   Give kernel modules path: ')
                variables['sat_path_modules'] = variables['sat_path_modules'].rstrip()
                if self.validate_target_path(variables, 'sat_path_modules'):
                    break
        print

        selection = 'n'
        if variables['sat_path_kernel'] != '':
            selection = raw_input("   Use kernel path: '" + variables['sat_path_kernel'] + "' ? [Y/n] ")
        if selection == 'n' or selection == 'N':
            self.print_path_type_hint('sat_path_kernel')
            while(True):
                self._helper.prepare_readline()
                variables['sat_path_kernel'] = raw_input('   Give another kernel path: ')
                variables['sat_path_kernel'] = variables['sat_path_kernel'].rstrip()
                if self.validate_target_path(variables, 'sat_path_kernel'):
                    break
        print

        selection = 'n'
        if variables['sat_path_kernel_src'] != '':
            selection = raw_input("   Use kernel source path: '" + variables['sat_path_kernel_src'] + "' ? [Y/n] ")
        if selection == 'n' or selection == 'N':
            self.print_path_type_hint('sat_path_kernel_src')
            while(True):
                self._helper.prepare_readline()
                variables['sat_path_kernel_src'] = raw_input('   Give another kernel source path: ')
                variables['sat_path_kernel_src'] = variables['sat_path_kernel_src'].rstrip()
                if self.validate_target_path(variables, 'sat_path_kernel_src'):
                    break
        print

    def _set_sat_target_paths(self, variables):
        print helper.color.BOLD + 'Select target paths:' + helper.color.END
        selection = 'n'
        if variables['sat_target_build'] != '':
            selection = raw_input("   Use target build path: '" + variables['sat_target_build'] + "' ? [Y/n] ")
        if selection == 'n' or selection == 'N':
            self.print_path_type_hint('sat_target_build')
            while(True):
                self._helper.prepare_readline()
                variables['sat_target_build'] = raw_input('   Give another target build path: ')
                variables['sat_target_build'] = variables['sat_target_build'].rstrip()
                if self.validate_target_path(variables, 'sat_target_build'):
                    break
        print

# ####################################
# Private methods
# ####################################

    def _get_build_info(self):
        self.debug_print("LinuxOs::_get_build_info")
        build_info = {}
        uname = platform.uname()
        linux_dist = platform.linux_distribution()
        build_info['brand'] = str(linux_dist[0]) + " " + str(linux_dist[1])
        build_info['name'] = uname[1]
        build_info['device'] = uname[1]
        build_info['android_v'] = ''

        build_info['prod_id'] = platform.release()
        build_info['version'] = platform.version()
        build_info['type'] = platform.system()
        build_info['platform'] = str(linux_dist[0]) + " " + str(linux_dist[1]) + " " + str(linux_dist[2])
        build_info['user'] = ''
        build_info['host'] = platform.libc_ver()[0] + " " + platform.libc_ver()[1]
        build_info['kernel_version'] = ' '.join(uname)

        pickle.dump(build_info, open(os.path.join(self._trace_path, "build_info.p"), "wb"), pickle.HIGHEST_PROTOCOL)
        print "Get build info from the device"
