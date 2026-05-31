"""Compatibility setup entry point for older pip and setuptools versions."""

from setuptools import find_packages, setup


setup(
    name="llm-workflow-engine",
    version="0.1.0",
    description="A local-first workflow harness for reliable AI agent automation",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="ymtzsbj",
    license="MIT",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.9",
    entry_points={"console_scripts": ["llm-workflow=llm_workflow_engine.cli:main"]},
)
