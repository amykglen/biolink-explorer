"""
Helper module for downloading and processing Biolink Model data.

This module provides a class, BiolinkManager, to fetch Biolink Model
releases (YAML format) from GitHub, cache them locally as JSON, and build
NetworkX directed acyclic graphs (DAGs) for Biolink categories and predicates.
It includes functionality to handle Biolink versions, caching, and conversion
to formats suitable for visualization libraries like Dash Cytoscape.

Partially inspired by https://github.com/RTXteam/RTX/tree/master/code/ARAX/BiolinkHelper
"""
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List, Union, Set

import networkx as nx
import requests
import yaml
from networkx.readwrite import json_graph

# --- Constants ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT_CATEGORY = "NamedThing"
DEFAULT_ROOT_PREDICATE = "related_to"
CORE_NX_PROPERTIES = {"id", "source", "target"}
GITHUB_TAGS_URL = "https://api.github.com/repos/biolink/biolink-model/tags"
GITHUB_RAW_CONTENT_URL_TEMPLATE = "https://raw.githubusercontent.com/biolink/biolink-model/{version_tag}/biolink-model.yaml"
TAGS_CACHE_FILENAME = "tags_cache.json"
TAGS_CACHE_EXPIRY_MINUTES = 5

# --- Logging Configuration ---
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s: %(message)s',
                    handlers=[logging.StreamHandler()])


