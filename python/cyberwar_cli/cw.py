import argparse
import json
import os

CONFIG = None
MY_PATH = os.path.dirname(os.path.abspath(__file__))

def processing():
    parser = argparse.ArgumentParser()

    parser.add_argument('-m', '--mode', choices=['init', 'launch'], required=True)
    parser.add_argument('--host', default=CONFIG['network']['switch']['host'])
    parser.add_argument('-p', '--port', default=CONFIG['network']['switch']['port'])
    parser.add_argument('-a', '--playground-address', default=CONFIG['network']['playground_address'])
    args = parser.parse_args()
    run(args)

def run(args):
    if args.mode == 'init':
        command = 'PYTHONPATH={}/game/src/ python -m cyberwar.game --init={},{},{}'.format(CONFIG['site_packages_path'], args.host, args.port, args.playground_address)
        os.system(command)
    elif args.mode == 'launch':
        command = 'PYTHONPATH={}/game/src/ python -m cyberwar.game --pypy={}'.format(CONFIG['site_packages_path'], CONFIG['pypy_path'])
        os.system(command)


if __name__ == '__main__':
    config_path = os.path.join(MY_PATH, 'cwconfig.json')
    with open(config_path, 'r') as f:
        CONFIG = json.load(f)
    processing()
