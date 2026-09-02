"""
Helper module for building Biolink Model category and predicate hierarchies.

This module provides a class, BiolinkManager, that uses the official Biolink
Model Toolkit (``bmt``) as the source of truth for all Biolink logic (categories,
predicates, their metadata, canonical status, domains/ranges, etc.). For a given
Biolink Model version it builds NetworkX directed acyclic graphs (DAGs) for the
category and predicate hierarchies, and converts them into a format suitable for
visualization with Dash Cytoscape.

Any Biolink version can be loaded by pointing ``bmt.Toolkit`` at the raw
biolink-model.yaml for the corresponding GitHub release tag; multiple versions
can coexist in one process. Each loaded version is cached in-process by the app,
so a given version's schema is fetched at most once per process.

Partially inspired by https://github.com/RTXteam/RTX/tree/master/code/ARAX/BiolinkHelper
"""
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional, Set, Union

import networkx as nx
import requests
from bmt import Toolkit
from bmt.utils import sentencecase_to_camelcase, sentencecase_to_snakecase
from networkx.readwrite import json_graph

# --- Constants ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT_CATEGORY = "NamedThing"
DEFAULT_ROOT_PREDICATE = "related_to"
ROOT_CATEGORY_ENGLISH = "named thing"
ROOT_PREDICATE_ENGLISH = "related to"
CORE_NX_PROPERTIES = {"id", "source", "target"}
GITHUB_TAGS_URL = "https://api.github.com/repos/biolink/biolink-model/tags"
GITHUB_RAW_CONTENT_URL_TEMPLATE = "https://raw.githubusercontent.com/biolink/biolink-model/{version_tag}/biolink-model.yaml"
SCHEMA_CACHE_DIR = f"{SCRIPT_DIR}/schema_cache"
TAGS_CACHE_FILENAME = "tags_cache.json"
TAGS_CACHE_EXPIRY_MINUTES = 5
# bmt.Toolkit requires a predicate map; we don't rely on it (inverses are derived
# from the schema itself), and older Biolink versions lack predicate_mapping.yaml,
# so we always pass this minimal valid map to keep loading fast and version-agnostic.
EMPTY_PREDICATE_MAP = {"predicate mappings": []}

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s',
                    handlers=[logging.StreamHandler()])


def get_biolink_github_tags() -> List[str]:
    tags_cache_path = f"{SCRIPT_DIR}/{TAGS_CACHE_FILENAME}"
    no_cache_exists = not os.path.exists(tags_cache_path)
    now = datetime.now()
    if no_cache_exists or (now - datetime.fromtimestamp(os.path.getmtime(tags_cache_path))
                           >= timedelta(minutes=TAGS_CACHE_EXPIRY_MINUTES)):
        # Our cache is stale, so we'll update it
        logging.info(f"Updating github tags cache..")
        tags = []
        page = 1
        per_page = 100  # GitHub's max per page
        while True:
            url = f"{GITHUB_TAGS_URL}?page={page}&per_page={per_page}"
            response = requests.get(url)
            if response.status_code != 200:
                raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
            page_tags = response.json()
            if not page_tags:
                break
            tags.extend(page_tags)
            page += 1

        # Save the updated tags to our cache
        tag_names = [tag["name"] for tag in tags]
        with open(tags_cache_path, "w+") as tags_cache_file:
            json.dump(tag_names, tags_cache_file, indent=2)

        return tag_names
    else:
        logging.info(f"Loading cached GitHub tags..")
        with open(tags_cache_path, "r") as tags_cache_file:
            tag_names = json.load(tags_cache_file)

    return tag_names


