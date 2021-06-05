import docker
import filecmp
import jinja2
import json
import os
import re
import requests
import shlex
import shutil
import socket
import subprocess


class ContainerManager:

    def __init__(self, settings, profile):
        self.profile = profile
        self.settings = settings

        display = os.environ['DISPLAY']
        display_split = display.split(':')

        self.display_id = ''
        self.hostip = ''
        if display_split[0]:
            self.display_id = display_split[1].split('.')[0]
            self.hostip = self.__get_hostip()
            display = self.hostip + ':' + display_split[1]

        self.settings['display'] = display
        self.settings['cookies'] = self.__get_xauth_cookie()

        self.image_name = 'rocked_' + profile['name']
        self.client = docker.from_env()


    def __get_hostip(self):
        # Connect to dummy IP to get the hostIP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.255.254", 49152))
        host_ip = s.getsockname()[0]
        s.close()
        return host_ip


    def exists_image(self):
        try:
            self.client.images.get(self.image_name)
            return True
        except docker.errors.ImageNotFound:
            return False


    def get_image(self):
        if self.exists_image():
            return self.image_name

        print('\nImage not found!')

        if self.build_image() is None:
            return
        return self.image_name


    def build_image(self, nocache=False, pull=False):
        print('\nBuild Image: ' + str(self.profile) + '\n')

        template_dir = self.settings['configdir'] + 'templates/' + self.profile['distro'] + '/'
        jinja_loader = jinja2.FileSystemLoader(searchpath=template_dir)
        jinja_env = jinja2.Environment(loader=jinja_loader)

        self.__copy_process_files()

        templates = ['vital_base', 'vital_locale', 'vital_user', 'vital_pulse', 'vital_mesa'] + self.profile['templates']
        entryscript_path = ''

        if 'entryscript' in self.profile:
            templates.append('vital_entrypoint')
            entryscript_path = self.__generate_entryscript()

        templates.append('vital_password')

        docker_layers = list()
        for template in templates:
            jinja_template = jinja_env.get_template(template + '.jinja')
            docker_layers.append(jinja_template.render(settings=self.settings, profile=self.profile))

        for layer in docker_layers:
            print(layer)

        dockerfile_path = self.settings['configdir'] + 'tmp/Dockerfile'
        with open(dockerfile_path, 'w') as f:
            f.write('\n'.join(docker_layers))

        log = self.client.api.build(path=self.settings['configdir'] + 'tmp/', tag='rocked_' + self.profile['name'], nocache=nocache, pull=pull, forcerm=True, decode=True)

        image_id = ''
        for chunk in log:
            if 'stream' in chunk:
                for line in chunk['stream'].rstrip('\n').splitlines():
                    print(line)
                    result = re.match('^Successfully\sbuilt\s(.*)', line)
                    if result is not None:
                        image_id = result.groups()[0]

        os.remove(dockerfile_path)
        if entryscript_path:
            os.remove(entryscript_path)

        if image_id:
            return image_id
        print('\nImage "' + self.image_name + '" could not be built!')


    def __generate_entryscript(self):
        entrypoint_dir = self.settings['configdir'] + 'entryscripts/' + self.profile['distro'] + '/'
        jinja_loader = jinja2.FileSystemLoader(searchpath=entrypoint_dir)
        jinja_env = jinja2.Environment(loader=jinja_loader)

        entryscript_template = jinja_env.get_template(self.profile['entryscript'] + '.sh.jinja')
        entryscript = entryscript_template.render(settings=self.settings, profile=self.profile)

        entryscript_path = self.settings['configdir'] + 'tmp/docker-entrypoint.sh'
        with open(entryscript_path, 'w') as f:
            f.write(entryscript)

        self.__make_executable(entryscript_path)
        return entryscript_path


    def __make_executable(self, path):
        executable_bit = 0o0111
        mode = os.stat(path).st_mode
        os.chmod(path, mode | executable_bit)


    def __copy_process_files(self):
        tmp_dir = self.settings['configdir'] + '/tmp/'
        process_dir = 'process_management/'
        process_files = ('process_monitor.py', 'process_reporter.sh', 'add_process.py', 'delete_process.py')

        for process_file in process_files:
            if os.path.isfile(tmp_dir + process_file):
                if filecmp.cmp(process_dir + process_file, tmp_dir + process_file, shallow=True):
                    continue
            shutil.copy2(process_dir + process_file, tmp_dir + process_file)


    def exists_container(self,container_id):
        container_name = self.image_name + '_' + container_id
        return self.client.containers.get(container_name)


    def create_container(self, container_id):
        run_dict = self.__merge_run(container_id)
        print('\nRun container "' + run_dict['name'] + '" with config:\n')
        for key, value in run_dict.items():
            print(key + ': ' + str(value))

        container = self.client.containers.run(**run_dict)
        self.__add_xauth(container)
        return container


    def __merge_run(self, container_id):
        default_dict = {
            'image': self.image_name,
            'command': 'process_monitor.py',
            'detach': True,
            'name': self.image_name + '_' + container_id,
            'tty': True
        }

        run_dict = {
            'devices': ['/dev/dri:/dev/dri'], #acceleration 3d and video
            'environment': ['DISPLAY=' + self.settings['display']],
            'remove': False,
            'user': self.settings['user'],
            'volumes': ['/tmp/.X11-unix:/tmp/.X11-unix', '/run/user/' + str(self.settings['userid']) + '/pulse:/run/user/' + str(self.settings['userid']) + '/pulse'],
            'working_dir': '/home/' + self.settings['user'],
        }

        if 'volumes' in self.profile['run']:
            for i, volume in enumerate(self.profile['run']['volumes']):
                self.profile['run']['volumes'][i] = jinja2.Template(volume).render(settings=self.settings, profile=self.profile)
                src_path = self.profile['run']['volumes'][i].split(':')[0]

                if not os.path.isfile(src_path) and not os.path.isdir(src_path):
                    os.makedirs(src_path)

        for key, value in self.profile['run'].items():
            if key in run_dict:
                if isinstance(value, type(run_dict[key])):
                    # TODO: Maybe merge dicts? (For volumes.)
                    if isinstance(value, list):
                        run_dict[key] = run_dict[key] + value
                    else:
                        run_dict[key] = value
                else:
                    print('Wrong Type: ' + str(type(value)) + ' !')
            else:
                run_dict[key] = value

        run_dict.update(default_dict)
        return run_dict


    def exec_container(self, container_id, command=''):
        try:
            container = self.exists_container(container_id)
        except docker.errors.NotFound:
            print('\nContainer not found!')
            container = self.create_container(container_id)

        if container.status == 'exited':
            print('\nStarting container "' + container.name + '".')
            container.start()
        self.__add_xauth(container)

        docker_exec = jinja2.Template('docker exec -it -u {{ user }} {{ container }} {{ command }}')
        exec_command = 'process_reporter.sh ' + self.settings['display']
        args = docker_exec.render(user=self.settings['user'], container=container.name, command=exec_command).split(' ')

        if not command:
            args += shlex.split(self.profile['run']['command'])
        else:
            args += command

        print('\nExec into container with command: "' + str(args) + '".\n')
        os.execv('/usr/bin/docker', args)


    def __get_xauth_cookie(self):
        output = subprocess.run(('xauth', 'list'), stdout=subprocess.PIPE)
        lines = output.stdout.decode('utf-8').split('\n')

        cookies = list()
        for line in lines:
            result = re.match('^' + os.uname()[1] + '(.*:' + self.display_id + ')\s*MIT-MAGIC-COOKIE-1\s*(.*)', line)
            if result is not None:
                cookies.append({'display': self.hostip + result.groups()[0], 'cookie': result.groups()[1]})
        return cookies


    def __add_xauth(self, container):
        xauth_add = jinja2.Template('xauth add {{ display }} . {{ cookie }}')

        if self.hostip:
            for entry in self.settings['cookies']:
                xauth_command = xauth_add.render(display=entry['display'], cookie=entry['cookie'])
                container.exec_run(xauth_command, user='root')
                container.exec_run(xauth_command, user=self.settings['user'])
            return

        xauth_command = xauth_add.render(display=self.settings['display'], cookie=self.settings['cookies'][0]['cookie'])
        container.exec_run(xauth_command, user='root')
        container.exec_run(xauth_command, user=self.settings['user'])


    def stop_container(self, container_id):
        try:
            container = self.exists_container(container_id)
        except docker.errors.NotFound:
            print('\nContainer not found!')
            return

        if container.status == 'running':
            print('\nStopping container "' + container.name + '".')
            container.stop(timeout=60)
            container.wait(condition='not-running')
        else:
            print('\nContainer "' + container.name + '" already stopped.')


    def remove_container(self, container_id):
        try:
            container = self.exists_container(container_id)
        except docker.errors.NotFound:
            print('\nContainer already removed!')
            return

        image_id = container.image.id
        if container.status == 'exited':
            print('\nRemove container "' + container.name + '".')
            container.remove()
            return container.image.id


    def update_image(self, force=False):
        if not self.exists_image():
            print('\nImage not found!')
            if self.build_image() is None:
                return
            return self.image_name

        base_image_id_old = ''
        image_id_old = self.client.images.get(self.image_name).id

        try:
            base_image_id_old = self.client.images.get(self.profile['baseimage']).id
        except docker.errors.ImageNotFound:
            print('\nBase image not found!')

        image_id = self.build_image(nocache=force, pull=True)
        if image_id is None:
            return

        base_image_id = self.client.images.get(self.profile['baseimage']).id
        image_id = self.client.images.get(self.image_name).id

        if base_image_id_old and base_image_id_old != base_image_id:
            self.remove_image(base_image_id_old)

        if image_id != image_id_old:
            self.remove_image(image_id_old)
        return self.image_name


    def list_containers(self):
        containers = self.client.containers.list(all=True)
        related_container_ids = list()

        for container in containers:
            result = re.match('^' + self.image_name + '_([0-9]+)', container.name)
            if result is not None:
                related_container_ids.append(result.groups()[0])
        return related_container_ids


    def remove_image(self, image_id, only_untangled=False):
        if image_id is None:
            return

        try:
            if only_untangled and not len(self.client.images.get(image_id).tags) == 0:
                return
            print('\nRemove image "' + image_id + '"!')
            self.client.images.remove(image_id)
        except docker.errors.ImageNotFound:
            print('\nImage "' + image_id + '" already removed.')
        except docker.errors.APIError as api_error:
            result = re.match('.*Conflict \("(.*)"\)', str(api_error))
            print('\n' + result.groups()[0])
