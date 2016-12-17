from setuptools import setup
import glob
with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(name='fastq-profiler',
      version='0.0.1',
      packages=['fq'],
      description='Summarize fastq files and store associated data.',
      url='https://github.com/danielecook/fastq-profiler',
      author='Daniel E. Cook',
      author_email='danielecook@gmail.com',
      license='MIT',
      install_requires=required,
      entry_points="""
      [console_scripts]
      fqprofile = fq.fqprofile:main
      """,
      zip_safe=False)

