#
# (c) 2017 Red Hat Inc.
# Copyright (C) 2021 Maipu.
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
author: 756928812@qq.com
cliconf: MPOS
short_description: Use mpos cliconf to run command on Maipu MPOS platform
description:
  - This mpos plugin provides low level abstraction apis for
    sending and receiving CLI commands from Maipu mpos network devices.
"""

import re
import json

from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils._text import to_text
from ansible.module_utils.common._collections_compat import Mapping
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.utils import (
    to_list,
)
from ansible.plugins.cliconf import CliconfBase, enable_mode


class Cliconf(CliconfBase):

    def get_device_info(self):
        device_info = {}

        device_info['network_os'] = 'mpos'
        reply = self.get('show version')
        data = to_text(reply, errors='surrogate_or_strict').strip()
        host = self.get('show hostname')
        hostname = to_text(host, errors='surrogate_or_strict').strip("Local hostname ")
        if data:
            device_info['network_os_version'] = self.parse_version(data)
            device_info['network_os_model'] = self.parse_model(data)
            device_info['network_os_hostname'] = hostname

        return device_info

    def parse_version(self, data):
        for line in data.split('\n'):
            line = line.strip()
            m_version_info = re.match(r"Software Version\s+:\s+(\S+)",
                                      line, re.M | re.I)
            if m_version_info:
                return m_version_info.group(1)
        return "NA"

    def parse_model(self, data):
        for line in data.split('\n'):
            line = line.strip()
            match = re.match(r'Hardware Model	(.*?)', line, re.M | re.I)
            if match:
                return match.group(1)
        return "NA"

    @enable_mode
    def get_config(self, source='running'):
        if source not in ('running', 'startup'):
            msg = "fetching configuration from %s is not supported"
            return self.invalid_params(msg % source)
        if source == 'running':
            cmd = 'show running-config'
        else:
            cmd = 'show startup-config'
        return self.send_command(cmd)

    @enable_mode
    def edit_config(self, candidate=None, commit=True):
        resp = {}
        results = []
        requests = []
        if commit:
            self.send_command('configure terminal')
            for line in to_list(candidate):
                if not isinstance(line, Mapping):
                    line = {'command': line}

                cmd = line['command']
                if cmd != 'end' and cmd[0] != '!':
                    results.append(self.send_command(**line))
                    requests.append(cmd)

            self.send_command('end')
        else:
            raise ValueError('check mode is not supported')

        resp['request'] = requests
        resp['response'] = results
        return resp

    def get(self, command, prompt=None, answer=None, sendonly=False, newline=True, check_all=False):
        return self.send_command(command=command, prompt=prompt, answer=answer, sendonly=sendonly, newline=newline,
                                 check_all=check_all)

    def get_capabilities(self):
        result = super(Cliconf, self).get_capabilities()
        return json.dumps(result)

    def set_cli_prompt_context(self):
        """
        Make sure we are in the operational cli mode
        :return: None
        """
        if self._connection.connected:
            out = self._connection.get_prompt()

            if out is None:
                raise AnsibleConnectionFailure(message=u'cli prompt is not identified from the last received'
                                                       u' response window: %s' % self._connection._last_recv_window)

            if to_text(out, errors='surrogate_then_replace').strip().endswith(')#'):
                self._connection.queue_message('vvvv', 'In Config mode, sending exit to device')
                self._connection.send_command('exit')
            else:
                self._connection.send_command('enable')
