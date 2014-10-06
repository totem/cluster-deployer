# cluster-deployer [![Build Status](https://travis-ci.org/totem/cluster-deployer.svg)](https://travis-ci.org/totem/cluster-deployer)
[![Coverage Status](https://coveralls.io/repos/totem/cluster-deployer/badge.png)](https://coveralls.io/r/totem/cluster-deployer)
[![Documentation Status](https://readthedocs.org/projects/cluster-deployer/badge/?version=latest)](https://readthedocs.org/projects/cluster-deployer/?badge=latest)


Totem Cluster Deployer

It provides the ability to deploy applications to a fleet cluster. It adds a layer of abstraction 
and provides a simple RESTFul API for the deployment. For deploying using totem, it also participates
in SWF Workflow for completing an end-to-end deployment workflow. 
(The SWF component is configurable and is turned off by default).

## Development Status
This library is currently under development.

## Documentation
Project uses Sphinx for code/api dpcumentation

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
- python 2.7.x  
- Mongo 2.6+  
- Virtualenv (Recommended)
- Python pip

### Dependencies

To install dependencies for the project, run command:  

```
pip install requirements.txt
```

In addition if you are developing on the project, run command: 

```
pip install dev-requirements.txt
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
python local.py
```

It assumes that mongo server (2.6+) is already running locally on port 27017 
and with no credentials. 

Once server is up you can access the root api using:  
[http://localhost:9000](http://localhost:9000)

### Using Docker

In order to run fully integrated server using docker using latest docker , run
command: 

```
sudo docker run -it --rm -h cluster-deployer-${USER} --name cluster-deployer  -e MONGO_HOST=mongodb://172.17.42.1:27017/totem_deployer -e MONGO_RESULTS_DB=totem_deployer -P totem/cluster-deployer
```

## Coding Standards and Guidelines

### flake8
In order to ensure that code follows PEP8 standards, run command: 

```
flake8 .
```