class BiolinkManager:

    def __init__(self, biolink_version: Optional[str] = None):
        """
        Initializes the BiolinkManager.

        Determines the Biolink version to use, loads it via bmt.Toolkit (fetching
        and caching the schema as needed), and builds the category and predicate
        DAGs plus their Dash Cytoscape representations.

        Args:
            biolink_version: The specific Biolink version number (e.g. "4.2.2") to
                use. If None, the latest version from GitHub tags will be used.
        """
        self.root_category: str = DEFAULT_ROOT_CATEGORY
        self.root_predicate: str = DEFAULT_ROOT_PREDICATE
        self.core_nx_properties: Set[str] = CORE_NX_PROPERTIES

        self.biolink_tags = get_biolink_github_tags()
        self.biolink_tags_set = set(self.biolink_tags)
        self.latest_tag = self.biolink_tags[0]
        self.biolink_version = biolink_version if biolink_version else self.latest_tag.lstrip("v")
        self.biolink_tag = f"v{self.biolink_version}" if f"v{self.biolink_version}" in self.biolink_tags_set else self.biolink_version

        logging.info(f"Biolink version to use is {self.biolink_version}, latest tag is {self.latest_tag}")
        self.toolkit = self.load_toolkit()
        # Prefer the version reported by the schema itself, when available
        try:
            schema_version = self.toolkit.get_model_version()
            if schema_version:
                self.biolink_version = schema_version
        except Exception:
            pass

        self.category_dag = self.build_category_dag()
        self.category_dag_dash = self.convert_to_dash_format(self.category_dag)
        self.predicate_dag = self.build_predicate_dag()
        self.predicate_dag_dash = self.convert_to_dash_format(self.predicate_dag)

        logging.info(f"Done loading BiolinkManager for version {self.biolink_version}.")

    # ------------------------------ Schema Loading ------------------------------ #

    def load_toolkit(self) -> Toolkit:
        """
        Builds a bmt.Toolkit for this version's schema.

        Primary path: load straight from the raw GitHub URL for the version tag.
        This matters because recent Biolink schemas are modular and pull in sibling
        YAML files via relative imports, which linkml resolves against the source
        location. The result is cached per-version in the app, so each version is
        fetched at most once per process.

        Fallback path: some older (single-file) Biolink YAMLs contain literal tab
        characters that linkml's strict YAML parser rejects. If the URL load fails,
        download the YAML, replace tabs with spaces, and load from that local copy.
        """
        request_url = GITHUB_RAW_CONTENT_URL_TEMPLATE.format(version_tag=self.biolink_tag)
        logging.info(f"Loading Biolink schema from {request_url}")
        try:
            return Toolkit(schema=request_url, predicate_map=EMPTY_PREDICATE_MAP)
        except Exception as url_error:
            logging.warning(f"Direct schema load failed ({url_error}); retrying with a sanitized local copy.")
            return self.load_toolkit_from_sanitized_copy(request_url)

    def load_toolkit_from_sanitized_copy(self, request_url: str) -> Toolkit:
        """Downloads the schema, replaces tab characters with spaces, and loads it locally."""
        response = requests.get(request_url, timeout=30)
        response.raise_for_status()
        # expandtabs(1) turns each tab into a single space, which fixes the
        # "tab where indentation space is expected" errors in some older versions.
        sanitized_yaml = response.text.expandtabs(1)
        os.makedirs(SCHEMA_CACHE_DIR, exist_ok=True)
        local_path = f"{SCHEMA_CACHE_DIR}/biolink-model_{self.biolink_version}.yaml"
        with open(local_path, "w") as schema_file:
            schema_file.write(sanitized_yaml)
        return Toolkit(schema=local_path, predicate_map=EMPTY_PREDICATE_MAP)

    # ------------------------------ DAG Building -------------------------------- #

    def build_category_dag(self) -> nx.DiGraph:
        logging.info(f"Building category graph..")
        category_dag = nx.DiGraph()
        tk = self.toolkit

        # NOTE: 'classes' includes some things that aren't categories; we filter below
        for class_name_english in tk.get_all_classes(formatted=False):
            element = tk.get_element(class_name_english)
            if element is None:
                continue
            class_name = sentencecase_to_camelcase(class_name_english)

            # Record relationship between this node and its parent, if provided
            if element.is_a:
                category_dag.add_edge(sentencecase_to_camelcase(element.is_a), class_name)
            # Record relationship between this node and any direct mixins (treat same as is_a)
            for mixin_english in (element.mixins or []):
                category_dag.add_edge(sentencecase_to_camelcase(mixin_english), class_name)

            # Record node metadata
            self.add_node_if_doesnt_exist(category_dag, class_name)
            self.record_common_metadata(category_dag.nodes[class_name], element)

        # Last, filter out things that are not categories ('classes' includes other things too..)
        non_category_node_ids = [node_id for node_id, data in category_dag.nodes(data=True)
                                 if not (self.root_category in self.get_ancestors(category_dag, node_id)
                                         or data.get("is_mixin"))]
        for non_category_node_id in non_category_node_ids:
            category_dag.remove_node(non_category_node_id)

        return category_dag

    def build_predicate_dag(self) -> nx.DiGraph:
        logging.info(f"Building predicate graph..")
        predicate_dag = nx.DiGraph()
        tk = self.toolkit

        # NOTE: 'slots' includes some things that aren't predicates; we filter below.
        # Unlike before, we now include ALL predicates (canonical and non-canonical).
        for slot_name_english in tk.get_all_slots(formatted=False):
            element = tk.get_element(slot_name_english)
            if element is None:
                continue
            slot_name = sentencecase_to_snakecase(slot_name_english)

            self.add_node_if_doesnt_exist(predicate_dag, slot_name)
            node = predicate_dag.nodes[slot_name]
            node["is_symmetric"] = bool(element.symmetric)
            node["is_canonical"] = bool(tk.is_translator_canonical_predicate(slot_name_english))
            node["domain"] = sentencecase_to_camelcase(element.domain) if element.domain else None
            node["range"] = sentencecase_to_camelcase(element.range) if element.range else None
            if element.inverse:
                node["inverse"] = sentencecase_to_snakecase(element.inverse)
            # 'opposite of' is recorded as an annotation (distinct from 'inverse')
            opposite_ann = (element.annotations or {}).get("opposite_of")
            if opposite_ann is not None:
                opposite_val = getattr(opposite_ann, "value", opposite_ann)
                if opposite_val:
                    node["opposite_of"] = sentencecase_to_snakecase(opposite_val)
            self.record_common_metadata(node, element)

            # Record relationship between this node and its parent, if provided
            if element.is_a:
                parent_name = sentencecase_to_snakecase(element.is_a)
                predicate_dag.add_edge(parent_name, slot_name, id=f"{parent_name}--{slot_name}")
            # Record relationship between this node and any direct mixins (treat same as is_a)
            for mixin_english in (element.mixins or []):
                mixin_name = sentencecase_to_snakecase(mixin_english)
                predicate_dag.add_edge(mixin_name, slot_name, id=f"{mixin_name}--{slot_name}")

        # Last, filter out things that are not predicates ('slots' includes other things too..)
        non_predicate_node_ids = [node_id for node_id, data in predicate_dag.nodes(data=True)
                                  if not (self.root_predicate in self.get_ancestors(predicate_dag, node_id)
                                          or data.get("is_mixin"))]
        for non_predicate_node_id in non_predicate_node_ids:
            predicate_dag.remove_node(non_predicate_node_id)

        # Fill in inverse relationships in both directions (the schema records them on one side only)
        for node_id, data in list(predicate_dag.nodes(data=True)):
            inverse_id = data.get("inverse")
            if inverse_id and predicate_dag.has_node(inverse_id) and not predicate_dag.nodes[inverse_id].get("inverse"):
                predicate_dag.nodes[inverse_id]["inverse"] = node_id

        return predicate_dag

    @staticmethod
    def record_common_metadata(node: dict, element) -> None:
        """Records description/notes/aliases metadata shared by categories and predicates."""
        node["is_mixin"] = bool(element.mixin)
        if element.description:
            node["description"] = element.description
        if element.notes:
            node["notes"] = list(element.notes)
        if element.aliases:
            node["aliases"] = list(element.aliases)

    # ------------------------------ Dash Conversion ----------------------------- #

    def convert_to_dash_format(self, nx_dag: nx.DiGraph) -> List[dict]:
        graph_type = "predicates" if self.root_predicate in nx_dag.nodes() else "categories"
        dict_dag = json_graph.node_link_data(nx_dag, edges="edges")
        dash_nodes = [{"data": {"id": node["id"],
                                "label": node["id"],
                                "attributes": self.extract_attributes(node)},
                       "classes": self.get_node_classes(node, graph_type)}
                      for node in dict_dag["nodes"]]
        dash_edges = [{"data": {"source": edge["source"],
                                "target": edge["target"],
                                "attributes": self.extract_attributes(edge)}}
                      for edge in dict_dag["edges"]]
        return dash_nodes + dash_edges

    def extract_attributes(self, nx_item: dict) -> dict:
        return {prop_name: value for prop_name, value in nx_item.items()
                if prop_name not in self.core_nx_properties}

    def get_node_classes(self, dag_node: dict, graph_type: str) -> str:
        classes = set()
        if dag_node.get("is_mixin"):
            classes.add("mixin")
        if graph_type == "predicates":
            classes.add("canonical" if dag_node.get("is_canonical") else "noncanonical")
            if ((not dag_node.get("domain") or dag_node["domain"] == self.root_category) and
                    (not dag_node.get("range") or dag_node["range"] == self.root_category)):
                classes.add("unspecific")
        return " ".join(classes)

    # ------------------------------ Graph Helpers ------------------------------- #

    @staticmethod
    def add_node_if_doesnt_exist(nx_graph: nx.DiGraph, node_id: str):
        if not nx_graph.has_node(node_id):
            nx_graph.add_node(node_id)

    def get_ancestors(self, nx_graph: nx.DiGraph, node_ids: Union[str, set, list]) -> Set[str]:
        node_ids = self.convert_to_set(node_ids)
        all_ancestors = [set(nx.ancestors(nx_graph, node_id)) for node_id in node_ids]
        unique_ancestors = node_ids.union(*all_ancestors)
        return unique_ancestors

    def get_descendants(self, nx_graph: nx.DiGraph, node_ids: Union[str, set, list]) -> Set[str]:
        node_ids = self.convert_to_set(node_ids)
        all_descendants = [set(nx.descendants(nx_graph, node_id)) for node_id in node_ids]
        unique_descendants = node_ids.union(*all_descendants)
        return unique_descendants

    @staticmethod
    def convert_to_set(item: any) -> set:
        if isinstance(item, set):
            return item
        elif isinstance(item, list):
            return set(item)
        elif item:
            return {item}
        else:
            return set()


def main():
    bm = BiolinkManager()
    print(f"Loaded Biolink {bm.biolink_version}: "
          f"{bm.category_dag.number_of_nodes()} categories, "
          f"{bm.predicate_dag.number_of_nodes()} predicates.")


if __name__ == "__main__":
    main()
