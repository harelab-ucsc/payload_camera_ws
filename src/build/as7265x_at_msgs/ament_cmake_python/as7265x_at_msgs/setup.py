from setuptools import find_packages
from setuptools import setup

setup(
    name='as7265x_at_msgs',
    version='0.0.1',
    packages=find_packages(
        include=('as7265x_at_msgs', 'as7265x_at_msgs.*')),
)
