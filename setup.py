# setup.py
from setuptools import setup, find_packages

setup(
    name='mellerikatedge',
    version='1.1',
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