class BiolinkManager:

    def __init__(self, biolink_version: Optional[str] = None):
        """
        Initializes the BiolinkManager.

        Fetches Biolink tags, determines the version to use, downloads or loads
        the Biolink model data, and builds the category and predicate DAGs.

        Args:
            biolink_version: The specific Biolink version number (e.g., "4.1.0")
                to use. If None, the latest version from GitHub tags will be used.
        """
        self.root_category: str = DEFAULT_ROOT_CATEGORY
        self.root_predicate: str = DEFAULT_ROOT_PREDICATE
        self.core_nx_properties: Set[str] = CORE_NX_PROPERTIES

        self.biolink_tags = self.get_biolink_github_tags()
        self.biolink_tags_set = set(self.biolink_tags)
        self.latest_tag = self.biolink_tags[0]
        self.biolink_version = biolink_version if biolink_version else self.latest_tag.lstrip("v")
        self.biolink_tag = f"v{self.biolink_version}" if f"v{self.biolink_version}" in self.biolink_tags_set else self.biolink_version
        self.biolink_local_path = f"{SCRIPT_DIR}/biolink_model_{self.biolink_version}.json"

        logging.info(f"Biolink version to use is {self.biolink_version}, latest tag is {self.latest_tag}")
        self.biolink_model_raw = self.download_biolink_model()

        self.category_dag = self.build_category_dag()
        self.category_dag_dash = self.convert_to_dash_format(self.category_dag)
        self.predicate_dag = self.build_predicate_dag()
        self.predicate_dag_dash = self.convert_to_dash_format(self.predicate_dag)

        logging.info(f"Done loading BiolinkManager.")

    def download_biolink_model(self) -> dict:
        if os.path.exists(self.biolink_local_path):
            # Load the cached Biolink Model file
            logging.info(f"Loading cached Biolink file ({self.biolink_local_path})")
            with open(self.biolink_local_path, "r") as biolink_json_file:
                return json.load(biolink_json_file)
        else:
            # Otherwise grab the Biolink Model yaml from GitHub
            logging.info(f"Grabbing Biolink Model YAML from GitHub")
            request_url = GITHUB_RAW_CONTENT_URL_TEMPLATE.format(version_tag=self.biolink_tag)
            response = requests.get(request_url, timeout=10)
            if response.status_code == 200:
                biolink_dict = yaml.safe_load(response.text)
                with open(self.biolink_local_path, "w+") as biolink_json_file:
                    json.dump(biolink_dict, biolink_json_file, indent=2)
                return biolink_dict
            else:
                logging.error(f"ERROR: Request to get Biolink {self.biolink_version} YAML file returned "
                                   f"{response.status_code} response. Cannot load Biolink Model data.")
                return dict()

    def build_category_dag(self) -> nx.DiGraph:
        logging.info(f"Building category graph..")
        category_dag = nx.DiGraph()

        for class_name_english, info in self.biolink_model_raw["classes"].items():
            class_name = self.convert_to_camelcase(class_name_english)
            # Record relationship between this node and its parent, if provided
            parent_name_english = info.get("is_a")
            if parent_name_english:
                parent_name = self.convert_to_camelcase(parent_name_english)
                category_dag.add_edge(parent_name, class_name)
            # Record relationship between this node and any direct 'mixins', if provided (treat same as is_a)
            direct_mappings_english = info.get("mixins", [])
            direct_mappings = {self.convert_to_camelcase(mapping_english)
                               for mapping_english in direct_mappings_english}
            for direct_mapping in direct_mappings:
                category_dag.add_edge(direct_mapping, class_name)

            # Record node metadata
            self.add_node_if_doesnt_exist(category_dag, class_name)
            node = category_dag.nodes[class_name]
            node["is_mixin"] = True if info.get("mixin") else False
            if info.get("description"):
                node["description"] = info["description"]
            if info.get("notes"):
                node["notes"] = info["notes"]
            if info.get("aliases"):
                node["aliases"] = info["aliases"]

        # Last, filter out things that are not categories (Biolink 'classes' includes other things too..)
        non_category_node_ids = [node_id for node_id, data in category_dag.nodes(data=True)
                                 if not (self.root_category in self.get_ancestors(category_dag, node_id)
                                         or data.get("is_mixin"))]
        for non_category_node_id in non_category_node_ids:
            category_dag.remove_node(non_category_node_id)

        return category_dag

    def build_predicate_dag(self) -> nx.DiGraph:
        logging.info(f"Building predicate graph..")
        predicate_dag = nx.DiGraph()

        # NOTE: 'slots' includes some things that aren't predicates, but we don't care; doesn't hurt to include them
        for slot_name_english, info in self.biolink_model_raw["slots"].items():
            slot_name = self.convert_to_snakecase(slot_name_english)

            # Only record this if it's a canonical predicate
            # NOTE: I think only predicates that have two forms are labeled as 'canonical'; single-form are not
            labeled_as_canonical = self.determine_if_labeled_canonical(info)
            has_inverse_specified = info.get("inverse")
            if labeled_as_canonical or not has_inverse_specified:
                self.add_node_if_doesnt_exist(predicate_dag, slot_name)
                # Record node metadata
                node = predicate_dag.nodes[slot_name]
                node["is_symmetric"] = True if info.get("symmetric") else False
                node["is_mixin"] = True if info.get("mixin") else False
                node["domain"] = self.convert_to_camelcase(info.get("domain"))
                node["range"] = self.convert_to_camelcase(info.get("range"))
                if info.get("description"):
                    node["description"] = info["description"]
                if info.get("notes"):
                    node["notes"] = info["notes"]
                if info.get("aliases"):
                    node["aliases"] = info["aliases"]

                # Record relationship between this node and its parent, if provided
                parent_name_english = info.get("is_a")
                if parent_name_english:
                    parent_name = self.convert_to_snakecase(parent_name_english)
                    predicate_dag.add_edge(parent_name, slot_name, id=f"{parent_name}--{slot_name}")
                # Record relationship between this node and any direct 'mixins', if provided (treat same as is_a)
                direct_mappings_english = info.get("mixins", [])
                direct_mappings = {self.convert_to_snakecase(mapping_english)
                                   for mapping_english in direct_mappings_english}
                for direct_mapping in direct_mappings:
                    predicate_dag.add_edge(direct_mapping, slot_name, id=f"{direct_mapping}--{slot_name}")

        # Last, filter out things that are not predicates (Biolink 'slots' includes other things too..)
        non_predicate_node_ids = [node_id for node_id, data in predicate_dag.nodes(data=True)
                                  if not (self.root_predicate in self.get_ancestors(predicate_dag, node_id)
                                          or data.get("is_mixin"))]
        for non_predicate_node_id in non_predicate_node_ids:
            predicate_dag.remove_node(non_predicate_node_id)

        return predicate_dag

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
            if ((not dag_node.get("domain") or dag_node["domain"] == self.root_category) and
                    (not dag_node.get("range") or dag_node["range"] == self.root_category)):
                classes.add("unspecific")
        return " ".join(classes)

    @staticmethod
    def convert_to_camelcase(english_term: Optional[str]) -> Optional[str]:
        if isinstance(english_term, str):
            return "".join([f"{word[0].upper()}{word[1:]}" for word in english_term.split(" ")])
        else:
            return english_term

    @staticmethod
    def convert_to_snakecase(english_term: str) -> Optional[str]:
        return english_term.replace(' ', '_')

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

    @staticmethod
    def determine_if_labeled_canonical(node_info: dict) -> bool:
        annotations = node_info.get("annotations")
        if isinstance(annotations, dict):
            if "canonical_predicate" in annotations:
                return True
        elif isinstance(annotations, list):  # Appears in some older Biolink versions (e.g., 2.2.1)
            if any(item for item in annotations
                   if item.get("value") and (item.get("tag") == "biolink:canonical_predicate" or item.get("tag") == "canonical_predicate")):
                return True
        return False

    @staticmethod
    def get_biolink_github_tags() -> List[str]:
        tags_cache_path = f"{SCRIPT_DIR}/tags_cache.json"
        no_cache_exists = not os.path.exists(tags_cache_path)
        now = datetime.now()
        if no_cache_exists or (now - datetime.fromtimestamp(os.path.getmtime(tags_cache_path)) >= timedelta(minutes=5)):
            # Our cache is stale, so we'll update it
            logging.info(f"Updating github tags cache..")
            tags = []
            page = 1
            per_page = 100  # GitHub's max per page
            while True:
                url = f"https://api.github.com/repos/biolink/biolink-model/tags?page={page}&per_page={per_page}"
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


def main():
    downloader = BiolinkManager()


if __name__ == "__main__":
    main()
