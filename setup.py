"""Setup script for the project."""

from setuptools import setup, find_packages

setup(
    name="ai-meal-planner",
    version="1.0.0",
    description="AI Agentic Meal Planning Application",
    packages=find_packages(),
    install_requires=[
        # Dependencies are in requirements.txt
    ],
    python_requires=">=3.10",
)

