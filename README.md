# Biolink Model Explorer

A Dash web application for visualizing and exploring the category and predicate hierarchies of the [Biolink Model](https://biolink.github.io/biolink-model/), deployed [here](https://biolink-explorer-app-286f906f6294.herokuapp.com/).

## Features

* Visualize Biolink Model category and predicate hierarchies.
* Search for specific categories/predicates.
* Filter by mixin status and predicate domain/range.
* View details for selected categories/predicates.
* Select different Biolink Model versions to explore dynamically.

## Prerequisites

* Python 3.12
* pip (Python package installer)
* Git (for cloning the repository)

## Setup and Installation

1.  Clone the repository and `cd` into it.
2.  Create and activate a Python 3.12 virtual environment.
3.  Run `pip install -r requirements.txt`
4.  Start the Dash server with: `python app.py`
5.  View the application in your browser at: http://127.0.0.1:8050