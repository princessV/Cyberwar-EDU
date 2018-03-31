import json
import os
import sys

MY_PATH = os.path.dirname(os.path.abspath(__file__))

class BColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'


class CyWECLI():
    def __init__(self):
        super().__init__()
        self.site_packages_path = os.path.abspath(os.path.join(MY_PATH, os.pardir))
        self.arg_dict = {}

    def start(self):
        print(BColors.HEADER + '\n This CLI helps your rapidly create your own game. \n' + BColors.ENDC)
        print(BColors.HEADER + ' A game directory will be created in current directory.' + BColors.ENDC)
        print(BColors.HEADER + ' Input .exit to exit. \n' + BColors.ENDC)

        self.arg_dict['name'] = self.get_input_path('name',
                                                    BColors.OKBLUE + 'Your cyberwar directory name:\n' + BColors.ENDC)
        self.arg_dict['pypy_path'] = self.get_input_path('pypy_path',
                                                         BColors.OKBLUE + 'Your local pypy sandbox path: (Don\'t use "~")\n' + BColors.ENDC)
        self.arg_dict['cc'] = self.get_input_path('cc',
                                                  BColors.OKBLUE + 'Your C&C folder directory: (leave blank for not creating C&C)\n' + BColors.ENDC)

        self.write_config()
        self.processing()

    def processing(self):
        os.mkdir(self.arg_dict['name'])

        self.copy_files_from_cywe(self.arg_dict['name'])

        os.system('cp {}/pypy/sandbox/libpypy3-c.so {}/'.format(self.arg_dict['pypy_path'], self.arg_dict['name']))
        os.system('cp {}/pypy/sandbox/pypy3-c-sandbox {}/'.format(self.arg_dict['pypy_path'], self.arg_dict['name']))

        os.system('cp {}/cw.py {}/'.format(MY_PATH, self.arg_dict['name']))
        os.system('cp {}/cwconfig.json {}/'.format(MY_PATH, self.arg_dict['name']))

        if len(self.arg_dict['cc']) > 0:
            os.mkdir('{}'.format(self.arg_dict['cc']))
            os.system('cp {}/bot/samples/command_and_control.py {}'.format(self.site_packages_path,
                                                                                  self.arg_dict['cc']))
            os.system(
                'cp {}/game/src/cyberwar/braininterface/translations.py {}'.format(self.site_packages_path,
                                                                                          self.arg_dict['cc']))

        print(BColors.OKGREEN + 'Finished!' + BColors.ENDC)

    def update_game(self):
        cyberwar_path = self.get_input_path('cyberwar_path', BColors.OKBLUE + 'Your cyberwar path:\n' + BColors.ENDC)

        self.copy_files_from_cywe(cyberwar_path)
        print(BColors.OKGREEN + 'Updated!' + BColors.ENDC)

    def copy_files_from_cywe(self, cyberwar_path):
        os.system('cp {}/game/samples/simple_player_object_types.ini {}/'.format(self.site_packages_path, cyberwar_path))
        os.system('cp {}/game/src/cyberwar/braininterface/translations.py {}/'.format(self.site_packages_path, cyberwar_path))
        os.system('cp {}/game/pypy-sandbox/src/*.py {}/'.format(self.site_packages_path, cyberwar_path))
        os.system('cp {}/bot/samples/*.py {}/'.format(self.site_packages_path, cyberwar_path))
        os.system('mv {}/simple_player_object_types.ini {}/object_types.ini'.format(cyberwar_path, cyberwar_path))

    def write_config(self):
        config = None
        config_path = os.path.join(MY_PATH, 'cwconfig.json')
        with open(config_path, 'r') as f:
            config = json.load(f)

        config['site_packages_path'] = self.site_packages_path
        config['pypy_path'] = os.path.abspath(self.arg_dict['pypy_path'])
        with open(config_path, 'w') as f:
            json.dump(config, f, indent='\t')

    def get_input_path(self, key, prompt):
        input_path = ''
        while True:
            input_path = input(prompt).strip()
            if input_path == '.exit':
                exit()
            if key == 'name':
                if os.path.exists(input_path):
                    prompt = BColors.WARNING + 'Path already exists, input again:\n' + BColors.ENDC
                elif len(input_path) > 0:
                    break
                else:
                    prompt = BColors.WARNING + 'Please specify your folder name:\n' + BColors.ENDC
            elif key == 'pypy_path' or key == 'cyberwar_path':
                if os.path.exists(input_path):
                    break
                else:
                    prompt = BColors.FAIL + 'Path does not exist, input again:\n' + BColors.ENDC
            else:
                break
        return input_path


def main():
    cli = CyWECLI()
    if len(sys.argv) == 1 or sys.argv[1] == 'init':
        cli.start()
    elif sys.argv[1] == 'update':
        cli.update_game()
    else:
        print('Unknown command')


if __name__ == '__main__':
    main()
