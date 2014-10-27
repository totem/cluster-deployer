"""
Module for updating/searching elastic search.
"""
from elasticsearch import Elasticsearch


def get_search_client():
    return Elasticsearch(hosts='localhost')

if __name__ == "__main__":
    es = get_search_client()
    es.index('cluster-deployer', 'deployments', {
        "meta-info": {
            "github": {
                "branch": "master",
                "commit": "9b3597b9da3957df7a91207ef4332d1efb400d7d",
                "owner": "totem",
                "repo": "spec-python"
            },
        }
    }, id='spec-python-develop+v1')
