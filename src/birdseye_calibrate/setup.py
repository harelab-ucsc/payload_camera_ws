from setuptools import find_packages, setup

package_name = 'birdseye_calibrate'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='mwmaster',
    maintainer_email='mwmaster@ucsc.edu',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'birdseye_tf_pub = birdseye_calibrate.birdseye_tf_publisher:main'
        ],
    },
)
