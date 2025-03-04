# setup.py
import os
from setuptools import setup, find_packages

def read_version():
    version_file = os.path.join(os.path.dirname(__file__), "src/mellerikatedge/version.py")
    with open(version_file) as f:
        code = compile(f.read(), version_file, 'exec')
        exec(code)
        return locals()['__version__']

setup(
    name='mellerikat-edge',
    version=read_version(),
    packages=find_packages(where='src'),
    package_dir={"": "src"},
    install_requires=[
        'requests',
        'websockets==10.4',
        'pandas',
        'loguru',
        'psutil',
        'ruamel.yaml',
        'nest_asyncio'
    ],
    entry_points={
        'console_scripts': [
            'edge=mellerikatedge.cli:main',
        ]
    },
    description='Receives the inference model from Mellerikat on Edge and performs inference',
    author='Mellerikat',
    author_email='contact@mellerikat.com',
    url='https://github.com/mellerikat/EdgeSDK',
)

# pip install build
# Build python -m build
# twine upload dist/*