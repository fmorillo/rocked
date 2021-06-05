#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argcomplete
import argparse
import json
import sys
from config_loader import ConfigLoader
from container_manager import ContainerManager


class ProfileChoices:
    def __init__(self):
        self.choices = list()
        with open('config.json', 'r') as json_file:
            config = json.load(json_file)
            profiles = config['profiles']
            for profile in profiles:
                self.choices.append(profile['name'])

    def __call__(self, **kwargs):
        return self.choices


def handle_args():
    parser = argparse.ArgumentParser(prog='rocked',
                                     usage='%(prog)s [options] command',
                                     description='Something')
    subparsers = parser.add_subparsers(dest='mode')

    setup_parser = subparsers.add_parser('setup', help='Setup default config')

    open_parser = subparsers.add_parser('open', help='Run / Start container and exec into container')
    open_parser.add_argument('-i', '--id', default='0', help='ID of container')
    open_parser.add_argument('-n', '--new', action='store_true', help='New ID for container')
    open_parser.add_argument('profile', help='Profile of container').completer=ProfileChoices()
    open_parser.add_argument('command', default='', nargs='?', help='Command executed in container')

    close_parser = subparsers.add_parser('close', help='Stop container')
    close_parser.add_argument('-i', '--id', default='0', help='ID of container')
    close_parser.add_argument('-a', '--all', action='store_true', help='All containers')
    close_parser.add_argument('profile', help='Profile of container').completer=ProfileChoices()

    remove_parser = subparsers.add_parser('remove', help='Remove container and associated untangled image')
    remove_parser.add_argument('-i', '--id', default='0', help='ID of container')
    remove_parser.add_argument('-a', '--all', action='store_true', help='All containers')
    remove_parser.add_argument('profile', help='Profile of container').completer=ProfileChoices()

    update_parser = subparsers.add_parser('update', help='Update image')
    update_parser.add_argument('-f', '--force', action='store_true', help='Force')
    update_parser.add_argument('profile', help='Profile of container').completer=ProfileChoices()

    destroy_parser = subparsers.add_parser('destroy', help='Remove all containers and images that belong to the profile')
    destroy_parser.add_argument('profile', help='Profile of container').completer=ProfileChoices()

    argcomplete.autocomplete(parser)
    args, unknown = parser.parse_known_args()

    if args.mode == 'open':
        if args.command:
            args.command = [args.command]
            if len(unknown) > 0:
                args.command += unknown
    return args

def main():
    args = handle_args()
    if args is None:
        return

    setup = False
    if args.mode == 'setup':
        setup = True

    with open('config.json', 'r') as json_file:
        loader = ConfigLoader(json.load(json_file), setup=setup)

    if loader.is_updated:
        with open('config.json', 'w') as json_file:
            json.dump(loader.config, json_file, indent=4)
        print('Config updated!')
    else:
        print('Config loaded!')

    if setup:
        return

    profile = loader.get_profile(args.profile)
    if profile is None:
        print('Profile with name "' + args.profile + '" not found!')
        return

    manager = ContainerManager(loader.get_settings(), profile)

    if args.mode == 'open':
        if not manager.exists_image():
            if manager.build_image() is None:
                return
        if args.new:
            container_ids = manager.list_containers()
            container_ids.append('-1')
            container_ids = sorted(map(int, container_ids))
            container_id = container_ids[-1] + 1
            for i in range(1, len(container_ids)):
                if (container_ids[i] - container_ids[i-1]) > 1:
                    container_id = container_ids[i-1] + 1
                    break
            manager.exec_container(str(container_id), args.command)
        else:
            manager.exec_container(args.id, args.command)
    elif args.mode == 'close':
        if args.all:
            container_ids, _ = manager.list_containers()
            for container_id in container_ids:
                manager.stop_container(container_id)
        else:
            manager.stop_container(args.id)
    elif args.mode == 'remove':
        if args.all:
            container_ids = manager.list_containers()
            for container_id in container_ids:
                manager.stop_container(container_id)
                image_id = manager.remove_container(container_id)
                manager.remove_image(image_id, only_untangled=True)
        else:
            manager.stop_container(args.id)
            image_id = manager.remove_container(args.id)
            manager.remove_image(image_id, only_untangled=True)
    elif args.mode == 'update':
        manager.update_image(force=args.force)
    elif args.mode == 'destroy':
        container_ids = manager.list_containers()
        for container_id in container_ids:
            manager.stop_container(container_id)
            image_id = manager.remove_container(container_id)
            manager.remove_image(image_id)
        manager.remove_image(manager.image_name)


if __name__ == '__main__':
    main()
