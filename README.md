# cluster-deployer [![Build Status](https://travis-ci.org/totem/cluster-deployer.svg)](https://travis-ci.org/totem/cluster-deployer) [![Coverage Status](https://coveralls.io/repos/totem/cluster-deployer/badge.png)](https://coveralls.io/r/totem/cluster-deployer) [![Documentation Status](https://readthedocs.org/projects/cluster-deployer/badge/?version=latest)](https://readthedocs.org/projects/cluster-deployer/?badge=latest)

It provides the ability to deploy applications to a fleet cluster. It adds a layer of abstraction 
and provides a simple RESTFul API for the deployment.  

## Development Status
This deployer component is currently under testing.

## Documentation
Project uses Sphinx for code/api documentation

### Location
The latest code/api documentation can be found at:
[http://cluster-deployer.readthedocs.org/](http://cluster-deployer.readthedocs.org/)

### Building documentation
To generate html documentation, use command: 

```
cd docs && make html
```

The documentation will be generated in docs/build folder.

## Requirements

The project has following dependencies  
- python 2.7.x (Fabric library is not compatible with Python 3.x)  
- Virtualenv (Recommended)
- Python pip
- etcd 0.4.6 (Required if using docker based deployment)
- docker 1.2 (Required if using docker based deployment)
- Elasticsearch 1.3+ (Recommended)

### Dependencies

To install dependencies for the project, run command:  

```
pip3 install -r requirements.txt
```

In addition if you are developing on the project, run command: 

```
pip3 install -r dev-requirements.txt
```

## Testing

Tests are located in tests folder. Project uses nose for testing.

### Unit Tests

To run all unit tests , run command :

```
nosetests -w tests/unit
```

## Running Server

### Local (Without celery worker)
To run the server locally (w/o celery worker) , run command:

```
python local-server.py
```

Once server is up you can access the root api using:  
[http://localhost:9000](http://localhost:9000)

### Using Docker

In order to run fully integrated server using docker using latest docker , run
command: 

```
sudo docker run -it --rm -h cluster-deployer-${USER} --name cluster-deployer -P totem/cluster-deployer
```

### Run Configuration (Environment Variables)  
| Env Variable | Description |  Default Value (Local) | Default Value (Docker)|
| ------------ | ----------- | ---------------------- | --------------------- |
| QUAY_ORGANIZATION | Organization in quay to pull images from. This is only required to construct image url when not explictly specified as part of request. | totem | totem|
| ETCD_HOST | Etcd server host. | 127.0.0.1 | 172.17.42.1 |
| ETCD_PORT | Etcd server port. | 4001 | 4001 |
| ETCD_TOTEM_BASE | Base path for totem configurations | /totem | /totem |
| ETCD_YODA_BASE | Base path for yoda proxy configurations | /yoda | /yoda |
| TASK_EXECUTORS | No. of processes to be created for celery task executions | Not Used | 2 |
| API_EXECUTORS | No. of uwsgi processes to be created for serving API | Not Used | 2 |
| HIPCHAT_TOKEN | Default hipchat token to be used for notifications | | |
| GITHUB_TOKEN | Github token for fetching fleet templates and for commit notifications.| | |
| HIPCHAT_ENABLED | Set it to true to enable hipchat notifications | false | false |
| HIPCHAT_ROOM | Room to be used for hipchat notifications | not-set | not-set |
| GITHUB_NOTIFICATION_ENABLED | Set it to true to enable github commit notifications. | false | false |
| BASE_URL | Base Url for Cluster Deployer (used for forming notification URLs)| http://localhost:9000| http://172.17.42.1:9000 |

 

## Coding Standards and Guidelines

### flake8
In order to ensure that code follows PEP8 standards, run command: 

```
flake8 .
```
