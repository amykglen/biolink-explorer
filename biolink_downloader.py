"""
Helper module based off of https://github.com/RTXteam/RTX/blob/master/code/ARAX/BiolinkHelper/biolink_helper.py.
"""
import json
import os
from typing import Optional, List, Tuple

import networkx as nx
import requests
import yaml
from networkx.readwrite import json_graph

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class BiolinkDownloader:

    def __init__(self, biolink_version: Optional[str] = None):
        self.biolink_version = biolink_version if biolink_version else "master"  # Default to latest version
        self.biolink_yaml_url = f"https://raw.githubusercontent.com/biolink/biolink-model/{self.biolink_version}/biolink-model.yaml"
        self.biolink_yaml_vurl = f"https://raw.githubusercontent.com/biolink/biolink-model/v{self.biolink_version}/biolink-model.yaml"
        self.root_category = "NamedThing"
        self.root_predicate = "related_to"
        self.core_nx_properties = {"id", "source", "target"}
        self.biolink_model_raw = self.download_biolink_model()
        self.category_dag = self.build_category_dag()
        self.category_dag_dash = self.convert_to_dash_format(self.category_dag)

        with open(f"{SCRIPT_DIR}/category_dag_dash.json", "w+") as category_file:
            json.dump(self.category_dag_dash, category_file, indent=2)

    def download_biolink_model(self) -> dict:
        response = requests.get(self.biolink_yaml_url, timeout=10)
        if response.status_code != 200:  # Sometimes Biolink's tags start with 'v', so try that
            response = requests.get(self.biolink_yaml_vurl, timeout=10)
        if response.status_code == 200:
            return yaml.safe_load(response.text)
        else:
            raise RuntimeError(f"ERROR: Request to get Biolink {self.biolink_version} YAML file returned "
                               f"{response.status_code} response. Cannot load BiolinkHelper.")

    def build_category_dag(self) -> dict:
        category_dag = nx.DiGraph()

        for class_name_english, info in self.biolink_model_raw["classes"].items():
            class_name = self.convert_to_biolink_camelcase(class_name_english)
            # Record relationship between this node and its parent, if provided
            parent_name_english = info.get("is_a")
            if parent_name_english:
                parent_name = self.convert_to_biolink_camelcase(parent_name_english)
                category_dag.add_edge(parent_name, class_name)
            # Record relationship between this node and any direct 'mixins', if provided (treat same as is_a)
            direct_mappings_english = info.get("mixins", [])
            direct_mappings = {self.convert_to_biolink_camelcase(mapping_english)
                               for mapping_english in direct_mappings_english}
            for direct_mapping in direct_mappings:
                category_dag.add_edge(direct_mapping, class_name)

            # Record node metadata
            self.add_node_if_doesnt_exist(category_dag, class_name)
            category_dag.nodes[class_name]["is_mixin"] = True if info.get("mixin") else False

        # Last, filter out things that are not categories (Biolink 'classes' includes other things too..)
        non_category_node_ids = [node_id for node_id, data in category_dag.nodes(data=True)
                                 if not (self.root_category in self.get_ancestors_nx(category_dag, node_id)
                                         or data.get("is_mixin"))]
        for non_category_node_id in non_category_node_ids:
            category_dag.remove_node(non_category_node_id)


        graph_dict = json_graph.node_link_data(category_dag, edges="edges")
        print(type(graph_dict))

        with open(f"{SCRIPT_DIR}/category_dag.json", "w+") as category_file:
            json.dump(graph_dict, category_file, indent=2)

        return graph_dict

    def convert_to_dash_format(self, nx_dag_dict: dict) -> List[dict]:
        dash_nodes = [{"data": {"id": node["id"],
                                "label": node["id"],
                                "attributes": self.extract_attributes(node)}}
                      for node in nx_dag_dict["nodes"]]
        dash_edges = [{"data": {"source": edge["source"],
                                "target": edge["target"],
                                "attributes": self.extract_attributes(edge)}}
                      for edge in nx_dag_dict["edges"]]
        return dash_nodes + dash_edges

    def extract_attributes(self, nx_item: dict) -> dict:
        return {prop_name: value for prop_name, value in nx_item.items()
                if prop_name not in self.core_nx_properties}

    @staticmethod
    def convert_to_biolink_camelcase(english_term: str):
        return "".join([f"{word[0].upper()}{word[1:]}" for word in english_term.split(" ")])

    @staticmethod
    def convert_to_biolink_snakecase(english_term: str):
        return english_term.replace(' ', '_')

    @staticmethod
    def add_node_if_doesnt_exist(nx_graph: nx.DiGraph, node_id: str):
        if not nx_graph.has_node(node_id):
            nx_graph.add_node(node_id)

    @staticmethod
    def get_ancestors_nx(nx_graph: nx.DiGraph, node_id: str) -> List[str]:
        return list(nx.ancestors(nx_graph, node_id).union({node_id}))

    @staticmethod
    def get_descendants_nx(nx_graph: nx.DiGraph, node_id: str) -> List[str]:
        return list(nx.descendants(nx_graph, node_id).union({node_id}))

def main():
    downloader = BiolinkDownloader()


if __name__ == "__main__":
    main()
