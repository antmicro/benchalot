import yaml
from itertools import product
with open("config.yml", 'r') as file:
    config = yaml.safe_load(file)


def product_dict(**kwargs):
    keys = kwargs.keys()
    for instance in product(*kwargs.values()):
        yield dict(zip(keys, instance))


combinations = list(product_dict(**config['matrix']))
print(combinations)
print(len(combinations))
