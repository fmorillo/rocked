#!/usr/bin/env python3

import docker
import json
import sys
from config_loader import ConfigLoader
from container_manager import ContainerManager


def handle_args():
    modes = {'i': 'init', 'o': 'open', 'c': 'close', 'u': 'update', 'r': 'reset', 'd': 'destroy', 'h': 'help'}
    args = {'mode': 'open', 'cid': '', 'profile': '', 'command': ''}

    try:
        pos = 1
        if sys.argv[pos] in modes:
            args['mode'] = modes[sys.argv[pos]]
            pos += 1
        elif sys.argv[pos] in modes.values():
            args['mode'] = sys.argv[pos]
            pos += 1

        args['profile'] = sys.argv[pos]
        pos += 1

        if sys.argv[pos].isnumeric() or sys.argv[pos] == 'n' or sys.argv[pos] == 'a' or sys.argv[pos] == 'f':
            args['cid'] = sys.argv[pos]
            pos += 1

        args['command'] = ' '.join(sys.argv[pos:])
    except IndexError:
        pass

    if args['mode'] == 'init':
        print('Mode "' + args['mode'] + '" not implemented!')
        return args

    if args['mode'] == 'help':
        print('Help')
        return None

    if not args['profile']:
        print('Profile missing!')
        return None

    if args['command'] and not args['mode'] == 'open':
        print('Command "' + args['command']  + '" not valid for mode "' + args['mode'] + '"!')
        return None

    if args['cid'] and args['mode'] == 'destroy':
        print('ID "' + args['cid'] + '" not valid for mode "' + args['mode'] + '"!')
        return None

    if args['cid'] == 'n' and not args['mode'] == 'open':
        print('New ID option not valid for mode "' + args['mode'] + '"!')
        return None

    if args['cid'] == 'a' and not (args['mode'] == 'close' or args['mode'] == 'reset'):
        print('All IDs option not valid for mode "' + args['mode'] + '"!')
        return None

    if args['cid'] == 'f' and not args['mode'] == 'update':
        print('Force option not valid for mode "' + args['mode'] + '"!')
        return None

    if not args['cid']:
        args['cid'] = '0'

    return args


def main():
    args = handle_args()
    if args is None:
        return

    with open('config.json', 'r') as json_file:
        loader = ConfigLoader(json.load(json_file))

    if loader.is_updated:
        with open('config.json', 'w') as json_file:
            json.dump(loader.config, json_file, indent=4)
        print('Config updated!')
    else:
        print('Config loaded!')

    if args['mode'] == 'init':
        # TODO: Implement init.
        return

    profile = loader.get_profile(args['profile'])
    if profile is None:
        print('Profile with name "' + args['profile'] + '" not found!')
        return

    manager = ContainerManager(loader.get_settings(), profile)

    if args['mode'] == 'open':
        if not manager.exists_image():
            if manager.build_image() is None:
                return
        if args['cid'] == 'n':
            container_ids, _ = manager.list_containers()
            container_ids = sorted(map(int, container_ids))
            container_id = container_ids[-1] + 1
            for i in range(1, len(container_ids)):
                if (container_ids[i] - container_ids[i-1]) > 1:
                    container_id = container_ids[i-1] + 1
            manager.exec_container(str(container_id), args['command'])
        else:
            manager.exec_container(args['cid'], args['command'])
    elif args['mode'] == 'close':
        if args['cid'] == 'a':
            container_ids, _ = manager.list_containers()
            for container_id in container_ids:
                manager.stop_container(container_id)
        else:
            manager.stop_container(args['cid'])
    elif args['mode'] == 'update':
        force = False
        if args['cid'] == 'f':
            force = True
        manager.update_image(force=force)
    elif args['mode'] == 'reset':
        if args['cid'] == 'a':
            container_ids, _ = manager.list_containers()
            for container_id in container_ids:
                manager.stop_container(container_id)
                manager.remove_container(container_id)
        else:
            manager.stop_container(args['cid'])
            manager.remove_container(args['cid'])
    elif args['mode'] == 'destroy':
        container_ids, image_ids = manager.list_containers()
        for container_id in container_ids:
            manager.stop_container(container_id)
            manager.remove_container(container_id)
        for image_id in image_ids:
            manager.remove_image(image_id)
        manager.remove_image(manager.image_name)


if __name__ == '__main__':
    main()
