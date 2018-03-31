# cyberwar-cli
CLI for rapid cyberwar building.

## Environment
This CLI is based on Python 3. You should use a Python 3 virtual environment if the Python 2 is also installed on your system.

## Installation
Very simple and no dependencies.
```sh
pip install git+https://github.com/CrimsonVista/Cyberwar-EDU.git
```
(Strongly recommend to use a virtual environment.)

## Instructions
Strongly recommend to start from a clean directory within which is only pypy sandbox directory, it will help you easily type the path when using this tool.

Just open terminal in this directory and type *cyberwar* or *cyberwar init*:
```sh
cyberwar # or cyberwar init
# Follow the prompts!
```
If you've already created the game and want to update the game (e.g., the Cyberwar-EDU is updated). Use pip install to upgrade this tool and then type *cyberwar update*:
```sh
cyberwar update
# Follow the prompts!
```
You can use the relative path when you input the path. That's why staring from a clean directory within which is only and pypy sandbox directory is strongly recommended. Since the file path tab completion feature is not enabled, using relative path will be less painful.

## Notice
The tool will create a 'cyberwar' (you named it!) directory for your local game with all the necessary things. It will also create a directory for command & control system if you specify.

There is also a quick-start script to init and launch the game. Config your *cwconfig.json* file in your *cyberwar/* and you can easily start the game. The *cwconfig.json* is like
```json
{
	"site_packages_path": "/path/to/site-packages",
	"pypy_path": "/path/to/sandbox",
	"network": {
		"switch": {
			"host": "127.0.0.1",
			"port": ""
		},
		"playground_address": ""
	}
}
```
The *cywe_path* and *pypy_path* will be automatically created when your create the game. Once you specify the TCP port of your switch and the playground address of your CC. You can easily use:
```sh
python cw.py -m init # init the game
python cw.py -m launch # launch the game
```
The two files can be customized on your own interest.
