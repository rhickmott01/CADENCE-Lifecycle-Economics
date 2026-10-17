import argparse
from cadence_lifecycle.hazus import export_partition
p=argparse.ArgumentParser();p.add_argument("partition");p.add_argument("output")
a=p.parse_args();print(export_partition(a.partition,a.output))
