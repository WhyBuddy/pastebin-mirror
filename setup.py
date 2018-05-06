from setuptools import setup

setup(
    name='pastebin-mirror',
    version='1.2.0',
    description='Mirror Pastebin to an SQLite DB',
    url='http://github.com/brannondorsey/pastebin-mirror',
    author='Brannon Dorsey',
    author_email='brannon@brannondorsey.com',
    license='MIT',
    packages=[
        'pastebin-mirror'
    ],
    install_requires=[
      'requests',
    ],
    zip_safe=False
)
