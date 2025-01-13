# setup.py
from setuptools import setup, find_packages

setup(
    name='mellerikatedge',
    version='1.0',
    packages=find_packages(
        where='src'
    ),
    package_dir={"": "src"},
    install_requires=[
        'requests',
        'websockets==10.4',
        'pandas',
        'loguru',
        'PyYAML',
        'psutil',
        'nest_asyncio'
    ],
    description='Receives the inference model from Mellerikat on Edge and performs inference',
    author='Mellerikat',
    author_email='contact@mellerikat.com',
    url='mellerikat.com',
)

# pip install build
# Build python -m build