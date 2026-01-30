from setuptools import find_packages, setup

package_name = 'andrea_multispec'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/rgb_plus_as7265x.launch.py']),
    ],

    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='pi4',
    maintainer_email='sammy.slug@ucsc.edu',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'spectral_bridge = multispec.spectral_bridge:main',
        ],
    },

)
