from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in solve_ninja/__init__.py
from solve_ninja import __version__ as version

setup(
	name="solve_ninja",
	version=version,
	description="This app is created to support ReapBenefit specific use cases",
	author="ReapBenefit",
	author_email="info@reapbenefit.org",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
