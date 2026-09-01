# Biolink Model Explorer

A Dash web application for visualizing and exploring the category and predicate hierarchies of the [Biolink Model](https://biolink.github.io/biolink-model/), deployed [here](https://biolink-explorer-app-286f906f6294.herokuapp.com/).

All Biolink logic (categories, predicates, their metadata, canonical status, domains/ranges, etc.) is powered by the official [Biolink Model Toolkit (`bmt`)](https://github.com/biolink/biolink-model-toolkit), and any Biolink Model version can be loaded on the fly.

## Features

* Visualize Biolink Model category and predicate hierarchies as a left-to-right tree.
* View **all** predicates, with canonical predicates visually distinguished from non-canonical ones.
* Search for specific categories/predicates (filters to their lineages).
* Filter by mixin status and predicate domain/range.
* View details for a selected category/predicate (description, domain/range, canonical status, inverse, etc.).
* Switch between different Biolink Model versions dynamically.

## Prerequisites

* Python 3.12
* [uv](https://docs.astral.sh/uv/) (Python package/dependency manager)
* Git (for cloning the repository)

## Setup and Installation

1.  Clone the repository and `cd` into it.
2.  Install dependencies (uv creates the virtual environment automatically):
    ```bash
    uv sync
    ```
3.  Start the Dash server:
    ```bash
    uv run python main.py
    ```
4.  View the application in your browser at: http://127.0.0.1:8050
