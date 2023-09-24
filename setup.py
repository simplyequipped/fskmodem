from setuptools import setup

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    name='fskmodem',
    version='0.2.0',
    author='Simply Equipped LLC',
    author_email='howard@simplyequipped.com',
    description='Full duplex AFSK modem using the minimodem application',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/simplyequipped/fskmodem',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
    ],
    python_requires='>=3.6'
)

