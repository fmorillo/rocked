import crypt
import re
import subprocess
import sys
from getpass import getuser, getpass
from grp import getgrgid
from locale import getlocale
from pwd import getpwnam
from tzlocal import get_localzone


class ConfigLoader():
    def __init__(self, json_config, setup=False):
        self.config = json_config
        self.is_updated = False
        print('Loading Config...\n')

        user_updated = False
        for key, value in self.config['settings'].items():
            if value is None or setup:
                self.is_updated = True

                if key == 'timezone':
                    self.__detect_timezone()
                elif key == 'locale':
                    self.__detect_locale()
                elif key == 'user' or key == 'userid' or key == 'group' or key == 'groupid' or key == 'configdir' or key == 'volumedir':
                    if not user_updated:
                        self.__detect_user()
                        user_updated = True
                elif key == 'secret':
                    self.__ask_secret()
                elif key == 'gpu':
                    self.__detect_gpu()

    def __ask_secret(self):
        while True:
            password = getpass('Please enter new password: ')
            if not password == getpass('Retype password: '):
                print('\nSorry, passwords do not match.')
            else:
                secret = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
                self.config['settings']['secret'] = secret.replace('/', '\/').replace('.', '\.')
                break
        print('Password change successful.\n')

    def __detect_timezone(self):
        self.config['settings']['timezone'] = get_localzone().zone
        print('Timezone updated to ' + self.config['settings']['timezone'] + '.\n')

    def __detect_locale(self):
        loc = getlocale()
        self.config['settings']['locale'] = loc[0] + '.' + loc[1]
        print('Locale updated to ' + self.config['settings']['locale'] + '.\n')

    def __detect_user(self):
        self.config['settings']['user'] = getuser()

        pwd_fields = getpwnam(getuser())
        self.config['settings']['userid'] = pwd_fields.pw_uid
        self.config['settings']['groupid'] = pwd_fields.pw_gid
        self.config['settings']['configdir'] = pwd_fields.pw_dir + '/.rocked/'
        self.config['settings']['volumedir'] = pwd_fields.pw_dir + '/rocked/'

        self.config['settings']['group'] = getgrgid(pwd_fields.pw_gid)[0]

        print('User settings updated to:')
        print('    User: ' + self.config['settings']['user'] + ' (' + str(self.config['settings']['userid']) + ')')
        print('    Group: ' + self.config['settings']['group'] + ' (' + str(self.config['settings']['groupid']) + ')')
        print('    Config Dir: ' + self.config['settings']['configdir'])
        print('    Volume Dir: ' + self.config['settings']['volumedir'] + '\n')

    def __detect_gpu(self):
        output = subprocess.run(('lspci', '-v'), stdout=subprocess.PIPE)
        lines = output.stdout.decode('utf-8').split('\n')

        gpus = list()
        matched = False
        for line in lines:
            if not matched:
                result = re.match('^([a-f0-9]{2}:[a-f0-9]{2}\.[a-f0-9]) VGA compatible controller: (.*\)).*\[VGA controller\]\)', line, flags=0)
                if result is not None:
                    slot = result.groups()[0]
                    gpu = result.groups()[1]
                    matched = True
            else:
                result = re.match('^\tKernel driver in use: (.*)', line, flags=0)
                if result is not None:
                    driver = result.groups()[0]
                    matched = False
                    gpus.append({'slot': slot, 'gpu': gpu, 'driver': driver})

        len_gpus = len(gpus)
        if len_gpus == 0:
            print('Found no GPU, using software rendering!\n')
            self.config['settings']['gpu'] = 'software'
        elif len_gpus > 1:
            unique_drivers = sorted(set([gpu['driver'] for gpu in gpus]))
            if len(unique_drivers) != 1:
                print('Found several GPUs!')
                for gpu in gpus:
                    print(gpu['slot'] + ' ' + gpu['gpu'] + ' [' + gpu['driver'] + ']')

                driver = ''
                while driver not in unique_drivers:
                    driver = input('Please select the driver you want to use [' + ', '.join(unique_drivers) + ']: ')
                print('Using driver ' + driver + ' for rendering!\n')
                self.config['settings']['gpu'] = driver
        else:
            print('Found GPU, using driver ' + driver + ' for rendering!\n')
            self.config['settings']['gpu'] = driver

    def get_profile(self, profile_name):
        for profile in self.config['profiles']:
            if profile['name'] == profile_name:
                return profile

    def get_settings(self):
        return self.config['settings']
