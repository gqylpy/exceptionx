import setuptools

setuptools.setup(
    name='exceptionx',
    version='4.1.4',
    author='Unnamed great master',
    author_email='<gqylpy@outlook.com>',
    license='MIT',
    url='http://gqylpy.com',
    project_urls={'Source': 'https://github.com/gqylpy/exceptionx'},
    description='''
        The `exceptionx` is a flexible and convenient Python exception handling
        library that allows you to dynamically create exception classes and
        provides various exception handling mechanisms.
    '''.strip().replace('\n       ', ''),
    long_description=open('README.md', encoding='utf8').read(),
    long_description_content_type='text/markdown',
    packages=['exceptionx'],
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: Chinese (Simplified)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Bug Tracking',
        'Topic :: Software Development :: Widget Sets',
        'Topic :: Artistic Software',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13'
    ]
)
