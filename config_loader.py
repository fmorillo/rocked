import crypt
import json
import re
import subprocess
from getpass import getuser, getpass
from grp import getgrgid
from locale import getlocale
from pwd import getpwnam
from tzlocal import get_localzone
import sys


class ConfigLoader():
    def __init__(self, json_config):
        self.config = json_config
        self.is_updated = False

        for key, value in self.config['settings'].items():
            if value is None:
                self.is_updated = True

                if key == 'timezone':
                    self.__detect_timezone()
                elif key == 'locale':
                    self.__detect_locale()
                elif key == 'user' or key == 'userid' or key == 'group' or key == 'groupid' or key == 'configdir' or key == 'volumedir':
                    self.__detect_user()
                elif key == 'secret':
                    self.__ask_secret()
                    pass
                elif key == 'gpu':
                    self.__detect_gpu()

    def __ask_secret(self):
        while True:
            secret = getpass()
            if not secret == getpass('Retype Password: '):
                print('\nSorry, passwords do not match.')
            else:
                self.config['settings']['secret'] = secret
                break

    def __detect_timezone(self):
        self.config['settings']['timezone'] = get_localzone().zone

    def __detect_locale(self):
        loc = getlocale()
        self.config['settings']['locale'] = loc[0] + '.' + loc[1]

    def __detect_user(self):
        self.config['settings']['user'] = getuser()

        pwd_fields = getpwnam(getuser())
        self.config['settings']['userid'] = pwd_fields.pw_uid
        self.config['settings']['groupid'] = pwd_fields.pw_gid
        self.config['settings']['configdir'] = pwd_fields.pw_dir + '/.rocked/'
        self.config['settings']['volumedir'] = pwd_fields.pw_dir + '/rocked/'

        self.config['settings']['group'] = getgrgid(pwd_fields.pw_gid)[0]

    def __detect_gpu(self):
        output = subprocess.run(('lspci', '-v'), capture_output=True)
        lines = output.stdout.decode('utf-8').split('\n')

        gpus = list()
        for line in lines:
            result = re.match('^[a-f0-9]{2}:[a-f0-9]{2}\.[a-f0-9] VGA compatible controller: (.*\)).*\[VGA controller\]\)', line, flags=0)
            if result is not None:
                gpus.append(result.groups()[0])

        if len(gpus) == 0:
            return None

        elif len(gpus) == 1:
            result = re.match('.*Intel.*', gpus[0])
            if result is not None:
                self.config['settings']['gpu'] = 'intel'
                return

            result = re.match('.*A[M|T][D|I].*', gpus[0])
            # TODO: Which AMD driver is it? OpenCL Support?
            if result is not None:
                self.config['settings']['gpu'] = 'amd'
                return

            result = re.match('.*NVIDIA.*', gpus[0])
            # TODO: Is it nouveau or Nvidia driver?
            if result is not None:
                self.config['settings']['gpu'] = 'nvidia'
                return

            self.config['settings']['gpu'] = 'software'
            return

        else:
            # TODO: Implement detetction with OpenGL?
            print('Detected too many GPUs!')

    def get_profile(self, profile_name):
        for profile in self.config['profiles']:
            if profile['name'] == profile_name:
                return profile
        # TODO: Raise profile not found!

    def get_settings(self):
        return self.config['settings']

